"""Global configuration for pytest."""
import glob
from pathlib import Path
import pytest
from itertools import product
from copy import deepcopy


def has_tag(filename, tag):
    """Check if a filename has a given tag."""
    return f':{tag}' in filename


def pytest_collection_modifyitems(items):
    """Add a "slow" marker to any test with a ':slow' substring in its name."""
    for item in items:
        if has_tag(item.nodeid, "slow"):
            item.add_marker(pytest.mark.slow)


def get_local_instance_parameter_values(metafunc):
    """Add `local_instance` variable to tests.

    Populate `local_instance` variable with any *.json file in the same
    directory as the test.
    """
    cur_dir = Path(metafunc.module.__file__).parent
    instances = glob.glob(str(cur_dir) + '/*.json')

    return instances


def is_valid_param_value_tuple(param_values):
    """Return if a given test parametrization is allowed."""
    return True


def pytest_generate_tests(metafunc):
    """Register ad-hoc test parameters."""
    parameters = []

    if 'local_instance' in metafunc.fixturenames:
        parameters.append((
            'local_instance',
            get_local_instance_parameter_values(metafunc)
        ))

    param_names = [par[0] for par in parameters]
    param_values = [par[1] for par in parameters]
    valid_param_value_tuples = [
        pytest.param(*param_value_tuple)
        for param_value_tuple in product(*param_values)
        if is_valid_param_value_tuple(dict(zip(param_names, param_value_tuple)))
    ]

    metafunc.parametrize(argnames=param_names, argvalues=valid_param_value_tuples)


def pytest_addoption(parser):
    parser.addoption('--slow', action='store_true', dest="slow",
                     default=False, help="enable slow tests")


def pytest_configure(config):
    if not config.option.slow:
        setattr(config.option, 'markexpr', 'not slow')
