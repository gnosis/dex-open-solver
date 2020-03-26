
"""Load and setup a token pair problem from an instance json."""
from copy import deepcopy

from src.core.api import load_fee
from src.core.order import Order
from src.core.orderbook import restrict_order_sell_amounts_by_balances


def load_problem(instance, token_pair):
    """Load and setup a token pair problem from an instance json."""
    b_buy_token, s_buy_token = token_pair

    accounts = deepcopy(instance['accounts'])

    orders = [
        Order.load_from_dict(index, order_dict)
        for index, order_dict in enumerate(instance['orders'])
    ]

    orders = restrict_order_sell_amounts_by_balances(orders, accounts)

    b_orders = [
        order for order in orders
        if order.buy_token == b_buy_token and order.sell_token == s_buy_token
    ]
    s_orders = [
        order for order in orders
        if order.buy_token == s_buy_token and order.sell_token == b_buy_token
    ]

    fee = load_fee(instance['fee'])

    # If one of the tokens in the token pair is the fee token, then it must be b_buy_token
    assert s_buy_token != fee.token

    f_orders = [
        order for order in orders
        if order.buy_token == b_buy_token and order.sell_token == fee.token
    ]

    return accounts, b_orders, s_orders, f_orders, fee
