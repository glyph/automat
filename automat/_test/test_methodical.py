
"""
Tests for the public interface of Automat.
"""

from unittest import TestCase

from automat import MethodicalMachine

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
        """
        class Machination(object):
            machine = MethodicalMachine()
        machination = Machination()
        with self.assertRaises(AttributeError) as cm:
            machination.machine
        self.assertIn("MethodicalMachine is an implementation detail",
                      str(cm.exception))


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
            @machine.output()
            def anOutput(self):
                return 1 / 0
        machination = Machination()
        with self.assertRaises(AttributeError) as cm:
            machination.anOutput

        self.assertIn(
            "Machination.anOutput is a state-machine output method; to "
            "produce this output, call an input method instead.",
            str(cm.exception)
        )

