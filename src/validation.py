from .objective import IntegerTraits, compute_sell_amounts_from_buy_amounts
from .util import order_sell_amount, order_limit_xrate
from fractions import Fraction as F


def validate(
    accounts,
    b_orders, s_orders,
    b_buy_amounts, s_buy_amounts,
    xrate,
    b_buy_token_price,
    fee,
    arith_traits=IntegerTraits()
):
    b_sell_amounts = compute_sell_amounts_from_buy_amounts(
        b_buy_amounts, xrate, b_buy_token_price, fee,
        arith_traits=arith_traits
    )
    s_sell_amounts = compute_sell_amounts_from_buy_amounts(
        s_buy_amounts, 1 / xrate, b_buy_token_price / xrate, fee,
        arith_traits=arith_traits
    )

    def validate_order_constraints(order, buy_amount, sell_amount):
        assert buy_amount == 0 or F(sell_amount, buy_amount) <= order_limit_xrate(order)
        assert sell_amount <= order_sell_amount(order)

    b_token_balance = 0
    s_token_balance = 0

    token_balance_account = {
        order['accountID']: {
            token: int(accounts[order['accountID']].get(token, 0))
            for token in [order['buyToken'], order['sellToken']]
        }
        for order in b_orders + s_orders}

    for order, buy_amount, sell_amount in zip(b_orders, b_buy_amounts, b_sell_amounts):
        validate_order_constraints(order, buy_amount, sell_amount)
        b_token_balance -= buy_amount
        s_token_balance += sell_amount
        token_balance_account[order['accountID']][order['buyToken']] += buy_amount
        token_balance_account[order['accountID']][order['sellToken']] -= sell_amount

    for order, buy_amount, sell_amount in zip(s_orders, s_buy_amounts, s_sell_amounts):
        validate_order_constraints(order, buy_amount, sell_amount)
        s_token_balance -= buy_amount
        b_token_balance += sell_amount
        token_balance_account[order['accountID']][order['buyToken']] += buy_amount
        token_balance_account[order['accountID']][order['sellToken']] -= sell_amount

    assert s_token_balance == 0 and b_token_balance >= 0
    assert all(token_balance_account[aID][t] >= 0
               for aID in token_balance_account
               for t in token_balance_account[aID]
               )
