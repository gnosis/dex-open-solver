from math import floor, ceil
from .objective import IntegerTraits, RationalTraits
import logging

logger = logging.getLogger(__name__)

def round_solution(
    b_orders, s_orders,
    b_buy_amounts, s_buy_amounts,
    xrate,
    b_buy_token_price,
    fee_ratio
):
    # floor all b_buy amounts
    for i in range(len(b_buy_amounts)):
        b_buy_amounts[i] = floor(b_buy_amounts[i])
    for i in range(len(s_buy_amounts)):
        s_buy_amounts[i] = floor(s_buy_amounts[i])

    def compute_imbalance():
        return sum(s_buy_amounts) - sum(
            IntegerTraits.compute_sell_from_buy_amount(
                buy_amount,
                xrate,
                buy_token_price=b_buy_token_price,
                fee_ratio=fee_ratio
            )
            for buy_amount in b_buy_amounts
        )

    while True:
        imbalance = compute_imbalance()
        if imbalance <= 0:
            break

        # try to be fair
        s_order_i = max(
            range(len(s_buy_amounts)),
            key=lambda i: s_buy_amounts[i]
        )
        s_buy_amount_delta = min(imbalance, s_buy_amounts[s_order_i])
        s_buy_amounts[s_order_i] -= s_buy_amount_delta

        logger.debug(
            f"Reducing order buy amount: {s_buy_amounts[s_order_i] + s_buy_amount_delta} "\
            f"-> {s_buy_amounts[s_order_i]}"
        )
    
    return b_buy_amounts, s_buy_amounts