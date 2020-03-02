from fractions import Fraction as F


def order_buy_amount(order):
    return F(order["buyAmount"])


def order_sell_amount(order):
    return F(order["sellAmount"])


def order_limit_xrate(order):
    return order_sell_amount(order) / order_buy_amount(order)
