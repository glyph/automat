from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    Any,
    Dict,
    List,
    Generic,
    TypeVar,
    Callable,
    Type,
    Sequence,
    Protocol,
    Optional,
)

from ._core import Transitioner, Automaton


InputsProto = TypeVar("InputsProto", covariant=True)
UserStateType = object
StateCore = TypeVar("StateCore")
OutputResult = TypeVar("OutputResult")


class HasName(Protocol):
    __name__: str


InputMethod = TypeVar("InputMethod", bound=HasName)


@dataclass
class ClassClusterInstance(Generic[InputsProto, StateCore]):
    """ """

    _builder: ClassClusterBuilder[InputsProto, StateCore]
    _stateCore: StateCore
    _transitioner: Transitioner
    _stateCluster: Dict[str, UserStateType] = field(default_factory=dict)

    def __getattr__(self, inputMethodName: str) -> Callable[..., object]:
        def method(*a, **kw) -> object:
            # We enforce only-a-single-output.
            currentState = self._transitioner._state
            [[outputMethodName], tracer] = self._transitioner.transition(
                inputMethodName
            )
            stateObject = self._stateCluster[currentState] = (
                self._stateCluster[currentState]
                if currentState in self._stateCluster
                else self._builder._stateFactories[currentState](self._stateCore)
            )
            realMethod = getattr(stateObject, outputMethodName)
            result = realMethod(*a, **kw)
            return result

        method.__name__ = inputMethodName
        return method


@dataclass
class ClassClusterBuilder(Generic[InputsProto, StateCore]):

    buildCore: Callable[..., StateCore]
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
            self.buildCore(*initArgs, **initKwargs),
            Transitioner(self._automaton, self._initalState.__name__),
        )
        return result  # type: ignore

    def state(self, stateType: Type[UserStateType]) -> BuildOneState:
        return BuildOneState(self, stateType)


@dataclass
class BuildOneState(Generic[InputsProto, StateCore]):
    _builder: ClassClusterBuilder[InputsProto, StateCore]
    _stateType: Type[UserStateType]

    def upon(
        self,
        method: InputMethod,
        output: InputMethod,
        enter: Optional[Type[UserStateType]] = None,
    ) -> BuildOneState:
        if enter is None:
            enter = self._stateType
        name = method.__name__
        self._builder._stateFactories[enter.__name__] = enter
        # todo: method & output ought to have matching signatures (modulo
        # 'self' of a different type)
        self._builder._automaton.addTransition(
            self._stateType.__name__,
            method.__name__,
            enter.__name__,
            [output.__name__],
        )
        return self


OneInputType = TypeVar("OneInputType", bound=Callable[..., Any])
T = TypeVar("T")
InputCallable = TypeVar("InputCallable")
OutputCallable = TypeVar("OutputCallable")


@dataclass
class ClusterStateDecorator(Generic[InputsProto, StateCore]):
    """
    Decorator-based interface.
    """

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
                self._buildCore, self._stateClasses[0]
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

    # TODO: when typing.Concatenate works on mypy, update this signature to
    # enforce the relationship between InputCallable and OutputCallable
    def handle(
        self,
        input: InputCallable,  # wants to be: Callable[Concatenate[SelfA, P], R]
        enter: Optional[Callable[[], Type[object]]] = None,
    ) -> Callable[
        [OutputCallable],  # wants to be: [Callable[Concatenate[SelfB, P], R]],
        OutputCallable,  # wants to be: Callable[Concatenate[SelfB, P], R]
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
        def put_in_beans(self, beans: object) -> None:
            "put in some beans"

        def brew_button(self) -> None:
            "press the brew button"

    @dataclass
    class BrewerStateCore(object):
        heat: int
        beans: Optional[object] = None

    CoffeeStateMachine: ClusterStateDecorator[
        CoffeeMachine, BrewerStateCore
    ] = ClusterStateDecorator(lambda: BrewerStateCore(0))

    @CoffeeStateMachine.state
    @dataclass
    class BeanHaver:
        core: BrewerStateCore

        @CoffeeStateMachine.handle(CoffeeMachine.brew_button, enter=lambda: NoBeanHaver)
        def heat_the_heating_element(self) -> None:
            self.core.heat += 1
            print("yay brewing beans")

        @CoffeeStateMachine.handle(CoffeeMachine.put_in_beans, enter=lambda: BeanHaver)
        def too_many_beans(self, beans: object) -> None:
            print("beans overflowing", beans)

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

    x: CoffeeMachine = CoffeeStateMachine.build()
    x.brew_button()
    x.brew_button()
    x.put_in_beans("beans")
    x.put_in_beans("oops too many beans")
    x.brew_button()
    x.brew_button()
