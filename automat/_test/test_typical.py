from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from unittest import TestCase

from .._typical import TypicalBuilder


class OneInput(Protocol):
    def one(self) -> int:
        "It's the input"

class StateCore(object):
    "It's a state core"
    count: int = 0

builder = TypicalBuilder(OneInput, StateCore)

@builder.state()
@dataclass
class TheState(object):
    # TODO: must be module-scope because type annotations get evaluated in
    # global scope
    core: StateCore

    @builder.handle(OneInput.one)
    def go(self) -> int:
        self.core.count += 1
        return self.core.count

C = builder.buildClass()

class TypicalTests(TestCase):
    """
    Tests for L{automat._typical}.
    """

    def test_basic_build(self) -> None:
        """
        Simplest test of all available classes.
        """

        i = C()

        self.assertEqual(i.one(), 1)
        self.assertEqual(i.one(), 2)
