# -*- test-case-name: automat._test.test_methodical -*-

import itertools
from collections import defaultdict
from functools import wraps
from itertools import count

from automat._core import NoTransition

try:
    # Python 3
    from inspect import getfullargspec as getArgsSpec
except ImportError:
    # Python 2
    from inspect import getargspec as getArgsSpec

import attr

from ._core import Transitioner
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


@attr.s(frozen=True)
class MethodicalFlag(object):
    """
    A state for a L{MethodicalMachine}.

    :ivar tuple states:
    """
    states = attr.ib(convert=tuple)
    method = attr.ib()
    serialized = attr.ib(repr=False)

    def _name(self):
        return self.method.__name__

    def _serialized(self):
        """
        Get the serialized reprisentation of the flag's name.

        :rtype: str
        """
        return self.serialized if self.serialized else self._name()


def _transitionerFromInstance(oself, symbol, automaton):
    """
    Get a L{Transitioner}

    :param oself: An instance of the class
        that the MethodicalMachine belongs to.
    :param str symbol:
    :param Automation automaton:
    :rtype: Transitioner
    """
    transitioner = getattr(oself, symbol, None)
    if transitioner is None:
        transitioner = Transitioner(
            automaton,
            automaton.initialState,
        )
        setattr(oself, symbol, transitioner)
    return transitioner


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
    method = attr.ib(validator=assertNoCode)  # type: Callable
    symbol = attr.ib(repr=False)
    _transitions = (  # type: Dict[State, Tuple[State, Outputs, Coloector]]
        attr.ib(default=attr.Factory(dict), repr=False)
    )

    def _transition(self, instance):
        """
        Transition the state of `instance`
        and get the corresponding outputs and collector.

        :type instance: Any
        :param instance: The instance on which the MethodicalInput was called.
        :rtype: Tuple[tuple, Callable]
        :return: The outputs, collector pair.
        """
        key = id(instance)
        old_state = self._machine._instance_states[key]
        try:
            new_state, outputs, collector = self._transitions[old_state]
        except KeyError:
            raise NoTransition(state=old_state, symbol=self)
        self._machine._instance_states[key] = new_state
        return outputs, collector

    def __get__(self, instance, type=None):
        """
        Return a function that takes no arguments and returns values returned
        by output functions produced by the given L{MethodicalInput} in
        C{instance}'s current state.
        """
        @preserveName(self.method)
        @wraps(self.method)
        def doInput(*args, **kwargs):
            self.method(instance, *args, **kwargs)
            outputs, collector = self._transition(instance)
            results = [o(instance, *args, **kwargs) for o in outputs]
            return collector(results)
        return doInput

    def _name(self):
        return self.method.__name__


@attr.s(frozen=True)
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

    def _name(self):
        return self.method.__name__

@attr.s(cmp=False, hash=False)
class MethodicalTracer(object):
    automaton = attr.ib(repr=False)
    symbol = attr.ib(repr=False)


    def __get__(self, oself, type=None):
        transitioner = _transitionerFromInstance(oself, self.symbol,
                                                 self.automaton)
        def setTrace(tracer):
            transitioner.setTrace(tracer)
        return setTrace



counter = count()
def gensym():
    """
    Create a unique Python identifier.
    """
    return "_symbol_" + str(next(counter))



class MethodicalMachine(object):
    """
    A :class:`MethodicalMachine` is an interface to an `Automaton`
    that uses methods on a class.
    """

    def __init__(self):
        self._flags = []
        self._symbol = gensym()
        self._initial_state = {}
        self._instance_states = defaultdict(self._get_initial_state)
        self._serialization_map = {}
        self._has_transitions = False

    @property
    def _unserialization_map(self):
        """ Mapping of serialized flag names to unserialized flag names. """
        return {val: key for key, val in self._serialization_map.items()}


    def _get_initial_state(self):
        return frozenset(self._initial_state.items())


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
    def flag(self, states, initial, serialized=None):
        """
        Declare a state, possibly an initial state or a terminal state.

        This is a decorator for methods, but it will modify the method so as
        not to be callable any more.

        :param initial: is this state the initial state?  Only one state on
            this :class:`automat.MethodicalMachine` may be an initial state; more than one is
            an error.

        @param serialized: a serializable value to be used to represent this
            state to external systems.  This value should be hashable;
            L{unicode} is a good type to use.
        @type serialized: a hashable (comparable) value
        :param states:
        """
        if self._has_transitions:
            raise RuntimeError('Flags may not be added after transitions.')

        def decorator(flagMethod):
            flag = MethodicalFlag(
                method=flagMethod,
                serialized=serialized,
                states=states,
            )
            self._flags.append(flag)
            self._initial_state[flag._name()] = initial
            self._serialization_map[flag._name()] = flag._serialized()
            return flag
        return decorator


    @_keywords_only
    def input(self):
        """
        Declare an input.

        This is a decorator for methods.
        """
        def decorator(inputMethod):
            return MethodicalInput(machine=self,
                                   method=inputMethod,
                                   symbol=self._symbol)
        return decorator


    @_keywords_only
    def output(self):
        """
        Declare an output.

        This is a decorator for methods.

        This method will be called when the state machine transitions to this
        state as specified in the decorated `output` method.
        """
        def decorator(outputMethod):
            return MethodicalOutput(machine=self, method=outputMethod)
        return decorator


    def _possible_states(self):
        """ Iterate over all possible flag combinations. """
        flag_names = [f._name() for f in self._flags]
        flag_states = [f.states for f in self._flags]
        for combo in itertools.product(*flag_states):
            yield frozenset(zip(flag_names, combo))

    def _validate_signatures(self, input, outputs):
        """
        Check that all of the output signatures match the input signature.

        :param MethodicalInput input:
        :param Iterable[MethodicalOutput] outputs:
        :raises: TypeError if there is a miss match.
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
                    )
                )

    def _check_that_transition_is_unique(self, from_states, input):
        """

        :param List[frozenset] from_states: A list of all flag combinations,
            that input will transition from.
        :param MethodicalInput input:
        :raises ValueError: If any of the from states are already registered.
        """
        for state in from_states:
            if state in input._transitions:
                raise ValueError(
                    "already have transition from {} via {}"
                    .format(state, input._name())
                )

    def transition(self, from_, to, input, outputs, collector=list):
        """
        Declare a state transition from one state to another
        when an input is called triggering certain outputs.

        :param dict from_: The state to transition from.
        :param dict to: The state to transition to.
        :param MethodicalInput input: The input that triggers the transition.
        :param List[MethodicalOutput] outputs: The outputs that are called
            when the transition occurs.
        :param Optional[Callable] collector: A function to collect
            the return values of all the outputs.
        """
        self._has_transitions = True

        self._validate_signatures(input, outputs)

        from_set = frozenset(from_.items())
        from_states = [s for s in self._possible_states()
                       if s.issuperset(from_set)]

        self._check_that_transition_is_unique(from_states, input)

        to_set = frozenset(to.items())
        for state in from_states:
            input._transitions[state] = (to_set, outputs, collector)

    def _serialize(self, state):
        """
        Convert an unserialized state into it's serialized representation.

        :param frozenset state: The instance of a class
            with a :py:class:`MethodicalMachine` attribute.
        :rtype: Dict[str, Any]
        :returns: The serialized state of `obj`.
        """
        mapping = self._serialization_map
        return {mapping[flag_name]: value for flag_name, value in state}


    @_keywords_only
    def serializer(self):
        """

        """
        def decorator(func):
            @wraps(func)
            def serialize(oself):
                state = self._instance_states[id(oself)]
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
        mapping = self._unserialization_map
        return frozenset((mapping[key], val) for key, val in state.items())

    @_keywords_only
    def unserializer(self):
        """

        """
        def decorator(func):
            @wraps(func)
            def unserialize(oself, *args, **kwargs):
                serialized_state = func(oself, *args, **kwargs)
                state = self._unserialize(serialized_state)
                self._instance_states[id(oself)] = state
                return None  # it's on purpose
            return unserialize
        return decorator

    # @property
    # def _setTrace(self):
    #     return MethodicalTracer(self._automaton, self._symbol)

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
