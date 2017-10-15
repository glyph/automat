# -*- test-case-name: automat._test.test_methodical -*-

import itertools
from collections import defaultdict
from functools import wraps
from itertools import count

import attr

from ._introspection import preserveName

try:
    # Python 3
    from inspect import getfullargspec as getArgsSpec
except ImportError:
    # Python 2
    from inspect import getargspec as getArgsSpec


def _keywordsOnly(f):
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


class NoTransition(Exception):
    """
    A finite state machine in C{state} has no transition for C{symbol}.

    @param state: the finite state machine's state at the time of the
        illegal transition.

    @param symbol: the input symbol for which no transition exists.
    """

    def __init__(self, state, symbol):
        self.state = state
        self.symbol = symbol
        super(Exception, self).__init__(
            "no transition for {} in {}".format(symbol, state)
        )


@attr.s(frozen=True)
class MethodicalFlag(object):
    """
    A flag for a L{MethodicalMachine}.
    """
    _states = attr.ib(convert=tuple)
    _method = attr.ib()
    _serialized = attr.ib(repr=False)

    def _name(self):
        """
        Get the flag's method name.

        :rtype: str
        """
        return self._method.__name__

    def _serializedName(self):
        """
        Get the serialized representation of the flag's name.

        :rtype: str
        """
        return self._serialized if self._serialized else self._name()


def _empty():
    pass


def _docstring():
    """docstring"""


def assertNoCode(inst, attribute, f):
    # The function body must be empty, i.e. "pass" or "return None", which
    # both yield the same bytecode: LOAD_CONST (None), RETURN_VALUE. We also
    # accept functions with only a docstring, which yields slightly different
    # bytecode, because the "None" is put in a different constant slot.

    # Unfortunately, this does not catch function bodies that return a
    # constant value, e.g. "return 1", because their code is identical to a
    # "return None". They differ in the contents of their constant table, but
    # checking that would require us to parse the bytecode, find the index
    # being returned, then making sure the table has a None at that index.

    if f.__code__.co_code not in (_empty.__code__.co_code,
                                  _docstring.__code__.co_code):
        raise ValueError("function body must be empty")


@attr.s(cmp=False, hash=False)
class MethodicalInput(object):
    """
    An input for a L{MethodicalMachine}.

    :ivar dict collectors:
    """
    _machine = attr.ib(repr=False)  # type: MethodicalMachine
    _method = attr.ib(validator=assertNoCode)  # type: Callable
    symbol = attr.ib(repr=False)
    _transitions = (  # type: Dict[State, Tuple[State, Outputs, Coloector]]
        attr.ib(default=attr.Factory(dict), repr=False)
    )

    def _name(self):
        return self._method.__name__

    def _transition(self, instance):
        """
        Transition the state of `instance`
        and get the corresponding outputs, output tracer and collector.

        :type instance: Any
        :param instance: The instance on which the MethodicalInput was called.
        :rtype: Tuple[tuple, Callable, Callable]
        :return: The outputs, outTracer and collector.
        """
        id_ = id(instance)
        oldState = self._machine._instanceStates[id_]
        try:
            newState, outputs, collector = self._transitions[oldState]
        except KeyError:
            raise NoTransition(state=oldState, symbol=self)
        self._machine._instanceStates[id_] = newState

        def dummyTracer(*args, **kwargs):
            """ This is a dummy traccer. """

        outTracer = dummyTracer
        inTracer = self._machine._instanceTracers.get(id_, dummyTracer)
        if inTracer:
            outTracer = inTracer(dict(oldState), self._name(), dict(newState))

        return outputs, outTracer or dummyTracer, collector

    def __get__(self, instance, type=None):
        """
        Return a function that takes no arguments and returns values returned
        by output functions produced by the given L{MethodicalInput} in
        C{instance}'s current state.
        """
        @preserveName(self._method)
        @wraps(self._method)
        def doInput(*args, **kwargs):
            # Check that function was called with the correct signature.
            self._method(instance, *args, **kwargs)

            outputs, outTracer, collector = self._transition(instance)
            for output in outputs:
                outTracer(output._name())
            results = [o(instance, *args, **kwargs) for o in outputs]
            return collector(results)

        return doInput


@attr.s(frozen=True)
class MethodicalOutput(object):
    """
    An output for a L{MethodicalMachine}.
    """
    _method = attr.ib()

    def _name(self):
        return self._method.__name__

    def __get__(self, oself, type=None):
        """
        Outputs are private, so raise an exception when we attempt to get one.
        """
        raise AttributeError(
            "{cls}.{method} is a state-machine output method; "
            "to produce this output, call an input method instead.".format(
                cls=type.__name__,
                method=self._name()
            )
        )

    def __call__(self, oself, *args, **kwargs):
        """
        Call the underlying method.
        """
        return self._method(oself, *args, **kwargs)


@attr.s(cmp=False, hash=False)
class MethodicalTracer(object):
    machine = attr.ib()

    def __get__(self, oself, type=None):

        def setTrace(tracer):
            self.machine._instanceTracers[id(oself)] = tracer

        return setTrace


counter = count()


def gensym():
    """
    Create a unique Python identifier.
    """
    return "_symbol_" + str(next(counter))


@attr.s
class MethodicalMachine(object):
    """
    A :class:`MethodicalMachine` is an interface to an `Automaton`
    that uses methods on a class.
    """

    _flags = attr.ib(default=attr.Factory(list))
    _hasTransitions = attr.ib(default=False)
    _initialState = attr.ib(default=attr.Factory(dict))
    _inputs = attr.ib(default=attr.Factory(list))
    _instanceStates = attr.ib()
    _instanceTracers = attr.ib(default=attr.Factory(dict))
    _serializationMap = attr.ib(default=attr.Factory(dict))
    _symbol = attr.ib(default=attr.Factory(gensym))

    def _getInitialState(self):
        return frozenset(self._initialState.items())

    @_instanceStates.default
    def _getInstanceStates(self):
        return defaultdict(self._getInitialState)

    @_keywordsOnly
    def flag(self, states, initial, serialized=None):
        """
        Declare a flag.

        This is a decorator for methods, but it will modify the method so as
        not to be callable any more.

        @param states: A list of the possible values for this flag.
        @type states: List[Hashable]

        @param initial: Which is the initial value for this flag?
        @type initial: L{bool}

        @param serialized: a serializable value to be used to represent this
            state to external systems.  This value should be hashable;
            L{unicode} is a good type to use.
        @type serialized: a hashable (comparable) value
        """
        if self._hasTransitions:
            raise RuntimeError('Flags may not be added after transitions.')
        if len(states) < 2:
            raise ValueError('Flags must have at least two states.')
        if initial not in states:
            raise ValueError('The initial state {} '
                             'must be in the states list {} '
                             'but was not found there.'
                             .format(repr(initial), repr(states)))

        def decorator(flagMethod):
            flag = MethodicalFlag(
                method=flagMethod,
                serialized=serialized,
                states=states,
            )
            self._flags.append(flag)
            self._initialState[flag._name()] = initial
            self._serializationMap[flag._name()] = flag._serializedName()
            return flag
        return decorator

    @_keywordsOnly
    def input(self):
        """
        Declare an input.

        This is a decorator for methods.
        """
        def decorator(inputMethod):
            input_ = MethodicalInput(machine=self,
                                   method=inputMethod,
                                   symbol=self._symbol)
            self._inputs.append(input_)
            return input_
        return decorator

    @_keywordsOnly
    def output(self):
        """
        Declare an output.

        This is a decorator for methods.

        This method will be called when the state machine transitions to this
        state as specified in the decorated `output` method.
        """
        def decorator(outputMethod):
            return MethodicalOutput(method=outputMethod)
        return decorator

    def _possibleStates(self):
        """
        Iterate over all possible flag combinations.

        :rtype: Iterator[frozenset]
        """
        flagNames = [f._name() for f in self._flags]
        flagStates = [f._states for f in self._flags]
        for combo in itertools.product(*flagStates):
            yield frozenset(zip(flagNames, combo))

    def _validateSignatures(self, input, outputs):
        """
        Check that all of the output signatures match the input signature.

        :param MethodicalInput input:
        :param Iterable[MethodicalOutput] outputs:
        :raises: TypeError if there is a miss match.
        """
        inputSpec = getArgsSpec(input._method)
        for output in outputs:
            outputSpec = getArgsSpec(output._method)
            if inputSpec != outputSpec:
                raise TypeError(
                    "method {input} signature {inputSignature} "
                    "does not match output {output} "
                    "signature {outputSignature}".format(
                        input=input._method.__name__,
                        output=output._method.__name__,
                        inputSignature=inputSpec,
                        outputSignature=outputSpec,
                    )
                )

    def _checkThatTransitionIsUnique(self, fromStates, input):
        """

        :param List[frozenset] fromStates: A list of all flag combinations,
            that input will potentially transition from.
        :param MethodicalInput input:
        :raises ValueError: If any of the from states are already registered.
        """
        for state in fromStates:
            if state in input._transitions:
                raise ValueError(
                    "already have transition from {} via {}"
                    .format(state, input._name())
                )

    def _validateState(self, state):
        """
        Check that `state` is a subset of a possible state for the machine.

        :param frozenset state:
        :raises ValueError: if `state` is not valid
        """
        for s in self._possibleStates():
            if state.issubset(s):
                return
        raise ValueError('{} is not a valid state.'.format(dict(state)))

    def transition(self, from_, to, input, outputs, collector=list):
        """
        Declare a state transition from one state to another
        when an input is called triggering certain outputs.

        If ``from_`` does not contain all the flags that exist for the machine,
        several transitions will be created,
        one for each permutation of the possible full states.

        :param dict from_: The state to transition from.
        :param dict to: The state to transition to.
        :param MethodicalInput input: The input that triggers the transition.
        :param List[MethodicalOutput] outputs: The outputs that are called
            when the transition occurs.
        :param Optional[Callable] collector: A function to collect
            the return values of all the outputs.
        """
        self._hasTransitions = True
        self._validateSignatures(input, outputs)
        fromSet = frozenset(from_.items())
        toSet = frozenset(to.items())
        self._validateState(fromSet)
        self._validateState(toSet)

        if set(to) != set(from_):
            raise ValueError('The flags in to {} '
                             'must be the same as the flags in from_ {}'
                             .format(list(to), list(from_)))

        fromStates = [s for s in self._possibleStates()
                      if s.issuperset(fromSet)]

        self._checkThatTransitionIsUnique(fromStates, input)

        toStates = []
        for state in fromStates:
            state = dict(state)
            state.update(to.items())
            toStates.append(frozenset(state.items()))

        for fromVariant, toVariant in zip(fromStates, toStates):
            input._transitions[fromVariant] = (toVariant, outputs, collector)

    def _serialize(self, state):
        """
        Convert an unserialized state into it's serialized representation.

        :param frozenset state: The instance of a class
            with a :py:class:`MethodicalMachine` attribute.
        :rtype: Dict[str, Any]
        :returns: The serialized state of `obj`.
        """
        mapping = self._serializationMap
        return {mapping[flagName]: value for flagName, value in state}

    @_keywordsOnly
    def serializer(self):
        """

        """
        def decorator(func):
            @wraps(func)
            def serialize(oself):
                state = self._instanceStates[id(oself)]
                return func(oself, self._serialize(state))
            return serialize
        return decorator

    def _unserialize(self, state):
        """
        Reconstruct the state of a mechanized object
        from it's serialized representation.

        :param Dict[str, Any] state: The state to reconstruct.
        :rtype: frozenset
        :returns: The internal state representation.
        """
        mapping = {val: key for key, val in self._serializationMap.items()}
        return frozenset((mapping[key], val) for key, val in state.items())

    @_keywordsOnly
    def unserializer(self):
        """

        """
        def decorator(func):
            @wraps(func)
            def unserialize(oself, *args, **kwargs):
                serializedState = func(oself, *args, **kwargs)
                state = self._unserialize(serializedState)
                self._instanceStates[id(oself)] = state
                return None  # it's on purpose
            return unserialize
        return decorator

    @property
    def _setTrace(self):
        return MethodicalTracer(self)

    def asDigraph(self):
        """
        Generate a L{graphviz.Digraph} that represents this machine's
        states and transitions.

        @return: L{graphviz.Digraph} object; for more information, please
            see the documentation for
            U{graphviz<https://graphviz.readthedocs.io/>}

        """
        from ._visualize import makeDigraph
        return makeDigraph(self)

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

    def _allTransitions(self):
        """
        Build an iterable of all transitions.

        :return:
        :rtype: Iterator[
            Tuple[dict, MethodicalInput, dict, List[MethodicalOutput]]
        ]
        """
        for input_ in self._inputs:
            for from_, (to, outputs, _) in input_._transitions.items():
                yield from_, input_, to, outputs
