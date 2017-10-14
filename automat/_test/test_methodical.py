"""
Tests for the public interface of Automat.
"""
from functools import reduce
from unittest import TestCase

from .. import MethodicalMachine, NoTransition
from .. import _methodical


class MethodicalTests(TestCase):
    """
    Tests for L{MethodicalMachine}.
    """

    def test_oneTransition(self):
        """
        L{MethodicalMachine} provides a way for you to declare a state machine
        with inputs, outputs, and flags as methods.  When you have declared an
        input, an output, and a flag, calling the input method in that state
        will produce the specified output.
        """

        class Machination(object):
            machine = MethodicalMachine()

            @machine.input()
            def anInput(self):
                "an input"

            @machine.output()
            def anOutput(self):
                "an output"
                return "an-output-value"

            @machine.output()
            def anotherOutput(self):
                "another output"
                return "another-output-value"

            @machine.flag(states=['state one', 'state two'], initial='state one')
            def aFlag(self):
                "a flag"

            machine.transition(
                from_={'aFlag': 'state one'},
                to={'aFlag': 'state two'},
                input=anInput,
                outputs=[anOutput],
            )
            machine.transition(
                from_={'aFlag': 'state two'},
                to={'aFlag': 'state two'},
                input=anInput,
                outputs=[anotherOutput],
            )

        m = Machination()
        self.assertEqual(m.anInput(), ["an-output-value"])
        self.assertEqual(m.anInput(), ["another-output-value"])

    def test_machineItselfIsPrivate(self):
        """
        L{MethodicalMachine} is an implementation detail.  If you attempt to
        access it on an instance of your class, you will get an exception.
        However, since tools may need to access it for the purposes of, for
        example, visualization, you may access it on the class itself.
        """
        expectedMachine = MethodicalMachine()
        class Machination(object):
            machine = expectedMachine
        machination = Machination()
        with self.assertRaises(AttributeError) as cm:
            machination.machine
        self.assertIn("MethodicalMachine is an implementation detail",
                      str(cm.exception))
        self.assertIs(Machination.machine, expectedMachine)

    def test_outputsArePrivate(self):
        """
        One of the benefits of using a state machine is that your output method
        implementations don't need to take invalid state transitions into
        account - the methods simply won't be called.  This property would be
        broken if client code called output methods directly, so output methods
        are not directly visible under their names.
        """

        class Machination(object):
            machine = MethodicalMachine()
            counter = 0

            @machine.input()
            def anInput(self):
                "an input"

            @machine.output()
            def anOutput(self):
                self.counter += 1

            @machine.flag(states=['a', 'b'], initial='b')
            def flag(self):
                "a machine state"

            machine.transition(
                from_={'flag': 'b'},
                to={'flag': 'b'},
                input=anInput,
                outputs=[anOutput],
            )

        mach1 = Machination()
        mach1.anInput()
        self.assertEqual(mach1.counter, 1)
        mach2 = Machination()
        with self.assertRaises(AttributeError) as cm:
            mach2.anOutput
        self.assertEqual(mach2.counter, 0)
        self.assertIn(
            "Machination.anOutput is a state-machine output method; to "
            "produce this output, call an input method instead.",
            str(cm.exception)
        )

    def test_multipleMachines(self):
        """
        Two machines may co-exist happily on the same instance; they don't
        interfere with each other.
        """
        class MultiMach(object):
            a = MethodicalMachine()
            b = MethodicalMachine()

            @a.input()
            def inputA(self):
                "input A"

            @b.input()
            def inputB(self):
                "input B"

            @a.flag(states=[1, 2], initial=1)
            def initialA(self):
                "initial A"

            @b.flag(states=[3, 4], initial=3)
            def initialB(self):
                "initial B"

            @a.output()
            def outputA(self):
                return "A"

            @b.output()
            def outputB(self):
                return "B"

            a.transition({'initialA': 1}, {'initialA': 2}, inputA, [outputA])
            b.transition({'initialB': 3}, {'initialB': 4}, inputB, [outputB])

        mm = MultiMach()
        self.assertEqual(mm.inputA(), ["A"])
        self.assertEqual(mm.inputB(), ["B"])

    def test_collectOutputs(self):
        """
        Outputs can be combined with the "collector" argument to "upon".
        """
        import operator

        class Machine(object):
            m = MethodicalMachine()

            @m.input()
            def input(self):
                "an input"

            @m.output()
            def outputA(self):
                return "A"

            @m.output()
            def outputB(self):
                return "B"

            @m.flag(states=[1, 2], initial=1)
            def flag(self):
                "a flag"

            m.transition({'flag': 1}, {'flag': 1}, input, [outputA, outputB],
                         collector=lambda x: reduce(operator.add, x))

        m = Machine()
        self.assertEqual(m.input(), "AB")

    def test_methodName(self):
        """
        Input methods preserve their declared names.
        """

        class Mech(object):
            m = MethodicalMachine()

            @m.input()
            def declaredInputName(self):
                "an input"

            @m.flag(states=['a', 'b'], initial='a')
            def aFlag(self):
                "flag"

        m = Mech()
        with self.assertRaises(TypeError) as cm:
            m.declaredInputName("too", "many", "arguments")
        self.assertIn("declaredInputName", str(cm.exception))

    def test_inputWithArguments(self):
        """
        If an input takes an argument, it will pass that along to its output.
        """

        class Mechanism(object):
            m = MethodicalMachine()

            @m.input()
            def input(self, x, y=1):
                "an input"

            @m.flag(states=['a', 'b', 'c'], initial='c')
            def flag(self):
                "a flag"

            @m.output()
            def output(self, x, y=1):
                self._x = x
                return x + y

            m.transition({'flag': 'c'}, {'flag': 'b'}, input, [output])

        m = Mechanism()
        self.assertEqual(m.input(3), [4])
        self.assertEqual(m._x, 3)

    def test_inputFunctionsMustBeEmpty(self):
        """
        The wrapped input function must have an empty body.
        """
        # input functions are executed to assert that the signature matches,
        # but their body must be empty

        _methodical._empty()  # chase coverage
        _methodical._docstring()

        class Mechanism(object):
            m = MethodicalMachine()
            with self.assertRaises(ValueError) as cm:
                @m.input()
                def input(self):
                    "an input"
                    list() # pragma: no cover
            self.assertEqual(str(cm.exception), "function body must be empty")

        # all three of these cases should be valid. Functions/methods with
        # docstrings produce slightly different bytecode than ones without.

        class MechanismWithDocstring(object):
            m = MethodicalMachine()

            @m.input()
            def input(self):
                "an input"

            @m.flag(states=[1, 2], initial=1)
            def flag(self):
                "flag"

            m.transition({'flag': 1}, {'flag': 2}, input, [])

        MechanismWithDocstring().input()

        class MechanismWithPass(object):
            m = MethodicalMachine()

            @m.input()
            def input(self):
                pass

            @m.flag(states=[1, 2], initial=1)
            def flag(self):
                "flag"

            m.transition({'flag': 1}, {'flag': 2}, input, [])

        MechanismWithPass().input()

        class MechanismWithDocstringAndPass(object):
            m = MethodicalMachine()

            @m.input()
            def input(self):
                "an input"
                pass

            @m.flag(states=[1, 2], initial=1)
            def flag(self):
                "flag"

            m.transition({'flag': 1}, {'flag': 2}, input, [])

        MechanismWithDocstringAndPass().input()

        class MechanismReturnsNone(object):
            m = MethodicalMachine()

            @m.input()
            def input(self):
                return None

            @m.flag(states=[1, 2], initial=1)
            def flag(self):
                "flag"

            m.transition({'flag': 1}, {'flag': 2}, input, [])

        MechanismReturnsNone().input()

        class MechanismWithDocstringAndReturnsNone(object):
            m = MethodicalMachine()
            @m.input()
            def input(self):
                "an input"
                return None

            @m.flag(states=[1, 2], initial=1)
            def flag(self):
                "flag"

            m.transition({'flag': 1}, {'flag': 2}, input, [])

        MechanismWithDocstringAndReturnsNone().input()

    def test_inputOutputMismatch(self):
        """
        All the argument lists of the outputs for a given input must match; if
        one does not the call to C{upon} will raise a C{TypeError}.
        """

        class Mechanism(object):
            m = MethodicalMachine()

            @m.input()
            def nameOfInput(self, a):
                "an input"

            @m.output()
            def outputThatMatches(self, a):
                "an output that matches"

            @m.output()
            def outputThatDoesntMatch(self, b):
                "an output that doesn't match"

            @m.flag(states=['a', 'b'], initial='b')
            def flag(self):
                "a flag"

            with self.assertRaises(TypeError) as cm:
                m.transition({'flag': 'b'}, {'flag': 'a'}, nameOfInput,
                             [outputThatMatches, outputThatDoesntMatch])
            self.assertIn("nameOfInput", str(cm.exception))
            self.assertIn("outputThatDoesntMatch", str(cm.exception))

    def test_multipleTransitionsFailure(self):
        """
        A L{MethodicalMachine} can only have one transition per start/event
        pair.
        """

        class WillFail(object):
            m = MethodicalMachine()

            @m.flag(states=['start', 'end'], initial='start')
            def flag(self):
                "The flag."

            @m.input()
            def event(self):
                "An event."

            m.transition(
                from_={'flag': 'start'},
                to={'flag': 'end'},
                input=event,
                outputs=[]
            )
            with self.assertRaises(ValueError):
                m.transition(
                    from_={'flag': 'start'},
                    to={'flag': 'end'},
                    input=event,
                    outputs=[]
                )

    def test_badTransitionForCurrentState(self):
        """
        Calling any input method that lacks a transition for the machine's
        current state raises an informative L{NoTransition}.
        """

        class OnlyOnePath(object):
            m = MethodicalMachine()

            @m.flag(states=['start', 'end'], initial='start')
            def flag(self):
                "The flag."

            @m.input()
            def advance(self):
                "Move from start to end."

            @m.input()
            def deadEnd(self):
                "A transition from nowhere to nowhere."

            m.transition({'flag': 'start'}, {'flag': 'end'}, advance, [])

        machine = OnlyOnePath()
        with self.assertRaises(NoTransition) as cm:
            machine.deadEnd()
        self.assertIn("deadEnd", str(cm.exception))
        self.assertIn("start", str(cm.exception))
        machine.advance()
        with self.assertRaises(NoTransition) as cm:
            machine.deadEnd()
        self.assertIn("deadEnd", str(cm.exception))
        self.assertIn("end", str(cm.exception))

    def test_saveState(self):
        """
        L{MethodicalMachine.serializer} is a decorator that expects its
        decoratee's signature to take a "state" dict as its first argument.
        """

        class Mechanism(object):
            m = MethodicalMachine()

            def __init__(self):
                self.value = 1

            @m.flag(states=['on', 'off'], initial='off', serialized='First')
            def first(self):
                "First flag."

            @m.flag(states=[1, 2], initial=1, serialized='Second')
            def second(self):
                "Second flag."

            @m.serializer()
            def save(self, state):
                return {
                    'machine-state': state,
                    'some-value': self.value,
                }

        self.assertEqual(
            Mechanism().save(),
            {
                "machine-state": {'First': 'off', 'Second': 1},
                "some-value": 1,
            }
        )

    def test_restoreState(self):
        """
        L{MethodicalMachine.unserializer} decorates a function that becomes a
        machine-state unserializer; its return value is mapped to the
        C{serialized} parameter to C{state}, and the L{MethodicalMachine}
        associated with that instance's state is updated to that state.
        """

        class Mechanism(object):
            m = MethodicalMachine()

            def __init__(self):
                self.value = 1
                self.ranOutput = False

            @m.flag(states=['off', 'on'], initial='off', serialized='First')
            def first(self):
                "First flag."

            @m.flag(states=[1, 2], initial=1, serialized='Second')
            def second(self):
                "Second flag."

            @m.input()
            def input(self):
                "an input"

            @m.output()
            def output(self):
                self.value = 2
                self.ranOutput = True
                return 1

            @m.output()
            def output2(self):
                return 2

            m.transition(
                from_={'first': 'off', 'second': 1},
                to={'first': 'on', 'second': 2},
                input=input,
                outputs=[output],
                collector=lambda x: list(x)[0],
            )
            m.transition(
                from_={'first': 'on', 'second': 2},
                to={'first': 'on', 'second': 2},
                input=input,
                outputs=[output2],
                collector=lambda x: list(x)[0],
            )

            @m.serializer()
            def save(self, state):
                return {
                    'machine-state': state,
                    'some-value': self.value,
                }

            @m.unserializer()
            def _restore(self, blob):
                self.value = blob['some-value']
                return blob['machine-state']

            @classmethod
            def fromBlob(cls, blob):
                self = cls()
                self._restore(blob)
                return self

        m1 = Mechanism()
        m1.input()
        blob = m1.save()
        m2 = Mechanism.fromBlob(blob)
        self.assertEqual(m2.ranOutput, False)
        self.assertEqual(m2.input(), 2)
        self.assertEqual(
            m2.save(),
            {
                'machine-state': {'First': 'on', 'Second': 2},
                'some-value': 2,
            }
        )

    def test_flags_must_have_more_than_one_state(self):
        """
        An error should be raised if a flag is defined
        with fewer than two states.
        """

        class Mechanism(object):
            mm = MethodicalMachine()
            with self.assertRaises(ValueError):
                @mm.flag(states=['one'], initial='one')
                def state(self):
                    """some state flag"""

    def test_initial_flag_state_must_be_in_states(self):
        """
        An error should be raised if a flag's initial state
        is not in it's states list.
        """

        class Mechanism(object):
            mm = MethodicalMachine()
            with self.assertRaises(ValueError):
                @mm.flag(states=[1, 2], initial=500)
                def state(self):
                    """some state flag"""

    def test_from_must_be_a_subset_of_a_valid_state(self):
        """ 'from_` must contain flags and values that have been defined. """

        class Methodical(object):
            mm = MethodicalMachine()

            @mm.flag(states=[1, 2], initial=2)
            def flag(self):
                """a flag"""

            @mm.input()
            def go(self):
                """do something"""

            with self.assertRaises(ValueError):
                mm.transition({'pole': 'saw'}, {'pole': 'barn'}, go, [])

    def test_to_must_be_a_subset_of_a_valid_state(self):
        """ 'to` must contain values that have been defined. """

        class Methodical(object):
            mm = MethodicalMachine()

            @mm.flag(states=[1, 2], initial=2)
            def flag(self):
                """a flag"""

            @mm.input()
            def go(self):
                """do something"""

            with self.assertRaises(ValueError):
                mm.transition({'flag': 1}, {'flag': 'pole'}, go, [])

    def test_to_state_must_match_from_state(self):
        """ `to` must have the same keys as `from_` """

        class Mechanism(object):
            mm = MethodicalMachine()

            @mm.flag(states=[1, 2], initial=1)
            def one(self):
                """a flag"""

            @mm.flag(states=['a', 'b'], initial='b')
            def two(self):
                """another flag"""

            @mm.input()
            def go(self):
                """do something"""

            with self.assertRaises(ValueError):
                mm.transition({'one': 2}, {'one': 1, 'two': 'b'}, go, [])


# FIXME: error for wrong types on any call to _oneTransition
# FIXME: better public API for .upon; maybe a context manager?
# FIXME: when transitions are defined, validate that we can always get to
# terminal? do we care about this?
# FIXME: implementation (and use-case/example) for passing args from in to out

# FIXME: possibly these need some kind of support from core
# FIXME: wildcard state (in all states, when input X, emit Y and go to Z)
# FIXME: wildcard input (in state X, when any input, emit Y and go to Z)
# FIXME: combined wildcards (in any state for any input, emit Y go to Z)
