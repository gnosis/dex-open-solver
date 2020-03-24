from fractions import Fraction as F
import argparse
import logging
import tempfile

from .api import load_problem, dump_solution
from .solver.xrate import find_best_xrate
from .solver.amount import find_best_buy_amounts
from .objective import (
    evaluate_objective_rational,
    IntegerTraits, RationalTraits
)
from .round import round_solution
from .validation import validate

logger = logging.getLogger(__name__)


def main(args):
    # Load sets of b_orders and s_orders
    accounts, b_orders, s_orders, fee = load_problem(
        args.instance, args.token_pair
    )

    args.instance.seek(0)

    assert len(b_orders) > 0 and len(s_orders) > 0

    if args.exchange_rate is None:
        xrate, _ = find_best_xrate(b_orders, s_orders, fee)
    else:
        xrate = args.exchange_rate

    if xrate is None:
        logger.info("No matching orders.")
        return

    b_buy_amounts, s_buy_amounts = find_best_buy_amounts(
        xrate, b_orders, s_orders, fee
    )

    objective = evaluate_objective_rational(
        b_orders, s_orders,
        xrate,
        b_buy_amounts, s_buy_amounts,
        b_buy_token_price=args.b_buy_token_price,
        fee=fee
    )

    def fraction_list_as_str(lst):
        return "[" + ", ".join(str(f) for f in lst) + "]"

    logger.info(f"xrate:\t{xrate}")
    logger.info(f"rational b_buy_amounts:\t{fraction_list_as_str(b_buy_amounts)}")
    logger.info(f"rational s_buy_amounts:\t{fraction_list_as_str(s_buy_amounts)}")
    logger.info(f"objective:\t{objective}")

    # Dump solution if a float solution is requested, otherwise round it first.
    if args.solution_type == "float":
        dump_solution(
            args.instance, args.solution,
            b_orders, s_orders, b_buy_amounts, s_buy_amounts,
            xrate=xrate,
            b_buy_token_price=args.b_buy_token_price,
            fee=fee,
            arith_traits=RationalTraits()
        )
    else:
        b_buy_amounts, s_buy_amounts = round_solution(
            b_orders, s_orders,
            b_buy_amounts, s_buy_amounts,
            xrate,
            b_buy_token_price=args.b_buy_token_price,
            fee=fee
        )
        logger.info(f"integer b_buy_amounts:\t{b_buy_amounts}")
        logger.info(f"integer s_buy_amounts:\t{s_buy_amounts}")

        validate(
            accounts,
            b_orders, s_orders, b_buy_amounts, s_buy_amounts,
            xrate, args.b_buy_token_price, fee
        )

        dump_solution(
            args.instance, args.solution,
            b_orders, s_orders, b_buy_amounts, s_buy_amounts,
            xrate=xrate,
            b_buy_token_price=args.b_buy_token_price,
            fee=fee,
            arith_traits=IntegerTraits()
        )

    logger.info(f"Solution file is {args.solution.name} .")


if __name__ == "__main__":

    logging.basicConfig(level=logging.DEBUG)
    logger.setLevel(logging.DEBUG)

    parser = argparse.ArgumentParser(
        description="Compute optimal execution of a set of orders over a pair of tokens"
    )
    parser.add_argument(
        'instance',
        type=argparse.FileType('r'),
        help='File containing the instance to solve.'
    )
    parser.add_argument(
        'token_pair',
        type=str,
        nargs=2,
        help='Token pair (b_buy_token, s_buy_token).'
    )
    parser.add_argument(
        '--b_buy_token_price',
        type=F,
        default=int(1e18),
        help="Price of b_buy_token (not required as it merely scales objective value)."
    )
    parser.add_argument(
        '--exchange_rate',
        type=F,
        help='Exchange rate (token1/token2) as a fraction.'
    )
    parser.add_argument(
        '--solution',
        type=argparse.FileType('w+'),
        default=tempfile.NamedTemporaryFile(
            mode='w+', delete=False, prefix="solution-", suffix=".json"
        ),
        help='File where the solution should be output to.'
    )

    parser.add_argument(
        '--solution_type',
        type=str,
        choices=["float", "int"],
        default="int",
        help='If a float or integer solution should be output.'
    )

    args = parser.parse_args()

    main(args)
