"""Assert that an instance should not crash the solver."""
from src.main import main
from argparse import Namespace
import tempfile


def test_should_not_crash(local_instance):
    """Asserts that passed local_instance should not raise."""
    solution = tempfile.NamedTemporaryFile(
        mode='w+', delete=False, prefix="solution-", suffix=".json"
    )
    with open(local_instance, "r") as fd:
        args = Namespace(
            instance=fd,
            token_pair=["token0", "token1"],
            exchange_rate=None,
            b_buy_token_price=int(1e18),
            solution_type="int",
            solution=solution
        )
        main(args)
