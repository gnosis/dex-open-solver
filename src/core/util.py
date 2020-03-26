from fractions import Fraction as F
import logging


def transform(obj, transformer):
    if isinstance(obj, dict):
        obj = {k: transform(v, transformer) for k, v in obj.items()}
    elif isinstance(obj, list):
        obj = [transform(i, transformer) for i in obj]
    elif isinstance(obj, tuple):
        obj = tuple(transform(i, transformer) for i in obj)
    obj = transformer(obj)
    return obj


def stringify_numeric(obj):
    def transformer(obj):
        if isinstance(obj, F) or isinstance(obj, int):
            return str(obj)
        return obj
    return transform(obj, transformer)


class PrettyFloat(float):
    def __str__(self):
        return '%.3e' % self

    def __repr__(self):
        return self.__str__()


class PrettyFraction(F):
    def __str__(self):
        return super().__str__()

    def __repr__(self):
        return self.__str__()


class LoggerFormatter(logging.Formatter):
    def __init__(self, *args, **kwargs):
        self.rationals = 'rationals' in kwargs.keys() and kwargs['rationals']
        kwargs.pop('rationals', None)
        super().__init__(*args, **kwargs)

    def transform_fractions_to_floats(self, obj):
        if isinstance(obj, F):
            return PrettyFloat(obj)
        return obj

    def prettify_fractions(self, obj):
        if isinstance(obj, F):
            return PrettyFraction(obj)
        return obj

    def format(self, record):
        if not self.rationals:
            record.args = transform(record.args, self.transform_fractions_to_floats)
        else:
            record.args = transform(record.args, self.prettify_fractions)
        text = f'{record.levelname:7s}::{record.module:<11s}: {record.getMessage()}'
        return text
