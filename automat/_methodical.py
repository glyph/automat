# -*- test-case-name: automat._test.test_methodical -*-

from functools import wraps
from itertools import count

try:
    # Python 3
    from inspect import getfullargspec as getArgsSpec
except ImportError:
    # Python 2
    from inspect import getargspec as getArgsSpec

import attr

from ._core import Transitioner, Automaton
from ._introspection import preserveName

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


@attr.s
class MethodicalState(object):
    """
    A state for a L{MethodicalMachine}.
    """
    machine = attr.ib(repr=False)
    method = attr.ib()
    serialized = attr.ib(repr=False)

    def upon(self, input, enter, outputs, collector=list):
        """
        Declare a state transition within the L{MethodicalMachine} associated
        with this L{MethodicalState}: upon the receipt of the input C{input},
        enter the state C{enter}, emitting each output in C{outputs}.
        """
        inputSpec = getArgsSpec(input.method)
        for output in outputs:
            outputSpec = getArgsSpec(output.method)
            if inputSpec != outputSpec:
                raise TypeError(
                    "method {input} signature {inputSignature} "
                    "does not match output {output} "
                    "signature {outputSignature}".format(
                        input=input.method.__name__,
                        output=output.method.__name__,
                        inputSignature=inputSpec,
                        outputSignature=outputSpec,
                ))
        self.machine._oneTransition(self, input, enter, outputs, collector)


def _transitionerFromInstance(oself, symbol, automaton):
    """
    Get a L{Transitioner}
    """
    transitioner = getattr(oself, symbol, None)
    if transitioner is None:
        transitioner = Transitioner(
            automaton,
            automaton.initialState,
        )
        setattr(oself, symbol, transitioner)
    return transitioner


@attr.s(cmp=False, hash=False)
class MethodicalInput(object):
    """
    An input for a L{MethodicalMachine}.
    """
    automaton = attr.ib(repr=False)
    method = attr.ib()
    symbol = attr.ib(repr=False)
    collectors = attr.ib(default=attr.Factory(dict), repr=False)


    def __get__(self, oself, type=None):
        """
        Return a function that takes no arguments and returns values returned
        by output functions produced by the given L{MethodicalInput} in
        C{oself}'s current state.
        """
        transitioner = _transitionerFromInstance(oself, self.symbol,
                                                 self.automaton)
        @preserveName(self.method)
        @wraps(self.method)
        def doInput(*args, **kwargs):
            self.method(oself, *args, **kwargs)
            previousState = transitioner._state
            outputs = transitioner.transition(self)
            collector = self.collectors[previousState]
            return collector(output(oself, *args, **kwargs)
                             for output in outputs)
        return doInput


@attr.s
class MethodicalOutput(object):
    """
    An output for a L{MethodicalMachine}.
    """
    machine = attr.ib(repr=False)
    method = attr.ib()

    def __get__(self, oself, type=None):
        """
        Outputs are private, so raise an exception when we attempt to get one.
        """
        raise AttributeError(
            "{cls}.{method} is a state-machine output method; "
            "to produce this output, call an input method instead.".format(
                cls=type.__name__,
                method=self.method.__name__
            )
        )


    def __call__(self, oself, *args, **kwargs):
        """
        Call the underlying method.
        """
        return self.method(oself, *args, **kwargs)



counter = count()
def gensym():
    """
    Create a unique Python identifier.
    """
    return "_symbol_" + str(next(counter))



class MethodicalMachine(object):
    """
    A L{MethodicalMachine} is an interface to an L{Automaton} that uses methods
    on a class.
    """

    def __init__(self):
        self._automaton = Automaton()
        self._reducers = {}
        self._symbol = gensym()


    def __get__(self, oself, type=None):
        """
        L{MethodicalMachine} is an implementation detail for setting up
        class-level state; applications should never need to access it on an
        instance.
        """
        if oself is not None:
            raise AttributeError(
                "MethodicalMachine is an implementation detail.")
        return self


    @_keywords_only
    def state(self, initial=False, terminal=False,
              serialized=None):
        """
        Declare a state, possibly an initial state or a terminal state.

        This is a decorator for methods, but it will modify the method so as
        not to be callable any more.

        @param initial: is this state the initial state?  Only one state on
            this L{MethodicalMachine} may be an initial state; more than one is
            an error.
        @type initial: L{bool}

        @param terminal: Is this state a terminal state, i.e. a state that the
            machine can end up in?  (This is purely informational at this
            point.)
        @type terminal: L{bool}

        @param serialized: a serializable value to be used to represent this
            state to external systems.  This value should be hashable;
            L{unicode} is a good type to use.
        @type serialized: a hashable (comparable) value
        """
        def decorator(stateMethod):
            state = MethodicalState(machine=self,
                                    method=stateMethod,
                                    serialized=serialized)
            if initial:
                self._automaton.initialState = state
            return state
        return decorator


    @_keywords_only
    def input(self):
        """
        Declare an input.

        This is a decorator for methods.
        """
        def decorator(inputMethod):
            return MethodicalInput(automaton=self._automaton,
                                   method=inputMethod,
                                   symbol=self._symbol)
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
            return MethodicalOutput(machine=self, method=outputMethod)
        return decorator


    def _oneTransition(self, startState, inputToken, endState, outputTokens,
                       collector):
        """
        See L{MethodicalState.upon}.
        """
        # FIXME: tests for all of this (some of it is wrong)
        # if not isinstance(startState, MethodicalState):
        #     raise NotImplementedError("start state {} isn't a state"
        #                               .format(startState))
        # if not isinstance(inputToken, MethodicalInput):
        #     raise NotImplementedError("start state {} isn't an input"
        #                               .format(inputToken))
        # if not isinstance(endState, MethodicalState):
        #     raise NotImplementedError("end state {} isn't a state"
        #                               .format(startState))
        # for output in outputTokens:
        #     if not isinstance(endState, MethodicalState):
        #         raise NotImplementedError("output state {} isn't a state"
        #                                   .format(endState))
        self._automaton.addTransition(startState, inputToken, endState,
                                      tuple(outputTokens))
        inputToken.collectors[startState] = collector


    @_keywords_only
    def serializer(self):
        """

        """
        def decorator(decoratee):
            @wraps(decoratee)
            def serialize(oself):
                transitioner = _transitionerFromInstance(oself, self._symbol,
                                                         self._automaton)
                return decoratee(oself, transitioner._state.serialized)
            return serialize
        return decorator

    @_keywords_only
    def unserializer(self):
        """

        """
        def decorator(decoratee):
            @wraps(decoratee)
            def unserialize(oself, *args, **kwargs):
                state = decoratee(oself, *args, **kwargs)
                mapping = {}
                for eachState in self._automaton.states():
                    mapping[eachState.serialized] = eachState
                transitioner = _transitionerFromInstance(
                    oself, self._symbol, self._automaton)
                transitioner._state = mapping[state]
                return None # it's on purpose
            return unserialize
        return decorator


    def asDigraph(self):
        """
        Generate a L{graphviz.Digraph} that represents this machine's
        states and transitions.

        @return: L{graphviz.Digraph} object; for more information, please
            see the documentation for
            U{graphviz<https://graphviz.readthedocs.io/>}

        """
        from ._visualize import makeDigraph
        return makeDigraph(
            self._automaton,
            stateAsString=lambda state: state.method.__name__,
            inputAsString=lambda input: input.method.__name__,
            outputAsString=lambda output: output.method.__name__,
        )
