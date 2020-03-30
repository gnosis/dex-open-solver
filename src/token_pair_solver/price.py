from fractions import Fraction as F
from math import ceil, floor

from src.core.constants import FEE_TOKEN_PRICE
from src.core.order import Order

from .xrate import find_best_xrate


def create_market_order(
    buy_token, sell_token, sell_amount, s_orders
):
    # Market order: sell everything at the lowest price.

    # Compute the most optimistic xrate selling buy_token for sell_token.
    min_xrate = min(order.max_xrate for order in s_orders)

    # Slack to make sure the order will be matched, even after rounding.
    min_xrate *= F(9, 10)

    market_order = Order(
        index=None,
        account_id=None,
        buy_token=buy_token,
        sell_token=sell_token,
        max_sell_amount=sell_amount,
        max_xrate=1 / min_xrate
    )
    return market_order


# Find a subset of f_orders (sell fee for buy_token) that can cover buy_token_imbalance.
def compute_token_price_to_cover_imbalance(
    buy_token, fee, buy_token_imbalance, f_orders
):
    # The max sell amount is the current fee imbalance plus an estimate
    # of the imbalance obtained when rounding to integers.
    sell_amount = buy_token_imbalance * F(101, 100)

    buy_fee_market_order = create_market_order(
        buy_token=fee.token, sell_token=buy_token,
        sell_amount=sell_amount,
        s_orders=f_orders
    )

    # Compute the optimal xrate, which is the absolute b_buy_token_price.
    xrate, _ = find_best_xrate([buy_fee_market_order], f_orders, fee)

    # Note: xrate = fee_token_price / buy_token_price.

    if xrate == buy_fee_market_order.max_xrate * (1 - fee.value):
        # If optimal xrate is the fee_debt_order limit xrate then
        # b_buy_token_price must rounded up implying that
        # xrate=[fee_token_price / b_buy_token_price] is rounded down
        # (and therefore does not violate fee_debt_order limit xrate).
        buy_token_price = ceil(FEE_TOKEN_PRICE / xrate)
    else:
        # Otherwise it is possible that the optimal xrate is the limit
        # xrate of some f_order, in which case b_buy_token_price must be rounded
        # down implying 1/xrate=[b_buy_token_price / fee_token_price] is rounded down
        # (and therefore does not violate the limit xrate of that f_order).
        buy_token_price = floor(FEE_TOKEN_PRICE / xrate)

    return buy_token_price
