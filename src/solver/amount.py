
"""Compute optimal buy amounts for a set of orders between two tokens.

Given an array YB of maximum sell amounts for all orders,
and an exchange rate xrate, solves the following optimization problem:

X* = argmax_{X} f(X, xrate)

where X is an array of buy amounts.
"""
from fractions import Fraction as F
import logging

from ..util import order_sell_amount, order_limit_xrate
from ..constants import MINIMUM_TRADABLE_AMOUNT

logger = logging.getLogger(__name__)

# To account for the possibility that the minimum tradable amount
# constraint will end up being violated when rounding the solution to
# integers, the effective lower bound is conservatively increased here.
MINIMUM_TRADABLE_AMOUNT = int(MINIMUM_TRADABLE_AMOUNT * 1.001)


def filter_orders_violating_limit_xrate(xrate, b_orders, s_orders, fee):
    """Remove orders that violate the limit exchange rate (considering the fee)."""

    # For b_orders: xrate <= order_limit_xrate * (1 - fee)
    b_orders = [
        order for order in b_orders
        if xrate <= order_limit_xrate(order) * (1 - fee)
    ]

    # For s_orders: 1 / xrate <= order_limit_xrate * (1 - fee)
    s_orders = [
        order for order in s_orders
        if 1 / xrate <= order_limit_xrate(order) * (1 - fee)
    ]

    return b_orders, s_orders


def filter_orders_violating_min_tradable_amount(xrate, b_orders, s_orders, fee):
    """Remove orders which will violate min tradable amount."""

    b_orders = [
        order for order in b_orders
        if order_sell_amount(order) >= MINIMUM_TRADABLE_AMOUNT
        and order_sell_amount(order) / xrate * (1 - fee) >= MINIMUM_TRADABLE_AMOUNT
    ]

    s_orders = [
        order for order in s_orders
        if order_sell_amount(order) >= MINIMUM_TRADABLE_AMOUNT
        and order_sell_amount(order) * xrate * (1 - fee) >= MINIMUM_TRADABLE_AMOUNT
    ]

    return b_orders, s_orders


def find_best_buy_amounts(xrate, b_orders, s_orders, fee):
    """Compute optimal buy amounts for two sets of orders between two tokens.

    Convention:
    xrate = p(b_token) / p(s_token) = (s_amount / b_amount) * (1 - fee).
    """

    all_b_orders = b_orders
    all_s_orders = s_orders

    # Remove orders that violate the limit exchange rate.
    b_orders, s_orders = filter_orders_violating_limit_xrate(
        xrate, b_orders, s_orders, fee
    )

    # Remove orders which will violate the min tradable amount.
    b_orders, s_orders = filter_orders_violating_min_tradable_amount(
        xrate, b_orders, s_orders, fee
    )

    # Sort orders by optimal execution order.
    b_orders = sorted(b_orders, key=order_limit_xrate, reverse=True)
    s_orders = sorted(s_orders, key=order_limit_xrate, reverse=True)

    # Execute orders.
    b_i = 0
    s_i = 0
    b_buy_amounts = [0] * len(b_orders)  # in b_token
    s_buy_amounts = [0] * len(s_orders)  # in s_token
    # The 'execution' list records the sequence of order execution, useful below
    # when potentially undoing execution due to the minimum tradable amount constraint
    execution = []
    while s_i < len(s_orders) and b_i < len(b_orders):
        execution.append((b_i, s_i))

        # b_buy_amount = b_sell_amount / xrate * (1 - fee)
        # => max(b_buy_amount) = order_sell_amount(b_order) / xrate * (1 - fee)
        # => the available b_buy_amount in the current b_order is:
        b_buy_amount_ub = (order_sell_amount(b_orders[b_i]) / xrate) * (1 - fee)\
            - b_buy_amounts[b_i]

        # s_buy_amount = s_sell_amount * xrate * (1 - fee)
        # => max(s_buy_amount) = order_sell_amount(s_order) * xrate * (1 - fee)
        # => the available s_buy_amount in the current s_order is:
        s_buy_amount_ub = order_sell_amount(s_orders[s_i]) * xrate * (1 - fee)\
            - s_buy_amounts[s_i]
        assert b_buy_amount_ub >= 0 and s_buy_amount_ub >= 0

        # Check which order gets completely filled first.
        # x = y / xrate * (1 - fee) holds
        # for some x <= b_buy_amount_ub, y <= s_buy_amount_ub
        # To create imbalance on both tokens, instead of just on b_buy_token,
        # remove all occurrences of the (1-fee) factor from here to the end

        # => if b_buy_amount_ub < s_buy_amount_ub / xrate * (1 - fee),
        # then the s_order will be fully filled, and b_order partially filled
        if b_buy_amount_ub < (s_buy_amount_ub / xrate) * (1 - fee):
            b_buy_amounts[b_i] += b_buy_amount_ub
            s_buy_amounts[s_i] += b_buy_amount_ub * xrate / (1 - fee)
            b_i += 1

        # => if b_buy_amount_ub > s_buy_amount_ub / xrate * (1 - fee),
        # then the b_order will be fully filled, and s_order partially filled
        elif b_buy_amount_ub > (s_buy_amount_ub / xrate) * (1 - fee):
            b_buy_amounts[b_i] += s_buy_amount_ub / xrate * (1 - fee)
            s_buy_amounts[s_i] += s_buy_amount_ub
            s_i += 1

        # => otherwise both orders are fully filled.
        else:
            b_buy_amounts[b_i] += b_buy_amount_ub
            s_buy_amounts[s_i] += s_buy_amount_ub
            b_i += 1
            s_i += 1

    # At this point it is possible that either the last b_order or the last s_order
    # (or both) fails to satisfy the minimum tradable constraint.
    # If one of these orders is removed, then it is possible that another will now
    # violate the constraint, and hence the loop.
    for b_i, s_i in reversed(execution):
        b_sell_amount = (b_buy_amounts[b_i] * xrate) / (1 - fee)
        s_sell_amount = (s_buy_amounts[s_i] / xrate) * (1 - fee)
        undone_order_execution = False

        # if current b_order fails to satisfy the minimum tradable amount, then undo it
        if b_buy_amounts[b_i] < MINIMUM_TRADABLE_AMOUNT \
           or b_sell_amount < MINIMUM_TRADABLE_AMOUNT:
            s_buy_amounts[s_i] -= b_sell_amount
            b_buy_amounts[b_i] = 0
            undone_order_execution = True
            logger.debug(
                f"b_order {b_i} violates minimum tradable amount constraint. Skipping."
            )

        # if current s_order fails to satisfy the minimum tradable amount, then undo it
        if s_buy_amounts[s_i] < MINIMUM_TRADABLE_AMOUNT \
                or s_sell_amount < MINIMUM_TRADABLE_AMOUNT:
            b_buy_amounts[b_i] -= s_sell_amount
            s_buy_amounts[s_i] = 0
            undone_order_execution = True
            logger.debug(
                f"s_order {s_i} violates minimum tradable amount constraint. Skipping."
            )

        if not undone_order_execution:
            break

    # Token balance invariant.
    assert sum(b_buy_amounts) * xrate == sum(s_buy_amounts) * (1 - fee)

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
