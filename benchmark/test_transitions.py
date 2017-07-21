# https://github.com/glyph/automat/issues/60

import automat


class Simple(object):
    """                                                                                                                     
    """
    _m = automat.MethodicalMachine()

    @_m.input()
    def one(self, data):
        "some input data"

    @_m.state(initial=True)
    def waiting(self):
        "patiently"

    @_m.output()
    def boom(self, data):
        pass

    waiting.upon(
        one,
        enter=waiting,
        outputs=[boom],
    )


def simple_one(machine, data):
    machine.one(data)


def test_simple_machine_transitions(benchmark):
    benchmark(simple_one, Simple(), 0)
