
"""Compute optimal buy amounts for a set of orders between two tokens.

Given an array YB of maximum sell amounts for all orders,
and an exchange rate xrate, solves the following optimization problem:

X* = argmax_{X} f(X, xrate)

where X is an array of buy amounts.
"""
import logging

from src.core.config import Config

logger = logging.getLogger(__name__)

# To account for the possibility that the minimum tradable amount
# constraint will end up being violated when rounding the solution to
# integers, the effective lower bound is conservatively increased here.
MIN_TRADABLE_AMOUNT = int(Config.MIN_TRADABLE_AMOUNT * 1.001)


#############################################################################
#    xrate = p(b_token) / p(s_token) = (s_amount / b_amount) * (1 - fee).   #
#############################################################################


# Convenience functions:

# Depending if the order is a b_order or an s_order, we have:

# b_buy_amount = b_sell_amount / xrate * (1 - fee)  [eq.1]
def b_buy_amount_from_b_sell_amount(b_sell_amount, xrate, fee):
    return (b_sell_amount / xrate) * (1 - fee.value)


def b_sell_amount_from_b_buy_amount(b_buy_amount, xrate, fee):
    return b_buy_amount * xrate / (1 - fee.value)


def b_buy_amount_from_b_max_sell_amount(order, xrate, fee):
    return b_buy_amount_from_b_sell_amount(order.max_sell_amount, xrate, fee)


# s_buy_amount = s_sell_amount * xrate * (1 - fee)  [eq.2]
def s_buy_amount_from_s_sell_amount(s_sell_amount, xrate, fee):
    return s_sell_amount * xrate * (1 - fee.value)


def s_sell_amount_from_s_buy_amount(s_buy_amount, xrate, fee):
    return s_buy_amount / xrate / (1 - fee.value)


def s_buy_amount_from_s_max_sell_amount(order, xrate, fee):
    return s_buy_amount_from_s_sell_amount(order.max_sell_amount, xrate, fee)


# To "convert" b_buy_amount to s_sell_amount there are several options,
# depending on which token will be balanced in the end. Here we choose to
# always balance s_buy_token (thus imbalacing b_buy_token).
# That is, we enforce that:
# b_sell_amount = s_buy_amount  [eq.3]


# Replacing eq.3 in eq.1 gives us:
# b_buy_amount = s_buy_amount / xrate * (1 - fee)
def b_buy_amount_from_s_buy_amount(s_buy_amount, xrate, fee):
    return (s_buy_amount / xrate) * (1 - fee.value)


# Starting with eq.3:
# s_buy_amount = b_sell_amount
#              = b_buy_amount * xrate / (1 - fee)  (from eq.1)
def s_buy_amount_from_b_buy_amount(b_buy_amount, xrate, fee):
    return b_buy_amount * xrate / (1 - fee.value)


# As said there were other options for managing the imbalance, namely creating
# imbalance on both tokens, or only on the s_buy_token, which would lead to different
# definitions of the two functions above.


def filter_orders_violating_max_xrate(xrate, b_orders, s_orders, fee):
    """Remove orders that violate the maximum exchange rate (considering the fee)."""

    # For b_orders: xrate <= max_xrate * (1 - fee)
    b_orders = [
        order for order in b_orders
        if xrate <= order.max_xrate * (1 - fee.value)
    ]

    # For s_orders: 1 / xrate <= max_xrate * (1 - fee)
    s_orders = [
        order for order in s_orders
        if 1 / xrate <= order.max_xrate * (1 - fee.value)
    ]

    return b_orders, s_orders


def filter_orders_violating_min_tradable_amount(xrate, b_orders, s_orders, fee):
    """Remove orders which will violate min tradable amount."""

    b_orders = [
        order for order in b_orders
        if order.max_sell_amount >= MIN_TRADABLE_AMOUNT
        and b_buy_amount_from_b_max_sell_amount(order, xrate, fee) >= MIN_TRADABLE_AMOUNT
    ]

    s_orders = [
        order for order in s_orders
        if order.max_sell_amount >= MIN_TRADABLE_AMOUNT
        and s_buy_amount_from_s_max_sell_amount(order, xrate, fee) >= MIN_TRADABLE_AMOUNT
    ]

    return b_orders, s_orders


# Exchange buy amounts between two matching orders b_orders[b_i] and s_orders[s_i].
# Returns the new b_i, s_i, after execution:
# b_i := b_i + 1 if b_order[b_i] was fully executed, or b_i otherwise.
# s_i := s_i + 1 if s_order[s_i] was fully executed, or s_i otherwise.
def execute_order_pair(b_i, s_i, xrate, b_orders, s_orders, fee):
    b_order = b_orders[b_i]
    s_order = s_orders[s_i]

    # The available b_buy_amount in the current b_order is:
    b_buy_amount_ub = b_buy_amount_from_b_max_sell_amount(b_order, xrate, fee) \
        - b_order.buy_amount

    # The available s_buy_amount in the current s_order is:
    s_buy_amount_ub = s_buy_amount_from_s_max_sell_amount(s_order, xrate, fee) \
        - s_order.buy_amount
    assert b_buy_amount_ub >= 0 and s_buy_amount_ub >= 0

    # Check which order gets completely filled first:

    b_buy_amount_from_s = b_buy_amount_from_s_buy_amount(s_buy_amount_ub, xrate, fee)
    s_buy_amount_from_b = s_buy_amount_from_b_buy_amount(b_buy_amount_ub, xrate, fee)

    # If the maximum buy amount capacity of the b_order is less than what can be
    # bought from the s_order, then the s_order will be fully filled, and b_order
    # partially filled.
    if b_buy_amount_ub < b_buy_amount_from_s:
        b_order.buy_amount += b_buy_amount_ub
        s_order.buy_amount += s_buy_amount_from_b
        b_i += 1

    # If the maximum buy amount capacity of the b_order is greater than what can be
    # bought from the s_order, then the b_order will be fully filled, and s_order
    # partially filled.
    elif b_buy_amount_ub > b_buy_amount_from_s:
        b_order.buy_amount += b_buy_amount_from_s
        s_order.buy_amount += s_buy_amount_ub
        s_i += 1

    # Otherwise both orders are fully filled.
    else:
        b_order.buy_amount += b_buy_amount_ub
        s_order.buy_amount += s_buy_amount_ub
        b_i += 1
        s_i += 1

    return (b_i, s_i)


# This functions is the inverse of the `execute_order_pair` function:
# Undoes exchange buy amounts between two matching orders b_orders[b_i] and s_orders[s_i].
# Returns the new b_i, s_i, after execution:
# b_i := b_i - 1 if b_order[b_i] was fully emptied, or b_i otherwise.
# s_i := s_i - 1 if s_order[s_i] was fully emptied, or s_i otherwise.
def undo_order_pair_execution(b_i, s_i, xrate, b_orders, s_orders, fee):
    b_order = b_orders[b_i]
    s_order = s_orders[s_i]

    # The maximum b_buy_amount that can be removed from the current b_order is:
    b_buy_amount_ub = b_order.buy_amount

    # The maximum s_buy_amount that can be removed from the current s_order is:
    s_buy_amount_ub = s_order.buy_amount
    assert b_buy_amount_ub >= 0 and s_buy_amount_ub >= 0

    # Check which order gets completely empty first:

    b_buy_amount_from_s = b_buy_amount_from_s_buy_amount(s_buy_amount_ub, xrate, fee)
    s_buy_amount_from_b = s_buy_amount_from_b_buy_amount(b_buy_amount_ub, xrate, fee)

    # If the maximum removable buy amount of the b_order is less than what can be
    # removed if the s_order is completely emptied, then the b_order will be empty
    # and the s_order partially filled.
    if b_buy_amount_ub < b_buy_amount_from_s:
        b_order.buy_amount = 0
        s_order.buy_amount -= s_buy_amount_from_b
        b_i -= 1

    # If the maximum removable buy amount of the b_order is greater than what can be
    # removed if the s_order is completely emptied, then the b_order will be partially
    # filled and the s_order empty.
    elif b_buy_amount_ub > b_buy_amount_from_s:
        b_order.buy_amount -= b_buy_amount_from_s
        s_order.buy_amount = 0
        s_i -= 1

    # Otherwise both orders are empty.
    else:
        b_order.buy_amount = 0
        s_order.buy_amount = 0
        b_i -= 1
        s_i -= 1

    return (b_i, s_i)


# Utility function called from `compute_buy_amounts` below.
# Removes 'amount_to_remove' from one or more orders buy amounts, in reversed
# execution order starting at order_i.
def remove_buy_amount(order_i, orders, amount_to_remove):
    while amount_to_remove > 0:
        assert order_i >= 0
        remove_delta = min(orders[order_i].buy_amount, amount_to_remove)
        orders[order_i].buy_amount -= remove_delta
        amount_to_remove -= remove_delta
        if orders[order_i].buy_amount == 0:
            order_i -= 1
    return order_i


# Sets b_buy_amount=0 for the given b_order and adjusts all s_buy_amounts of
# the s_orders buying the undone amount, potentially setting some to zero as well.
def undo_b_order_execution(b_i, s_i, b_orders, s_orders, xrate, fee):
    # Remove s_buy_amounts from all s_orders necessary to cover removed amount.
    s_buy_amount = s_buy_amount_from_b_buy_amount(b_orders[b_i].buy_amount, xrate, fee)
    s_i = remove_buy_amount(s_i, s_orders, s_buy_amount)

    # Undo current b_order.
    b_orders[b_i].buy_amount = 0
    b_i -= 1

    # Invariant: either the above undid all orders, or there are matching orders.
    assert (b_i == -1 and s_i == -1) or (b_i >= 0 and s_i >= 0)

    return b_i, s_i


# Sets s_buy_amount=0 for the given s_order and adjusts all b_buy_amounts of
# the b_orders buying the undone amount, potentially setting some to zero as well.
def undo_s_order_execution(b_i, s_i, b_orders, s_orders, xrate, fee):
    # Remove b_buy_amounts from all b_orders necessary to cover removed amount.
    b_buy_amount = b_buy_amount_from_s_buy_amount(s_orders[s_i].buy_amount, xrate, fee)
    b_i = remove_buy_amount(b_i, b_orders, b_buy_amount)

    # Undo current s_order.
    s_orders[s_i].buy_amount = 0
    s_i -= 1

    # Invariant: either the above undid all orders, or there are matching orders.
    assert (b_i == -1 and s_i == -1) or (b_i >= 0 and s_i >= 0)

    return b_i, s_i


# Checks if either b_orders[b_i] or s_orders[s_i], or both, violate the minimum tradable
# amount constraint, and undo them if so.
def undo_order_execution_violating_min_tradable_amount_constraint(
    b_i, s_i, b_orders, s_orders, xrate, fee
):
    undone_order_execution = False

    # If there is nothing else to undo then exit immediately.
    if b_i < 0:
        return (b_i, s_i, undone_order_execution)

    # If current b_order fails to satisfy the minimum tradable amount, then undo it.
    b_buy_amount = b_orders[b_i].buy_amount
    b_sell_amount = b_sell_amount_from_b_buy_amount(b_buy_amount, xrate, fee)
    if b_buy_amount < MIN_TRADABLE_AMOUNT or b_sell_amount < MIN_TRADABLE_AMOUNT:
        logger.debug(
            "b_order %s violates minimum tradable amount constraint. Skipped.",
            b_orders[b_i].index
        )
        b_i, s_i = undo_b_order_execution(b_i, s_i, b_orders, s_orders, xrate, fee)
        undone_order_execution = True

    # If there is nothing else to undo then exit immediately.
    if s_i < 0:
        return (b_i, s_i, undone_order_execution)

    # If current s_order fails to satisfy the minimum tradable amount, then undo it.
    s_buy_amount = s_orders[s_i].buy_amount
    s_sell_amount = s_sell_amount_from_s_buy_amount(s_buy_amount, xrate, fee)
    if s_buy_amount < MIN_TRADABLE_AMOUNT or s_sell_amount < MIN_TRADABLE_AMOUNT:
        # Undo current s_order.
        logger.debug(
            "s_order %s violates minimum tradable amount constraint. Skipped.",
            s_orders[s_i].index
        )
        b_i, s_i = undo_s_order_execution(b_i, s_i, b_orders, s_orders, xrate, fee)
        undone_order_execution = True

    return (b_i, s_i, undone_order_execution)


def compute_buy_amounts(
    xrate, b_orders, s_orders, fee, max_nr_exec_orders=None
):
    """Compute optimal buy amounts for two sets of orders between two tokens.

    Convention:
    xrate = p(b_token) / p(s_token) = (s_amount / b_amount) * (1 - fee).
    """

    # NOTE: do not add this as a default parameter above, since
    # default parameters are evaluated when the function is defined, and
    # not when it is called. This means that runtime changes to the Config
    # singleton would not be reflected.
    if max_nr_exec_orders is None:
        max_nr_exec_orders = Config.MAX_NR_EXEC_ORDERS

    # Reset buy amounts to zero.
    for b_order in b_orders:
        b_order.buy_amount = 0
    for s_order in s_orders:
        s_order.buy_amount = 0

    # Remove orders that violate the maximum exchange rate.
    b_orders, s_orders = filter_orders_violating_max_xrate(
        xrate, b_orders, s_orders, fee
    )

    # Remove orders which will violate the min tradable amount.
    b_orders, s_orders = filter_orders_violating_min_tradable_amount(
        xrate, b_orders, s_orders, fee
    )

    # Early exit: if there are no orders on one of the sides, there's no match.
    if len(b_orders) == 0 or len(s_orders) == 0:
        return

    # Sort orders by optimal execution order.
    b_orders = sorted(b_orders, key=lambda o: o.max_xrate, reverse=True)
    s_orders = sorted(s_orders, key=lambda o: o.max_xrate, reverse=True)

    # Execute matching orders, bounded by the max_nr_exec_orders constraint:
    b_i = 0
    s_i = 0
    while s_i < len(s_orders) and b_i < len(b_orders) \
            and s_i + b_i < max_nr_exec_orders:
        b_i, s_i = execute_order_pair(
            b_i, s_i, xrate, b_orders, s_orders, fee
        )

    # Point b_i, s_i to the last executed orders.
    b_i = b_i if b_i < len(b_orders) and b_orders[b_i].buy_amount > 0 else b_i - 1
    s_i = s_i if s_i < len(s_orders) and s_orders[s_i].buy_amount > 0 else s_i - 1

    # Total number of executed orders (note: array indexing is 0-based, hence the +2)
    nr_exec_orders = b_i + s_i + 2

    # Since the last iteration of the above loop could have incremented s_i + b_i by 2,
    # it can happen that now nr_exec_orders == max_nr_exec_orders + 1, in which case
    # at least 1 and at most 2 orders need to be undone.
    if nr_exec_orders > max_nr_exec_orders:
        assert nr_exec_orders == max_nr_exec_orders + 1
        b_i, s_i = undo_order_pair_execution(b_i, s_i, xrate, b_orders, s_orders, fee)

    # At this point it is possible that either the last b_order or the last s_order
    # (or both) fails to satisfy the minimum tradable constraint.
    # If one of these orders is removed, then it is possible that another will now
    # violate the constraint, and hence the loop.
    undone_order_execution = True
    while undone_order_execution:
        b_i, s_i, undone_order_execution = \
            undo_order_execution_violating_min_tradable_amount_constraint(
                b_i, s_i, b_orders, s_orders, xrate, fee
            )

    # Token balance invariant.
    assert sum(b_order.buy_amount for b_order in b_orders) * xrate == \
        sum(s_order.buy_amount for s_order in s_orders) * (1 - fee.value)
