from fractions import Fraction as F

from .config import Config
from .orderbook import count_nr_exec_orders


def validate_order_constraints(order, buy_amount, sell_amount):
    # Limit exchange rate constraint
    assert buy_amount == 0 or F(sell_amount, buy_amount) <= order.max_xrate

    # Maximum sell amount constraint
    assert sell_amount <= order.max_sell_amount

    # Minimum tradable amount constraint
    assert buy_amount == 0 or buy_amount >= Config.MIN_TRADABLE_AMOUNT
    assert sell_amount == 0 or sell_amount >= Config.MIN_TRADABLE_AMOUNT


def validate(
    accounts,
    orders,
    prices,
    fee,
    max_nr_exec_orders=None
):
    # NOTE: do not add this as a default parameter above, since
    # default parameters are evaluated when the function is defined, and
    # not when it is called. This means that runtime changes to the Config
    # singleton would not be reflected.
    if max_nr_exec_orders is None:
        max_nr_exec_orders = Config.MAX_NR_EXEC_ORDERS

    assert all(price.denominator == 1 for price in prices.values())

    nr_exec_orders = count_nr_exec_orders(orders)

    if nr_exec_orders == 0:
        return

    # Validate maximum number of executed orders constraint.
    assert nr_exec_orders <= max_nr_exec_orders

    tokens = prices.keys()
    token_balances = {token: 0 for token in tokens}

    token_balance_account = {
        order.account_id: {
            token: int(accounts[order.account_id].get(token, 0))
            for token in tokens
        }
        for order in orders
    }

    # Validate order constraints, and collect token and account balances.
    for order in orders:
        validate_order_constraints(order, order.buy_amount, order.sell_amount)
        token_balances[order.buy_token] -= order.buy_amount
        token_balances[order.sell_token] += order.sell_amount
        token_balance_account[order.account_id][order.buy_token] += order.buy_amount
        token_balance_account[order.account_id][order.sell_token] -= order.sell_amount

    # Validate token balance constraint.
    for token in token_balances.keys():
        if token == fee.token:
            # there is more fee sold than bought
            assert token_balances[token] >= 0
        else:
            assert token_balances[token] == 0

    # Validate economic viability constraint.
    total_fees = token_balances[fee.token]
    assert total_fees / nr_exec_orders >= Config.MIN_AVERAGE_ORDER_FEE

    # Validate account balance constraint.
    assert all(token_balance_account[aID][t] >= 0
               for aID in token_balance_account
               for t in token_balance_account[aID]
               )
