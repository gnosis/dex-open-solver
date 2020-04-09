"""Assert that an instance has a nontrivial solution."""
from src.token_pair_solver.solver import main
from argparse import Namespace
import json


def test_has_non_trivial_solution(local_instance):
    """Asserts that passed local_instance has a nontrivial solution."""
    with open(local_instance, 'r') as fd:
        args = Namespace(
            instance=fd,
            token_pair=('token0', 'token1'),
            solution_filename=None,
            xrate=None
        )
        solution = main(args)
        assert any(int(order["execSellAmount"]) > 0 for order in solution["orders"])
