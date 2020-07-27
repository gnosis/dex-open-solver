"""Compute the optimal exchange rate for a set of orders between two tokens.

Given an array YB of maximum sell amounts and an array PI of maximum exchange rates,
solves the following optimization problem:

xrate* = argmax_{X, xrate} f(X, xrate)
s.t.
x_i * xrate <= yb_i, for all x_i in X.
xrate <= pi_i, for all pi_i in PI.

See https://github.com/gnosis/dex-open-solver/blob/master/doc/token_pair/token_pair.pdf.
"""

import logging
from collections import deque, namedtuple
from fractions import Fraction as F
from functools import lru_cache
from itertools import groupby
from math import sqrt, log, ceil

from src.core.config import Config

from .amount import compute_buy_amounts
from .orderbook import compute_objective_rational, prune_unrealizable_orders

logger = logging.getLogger(__name__)


IntervalData = namedtuple('IntervalData', ['xrate', 'orders', 'partial'])


# Generate the b_order indexes that needs to execute to satisfy current
# given s_sell_amount and xrate intervals, and the equation:
# xrate = b_sell_amount / (s_sell_amount * (1 - fee))
# <=> b_sell_amount = s_sell_amount * xrate * (1 - fee).
def xrate_interval_iterator_b_orders(
    b_orders,
    s_sell_amount_lb,
    s_sell_amount_ub,
    xrate_lb,
    xrate_ub,
    fee
):
    b_sell_amount_lb = s_sell_amount_lb * xrate_lb * (1 - fee.value)
    b_sell_amount_ub = s_sell_amount_ub * xrate_ub * (1 - fee.value)

    cur_b_sell_amount_ub = sum(b_order.max_sell_amount for b_order in b_orders)
    for i in range(len(b_orders)):
        cur_b_sell_amount_lb = cur_b_sell_amount_ub \
            - b_orders[i].max_sell_amount
        if cur_b_sell_amount_ub < b_sell_amount_lb:
            break
        if cur_b_sell_amount_lb <= b_sell_amount_ub:
            yield i
        cur_b_sell_amount_ub -= b_orders[i].max_sell_amount


# Generate the s_order indexes that needs to execute to satisfy current
# given b_sell_amount and xrate intervals, and the equation:
# xrate = b_sell_amount / (s_sell_amount * (1 - fee))
# <=> s_sell_amount = b_sell_amount / (xrate * (1 - fee)).
def xrate_interval_iterator_s_orders(
    s_orders,
    b_sell_amount_lb,
    b_sell_amount_ub,
    xrate_lb,
    xrate_ub,
    fee
):
    s_sell_amount_lb = b_sell_amount_lb / (xrate_ub * (1 - fee.value))
    s_sell_amount_ub = b_sell_amount_ub / (xrate_lb * (1 - fee.value))

    cur_s_sell_amount_ub = sum(s_order.max_sell_amount for s_order in s_orders)
    for i in range(len(s_orders)):
        cur_s_sell_amount_lb = cur_s_sell_amount_ub \
            - s_orders[i].max_sell_amount
        if cur_s_sell_amount_ub < s_sell_amount_lb:
            break
        if cur_s_sell_amount_lb <= s_sell_amount_ub:
            yield i
        cur_s_sell_amount_ub -= s_orders[i].max_sell_amount


def xrate_interval_iterator(b_orders, s_orders, fee, optimal_trivial_xrate=None):
    """Exchange rate interval iterator.

    Iterates through intervals [xrate_lb, xrate_ub] of possible values for xrate,
    where xrate_lb, xrate_ub are defined by the max_xrate's of two orders that are
    consecutive in the optimal execution order.

    At each iteration yields an IntervalData object containing the xrate interval,
    two sorted lists: b_exec_orders and s_exec_orders, which can be executed
    if xrate is in the given interval, and a pair of indexes into the exec order lists
    pointing to the first partially executed order in each corresponding list.

    Skips some suboptimal intervals.
    """
    assert len(b_orders) > 0 and len(s_orders) > 0
    B, S = 0, 1

    # Collect b_orders and s_orders in a single list sorted by optimal execution order.
    OrderVariant = namedtuple('OrderInfo', ['type', 'xrate', 'data'])
    f = 1 - fee.value
    all_orders = [
        OrderVariant(B, b_order.max_xrate * f, b_order)
        for b_order in b_orders
    ] + [
        OrderVariant(S, 1 / (s_order.max_xrate * f), s_order)
        for s_order in s_orders
    ]

    all_orders = sorted(all_orders, key=lambda order: order.xrate, reverse=True)

    # Loop through all possible intervals for xrate, ordered from highest to lowest.

    # The list of b_orders which can be executed if xrate is in the current interval,
    # initially empty.
    b_exec_orders = deque()

    # The list of s_orders which can be executed if xrate is in the current interval,
    # initially holding all s_orders.
    s_exec_orders = deque([order.data for order in all_orders if order.type == S])

    # Total sell amount of b_orders in the b_exec_orders list.
    b_exec_sell_amount_ub = 0

    # Total sell amount of s_orders in the s_exec_orders list.
    s_exec_sell_amount_ub = sum(s_order.max_sell_amount for s_order in s_orders)

    # Main loop.
    for order_i in range(len(all_orders) - 1):
        order_type, order_xrate, order = all_orders[order_i]
        next_order_xrate = all_orders[order_i + 1].xrate

        # Update exec_orders / exec_sell_amounts.
        if order_type == B:
            b_exec_orders.appendleft(order)
            b_exec_sell_amount_ub += order.max_sell_amount

        if order_type == S:
            s_exec_orders.popleft()
            s_exec_sell_amount_ub -= order.max_sell_amount

        # If optimal_trivial_xrate is given, then consider only xrate intervals for
        # which optimal_trivial_xrate is an endpoint.
        if optimal_trivial_xrate is not None:
            test_xrates = {order_xrate, next_order_xrate}
            if order_i > 0:
                prev_order_xrate = all_orders[order_i - 1].xrate
                test_xrates.add(prev_order_xrate)
            if optimal_trivial_xrate not in test_xrates:
                continue

        # If no b_order was yet visited, there can't be a match => go to next order.
        if len(b_exec_orders) == 0:
            continue

        # If there are no more s_orders below current xrate interval, then there can't
        # be no more matches => exit iteration.
        if len(s_exec_orders) == 0:
            return

        # xrate interval associated with this iteration.
        xrate_lb = next_order_xrate
        xrate_ub = order_xrate

        # lb(exec_sell_amount) is the sold amount of all executed orders, except the
        # last one, which potentially may be only partially executed.
        b_exec_sell_amount_lb = b_exec_sell_amount_ub - b_exec_orders[0].max_sell_amount
        s_exec_sell_amount_lb = s_exec_sell_amount_ub - s_exec_orders[0].max_sell_amount

        # yield fixed set of s_exec_orders and distinct sets b_exec_orders
        for i in xrate_interval_iterator_b_orders(
            b_exec_orders,
            s_exec_sell_amount_lb, s_exec_sell_amount_ub,
            xrate_lb, xrate_ub,
            fee
        ):
            yield IntervalData(
                xrate=(xrate_lb, xrate_ub),
                orders=(list(b_exec_orders), list(s_exec_orders)),
                partial=(i, 0)
            )

        # yield fixed set of b_exec_orders and distinct sets s_exec_orders
        for i in xrate_interval_iterator_s_orders(
            s_exec_orders,
            b_exec_sell_amount_lb, b_exec_sell_amount_ub,
            xrate_lb, xrate_ub,
            fee
        ):
            yield IntervalData(
                xrate=(xrate_lb, xrate_ub),
                orders=(list(b_exec_orders), list(s_exec_orders)),
                partial=(0, i)
            )


class SymbolicSolver:
    Constants = namedtuple(
        'Constants',
        ['b_pi', 'b_yb', 'b_yb_F', 's_pi', 's_yb', 's_yb_F', 'c', 'f']
    )

    def __init__(self, fee):
        self.fee = fee

    # Iterates through the set of unfilled orders.
    def orders_U(self, orders, partial_idx):
        yield from orders[:partial_idx]

    # Iterates through the set of completely filled orders.
    def orders_F(self, orders, partial_idx):
        yield from orders[(partial_idx + 1):]

    # Total sell amount of completely filled orders.
    def sum_yb_F(self, orders, partial_idx):
        return sum(
            order.max_sell_amount
            for order in self.orders_F(orders, partial_idx)
        )

    # Constant c - see "Local optima for a given interval" in the documentation.
    def c_constant(self, b_orders, b_partial_idx, s_orders, s_partial_idx):
        b_sum_yb_F, b_sum_yb_U = (
            sum(
                o.max_sell_amount for o in fn(b_orders, b_partial_idx)
            ) for fn in (self.orders_F, self.orders_U)
        )
        s_sum_ybpi_F, s_sum_ybpi_U = (
            sum(
                o.max_sell_amount / o.max_xrate for o in fn(s_orders, s_partial_idx)
            ) for fn in (self.orders_F, self.orders_U)
        )
        f = 1 - self.fee.value
        return f * (b_sum_yb_F - b_sum_yb_U) - s_sum_ybpi_F + s_sum_ybpi_U

    def compute_constants(self, interval_data):
        b_orders, s_orders = interval_data.orders
        b_partial_idx, s_partial_idx = interval_data.partial

        b_pi = b_orders[b_partial_idx].max_xrate
        s_pi = s_orders[s_partial_idx].max_xrate

        b_yb = b_orders[b_partial_idx].max_sell_amount
        s_yb = s_orders[s_partial_idx].max_sell_amount

        b_yb_F = self.sum_yb_F(b_orders, b_partial_idx)
        s_yb_F = self.sum_yb_F(s_orders, s_partial_idx)

        c = self.c_constant(b_orders, b_partial_idx, s_orders, s_partial_idx)
        f = 1 - self.fee.value

        return self.Constants(
            b_pi=b_pi, b_yb=b_yb, b_yb_F=b_yb_F,
            s_pi=s_pi, s_yb=s_yb, s_yb_F=s_yb_F,
            c=c, f=f
        )

    # Root 1:
    # xrate == b_pi * (1 - fee)
    # examples: data/token_pair-1-1-5.json
    def root1(self, b_exec_order):
        b_pi = b_exec_order.max_xrate
        return b_pi * (1 - self.fee.value)

    # Root 2:
    # xrate == 1 / (s_pi * (1 - fee))
    # examples: data/token_pair-2-2-1.json
    def root2(self, s_exec_order):
        s_pi = s_exec_order.max_xrate
        return 1 / (s_pi * (1 - self.fee.value))

    # Root 3:
    # xrate in ]1/s_pi, b_pi[,
    # b_exec_order[0] fully filled,
    # s_exec_order[0] partially filled
    # examples: data/token_pair-3-2-1.json (local optimum only)
    def root3(self, c):
        fp = Config.FEE_TOKEN_PRICE

        n = 4 * (c.b_yb + c.b_yb_F)
        d1 = c.f * (c.s_pi * (c.c + 2 * (c.b_yb + c.b_yb_F)) + c.s_yb + 2 * c.s_yb_F)
        d2 = c.s_pi * (
            c.b_yb * (1 + c.f**2 * (2 * fp - 1))
            + c.b_yb_F * (1 - c.f**2)
        ) / (2 * fp)

        r = n / (d1 + d2)
        return r

    # Root 4:
    # xrate in ]1/s_pi, b_pi[,
    # b_exec_order[0] partially filled,
    # s_exec_order[0] fully filled
    # examples: data/token_pair-1-1-1.json, data/token_pair-2-1-1.json
    def root4(self, c):
        n = c.b_pi * (c.s_pi * (-c.c + c.f * c.b_yb + 2 * c.f * c.b_yb_F) + c.s_yb)
        d = 2 * c.f * c.s_pi * (c.s_yb + c.s_yb_F)
        t = n / d
        r = F(sqrt(t)) if t >= 0 else None
        return r

    # Root 5:
    # xrate in ]1/s_pi, b_pi[,
    # all orders fully filled
    # examples: data/token_pair-1-1-{2,4}.json, data/token_pair-2-2-2.json
    def root5(self, c):
        r = (c.b_yb + c.b_yb_F) / (c.f * (c.s_yb + c.s_yb_F))
        return r

    # Computes objective value from order execution via `compute_buy_amounts`.
    def compute_objective(self, xrate, b_orders, s_orders):
        compute_buy_amounts(
            xrate, b_orders, s_orders, fee=self.fee
        )
        return compute_objective_rational(
            b_orders=b_orders, s_orders=s_orders, f_orders=[],
            xrate=xrate,
            b_buy_token_price=1,
            fee=self.fee
        )

    # Collect the local optima that lie strictly within the given interval.
    # Also returns the id (3-5) of the root for debugging purposes
    def collect_local_optima_within_interval(self, interval_data):
        constants = self.compute_constants(interval_data)
        xrates = list(map(lambda f: f(constants), [
            self.root3, self.root4, self.root5
        ]))
        # Filter out solutions that fall outside the given xrate interval.
        xrate_lb, xrate_ub = interval_data.xrate
        xrates = [
            (xrate, i + 2) for i, xrate in enumerate(xrates)
            if xrate is not None and xrate > xrate_lb and xrate < xrate_ub
        ]
        # aggregate by root value
        xrates = sorted(xrates, key=lambda xi: xi[0])
        xrates = [
            (k, [(i + 1) for x, i in g])
            for k, g in groupby(xrates, key=lambda xi: xi[0])
        ]
        return xrates

    # Compute the optimal xrate in the interval ]xrate_lb, xrate_ub[.
    def solve_interval(self, interval_data):
        xrates = self.collect_local_optima_within_interval(interval_data)

        xrate_lb, xrate_ub = interval_data.xrate
        b_orders, s_orders = interval_data.orders

        if len(xrates) == 0:
            return (None, None)

        xrates_obj = [
            (
                xrate,
                root_ids,
                self.compute_objective(xrate, b_orders, s_orders)
            ) for xrate, root_ids in xrates
        ]

        opt = max(xrates_obj, key=lambda xio: xio[2])

        logger.debug(
            "Exchange rate candidates in interval xrate \u2208 [%s, %s]:",
            xrate_lb, xrate_ub
        )
        for xrate, root_ids, obj in xrates_obj:
            logger.debug(
                "\troots%s : (%s, %s)\t" + ("[local optimum]" if obj == opt[2] else ""),
                root_ids, xrate, obj
            )

        return (opt[0], opt[2])

    # Collect the local optima in case there is no match.
    # Also returns the id (1-2) of the root for debugging purposes
    # The buy/sell amounts can be zero because of:
    # a) Incompatible limit xrates
    # b) Side constraints (min tradable amount, economic viability, etc.)
    # When this happens, one of the limit xrates (roots 1,2) is optimal.
    # If the cause of no matching is a), there can be other optimal points which
    # are more interesting, e.g. for price estimation (see issue #25).
    def collect_local_optima_for_trivial_solution(self, b_orders, s_orders):
        xrates = [
            (self.root1(b_order), 0) for b_order in b_orders
        ] + [
            (self.root2(s_order), 1) for s_order in s_orders
        ]
        # aggregate by root value
        xrates = sorted(xrates, key=lambda xi: xi[0])
        xrates = [
            (k, [(i + 1) for x, i in g])
            for k, g in groupby(xrates, key=lambda xi: xi[0])
        ]
        return xrates

    # The objective function is non-deferentiable but has only one
    # local optimum. It's semi-derivative has only one zero, which
    # can be found in O(log2(n)) steps using binary search.
    def solve_trivial_bin_search(self, xrates, b_orders, s_orders):

        # Remove duplicates and sort.
        xrates = sorted(list(set(xrates)))

        # Memoizing this function saves a few computations,
        # since the code below may evaluate the objective on the
        # same point multiple times.
        @lru_cache(maxsize=ceil(log(len(xrates))))
        def f(xrate):
            return self.compute_objective(xrate, b_orders, s_orders)

        # If the least as at most 2 elements, there's no need for binary search.
        if len(xrates) <= 2:
            xrate = max(xrates, key=f)
            return xrate, f(xrate)

        # Case where the optimal is the leftmost element.
        if f(xrates[0]) > f(xrates[1]):
            return xrates[0], f(xrates[0])

        # Case where the optimal is the rightmost element.
        if f(xrates[-1]) > f(xrates[-2]):
            return xrates[-1], f(xrates[-1])

        # binary search on the semi-derivative of f(xrate)
        left = 1
        right = len(xrates) - 1
        center = (left + right) // 2
        while left != center and right != center:
            d_left = f(xrates[left]) - f(xrates[left - 1])
            d_right = f(xrates[right]) - f(xrates[right - 1])
            d_center = f(xrates[center]) - f(xrates[center - 1])
            if d_left * d_center > 0:
                assert d_left > 0
                left = center
            else:
                assert d_right < 0
                assert d_center < 0
                right = center
            center = (left + right) // 2

        return xrates[center], f(xrates[center])

    # Compute the optimal xrate for the trivial solution (zero buy/sell amounts).
    def solve_trivial(self, b_orders, s_orders):
        xrates = self.collect_local_optima_for_trivial_solution(b_orders, s_orders)

        if len(xrates) == 0:
            return (None, None)

        # Ignore root_ids.
        xrates = [xrate for xrate, root_ids in xrates]
        xrate, obj = self.solve_trivial_bin_search(xrates, b_orders, s_orders)

        return xrate, obj

    def solve(self, b_orders, s_orders):
        b_orders, s_orders = prune_unrealizable_orders(b_orders, s_orders, self.fee)

        # xrate local optima for trivial solution.
        xrates_obj = [
            self.solve_trivial(b_orders, s_orders)
        ]

        # find the xrate for the trivial solution with maximum objective.
        best_trivial_xrate = max(xrates_obj, key=lambda x: x[1])[0]

        xrates_obj += [
            self.solve_interval(interval_data)
            for interval_data in xrate_interval_iterator(
                b_orders, s_orders, self.fee, best_trivial_xrate
            )
        ]

        # Filter out invalid xrates.
        xrates_obj = [(xrate, obj) for xrate, obj in xrates_obj if xrate is not None]

        if len(xrates_obj) == 0:
            return None, None

        # Global optimum is maximum of local optima.
        return max(xrates_obj, key=lambda xo: xo[1])


def find_best_xrate(b_orders, s_orders, fee, Solver=SymbolicSolver):
    """Find the optimal xrate for executing a set of orders and counter-orders.

    Convention: xrate = p(b_buy_token) / p(s_buy_token) = s_buy_amount / b_buy_amount.
    """
    solver = Solver(fee)
    return solver.solve(b_orders, s_orders)
