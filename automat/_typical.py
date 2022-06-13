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
    overload,
)

from ._core import Automaton, Transitioner


if sys.version_info >= (3, 10):
    from typing import Concatenate, ParamSpec

    P = ParamSpec("P")
    ThisInputArgs = ParamSpec("ThisInputArgs")
else:
    if not TYPE_CHECKING:
        P = TypeVar("P")


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
    pname: str,
    ptype: Type[object],
    transitionSignature: Signature | None,
    passedParams: Dict[str, object],
    stateCore: object,
    existingStateCluster: Mapping[str, object],
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
    # TODO: this needs to do some prechecking so we don't get runtime errors if
    # we can avoid it; specifically we can import-time check to see if there
    # are any transition paths into a state (B) that requires another state (A)
    # which do not pass through the required state (A), and checking the
    # matching name/type annotations on both the state core and the transition
    # methods.
    if transitionSignature is not None and pname in transitionSignature.parameters:
        transitionParam = transitionSignature.parameters[pname]
        # type-matching, check for Any, check for lacking annotation?
        if transitionParam.annotation == ptype:
            return passedParams[pname]
    if (it := getattr(stateCore, pname, None)) is not None:
        return it
    # TODO: better keys for existingStateCluster
    if ptype.__name__ in existingStateCluster:
        return existingStateCluster[ptype.__name__]
    if ptype is type(stateCore):
        return stateCore
    raise CouldNotFindAutoParam(f"Could not find parameter {pname} anywhere.")


def _buildNewState(
    transitionMethod: Any,
    stateFactory: Callable[..., Any],
    stateCore: object,
    args: Tuple[Any, ...],
    kwargs: Dict[str, object],
    existingStateCluster: Mapping[str, object],
) -> Any:
    """
    Create a new state object based on the existing state cluster.
    """
    k = {}
    transitionSignature = (
        signature(transitionMethod, eval_str=True, globals=globals())
        if transitionMethod is not None
        else None
    )
    passedParams: Dict[str, object] = (
        {}
        if transitionSignature is None
        else transitionSignature.bind(stateCore, *args, **kwargs).arguments
    )
    factorySignature = signature(stateFactory, eval_str=True)
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
        )

    return stateFactory(**k)


def _updateState(
    oldState: str | None,
    self: _TypicalInstance[InputsProto, StateCore],
    a: Tuple[object, ...],
    kw: Dict[str, object],
    stateFactories: Dict[str, Callable[..., UserStateType]],
    inputMethod: Callable[..., object] | None,
) -> Tuple[Any, object]:
    currentState = self._transitioner._state
    stateFactory = stateFactories[currentState]
    if currentState in self._stateCluster:
        stateObject = self._stateCluster[currentState]
    else:
        stateObject = self._stateCluster[currentState] = _buildNewState(
            inputMethod,
            stateFactory,
            self._stateCore,
            a,
            kw,
            self._stateCluster,
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
    stateProtocol: ProtocolAtRuntime[InputsProto],
) -> Callable[..., object]:
    inputMethodName = inputMethod.__name__

    @wraps(inputMethod)
    def method(self: _TypicalInstance[InputsProto, StateCore], *a, **kw) -> object:
        oldState = self._transitioner._state
        stateObject = self._stateCluster[oldState]
        [[outputMethodName], tracer] = self._transitioner.transition(inputMethodName)
        try:
            if outputMethodName is None:
                raise RuntimeError("unhandled state transition")
            else:
                realMethod = getattr(stateObject, outputMethodName)
                if realMethod.__automat_handler__[-1]:
                    a = (self, *a)
                result = realMethod(*a, **kw)
        finally:
            _updateState(oldState, self, a, kw, stateFactories, inputMethod)
        return result

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

    def __call__(self, *initArgs: P.args, **initKwargs: P.kwargs) -> InputsProto:
        """
        Instantiate the class asociated with this L{_TypicalClass}, producing
        something that appears to be an L{InputsProto}.
        """
        result = self._realSyntheticType(
            self._buildCore(*initArgs, **initKwargs),
            Transitioner(self._automaton, self._initialState.__name__),
        )
        _updateState(None, result, (), {}, self._stateFactories, None)
        return result  # type: ignore

    def __instancecheck__(self, other: object) -> bool:
        """
        A L{_TypicalInstance} is an instance of this L{_TypicalClass} it
        points to this object.
        """
        return isinstance(other, self._realSyntheticType)


class _TypicalErrorState:
    """
    This is the default error state.  It has no methods, and so you cannot
    recover by default.
    """

    __persistState__ = False


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
    _errorState: Type[object] = _TypicalErrorState
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
                stateFactories[stateClass.__name__] = stateClass
                for outputMethodName in dir(stateClass):
                    outputMethod = getattr(stateClass, outputMethodName)
                    ah = getattr(outputMethod, "__automat_handler__", None)
                    if ah is None:
                        continue
                    inputMethod: Callable[..., object]
                    enter: Optional[Callable[[], Type[object]]]
                    [inputMethod, enter, shouldPassSelf] = ah
                    newStateType = stateClass if enter is None else enter()
                    inputName = inputMethod.__name__
                    if inputName not in possibleInputs:
                        # TODO: arrogate these to the correct place.
                        continue
                    automaton.addTransition(
                        stateClass.__name__,
                        inputName,
                        newStateType.__name__,
                        [outputMethodName],
                    )
            for eachInput in possibleInputs:
                ns[eachInput] = _bindableTransitionMethod(
                    getattr(eachStateProtocol, eachInput),
                    stateFactories,
                    eachStateProtocol,
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
        enter: Optional[Callable[[], Type[object]]] = None,
    ) -> Callable[
        [Callable[Concatenate[SelfB, ThisInputArgs], R]],
        Callable[Concatenate[SelfB, ThisInputArgs], R],
    ]:
        """
        Define an input handler.
        """

        def decorator(c: OutputCallable) -> OutputCallable:
            c.__automat_handler__ = [input, enter, False]  # type: ignore
            return c

        return decorator

    def handle2(
        self,
        input: Callable[Concatenate[SelfA, ThisInputArgs], R],
        enter: Optional[Callable[[], Type[object]]] = None,
    ) -> Callable[
        [Callable[Concatenate[SelfB, InputsProto, ThisInputArgs], R]],
        Callable[Concatenate[SelfB, InputsProto, ThisInputArgs], R],
    ]:
        """
        Define an input handler.
        """

        def decorator(c: OutputCallable) -> OutputCallable:
            c.__automat_handler__ = [input, enter, True]  # type: ignore
            return c

        return decorator

    @overload
    def implement(
        self,
        input: Callable[Concatenate[SelfA, ThisInputArgs], R],
    ) -> Callable[
        [Callable[Concatenate[InputsProto, StateCore, ThisInputArgs], R]],
        Callable[Concatenate[InputsProto, StateCore, ThisInputArgs], R],
    ]:
        def decorator(f: OutputCallable) -> OutputCallable:
            self._defaultMethods[input.__name__] = (f, False)
            return f

        return decorator

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
