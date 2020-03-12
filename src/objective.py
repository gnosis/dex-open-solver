from .util import order_sell_amount, order_limit_xrate


class RationalTraits:
    """Objective calculation using real or rational arithmeric."""
    # xrate is in [sell_token] / [buy_token] units
    @classmethod
    def compute_sell_from_buy_amount(cls, buy_amount, xrate, fee=0, **kwargs):
        return buy_amount * xrate / (1 - fee)

    # xrate and max_xrate is in [sell_token] / [buy_token] units
    @classmethod
    def compute_objective_term(
        cls, buy_amount, max_sell_amount, xrate, max_xrate, **kwargs
    ):
        u = cls.compute_utility(buy_amount, max_sell_amount, xrate, max_xrate, **kwargs)
        umax = cls.compute_max_utility(max_sell_amount, xrate, max_xrate, **kwargs)
        return 2 * u - umax

    @classmethod
    def compute_max_utility(cls, max_sell_amount, xrate, max_xrate, **kwargs):
        min_buy_amount = max_sell_amount / xrate
        return max(
            0,
            cls.compute_utility(
                min_buy_amount, max_sell_amount, xrate, max_xrate, **kwargs
            )
        )

    @classmethod
    def compute_utility(
        cls, buy_amount, max_sell_amount, xrate, max_xrate,
        buy_token_price=1, **kwargs
    ):
        sell_amount = cls.compute_sell_from_buy_amount(
            buy_amount, xrate, buy_token_price=buy_token_price, **kwargs
        )
        u = buy_token_price * (buy_amount - sell_amount / max_xrate)
        return u


class IntegerTraits:
    """Objective calculation using integer arithmeric.

    Follows smartcontract semantics.
    """

    # xrate is in [sell_token] / [buy_token] units
    @classmethod
    def compute_sell_from_buy_amount(
        cls, buy_amount, xrate,
        buy_token_price=1,
        fee=0
    ):
        sell_token_price = buy_token_price / xrate
        sell_amount = (buy_amount * buy_token_price)\
            // (1 - fee)\
            // sell_token_price
        return sell_amount

    # xrate and max_xrate is in [sell_token] / [buy_token] units
    @classmethod
    def compute_objective_term(
        cls, buy_amount, max_sell_amount, xrate, max_xrate, **kwargs
    ):
        u = cls.compute_utility(buy_amount, max_sell_amount, xrate, max_xrate, **kwargs)
        umax = cls.compute_max_utility(max_sell_amount, xrate, max_xrate, **kwargs)
        return 2 * u - umax

    # TODO: Not exactly right yet, the balance redistribution is missing
    @classmethod
    def compute_max_utility(
        cls, max_sell_amount, xrate, max_xrate,
        buy_token_price=1, fee=0
    ):
        sell_token_price = buy_token_price / xrate
        min_buy_amount = max_sell_amount / xrate

        # This is the correct formula, but smart contract factors out the fees from
        # the utility functions and adds it in the end to the objective
        # (and standard solver's code is not doing that at the moment)
        # umax = max(
        #    (
        #        max_sell_amount * self.sell_token_price
        #        * (self.fee.denominator * 2 - 1)
        #    )
        #    // (self.fee.denominator * 2)
        #    - (max_sell_amount * min_buy_amount * self.buy_token_price)
        #    // max_sell_amount,
        #    0
        # )

        umax = max(
            (
                max_sell_amount * sell_token_price * (fee.denominator - 1)
            ) // fee.denominator
            - (max_sell_amount * min_buy_amount * buy_token_price) // max_sell_amount,
            0
        )

        return umax

    @classmethod
    def compute_utility(
        cls, buy_amount, max_sell_amount, xrate, max_xrate,
        buy_token_price=1, **kwargs
    ):
        min_buy_amount = max_sell_amount / max_xrate
        sell_amount = cls.compute_sell_from_buy_amount(
            buy_amount, xrate, buy_token_price=buy_token_price, **kwargs
        )
        u = (
            (buy_amount * max_sell_amount - sell_amount * min_buy_amount)
            * buy_token_price
        ) // max_sell_amount
        return u


def evaluate_objective_b(
    orders,
    xrate,
    buy_amounts,
    arith_traits=RationalTraits(),
    buy_token_price=None,
    **kwargs
):
    return sum(
        arith_traits.compute_objective_term(
            buy_amount=buy_amount,
            max_sell_amount=order_sell_amount(order),
            xrate=xrate,
            max_xrate=order_limit_xrate(order),
            buy_token_price=buy_token_price,
            **kwargs
        ) for buy_amount, order in zip(buy_amounts, orders)
    )


def evaluate_objective(
    b_orders, s_orders,
    xrate,
    b_buy_amounts, s_buy_amounts,
    arith_traits=RationalTraits(),
    b_buy_token_price=1,
    **kwargs
):
    t1 = evaluate_objective_b(
        b_orders, xrate, b_buy_amounts,
        buy_token_price=b_buy_token_price,
        **kwargs
    )
    t2 = evaluate_objective_b(
        s_orders, 1 / xrate, s_buy_amounts,
        buy_token_price=b_buy_token_price / xrate,
        **kwargs
    )
    return t1 + t2


def evaluate_objective_rational(
    b_orders, s_orders,
    xrate,
    b_buy_amounts, s_buy_amounts,
    **kwargs
):
    return evaluate_objective(
        b_orders, s_orders, xrate, b_buy_amounts, s_buy_amounts,
        arith_traits=RationalTraits(),
        **kwargs
    )


def evaluate_objective_integer(
    b_orders, s_orders,
    xrate,
    b_buy_amounts, s_buy_amounts,
    **kwargs
):
    return evaluate_objective(
        b_orders, s_orders, xrate, b_buy_amounts, s_buy_amounts,
        arith_traits=IntegerTraits(),
        **kwargs
    )


def compute_sell_amounts_from_buy_amounts(
    buy_amounts, xrate, buy_token_price, fee,
    arith_traits=RationalTraits()
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


def compute_sell_amounts_from_buy_amounts_rational(
    buy_amounts, xrate, buy_token_price, fee
):
    return compute_sell_amounts_from_buy_amounts(
        buy_amounts, xrate, buy_token_price, fee, arith_traits=RationalTraits()
    )


def compute_sell_amounts_from_buy_amounts_integer(
    buy_amounts, xrate, buy_token_price, fee
):
    return compute_sell_amounts_from_buy_amounts(
        buy_amounts, xrate, buy_token_price, fee, arith_traits=IntegerTraits()
    )
