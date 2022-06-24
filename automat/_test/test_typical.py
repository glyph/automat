from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from unittest import TestCase

from .._typical import TypicalBuilder


class SomeInputs(Protocol):
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

    def in_every_state(self, fixture: TestCase) -> int:
        """
        Every state implements this with a default method.
        """

    def next(self) -> tuple[object, int]:
        """
        Advance to next state in the chain for testing something about
        transitioning.
        """

    def back(self) -> tuple[object, int]:
        """
        Return to previous state in the chain for testing something about
        transitioning.
        """



class StateCore(object):
    "It's a state core"
    count: int = 0
    shared: int = 10


builder = TypicalBuilder(SomeInputs, StateCore)


@builder.implement(SomeInputs.in_every_state)
def everystate(
    public_interface: SomeInputs, state_core: StateCore, fixture: TestCase
) -> int:
    """
    In every state, we can implement this the same way.
    """
    methods = set(dir(public_interface))
    fixture.assertIn("one", methods)
    fixture.assertIn("depcheck", methods)
    fixture.assertIn("valcheck", methods)
    fixture.assertIn("in_every_state", methods)
    fixture.assertNotIn("not_an_input", methods)
    fixture.assertIsInstance(state_core, StateCore)
    state_core.shared += 1
    return state_core.shared


@builder.state()
@dataclass
class TheState(object):
    # TODO: right now this must be module-scope because type annotations get
    # evaluated in global scope, but we could capture scopes in .state() and
    # .handle()
    core: StateCore

    @builder.handle(SomeInputs.one)
    def go(self) -> int:
        self.core.count += 1
        return self.core.count

    @builder.handle(SomeInputs.depcheck, enter=lambda: CoreDataRequirer)
    def from_core(self, count: str):
        return count

    @builder.handle(SomeInputs.next, enter=lambda: RequiresTheState1)
    def justself(self) -> tuple[object, int]:
        return (self, 0)

@builder.state()
@dataclass
class RequiresTheState1(object):
    other_state: TheState

    @builder.handle(SomeInputs.next, enter=lambda: RequiresTheState2)
    def justrequired(self) -> tuple[object, int]:
        return (self.other_state, 1)

    @builder.handle(SomeInputs.back, enter=lambda: TheState)
    def goback(self) -> tuple[object, int]:
        return (self.other_state, 1)


@builder.state()
@dataclass
class RequiresTheState2(object):
    other_state: TheState

    @builder.handle(SomeInputs.next)
    def justrequired(self) -> tuple[object, int]:
        return (self.other_state, 2)


@builder.state()
@dataclass
class CoreDataRequirer(object):
    """
    I require data supplied by the state core.
    """

    count: int

    @builder.handle(SomeInputs.valcheck)
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

    def test_default_implementation(self) -> None:
        """
        L{TypicalBuilder.implement} implements the state behavior for every
        state.
        """
        i = C()
        self.assertEqual(i.in_every_state(self), 11)
        # ^ note the value here starts at 10 to distinguish value from 'count'
        i.depcheck("ignore")
        self.assertEqual(i.in_every_state(self), 12)

    def test_state_persistence(self) -> None:
        """
        The same state object required in different contexts should remain
        identical.
        """
        i = C()
        a, c0 = i.next()
        b, c1 = i.back()
        c, c2 = i.next()
        d, c3 = i.next()
        e, c4 = i.next()
        self.assertEqual(c0, 0)
        self.assertEqual(c1, 1)
        self.assertEqual(c2, 0)
        self.assertEqual(c3, 1)
        self.assertEqual(c4, 2)
        self.assertIs(a, b)
        self.assertIs(a, c)
        self.assertIs(a, d)
        self.assertIs(a, e)
