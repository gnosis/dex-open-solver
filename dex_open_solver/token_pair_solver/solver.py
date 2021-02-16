import json
import logging
import time
from copy import deepcopy
from decimal import Decimal as D
from fractions import Fraction as F
from math import ceil, floor

from ..core.api import Stats, dump_solution
from ..core.config import Config
from ..core.orderbook import (compute_approx_economic_viable_subset,
                              count_nr_exec_orders, is_economic_viable,
                              is_trivial, sorted_orders_by_exec_priority)
from ..core.round import round_solution
from ..core.validation import validate
from .amount import compute_buy_amounts
from .api import load_problem
from .orderbook import (IntegerTraits, RationalTraits, aggregate_orders_prices,
                        compute_b_buy_token_imbalance,
                        compute_objective_rational,
                        count_orders_satisfying_xrate,
                        prune_unrealizable_orders)
from .price import compute_token_price_to_cover_imbalance, create_market_order
from .round import rounding_buffer
from .xrate import find_best_xrate

logger = logging.getLogger(__name__)

TRIVIAL_SOLUTION = ([], {})


def compute_s_buy_token_price(b_buy_token_price, xrate, b_orders, s_orders, fee):
    s_buy_token_price_up = ceil(b_buy_token_price / xrate)
    s_buy_token_price_down = floor(b_buy_token_price / xrate)
    xrate_up = F(b_buy_token_price, s_buy_token_price_up)
    xrate_down = F(b_buy_token_price, s_buy_token_price_down)
    cu = count_orders_satisfying_xrate(b_orders, xrate_up, fee) + \
        count_orders_satisfying_xrate(s_orders, 1 / xrate_up, fee)
    cd = count_orders_satisfying_xrate(b_orders, xrate_down, fee) + \
        count_orders_satisfying_xrate(s_orders, 1 / xrate_down, fee)
    if cu > cd:
        return s_buy_token_price_up
    else:
        return s_buy_token_price_down


def solve_token_pair(
    token_pair,
    b_orders, s_orders,
    fee,
    xrate=None,
    b_buy_token_price=None,
    max_nr_exec_orders=None
):
    """Find optimal execution of b_orders and s_orders.

    Sets b_orders/s_orders buy_amount and returns optimal exchange rate.
    """

    # NOTE: do not add this as a default parameter above, since
    # default parameters are evaluated when the function is defined, and
    # not when it is called. This means that runtime changes to the Config
    # singleton would not be reflected.
    if max_nr_exec_orders is None:
        max_nr_exec_orders = Config.MAX_NR_EXEC_ORDERS

    if len(b_orders) == 0 or len(s_orders) == 0:
        return None

    b_buy_token, s_buy_token = token_pair

    if b_buy_token == fee.token:
        b_buy_token_price = Config.FEE_TOKEN_PRICE

    # Compute optimal exchange rate if not given.
    if xrate is None:
        xrate, _ = find_best_xrate(b_orders, s_orders, fee)
        logger.debug(
            "p(%s) / p(%s) = %s (precise arithmetic)",
            b_buy_token,
            s_buy_token, xrate
        )

    # Return if there is no possible order matching.
    if xrate is None:
        return None

    # If b_buy_token_price is given, adjust xrate so that
    # xrate = b_buy_token_price / s_buy_token_price
    # and s_buy_token_price is an integer.
    if b_buy_token_price is not None:
        s_buy_token_price = compute_s_buy_token_price(
            b_buy_token_price, xrate, b_orders, s_orders, fee
        )
        xrate = F(b_buy_token_price, s_buy_token_price)
        logger.debug("Adjusted xrate\t:\t%s", xrate)

    # Execute orders based on optimal exchange rate.
    compute_buy_amounts(
        xrate, b_orders, s_orders, fee, max_nr_exec_orders=max_nr_exec_orders
    )

    return xrate


def solve_b_buy_token_and_fee_token(
    b_buy_token_imbalance, b_buy_token, b_orders, f_orders, fee
):
    """Find optimal execution of b_orders and f_orders.

    The b_buy_token_imbalance is the amount (or an estimation) that needs
    to be sold for fee. This is required since there may be no orders selling
    b_buy_token for fee directly, meaning the price of b_buy_token would be
    unbounded.

    Future work: also consider other orders selling b_buy_token for fee.

    Returns price of b_buy_token.
    """

    # Compute b_buy_token_price such that it is possible to sell the b_buy_token
    # imbalance due to fee (plus a rounding buffer) for fee.
    # This fixes the final b_buy_token_price.
    b_buy_token_price = compute_token_price_to_cover_imbalance(
        buy_token=b_buy_token,
        fee=fee,
        buy_token_imbalance=b_buy_token_imbalance,
        f_orders=f_orders
    )

    # Execute orders that buy the b_buy_token imbalance due to fee for fee.
    # 1/2: create an artificial order selling the b_buy_token imbalance for fee.
    fee_debt_order = create_market_order(
        buy_token=fee.token, sell_token=b_buy_token,
        sell_amount=b_buy_token_imbalance,
        s_orders=f_orders
    )

    # 2/2: execute the artifical order against existing orders buying b_buy_token
    # for fee (i.e. f_orders).
    fee_xrate = F(Config.FEE_TOKEN_PRICE, b_buy_token_price)
    fee_xrate = solve_token_pair(
        (fee.token, b_buy_token),
        [fee_debt_order], f_orders, fee,
        xrate=fee_xrate
    )
    assert fee_xrate is not None

    return b_buy_token_price


def compute_nr_f_orders_to_execute(b_orders, s_orders, f_orders):
    """Compute the number (interval) of f_orders that can be executed
    while satisfying the maximum number of executed orders constraint.
    """

    # Pre-condition: the following constraint is assumed:
    # nr_exec_b_orders + nr_exec_s_orders <= MAX_NR_EXEC_ORDERS
    # which gives an upper bound for the number of executed b/s orders:
    max_nr_exec_b_orders = count_nr_exec_orders(b_orders)
    max_nr_exec_s_orders = count_nr_exec_orders(s_orders)

    assert max_nr_exec_b_orders + max_nr_exec_s_orders <= Config.MAX_NR_EXEC_ORDERS

    # The actual constraint to enforce is:
    # nr_b_exec_orders + nr_s_exec_orders + nr_f_exec_orders <= MAX_NR_EXEC_ORDERS
    # <=> nr_f_exec_orders <= MAX_NR_EXEC_ORDERS - nr_b_exec_orders - nr_s_exec_orders

    # Which is trivially satisfied if:
    # nr_f_exec_orders <=
    # MAX_NR_EXEC_ORDERS - max(nr_b_exec_orders) - max(nr_s_exec_orders)
    min_max_nr_exec_f_orders = Config.MAX_NR_EXEC_ORDERS \
        - max_nr_exec_b_orders - max_nr_exec_s_orders + 1

    # At least one b_order and one s_order must be matched.
    max_nr_exec_f_orders = min(len(f_orders), Config.MAX_NR_EXEC_ORDERS - 2)

    # Try the highest number of f_orders as possible. In other words, do not constrain
    # the number of f_orders to execute unless it is really necessary.
    min_nr_exec_f_orders = min(min_max_nr_exec_f_orders, max_nr_exec_f_orders)

    # At least one f_order needs to be executed.
    min_nr_exec_f_orders = max(min_nr_exec_f_orders, 1)

    return (min_nr_exec_f_orders, max_nr_exec_f_orders)


def solve_token_pair_and_fee_token_given_exec_f_orders(
    nr_exec_f_orders,
    approx_b_buy_token_imbalance,
    token_pair,
    b_orders, s_orders, f_orders,
    xrate,
    fee
):
    """Match orders between token pair and the fee token, assuming
    that there will be at most `nr_exec_f_orders` orders selling
    fee for b_buy_token.

    Sets b_orders/s_orders/f_orders buy_amounts for the best execution.
    Return the objective value f, the exchange rate b/s, and the exchange
    rate b/f (i.e. the price of b_token).
    """
    b_buy_token, s_buy_token = token_pair

    # Match fee_token <-> b_buy_token.
    b_buy_token_price = solve_b_buy_token_and_fee_token(
        approx_b_buy_token_imbalance,
        b_buy_token, b_orders, f_orders[:nr_exec_f_orders],
        fee=fee
    )

    # It can happen (due to side constraints) that the number of executed
    # orders selling fee is less than what was requested.
    nr_exec_f_orders = count_nr_exec_orders(f_orders[:nr_exec_f_orders])

    # If there are no f_orders, there can't be no match and no price.
    if nr_exec_f_orders == 0:
        return (0, xrate, None)

    # Re-execute orders between token pair with the fixed b_buy_token_price,
    # and adjusted max_nr_exec_orders.
    # This fixes the final xrate, and therefore the final s_buy_token_price.
    max_nr_bs_exec_orders = Config.MAX_NR_EXEC_ORDERS - nr_exec_f_orders

    logger.debug("")
    logger.debug("=== (Re)solving %s -- %s ===", b_buy_token, s_buy_token)
    logger.debug("\tWith price for %s\t:\t%s", b_buy_token, b_buy_token_price)
    logger.debug("\tWith maximum nr bs orders\t:\t%s", max_nr_bs_exec_orders)
    logger.debug("\tWith nr f orders\t:\t%s", nr_exec_f_orders)

    # Execute orders with slightly decreased max_sell_amounts so that later on
    # is possible to round solution without violating the max sell amount constraint.
    with rounding_buffer(token_pair, b_orders, s_orders, xrate, b_buy_token_price, fee):
        adjusted_xrate = solve_token_pair(
            token_pair,
            b_orders, s_orders,
            fee,
            xrate=xrate,
            b_buy_token_price=b_buy_token_price,
            max_nr_exec_orders=max_nr_bs_exec_orders
        )

    objective = compute_objective_rational(
        b_orders, s_orders, f_orders,
        adjusted_xrate,
        b_buy_token_price,
        fee
    )

    return (objective, adjusted_xrate, b_buy_token_price)


def solve_token_pair_and_fee_token(
    token_pair, accounts, b_orders, s_orders, f_orders, fee,
    xrate=None
):
    """Match orders between token pair and the fee token, taking into account
    all side constraints except economic viability. This means the solution obtained
    from this function can be economic inviable (see also config.MIN_AVERAGE_ORDER_FEE,
    for what exactly that means).

    If xrate is given, then it will be used instead of trying to find
    optimal xrate.

    Sets b_orders/s_orders/f_orders (integral) buy_amounts for the best execution.
    """
    # remove trivially infeasible orders
    b_orders, s_orders = prune_unrealizable_orders(b_orders, s_orders, fee)

    if len(b_orders) == 0 or len(s_orders) == 0:
        return TRIVIAL_SOLUTION

    # This function does not support s_buy_token = fee token.
    if token_pair[1] == fee.token:
        token_pair = tuple(reversed(token_pair))
        b_orders, s_orders = s_orders, b_orders

    b_buy_token, s_buy_token = token_pair

    logger.debug("=== Order matching on token pair + fee token ===")
    logger.debug("b_buy_token\t:\t%s", b_buy_token)
    logger.debug("s_buy_token\t:\t%s", s_buy_token)
    logger.debug("fee_token  \t:\t%s", fee.token)

    # Find optimal execution between b_buy_token <-> s_buy_token.
    logger.debug("")
    logger.debug(
        "=== Solving %s -- %s (rational arithmetic) ===",
        b_buy_token, s_buy_token
    )
    xrate = solve_token_pair(token_pair, b_orders, s_orders, fee, xrate=xrate)

    if count_nr_exec_orders(b_orders) == 0:
        logger.info("No matching orders between %s and %s.", b_buy_token, s_buy_token)
        return TRIVIAL_SOLUTION

    if b_buy_token == fee.token:
        # If b_buy_token is fee, then there is only two sets of orders,
        # b_orders, and s_orders, for which buy_amounts were computed above.
        f_orders = []
        b_buy_token_price = Config.FEE_TOKEN_PRICE
    else:
        # Otherwise orders buying b_buy_token for fee must be considered, so that
        # the b_buy_token imbalance due to fee and rounding can be bought.
        if len(f_orders) == 0:
            return TRIVIAL_SOLUTION

        logger.debug("")
        logger.debug("=== Computing price of %s ===", b_buy_token)

        # Find imbalance due to fee of b_buy_token
        # (imbalance due to fee of s_buy_token is zero).
        b_buy_token_imbalance = compute_b_buy_token_imbalance(
            b_orders, s_orders,
            xrate, 1, fee, RationalTraits
        )
        logger.debug(
            "Imbalance of %s\t:\t%s (due to fee)", b_buy_token, b_buy_token_imbalance
        )

        # Compute the number of f_orders that can be executed so that the maximum number
        # of executed orders constraint is satisfied.
        min_nr_exec_f_orders, max_nr_exec_f_orders = \
            compute_nr_f_orders_to_execute(b_orders, s_orders, f_orders)

        # If the interval of number of f_orders to try is empty, then there's no solution.
        if min_nr_exec_f_orders > max_nr_exec_f_orders:
            return TRIVIAL_SOLUTION

        logger.debug("")
        logger.debug(
            "=== Solving %s -- %s (nr_exec_f_orders \u2208 [%s, %s]) ===",
            b_buy_token, fee.token, min_nr_exec_f_orders, max_nr_exec_f_orders
        )

        # Find number of f_orders that leads to higher objective value.
        f_orders = sorted_orders_by_exec_priority(f_orders)
        best_objective = None
        best_solution = (xrate, None, b_orders, s_orders, f_orders)
        for nr_exec_f_orders in range(min_nr_exec_f_orders, max_nr_exec_f_orders + 1):

            # Reset exec amounts of f orders.
            for f_order in f_orders:
                f_order.buy_amount = 0
                f_order.sell_amount = 0

            # Compute objective value and solution given current nr_exec_f_orders.
            objective, adjusted_xrate, b_buy_token_price = \
                solve_token_pair_and_fee_token_given_exec_f_orders(
                    nr_exec_f_orders, b_buy_token_imbalance,
                    token_pair, b_orders, s_orders, f_orders, xrate, fee
                )

            # Skip iteration if it was not possible to connect to fee token.
            if b_buy_token_price is None:
                continue

            assert objective is not None

            logger.debug("Objective\t:\t%s\t[best=%s]", objective, best_objective)

            # Optimization: Since f_orders are ordered by limit xrate, the objective
            # as a function of the size of the prefix used has only one optimum.
            # In other words, we can stop trying to augmenting the set of f_orders
            # once adding a new f_order degrades the objective.
            if best_objective is not None and objective < best_objective:
                break

            # Update best solution found so far if necessary.
            assert best_objective is None or objective >= best_objective
            best_objective = objective
            best_solution = deepcopy(
                (adjusted_xrate, b_buy_token_price, b_orders, s_orders, f_orders)
            )

        xrate, b_buy_token_price, b_orders, s_orders, f_orders = best_solution

        # Return trivial solution in case it was not possible to connect to the fee token.
        # This can happen due to side constraints, for example if the resulting f_orders
        # violate the minimum tradable amount.
        if b_buy_token_price is None:
            logger.debug("Could not execute f_orders.")
            return TRIVIAL_SOLUTION

        logger.debug("Price of %s\t:\t%s", b_buy_token, b_buy_token_price)
        logger.debug("Price of %s\t:\t%s", s_buy_token, b_buy_token_price / xrate)
        logger.debug(
            "Amounts of %s bought in exchange for %s:",
            b_buy_token, s_buy_token
        )
        logger.debug("\t%s", [
            {b_order.id: b_order.buy_amount}
            for b_order in b_orders if b_order.buy_amount > 0
        ])
        logger.debug(
            "Amounts of %s bought in exchange for %s:",
            s_buy_token, b_buy_token
        )
        logger.debug("\t%s", [
            {s_order.id: s_order.buy_amount}
            for s_order in s_orders if s_order.buy_amount > 0
        ])

        logger.debug(
            "Amounts of %s bought in exchange for FEE (%s):",
            b_buy_token, fee.token
        )
        logger.debug("\t%s", [
            {f_order.id: f_order.buy_amount}
            for f_order in f_orders if f_order.buy_amount > 0
        ])

    # Aggregate orders and prices.
    orders, prices = aggregate_orders_prices(
        token_pair, b_orders, s_orders, f_orders, xrate, b_buy_token_price, fee
    )

    # Integrate sell_amounts and prices in solution, and round.
    logger.debug("")
    logger.debug("=== Rounding ===")
    if not round_solution(prices, orders, fee):
        logger.warning("Could not round solution.")
        return TRIVIAL_SOLUTION

    return orders, prices


def solve_token_pair_and_fee_token_economic_viable(
    token_pair, accounts, b_orders, s_orders, f_orders, fee,
    xrate=None
):
    """Match orders between token pair and the fee token, taking into
    account all side constraints, including economic viability.

    If xrate is given, then it will be used instead of trying to find
    optimal xrate.

    Sets b_orders/s_orders/f_orders (integral) buy_amounts for the best execution.
    Also returns the (integral) prices found.
    """
    b_buy_token, s_buy_token = token_pair

    orders, prices = TRIVIAL_SOLUTION

    # Search for an economically viable solution.
    while len(b_orders) > 0 or len(s_orders) > 0:

        # Solve current problem.
        orders, prices = solve_token_pair_and_fee_token(
            token_pair, accounts, b_orders, s_orders, f_orders, fee, xrate
        )

        # If solution is economically viable, exit.
        # Hopefully, in large majority of cases this will occur in the first iteration.
        if is_economic_viable(orders, prices, fee, IntegerTraits) or is_trivial(orders):
            break

        # If solution cannot be made economically viable (assuming prices wouldn't change)
        if len(compute_approx_economic_viable_subset(
            orders, prices, fee, IntegerTraits
        )) == 0:
            orders, prices = TRIVIAL_SOLUTION
            break

        # Note: to increase performance, we could consider removing all orders that do not
        # satisfy min_abs_fee_per_order here at once, instead of removing one at a time as
        # it is currently. The advantage of removing one by one is that it will not remove
        # more than needed (note that prices, and hence order fees, keep changing).

        # Find and remove the order paying the least fee.
        b_order_with_min_buy_amount = min(
            [o for o in b_orders if o.buy_amount > 0],
            key=lambda o: o.buy_amount
        )
        s_order_with_min_buy_amount = min(
            [o for o in s_orders if o.buy_amount > 0],
            key=lambda o: o.buy_amount
        )

        if b_order_with_min_buy_amount.buy_amount * prices[b_buy_token]\
           < s_order_with_min_buy_amount.buy_amount * prices[s_buy_token]:
            b_orders = [
                o for o in b_orders if o.id != b_order_with_min_buy_amount.id
            ]
        else:
            s_orders = [
                o for o in s_orders if o.id != s_order_with_min_buy_amount.id
            ]

    # Make sure the solution is correct.
    validate(accounts, orders, prices, fee)

    return orders, prices


def main(args):
    start_time = time.time()

    # Load dict from json.
    instance = json.load(args.instance, parse_float=D)

    # Load problem.
    # b_orders: orders buying b_buy_token
    # s_orders: orders selling b_buy_token (buying s_buy_token)
    # f_orders: orders selling fee token for b_buy_token
    accounts, b_orders, s_orders, f_orders, fee = load_problem(
        instance, args.token_pair
    )

    # Find token pair + fee token matching.
    orders, prices = solve_token_pair_and_fee_token_economic_viable(
        args.token_pair, accounts, b_orders, s_orders, f_orders, fee, xrate=args.xrate
    )

    runtime = time.time() - start_time
    stats = Stats(runtime=runtime, exit_status="completed")

    # Dump solution to file.
    dump_solution(
        instance, args.solution_filename,
        orders,
        prices,
        fee=fee,
        stats=stats,
        arith_traits=IntegerTraits()
    )

    return instance


def setup_arg_parser(subparsers):
    parser = subparsers.add_parser(
        'token-pair', help="Matches orders on a given token pair."
    )

    parser.add_argument(
        'token_pair',
        type=str,
        nargs=2,
        help='Token pair (b_buy_token, s_buy_token).'
    )
    parser.add_argument(
        '--xrate',
        type=F,
        help='Exchange rate (token1/token2) as a fraction.'
    )

    parser.set_defaults(exec_subcommand=main)
