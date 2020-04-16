"""Functions for orderbooks containing 2 tokens (and optionally the fee token)."""
from fractions import Fraction as F

from src.core.config import Config
from src.core.order_util import IntegerTraits, RationalTraits


def compute_sell_amounts_from_buy_amounts(
    buy_amounts, xrate, buy_token_price, fee,
    arith_traits=RationalTraits
):
    sell_amounts = [
        arith_traits.compute_sell_from_buy_amount(
            buy_amount=buy_amount,
            xrate=xrate,
            buy_token_price=buy_token_price,
            fee=fee
        ) for buy_amount in buy_amounts
    ]
    return sell_amounts


def compute_b_buy_token_imbalance(
    b_orders, s_orders,
    xrate,
    b_buy_token_price,
    fee,
    arith_traits=IntegerTraits
):
    b_total_buy_amount = sum(b_order.buy_amount for b_order in b_orders)
    s_total_sell_amount = sum(
        compute_sell_amounts_from_buy_amounts(
            [s_order.buy_amount for s_order in s_orders],
            1 / xrate,
            buy_token_price=b_buy_token_price / xrate,
            fee=fee,
            arith_traits=arith_traits
        )
    )
    return s_total_sell_amount - b_total_buy_amount


def compute_objective_for_orders(
    orders,
    xrate,
    buy_token_price,
    fee,
    arith_traits=RationalTraits
):
    return sum(
        arith_traits.compute_objective_term(
            order=order,
            xrate=xrate,
            buy_token_price=buy_token_price,
            fee=fee
        ) for order in orders
    )


def compute_objective(
    b_orders, s_orders, f_orders,
    xrate,
    b_buy_token_price,
    fee,
    arith_traits
):
    # 2u-umax terms for b_orders
    t1 = compute_objective_for_orders(
        orders=b_orders,
        xrate=xrate,
        buy_token_price=b_buy_token_price,
        fee=fee,
        arith_traits=arith_traits
    )

    # 2u-umax terms for s_orders
    t2 = compute_objective_for_orders(
        orders=s_orders,
        xrate=1 / xrate,
        buy_token_price=b_buy_token_price / xrate,
        fee=fee,
        arith_traits=arith_traits
    )

    # 2u-umax terms for f_orders
    t3 = compute_objective_for_orders(
        orders=f_orders,
        xrate=F(b_buy_token_price) / F(Config.FEE_TOKEN_PRICE),
        buy_token_price=b_buy_token_price,
        fee=fee,
        arith_traits=arith_traits
    )

    # Integrate 0.5 * fees into the objective computation.

    # Compute the total amount of b_buy_token bought for s_buy_token
    b_buy_token_imbalance = compute_b_buy_token_imbalance(
        b_orders, s_orders, xrate, b_buy_token_price, fee, arith_traits
    )

    # The imbalance multiplied by the price of b_buy_token is the total fee volume
    # which is then divided by the fee_token_price to get the amount of fee tokens.
    fees_payed = b_buy_token_imbalance * F(b_buy_token_price) / F(Config.FEE_TOKEN_PRICE)

    return t1 + t2 + t3 + fees_payed / 2


def compute_objective_rational(*args, **kwargs):
    return compute_objective(*args, **kwargs, arith_traits=RationalTraits)


def compute_objective_integer(*args, **kwargs):
    return compute_objective(*args, **kwargs, arith_traits=IntegerTraits)


def aggregate_orders_prices(
    token_pair,
    b_orders, s_orders, f_orders,
    xrate,
    b_buy_token_price,
    fee
):
    b_buy_token, s_buy_token = token_pair

    # Aggregate orders.
    orders = b_orders + s_orders + f_orders

    # Aggregate prices.
    prices = {
        fee.token: Config.FEE_TOKEN_PRICE,
        b_buy_token: b_buy_token_price,
        s_buy_token: b_buy_token_price / xrate
    }

    return orders, prices


def count_orders_satisfying_xrate(b_orders, xrate, fee):
    return sum(xrate <= b_order.max_xrate * (1 - fee.value) for b_order in b_orders)
