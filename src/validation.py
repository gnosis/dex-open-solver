from .objective import IntegerTraits, compute_sell_amounts_from_buy_amounts
from .util import order_sell_amount, order_limit_xrate

def validate(
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
        assert buy_amount == 0 or sell_amount / buy_amount <= order_limit_xrate(order)
        assert sell_amount <= order_sell_amount(order)

    b_token_balance = 0
    s_token_balance = 0
    for order, buy_amount, sell_amount in zip(b_orders, b_buy_amounts, b_sell_amounts):
        validate_order_constraints(order, buy_amount, sell_amount)
        b_token_balance -= buy_amount
        s_token_balance += sell_amount

    for order, buy_amount, sell_amount in zip(s_orders, s_buy_amounts, s_sell_amounts):
        validate_order_constraints(order, buy_amount, sell_amount)
        s_token_balance -= buy_amount
        b_token_balance += sell_amount

    assert s_token_balance == 0 and b_token_balance >= 0
