from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from unittest import TestCase

from .._typical import TypicalBuilder


@dataclass
class SomethingSpecial(object):
    """
    Stub custom 'user defined' type.
    """

    # have a value just to make sure we've got a distinct value in the test
    value: str


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

    def ephemeral(self) -> None:
        """
        go to non-persistent state
        """

    def persistent(self) -> None:
        """
        go to a persistent state
        """

    def special(self, something: SomethingSpecial) -> None:
        """
        do something special
        """

    def special_ephemeral(self, something: SomethingSpecial) -> None:
        """
        require SomethingSpecial but on an ephemeral state object so it's
        re-set every time
        """

    def read_special(self) -> SomethingSpecial:
        """
        read the special value
        """

    def outside(result) -> None:
        """
        get ready to reveal inputs
        """

    def reveal_inputs(self) -> SomeInputs:
        """
        return this object in states that depend on it
        """


class StateCore(object):
    "It's a state core"
    count: int = 0
    shared: int = 10


builder = TypicalBuilder(SomeInputs, StateCore)
# TODO: right now this must be module-scope because type annotations get
# evaluated in global scope, but we could capture scopes in .state() and
# .handle()


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
class FirstState(object):
    core: StateCore

    @builder.handle(SomeInputs.one)
    def go(self) -> int:
        self.core.count += 1
        return self.core.count

    @builder.handle(SomeInputs.depcheck, enter=lambda: CoreDataRequirer)
    def from_core(self, count: str):
        return count

    @builder.handle(SomeInputs.persistent, enter=lambda: CoreDataRequirer)
    def persistent(self) -> None:
        pass

    @builder.handle(SomeInputs.next, enter=lambda: RequiresFirstState1)
    def justself(self) -> tuple[object, int]:
        return (self, 0)

    @builder.handle(SomeInputs.ephemeral, enter=lambda: Ephemeral)
    def ephemeral(self) -> None:
        ...

    @builder.handle(SomeInputs.special, enter=lambda: RequiresSpecial)
    def special(self, something: SomethingSpecial) -> None:
        ...

    @builder.handle(
        SomeInputs.special_ephemeral, enter=lambda: RequiresSpecialEphemeral
    )
    def special_ephemeral(self, something: SomethingSpecial) -> None:
        ...

    @builder.handle(SomeInputs.outside, enter=lambda: RequiresOutside)
    def outside(self) -> None:
        """
        transition to state that can respond to reveal_inputs
        """


@builder.state()
@dataclass
class RequiresSpecial(object):
    something: SomethingSpecial

    @builder.handle(SomeInputs.read_special, enter=lambda: RequiresSpecial)
    def read_special(self) -> SomethingSpecial:
        return self.something

    @builder.handle(SomeInputs.back, enter=lambda: FirstState)
    def back(self) -> tuple[object, int]:
        return self, 7890


@builder.state()
@dataclass
class RequiresOutside(object):
    """ """

    machine_itself: SomeInputs

    @builder.handle(SomeInputs.reveal_inputs)
    def reveal_inputs(self) -> SomeInputs:
        return self.machine_itself


@builder.state(persist=False)
@dataclass
class RequiresSpecialEphemeral(object):
    something: SomethingSpecial

    @builder.handle(SomeInputs.read_special, enter=lambda: RequiresSpecial)
    def read_special(self) -> SomethingSpecial:
        return self.something

    @builder.handle(SomeInputs.back, enter=lambda: FirstState)
    def back(self) -> tuple[object, int]:
        return self, 12013


@builder.state()
@dataclass
class RequiresFirstState1(object):
    other_state: FirstState

    @builder.handle(SomeInputs.next, enter=lambda: RequiresFirstState2)
    def justrequired(self) -> tuple[object, int]:
        return (self.other_state, 1)

    @builder.handle(SomeInputs.back, enter=lambda: FirstState)
    def goback(self) -> tuple[object, int]:
        return (self.other_state, 1)


@builder.state()
@dataclass
class RequiresFirstState2(object):
    other_state: FirstState

    @builder.handle(SomeInputs.next)
    def justrequired(self) -> tuple[object, int]:
        return (self.other_state, 2)


@builder.state()
@dataclass
class CoreDataRequirer(object):
    """
    I require data supplied by the state core (persistently).
    """

    count: int

    @builder.handle(SomeInputs.valcheck)
    def get(self) -> int:
        return self.count

    @builder.handle(SomeInputs.ephemeral, enter=lambda: Ephemeral)
    def ephemeral(self) -> None:
        pass

    @builder.handle(SomeInputs.back, enter=lambda: FirstState)
    def back(self) -> tuple[object, int]:
        return self, 1234


@builder.state(persist=False)
@dataclass
class Ephemeral:
    count: int

    @builder.handle(SomeInputs.valcheck)
    def get(self):
        return self.count

    @builder.handle(SomeInputs.persistent, enter=lambda: CoreDataRequirer)
    def persistent(self) -> None:
        pass

    @builder.handle(SomeInputs.back, enter=lambda: FirstState)
    def back(self) -> tuple[object, int]:
        return self, 5678


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

    def test_dependencies_persistent_lifecycle(self) -> None:
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

    def test_dependencies_ephemeral_lifecycle(self) -> None:
        """
        Ensure that ephemeral states are reset on each use, and persistent
        states aren't.
        """
        i = C()
        i.ephemeral()
        self.assertEqual(i.valcheck(), 0)
        i.persistent()
        self.assertEqual(i.valcheck(), 0)
        i.back()
        i.one()
        i.one()
        i.one()
        i.ephemeral()
        self.assertEqual(i.valcheck(), 3)
        i.persistent()
        self.assertEqual(i.valcheck(), 0)

    def test_state_constructor_from_transition_signature(self) -> None:
        """
        If a state class's constructor has a parameter matching a value from
        the method that transitions to it, that parameter is passed in.
        """
        i = C()
        i.special(SomethingSpecial("first"))
        self.assertEqual(i.read_special(), SomethingSpecial("first"))
        self.assertEqual(i.read_special(), SomethingSpecial("first"))
        i.back()
        i.special(SomethingSpecial("second"))
        self.assertEqual(i.read_special(), SomethingSpecial("first"))
        i.back()
        i.special_ephemeral(SomethingSpecial("third"))
        self.assertEqual(i.read_special(), SomethingSpecial("third"))
        i.back()
        i.special_ephemeral(SomethingSpecial("fourth"))
        self.assertEqual(i.read_special(), SomethingSpecial("fourth"))

    def test_reveal_inputs(self) -> None:
        """
        If a state class's constructor has a parameter matching the type of the
        protocol, it injects the state machine itself so that methods can
        provide inputs to push the state machine forward conditionally, or in
        response to external events (i.e. if a callback is required).
        """
        i = C()
        i.outside()
        self.assertIs(i.reveal_inputs(), i)
