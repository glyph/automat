from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    Any,
    Dict,
    Generic,
    TypeVar,
    Callable,
    Type,
    Sequence,
    Protocol,
    Optional,
)

from ._core import Transitioner, Automaton


InputsProto = TypeVar("InputsProto")
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
    _currentState: UserStateType
    _transitioner: Transitioner
    _stateCluster: Dict[str, UserStateType] = field(default_factory=dict)

    def __getattr__(self, inputMethodName: str) -> Callable[..., object]:
        def method(*a, **kw) -> object:
            # We enforce only-a-single-output.
            [[outputMethodName], tracer] = self._transitioner.transition(
                inputMethodName
            )
            currentState = self._currentState
            # TODO: state value
            realMethod = getattr(currentState, outputMethodName)
            result = realMethod(*a, **kw)
            self._currentState = self._builder._stateFactories[
                self._transitioner._state
            ](self._stateCore)
            return result

        method.__name__ = inputMethodName
        return method


@dataclass
class ClassClusterBuilder(Generic[InputsProto, StateCore]):

    buildCore: Callable[..., StateCore]
    initialStateFactory: Callable[[StateCore], UserStateType]

    _stateFactories: Dict[str, Callable[[StateCore], UserStateType]] = field(
        default_factory=dict
    )
    _automaton: Automaton = field(default_factory=Automaton)

    def build(self, *initArgs: object, **initKwargs) -> InputsProto:
        """
        Create an inputs proto
        """
        core = self.buildCore(*initArgs, **initKwargs)
        initialState = self.initialStateFactory(core)
        result = ClassClusterInstance(
            self,
            core,
            initialState,
            Transitioner(self._automaton, type(initialState).__name__),
        )
        return result  # type: ignore

    def state(self, stateType: Type[UserStateType]) -> ClusterStateBuilder:
        return ClusterStateBuilder(self, stateType)


@dataclass
class ClusterStateBuilder(object):
    _builder: ClusterStateBuilder
    _stateType: Type[UserStateType]

    def upon(
        self,
        method: InputMethod,
        output: InputMethod,
        enter: Optional[Type[UserStateType]] = None,
    ) -> ClusterStateBuilder:
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

    # @stateful(Button) # alternate?
    @dataclass
    class BeanHaver(object):
        core: BrewerStateCore

        # @handle(Button.put_in_beans, enter=lambda: NoBeanHaver) # alternate?
        def heat_the_heating_element(self) -> None:
            self.core.heat += 1
            print("yay brewing beans")

    # @stateful(Button) # alternate?
    @dataclass
    class NoBeanHaver(object):
        core: BrewerStateCore

        def no_beans(self) -> None:
            print("no beans, not heating")

        def add_beans(self, beans) -> None:
            print("put in some beans")
            self.core.beans = beans

    builder = ClassClusterBuilder[CoffeeMachine, BrewerStateCore](
        lambda: BrewerStateCore(0), BeanHaver
    )
    (
        builder.state(BeanHaver).upon(
            CoffeeMachine.brew_button,
            BeanHaver.heat_the_heating_element,
            NoBeanHaver,
        )
    )
    (
        builder.state(NoBeanHaver)
        .upon(
            CoffeeMachine.brew_button,
            NoBeanHaver.no_beans,
        )
        .upon(
            CoffeeMachine.put_in_beans,
            NoBeanHaver.add_beans,
            BeanHaver,
        )
    )
    x: CoffeeMachine = builder.build()
    x.brew_button()
    x.brew_button()
    x.put_in_beans("beans")
    x.brew_button()
    x.brew_button()
