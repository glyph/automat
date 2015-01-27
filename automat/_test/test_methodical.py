
"""
Tests for the public interface of Automat.
"""

from unittest import TestCase

from .. import MethodicalMachine

class MethodicalTests(TestCase):
    """
    Tests for L{MethodicalMachine}.
    """

    def test_oneTransition(self):
        """
        L{MethodicalMachine} provides a way for you to declare a state machine
        with inputs, outputs, and states as methods.  When you have declared an
        input, an output, and a state, calling the input method in that state
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

            @machine.state(initial=True)
            def anState(self):
                "a state"

            @machine.state()
            def anotherState(self):
                "another state"

            anState.upon(anInput, enter=anotherState, outputs=[anOutput])
            anotherState.upon(anInput, enter=anotherState,
                              outputs=[anotherOutput])

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
            @machine.state(initial=True)
            def state(self):
                "a machine state"
            state.upon(anInput, enter=state, outputs=[anOutput])
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
            @a.state(initial=True)
            def initialA(self):
                "initial A"
            @b.state(initial=True)
            def initialB(self):
                "initial B"
            def outputA(self):
                return "A"
            def outputB(self):
                return "B"
            initialA.upon(inputA, initialA, [outputA])
            initialB.upon(inputB, initialB, [outputB])

        mm = MultiMach()
        self.assertEqual(mm.inputA(), ["A"])
        self.assertEqual(mm.inputB(), ["B"])


    def test_methodName(self):
        """
        Input methods preserve their declared names.
        """
        class Mech(object):
            m = MethodicalMachine()
            @m.input()
            def declaredInputName(self):
                "an input"
            @m.state(initial=True)
            def aState(self):
                "state"
        m = Mech()
        with self.assertRaises(TypeError) as cm:
            m.declaredInputName("too", "many", "arguments")
        self.assertIn("declaredInputName", str(cm.exception))

# FIXME: error for more than one initial state
# FIXME: error for wrong types on any call to _oneTransition
# FIXME: better public API for .upon; maybe a context manager?
# FIXME: when transitions are defined, validate that we can always get to
# terminal? do we care about this?
# FIXME: implementation (and use-case/example) for passing args from in to out

# FIXME: possibly these need some kind of support from core
# FIXME: wildcard state (in all states, when input X, emit Y and go to Z)
# FIXME: wildcard input (in state X, when any input, emit Y and go to Z)
# FIXME: combined wildcards (in any state for any input, emit Y go to Z)
