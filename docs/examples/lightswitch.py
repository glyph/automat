from operator import itemgetter

from automat import MethodicalMachine


class LightSwitch(object):
    machine = MethodicalMachine()

    @machine.flag(states=[True, False], initial=False,
                  serialized="Is the light switch on?")
    def state(self):
        "the switch state flag"

    @machine.input()
    def flip(self):
        "flip the switch"

    machine.transition(
        from_={'state': True},
        to={'state': False},
        input=flip,
        outputs=[],
    )
    machine.transition(
        from_={'state': False},
        to={'state': True},
        input=flip,
        outputs=[],
    )

    @machine.input()
    def query_power(self):
        "return True if powered, False otherwise"

    @machine.output()
    def _is_powered(self):
        return True

    @machine.output()
    def _not_powered(self):
        return False

    machine.transition(
        from_={'state': True},
        to={'state': True},
        input=query_power,
        outputs=[_is_powered],
        collector=itemgetter(0)
    )
    machine.transition(
        from_={'state': False},
        to={'state': False},
        input=query_power,
        outputs=[_not_powered],
        collector=itemgetter(0),
    )

    @machine.serializer()
    def save(self, state):
        return state

    @machine.unserializer()
    def _restore(self, blob):
        return blob

    @classmethod
    def from_blob(cls, blob):
        self = cls()
        self._restore(blob)
        return self


if __name__ == "__main__":
    l = LightSwitch()
    print(l.query_power())
