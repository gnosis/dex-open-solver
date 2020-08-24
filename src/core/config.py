from src.core.util import classproperty


class Config:
    """Configuration parameters for the solver."""

    # Main problem parameters:

    """Minimum amount bought or sold in an order."""
    MIN_TRADABLE_AMOUNT = 10000

    """Price of fee token."""
    FEE_TOKEN_PRICE = int(1e18)

    """Maximum number of executed orders."""
    MAX_NR_EXEC_ORDERS = 30

    """Minimum average fee payed per order on an admissible solution."""
    MIN_AVERAGE_ORDER_FEE = 0

    """Minimum absolute fee payed per (non fee selling) order on "
    "an admissible solution."""
    MIN_ABSOLUTE_ORDER_FEE = 0

    # Rounding parameters:

    # Rational solver will enforce that tradable amounts are
    # >= MIN_TRADABLE_AMOUNT * (1 + MIN_TRADABLE_AMOUNT_ROUNDING_TOL).
    # This extra slack is to make sure the constraint won't be violated
    # after rounding the solution to integers.
    MIN_TRADABLE_AMOUNT_ROUNDING_TOL = 0.001

    # Set maximum amount that might need to be rounded in terms of fee token:
    # The assumption is that the solver will not incur float/int imprecisions
    # for a single order that are higher in value than this constant.
    # TODO: Monitor constant and eventually improve.
    MAX_ROUNDING_VOLUME = 10**11

    # Set assumed value for the error factor in the estimated prices:
    # e.g., PRICE_ESTIMATION_ERROR = 10 means that the price can be off by a factor of 10.
    # Larger error estimations lead to larger rounding buffers.
    # TODO: Monitor constant and eventually improve.
    PRICE_ESTIMATION_ERROR = 10

    # Convenience method to compute effective min tradable amount.
    @classproperty
    def MIN_RATIONAL_TRADABLE_AMOUNT(self):
        return int(
            self.MIN_TRADABLE_AMOUNT * (1 + self.MIN_TRADABLE_AMOUNT_ROUNDING_TOL)
        )
