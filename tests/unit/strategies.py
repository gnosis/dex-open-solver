"""Hypothesis (https://hypothesis.readthedocs.io/) strategies for tests."""

from fractions import Fraction as F
from typing import List, Optional

import hypothesis.strategies as s
from hypothesis.strategies import composite

from src.core.order import Order

DEFAULT_MAX_XRATE = F(10)


def random_xrate(
    max_xrate_ub: Optional[F] = DEFAULT_MAX_XRATE
) -> s.SearchStrategy[F]:
    """Strategy for generating random exchange rates.

    Arguments:
    max_xrate_ub -- Maximum exchange rate (in any direction).
    """
    if max_xrate_ub >= 1:
        return s.fractions(min_value=1 / max_xrate_ub, max_value=max_xrate_ub)
    else:
        return s.fractions(min_value=max_xrate_ub, max_value=1 / max_xrate_ub)


RANDOM_ORDER_DEFAULT_MAX_AMOUNT_LB = 9000
RANDOM_ORDER_DEFAULT_MAX_AMOUNT_UB = 20000

order_counter = 0


@composite
def random_order(
    draw,
    buy_token: Optional[str] = 'token0',
    sell_token: Optional[str] = 'token1',
    max_sell_amount_lb: Optional[int] = RANDOM_ORDER_DEFAULT_MAX_AMOUNT_LB,
    max_sell_amount_ub: Optional[int] = RANDOM_ORDER_DEFAULT_MAX_AMOUNT_UB,
    max_xrate: Optional[F] = None,
    max_xrate_ub: Optional[F] = DEFAULT_MAX_XRATE
) -> s.SearchStrategy[Order]:
    """Strategy for generating random Order's.

    Arguments:
    buy_token -- Token to be bought.
    sell_token -- Token to be sold.
    max_sell_amount_lb -- Lower bound for the sampled maximum sell amount
    max_sell_amount_ub -- Upper bound for the sampled maximum sell amount
    max_xrate -- Limit exchange rate
    max_xrate_ub -- Maximum exchange rate (in any direction) in case limit is not
                provided.
    """

    # Sample max sell amount
    assert max_sell_amount_lb <= max_sell_amount_ub
    max_sell_amount = draw(
        s.integers(min_value=max_sell_amount_lb, max_value=max_sell_amount_ub)
    )

    # Sample max_xrate
    if max_xrate is None:
        max_xrate = draw(random_xrate(max_xrate_ub))

    return Order(
        index=order_counter,
        account_id=None,  # To be filled later.
        buy_token=buy_token,
        sell_token=sell_token,
        max_sell_amount=max_sell_amount,
        max_xrate=max_xrate
    )


def random_order_list(
    min_size: int,
    max_size: int,
    **kwargs
) -> s.SearchStrategy[List[Order]]:
    """Strategy for generating lists of random orders.

    Arguments:
    min_size -- Min size of list.
    max_size -- Max size of list.
    **kwargs -- Args passed to random order strategy.
    """
    orders = random_order(**kwargs)
    return s.lists(orders, min_size=min_size, max_size=max_size)
