import json
import logging
from copy import deepcopy
from decimal import Decimal as D
from functools import reduce

from src.core.api import IntegerTraits, dump_solution, load_problem
from src.core.orderbook import compute_objective_value, update_accounts
from src.token_pair_solver.solver import solve_token_pair_and_fee_token_economic_viable

logger = logging.getLogger(__name__)


TRIVIAL_SOLUTION = ([], {})


def match_token_pair(token_pair, accounts, orders, fee):
    b_buy_token, s_buy_token = token_pair

    b_orders = [
        order for order in orders
        if order.buy_token == b_buy_token and order.sell_token == s_buy_token
    ]
    if len(b_orders) == 0:
        return TRIVIAL_SOLUTION

    s_orders = [
        order for order in orders
        if order.buy_token == s_buy_token and order.sell_token == b_buy_token
    ]
    if len(s_orders) == 0:
        return TRIVIAL_SOLUTION

    if b_buy_token != fee.token:
        f_orders = [
            order for order in orders
            if order.buy_token == b_buy_token and order.sell_token == fee.token
        ]
        if len(f_orders) == 0:
            return TRIVIAL_SOLUTION
    else:
        f_orders = []

    # Find token pair + fee token matching.
    orders, prices = solve_token_pair_and_fee_token_economic_viable(
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


def eligible_token_pairs(orders, fee_token):
    # Set of tokens directly connected to fee token (except fee).
    directly_connected_tokens = {
        o.buy_token for o in orders if o.sell_token == fee_token
    }

    # A set with all tokens.
    all_tokens = reduce(lambda x, y: x | y, (o.tokens for o in orders))

    # All permutations that do not include fee, and where the first
    # token in the token pair is directly connected to fee.
    for b_token in directly_connected_tokens:
        for s_token in all_tokens - {b_token, fee_token}:
            yield (b_token, s_token)

    # All permutations where the first token is the fee token.
    for s_token in all_tokens - {fee_token}:
        yield (fee_token, s_token)


def main(args):
    # Load dict from json.
    instance = json.load(args.instance, parse_float=D)

    # Load problem.
    accounts, orders, fee = load_problem(instance)

    # Find token pair + fee token matching.
    # TODO: parallelize this loop.
    best_objective = 0
    best_solution = TRIVIAL_SOLUTION
    for token_pair in eligible_token_pairs(orders, fee.token):
        objective, solution = match_token_pair_and_evaluate(
            token_pair, accounts, orders, fee
        )
        if best_objective is None or objective > best_objective:
            best_objective = objective
            best_solution = deepcopy(solution)

    orders, prices = best_solution

    # Dump solution to file.
    dump_solution(
        instance, args.solution_filename,
        orders,
        prices,
        fee=fee,
        arith_traits=IntegerTraits
    )

    return instance


def setup_arg_parser(subparsers):
    parser = subparsers.add_parser(
        'best-token-pair',
        help="Matches orders on the token pair that leads to higher objective."
    )

    parser.set_defaults(exec_subcommand=main)
