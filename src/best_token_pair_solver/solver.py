import json
import logging
from copy import deepcopy
from decimal import Decimal as D
from itertools import permutations

from src.core.api import IntegerTraits, dump_solution, load_problem
from src.core.orderbook import (compute_connected_tokens,
                                compute_objective_value, update_accounts)
from src.token_pair_solver.solver import solve_token_pair_and_fee_token

logger = logging.getLogger(__name__)


def match_token_pair(token_pair, accounts, orders, fee):
    b_buy_token, s_buy_token = token_pair
    trivial_solution = ([], dict())

    b_orders = [
        order for order in orders
        if order.buy_token == b_buy_token and order.sell_token == s_buy_token
    ]
    if len(b_orders) == 0:
        return trivial_solution

    s_orders = [
        order for order in orders
        if order.buy_token == s_buy_token and order.sell_token == b_buy_token
    ]
    if len(s_orders) == 0:
        return trivial_solution

    f_orders = [
        order for order in orders
        if order.buy_token == b_buy_token and order.sell_token == fee.token
    ]
    if len(f_orders) == 0:
        return trivial_solution

    # Find token pair + fee token matching.
    orders, prices = solve_token_pair_and_fee_token(
        token_pair, accounts, b_orders, s_orders, f_orders, fee
    )
    return (orders, prices)


def match_token_pair_and_evaluate(token_pair, accounts, orders, fee):
    # Compute current token pair solution: buy/sell amounts and best prices.
    orders, prices = match_token_pair(token_pair, accounts, orders, fee)

    # Update accounts for current token pair solution.
    accounts_updated = deepcopy(accounts)
    update_accounts(accounts_updated, orders)

    # Compute objective value for current token pair solution.
    objective = compute_objective_value(prices, accounts_updated, orders, fee)

    return (objective, (orders, prices))


def main(args):
    # Load dict from json.
    instance = json.load(args.instance, parse_float=D)

    # Load problem.
    accounts, orders, fee = load_problem(instance)

    # Find all tokens connected to the fee token.
    connected_tokens = compute_connected_tokens(orders, fee.token)

    # Find token pair + fee token matching.
    # TODO: parallelize this loop.
    best_objective = 0
    best_solution = ([], {})
    for token_pair in permutations(connected_tokens, 2):
        objective, solution = match_token_pair_and_evaluate(
            token_pair, accounts, orders, fee
        )
        if best_objective is None or objective > best_objective:
            best_objective = objective
            best_solution = deepcopy(solution)

    orders, prices = best_solution

    # Dump solution to file.
    dump_solution(
        instance, args.solution,
        orders,
        prices,
        fee=fee,
        arith_traits=IntegerTraits
    )

    logger.info("Solution file is '%s'.", args.solution.name)


def setup_arg_parser(subparsers):
    parser = subparsers.add_parser(
        'best-token-pair',
        help="Matches orders on the token pair that leads to higher objective."
    )

    parser.set_defaults(exec_subcommand=main)
