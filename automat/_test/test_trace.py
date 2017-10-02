from unittest import TestCase
from .._methodical import MethodicalMachine

class SampleObject(object):
    mm = MethodicalMachine()

    @mm.flag(states=['begin', 'middle', 'end'], initial='begin')
    def state(self):
        "state flag"

    @mm.input()
    def go1(self):
        "sample input"
    @mm.input()
    def go2(self):
        "sample input"
    @mm.input()
    def back(self):
        "sample input"

    @mm.output()
    def out(self):
        "sample output"

    # setTrace = mm._setTrace

    mm.transition({'state': 'begin'}, {'state': 'middle'}, go1, [out])
    mm.transition({'state': 'middle'}, {'state': 'end'}, go2, [out])
    mm.transition({'state': 'end'}, {'state': 'middle'}, back, [])
    mm.transition({'state': 'middle'}, {'state': 'begin'}, back, [])

class TraceTests(TestCase):
    def test_only_inputs(self):
        traces = []
        def tracer(old_state, input, new_state):
            traces.append((old_state, input, new_state))
            return None # "I only care about inputs, not outputs"
        s = SampleObject()
        s.setTrace(tracer)

        s.go1()
        self.assertEqual(
            traces,
            [
                ({'state': 'begin'}, "go1", {'state': 'middle'}),
            ],
        )

        s.go2()
        self.assertEqual(
            traces,
            [
                ({'state': 'begin'}, "go1", {'state': 'middle'}),
                ({'state': 'middle'}, "go2", {'state': 'end'}),
            ],
        )
        s.setTrace(None)
        s.back()
        self.assertEqual(
            traces,
            [
                ({'state': 'begin'}, "go1", {'state': 'middle'}),
                ({'state': 'middle'}, "go2", {'state': 'end'}),
            ],
        )
        s.go2()
        self.assertEqual(
            traces,
            [
                ({'state': 'begin'}, "go1", {'state': 'middle'}),
                ({'state': 'middle'}, "go2", {'state': 'end'}),
            ],
        )

    def test_inputs_and_outputs(self):
        traces = []
        def tracer(old_state, input, new_state):
            traces.append((old_state, input, new_state, None))
            def trace_outputs(output):
                traces.append((old_state, input, new_state, output))
            return trace_outputs # "I care about outputs too"
        s = SampleObject()
        s.setTrace(tracer)

        s.go1()
        self.assertEqual(
            traces,
            [
                ({'state': 'begin'}, "go1", {'state': 'middle'}, None),
                ({'state': 'begin'}, "go1", {'state': 'middle'}, "out"),
            ],
        )

        s.go2()
        self.assertEqual(
            traces,
            [
                ({'state': 'begin'}, "go1", {'state': 'middle'}, None),
                ({'state': 'begin'}, "go1", {'state': 'middle'}, "out"),
                ({'state': 'middle'}, "go2", {'state': 'end'}, None),
                ({'state': 'middle'}, "go2", {'state': 'end'}, "out"),
            ],
        )
        s.setTrace(None)
        s.back()
        self.assertEqual(
            traces,
            [
                ({'state': 'begin'}, "go1", {'state': 'middle'}, None),
                ({'state': 'begin'}, "go1", {'state': 'middle'}, "out"),
                ({'state': 'middle'}, "go2", {'state': 'end'}, None),
                ({'state': 'middle'}, "go2", {'state': 'end'}, "out"),
            ],
        )
        s.go2()
        self.assertEqual(
            traces,
            [
                ({'state': 'begin'}, "go1", {'state': 'middle'}, None),
                ({'state': 'begin'}, "go1", {'state': 'middle'}, "out"),
                ({'state': 'middle'}, "go2", {'state': 'end'}, None),
                ({'state': 'middle'}, "go2", {'state': 'end'}, "out"),
            ],
        )
