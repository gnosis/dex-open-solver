"""Assert that an instance has a nonnegative touched disregarded utility."""
from dex_open_solver.token_pair_solver.solver import main
from argparse import Namespace


def test_has_nonnegative_touched_du_objective(local_instance):
    """Asserts that passed local_instance has nonnegative touched disregarded utility.
    
    That is, it asserts that u <= umax over touched orders.
    """
    with open(local_instance, 'r') as fd:
        args = Namespace(
            instance=fd,
            token_pair=('token0', 'token1'),
            solution_filename=None,
            xrate=None
        )
        solution = main(args)
        objective_metrics = solution['objVals']
        assert objective_metrics['utility_disreg_touched'] >= 0
