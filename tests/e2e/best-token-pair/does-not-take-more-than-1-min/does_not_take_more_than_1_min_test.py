"""Asserts that solver does not take more than 1 minute to solve passed instance."""
from dex_open_solver.best_token_pair_solver.solver import main
from argparse import Namespace
from time import time


def test_does_not_take_more_than_1_min(local_instance):
    """Asserts that solver does not take more than 1 minute to solve passed instance."""
    with open(local_instance, 'r') as fd:
        args = Namespace(
            instance=fd,
            solution_filename=None,
            xrate=None
        )
        tic = time()
        main(args)
        tac = time()
        assert tac - tic <= 60
