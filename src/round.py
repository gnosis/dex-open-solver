from math import floor
from .objective import compute_sell_amounts_from_buy_amounts, IntegerTraits
import logging

logger = logging.getLogger(__name__)

# TODO: not sure this is correct: check with Tom


# Token balance must hold for all tokens except fee.
# Here we always assume that b_buy_token is either fee, or it is the
# parent of s_buy_token in the spanning tree from fee.
# This means the imbalance should be the difference between the total
# amount of s_buy_token bought and sold
def compute_s_buy_token_imbalance(
    b_buy_amounts, s_buy_amounts,
    xrate,
    b_buy_token_price,
    fee,
    arith_traits=IntegerTraits()
):
    s_total_buy_amount = sum(s_buy_amounts)
    b_total_sell_amount = sum(
        compute_sell_amounts_from_buy_amounts(
            b_buy_amounts,
            xrate,
            buy_token_price=b_buy_token_price,
            fee=fee,
            arith_traits=arith_traits
        )
    )
    return s_total_buy_amount - b_total_sell_amount


def compute_b_buy_token_imbalance(
    b_buy_amounts, s_buy_amounts,
    xrate,
    b_buy_token_price,
    fee,
    arith_traits=IntegerTraits()
):
    b_total_buy_amount = sum(b_buy_amounts)
    s_total_sell_amount = sum(
        compute_sell_amounts_from_buy_amounts(
            s_buy_amounts,
            1 / xrate,
            buy_token_price=b_buy_token_price / xrate,
            fee=fee,
            arith_traits=arith_traits
        )
    )
    return b_total_buy_amount - s_total_sell_amount


def round_solution(
    b_orders, s_orders,
    b_buy_amounts, s_buy_amounts,
    xrate,
    b_buy_token_price,
    fee
):
    # floor all b_buy amounts
    for i in range(len(b_buy_amounts)):
        b_buy_amounts[i] = floor(b_buy_amounts[i])
    for i in range(len(s_buy_amounts)):
        s_buy_amounts[i] = floor(s_buy_amounts[i])

    while True:
        imbalance = compute_s_buy_token_imbalance(
            b_buy_amounts, s_buy_amounts, xrate, b_buy_token_price, fee
        )

        if imbalance == 0:
            break

        # TODO: how to do this fairly?
        s_order_i = max(
            range(len(s_buy_amounts)),
            key=lambda i: s_buy_amounts[i]
        )
        s_buy_amount_delta = min(imbalance, s_buy_amounts[s_order_i])
        s_buy_amounts[s_order_i] -= s_buy_amount_delta

        logger.debug(
            "Reducing order buy amount: "
            f"{s_buy_amounts[s_order_i] + s_buy_amount_delta} "
            f"-> {s_buy_amounts[s_order_i]}"
        )

    assert imbalance == 0
    return b_buy_amounts, s_buy_amounts
