
from automat._core import Automaton

from unittest import TestCase

class CoreTests(TestCase):
    """
    Tests for Automat's (currently private, implementation detail) core.
    """

    def test_noOutputForInput(self):
        """
        L{Automaton.outputForInput} raises L{NotImplementedError} if no
        transition for that input is defined.
        """
        a = Automaton()
        self.assertRaises(NotImplementedError, a.outputForInput,
                          "no-state", "no-symbol")


    def test_oneTransition(self):
        """
        L{Automaton.addTransition} adds its input symbol to
        L{Automaton.inputAlphabet}, all its outputs to
        L{Automaton.outputAlphabet}, and causes L{Automaton.outputForInput} to
        start returning the new state and output symbols.
        """
        a = Automaton()
        a.addTransition("beginning", "begin", "ending", ["end"])
        self.assertEqual(list(a.inputAlphabet()), ["begin"])
        self.assertEqual(list(a.outputAlphabet()), ["end"])
        self.assertEqual(a.outputForInput("beginning", "begin"),
                         ("ending", ["end"]))

