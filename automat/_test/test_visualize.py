import functools

import os
import subprocess
from unittest import TestCase, skipIf

from characteristic import attributes

from .._methodical import MethodicalMachine


def isGraphvizModuleInstalled():
    """
    Is the graphviz Python module installed?
    """
    try:
        __import__("graphviz")
    except ImportError:
        return False
    else:
        return True


def isGraphvizInstalled():
    """
    Are the graphviz tools installed?
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


@skipIf(not isGraphvizModuleInstalled(), "Graphviz module is not installed.")
class ElementMakerTests(TestCase):
    """
    Tests that ensure elementMaker generates correct HTML.
    """

    def setUp(self):
        from .._visualize import elementMaker
        self.elementMaker = elementMaker

    def test_sortsAttrs(self):
        """
        L{elementMaker} orders HTML attributes lexicographically.
        """
        expected = r'<div a="1" b="2" c="3"></div>'
        self.assertEqual(expected,
                         self.elementMaker("div",
                                           b='2',
                                           a='1',
                                           c='3'))

    def test_quotesAttrs(self):
        """
        L{elementMaker} quotes HTML attributes correctly.
        """
        expected = r'<div a="1" b="a \" quote" c="a string"></div>'
        self.assertEqual(expected,
                         self.elementMaker("div",
                                           b='a " quote',
                                           a=1,
                                           c="a string"))

    def test_noAttrs(self):
        """
        L{elementMaker} should render an element with no attributes.
        """
        expected = r'<div ></div>'
        self.assertEqual(expected, self.elementMaker("div"))


@attributes(['name', 'children', 'attrs'])
class HTMLElement(object):
    """Holds an HTML element, as created by elementMaker."""


def findElements(element, predicate):
    """
    Recursively collect all elements in an L{HTMLElement} tree that
    match the optional predicate.
    """
    if predicate(element):
        return [element]
    elif isLeaf(element):
        return []

    return [result
            for child in element.children
            for result in findElements(child, predicate)]


def isLeaf(element):
    """
    This HTML element is actually leaf node.
    """
    return not isinstance(element, HTMLElement)


@skipIf(not isGraphvizModuleInstalled(), "Graphviz module is not installed.")
class TableMakerTests(TestCase):
    """
    Tests that ensure tableMaker generates correctly structured tables.
    """

    def fakeElementMaker(self, name, *children, **attrs):
        return HTMLElement(name=name, children=children, attrs=attrs)

    def setUp(self):
        from .._visualize import tableMaker

        self.inputLabel = "input label"
        self.port = "the port"
        self.tableMaker = functools.partial(tableMaker,
                                            _E=self.fakeElementMaker)

    def test_inputLabelRow(self):
        """
        The table returned by L{tableMaker} always contains the input
        symbol label in its first row, and that row contains one cell
        with a port attribute set to the provided port.
        """

        def hasPort(element):
            return (not isLeaf(element)
                    and element.attrs.get("port") == self.port)

        for outputLabels in ([], ["an output label"]):
            table = self.tableMaker(self.inputLabel, outputLabels,
                                    port=self.port)
            self.assertGreater(len(table.children), 0)
            inputLabelRow = table.children[0]

            portCandidates = findElements(table, hasPort)

            self.assertEqual(len(portCandidates), 1)
            self.assertEqual(portCandidates[0].name, "td")
            self.assertEqual(findElements(inputLabelRow, isLeaf),
                             [self.inputLabel])

    def test_noOutputLabels(self):
        """
        L{tableMaker} does not add a colspan attribute to the input
        label's cell or a second row if there no output labels.
        """
        table = self.tableMaker("input label", (), port=self.port)
        self.assertEqual(len(table.children), 1)
        (inputLabelRow,) = table.children
        self.assertNotIn("colspan", inputLabelRow.attrs)

    def test_withOutputLabels(self):
        """
        L{tableMaker} adds a colspan attribute to the input label's cell
        equal to the number of output labels and a second row that
        contains the output labels.
        """
        table = self.tableMaker(self.inputLabel, ("output label 1",
                                                  "output label 2"),
                                port=self.port)

        self.assertEqual(len(table.children), 2)
        inputRow, outputRow = table.children

        def hasCorrectColspan(element):
            return (not isLeaf(element)
                    and element.name == "td"
                    and element.attrs.get('colspan') == "2")

        self.assertEqual(len(findElements(inputRow, hasCorrectColspan)),
                         1)
        self.assertEqual(findElements(outputRow, isLeaf), ["output label 1",
                                                           "output label 2"])


@skipIf(not isGraphvizModuleInstalled(), "Graphviz module is not installed.")
@skipIf(not isGraphvizInstalled(), "Graphviz tools are not installed.")
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
        out, err = p.communicate("".join(sampleMachine().asDigraph())
                                 .encode("utf-8"))
        self.assertEqual(p.returncode, 0)


@skipIf(not isGraphvizModuleInstalled(), "Graphviz module is not installed.")
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
        gvout = "".join(sampleMachine().asDigraph())
        self.assertIn("begin", gvout)
        self.assertIn("end", gvout)
        self.assertIn("go", gvout)
        self.assertIn("out", gvout)
