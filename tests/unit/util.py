from typing import List, Union, Tuple, Dict, Callable
from hypothesis.core import TestFunc, Example


def examples(example_list: List[Union[Tuple, Dict]]) -> Callable[[TestFunc], TestFunc]:
    """A decorator which ensures a specific list of examples is always tested.

    Generalizes @hypothesis.example decorator to a list of examples.
    """
    def accept(test):
        if not hasattr(test, "hypothesis_explicit_examples"):
            test.hypothesis_explicit_examples = []
        for example in reversed(example_list):
            if isinstance(example, dict):
                test.hypothesis_explicit_examples.append(Example(tuple(), example))
            else:
                test.hypothesis_explicit_examples.append(Example(example, {}))
        return test

    return accept
