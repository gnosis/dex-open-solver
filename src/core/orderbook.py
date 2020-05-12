import logging
from fractions import Fraction as F
from typing import Dict, List, Tuple

from .config import Config
from .order import Order
from .order_util import IntegerTraits

logger = logging.getLogger(__name__)


def compute_solution_metrics(prices, accounts_updated, orders, fee):
    """Compute objective function values and other metrics."""
    # Init objective values.
    obj = {'volume': 0,
           'utility': 0,
           'utility_disreg': 0,
           'utility_disreg_touched': 0,
           'fees': 0,
           'orders_touched': 0}

    for order in orders:
        if prices[order.buy_token] is None or prices[order.sell_token] is None:
            assert order.buy_amount == 0 and order.sell_amount == 0
            continue
        else:
            sell_token_price = prices[order.sell_token]
            buy_token_price = prices[order.buy_token]

        # Volume (referring to sell amount).
        obj['volume'] += order.sell_amount * sell_token_price

        xrate = F(buy_token_price, sell_token_price)

        # Utility at current prices.
        u = IntegerTraits.compute_utility_term(
            order=order,
            xrate=xrate,
            buy_token_price=buy_token_price,
            fee=fee
        )

        # Compute maximum possible utility analogously to the smart contract
        # (i.e., depending on the remaining token balance after order execution).
        if order.account_id is not None:
            balance_updated = accounts_updated[order.account_id].get(order.sell_token, 0)
        else:
            balance_updated = 0
        umax = IntegerTraits.compute_max_utility_term(
            order=order,
            xrate=xrate,
            buy_token_price=buy_token_price,
            fee=fee,
            balance_updated=balance_updated
        )

        if u > umax:
            logger.warning(
                "Computed utility of <%s> larger than maximum utility:", order.index
            )
            logger.warning("u    = %d", u)
            logger.warning("umax = %d", umax)

        obj['utility'] += u
        obj['utility_disreg'] += max(umax - u, 0)

        if order.sell_amount > 0:
            obj['orders_touched'] += 1
            obj['utility_disreg_touched'] += (umax - u)

            order.utility = u
            order.utility_disreg = (umax - u)

        # Fee amount as net difference of fee token sold/bought.
        if order.sell_token == fee.token:
            obj['fees'] += order.sell_amount
        elif order.buy_token == fee.token:
            obj['fees'] -= order.buy_amount

    return obj


def filter_orders_tokenpair(
    orders: List[Order],
    token_pair: Tuple[str, str]
) -> List[Dict]:
    """Find all orders on a single given token pair.

    Args:
        orders: List of orders.
        tokenpair: Tuple of two token IDs.

    Returns:
        The filtered orders.

    """
    return [
        order for order in orders
        if set(token_pair) == {order.sell_token, order.buy_token}
    ]


def restrict_order_sell_amounts_by_balances(
    orders: List[Order],
    accounts: Dict[str, Dict[str, int]]
) -> List[Dict]:
    """Restrict order sell amounts to available account balances.

    This method also filters out orders that end up with a sell amount of zero.

    Args:
        orders: List of orders.
        accounts: Dict of accounts and their token balances.

    Returns:
        The capped orders.

    """
    orders_capped = []

    # Init dict for remaining balance per account and token pair.
    remaining_balances = {}

    # Iterate over orders sorted by limit price (best -> worse).
    for order in sorted(orders, key=lambda o: o.max_xrate, reverse=True):
        aID, tS, tB = order.account_id, order.sell_token, order.buy_token

        # Init remaining balance for new token pair on some account.
        if (aID, tS, tB) not in remaining_balances:
            sell_token_balance = F(accounts.get(aID, {}).get(tS, 0))
            remaining_balances[(aID, tS, tB)] = sell_token_balance

        # Get sell amount (capped by available account balance).
        sell_amount_old = order.max_sell_amount
        sell_amount_new = min(sell_amount_old, remaining_balances[aID, tS, tB])

        # Skip orders with zero sell amount.
        if sell_amount_new == 0:
            continue
        else:
            assert sell_amount_old > 0

        # Update remaining balance.
        remaining_balances[aID, tS, tB] -= sell_amount_new
        assert remaining_balances[aID, tS, tB] >= 0

        order.max_sell_amount = sell_amount_new

        # Append capped order.
        orders_capped.append(order)

    return orders_capped


def count_nr_exec_orders(orders):
    return sum(order.buy_amount > 0 for order in orders)


def compute_objective(prices, accounts_updated, orders, fee):
    """Compute objective function value of solution."""
    # Init objective values.
    total_u = 0
    total_umax = 0

    for order in orders:
        if prices[order.buy_token] is None or prices[order.sell_token] is None:
            assert order.buy_amount == 0 and order.sell_amount == 0
            continue
        else:
            sell_token_price = prices[order.sell_token]
            buy_token_price = prices[order.buy_token]

        xrate = F(buy_token_price, sell_token_price)

        # Utility at current prices.
        u = IntegerTraits.compute_utility_term(
            order=order,
            xrate=xrate,
            buy_token_price=buy_token_price,
            fee=fee
        )

        # Compute maximum possible utility analogously to the smart contract
        # (i.e., depending on the remaining token balance after order execution).
        if order.account_id is not None:
            balance_updated = accounts_updated[order.account_id].get(order.sell_token, 0)
        else:
            balance_updated = 0
        umax = IntegerTraits.compute_max_utility_term(
            order=order,
            xrate=xrate,
            buy_token_price=buy_token_price,
            fee=fee,
            balance_updated=balance_updated
        )
        umax = max(u, umax)

        total_u += u
        total_umax += umax

    return 2 * total_u - total_umax


# Update accounts from order execution.
def update_accounts(accounts, orders):
    for order in orders:
        account_id = order.account_id
        buy_token = order.buy_token
        sell_token = order.sell_token
        if order.buy_token not in accounts[account_id]:
            accounts[account_id][order.buy_token] = 0
        accounts[account_id][buy_token] = int(accounts[account_id][buy_token])
        accounts[account_id][sell_token] = int(accounts[account_id][sell_token])
        accounts[account_id][buy_token] += order.buy_amount
        accounts[account_id][sell_token] -= order.sell_amount


def compute_connected_tokens(orders, fee_token):
    """Return the list of tokens connected to the fee_token."""
    # Get subsets of tokens bought and sold.
    tokens_sold = {o.sell_token for o in orders}
    tokens_bought = {o.buy_token for o in orders}

    # Create token->[token,...,token] lookup adjacency list,
    # considering only tokens that are both sold and bought.
    token_adjacency = {
        token: set()
        for token in tokens_sold.intersection(tokens_bought).union({fee_token})
    }

    for order in orders:
        sell_token, buy_token = order.sell_token, order.buy_token
        if all(t in token_adjacency.keys() for t in [sell_token, buy_token]):
            token_adjacency[buy_token].add(sell_token)
            token_adjacency[sell_token].add(buy_token)

    # Breadth-first search: keep adding adjacent tokens until all visited.
    # The loop below has at most len(tokens) iterations.
    connected_tokens = [fee_token]
    cur_token_idx = 0
    while len(connected_tokens) > cur_token_idx:
        cur_token = connected_tokens[cur_token_idx]
        # new_tokens: All tokens directly connected to cur_token that are
        # not yet visited but must be visited eventually.
        new_tokens = token_adjacency[cur_token] - set(connected_tokens)
        connected_tokens += list(new_tokens)
        cur_token_idx += 1

    # Return the set of visited tokens.
    return set(connected_tokens)


def compute_total_fee(orders, prices, fee, arith_traits):
    """Compute total fee in the solution."""
    sold_fee = sum(
        order.get_sell_amount_from_buy_amount(prices, fee, arith_traits)
        for order in orders if order.sell_token == fee.token
    )
    bought_fee = sum(
        order.buy_amount
        for order in orders if order.buy_token == fee.token
    )
    return sold_fee - bought_fee


def compute_average_order_fee(orders, prices, fee, arith_traits):
    return compute_total_fee(orders, prices, fee, arith_traits) \
        / count_nr_exec_orders(orders)


def is_economic_viable(orders, prices, fee, arith_traits):
    # Trivial solution is economically viable.
    if count_nr_exec_orders(orders) == 0:
        return True

    # Shortcut to avoid computing fees.
    if Config.MIN_AVERAGE_ORDER_FEE == 0:
        return True

    average_order_fee = compute_average_order_fee(orders, prices, fee, arith_traits)

    # Compute average fees.
    return average_order_fee >= Config.MIN_AVERAGE_ORDER_FEE


def is_trivial(orders):
    return count_nr_exec_orders(orders) == 0


# Note: this is an approximation, there is no guarantee that the returned
# subset is economically viable (or even feasible) at all.
def compute_approx_economic_viable_subset(orders, prices, fee, arith_traits):
    # Shortcut.
    if Config.MIN_AVERAGE_ORDER_FEE == 0:
        return orders

    # Remove empty orders.
    orders_by_dec_volume = [o for o in orders if o.buy_amount > 0]

    # Sort orders by decreasing volume
    orders_by_dec_volume = sorted(
        orders_by_dec_volume,
        key=lambda o: o.buy_amount * prices[o.buy_token],
        reverse=True
    )

    # Return maximal subset of orders that satisfy the minimum economic
    # viability constraint (but may fail to satify other constraints)
    i = 1
    while compute_average_order_fee(
        orders_by_dec_volume[:i], prices, fee, arith_traits
    ) >= Config.MIN_AVERAGE_ORDER_FEE:
        i += 1

    orders = orders[:i]

    # If there are only buy orders or only sell orders in the subset then
    # the subset can be further reduced to the trivial solution.
    if len({o.buy_token for o in orders}) == 1:
        return []

    return orders
