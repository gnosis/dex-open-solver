from contextlib import contextmanager

from src.core.round import setup_rounding_buffer

from .orderbook import aggregate_orders_prices


@contextmanager
def rounding_buffer(
    token_pair,
    b_orders, s_orders,
    xrate,
    b_buy_token_price,
    fee
):
    """A context manager for handling orders with adjusted max_sell_amounts."""

    # Save original max sell amounts.
    b_max_sell_amounts = [b_order.max_sell_amount for b_order in b_orders]
    s_max_sell_amounts = [s_order.max_sell_amount for s_order in s_orders]

    # Slightly decrease max_sell_amounts so that is possible to round solution
    # without violating the max sell amount constraint.
    orders, prices = aggregate_orders_prices(
        token_pair, b_orders, s_orders, [], xrate, b_buy_token_price, fee
    )
    setup_rounding_buffer(orders, list(token_pair), prices, fee)

    try:
        yield (b_orders, s_orders)
    finally:
        # Restore original max sell amounts.
        for order, original_max_sell_amount in zip(b_orders, b_max_sell_amounts):
            order.force_set_max_sell_amount(original_max_sell_amount)
        for order, original_max_sell_amount in zip(s_orders, s_max_sell_amounts):
            order.force_set_max_sell_amount(original_max_sell_amount)
