"""Assert that an instance has a trivial solution."""
from src.best_token_pair_solver.solver import main
from argparse import Namespace


def test_has_trivial_solution(local_instance):
    """Asserts that passed local_instance has a trivial solution."""
    with open(local_instance, 'r') as fd:
        args = Namespace(
            instance=fd,
            solution_filename=None,
            xrate=None
        )
        solution = main(args)
        assert len(solution["orders"]) == 0

