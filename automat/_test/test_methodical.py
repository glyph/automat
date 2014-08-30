
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
        Test for the simplest possible L{MethodicalMachine}.
        """

        class Machination(object):
            _machine = MethodicalMachine()
            @_machine.input()
            def anInput(self):
                "an input"

            @_machine.output()
            def _anOutput(self):
                "an output"
                return "an-output-value"

            @_machine.output()
            def _anotherOutput(self):
                "another output"
                return "another-output-value"

            @_machine.state(initial=True)
            def _anState(self):
                "a state"

            @_machine.state()
            def _anotherState(self):
                "another state"

            _anState.upon(anInput, _anotherState, [_anOutput])
            _anotherState.upon(anInput, _anotherState, [_anotherOutput])

        m = Machination()
        self.assertEqual(m.anInput(), ["an-output-value"])
        self.assertEqual(m.anInput(), ["another-output-value"])


