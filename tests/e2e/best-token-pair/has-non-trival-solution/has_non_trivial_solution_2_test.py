"""Assert that an instance has a nontrivial solution."""
from dex_open_solver.best_token_pair_solver.solver import main
from argparse import Namespace


def test_has_non_trivial_solution(local_instance):
    """Asserts that passed local_instance has a nontrivial solution."""
    with open(local_instance, 'r') as fd:
        args = Namespace(
            instance=fd,
            solution_filename=None,
            xrate=None
        )
        solution = main(args)
        assert any(int(order["execSellAmount"]) > 0 for order in solution["orders"])
