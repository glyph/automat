
from __future__ import unicode_literals

import os
import subprocess
from unittest import TestCase, skipIf

from .._methodical import MethodicalMachine

def isGraphvizInstalled():
    """
    Is graphviz installed?
    """
    r, w = os.pipe()
    os.close(w)
    try:
        return not subprocess.call("dot", stdin=r, shell=True)
    finally:
        os.close(r)



def sampleMachine():
    """
    Create a sample L{MethodicalMachine} with some sample states.
    """
    mm = MethodicalMachine()
    class SampleObject(object):
        @mm.state(initial=True)
        def begin(self):
            "initial state"
        @mm.state()
        def end(self):
            "end state"
        @mm.input()
        def go(self):
            "sample input"
        @mm.output()
        def out(self):
            "sample output"
        begin.upon(go, end, [out])
    so = SampleObject()
    so.go()
    return mm



@skipIf(not isGraphvizInstalled(), "Graphviz is not installed.")
class IntegrationTests(TestCase):
    """
    Tests which make sure Graphviz can understand the output produced by
    Automat.
    """

    def test_validGraphviz(self):
        """
        L{graphviz} emits valid graphviz data.
        """
        p = subprocess.Popen("dot", stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE)
        out, err = p.communicate("".join(sampleMachine().graphviz())
                                 .encode("utf-8"))
        self.assertEqual(p.returncode, 0)


class SpotChecks(TestCase):
    """
    Tests to make sure that the output contains salient features of the machine
    being generated.
    """

    def test_containsMachineFeatures(self):
        """
        The output of L{graphviz} should contain the names of the states,
        inputs, outputs in the state machine.
        """
        gvout = "".join(sampleMachine().graphviz())
        self.assertIn("begin", gvout)
        self.assertIn("end", gvout)
        self.assertIn("go", gvout)
        self.assertIn("out", gvout)
