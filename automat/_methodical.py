# -*- test-case-name: automat._test.test_methodical -*-

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
        transitioner = getattr(oself, '_transitioner', None)
        if transitioner is None:
            transitioner = oself._transitioner = Transitioner(
                self._automaton,
                list(self._automaton._initialStates)[0],
            )
        def doInput(methodInput):
            outputs = []
            for output in transitioner.transition(methodInput):
                # TODO: return return value
                outputs.append(output(self))
            return outputs
        return doInput
