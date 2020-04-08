from fractions import Fraction as F

from hypothesis import event, example, given
from hypothesis import strategies as s

from src.core.api import Fee
from src.core.config import Config
from src.core.order import Order
from src.core.orderbook import count_nr_exec_orders
from src.token_pair_solver.solver import solve_token_pair_and_fee_token_economic_viable
from tests.unit.strategies import random_order_list


fee = Fee(token='F', value=F(1, 1000))

example_1 = {
    'b_orders': [
        Order(0, None, 'T0', 'T1', 11109, F(1))
    ],
    's_orders': [
        Order(2, None, 'T1', 'T0', 11132, F(17, 10))
    ],
    'f_orders': [
        Order(4, None, 'T0', 'F', 9000, F(228, 25))
    ],
    'max_nr_exec_orders': 3
}


@given(
    random_order_list(min_size=1, max_size=4, buy_token='T0', sell_token='T1'),
    random_order_list(min_size=1, max_size=4, buy_token='T1', sell_token='T0'),
    random_order_list(min_size=1, max_size=4, buy_token='T0', sell_token='F'),
    s.integers(min_value=2, max_value=12)
)
@example(**example_1)
def test_solve_token_pair_and_fee_token_economic_viable(
    b_orders, s_orders, f_orders, max_nr_exec_orders
):
    token_pair = ('T0', 'T1')

    Config.MAX_NR_EXEC_ORDERS = max_nr_exec_orders
    Config.MAX_ROUNDING_VOLUME = 100

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

    event(f"trivial solution = {count_nr_exec_orders(orders) == 0}")
