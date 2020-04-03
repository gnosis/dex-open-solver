
"""Minimum amount bought or sold in an order."""
MIN_TRADABLE_AMOUNT = 10000

"""Price of fee token."""
FEE_TOKEN_PRICE = int(1e18)

"""Maximum number of executed orders."""
MAX_NR_EXEC_ORDERS = 30

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
