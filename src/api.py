import json
from decimal import Decimal as D
from fractions import Fraction as F
from .objective import (
    IntegerTraits, RationalTraits, compute_sell_amounts_from_buy_amounts
)
from .util import (
    restrict_order_sell_amounts_by_balances,
    filter_orders_tokenpair
)


def load_problem(problem_file, token_pair):
    problem = json.load(problem_file, parse_float=D)
    b_buy_token, s_buy_token = token_pair

    orders = filter_orders_tokenpair(problem['orders'], token_pair)

    orders = restrict_order_sell_amounts_by_balances(orders, problem['accounts'])

    b_orders = [
        order for order in orders
        if order["buyToken"] == b_buy_token and order["sellToken"] == s_buy_token
    ]
    s_orders = [
        order for order in orders
        if order["buyToken"] == s_buy_token and order["sellToken"] == b_buy_token
    ]

    fee = F(problem["fee"]["ratio"])

    return b_orders, s_orders, fee


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

    instance = json.load(problem_file)

    # Dump b_orders and s_orders keeping the original (interleaved) order.
    all_orders = []
    b_i = 0
    s_i = 0
    for order in instance["orders"]:
        if b_i < len(b_orders) and order == b_orders[b_i]:
            order = b_orders[b_i]
            order["execBuyAmount"] = str(b_buy_amounts[b_i])
            order["execSellAmount"] = str(b_sell_amounts[b_i])
            all_orders.append(order)
            b_i += 1
        elif s_i < len(s_orders) and order == s_orders[s_i]:
            order = s_orders[s_i]
            order["execBuyAmount"] = str(s_buy_amounts[s_i])
            order["execSellAmount"] = str(s_sell_amounts[s_i])
            all_orders.append(order)
            s_i += 1

    instance["orders"] = all_orders

    # TODO: should we remove unused accounts as well?

    json.dump(instance, solution_file, indent=4)
