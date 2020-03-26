from fractions import Fraction as F

from .order import Order


class BaseTraits:
    # xrate and max_xrate is in [sell_token] / [buy_token] units
    @classmethod
    def compute_objective_term(
        cls,
        order: Order,
        xrate: F,
        buy_token_price: F,
        fee
    ) -> F:
        u = cls.compute_utility_term(
            order=order,
            xrate=xrate,
            buy_token_price=buy_token_price,
            fee=fee
        )
        umax = cls.compute_max_utility_term(
            order=order,
            xrate=xrate,
            buy_token_price=buy_token_price,
            fee=fee
        )
        return 2 * u - umax


class RationalTraits(BaseTraits):
    """Order utility functions based on real or rational arithmeric."""
    # xrate is in [sell_token] / [buy_token] units
    @classmethod
    def compute_sell_from_buy_amount(cls, buy_amount, xrate, fee, **kwargs):
        return buy_amount * xrate / (1 - fee.value)

    @classmethod
    def compute_max_utility_term(cls, order, xrate, buy_token_price, fee):
        min_buy_amount = order.max_sell_amount / xrate
        return max(
            0,
            cls.compute_utility_term(
                order=order.with_buy_amount(min_buy_amount),
                xrate=xrate,
                buy_token_price=buy_token_price,
                fee=fee
            )
        )

    @classmethod
    def compute_utility_term(cls, order, xrate, buy_token_price, fee):
        sell_amount = cls.compute_sell_from_buy_amount(
            buy_amount=order.buy_amount,
            xrate=xrate,
            buy_token_price=buy_token_price,
            fee=fee
        )
        u = buy_token_price * (order.buy_amount - sell_amount / order.max_xrate)
        return u


class IntegerTraits(BaseTraits):
    """Order utility functions based on integer arithmeric.

    Follows smartcontract semantics.
    """

    # xrate is in [sell_token] / [buy_token] units
    @classmethod
    def compute_sell_from_buy_amount(cls, buy_amount, xrate, buy_token_price, fee):
        assert buy_token_price.denominator == 1
        sell_token_price = buy_token_price / xrate
        assert sell_token_price.denominator == 1
        sell_amount = (buy_amount * buy_token_price)\
            // (1 - fee.value)\
            // sell_token_price
        return sell_amount

    @classmethod
    def compute_max_utility_term(cls, order, xrate, buy_token_price, fee):
        sell_token_price = buy_token_price / xrate
        min_buy_amount = order.max_sell_amount / order.max_xrate
        max_sell_amount = order.max_sell_amount
        fee_denom = fee.value.denominator
        umax = max(
            (max_sell_amount * sell_token_price * (fee_denom - 1)) // fee_denom
            - (max_sell_amount * min_buy_amount * buy_token_price) // max_sell_amount,
            0
        )

        return umax

    @classmethod
    def compute_utility_term(
        cls, order, xrate, buy_token_price, fee
    ):
        min_buy_amount = order.max_sell_amount / order.max_xrate
        buy_amount = order.buy_amount
        max_sell_amount = order.max_sell_amount
        sell_amount = cls.compute_sell_from_buy_amount(
            buy_amount=buy_amount,
            xrate=xrate,
            buy_token_price=buy_token_price,
            fee=fee
        )
        u = (
            (buy_amount * max_sell_amount - sell_amount * min_buy_amount)
            * buy_token_price
        ) // max_sell_amount
        return u
