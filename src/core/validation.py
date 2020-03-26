from .constants import MINIMUM_TRADABLE_AMOUNT
from fractions import Fraction as F


def validate_order_constraints(order, buy_amount, sell_amount):
    # Limit exchange rate constraint
    assert buy_amount == 0 or F(sell_amount, buy_amount) <= order.max_xrate

    # Maximum sell amount constraint
    assert sell_amount <= order.max_sell_amount

    # Minimum tradable amount constraint
    assert buy_amount == 0 or buy_amount >= MINIMUM_TRADABLE_AMOUNT
    assert sell_amount == 0 or sell_amount >= MINIMUM_TRADABLE_AMOUNT


def validate(
    accounts,
    orders,
    prices,
    fee
):
    assert all(price.denominator == 1 for price in prices.values())

    tokens = prices.keys()
    token_balances = {token: 0 for token in tokens}

    token_balance_account = {
        order.account_id: {
            token: int(accounts[order.account_id].get(token, 0))
            for token in tokens
        }
        for order in orders
    }

    for order in orders:
        validate_order_constraints(order, order.buy_amount, order.sell_amount)
        token_balances[order.buy_token] -= order.buy_amount
        token_balances[order.sell_token] += order.sell_amount
        token_balance_account[order.account_id][order.buy_token] += order.buy_amount
        token_balance_account[order.account_id][order.sell_token] -= order.sell_amount

    for token in token_balances.keys():
        if token == fee.token:
            # there is more fee sold than bought
            assert token_balances[token] >= 0
        else:
            assert token_balances[token] == 0

    assert all(token_balance_account[aID][t] >= 0
               for aID in token_balance_account
               for t in token_balance_account[aID]
               )
