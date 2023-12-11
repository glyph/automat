# -*- test-case-name: automat._test.test_typical -*-
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from inspect import Parameter, Signature, signature
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Generic,
    Iterable,
    List,
    Mapping,
    NoReturn,
    Optional,
    Protocol,
    Sequence,
    TYPE_CHECKING,
    Tuple,
    Type,
    TypeVar,
    Union,
    get_type_hints,
    overload,
)

from ._core import Automaton, Transitioner


if TYPE_CHECKING:
    from typing import Concatenate, ParamSpec

    P = ParamSpec("P")
    ThisInputArgs = ParamSpec("ThisInputArgs")
else:
    # really just for lower python versions but it's simpler to just have it be
    # always at runtime
    P = TypeVar("P")
    ThisInputArgs = TypeVar("ThisInputArgs")
    Concatenate = Union


InputsProto = TypeVar("InputsProto", covariant=True)
PrivateProto = TypeVar("PrivateProto", covariant=True)
UserStateType = object
StateCore = TypeVar("StateCore")
OutputResult = TypeVar("OutputResult")
SelfA = TypeVar("SelfA")
SelfB = TypeVar("SelfB")
R = TypeVar("R")
T = TypeVar("T")
OutputCallable = TypeVar("OutputCallable", bound=Callable[..., Any])


@dataclass
class Enter:
    """
    Type annotation instruction to enter the next state.
    """

    state: Type[object]


class ProtocolAtRuntime(Protocol[InputsProto]):
    # __name__: str # https://github.com/python/mypy/issues/12976
    def __call__(self) -> InputsProto:
        ...


def _name(x: ProtocolAtRuntime[T]) -> str:
    return x.__name__  # type:ignore[attr-defined]


class CouldNotFindAutoParam(RuntimeError):
    """
    Raised when an automatically-populated parameter cannot be found.
    """


def _liveSignature(method: Callable[..., object]) -> Signature:
    """
    Get a signature with evaluated annotations.
    """
    # TODO: could this be replaced with get_type_hints?
    result = signature(method)
    for param in result.parameters.values():
        annotation = param.annotation
        if isinstance(annotation, str):
            scope = getattr(method, "__globals__", None)
            if scope is None:
                module = sys.modules[method.__module__]
                scope = module.__dict__
            param._annotation = eval(annotation, scope)  # type:ignore
    return result


class ValueBuilder(Protocol):
    def __call__(
        self,
        syntheticSelf: _TypicalInstance[InputsProto, StateCore],
        stateCore: object,
        existingStateCluster: Mapping[str, object],
    ) -> object:
        ...


class StateBuilder(Protocol):
    def __call__(
        self,
        syntheticSelf: _TypicalInstance[InputsProto, StateCore],
        stateCore: object,
        existingStateCluster: Mapping[str, object],
        args: Tuple[object, ...],
        kwargs: Dict[str, object],
    ) -> object:
        ...


def _getOtherState(name: str) -> ValueBuilder:
    def _otherState(
        syntheticSelf: _TypicalInstance[InputsProto, StateCore],
        stateCore: object,
        existingStateCluster: Mapping[str, object],
    ) -> object:
        return existingStateCluster[name]

    return _otherState


def _getCore(
    syntheticSelf: _TypicalInstance[InputsProto, StateCore],
    stateCore: object,
    existingStateCluster: Mapping[str, object],
) -> object:
    return stateCore


def _getCoreAttribute(attr: str) -> ValueBuilder:
    # TODO: automatically getting attributes from the core object rather than
    # the input signature is probably just a bad idea, way too much magic.  it
    # exists because the "state just constructed" hook of __post_init__ (or
    # __init__ sometimes I guess) is an awkward way of populating
    # derived-but-cached attributes.  But it would probably be best to just get
    # rid of these sematics and see if there's some explicit / opt-in version
    # of this we could add as an API later.
    def _coreGetter(
        syntheticSelf: _TypicalInstance[InputsProto, StateCore],
        stateCore: object,
        existingStateCluster: Mapping[str, object],
    ) -> object:
        return getattr(stateCore, attr)

    return _coreGetter


def _getSynthSelf(
    syntheticSelf: _TypicalInstance[InputsProto, StateCore],
    stateCore: object,
    existingStateCluster: Mapping[str, object],
) -> object:
    return syntheticSelf


def _stateBuilder(
    inputSignature: Signature,
    factorySignature: Signature,
    stateFactory: Callable[..., Any],
    suppliers: list[tuple[str, ValueBuilder]] = [],
):
    wanted = frozenset(factorySignature.parameters)

    def _(
        syntheticSelf: _TypicalInstance[InputsProto, StateCore],
        stateCore: object,
        existingStateCluster: Mapping[str, object],
        args: Tuple[object, ...],
        kwargs: Dict[str, object],
    ) -> object:
        boundArgs = inputSignature.bind(*args, **kwargs).arguments
        for unwanted in frozenset(boundArgs) - wanted:
            del boundArgs[unwanted]
        for (extraParamName, extraParamFactory) in suppliers:
            boundArgs[extraParamName] = extraParamFactory(
                syntheticSelf, stateCore, existingStateCluster
            )
        return stateFactory(**boundArgs)

    return _


def _valueSuppliers(
    factorySignature: Signature,
    transitionSignature: Signature,
    stateFactories: Dict[str, Callable[..., UserStateType]],
    stateCoreType: type[object],
    inputProtocols: frozenset[ProtocolAtRuntime[object]],
) -> Iterable[tuple[str, ValueBuilder]]:

    factoryNeeds = set(factorySignature.parameters)
    transitionSupplies = set(transitionSignature.parameters)
    notSuppliedParams = factoryNeeds - transitionSupplies

    for maybeTypeMismatch in factoryNeeds & transitionSupplies:
        if (
            transitionSignature.parameters[maybeTypeMismatch].annotation
            != factorySignature.parameters[maybeTypeMismatch].annotation
        ):
            if (
                factorySignature.parameters[maybeTypeMismatch].default
                == Parameter.empty
            ):
                notSuppliedParams.add(maybeTypeMismatch)

    for notSuppliedByTransitionName in notSuppliedParams:
        # These are the parameters we will need to supply.
        notSuppliedByTransition = factorySignature.parameters[
            notSuppliedByTransitionName
        ]
        parameterType = notSuppliedByTransition.annotation
        if parameterType.__name__ in stateFactories:
            yield (
                (
                    notSuppliedByTransitionName,
                    _getOtherState(parameterType.__name__),
                )
            )
        elif parameterType is stateCoreType:
            yield ((notSuppliedByTransitionName, _getCore))
        elif parameterType in inputProtocols:
            yield ((notSuppliedByTransitionName, _getSynthSelf))
        else:
            yield (
                (
                    notSuppliedByTransitionName,
                    _getCoreAttribute(notSuppliedByTransitionName),
                )
            )


def _buildStateBuilder(
    stateCoreType: type[object],
    stateFactory: Callable[..., Any],
    stateFactories: Dict[str, Callable[..., UserStateType]],
    transitionMethod: Any,
    inputProtocols: frozenset[ProtocolAtRuntime[object]],
) -> StateBuilder:
    """
    We want to build a factory that takes live args/kwargs and translates them
    into a state instance.

    @param transitionMethod: The method from the state-machine protocol, which
        documents its public parameters.
    """
    # TODO: benchmark the generated function, it's probably going to be pretty
    # performance sensitive, and probably switch over to codegen a-la attrs or
    # dataclassess since that will probably be faster.

    # the transition signature is empty / no arguments for the initial state
    # build
    transitionSignature = (
        _liveSignature(transitionMethod)
        if transitionMethod is not None
        else Signature([Parameter("self", Parameter.POSITIONAL_OR_KEYWORD)])
    )
    skipped = iter(transitionSignature.parameters.values())
    next(skipped)
    transitionSignature = transitionSignature.replace(parameters=list(skipped))
    factorySignature = _liveSignature(stateFactory)

    # All the parameters that the transition expects MUST be supplied by the
    # caller; they will be passed along to the factory.  The factory should not
    # supply them in other ways (default values will not be respected,
    # attributes won't be pulled from the state core, etc)

    suppliers = list(
        _valueSuppliers(
            factorySignature,
            transitionSignature,
            stateFactories,
            stateCoreType,
            inputProtocols,
        )
    )
    return _stateBuilder(transitionSignature, factorySignature, stateFactory, suppliers)


_baseMethods = set(dir(Protocol))


def _bindableInputMethod(
    inputMethod: Callable[..., object],
    inputProtocols: frozenset[ProtocolAtRuntime[object]],
    errorState: Callable[..., object],
) -> Callable[..., object]:
    """
    Create a bindable method (i.e. "function for use at class scope") to
    implement a I{state machine input} for the given L{_TypicalInstance}.
    """
    inputMethodName = inputMethod.__name__

    @wraps(inputMethod)
    def method(self: _TypicalInstance[InputsProto, StateCore], *a, **kw) -> object:
        oldStateName = self._transitioner._state
        oldStateObject = self._stateCluster[oldStateName]
        [[outputMethodName], tracer] = self._transitioner.transition(inputMethodName)
        newStateName = self._transitioner._state
        # here we need to invoke the output method
        if outputMethodName is None:
            self._stateCluster[newStateName] = errorState()
            raise RuntimeError(
                f"unhandled: state:{oldStateName} input:{inputMethodName}"
            )
        realMethod = getattr(oldStateObject, outputMethodName)
        stateBuilder: StateBuilder = realMethod.__stateBuilder__
        if newStateName not in self._stateCluster:
            newBuilt = self._stateCluster[newStateName] = stateBuilder(
                self, self._stateCore, self._stateCluster, a, kw
            )
        result = realMethod(*a, **kw)
        if (
            newStateName != oldStateName
            and not oldStateObject.__persistState__  # type:ignore[attr-defined]
        ):
            del self._stateCluster[oldStateName]
        return result

    return method


def _bindableCommonMethod(
    inputMethod: Callable[..., object],
    impl: Callable[..., object],
    includePrivate: bool,
) -> Callable[..., object]:
    """
    Create a bindable method (i.e. "function for use at class scope") to
    implement a I{common behavior} across all states of a given
    L{_TypicalInstance}.  Common methods appear to callers as methods.

    However, unlike transition methods which invoke state-specific behavior and
    may transition the state machine, common methods are just like regular
    methods you might define on a class, that are defined on the *outer* state machine.
    """

    @wraps(inputMethod)
    def method(self: _TypicalInstance[InputsProto, StateCore], *a, **kw) -> object:
        return impl(
            self, self._stateCore, *([self] if includePrivate else []), *a, **kw
        )

    return method


@dataclass
class _TypicalInstance(Generic[InputsProto, StateCore]):
    """
    Trivial superclass of state-cluster instances.  To application code,
    appears to be a provider of the C{InputsProto} protocol.  Methods are
    populated below by the logic in L{TypicalBuilder.buildClass}.
    """

    _stateCore: StateCore
    _transitioner: Transitioner
    _stateCluster: Dict[str, UserStateType] = field(default_factory=dict)


if TYPE_CHECKING:
    _typeish = type
else:
    _typeish = object


@dataclass
class _TypicalClass(
    Generic[InputsProto, StateCore, P],
    _typeish,  # Lie about being a type to work around
    # https://github.com/python/mypy/issues/12974
):
    """
    Class-ish object that supplies the implementation of the protocol described
    by L{InputsProto}.  This class's constructor mimics the signature of its
    state-builder function, and it will type-check accordingly.
    """

    _buildCore: Callable[P, StateCore]
    _initialState: Type[UserStateType]
    _automaton: Automaton
    _realSyntheticType: Type[_TypicalInstance]
    _inputProtocols: frozenset[ProtocolAtRuntime[object]]
    _initialStateBuilder: StateBuilder

    def __call__(self, *initArgs: P.args, **initKwargs: P.kwargs) -> InputsProto:
        """
        Instantiate the class asociated with this L{_TypicalClass}, producing
        something that appears to be an L{InputsProto}.
        """
        result = self._realSyntheticType(
            stateCore := self._buildCore(*initArgs, **initKwargs),
            Transitioner(self._automaton, self._initialState.__name__),
        )
        result._stateCluster[result._transitioner._state] = self._initialStateBuilder(
            result, stateCore, result._stateCluster, initArgs, initKwargs
        )
        return result  # type: ignore

    def __instancecheck__(self, other: object) -> bool:
        """
        A L{_TypicalInstance} is an instance of this L{_TypicalClass} it
        points to this object.
        """
        return isinstance(other, self._realSyntheticType)


class ErrorState:
    """
    This is the default error state.  It has no methods, and so you cannot
    recover by default.
    """

    __persistState__ = False


StateCoreContra = TypeVar("StateCoreContra", contravariant=True)


class NextStateFactory(Protocol[P, StateCoreContra]):
    def __call__(self, core: StateCoreContra, *args: P.args, **kw: P.kwargs) -> object:
        ...


SelfCon = TypeVar("SelfCon", contravariant=True)
InputsProtoInv = TypeVar("InputsProtoInv")
InputsProtoCon = TypeVar("InputsProtoCon", contravariant=True)
StateCoreCo = TypeVar("StateCoreCo", covariant=True)
StateCoreCon = TypeVar("StateCoreCon", contravariant=True)


AnyArgs = Union[
    Callable[Concatenate[StateCore, ThisInputArgs], object],
    Callable[Concatenate[StateCore, InputsProtoInv, ThisInputArgs], object],
    Callable[[StateCore, InputsProtoInv], object],
    Callable[[StateCore], object],
    Callable[[InputsProtoInv], object],
    Callable[[], object],
    None,
]


class Handler(Protocol[InputsProtoInv, SelfCon, ThisInputArgs, R, SelfA, StateCore]):
    __automat_handler__: tuple[
        Callable[Concatenate[SelfA, ThisInputArgs], R],
        Optional[AnyArgs[StateCore, ThisInputArgs, InputsProtoInv]],
    ]
    enter: Callable[
        [AnyArgs[StateCore, ThisInputArgs, InputsProtoInv]],
        None,
    ]

    def __call__(
        notself,
        /,
        self: SelfCon,
        *args: ThisInputArgs.args,
        **kwargs: ThisInputArgs.kwargs,
    ) -> R:
        ...

    @overload
    def __get__(self: T, instance: None, owner: Optional[Type[object]] = None) -> T:
        ...

    @overload
    def __get__(
        self, instance: object, owner: Optional[Type[object]] = None
    ) -> Callable[ThisInputArgs, R]:
        ...


AnyHandler = Handler[object, object, ..., object, object, object]


def _stateOutputs(
    stateClass: type[object],
) -> Iterable[tuple[str, str, str, Callable[..., object]]]:
    """
    Extract all input-handling methods from a given state class, returning a
    3-tuple of:

        1. the name of the I{output method} from the state class; i.e. the
           method that has actually been defined here.

        2. the name of the I{input method} from the inputs C{Protocol} on the
           state machine

        3. the name of the I{state builder} (as stored in
           L{_TypicalClass._stateBuilders}) to invoke, in order to build the
           state to transition to after the aforementioned state-machine input
           has been handled by the aforementioned state output method.
    """
    for outputMethodName in dir(stateClass):
        maybeOutputMethod = getattr(stateClass, outputMethodName)
        if not hasattr(maybeOutputMethod, "__automat_handler__"):
            continue
        outputMethod: AnyHandler = maybeOutputMethod
        [inputMethod, enterParameter] = outputMethod.__automat_handler__
        newStateFactory: Callable[..., object]
        if enterParameter is not None:
            newStateFactory = enterParameter
        else:
            newStateFactory = stateClass
        if sys.version_info >= (3, 9):
            for enterAnnotation in (
                each
                for each in getattr(
                    get_type_hints(outputMethod, include_extras=True).get("return"),
                    "__metadata__",
                    (),
                )
                if isinstance(each, Enter)
            ):
                newStateFactory = enterAnnotation.state
        yield outputMethodName, inputMethod.__name__, newStateFactory.__name__, newStateFactory


METADATA_DETRITUS = frozenset(["__dict__", "__weakref__", *dir(Protocol)])
"""
The process of defining a Protocol, or any Python class really, leaves behind
some extra junk which we cannot consider state-machine input methods.
"""


@dataclass
class TypicalBuilder(Generic[InputsProto, StateCore, P]):
    """
    Decorator-based interface.
    """

    _stateProtocol: ProtocolAtRuntime[InputsProto]
    _buildCore: Callable[P, StateCore]
    _privateProtocols: set[ProtocolAtRuntime[object]] = field(default_factory=set)

    # internal state
    _stateClasses: List[Type[object]] = field(default_factory=list)
    _built: bool = False
    _errorState: Type[object] = ErrorState
    _commonMethods: Dict[str, Tuple[Callable[..., Any], bool]] = field(
        default_factory=dict
    )

    def buildClass(self) -> _TypicalClass[InputsProto, StateCore, P]:
        """
        Transfer state class declarations into underlying state machine.
        """
        if self._built:
            raise RuntimeError("You can only build once, after that use the class")
        self._built = True
        automaton = Automaton()
        automaton.unhandledTransition(self._errorState.__name__, [None])
        stateFactories: Dict[str, Callable[..., UserStateType]] = {}
        allProtocols = frozenset([self._stateProtocol, *self._privateProtocols])

        # TODO: fix this to grab a return annotation or something
        stateCoreType: type[object] = self._buildCore  # type:ignore[assignment]

        ns: Dict[str, object] = {
            "_stateFactories": stateFactories,
        }
        buildAfterFactories = []
        for eachStateProtocol in [self._stateProtocol, *self._privateProtocols]:
            possibleInputs = frozenset(dir(eachStateProtocol)) - METADATA_DETRITUS
            for stateClass in [*self._stateClasses, self._errorState]:
                stateName = stateClass.__name__
                stateFactories[stateName] = stateClass
                for (
                    outputName,
                    inputName,
                    newStateName,
                    newStateFactory,
                ) in _stateOutputs(stateClass):
                    output = getattr(stateClass, outputName)
                    if inputName in possibleInputs:
                        automaton.addTransition(
                            stateName, inputName, newStateName, [outputName]
                        )
                        buildAfterFactories.append(
                            (output, stateCoreType, stateClass, newStateFactory)
                        )
            for eachInput in possibleInputs:
                ns[eachInput] = _bindableInputMethod(
                    getattr(eachStateProtocol, eachInput),
                    allProtocols,
                    self._errorState,
                )
        # stateFactories is built, now time to build the builders

        for (
            output,
            stateCoreType,
            stateClassName,
            newStateFactory,
        ) in buildAfterFactories:
            output.__stateBuilder__ = _buildStateBuilder(
                stateCoreType,
                newStateFactory,
                stateFactories,
                output,
                allProtocols,
            )

        # common methods are really only supposed to work for the main / public
        # interface, since the only reason to have them is public-facing.
        commonMethods = {
            commonMethodName: _bindableCommonMethod(
                getattr(self._stateProtocol, commonMethodName),
                commonImpl,
                includePrivate,
            )
            for commonMethodName, (
                commonImpl,
                includePrivate,
            ) in self._commonMethods.items()
        }
        # initial state builder has to take the arguments for the state core's
        # constructor.
        initialStateBuilder = _buildStateBuilder(
            stateCoreType,
            self._stateClasses[0],
            stateFactories,
            stateCoreType.__init__,
            allProtocols,
        )
        return _TypicalClass(
            self._buildCore,
            self._stateClasses[0],
            automaton,
            type(
                f"Machine<{_name(self._stateProtocol)}>",
                tuple([_TypicalInstance]),
                {
                    **ns,
                    **commonMethods,
                },
            ),
            allProtocols,
            initialStateBuilder,
        )

    def state(self, *, persist=True, error=False) -> Callable[[Type[T]], Type[T]]:
        """
        Decorate a state class to note that it's a state.

        @param persist: Whether to forget the given state when transitioning
            away from it.
        """

        def _saveStateClass(stateClass: Type[T]) -> Type[T]:
            stateClass.__persistState__ = persist  # type: ignore
            if error:
                self._errorState = stateClass
            else:
                self._stateClasses.append(stateClass)
            return stateClass

        return _saveStateClass

    def handle(
        self,
        input: Callable[Concatenate[SelfA, ThisInputArgs], R],
        enter: Optional[AnyArgs[StateCore, ThisInputArgs, InputsProto]] = None,
    ) -> Callable[
        [Callable[Concatenate[SelfB, ThisInputArgs], R]],
        Handler[InputsProto, SelfB, ThisInputArgs, R, SelfA, StateCore],
    ]:
        """
        Define an input handler.
        """

        def decorator(
            c: OutputCallable,
        ) -> Handler[InputsProto, SelfB, ThisInputArgs, R, SelfA, StateCore]:
            result: Handler[InputsProto, SelfB, ThisInputArgs, R, SelfA, StateCore]
            result = c  # type:ignore[assignment]
            result.__automat_handler__ = (input, enter)

            def doSetEnter(new: AnyArgs[StateCore, ThisInputArgs, InputsProto]) -> None:
                result.__automat_handler__ = (input, new)

            result.enter = doSetEnter
            return result

        return decorator

    @overload
    def common(
        self,
        input: Callable[Concatenate[SelfA, ThisInputArgs], R],
    ) -> Callable[
        [Callable[Concatenate[InputsProto, StateCore, ThisInputArgs], R]],
        Callable[Concatenate[InputsProto, StateCore, ThisInputArgs], R],
    ]:
        ...

    @overload
    def common(
        self,
        input: Callable[Concatenate[SelfA, ThisInputArgs], R],
        privateType: ProtocolAtRuntime[PrivateProto],
    ) -> Callable[
        [Callable[Concatenate[InputsProto, StateCore, PrivateProto, ThisInputArgs], R]],
        Callable[Concatenate[InputsProto, StateCore, PrivateProto, ThisInputArgs], R],
    ]:
        ...

    def common(
        self,
        input: Callable[Concatenate[SelfA, ThisInputArgs], R],
        privateType: ProtocolAtRuntime[PrivateProto] | None = None,
    ) -> (
        Callable[
            [
                Callable[
                    Concatenate[InputsProto, StateCore, PrivateProto, ThisInputArgs], R
                ]
            ],
            Callable[
                Concatenate[InputsProto, StateCore, PrivateProto, ThisInputArgs], R
            ],
        ]
        | Callable[
            [Callable[Concatenate[InputsProto, StateCore, ThisInputArgs], R]],
            Callable[Concatenate[InputsProto, StateCore, ThisInputArgs], R],
        ]
    ):
        """
        Implement one of the methods on the public inputs protocol.
        """
        if privateType is not None:
            self._privateProtocols.add(privateType)

        def decorator(f: OutputCallable) -> OutputCallable:
            self._commonMethods[input.__name__] = (f, privateType is not None)
            return f

        return decorator
