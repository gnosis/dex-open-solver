from .util import order_sell_amount, order_limit_xrate


class RationalTraits:
    """Objective calculation using real or rational arithmeric."""
    # xrate is in [sell_token] / [buy_token] units
    @classmethod
    def compute_sell_from_buy_amount(cls, buy_amount, xrate, fee, **kwargs):
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
        buy_token_price,
        fee
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
    arith_traits,
    b_buy_token_price,
    fee
):
    # 2u-umax terms for b_orders
    t1 = evaluate_objective_b(
        b_orders, xrate, b_buy_amounts,
        buy_token_price=b_buy_token_price,
        fee=fee
    )

    # 2u-umax terms for s_orders
    t2 = evaluate_objective_b(
        s_orders, 1 / xrate, s_buy_amounts,
        buy_token_price=b_buy_token_price / xrate,
        fee=fee
    )

    # 0.5 * fees
    # TODO: not sure this is correct: check with Tom
    # Compute the total amount of b_buy_token bought
    b_total_buy_amount = sum(b_buy_amounts)
    # Compute the total amount of b_buy_token sold
    s_total_sell_amount = sum(
        compute_sell_amounts_from_buy_amounts(
            s_buy_amounts, 1 / xrate, b_buy_token_price / xrate, fee, arith_traits
        )
    )
    # The difference multiplied by the price of b_buy_token is the total fee volume
    # which is then divided by the fee_token_price to get the amount of fee tokens.
    b_buy_amount_diff = s_total_sell_amount - b_total_buy_amount
    fee_token_price = int(1e18)  # should this be a constant?
    fees_payed = b_buy_amount_diff * b_buy_token_price / fee_token_price

    return t1 + t2 + fees_payed / 2


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
