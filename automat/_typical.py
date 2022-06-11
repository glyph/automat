from __future__ import annotations

from dataclasses import dataclass, field
from inspect import Signature, get_annotations, signature
from typing import (
    Any,
    Callable,
    Concatenate,
    Dict,
    Generic,
    List,
    Mapping,
    Optional,
    ParamSpec,
    Protocol,
    Sequence,
    Tuple,
    Type,
    TypeVar,
)

from ._core import Automaton, Transitioner


InputsProto = TypeVar("InputsProto", covariant=True)
UserStateType = object
StateCore = TypeVar("StateCore")
OutputResult = TypeVar("OutputResult")
SelfA = TypeVar("SelfA")
SelfB = TypeVar("SelfB")
R = TypeVar("R")
P = ParamSpec("P")


class ProtocolAtRuntime(Protocol[InputsProto]):
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
        expectedParams[each] for each in list(expectedParams.keys())[1:]
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
    self: ClassClusterInstance[InputsProto, StateCore],
    inputMethodName: Optional[str],
    a: Tuple[object, ...],
    kw: Dict[str, object],
) -> Tuple[Any, object]:
    """ """
    currentState = self._transitioner._state
    stateFactory = self._builder._stateFactories[currentState]
    if currentState in self._stateCluster:
        return stateFactory, self._stateCluster[currentState]
    stateObject = self._stateCluster[currentState] = _buildNewState(
        getattr(self._builder._stateProtocol, inputMethodName)
        if inputMethodName is not None
        else None,
        stateFactory,
        self._stateCore,
        a,
        kw,
        self._stateCluster,
    )
    if oldState is not None:
        if oldState != currentState:
            if not stateFactory.__persistState__:  # type: ignore
                del self._stateCluster[oldState]
    return stateFactory, stateObject


@dataclass
class ClassClusterInstance(Generic[InputsProto, StateCore]):
    """ """

    _builder: ClassClusterBuilder[InputsProto, StateCore]
    _stateCore: StateCore
    _transitioner: Transitioner
    _stateCluster: Dict[str, UserStateType] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """
        Pre-allocate the initial state object so we'll fail somewhere
        comprehensible in L{ClassClusterBuilder.build}.
        """
        _updateState(None, self, None, (), {})

    def __getattr__(self, inputMethodName: str) -> Callable[..., object]:
        # TODO: this could all be done ahead of time by building an actual type
        # object with methods populated, no need to dynamically (slowly) build
        # function objects on each method call
        def method(*a, **kw) -> object:
            # We enforce only-a-single-output.
            oldState = self._transitioner._state
            stateObject = self._stateCluster[oldState]
            [[outputMethodName], tracer] = self._transitioner.transition(
                inputMethodName
            )
            realMethod = getattr(stateObject, outputMethodName)
            result = realMethod(*a, **kw)
            _updateState(oldState, self, inputMethodName, a, kw)
            return result

        method.__name__ = inputMethodName
        return method


@dataclass
class ClassClusterBuilder(Generic[InputsProto, StateCore]):

    _stateProtocol: ProtocolAtRuntime[InputsProto]
    _buildCore: Callable[..., StateCore]
    _initalState: Type[UserStateType]
    _stateFactories: Dict[str, Callable[[StateCore], UserStateType]] = field(
        default_factory=dict
    )
    _automaton: Automaton = field(default_factory=Automaton)

    def build(self, *initArgs: object, **initKwargs) -> InputsProto:
        """
        Create an inputs proto
        """
        result = ClassClusterInstance(
            self,
            self._buildCore(*initArgs, **initKwargs),
            Transitioner(self._automaton, self._initalState.__name__),
        )
        return result  # type: ignore


OneInputType = TypeVar("OneInputType", bound=Callable[..., Any])
T = TypeVar("T")
InputCallable = TypeVar("InputCallable")
OutputCallable = TypeVar("OutputCallable")


@dataclass
class ClusterStateDecorator(Generic[InputsProto, StateCore]):
    """
    Decorator-based interface.
    """

    _stateProtocol: ProtocolAtRuntime[InputsProto]
    _buildCore: Callable[[], StateCore]
    _stateClasses: List[Type[object]] = field(default_factory=list)
    _builder: Optional[ClassClusterBuilder[InputsProto, StateCore]] = None

    def _finish(self, builder: ClassClusterBuilder[InputsProto, StateCore]) -> None:
        """
        Transfer state class declarations into underlying state machine.
        """
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
                builder._stateFactories[newStateType.__name__] = newStateType
                # todo: method & output ought to have matching signatures (modulo
                # 'self' of a different type)
                builder._automaton.addTransition(
                    stateClass.__name__,
                    method.__name__,
                    newStateType.__name__,
                    [output.__name__],
                )

    def build(self, *initArgs: object, **initKwargs) -> InputsProto:
        """
        Initialize the state transitions if necessary, then build.
        """
        if self._builder is None:
            self._builder = builder = ClassClusterBuilder[InputsProto, StateCore](
                self._stateProtocol, self._buildCore, self._stateClasses[0]
            )
            self._finish(builder)
        else:
            builder = self._builder
        return self._builder.build(*initArgs, **initKwargs)

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
        input: Callable[Concatenate[SelfA, P], R],
        enter: Optional[Callable[[], Type[object]]] = None,
    ) -> Callable[
        [Callable[Concatenate[SelfB, P], R]], Callable[Concatenate[SelfB, P], R]
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
        heat: int
        beans: Optional[object] = None

    CoffeeStateMachine = ClusterStateDecorator(
        CoffeeMachine, lambda: BrewerStateCore(0)
    )

    @CoffeeStateMachine.state()
    @dataclass
    class NoBeanHaver(object):
        core: BrewerStateCore

        def __post_init__(self) -> None:
            print("Constructed no-bean-haver.")

        @CoffeeStateMachine.handle(CoffeeMachine.brew_button)
        def no_beans(self) -> None:
            print("no beans, not heating")

        @CoffeeStateMachine.handle(CoffeeMachine.put_in_beans, enter=lambda: BeanHaver)
        def add_beans(self, beans) -> None:
            print("put in some beans", repr(beans))
            self.core.beans = beans

    @CoffeeStateMachine.state()
    @dataclass
    class BeanHaver:
        core: BrewerStateCore
        beans: str

        def __post_init__(self) -> None:
            print("constructed bean haver with", self.beans)

        @CoffeeStateMachine.handle(CoffeeMachine.brew_button, enter=lambda: NoBeanHaver)
        def heat_the_heating_element(self) -> None:
            self.core.heat += 1
            print("yay brewing:", repr(self.beans))

        @CoffeeStateMachine.handle(CoffeeMachine.put_in_beans, enter=lambda: BeanHaver)
        def too_many_beans(self, beans: object) -> None:
            print("beans overflowing:", repr(beans), self.beans)

    """
    Need a better example that has a start, handshake, and established state
    class, and the established state class can have a reference to an instance
    of the handshake state class, and can thereby access its state.
    """

    print("building...")
    x: CoffeeMachine = CoffeeStateMachine.build()
    print("built")
    x.brew_button()
    x.brew_button()
    x.put_in_beans("old beans")
    x.put_in_beans("oops too many beans")
    x.brew_button()
    x.brew_button()
    x.put_in_beans("new beans")
    x.brew_button()
