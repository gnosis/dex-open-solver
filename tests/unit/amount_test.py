from hypothesis import given, strategies as s
from fractions import Fraction as F

from src.token_pair_solver.amount import compute_buy_amounts
from src.core.validation import validate
from src.core.api import Fee
from src.core.order_util import RationalTraits

from tests.unit.strategies import random_xrate, random_order_list

fee = Fee(token='T0', value=F(1, 1000))


@given(
    random_order_list(min_size=1, max_size=4, buy_token='T0', sell_token='T1'),
    random_order_list(min_size=1, max_size=4, buy_token='T1', sell_token='T0'),
    random_xrate(),
    s.integers(min_value=2, max_value=8)
)
def test_compute_buy_amounts(b_orders, s_orders, xrate, max_nr_exec_orders):
    compute_buy_amounts(xrate, b_orders, s_orders, fee, max_nr_exec_orders)

    prices = {
        'T0': xrate.numerator,
        'T1': xrate.denominator
    }

    for order in b_orders + s_orders:
        order.set_sell_amount_from_buy_amount(prices, fee, RationalTraits)

    # create accounts that cover all sell amounts
    accounts = {
        'A': {
            'T0': sum(s_order.sell_amount for s_order in s_orders),
            'T1': sum(b_order.sell_amount for b_order in b_orders)
        }
    }
    for b_order in b_orders:
        b_order.account_id = 'A'
    for s_order in s_orders:
        s_order.account_id = 'A'

    validate(
        accounts=accounts,
        orders=b_orders + s_orders,
        prices=prices,
        fee=fee,
        max_nr_exec_orders=max_nr_exec_orders
    )
