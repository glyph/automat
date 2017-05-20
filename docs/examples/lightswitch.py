from operator import itemgetter

from automat import MethodicalMachine


class LightSwitch(object):
    machine = MethodicalMachine()

    @machine.state(serialized="on")
    def on_state(self):
        "the switch is on"
    @machine.state(serialized="off", initial=True)
    def off_state(self):
        "the switch is off"
    @machine.input()
    def flip(self):
        "flip the switch"
    on_state.upon(flip, enter=off_state, outputs=[])
    off_state.upon(flip, enter=on_state, outputs=[])

    @machine.input()
    def query_power(self):
        "return True if powered, False otherwise"
    @machine.output()
    def _is_powered(self):
        return True

    @machine.output()
    def _not_powered(self):
        return False
    on_state.upon(query_power, enter=on_state, outputs=[_is_powered],
                  collector=itemgetter(0))
    off_state.upon(query_power, enter=off_state, outputs=[_not_powered],
                   collector=itemgetter(0))

    @machine.serializer()
    def save(self, state):
        return {"is-it-on": state}

    @machine.unserializer()
    def _restore(self, blob):
        return blob["is-it-on"]

    @classmethod
    def from_blob(cls, blob):
        self = cls()
        self._restore(blob)
        return self


if __name__ == "__main__":
    l = LightSwitch()
    print(l.query_power())
