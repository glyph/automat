from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any, Protocol


if sys.version_info >= (3, 9):
    from typing import Annotated

from unittest import TestCase

from .._typical import TypicalBuilder
from automat import Enter


def requiredPreviousState(message: str) -> Any:
    def nope() -> Any:
        raise RuntimeError(f"noep: {message}")

    return field(default_factory=nope)


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

    def valcheck2(self) -> int:
        """
        check on the other value
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

    def use_private(self) -> PrivateInputs:
        """
        Get the private interface.
        """


class PrivateInputs(Protocol):
    """
    Private Inputs!
    """

    def _private_method(self) -> int:
        """
        These methods are kept separate
        """


class StateCore(object):
    "It's a state core"
    count: int = 0
    shared: int = 10


builder = TypicalBuilder(SomeInputs, StateCore)
# TODO: right now this must be module-scope because type annotations get
# evaluated in global scope, but we could capture scopes in .state() and
# .handle()


@builder.common(SomeInputs.in_every_state)
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

    if sys.version_info >= (3, 9):
        # Use Annotated when we can
        @builder.handle(SomeInputs.depcheck)
        def from_core(self, count: str) -> Annotated[str, Enter(CoreDataRequirer)]:
            return count

    else:

        @builder.handle(SomeInputs.depcheck, enter=CoreDataRequirer)
        def from_core(self, count: str) -> str:
            return count

    @builder.handle(SomeInputs.next)
    def justself(self) -> tuple[object, int]:
        return (self, 0)

    @builder.handle(SomeInputs.ephemeral)
    def ephemeral(self) -> None:
        ...

    @builder.handle(SomeInputs.special)
    def special(self, something: SomethingSpecial) -> None:
        ...

    @builder.handle(SomeInputs.special_ephemeral)
    def special_ephemeral(self, something: SomethingSpecial) -> None:
        ...

    @builder.handle(SomeInputs.outside)
    def outside(self) -> None:
        """
        transition to state that can respond to reveal_inputs
        """

    @builder.handle(PrivateInputs._private_method)
    def _private(self) -> int:
        """
        Implement the private method.
        """
        return 3333


@builder.common(SomeInputs.use_private, PrivateInputs)
def use_private(
    public: SomeInputs, core: StateCore, private: PrivateInputs
) -> PrivateInputs:
    return private


@builder.state()
@dataclass
class RequiresSpecial(object):
    something: SomethingSpecial = requiredPreviousState("RequiresSpecial.something")

    @builder.handle(SomeInputs.read_special)
    # can't get any of these to type-check because we can require any previous
    # state.  maybe that's a mistake?  if you want to know about something,
    # scribble it on the state core?

    def read_special(self) -> SomethingSpecial:
        return self.something

    @builder.handle(SomeInputs.back, enter=FirstState)
    def back(self) -> tuple[object, int]:
        return self, 7890

FirstState.special.enter(RequiresSpecial)
RequiresSpecial.read_special.enter(RequiresSpecial)

@builder.state()
@dataclass
class RequiresOutside(object):
    """ """

    machine_itself: SomeInputs

    @builder.handle(SomeInputs.reveal_inputs)
    def reveal_inputs(self) -> SomeInputs:
        return self.machine_itself

FirstState.outside.enter(RequiresOutside)

@builder.state(persist=False)
@dataclass
class RequiresSpecialEphemeral(object):
    something: SomethingSpecial# = requiredPreviousState("RequiresSpecialEphemeral.something")

    @builder.handle(SomeInputs.read_special, enter=RequiresSpecial)
    def read_special(self) -> SomethingSpecial:
        return self.something

FirstState.special_ephemeral.enter(RequiresSpecialEphemeral)

@builder.state()
@dataclass
class RequiresFirstState1(object):
    other_state: FirstState# = requiredPreviousState("RequiresFirstState1.other_state")

    @builder.handle(SomeInputs.next)
    def justrequired(self) -> tuple[object, int]:
        return (self.other_state, 1)

    @builder.handle(SomeInputs.back, enter=FirstState)
    def goback(self) -> tuple[object, int]:
        return (self.other_state, 1)


FirstState.justself.enter(RequiresFirstState1)


@builder.state()
@dataclass
class RequiresFirstState2(object):
    other_state: FirstState# = requiredPreviousState("RequiresFirstState2.other_state")

    @builder.handle(SomeInputs.next)
    def justrequired(self) -> tuple[object, int]:
        return (self.other_state, 2)

RequiresFirstState1.justrequired.enter(RequiresFirstState2)

@builder.state()
@dataclass
class CoreDataRequirer(object):
    """
    I require data supplied by the state core (persistently).
    """

    count: int# = requiredPreviousState("CoreDataRequirer.count")
    shared: int = 7878

    @builder.handle(SomeInputs.valcheck)
    def get(self) -> int:
        return self.count

    @builder.handle(SomeInputs.valcheck2)
    def getshared(self) -> int:
        return self.shared

    @builder.handle(SomeInputs.back, enter=FirstState)
    def back(self) -> tuple[object, int]:
        return self, 1234


@builder.state(persist=False)
@dataclass
class Ephemeral:
    count: int# = requiredPreviousState("Ephemeral.count")

    @builder.handle(SomeInputs.valcheck)
    def get(self):
        return self.count

    @builder.handle(SomeInputs.persistent, enter=CoreDataRequirer)
    def persistent(self) -> None:
        pass

print('setting FirstState.ephemeral to enter')
FirstState.ephemeral.enter(Ephemeral)
print("i set it")

C = builder.buildClass()


class Simple(Protocol):
    """
    A very simple protocol.
    """

    def method(self) -> int:
        """
        An input.
        """

    def unhandled(self) -> str:
        """
        An input that is not handled in the first state.
        """


class EmptyCore(object):
    """
    State core with no properties.
    """


builder1 = TypicalBuilder(Simple, EmptyCore)


@builder1.state()
class SimpleState(object):
    """
    State that cannot handle any inputs
    """

    @builder1.handle(Simple.method)
    def method(self) -> int:
        return 7


@builder1.state(error=True)
class RecoverableErrorState(object):
    """
    Error state where we can recover.
    """

    @builder1.handle(Simple.method, enter=SimpleState)
    def method(self) -> int:
        """
        Return a tag, then transition back to the recoverable state.
        """
        return 8

    @builder1.handle(Simple.unhandled)
    def unhandled(self) -> str:
        """
        We do handle it though.
        """
        return "handled"


C1 = builder1.buildClass()


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
        default = i.valcheck2()
        self.assertEqual(i.valcheck(), 2)
        self.assertEqual(default, 7878)

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

    def test_private_protocol(self) -> None:
        """
        You can use a private protocol to have private input methods for e.g.
        callbacks that are not exposed publicly on your public interface.
        """
        i = C()
        nothing = object()
        private_proxy = i.use_private()
        # possible TODOs: should we separate interfaces at runtime?
        # TODO: private methods do not appear on the public object.
        # self.assertIs(getattr(i, "_private_method", nothing), nothing)
        # Public methods do not appear on the private object.
        # TODO: self.assertIs(getattr(private_proxy, "use_private", nothing), nothing)
        self.assertEqual(private_proxy._private_method(), 3333)

    def test_unhandled_transition(self) -> None:
        """
        Unhandled transitions raise an exception and transition to an
        unrecoverable error state.
        """
        i = C()
        with self.assertRaises(RuntimeError) as re:
            i.valcheck()

        def check(it: str, state: str, input: str) -> None:
            self.assertIn("unhandled:", it)
            self.assertIn(f"state:{state}", it)
            self.assertIn(f"input:{input}", it)

        check(str(re.exception), "FirstState", "valcheck")
        with self.assertRaises(RuntimeError) as re:
            i.next()
        check(str(re.exception), "Error", "next")

    def test_unhandled_custom_error(self) -> None:
        """
        Unhandled transitions raise an exception and transition to an
        unrecoverable error state.
        """
        i = C1()
        self.assertEqual(i.method(), 7)
        with self.assertRaises(RuntimeError) as re:
            i.unhandled()

        def check(it: str, state: str, input: str) -> None:
            self.assertIn("unhandled:", it)
            self.assertIn(f"state:{state}", it)
            self.assertIn(f"input:{input}", it)

        check(str(re.exception), "SimpleState", "unhandled")
        self.assertEqual(i.unhandled(), "handled")
        self.assertEqual(i.method(), 8)
        self.assertEqual(i.method(), 7)

    def test_isinstance(self) -> None:
        """
        isinstance(proxy, _TypicalClass) returns True.
        """
        i = C1()
        self.assertIsInstance(i, C1)
        self.assertNotIsInstance(object(), C1)
        self.assertNotIsInstance(i, C)

    def test_buildTwice(self) -> None:
        """
        You can't .buildClass twice.
        """
        with self.assertRaises(RuntimeError) as re:
            builder.buildClass()
        self.assertIn("only build once", str(re.exception))

    def test_unsatisfiedDependency(self) -> None:
        """
        Unsatisfied dependencies will raise an exception in buildClass.
        """

        class Empty(Protocol):
            pass

        class Core:
            pass

        tmpbuild = TypicalBuilder(Empty, Core)

        @tmpbuild.state()
        @dataclass
        class StateWithReq:
            foo: float

        X = tmpbuild.buildClass()
        with self.assertRaises(AttributeError) as re:
            X()
        self.assertIn("has no attribute 'foo'", str(re.exception))
