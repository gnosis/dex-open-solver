import logging
from collections import OrderedDict
from fractions import Fraction as F
from math import ceil, floor
from typing import Dict, List, Tuple

import networkx as nx

from .api import Fee
from .constants import (MAX_ROUNDING_VOLUME, MIN_TRADABLE_AMOUNT,
                        PRICE_ESTIMATION_ERROR)
from .order import Order
from .order_util import IntegerTraits

logger = logging.getLogger(__name__)


def compute_token_balances(tokens, orders):
    """Compute the (im)balances for all tokens."""
    token_balances = {token: 0 for token in tokens}

    for order in orders:
        token_balances[order.buy_token] -= order.buy_amount
        token_balances[order.sell_token] += order.sell_amount

    return token_balances


def setup_rounding_buffer(
    orders: List[Order],
    connected_tokens: List[str],
    estimated_token_prices: Dict[str, F],
    fee: Fee
) -> Tuple[Dict[str, Dict], List[Dict]]:
    """Introduce rounding buffer for order sell amounts.

    Args:
        orders: List of orders.
        connected_tokens: List of tokens connected to the fee token.
        estimated_token_prices: Dict of estimated prices for all tokens.
        fee: Fee namedtuple.

    Returns:
        The updated orders.

    """
    # Compute amount of all tokens equivalent to MAX_ROUNDING_VOLUME.
    max_rounding_amounts = {}
    fee_token_price = estimated_token_prices[fee.token]
    for t in connected_tokens:
        assert t in estimated_token_prices

        estimated_price_in_fee_token = F(estimated_token_prices[t]) / F(fee_token_price)
        max_rounding_amount = F(MAX_ROUNDING_VOLUME) / estimated_price_in_fee_token

        max_rounding_amounts[t] = ceil(max_rounding_amount)
        assert max_rounding_amounts[t] >= 1

        # logging.info("Maximum assumed rounding error for [%s] : %20d"
        #             % (t, max_rounding_amounts[t].quantize(Decimal('1e-4'))))

    # Apply rounding buffer to order max sell amounts.
    for o in orders:
        tS, tB = o.sell_token, o.buy_token

        if not all(t in connected_tokens for t in [tS, tB]):
            # Order will never be touched, because of no connection to fee token.
            continue

        # a) Compute rounding buffer:
        # In the current float->int solution rounding, executed buy amounts are
        # adjusted, then executed sell amounts recomputed. We thus need to make
        # sure that expected adjustments on the buy-side will not lead to
        # violations on the sell-side (i.e., exceeding maximum sell amount).
        estimated_xrate = estimated_token_prices[tB] / estimated_token_prices[tS]
        rounding_buffer = max_rounding_amounts[tB] * estimated_xrate
        rounding_buffer = rounding_buffer * PRICE_ESTIMATION_ERROR**2
        rounding_buffer = ceil(rounding_buffer)
        assert rounding_buffer >= 1

        # b) Reduce order max sell amounts.
        old_max_sell_amount = o.max_sell_amount
        new_max_sell_amount = max(old_max_sell_amount - rounding_buffer, 0)

        logging.info(
            "Reducing max sell amount [%s] of order <%s> : %25d --> %25d",
            tS, o.index, old_max_sell_amount, new_max_sell_amount
        )

        assert new_max_sell_amount < old_max_sell_amount or old_max_sell_amount == 0
        o.max_sell_amount = new_max_sell_amount

    return orders


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
