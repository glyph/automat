

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
    for state in automaton.states():
        if state in automaton.initialStates():
            stateShape = "doubleoctagon"
        else:
            stateShape = "octagon"
        yield ('  {} [shape="{}"]\n'
               .format(_gvquote(stateAsString(state)), stateShape))
    for n, eachTransition in enumerate(automaton.allTransitions()):
        inState, inputSymbol, outState, outputSymbols = eachTransition
        thisTransition = "t{}".format(n)
        inputLabel = inputAsString(inputSymbol)
        table = ('<table port="tableport"><tr><td colspan="{}">{}</td></tr>'
                 '<tr>').format(len(outputSymbols), inputLabel)
        for eachOutput in outputSymbols:
            outputLabel = outputAsString(eachOutput)
            table += "<td>{}</td>".format(outputLabel)
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
