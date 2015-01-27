# -*- test-case-name: automat._test.test_core -*-

"""
A core state-machine abstraction.

Perhaps something that could be replaced with or integrated into machinist.
"""

from itertools import chain


class Automaton(object):
    """
    A declaration of a finite state machine.

    Note that this is not the machine itself; it is immutable.
    """

    def __init__(self):
        """
        Initialize the set of transitions and final states.
        """
        self._initialStates = set()
        self._transitions = set()


    def addTransition(self, inState, inputSymbol, outState, outputSymbols):
        """
        Add the given transition to the outputSymbol.
        """
        self._transitions.add(
            (inState, inputSymbol, outState, tuple(outputSymbols))
        )


    def allTransitions(self):
        """
        All transitions.
        """
        return frozenset(self._transitions)


    def addInitialState(self, state):
        """
        Add the given atom to the set of initial states.
        """
        self._initialStates.add(state)


    def inputAlphabet(self):
        """
        The full set of symbols acceptable to this automaton.
        """
        return set(inputSymbol for (inState, inputSymbol, outState,
                                    outputSymbol) in self._transitions)


    def outputAlphabet(self):
        """
        The full set of symbols which can be produced by this automaton.
        """
        return set(
            chain.from_iterable(
                outputSymbols for
                (inState, inputSymbol, outState, outputSymbols)
                in self._transitions
            )
        )


    def states(self):
        """
        All valid states; "Q" in the mathematical description of a state
        machine.
        """
        return frozenset(
            chain.from_iterable(
                (inState, outState)
                for
                (inState, inputSymbol, outState, outputSymbol)
                in self._transitions
            )
        )


    def initialStates(self):
        """
        
        """
        return frozenset(self._initialStates)


    def outputForInput(self, inState, inputSymbol):
        """
        A 2-tuple of (outState, outputSymbols) for inputSymbol.
        """
        for (anInState, anInputSymbol,
             outState, outputSymbols) in self._transitions:
            if (inState, inputSymbol) == (anInState, anInputSymbol):
                return (outState, list(outputSymbols))
        raise NotImplementedError("no transition for {} in {}"
                                  .format(inputSymbol, inState))



class Transitioner(object):
    """
    The combination of a current state and an L{Automaton}.
    """

    def __init__(self, automaton, initialState):
        self._automaton = automaton
        self._state = initialState


    def transition(self, inputSymbol):
        """
        Transition between states, returning any outputs.
        """
        outState, outputSymbols = self._automaton.outputForInput(self._state,
                                                                 inputSymbol)
        self._state = outState
        return outputSymbols



