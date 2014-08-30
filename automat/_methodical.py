# -*- test-case-name: test_automat -*-

from functools import wraps
from characteristic import attributes

from ._core import Transitioner, Automaton

def _keywords_only(f):
    """
    Decorate a function so all its arguments must be passed by keyword.

    A useful utility for decorators that take arguments so that they don't
    accidentally get passed the thing they're decorating as their first
    argument.

    Only works for methods right now.
    """
    @wraps(f)
    def g(self, **kw):
        return f(self, **kw)
    return g



@attributes(['machine', 'method'])
class MethodicalState(object):
    """
    A state for a L{MethodicalMachine}.
    """



@attributes(['machine', 'method'])
class MethodicalInput(object):
    """
    An input for a L{MethodicalMachine}.
    """

    def __get__(self, oself, type=None):
        """
        Perform the input.
        """
        def inputit():
            # provide the input to the transitioner
            inputFunction = self.machine.inputFunctionFor(oself)
            return inputFunction(self)
        return inputit



class MethodicalMachine(object):
    """
    A L{MethodicalMachine} is an interface to an L{Automaton} that uses methods
    on a class.
    """

    def __init__(self):
        self._automaton = Automaton()


    @_keywords_only
    def state(self, initial=False, terminal=False):
        """
        Declare a state, possibly an initial state or a terminal state.

        This is a decorator for methods, but it will modify the method so as
        not to be callable any more.
        """
        def decorator(stateMethod):
            state = MethodicalState(machine=self,
                                    method=stateMethod)
            if initial:
                self._automaton.addInitialState(state)
            return state
        return decorator


    @_keywords_only
    def input(self):
        """
        Declare an input.

        This is a decorator for methods.
        """
        def decorator(inputMethod):
            return MethodicalInput(machine=self,
                                   method=inputMethod)
        return decorator


    @_keywords_only
    def output(self):
        """
        Declare an output.

        This is a decorator for methods.

        This method will be called when the state machine transitions to this
        state as specified in the L{MethodicalMachine.output} method.
        """
        def decorator(outputMethod):
            @wraps(outputMethod)
            def wrapper(self):
                return outputMethod(self)
            # is wrapping even necessary? hmm.
            return wrapper
        return decorator


    def transitions(self, transitions):
        """
        Declare a set of transitions.

        @param transitions: a L{list} of 4-tuples of (startState - a method
            decorated with C{@state()}, inputToken - a method decorated with
            C{@input()}, endState - a method decorated with C{@state()},
            outputTokens - a method decorated with C{@output()}).
        @type transitions: L{list} of 4-L{tuples} of (L{MethodicalState},
            L{MethodicalInput}, L{MethodicalState}, L{list} of
            L{types.FunctionType}).
        """
        for startState, inputToken, endState, outputTokens in transitions:
            if not isinstance(startState, MethodicalState):
                raise NotImplementedError("start state {} isn't a state"
                                          .format(startState))
            if not isinstance(inputToken, MethodicalInput):
                raise NotImplementedError("start state {} isn't an input"
                                          .format(inputToken))
            if not isinstance(endState, MethodicalState):
                raise NotImplementedError("end state {} isn't a state"
                                          .format(startState))
            for output in outputTokens:
                if not isinstance(endState, MethodicalState):
                    raise NotImplementedError("output state {} isn't a state"
                                              .format(endState))
            self._automaton.addTransition(startState, inputToken, endState,
                                          tuple(outputTokens))


    def inputFunctionFor(self, oself):
        """
        Get a L{MethodicalTransitioner} associated with C{oself}, creating one
        if it doesn't exist.
        """
        doInput = getattr(oself, '_doInput', None)
        if doInput is not None:
            return doInput
        transitioner = MethodicalTransitioner(automaton=self._automaton,
                                              appobj=oself)
        oself._doInput = transitioner.doInput
        return oself._doInput



@attributes(['automaton', 'appobj'])
class MethodicalTransitioner(object):
    """
    Methodical transitioner.
    """

    def __init__(self):
        self._transitioner = Transitioner(
            self.automaton,
            # TODO: enforce a single initial state, or figure out a way to
            # specify it.
            list(self.automaton._initialStates)[0],
        )

    def doInput(self, methodInput):
        outputs = []
        for output in self._transitioner.transition(methodInput):
            # TODO: return return value
            outputs.append(output(self.appobj))
        return outputs
