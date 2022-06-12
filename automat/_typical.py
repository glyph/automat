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
    __name__: str

    def __call__(self) -> InputsProto:
        ...


class HasName(Protocol):
    __name__: str


InputMethod = TypeVar("InputMethod", bound=HasName)


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
                    [inputMethod, enter] = ah
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
                f"Machine<{self._stateProtocol.__name__}>",
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
            c.__automat_handler__ = [input, enter]  # type: ignore
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


if __name__ == "__main__":

    class CoffeeMachine(Protocol):
        def put_in_beans(self, beans: str) -> None:
            "put in some beans"

        def brew_button(self) -> None:
            "press the brew button"

    @dataclass
    class BrewerStateCore(object):
        heat: int = 0

    coffee = TypicalBuilder(CoffeeMachine, BrewerStateCore)

    @coffee.state()
    class NoBeanHaver(object):
        @coffee.handle(CoffeeMachine.brew_button)
        def no_beans(self) -> None:
            print("no beans, not heating")

        @coffee.handle(CoffeeMachine.put_in_beans, enter=lambda: BeanHaver)
        def add_beans(self, beans) -> None:
            print("put in some beans", repr(beans))

    @coffee.state(persist=False)
    @dataclass
    class BeanHaver:
        core: BrewerStateCore
        beans: str

        @coffee.handle(CoffeeMachine.brew_button, enter=lambda: NoBeanHaver)
        def heat_the_heating_element(self) -> None:
            self.core.heat += 1
            print("yay brewing:", repr(self.beans))

        @coffee.handle(CoffeeMachine.put_in_beans, enter=lambda: BeanHaver)
        def too_many_beans(self, beans: object) -> None:
            print("beans overflowing:", repr(beans), self.beans)

    """
    Need a better example that has a start, handshake, and established state
    class, and the established state class can have a reference to an instance
    of the handshake state class, and can thereby access its state.
    """

    CoffeeStateMachine = coffee.buildClass()
    print("Created:", CoffeeStateMachine)
    x: CoffeeMachine = CoffeeStateMachine(3)
    print(isinstance(x, CoffeeStateMachine))
    x.brew_button()
    x.brew_button()
    x.put_in_beans("old beans")
    x.put_in_beans("oops too many beans")
    x.brew_button()
    x.brew_button()
    x.put_in_beans("new beans")
    x.brew_button()

    @dataclass
    class ControlPlane(object):
        _cb: Callable[[Callable[[Turnstile], None]], None]
        _pending_operation: str | None = None
        _money_counter: int = 0

        def __post_init__(self) -> None:
            # Hmm. Don't love this pattern for handing portions of the state
            # core back to the caller...
            @self._cb
            def complete_operation(t: Turnstile) -> None:
                o, self._pending_operation = self._pending_operation, None
                match o:
                    case "lock":
                        t.arm_lock_engaged()
                    case "unlock":
                        t.arm_lock_disengaged()
                        t.arm_rotated()
                    case None:
                        t.token_inserted()

        def lock(self) -> None:
            assert self._pending_operation is None
            self._pending_operation = "lock"

        def unlock(self) -> None:
            assert self._pending_operation is None
            self._pending_operation = "unlock"

        def reset(self) -> None:
            self._pending_operation = None

    class Turnstile(Protocol):
        def kick(self) -> None:
            ...

        def token_inserted(self) -> None:
            ...

        def arm_rotated(self) -> None:
            ...

        def arm_lock_engaged(self) -> None:
            ...

        def arm_lock_disengaged(self) -> None:
            ...

        def repair(self) -> None:
            ...

    turn = TypicalBuilder(Turnstile, ControlPlane)

    # You can use .implement to have wrapper implementations that apply in all
    # states.  Note that these methods will execute even in error states, so if
    # you need to bail out in error conditions make sure to call something on
    # your public-protocol first argument.

    @turn.implement(Turnstile.kick)
    def kick(t: Turnstile, p: ControlPlane) -> None:
        print("BANG")

    # You can also define *internal* protocols that your state classes can use.
    # Mypy will not make these methods visible to your callers, although they
    # are present at runtime.
    class InternalTurnstile(Protocol):
        def _add_token(self) -> int:
            pass

        def _enough_tokens(self) -> None:
            ...

    # If you ask for an internal interface, it will be passed along with the
    # public interface and state core.  Internal interfaces like this can be
    # used for "private" inputs; i.e. inputs to the state machine which should
    # only be generated when certain conditions are met, such as a counter
    # exceeding a threshold as shown here.
    @turn.implement(Turnstile.token_inserted, InternalTurnstile)
    def count_money(t: Turnstile, p: ControlPlane, private: InternalTurnstile) -> None:
        print("**plink**")
        if private._add_token() == 3:
            private._enough_tokens()

    @turn.state(persist=False)
    @dataclass
    class Unpaid(object):
        "Locked, not paid"
        plane: ControlPlane
        # persist=False above means this gets reset every time we exit this
        # state.
        money: int = 0

        @turn.handle(InternalTurnstile._add_token)
        def pay(self) -> int:
            self.money += 1
            return self.money

        @turn.handle(InternalTurnstile._enough_tokens, enter=lambda: Unlocking)
        def paid(self) -> None:
            print("requesting unlock")
            self.plane.unlock()

    @turn.state()
    class Unlocking(object):
        "Paid, not unlocked yet."

        @turn.handle(Turnstile.arm_lock_disengaged, enter=lambda: Paid)
        def ready(self) -> None:
            print("unlocked, waiting for customer to walk through")

    @turn.state()
    @dataclass
    class Paid(object):
        "Paid and unlocked."
        plane: ControlPlane

        @turn.handle(Turnstile.arm_rotated, enter=lambda: Locking)
        def relock(self) -> None:
            print("customer walked through, locking")
            self.plane.lock()

    @turn.state()
    class Locking(object):
        "Fare consumed, not yet locked."

        @turn.handle(Turnstile.arm_lock_engaged, enter=lambda: Unpaid)
        def engaged(self) -> None:
            print("finished locking")

    @turn.state(error=True)
    @dataclass
    class Broken(object):
        plane: ControlPlane

        @turn.handle(Turnstile.repair, enter=lambda: Unpaid)
        def repair(self) -> None:
            self.plane.reset()

    Turner = turn.buildClass()
    loops: List[Callable[[Turnstile], None]] = []
    t = Turner(loops.append)
    [loop] = loops
    print()
    print("turnstile example:")
    t.kick()
    for _ in range(10):
        loop(t)

    print("haywire messages from microcontroller")
    import traceback

    try:
        t.arm_rotated()
    except:
        traceback.print_exc()
        print("handled")
    try:
        t.arm_rotated()
    except:
        traceback.print_exc()
        print("still broken, fixing")
        t.repair()
    # fixed now
    for _ in range(10):
        loop(t)
