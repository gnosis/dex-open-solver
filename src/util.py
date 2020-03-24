from typing import List, Dict, Tuple
from fractions import Fraction as F
from decimal import Decimal as D
import json


def order_buy_amount(order):
    return F(order["buyAmount"])


def order_sell_amount(order):
    return F(order["sellAmount"])


def order_limit_xrate(order):
    return order_sell_amount(order) / order_buy_amount(order)


def is_same_order(order1, order2):
    return order1["ID"] == order2["ID"]


def filter_orders_tokenpair(
        orders: List[Dict],
        token_pair: Tuple[str, str]) -> List[Dict]:
    """Find all orders on a single given token pair.

    Args:
        orders: List of orders.
        tokenpair: Tuple of two token IDs.

    Returns:
        The filtered orders.

    """
    return [o for o in orders if set(token_pair) == {o['sellToken'], o['buyToken']}]


def restrict_order_sell_amounts_by_balances(
        orders: List[Dict],
        accounts: Dict[str, Dict[str, int]]) -> List[Dict]:
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
    for o in sorted(orders, key=order_limit_xrate, reverse=True):
        aID, tS, tB = o['accountID'], o['sellToken'], o['buyToken']

        # Init remaining balance for new token pair on some account.
        if (aID, tS, tB) not in remaining_balances:
            sell_token_balance = F(accounts.get(o['accountID'], {}).get(tS, 0))
            remaining_balances[(aID, tS, tB)] = sell_token_balance

        # Get sell amount (capped by available account balance).
        sell_amount_old = F(o['sellAmount'])
        sell_amount_new = min(sell_amount_old, remaining_balances[aID, tS, tB])

        # Skip orders with zero sell amount.
        if sell_amount_new == 0:
            continue
        else:
            assert sell_amount_old > 0

        # Update remaining balance.
        remaining_balances[aID, tS, tB] -= sell_amount_new
        assert remaining_balances[aID, tS, tB] >= 0

        # Update buy amount according to capped sell amount.
        buy_amount_old = F(o['buyAmount'])
        buy_amount_new = buy_amount_old * sell_amount_new / sell_amount_old

        o['sellAmount'] = sell_amount_new
        o['buyAmount'] = buy_amount_new

        # Append capped order.
        orders_capped.append(o)

    return orders_capped


class DecimalToStringEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, D):
            return str(obj)
        return json.JSONEncoder.default(self, obj)
