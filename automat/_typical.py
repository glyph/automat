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


def _magicValueForParameter(
    parameterName: str,
    parameterType: Type[object],
    transitionSignature: Signature | None,
    passedParams: Dict[str, object],
    stateCore: object,
    existingStateCluster: Mapping[str, object],
    inputProtocols: set[ProtocolAtRuntime[object]],
    syntheticSelf: _TypicalInstance[InputsProto, StateCore],
) -> object:
    """
    When a state requires an attribute to be constructed, automatically
    determine where that attribute might need to come from, which may be one
    of:

        1. If a parameter of a matching name and type is passed in to the
           method causing the state transition, pass that along.

        2. If an attribute of a matching name and type is present on the state
           core object, pass it along.

        3. If it's the type of one of the other state objects, and it's already
           been populated,

        4. If it's the type of the state core, pass the state core.
    """
    # TODO: this needs to do some prechecking so we push as many errors to
    # import time as we possibly can; specifically we can import-time check to
    # see if there are any transition paths into a state (B) that requires
    # another state (A) which do not pass through the required state (A), and
    # checking the matching name/type annotations on both the state core and
    # the transition methods.
    if (
        transitionSignature is not None
        and parameterName in transitionSignature.parameters
    ):
        transitionParam = transitionSignature.parameters[parameterName]
        # type-matching, check for Any, check for lacking annotation?
        if transitionParam.annotation == parameterType:
            return passedParams[parameterName]
    if (it := getattr(stateCore, parameterName, None)) is not None:
        # This is probably way too much magic to do by default.  It might make
        # the most sense to just force everybody to wrap the whole state core
        # if they want to reference its state.
        return it
    # TODO: better keys for existingStateCluster
    if parameterType.__name__ in existingStateCluster:
        return existingStateCluster[parameterType.__name__]
    if parameterType is type(stateCore):
        return stateCore
    if parameterType in inputProtocols:
        return syntheticSelf
    raise CouldNotFindAutoParam(f"Could not find parameter {parameterName} anywhere.")


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


def _buildNewState(
    syntheticSelf: _TypicalInstance[InputsProto, StateCore],
    transitionMethod: Any,
    stateFactory: Callable[..., Any],
    stateCore: object,
    args: Tuple[Any, ...],
    kwargs: Dict[str, object],
    existingStateCluster: Mapping[str, object],
    inputProtocols: set[ProtocolAtRuntime[object]],
) -> Any:
    """
    Create a new state object based on the existing state cluster.
    """
    k = {}
    transitionSignature = (
        _liveSignature(transitionMethod) if transitionMethod is not None else None
    )
    passedParams: Dict[str, object] = (
        {}
        if transitionSignature is None
        else transitionSignature.bind(stateCore, *args, **kwargs).arguments
    )
    factorySignature = _liveSignature(stateFactory)
    expectedParams = factorySignature.parameters

    for extraParam in expectedParams.values():
        if extraParam.default is not Parameter.empty:
            continue
        paramName = extraParam.name
        k[paramName] = _magicValueForParameter(
            paramName,
            extraParam.annotation,
            transitionSignature,
            passedParams,
            stateCore,
            existingStateCluster,
            inputProtocols,
            syntheticSelf,
        )
    return stateFactory(**k)


def _updateState(
    self: _TypicalInstance[InputsProto, StateCore],
    oldState: str | None,
    a: Tuple[object, ...],
    kw: Dict[str, object],
    stateFactories: Dict[str, Callable[..., UserStateType]],
    inputMethod: Callable[..., object] | None,
    inputProtocols: set[ProtocolAtRuntime[object]],
) -> Tuple[Any, object]:
    currentState = self._transitioner._state
    stateFactory = stateFactories[currentState]
    if currentState in self._stateCluster:
        stateObject = self._stateCluster[currentState]
    else:
        stateObject = self._stateCluster[currentState] = _buildNewState(
            self,
            inputMethod,
            stateFactory,
            self._stateCore,
            a,
            kw,
            self._stateCluster,
            inputProtocols,
        )
    if oldState is not None:
        oldStateFactory = stateFactories[oldState]
        if oldState != currentState:
            shouldOldPersist: bool = oldStateFactory.__persistState__  # type: ignore
            if not shouldOldPersist:
                del self._stateCluster[oldState]
    return stateFactory, stateObject


_baseMethods = set(dir(Protocol))


def _bindableTransitionMethod(
    inputMethod: Callable[..., object],
    stateFactories: Dict[str, Callable[..., UserStateType]],
    inputProtocols: set[ProtocolAtRuntime[object]],
) -> Callable[..., object]:
    inputMethodName = inputMethod.__name__

    @wraps(inputMethod)
    def method(self: _TypicalInstance[InputsProto, StateCore], *a, **kw) -> object:
        oldState = self._transitioner._state
        stateObject = self._stateCluster[oldState]
        [[outputMethodName], tracer] = self._transitioner.transition(inputMethodName)
        _updateState(self, oldState, a, kw, stateFactories, inputMethod, inputProtocols)
        if outputMethodName is None:
            raise RuntimeError(f"unhandled: state:{oldState} input:{inputMethodName}")
        realMethod = getattr(stateObject, outputMethodName)
        return realMethod(*a, **kw)

    return method


def _bindableDefaultMethod(
    inputMethod: Callable[..., object],
    impl: Callable[..., object],
    includePrivate: bool,
) -> Callable[..., object]:
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
    _stateFactories: Dict[str, Callable[..., UserStateType]]
    _inputProtocols: set[ProtocolAtRuntime[object]]

    def __call__(self, *initArgs: P.args, **initKwargs: P.kwargs) -> InputsProto:
        """
        Instantiate the class asociated with this L{_TypicalClass}, producing
        something that appears to be an L{InputsProto}.
        """
        result = self._realSyntheticType(
            self._buildCore(*initArgs, **initKwargs),
            Transitioner(self._automaton, self._initialState.__name__),
        )
        _updateState(
            result, None, (), {}, self._stateFactories, None, self._inputProtocols
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


def _stateInputs(stateClass: type[object]) -> Iterable[tuple[str, str, str]]:
    """
    Extract all input-handling methods from a given state class, returning a
    3-tuple of:

        1. the name of the I{output method} from the state class; i.e. the
           method that has actually been defined here.

        2. the name of the I{input method} from the inputs C{Protocol} on the
           state machine

        3. the name of the I{state factory} (as stored in
           L{_TypicalClass._stateFactories}) to invoke, in order to build the
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
        yield outputMethodName, inputMethod.__name__, newStateFactory.__name__


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
    _defaultMethods: Dict[str, Tuple[Callable[..., Any], bool]] = field(
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

        ns: Dict[str, object] = {
            "_stateFactories": stateFactories,
        }
        for eachStateProtocol in [self._stateProtocol, *self._privateProtocols]:
            possibleInputs = set(dir(eachStateProtocol)) - set(
                ["__dict__", "__weakref__", *dir(Protocol)]
            )
            for stateClass in [*self._stateClasses, self._errorState]:
                stateName = stateClass.__name__
                stateFactories[stateName] = stateClass
                for (outputName, inputName, newStateName) in _stateInputs(stateClass):
                    if inputName in possibleInputs:
                        automaton.addTransition(
                            stateName, inputName, newStateName, [outputName]
                        )
            for eachInput in possibleInputs:
                ns[eachInput] = _bindableTransitionMethod(
                    getattr(eachStateProtocol, eachInput),
                    stateFactories,
                    set([self._stateProtocol, *self._privateProtocols]),
                )

        # default methods are really only supposed to work for the main /
        # public interface, since the only reason to have them is public-facing.
        defaultMethods = {
            defaultMethodName: _bindableDefaultMethod(
                getattr(self._stateProtocol, defaultMethodName),
                defaultImpl,
                includePrivate,
            )
            for defaultMethodName, (
                defaultImpl,
                includePrivate,
            ) in self._defaultMethods.items()
        }
        return _TypicalClass(
            self._buildCore,
            self._stateClasses[0],
            automaton,
            type(
                f"Machine<{_name(self._stateProtocol)}>",
                tuple([_TypicalInstance]),
                {
                    **ns,
                    **defaultMethods,
                },
            ),
            stateFactories,
            set([self._stateProtocol, *self._privateProtocols]),
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

            def doSetEnter(
                new: AnyArgs[StateCore, ThisInputArgs, InputsProto],
            ) -> None:
                result.__automat_handler__ = (input, new)

            result.enter = doSetEnter
            return result

        return decorator

    @overload
    def implement(
        self,
        input: Callable[Concatenate[SelfA, ThisInputArgs], R],
    ) -> Callable[
        [Callable[Concatenate[InputsProto, StateCore, ThisInputArgs], R]],
        Callable[Concatenate[InputsProto, StateCore, ThisInputArgs], R],
    ]:
        ...

    @overload
    def implement(
        self,
        input: Callable[Concatenate[SelfA, ThisInputArgs], R],
        privateType: ProtocolAtRuntime[PrivateProto],
    ) -> Callable[
        [Callable[Concatenate[InputsProto, StateCore, PrivateProto, ThisInputArgs], R]],
        Callable[Concatenate[InputsProto, StateCore, PrivateProto, ThisInputArgs], R],
    ]:
        ...

    def implement(
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
            self._defaultMethods[input.__name__] = (f, privateType is not None)
            return f

        return decorator
