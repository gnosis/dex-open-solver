from fractions import Fraction as F

from hypothesis import event, given

from src.core.api import Fee
from src.core.config import Config
from src.core.orderbook import count_nr_exec_orders
from src.token_pair_solver.solver import (
    solve_token_pair_and_fee_token_economic_viable
)
from tests.unit.solver_test_examples import (
    min_average_order_fee_constraint_examples,
    solve_token_pair_and_fee_token_examples)
from tests.unit.strategies import random_order_list
from tests.unit.util import examples


def solve_token_pair_and_fee_token_helper(
    b_orders, s_orders, f_orders, fee
):
    token_pair = ('T0', 'T1')

    # create accounts that cover all sell amounts
    # (for efficiency this function does not test account balance constraints).
    accounts = {
        'A': {
            'T0': sum(s_order.max_sell_amount for s_order in s_orders),
            'T1': sum(b_order.max_sell_amount for b_order in b_orders),
            'F': sum(f_order.max_sell_amount for f_order in f_orders)
        }
    }
    for b_order in b_orders:
        b_order.account_id = 'A'
    for s_order in s_orders:
        s_order.account_id = 'A'
    for f_order in f_orders:
        f_order.account_id = 'A'

    orders, prices = solve_token_pair_and_fee_token_economic_viable(
        token_pair, accounts, b_orders, s_orders, f_orders, fee
    )

    if count_nr_exec_orders(orders) == 0:
        event("found trivial solution")
    else:
        event("found non-trivial solution")


# Test main function using default constants.
@given(
    random_order_list(min_size=1, max_size=4, buy_token='T0', sell_token='T1'),
    random_order_list(min_size=1, max_size=4, buy_token='T1', sell_token='T0'),
    random_order_list(min_size=1, max_size=4, buy_token='T0', sell_token='F')
)
@examples(solve_token_pair_and_fee_token_examples)
def test_solve_token_pair_and_fee_token(b_orders, s_orders, f_orders):
    fee = Fee(token='F', value=F(1, 1000))
    Config.MIN_AVERAGE_ORDER_FEE = 0
    Config.MIN_ABSOLUTE_ORDER_FEE = 0
    solve_token_pair_and_fee_token_helper(b_orders, s_orders, f_orders, fee)


# Test minimum average fee per order constraint.
@given(
    random_order_list(min_size=1, max_size=4, buy_token='T0', sell_token='T1'),
    random_order_list(min_size=1, max_size=4, buy_token='T1', sell_token='T0'),
    random_order_list(min_size=1, max_size=4, buy_token='T0', sell_token='F')
)
@examples(min_average_order_fee_constraint_examples)
def test_min_average_order_fee_constraint(
    b_orders, s_orders, f_orders
):
    fee = Fee(token='F', value=F(1, 1000))

    Config.MIN_AVERAGE_ORDER_FEE = int(10e18)
    Config.MIN_ABSOLUTE_ORDER_FEE = 0

    solve_token_pair_and_fee_token_helper(b_orders, s_orders, f_orders, fee)


# Test minimum absolute fee per order constraint.
@given(
    random_order_list(min_size=1, max_size=4, buy_token='T0', sell_token='T1'),
    random_order_list(min_size=1, max_size=4, buy_token='T1', sell_token='T0'),
    random_order_list(min_size=1, max_size=4, buy_token='T0', sell_token='F')
)
def test_min_absolute_order_fee_constraint(
    b_orders, s_orders, f_orders
):
    # Note that fee ratio here is different than usual.
    fee = Fee(token='F', value=F(1, 1000))

    Config.MIN_AVERAGE_ORDER_FEE = 0
    Config.MIN_ABSOLUTE_ORDER_FEE = int(10e18)

    solve_token_pair_and_fee_token_helper(b_orders, s_orders, f_orders, fee)
