
from __future__ import unicode_literals

def _gvquote(s):
    return '"{}"'.format(s.replace('"', r'\"'))

def _gvhtml(s):
    return '<{}>'.format(s)


def graphviz(automaton, inputAsString=repr,
             outputAsString=repr,
             stateAsString=repr):
    """
    Produce a graphviz dot file as an iterable of bytes.

    Use like so::

        with f as open('something', 'wb'):
            f.writelines(graphviz(automaton))
    """
    yield "digraph {\n"
    # yield "pad=0.25;\n"
    # yield 'splines="curved";\n'
    yield "graph[pack=true,dpi=100]\n"
    yield 'node[fontname="Menlo"]\n'
    yield 'edge[fontname="Menlo"]\n'

    for state in automaton.states():
        if state in automaton.initialStates():
            stateShape = "bold"
            fontName = "Menlo-Bold"
        else:
            stateShape = ""
            fontName = "Menlo"
        yield ('  {} [fontname="{}" shape="ellipse" style="{}" color="blue"]\n'
               .format(_gvquote(stateAsString(state)), fontName, stateShape))
    for n, eachTransition in enumerate(automaton.allTransitions()):
        inState, inputSymbol, outState, outputSymbols = eachTransition
        thisTransition = "t{}".format(n)
        inputLabel = inputAsString(inputSymbol)
        table = (
            '<table port="tableport">'
            '<tr><td color="purple" colspan="{}">'
            '<font face="menlo-italic">{}</font></td></tr>'
            '<tr>').format(len(outputSymbols), inputLabel)
        for eachOutput in outputSymbols:
            outputLabel = outputAsString(eachOutput)
            table += (
                '<td color="pink"><font point-size="9">{}</font></td>'
                .format(outputLabel))
        table += "</tr></table>"

        yield '    {} [shape=none margin=0.2 label={}]\n'.format(
            thisTransition, _gvhtml(table)
        )
        yield '    {} -> {}:tableport:w[arrowhead=none]\n'.format(
            _gvquote(stateAsString(inState)),
            thisTransition,
        )
        yield '    {}:tableport:e -> {}\n'.format(
            thisTransition,
            _gvquote(stateAsString(outState)),
        )
    yield "}\n"
