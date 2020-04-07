"""Compute the optimal exchange rate for a set of orders between two tokens.

Given an array YB of maximum sell amounts and an array PI of maximum exchange rates,
solves the following optimization problem:

xrate* = argmax_{X, xrate} f(X, xrate)
s.t.
x_i * xrate <= yb_i, for all x_i in X.
xrate <= pi_i, for all pi_i in PI.
"""
import logging
from collections import deque, namedtuple
from fractions import Fraction as F
from itertools import groupby
from math import sqrt

from src.core.config import Config

from .amount import compute_buy_amounts
from .orderbook import compute_objective_rational

logger = logging.getLogger(__name__)


def xrate_interval_iterator(b_orders, s_orders, fee):
    """Exchange rate interval [xrate_lb, xrate_lb] iterator.

    Iterates through intervals [xrate_lb, xrate_ub] of possible values for xrate,
    where xrate_lb, xrate_ub are defined by the max_xrate's of two orders that are
    consecutive in the optimal execution order.

    At each iteration yields the xrate interval, and two sorted lists: the b_orders
    and s_orders, which can be executed if xrate is in the given interval.

    Skips iterations where this interval is trivially empty.
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
    b_exec_sell_amount = 0

    # Total sell amount of s_orders in the s_exec_orders list.
    s_exec_sell_amount = sum(s_order.max_sell_amount for s_order in s_orders)

    # Main loop.
    for order_i in range(len(all_orders) - 1):
        order_type, order_xrate, order = all_orders[order_i]
        next_order_xrate = all_orders[order_i + 1].xrate

        # Update exec_orders / exec_sell_amounts.
        if order_type == B:
            b_exec_orders.appendleft(order)
            b_exec_sell_amount += order.max_sell_amount

        if order_type == S:
            s_exec_orders.popleft()
            s_exec_sell_amount -= order.max_sell_amount

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

        # The following block of code is an optimization, it tries to shrink the above
        # xrate interval, potentially making it empty thus skipping the current iteration.

        # In any optimal execution, either the the b_order right above the optimal xrate
        # or the s_order right below will be partially executed (i.e. non empty).

        # In case xrate is in [xrate_lb, xrate_ub] then:
        # total b_exec_sell_amount is in [b_exec_sell_amount_lb, b_exec_sell_amount_ub].
        # total s_exec_sell_amount is in [s_exec_sell_amount_lb, s_exec_sell_amount_ub].

        # ub(exec_sell_amount) is the sold amount of all executed orders.
        b_exec_sell_amount_ub = b_exec_sell_amount
        s_exec_sell_amount_ub = s_exec_sell_amount

        # lb(exec_sell_amount) is the sold amount of all executed orders, except the
        # last one, which potentially may be only partially executed.
        b_exec_sell_amount_lb = b_exec_sell_amount - b_exec_orders[0].max_sell_amount
        s_exec_sell_amount_lb = s_exec_sell_amount - s_exec_orders[0].max_sell_amount

        # Interval arithmetic on the equation:
        # xrate = b_exec_sell_amount / (s_exec_sell_amount * (1 - fee)).
        if s_exec_sell_amount_ub > 0:
            xrate_lb = max(
                xrate_lb,
                b_exec_sell_amount_lb / (s_exec_sell_amount_ub * (1 - fee.value))
            )

        if s_exec_sell_amount_lb > 0:
            xrate_ub = min(
                xrate_ub,
                b_exec_sell_amount_ub / (s_exec_sell_amount_lb * (1 - fee.value))
            )

        # Skip current iteration if current xrate interval can't contain the optimal.
        if xrate_lb > xrate_ub:
            continue

        yield xrate_lb, xrate_ub, list(b_exec_orders), list(s_exec_orders)


# TODO: check if possible to describe the set of roots more compactly.

def yb(order):
    return order.max_sell_amount


def pi(order):
    return order.max_xrate


class SymbolicSolver:
    def __init__(self, fee):
        self.fee = fee

    # Root 1:
    # xrate == b_pi * (1 - fee)
    # examples: data/token_pair-1-1-5.json
    def root1(self, b_exec_orders, s_exec_orders):
        b_pi = pi(b_exec_orders[0])
        return b_pi * (1 - self.fee.value)

    # Root 2:
    # xrate == 1 / (s_pi * (1 - fee))
    # examples: data/token_pair-2-2-1.json
    def root2(self, b_exec_orders, s_exec_orders):
        s_pi = pi(s_exec_orders[0])
        return 1 / (s_pi * (1 - self.fee.value))

    # Root 3:
    # xrate in ]1/s_pi, b_pi[,
    # b_exec_order[0] fully filled,
    # s_exec_order[0] partially filled
    # examples: data/token_pair-3-2-1.json (local optimum only)
    def root3(self, b_exec_orders, s_exec_orders):
        s_pi = pi(s_exec_orders[0])
        s_yb = yb(s_exec_orders[0])
        b_yb_sum = sum(yb(b_order) for b_order in b_exec_orders)

        t = sum(
            yb(s_order) * (2 - s_pi / pi(s_order))
            for s_order in s_exec_orders[1:]
        )
        # since s_pi <= pi(s_order) for all s_order,
        # then it must be true that
        assert t >= 0

        f = 1 - self.fee.value

        fp = Config.FEE_TOKEN_PRICE
        c = 2 + f + (1 - f**2) / (2 * f * fp)
        r = 4 * b_yb_sum / (f * (c * s_pi * b_yb_sum + s_yb + t))
        return r

    # Root 4:
    # xrate in ]1/s_pi, b_pi[,
    # b_exec_order[0] partially filled,
    # s_exec_order[0] fully filled
    # examples: data/token_pair-1-1-1.json, data/token_pair-2-1-1.json
    def root4(self, b_exec_orders, s_exec_orders):
        b_pi = pi(b_exec_orders[0])

        b_yb_sum = sum(yb(b_order) for b_order in b_exec_orders)
        s_yb_sum = sum(yb(s_order) for s_order in s_exec_orders)

        f = 1 - self.fee.value

        a = sum(yb(s_order) / pi(s_order) for s_order in s_exec_orders)
        t = b_pi * (f * b_yb_sum + a) / (2 * f * s_yb_sum)
        r = sqrt(t) if t >= 0 else None

        # This is the only irrational root. Approximating:
        return F(r)

    # Root 5:
    # xrate in ]1/s_pi, b_pi[,
    # all orders fully filled
    # examples: data/token_pair-1-1-{2,4}.json, data/token_pair-2-2-2.json
    def root5(self, b_exec_orders, s_exec_orders):
        b_yb_sum = sum(yb(b_order) for b_order in b_exec_orders)
        s_yb_sum = sum(yb(s_order) for s_order in s_exec_orders)

        r = b_yb_sum / (s_yb_sum * (1 - self.fee.value))
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
    def collect_local_optima_within_interval(
        self, xrate_lb, xrate_ub, b_exec_orders, s_exec_orders
    ):
        xrates = map(lambda f: f(b_exec_orders, s_exec_orders), [
            self.root3, self.root4, self.root5
        ])
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
    def solve_interval(self, xrate_lb, xrate_ub, b_orders, s_orders):
        xrates = self.collect_local_optima_within_interval(
            xrate_lb, xrate_ub, b_orders, s_orders
        )

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
            (self.root1([b_order], None), 0) for b_order in b_orders
        ] + [
            (self.root2(None, [s_order]), 1) for s_order in s_orders
        ]
        # aggregate by root value
        xrates = sorted(xrates, key=lambda xi: xi[0])
        xrates = [
            (k, [(i + 1) for x, i in g])
            for k, g in groupby(xrates, key=lambda xi: xi[0])
        ]
        return xrates

    # Compute the optimal xrate for the trivial solution (zero buy/sell amounts).
    def solve_trivial(self, b_orders, s_orders):
        xrates = self.collect_local_optima_for_trivial_solution(b_orders, s_orders)

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

        logger.debug("Exchange rate candidates for trivial solution:")
        for xrate, root_ids, obj in xrates_obj:
            logger.debug(
                "\troots%s : (%s, %s)\t" + ("[local optimum]" if obj == opt[2] else ""),
                root_ids, xrate, obj
            )

        return (opt[0], opt[2])

    def solve(self, b_orders, s_orders):
        # xrate local optima within each xrate interval.
        xrates_obj = [
            self.solve_interval(
                xrate_lb, xrate_ub, b_exec_orders, s_exec_orders
            )
            for xrate_lb, xrate_ub, b_exec_orders, s_exec_orders
            in xrate_interval_iterator(b_orders, s_orders, self.fee)
        ]
        # xrate local optima for trivial solution.
        xrates_obj += [
            self.solve_trivial(b_orders, s_orders)
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
