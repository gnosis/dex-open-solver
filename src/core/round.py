import logging
from collections import OrderedDict
from math import floor

import networkx as nx

from .constants import MIN_TRADABLE_AMOUNT
from .order_util import IntegerTraits

logger = logging.getLogger(__name__)


def compute_token_balances(tokens, orders):
    """Compute the (im)balances for all tokens."""
    token_balances = {token: 0 for token in tokens}

    for order in orders:
        token_balances[order.buy_token] -= order.buy_amount
        token_balances[order.sell_token] += order.sell_amount

    return token_balances


def compute_spanning_order_arborescence(orders, fee):
    """Compute a spanning arborescence with fee token as root.

    Arcs correspond to orders and point from sellToken to buyToken.
    The arborescence is computed via Edmond's algorithm.

    Args:
        orders: Orders as list[dict].

    Returns:
        The rooted spanning tree as dict of {child_token -> parent_token}.

    """
    # Force fee token to be root by excluding any edges pointing to it.
    # (use OrderedDict.fromkeys() to remove duplicates while preserving order)
    edges = OrderedDict.fromkeys([
        (o.sell_token, o.buy_token)
        for o in orders if o.buy_token != fee.token
    ])

    G = nx.DiGraph(list(edges))

    logging.debug("Directed edges: {}".format(G.edges))
    logging.debug("{} Touched tokens: {}".format(len(G.nodes), sorted(G.nodes)))

    # Compute spanning arborescence
    arborescence = nx.algorithms.tree.branchings.Edmonds(G).find_optimum()
    return {e[1]: e[0] for e in arborescence.edges}


def round_solution(prices, orders, fee):

    # Iterate over orders and round amounts.
    for order in orders:
        # Make sure order buy_amount is an integer
        order.buy_amount = floor(order.buy_amount)
        # Set exec sell amount according to uniform clearing price.
        order.set_sell_amount_from_buy_amount(prices, fee, IntegerTraits)

    token_balances = compute_token_balances(prices.keys(), orders)
    logging.debug("Token balances (initial):")
    for token, balance in token_balances.items():
        logging.debug("\t%5s : %28d", token, balance)

    # Compute spanning tree of orders with fee token as root.
    tree = compute_spanning_order_arborescence(
        [order for order in orders if order.sell_amount > 0],
        fee
    )

    # Iteratively move rounding errors towards fee token.
    while tree:

        # Find leaf and parent node.
        leaf_token = [
            child for child in tree.keys()
            if child not in tree.values()
        ][0]
        parent_token = tree[leaf_token]

        # Find and adjust order selling tL, buying tP.
        # Sort in decreasing execBuyAmount so that the full rounding
        # procedure touches the less number of orders.
        for order in sorted(orders, key=lambda order: -order.buy_amount):

            if order.buy_token != leaf_token or order.sell_token != parent_token \
               or order.buy_amount == 0:
                continue

            # Amount to be subtracted from order.buy_amount
            buy_amount_delta = min(
                order.buy_amount - MIN_TRADABLE_AMOUNT,
                -token_balances[leaf_token]
            )

            # Skip order if rounding would lead to violation of minimum tradable amount.
            if order.buy_amount - buy_amount_delta < MIN_TRADABLE_AMOUNT:
                continue

            # Skip order if rounding would lead to violation of max sell amount.
            if order.with_buy_amount(order.buy_amount - buy_amount_delta)\
               .get_sell_amount_from_buy_amount(prices, fee, IntegerTraits)\
               > order.max_sell_amount:
                continue

            # Otherwise round order.
            token_balances[leaf_token] += buy_amount_delta
            old_buy_amount, old_sell_amount = order.buy_amount, order.sell_amount
            order.buy_amount -= buy_amount_delta
            order.set_sell_amount_from_buy_amount(prices, fee, IntegerTraits)

            logging.debug("Adjusting order %s:", order.index)
            logging.debug(
                "\t(old) buy_amount : %25d  -- sell_amount: %25d",
                old_buy_amount, old_sell_amount
            )
            logging.debug(
                "\t(new) buy_amount : %25d  -- sell_amount: %25d",
                order.buy_amount, order.sell_amount
            )

            if token_balances[leaf_token] == 0:
                break

        # Compute and check updated token balances.
        token_balances = compute_token_balances(prices.keys(), orders)
        logging.debug("Token balances (after balancing %s):", leaf_token)
        for token, balance in token_balances.items():
            logging.debug("\t%5s : %28d", token, balance)

        # If it is not possible to round, return false.
        # This can happen due to:
        # a) Not enough fee can be sold for b_buy_token.
        # b) There's currently no max_sell_amount buffer.
        # TODO: fix b).
        if token_balances[leaf_token] != 0:
            return False

        del tree[leaf_token]

    return True
