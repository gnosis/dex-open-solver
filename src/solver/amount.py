
"""Compute optimal buy amounts for a set of orders between two tokens.

Given an array YB of maximum sell amounts for all orders,
and an exchange rate xrate, solves the following optimization problem:

X* = argmax_{X} f(X, xrate)
s.t.
x_i * xrate <= yb_i, for all x_i in X.

where X is an array of buy amounts.
"""
from fractions import Fraction as F

from ..util import order_sell_amount, order_limit_xrate


# xrate = p(b_token) / p(s_token) = s_amount / b_amount.
def find_best_buy_amounts(xrate, b_orders, s_orders, fee_ratio=F(0)):
    all_b_orders = b_orders
    all_s_orders = s_orders

    # Remove orders that will violate the limit exchange rate after the fee is deducted.
    b_orders = [
        order for order in b_orders
        if order_limit_xrate(order) * (1 - fee_ratio) >= xrate
    ]
    s_orders = [
        order for order in s_orders
        if order_limit_xrate(order) * (1 - fee_ratio) >= 1 / xrate
    ]

    # Sort orders by optimal execution order.
    b_orders = sorted(b_orders, key=order_limit_xrate, reverse=True)
    s_orders = sorted(s_orders, key=order_limit_xrate, reverse=True)

    # Execute orders.
    b_i = 0
    s_i = 0
    b_buy_amounts = [0] * len(b_orders)  # in b_token
    s_buy_amounts = [0] * len(s_orders)  # in s_token
    while s_i < len(s_orders) and b_i < len(b_orders):
        b_buy_amount_ub = order_sell_amount(b_orders[b_i]) * (1 - fee_ratio) / xrate - b_buy_amounts[b_i]
        s_buy_amount_ub = order_sell_amount(s_orders[s_i]) * (1 - fee_ratio) * xrate - s_buy_amounts[s_i]
        assert b_buy_amount_ub >= 0 and s_buy_amount_ub >= 0

        # Check which order gets completely filled first
        if b_buy_amount_ub < s_buy_amount_ub / xrate * (1 - fee_ratio):
            b_buy_amounts[b_i] += b_buy_amount_ub
            s_buy_amounts[s_i] += b_buy_amount_ub * xrate / (1 - fee_ratio)
            b_i += 1
        elif b_buy_amount_ub > s_buy_amount_ub / xrate * (1 - fee_ratio):
            b_buy_amounts[b_i] += s_buy_amount_ub / xrate * (1 - fee_ratio)
            s_buy_amounts[s_i] += s_buy_amount_ub
            s_i += 1
        else:
            b_buy_amounts[b_i] += b_buy_amount_ub
            s_buy_amounts[s_i] += s_buy_amount_ub
            b_i += 1
            s_i += 1

    # Token balance invariant.
    assert sum(b_buy_amounts) * xrate == sum(s_buy_amounts) * (1 - fee_ratio)

    # Integrate the execution amounts of the excluded orders.
    all_b_buy_amounts = [0] * len(all_b_orders)
    for i, b_order in enumerate(b_orders):
        if b_buy_amounts[i] > 0:
            all_b_buy_amounts[all_b_orders.index(b_order)] = b_buy_amounts[i]

    all_s_buy_amounts = [0] * len(all_s_orders)
    for i, s_order in enumerate(s_orders):
        if s_buy_amounts[i] > 0:
            all_s_buy_amounts[all_s_orders.index(s_order)] = s_buy_amounts[i]
    return all_b_buy_amounts, all_s_buy_amounts
