import graphviz


def _gvhtml(s):
    return '<{}>'.format(s)


def makeDigraph(automaton, inputAsString=repr,
                outputAsString=repr,
                stateAsString=repr):
    """
    Produce a C{graphviz.Digraph} object from automaton.

    """
    digraph = graphviz.Digraph(graph_attr={'pack': 'true',
                                           'dpi': '100'},
                               node_attr={'fontname': 'Menlo'},
                               edge_attr={'fontname': 'Menlo'})

    for state in automaton.states():
        if state is automaton.initialState:
            stateShape = "bold"
            fontName = "Menlo-Bold"
        else:
            stateShape = ""
            fontName = "Menlo"
        digraph.node(stateAsString(state),
                     fontame=fontName,
                     shape="ellipse",
                     style=stateShape,
                     color="blue")
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

        digraph.node(thisTransition,
                     label=_gvhtml(table), margin="0.2", shape="none")

        digraph.edge(stateAsString(inState),
                     '{}:tableport:w'.format(thisTransition),
                     arrowhead="none")
        digraph.edge('{}:tableport:e'.format(thisTransition),
                     stateAsString(outState))

    return digraph
