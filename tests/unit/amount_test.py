from hypothesis import given
from fractions import Fraction as F

from src.solver.amount import find_best_buy_amounts
from src.validation import validate
from src.objective import RationalTraits

from tests.unit.strategies import random_xrate, random_order_list

fee = F(1, 1000)


@given(
    random_order_list(min_size=1, max_size=4, buy_token="T0", sell_token="T1"),
    random_order_list(min_size=1, max_size=4, buy_token="T1", sell_token="T0"),
    random_xrate()
)
def test_find_best_buy_amounts(b_orders, s_orders, xrate):
    b_buy_amounts, s_buy_amounts = find_best_buy_amounts(
        xrate, b_orders, s_orders, fee
    )
    # create accounts that cover all sell amounts
    accounts = {
        "A": {
            "T0": sum(s_buy_amounts),
            "T1": sum(b_buy_amounts)
        }
    }
    for b_order in b_orders:
        b_order["accountID"] = "A"
    for s_order in s_orders:
        s_order["accountID"] = "A"
    validate(
        accounts,
        b_orders, s_orders,
        b_buy_amounts, s_buy_amounts,
        xrate, 1, fee, RationalTraits()
    )
