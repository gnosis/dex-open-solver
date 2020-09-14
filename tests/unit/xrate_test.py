from fractions import Fraction as F

from hypothesis import assume, given, settings

from dex_open_solver.core.api import Fee
from dex_open_solver.core.config import Config
from dex_open_solver.token_pair_solver.amount import compute_buy_amounts
from dex_open_solver.token_pair_solver.orderbook import compute_objective_rational
from dex_open_solver.token_pair_solver.xrate import find_best_xrate
from tests.unit.strategies import random_order_list
from tests.unit.util import examples
from tests.unit.xrate_test_examples import find_best_xrate_examples

fee = Fee(token='T0', value=F(1, 1000))


def compute_objective(b_orders, s_orders, xrate, fee):
    compute_buy_amounts(xrate, b_orders, s_orders, fee)
    return compute_objective_rational(
        b_orders, s_orders, [],
        xrate,
        b_buy_token_price=1,
        fee=fee
    )


@given(
    random_order_list(min_size=1, max_size=4, buy_token='T0', sell_token='T1'),
    random_order_list(min_size=1, max_size=4, buy_token='T1', sell_token='T0')
)
@examples(find_best_xrate_examples)
@settings(deadline=None)
def test_find_best_xrate(b_orders, s_orders):
    """Test if find_best_xrate returns the optimal xrate."""

    # Skip cases when there is no possible matching:
    b_order_xrates = [b_o.max_xrate * (1 - fee.value) for b_o in b_orders]
    s_order_xrates = [1 / (s_o.max_xrate * (1 - fee.value)) for s_o in s_orders]

    xrate_ub = max(b_order_xrates)
    xrate_lb = min(s_order_xrates)

    assume(xrate_lb <= xrate_ub)

    # Disable side constraints.
    Config.MAX_NR_EXEC_ORDERS = len(b_orders) + len(s_orders)
    Config.MIN_TRADABLE_AMOUNT = 0

    optimal_xrate, _ = find_best_xrate(b_orders, s_orders, fee)
    optimal_objective = compute_objective(b_orders, s_orders, optimal_xrate, fee)

    # brute-force algorithm to try to find a better xrate
    nr_steps = 100
    step = (xrate_ub - xrate_lb) / nr_steps
    xrate = xrate_lb
    while xrate <= xrate_ub:
        objective = compute_objective(b_orders, s_orders, xrate, fee)
        assert objective <= optimal_objective
        xrate += step
