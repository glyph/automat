from __future__ import annotations

from dataclasses import dataclass, field
from inspect import get_annotations, signature
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


class HasName(Protocol):
    __name__: str


InputMethod = TypeVar("InputMethod", bound=HasName)


def _dobuild(
    transitionMethod: Any,
    stateFactory: Callable[..., Any],
    stateCore: object,
    args: Tuple[Any, ...],
    kwargs: Dict[str, object],
    existingStateCluster: Mapping[str, object],
) -> Any:
    """ """
    k = {}
    transitionSignature = signature(transitionMethod, eval_str=True, globals=globals())
    passedParams = transitionSignature.bind(stateCore, *args, **kwargs).arguments
    factorySignature = signature(stateFactory, eval_str=True)
    expectedParams = factorySignature.parameters
    for extra_param in (
        expectedParams[each] for each in list(expectedParams.keys())[1:]
    ):
        ptype = extra_param.annotation
        pname = extra_param.name

        def _() -> object:
            if pname in transitionSignature.parameters:
                transitionParam = transitionSignature.parameters[pname]
                # type-matching, check for Any, check for lacking annotation?
                if transitionParam.annotation == ptype:
                    return passedParams[pname]
            if (it := getattr(stateCore, pname, None)) is not None:
                return it
            # TODO: better keys for existingStateCluster
            if ptype.__name__ in existingStateCluster:
                return existingStateCluster[ptype.__name__]
            raise RuntimeError("oops no param", pname, ptype)

        k[pname] = _()
    return stateFactory(stateCore, **k)


@dataclass
class ClassClusterInstance(Generic[InputsProto, StateCore]):
    """ """

    _builder: ClassClusterBuilder[InputsProto, StateCore]
    _stateCore: StateCore
    _transitioner: Transitioner
    _stateCluster: Dict[str, UserStateType] = field(default_factory=dict)

    def __getattr__(self, inputMethodName: str) -> Callable[..., object]:
        # TODO: this could all be done ahead of time by building an actual type
        # object with methods populated, no need to dynamically (slowly) build
        # function objects on each method call
        def method(*a, **kw) -> object:
            # We enforce only-a-single-output.
            currentState = self._transitioner._state
            [[outputMethodName], tracer] = self._transitioner.transition(
                inputMethodName
            )
            stateObject = self._stateCluster[currentState] = (
                self._stateCluster[currentState]
                if currentState in self._stateCluster
                else _dobuild(
                    getattr(self._builder._stateProtocol, inputMethodName),
                    self._builder._stateFactories[currentState],
                    self._stateCore,
                    a,
                    kw,
                    self._stateCluster,
                )
            )
            realMethod = getattr(stateObject, outputMethodName)
            result = realMethod(*a, **kw)
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


class ProtocolAtRuntime(Protocol[InputsProto]):
    def __call__(self) -> InputsProto:
        ...


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

    def state(self, stateClass: Type[T]) -> Type[T]:
        """
        Decorate a state class to note that it's a state.
        """
        self._stateClasses.append(stateClass)
        return stateClass

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

    @CoffeeStateMachine.state
    @dataclass
    class NoBeanHaver(object):
        core: BrewerStateCore

        @CoffeeStateMachine.handle(CoffeeMachine.brew_button)
        def no_beans(self) -> None:
            print("no beans, not heating")

        @CoffeeStateMachine.handle(CoffeeMachine.put_in_beans, enter=lambda: BeanHaver)
        def add_beans(self, beans) -> None:
            print("put in some beans")
            self.core.beans = beans

    @CoffeeStateMachine.state
    @dataclass
    class BeanHaver:
        core: BrewerStateCore
        beans: str

        @CoffeeStateMachine.handle(CoffeeMachine.brew_button, enter=lambda: NoBeanHaver)
        def heat_the_heating_element(self) -> None:
            self.core.heat += 1
            print("yay brewing beans")

        @CoffeeStateMachine.handle(CoffeeMachine.put_in_beans, enter=lambda: BeanHaver)
        def too_many_beans(self, beans: object) -> None:
            print("beans overflowing:", repr(beans))

    """
    Need a better example that has a start, handshake, and established state
    class, and the established state class can have a reference to an instance
    of the handshake state class, and can thereby access its state.
    """

    x: CoffeeMachine = CoffeeStateMachine.build()
    x.brew_button()
    x.brew_button()
    x.put_in_beans("beans")
    x.put_in_beans("oops too many beans")
    x.brew_button()
    x.brew_button()
