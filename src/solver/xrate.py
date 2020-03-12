"""Compute the optimal exchange rate for a set of orders between two tokens.

Given an array YB of maximum sell amounts and an array PI of maximum exchange rates,
solves the following optimization problem:

xrate* = argmax_{X, xrate} f(X, xrate)
s.t.
x_i * xrate <= yb_i, for all x_i in X.
xrate <= pi_i, for all pi_i in PI.
"""
from math import sqrt

from ..util import order_sell_amount, order_limit_xrate
from .amount import find_best_buy_amounts
from ..objective import evaluate_objective_rational
import logging
from collections import namedtuple, deque
from itertools import groupby
from fractions import Fraction as F

logger = logging.getLogger(__name__)


def xrate_interval_iterator(b_orders, s_orders, fee):
    assert len(b_orders) > 0 and len(s_orders) > 0
    B, S = 0, 1

    f = 1 - fee
    Order = namedtuple('Order', ['type', 'xrate', 'data'])
    all_orders = [
        Order(B, order_limit_xrate(b_order) / f, b_order)
        for b_order in b_orders
    ] + [
        Order(S, 1 / (order_limit_xrate(s_order) / f), s_order)
        for s_order in s_orders
    ]

    all_orders = sorted(all_orders, key=lambda order: order.xrate, reverse=True)

    b_exec_orders = deque()
    s_exec_orders = deque([order.data for order in all_orders if order.type == S])
    b_exec_sell_amount = 0
    s_exec_sell_amount = sum(order_sell_amount(s_order) for s_order in s_orders)
    for order_i in range(len(all_orders) - 1):
        order_type, order_xrate, order = all_orders[order_i]
        next_order_xrate = all_orders[order_i + 1].xrate

        if order_type == B:
            b_exec_orders.appendleft(order)
            b_exec_sell_amount += order_sell_amount(order)

        if order_type == S:
            s_exec_orders.popleft()
            s_exec_sell_amount -= order_sell_amount(order)

        if len(b_exec_orders) == 0:
            continue
        if len(s_exec_orders) == 0:
            return

        xrate_lb = next_order_xrate
        xrate_ub = order_xrate

        b_exec_sell_amount_lb = b_exec_sell_amount - order_sell_amount(b_exec_orders[0])
        b_exec_sell_amount_ub = b_exec_sell_amount

        s_exec_sell_amount_lb = s_exec_sell_amount - order_sell_amount(s_exec_orders[0])
        s_exec_sell_amount_ub = s_exec_sell_amount

        if s_exec_sell_amount_ub > 0:
            xrate_lb = max(xrate_lb, b_exec_sell_amount_lb / s_exec_sell_amount_ub)
        if s_exec_sell_amount_lb > 0:
            xrate_ub = min(xrate_ub, b_exec_sell_amount_ub / s_exec_sell_amount_lb)

        if xrate_lb > xrate_ub:
            continue

        yield xrate_lb, xrate_ub, list(b_exec_orders), list(s_exec_orders)


# TODO: check if possible to describe the set of roots more compactly.

yb = order_sell_amount
pi = order_limit_xrate


class SymbolicSolver:
    def __init__(self, fee):
        self.fee = fee

    # Root 1:
    # xrate == b_pi
    # examples: data/token_pair-1-1-5.json
    def root1(self, b_exec_orders, s_exec_orders):
        b_pi = pi(b_exec_orders[0])
        return b_pi * (1 - self.fee)

    # Root 2:
    # xrate == 1/s_pi
    # examples: data/token_pair-2-2-1.json
    def root2(self, b_exec_orders, s_exec_orders):
        s_pi = pi(s_exec_orders[0])
        return 1 / (s_pi * (1 - self.fee))

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

        f = 1 - self.fee
        r = 4 * b_yb_sum / ((2 + f) * s_pi * b_yb_sum + f * s_yb + f * t)
        return r

    # Root 4:
    # xrate in ]1/s_pi, b_pi[,
    # b_exec_order[0] partially filled,
    # s_exec_order[0] fully filled
    # examples: data/token_pair-1-1-1.json, data/token_pair-2-1-1.json
    # TODO: It seems this root can only be the optimum when len(s_exec_order)==1. Why?
    def root4(self, b_exec_orders, s_exec_orders):
        if len(s_exec_orders) > 1:
            return None
        b_pi = pi(b_exec_orders[0])
        s_pi = pi(s_exec_orders[0])
        s_yb = yb(s_exec_orders[0])
        b_yb_sum = sum(yb(b_order) for b_order in b_exec_orders)

        t = b_pi * (s_pi * b_yb_sum + s_yb) / (2 * s_pi * s_yb * (1 - self.fee))
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

        r = b_yb_sum / (s_yb_sum * (1 - self.fee))
        return r

    # Also returns the id (1-5) of the root for debugging purposes
    def collect_local_optima(self, xrate_lb, xrate_ub, b_exec_orders, s_exec_orders):
        xrates = map(lambda f: f(b_exec_orders, s_exec_orders), [
            self.root1, self.root2, self.root3,
            self.root4, self.root5
        ])
        xrates = [
            (xrate, i) for i, xrate in enumerate(xrates)
            if xrate is not None and xrate >= xrate_lb and xrate <= xrate_ub
        ]
        # aggregate by root value
        xrates = sorted(xrates, key=lambda xi: xi[0])
        xrates = [
            (k, [(i + 1) for x, i in g])
            for k, g in groupby(xrates, key=lambda xi: xi[0])
        ]
        return xrates

    def solve_interval(self, xrate_lb, xrate_ub, b_exec_orders, s_exec_orders):
        xrates = self.collect_local_optima(
            xrate_lb, xrate_ub, b_exec_orders, s_exec_orders
        )

        if len(xrates) == 0:
            return (None, None)

        def compute_objective(xrate):
            b_buy_amounts, s_buy_amounts = find_best_buy_amounts(
                xrate, b_exec_orders, s_exec_orders, fee=self.fee
            )
            return evaluate_objective_rational(
                b_exec_orders, s_exec_orders, xrate,
                b_buy_amounts, s_buy_amounts,
                b_buy_token_price=1,
                fee=self.fee
            )

        xrates_obj = [
            (
                xrate,
                root_ids,
                compute_objective(xrate)
            ) for xrate, root_ids in xrates
        ]

        opt = max(xrates_obj, key=lambda xio: xio[2])

        b_pi = pi(b_exec_orders[0])
        s_pi = pi(s_exec_orders[0])
        for xrate, root_ids, obj in xrates_obj:
            logger.debug(
                f"xrate in [{float(1/s_pi)}, {float(b_pi)}] -> "
                + f"roots{root_ids}=({float(xrate)}, {float(obj)}) "
                + ("[LOC_OPT]" if obj == opt[2] else "")
            )

        return (opt[0], opt[2])

    def solve(self, b_orders, s_orders):
        xrates_obj = [
            self.solve_interval(
                xrate_lb, xrate_ub, b_exec_orders, s_exec_orders
            )
            for xrate_lb, xrate_ub, b_exec_orders, s_exec_orders
            in xrate_interval_iterator(b_orders, s_orders, self.fee)
        ]
        xrates_obj = [(xrate, obj) for xrate, obj in xrates_obj if xrate is not None]

        return max(xrates_obj, key=lambda xo: xo[1])


def find_best_xrate(b_orders, s_orders, fee, Solver=SymbolicSolver):
    """Find the optimal xrate for executing a set of orders and counter-orders.

    Convention: xrate = p(b_buy_token) / p(s_buy_token) = s_buy_amount / b_buy_amount.
    """
    solver = Solver(fee)
    return solver.solve(b_orders, s_orders)
