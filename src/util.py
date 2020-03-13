from typing import List, Dict, Tuple
import decimal
from decimal import Decimal as D
from fractions import Fraction as F


def order_buy_amount(order):
    return F(order["buyAmount"])


def order_sell_amount(order):
    return F(order["sellAmount"])


def order_limit_xrate(order):
    return order_sell_amount(order) / order_buy_amount(order)


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

    for o in orders:
        tS = o['sellToken']

        # Get sell amount (capped by available account balance).
        available_balance = D(accounts.get(o['accountID'], {}).get(tS, 0))
        sell_amount_old = D(o['sellAmount'])
        sell_amount_new = min(sell_amount_old, available_balance)

        # Skip orders with zero sell amount.
        if sell_amount_new == 0:
            continue
        else:
            assert sell_amount_old > 0

        # Update buy amount according to capped sell amount.
        buy_amount_old = D(o['buyAmount'])
        buy_amount_new = buy_amount_old * sell_amount_new / sell_amount_old
        buy_amount_new = buy_amount_new.to_integral_value(rounding=decimal.ROUND_UP)

        o['sellAmount'] = sell_amount_new
        o['buyAmount'] = buy_amount_new

        # Append capped order.
        orders_capped.append(o)

    return orders_capped
