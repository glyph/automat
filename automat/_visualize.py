import graphviz


def _gvquote(s):
    return '"{}"'.format(s.replace('"', r'\"'))


def _gvhtml(s):
    return '<{}>'.format(s)


def elementMaker(name, *children, **attrs):
    """
    Construct a string from the HTML element description.
    """
    formattedAttrs = ' '.join('{}={}'.format(key, _gvquote(str(value)))
                              for key, value in sorted(attrs.items()))
    formattedChildren = ''.join(children)
    return u'<{name} {attrs}>{children}</{name}>'.format(
        name=name,
        attrs=formattedAttrs,
        children=formattedChildren)


def tableMaker(inputLabel, outputLabels, port, _E=elementMaker):
    """
    Construct an HTML table to label a state transition.
    """
    colspan = {}
    if outputLabels:
        colspan['colspan'] = str(len(outputLabels))

    inputLabelCell = _E("td",
                        _E("font",
                           inputLabel,
                           face="menlo-italic"),
                        color="purple",
                        port=port,
                        **colspan)

    pointSize = {"point-size": "9"}
    outputLabelCells = [_E("td",
                           _E("font",
                              outputLabel,
                              **pointSize),
                           color="pink")
                        for outputLabel in outputLabels]

    rows = [_E("tr", inputLabelCell)]

    if outputLabels:
        rows.append(_E("tr", *outputLabelCells))

    return _E("table", *rows)


def makeDigraph(automaton, inputAsString=repr,
                outputAsString=repr,
                stateAsString=repr):
    """
    Produce a L{graphviz.Digraph} object from an automaton.
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

        port = "tableport"
        table = tableMaker(inputLabel, [outputAsString(outputSymbol)
                                        for outputSymbol in outputSymbols],
                           port=port)

        digraph.node(thisTransition,
                     label=_gvhtml(table), margin="0.2", shape="none")

        digraph.edge(stateAsString(inState),
                     '{}:{}:w'.format(thisTransition, port),
                     arrowhead="none")
        digraph.edge('{}:{}:e'.format(thisTransition, port),
                     stateAsString(outState))

    return digraph
