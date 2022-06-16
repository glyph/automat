from dataclasses import dataclass
from typing import Protocol
from automat import TypicalBuilder


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
