import json
from decimal import Decimal as D
from fractions import Fraction as F
from typing import List, Dict
from .objective import (
    IntegerTraits, RationalTraits, compute_sell_amounts_from_buy_amounts
)
from .util import (
    restrict_order_sell_amounts_by_balances,
    filter_orders_tokenpair,
    is_same_order
)


def init_order_IDs(orders: List[Dict]) -> List[Dict]:
    # Get required length of order ID string.
    nchars_order_id = len(str(len(orders)))
    # Store position of order in input list and set ID (with leading zeroes, e.g., '001').
    for idx, order in enumerate(orders):
        order['listIdx'] = idx
        order['ID'] = '%0*d' % (nchars_order_id, idx)
    return orders


def load_problem(problem_file, token_pair):
    problem = json.load(problem_file, parse_float=D)
    b_buy_token, s_buy_token = token_pair

    accounts = problem['accounts']

    orders = problem['orders']

    orders = init_order_IDs(orders)

    orders = filter_orders_tokenpair(orders, token_pair)

    orders = restrict_order_sell_amounts_by_balances(orders, accounts)

    b_orders = [
        order for order in orders
        if order["buyToken"] == b_buy_token and order["sellToken"] == s_buy_token
    ]
    s_orders = [
        order for order in orders
        if order["buyToken"] == s_buy_token and order["sellToken"] == b_buy_token
    ]

    fee = F(problem["fee"]["ratio"])

    return accounts, b_orders, s_orders, fee


def dump_solution(
    problem_file, solution_file,
    b_orders, s_orders,
    b_buy_amounts, s_buy_amounts,
    xrate,
    b_buy_token_price,
    fee,
    arith_traits=IntegerTraits()
):
    b_sell_amounts = compute_sell_amounts_from_buy_amounts(
        b_buy_amounts, xrate, b_buy_token_price, fee,
        arith_traits=arith_traits
    )
    s_sell_amounts = compute_sell_amounts_from_buy_amounts(
        s_buy_amounts, 1 / xrate, b_buy_token_price / xrate, fee,
        arith_traits=arith_traits
    )

    # Output floats instead of rational numbers to make it for easier inspection
    if isinstance(arith_traits, RationalTraits):
        b_buy_amounts = list(map(float, b_buy_amounts))
        s_buy_amounts = list(map(float, s_buy_amounts))
        b_sell_amounts = list(map(float, b_sell_amounts))
        s_sell_amounts = list(map(float, s_sell_amounts))

    # Dump b_orders and s_orders keeping the original (interleaved) order.
    all_orders = []
    b_i = 0
    s_i = 0

    instance = json.load(problem_file)
    original_orders = init_order_IDs(instance["orders"])
    for order in original_orders:
        if b_i < len(b_orders) and is_same_order(order, b_orders[b_i]):
            order["execSellAmount"] = str(b_sell_amounts[b_i])
            order["execBuyAmount"] = str(b_buy_amounts[b_i])
            all_orders.append(order)
            b_i += 1
        elif s_i < len(s_orders) and is_same_order(order, s_orders[s_i]):
            order["execSellAmount"] = str(s_sell_amounts[s_i])
            order["execBuyAmount"] = str(s_buy_amounts[s_i])
            all_orders.append(order)
            s_i += 1

    instance["orders"] = all_orders

    # TODO: should we remove unused accounts as well?
    json.dump(instance, solution_file, indent=4)
