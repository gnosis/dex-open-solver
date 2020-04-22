from fractions import Fraction as F

from hypothesis import event, given
from hypothesis import strategies as s

from src.core.api import Fee
from src.core.order_util import RationalTraits
from src.core.orderbook import count_nr_exec_orders
from src.core.validation import validate
from src.token_pair_solver.amount import compute_buy_amounts
from tests.unit.amount_test_examples import (
    max_nr_orders_constraint_examples, min_tradable_amount_constraint_examples
)
from tests.unit.strategies import random_small_order_list, random_xrate
from tests.unit.util import examples

fee = Fee(token='T0', value=F(1, 1000))


def compute_buy_amounts_helper(b_orders, s_orders, xrate, max_nr_exec_orders):
    compute_buy_amounts(xrate, b_orders, s_orders, fee, max_nr_exec_orders)

    prices = {
        'T0': xrate.numerator,
        'T1': xrate.denominator
    }

    for order in b_orders + s_orders:
        order.set_sell_amount_from_buy_amount(prices, fee, RationalTraits)

    if count_nr_exec_orders(b_orders) == 0:
        event("found trivial solution")
    else:
        event("found non-trivial solution")

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


# Tests main function using small amount orders, to maximize likelihood of creating
# problems that violate side constraints.
@given(
    random_small_order_list(min_size=1, max_size=4, buy_token='T0', sell_token='T1'),
    random_small_order_list(min_size=1, max_size=4, buy_token='T1', sell_token='T0'),
    random_xrate(),
    s.integers(min_value=2, max_value=8)
)
@examples(max_nr_orders_constraint_examples)
@examples(min_tradable_amount_constraint_examples)
def test_compute_buy_amounts_small(b_orders, s_orders, xrate, max_nr_exec_orders):
    compute_buy_amounts_helper(b_orders, s_orders, xrate, max_nr_exec_orders)
