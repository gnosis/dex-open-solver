"""Assert that an instance should not crash the solver."""
from src.best_token_pair_solver.solver import main
from argparse import Namespace


def test_should_not_crash(local_instance):
    """Asserts that passed local_instance should not raise."""
    with open(local_instance, 'r') as fd:
        args = Namespace(
            instance=fd,
            solution_filename=None,
            xrate=None
        )
        main(args)
