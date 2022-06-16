from __future__ import print_function, annotations
import argparse
import sys

import attr
import graphviz

from ._discover import findMachines


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


@attr.frozen
class Transition:
     inStateInitial: bool
     outStateInitial: bool
     inState: str
     outState: str
     inputName: str
     outputs: Sequence[str]


def transitions(automaton, inputAsString=repr,
                outputAsString=repr,
                stateAsString=repr):
    for eachTransition in automaton.allTransitions():
        inState, inputSymbol, outState, outputSymbols = eachTransition
        inStateInitial = inState is automaton.initialState
        outStateInitial = outState is automaton.initialState
        inStateName = stateAsString(inState)
        outStateName = stateAsString(outState)
        inputName = inputAsString(inputSymbol)
        outputs = [outputAsString(outputSymbol) for outputSymbol in outputSymbols]
        yield Transition(
            inStateInitial=inStateInitial,
            outStateInitial=outStateInitial,
            inState=inState,
            outState=outState,
            inputName=inputName,
            outputs=outputs,
        )


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

    nodes = set()
    def maybeAddState(name, isInitial):
        if name in nodes:
            return
        if isInitial:
            stateShape = "bold"
            fontName = "Menlo-Bold"
        else:
            stateShape = ""
            fontName = "Menlo"
        digraph.node(name,
                     fontame=fontName,
                     shape="ellipse",
                     style=stateShape,
                     color="blue")
        nodes.add(name)
        
    for n, transition in enumerate(transitions(automaton, inputAsString,
                outputAsString,
                stateAsString)):
        maybeAddState(transition.inState, transition.inStateInitial)
        maybeAddState(transition.outState, transition.outStateInitial)
        thisTransition = "t{}".format(n)
        inputLabel = transition.inputName

        port = "tableport"
        table = tableMaker(inputLabel, transition.outputs,
                           port=port)

        digraph.node(thisTransition,
                     label=_gvhtml(table), margin="0.2", shape="none")

        digraph.edge(transition.inState,
                     '{}:{}:w'.format(thisTransition, port),
                     arrowhead="none")
        digraph.edge('{}:{}:e'.format(thisTransition, port),
                     transition.outState)

    return digraph


def tool(_progname=sys.argv[0],
         _argv=sys.argv[1:],
         _syspath=sys.path,
         _findMachines=findMachines,
         _print=print):
    """
    Entry point for command line utility.
    """

    DESCRIPTION = """
    Visualize automat.MethodicalMachines as graphviz graphs.
    """
    EPILOG = """
    You must have the graphviz tool suite installed.  Please visit
    http://www.graphviz.org for more information.
    """
    if _syspath[0]:
        _syspath.insert(0, '')
    argumentParser = argparse.ArgumentParser(
        prog=_progname,
        description=DESCRIPTION,
        epilog=EPILOG)
    argumentParser.add_argument('fqpn',
                                help="A Fully Qualified Path name"
                                " representing where to find machines.")
    argumentParser.add_argument('--quiet', '-q',
                                help="suppress output",
                                default=False,
                                action="store_true")
    argumentParser.add_argument('--dot-directory', '-d',
                                help="Where to write out .dot files.",
                                default=".automat_visualize")
    argumentParser.add_argument('--image-directory', '-i',
                                help="Where to write out image files.",
                                default=".automat_visualize")
    argumentParser.add_argument('--image-type', '-t',
                                help="The image format.",
                                choices=graphviz.FORMATS,
                                default='png')
    argumentParser.add_argument('--view', '-v',
                                help="View rendered graphs with"
                                " default image viewer",
                                default=False,
                                action="store_true")
    args = argumentParser.parse_args(_argv)

    explicitlySaveDot = (args.dot_directory
                         and (not args.image_directory
                              or args.image_directory != args.dot_directory))
    if args.quiet:
        def _print(*args):
            pass

    for fqpn, machine in _findMachines(args.fqpn):
        _print(fqpn, '...discovered')

        digraph = machine.asDigraph()

        if explicitlySaveDot:
            digraph.save(filename="{}.dot".format(fqpn),
                         directory=args.dot_directory)
            _print(fqpn, "...wrote dot into", args.dot_directory)

        if args.image_directory:
            deleteDot = not args.dot_directory or explicitlySaveDot
            digraph.format = args.image_type
            digraph.render(filename="{}.dot".format(fqpn),
                           directory=args.image_directory,
                           view=args.view,
                           cleanup=deleteDot)
            if deleteDot:
                msg = "...wrote image into"
            else:
                msg = "...wrote image and dot into"
            _print(fqpn, msg, args.image_directory)
