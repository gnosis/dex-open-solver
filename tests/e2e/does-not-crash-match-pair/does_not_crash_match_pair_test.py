"""Assert that an instance should not crash the solver."""
from src.token_pair_solver.solver import main
from argparse import Namespace
import tempfile


def test_should_not_crash(local_instance):
    """Asserts that passed local_instance should not raise."""
    solution = tempfile.NamedTemporaryFile(
        mode='w+', delete=False, prefix='solution-', suffix='.json'
    )
    with open(local_instance, 'r') as fd:
        args = Namespace(
            instance=fd,
            token_pair=('token0', 'token1'),
            solution=solution,
            xrate=None
        )
        main(args)
