from automat import MethodicalMachine


class CoffeeBrewer(object):
    _machine = MethodicalMachine()

    @_machine.input()
    def brew_button(self):
        "The user pressed the 'brew' button."

    @_machine.output()
    def _heat_the_heating_element(self):
        "Heat up the heating element, which should cause coffee to happen."
        # self._heating_element.turn_on()

    @_machine.flag(states=[True, False], initial=False)
    def beans(self):
        "Indicates whether or not you have beans."

    @_machine.input()
    def put_in_beans(self, beans):
        "The user put in some beans."

    @_machine.output()
    def _save_beans(self, beans):
        "The beans are now in the machine; save them."
        self._beans = beans

    @_machine.output()
    def _describe_coffee(self):
        return "A cup of coffee made with {}.".format(self._beans)

    _machine.transition(
        from_={'beans': False},
        to={'beans': True},
        input=put_in_beans,
        outputs=[_save_beans],
    )
    _machine.transition(
        from_={'beans': True},
        to={'beans': False},
        input=brew_button,
        outputs=[_heat_the_heating_element, _describe_coffee],
        collector=lambda iterable: list(iterable)[-1]
    )

cb = CoffeeBrewer()
cb.put_in_beans("real good beans")
print(cb.brew_button())
