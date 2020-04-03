from hypothesis import given, strategies as s
from fractions import Fraction as F

from src.token_pair_solver.solver import solve_token_pair_and_fee_token
from src.core.api import Fee

from tests.unit.strategies import random_order_list

fee = Fee(token='F', value=F(1, 1000))


@given(
    random_order_list(min_size=1, max_size=4, buy_token='T0', sell_token='T1'),
    random_order_list(min_size=1, max_size=4, buy_token='T1', sell_token='T0'),
    random_order_list(min_size=1, max_size=4, buy_token='T0', sell_token='F'),
    s.integers(min_value=2, max_value=12)
)
def test_solve_token_pair_and_fee_token(b_orders, s_orders, f_orders, max_nr_exec_orders):
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

    solve_token_pair_and_fee_token(
        token_pair, accounts, b_orders, s_orders, f_orders, fee,
        xrate=None
    )
