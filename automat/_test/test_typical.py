from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from unittest import TestCase

from .._typical import TypicalBuilder


class OneInput(Protocol):
    def one(self) -> int:
        "It's the input"

    def depcheck(self, count: str) -> str:
        """
        Check populating of dependencies.

        Parameter of conflicting type should not be used.
        """

    def valcheck(self) -> int:
        """
        check on the value
        """

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

    @builder.handle(OneInput.depcheck, enter=lambda: CoreDataRequirer)
    def from_core(self, count: str):
        return count


@builder.state()
@dataclass
class CoreDataRequirer(object):
    """
    I require data supplied by the state core.
    """
    count: int

    @builder.handle(OneInput.valcheck)
    def get(self) -> int:
        return self.count

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

    def test_required_from_core(self) -> None:
        """
        Parameters required by state class which match a type/name pair exactly
        from the state core will be populated from there (state input
        parameters will be ignored if they are the wrong type).
        """
        i = C()
        i.one()
        i.one()
        i.depcheck("ignore")
        self.assertEqual(i.valcheck(), 2)
