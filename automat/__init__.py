# -*- test-case-name: automat -*-
from ._methodical import MethodicalMachine
from ._core import NoTransition
from ._typical import ClusterStateDecorator as TypicalMachine

__all__ = [
    'MethodicalMachine',
    'TypicalMachine',
    'NoTransition',
]
