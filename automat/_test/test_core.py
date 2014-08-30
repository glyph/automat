
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
