"""Assert that an instance should not crash the solver."""
from src.main import main
from argparse import Namespace


def test_should_not_crash(local_instance):
    """Asserts that passed local_instance should not raise."""
    args = Namespace(
        instance=open(local_instance, "r"),
        token_pair=["token0", "token1"],
        exchange_rate=None
    )
    main(args)
