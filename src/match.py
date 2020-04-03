import argparse
import logging
import tempfile

from .core.util import LoggerFormatter
from .token_pair_solver.solver import \
    setup_arg_parser as setup_token_pair_solver_parser
from .best_token_pair_solver.solver import \
    setup_arg_parser as setup_best_token_pair_parser

logger = logging.getLogger(__name__)


if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description="Match orders in an orderbook."
    )
    parser.add_argument(
        'instance',
        type=argparse.FileType('r'),
        help="File containing the instance to solve."
    )
    parser.add_argument(
        '--solution',
        type=argparse.FileType('w+'),
        default=tempfile.NamedTemporaryFile(
            mode='w+', delete=False, prefix='solution-', suffix='.json'
        ),
        help="File where the solution should be output to. "
             "(by default creates a file in a temp directory)"
    )
    parser.add_argument(
        '--logging',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        type=str,
        help="Logging level."
    )
    parser.add_argument(
        '--log-rationals',
        default=False,
        type=bool,
        help="If true then all numeric quantities will be logged in rational form."
    )

    subparsers = parser.add_subparsers(
        title='subcommand',
        description="valid subcommands",
        help="run `subcommand --help` for help on a subcommand"
    )

    setup_token_pair_solver_parser(subparsers)

    setup_best_token_pair_parser(subparsers)

    args = parser.parse_args()
    log_level = getattr(logging, args.logging)

    handler = logging.StreamHandler()
    formatter = LoggerFormatter(style='{', rationals=args.log_rationals)
    handler.setFormatter(formatter)
    logging.basicConfig(level=log_level, style='{', handlers=[handler])
    logger.setLevel(log_level)

    args.exec_subcommand(args)
