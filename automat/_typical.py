from __future__ import annotations

import sys
from dataclasses import dataclass, field
from functools import wraps
from inspect import Signature, signature
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Generic,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    TYPE_CHECKING,
    Tuple,
    Type,
    TypeVar,
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
UserStateType = object
StateCore = TypeVar("StateCore")
OutputResult = TypeVar("OutputResult")
SelfA = TypeVar("SelfA")
SelfB = TypeVar("SelfB")
R = TypeVar("R")
T = TypeVar("T")
OutputCallable = TypeVar("OutputCallable")


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

    for extra_param in (
        expectedParams[each] for each in list(expectedParams.keys())[1:]  # skip `self`
    ):
        param_name = extra_param.name
        k[param_name] = _magicValueForParameter(
            param_name,
            extra_param.annotation,
            transitionSignature,
            passedParams,
            stateCore,
            existingStateCluster,
        )

    return stateFactory(stateCore, **k)


def _updateState(
    oldState: str | None,
    self: _TypicalInstance[InputsProto, StateCore],
    inputMethodName: Optional[str],
    a: Tuple[object, ...],
    kw: Dict[str, object],
    stateFactories: Dict[str, Callable[[StateCore], UserStateType]],
    stateProtocol: ProtocolAtRuntime[InputsProto],
) -> Tuple[Any, object]:
    currentState = self._transitioner._state
    stateFactory = stateFactories[currentState]
    if currentState in self._stateCluster:
        stateObject = self._stateCluster[currentState]
    else:
        stateObject = self._stateCluster[currentState] = _buildNewState(
            getattr(stateProtocol, inputMethodName)
            if inputMethodName is not None
            else None,
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
    inputMethod: Callable,
    stateFactories: Dict[str, Callable[[StateCore], UserStateType]],
    stateProtocol: ProtocolAtRuntime[InputsProto],
) -> Callable[..., object]:
    inputMethodName = inputMethod.__name__

    @wraps(inputMethod)
    def method(self: _TypicalInstance[InputsProto, StateCore], *a, **kw) -> object:
        oldState = self._transitioner._state
        stateObject = self._stateCluster[oldState]
        [[outputMethodName], tracer] = self._transitioner.transition(inputMethodName)
        realMethod = getattr(stateObject, outputMethodName)
        result = realMethod(*a, **kw)
        _updateState(
            oldState, self, inputMethodName, a, kw, stateFactories, stateProtocol
        )
        return result

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
    by L{InputsProto}.  This class's constructor mimics the signature of
    """

    _buildCore: Callable[P, StateCore]
    _initalState: Type[UserStateType]
    _automaton: Automaton
    _realSyntheticType: Type[_TypicalInstance]
    _stateFactories: Dict[str, Callable[[StateCore], UserStateType]]
    _stateProtocol: ProtocolAtRuntime[InputsProto]

    def __call__(self, *initArgs: P.args, **initKwargs: P.kwargs) -> InputsProto:
        """
        Create an inputs proto
        """
        result = self._realSyntheticType(
            self._buildCore(*initArgs, **initKwargs),
            Transitioner(self._automaton, self._initalState.__name__),
        )
        _updateState(
            None, result, None, (), {}, self._stateFactories, self._stateProtocol
        )
        return result  # type: ignore

    def __instancecheck__(self, other: object) -> bool:
        """
        A L{_TypicalInstance} is an instance of this L{_TypicalClass} it
        points to this object.
        """
        return isinstance(other, self._realSyntheticType)


@dataclass
class TypicalBuilder(Generic[InputsProto, StateCore, P]):
    """
    Decorator-based interface.
    """

    _stateProtocol: ProtocolAtRuntime[InputsProto]
    _buildCore: Callable[P, StateCore]
    _stateClasses: List[Type[object]] = field(default_factory=list)

    def buildClass(self) -> _TypicalClass[InputsProto, StateCore, P]:
        """
        Transfer state class declarations into underlying state machine.
        """
        automaton = Automaton()
        stateFactories: Dict[str, Callable[[StateCore], UserStateType]] = {}
        for stateClass in self._stateClasses:
            for x in dir(stateClass):
                output = getattr(stateClass, x)
                ah = getattr(output, "__automat_handler__", None)
                if ah is None:
                    continue
                method: Callable[..., object]
                enter: Optional[Callable[[], Type[object]]]
                [method, enter] = ah
                newStateType = stateClass if enter is None else enter()
                name = method.__name__
                stateFactories[newStateType.__name__] = newStateType
                # todo: method & output ought to have matching signatures (modulo
                # 'self' of a different type)
                automaton.addTransition(
                    stateClass.__name__,
                    method.__name__,
                    newStateType.__name__,
                    [output.__name__],
                )
        return _TypicalClass(
            self._buildCore,
            self._stateClasses[0],
            automaton,
            type(
                f"Machine<{self._stateProtocol.__name__}>",
                tuple([_TypicalInstance]),
                {
                    "_stateProtocol": self._stateProtocol,
                    "_stateFactories": stateFactories,
                    **{
                        inputMethodName: _bindableTransitionMethod(
                            getattr(self._stateProtocol, inputMethodName),
                            stateFactories,
                            self._stateProtocol,
                        )
                        for inputMethodName in (
                            set(dir(self._stateProtocol))
                            - set(["__dict__", "__weakref__", *dir(Protocol)])
                        )
                    },
                },
            ),
            stateFactories,
            self._stateProtocol,
        )

    def state(self, *, persist=True) -> Callable[[Type[T]], Type[T]]:
        """
        Decorate a state class to note that it's a state.

        @param persist: Whether to forget the given state when transitioning
            away from it.
        """

        def _saveStateClass(stateClass: Type[T]) -> Type[T]:
            stateClass.__persistState__ = persist  # type: ignore
            self._stateClasses.append(stateClass)
            return stateClass

        return _saveStateClass

    def initial(self, stateClass: Type[T]) -> Type[T]:
        """
        Decorate a state class to note that it's the initial state.
        """
        self._stateClasses.insert(0, stateClass)
        return stateClass

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


if __name__ == "__main__":

    class CoffeeMachine(Protocol):
        def put_in_beans(self, beans: str) -> None:
            "put in some beans"

        def brew_button(self) -> None:
            "press the brew button"

    @dataclass
    class BrewerStateCore(object):
        heat: int = 0
        beans: Optional[object] = None

    coffee = TypicalBuilder(CoffeeMachine, BrewerStateCore)

    @coffee.state()
    @dataclass
    class NoBeanHaver(object):
        core: BrewerStateCore

        @coffee.handle(CoffeeMachine.brew_button)
        def no_beans(self) -> None:
            print("no beans, not heating")

        @coffee.handle(CoffeeMachine.put_in_beans, enter=lambda: BeanHaver)
        def add_beans(self, beans) -> None:
            print("put in some beans", repr(beans))
            self.core.beans = beans

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
