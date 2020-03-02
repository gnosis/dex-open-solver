from fractions import Fraction as F
import argparse
import json
import logging
from .solver.xrate import find_best_xrate
from .solver.amount import find_best_buy_amounts
from .objective import evaluate_objective_rational

logger = logging.getLogger(__name__)


def main(instance, token_pair, b_buy_token_price, xrate=None):
    problem = json.load(instance)
    b_buy_token, s_buy_token = token_pair

    b_orders = [
        order for order in problem["orders"]
        if order["buyToken"] == b_buy_token and order["sellToken"] == s_buy_token
    ]
    s_orders = [
        order for order in problem["orders"]
        if order["buyToken"] == s_buy_token and order["sellToken"] == b_buy_token
    ]

    fee_ratio = F(0)    # TODO:  fee is not working yet

    if xrate is None:
        xrate, _ = find_best_xrate(b_orders, s_orders, fee_ratio)

    b_buy_amounts, s_buy_amounts = find_best_buy_amounts(
        xrate, b_orders, s_orders, fee_ratio
    )

    objective = evaluate_objective_rational(
        b_orders,
        s_orders,
        xrate,
        b_buy_amounts,
        s_buy_amounts,
        b_buy_token_price=b_buy_token_price,
        s_buy_token_price=b_buy_token_price / xrate
    )

    def fraction_list_as_str(lst):
        return "[" + ", ".join(str(f) for f in lst) + "]"

    logger.info(f"xrate:\t{xrate}")
    logger.info(f"b_buy_amounts:\t{fraction_list_as_str(b_buy_amounts)}")
    logger.info(f"s_buy_amounts:\t{fraction_list_as_str(s_buy_amounts)}")
    logger.info(f"objective:\t{objective}")


if __name__ == "__main__":

    logging.basicConfig(level=logging.DEBUG)
    logger.setLevel(logging.DEBUG)

    parser = argparse.ArgumentParser(
        description="Compute optimal execution of a set of orders over a pair of tokens"
    )
    parser.add_argument(
        'instance',
        type=argparse.FileType('r'),
        help='File containing the source instance analyze.'
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

    args = parser.parse_args()

    main(args.instance, args.token_pair, args.b_buy_token_price, args.exchange_rate)
