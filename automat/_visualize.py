

def _gvquote(s):
    return '"{}"'.format(s.replace('"', r'\"'))

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
    yield "pack=true;\n"
    for state in automaton.states():
        if state in automaton.initialStates():
            stateShape = "doubleoctagon"
        else:
            stateShape = "octagon"
        yield ('  {} [shape="{}"];'
               .format(_gvquote(stateAsString(state)), stateShape))
    for n, eachTransition in enumerate(automaton.allTransitions()):
        inState, inputSymbol, outState, outputSymbols = eachTransition
        inputLabel = inputAsString(inputSymbol)
        thisInput = _gvquote("input({}):\n".format(n) + inputLabel)
        theseOutputs = ""
        for eachOutput in outputSymbols:
            outputLabel = outputAsString(eachOutput)
            anOutput = _gvquote("output({}):\n".format(n) +
                                outputLabel)
            yield ("  {} [shape=larrow margin=0.2 label={}];\n"
                   .format(anOutput, outputLabel)
            )
            theseOutputs += " -> {}".format(anOutput)
        yield '    {} [shape=rarrow margin=0.2 label={}];\n'.format(
            thisInput, _gvquote(inputLabel)
        )
        yield '    {} -> {} {} -> {} [color=grey];\n'.format(
            _gvquote(stateAsString(inState)),
            thisInput,
            theseOutputs,
            _gvquote(stateAsString(outState)),
        )
    yield "}\n"
