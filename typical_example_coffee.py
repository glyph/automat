from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated as A, Callable, Protocol, TypeVar, reveal_type

from automat import Enter, TypicalBuilder


class CoffeeMachine(Protocol):
    def put_in_beans(self, beans: str) -> None:
        "put in some beans"

    def brew_button(self) -> None:
        "press the brew button"


@dataclass
class BrewerStateCore(object):
    heat: int = 0


coffee = TypicalBuilder(CoffeeMachine, BrewerStateCore)


# if 0:
#     what = None
# else:
#     what = makeMakeBeanHaver


def makeBeanHaverMaker() -> type[BeanHaver]:
    return BeanHaver


T = TypeVar("T")


def make(x: Callable[[], type[T]]) -> Callable[[], type[T]]:
    """
    This is a workaround for a bug in older versions of mypy.
    """
    return x


@coffee.state()
class NoBeanHaver(object):
    @coffee.handle(CoffeeMachine.brew_button)
    def no_beans(self) -> None:
        print("no beans, not heating")

    @coffee.handle(CoffeeMachine.put_in_beans)
    def add_beans(self, beans: str) -> None:
        print("put in some beans", repr(beans))


@coffee.state(persist=False)
@dataclass
class BeanHaver:
    core: BrewerStateCore
    beans: str

    @coffee.handle(CoffeeMachine.brew_button)
    def heat_the_heating_element(self) -> A[None, Enter(NoBeanHaver)]:
        self.core.heat += 1
        print("yay brewing:", repr(self.beans))

    @coffee.handle(CoffeeMachine.put_in_beans)
    def too_many_beans(self, beans: object) -> None:
        print("beans overflowing:", repr(beans), self.beans)


NoBeanHaver.add_beans.enter(BeanHaver)

CoffeeStateMachine = coffee.buildClass()
print("Created:", CoffeeStateMachine)
# pass initial heat of 3 to BrewerStateCore
x: CoffeeMachine = CoffeeStateMachine(3)
print(x)
x.brew_button()
x.brew_button()
x.put_in_beans("old beans")
x.put_in_beans("oops too many beans")
x.brew_button()
x.brew_button()
x.put_in_beans("new beans")
x.brew_button()
