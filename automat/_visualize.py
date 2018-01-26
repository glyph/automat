from __future__ import print_function
import argparse
import sys

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


def _stateAsString(state):
    """
    Convert an internal state representation to a string.

    :param frozenset state:
    :return: The string representation of the state.
    :rtype: str
    """
    rows = []
    for name, value in state:
        rows.append('{} = {}'.format(name, value))
    string = '\n'.join(rows)
    if ':' in string:
        # graphviz splits names on colons
        # and treats the part after the colon as a port,
        # but it only does this for edges!
        # Colons in names will likely cause graphviz to crash,
        # and they will certainly cause the generated graph to be wrong.
        raise ValueError('":" is not a valid character for state names.')
    return string


def makeDigraph(machine):
    """
    Produce a L{graphviz.Digraph} object from a machine.

    :param MethodicalMachine machine: The machine to graph.
    """
    digraph = graphviz.Digraph(graph_attr={'pack': 'true',
                                           'dpi': '100'},
                               node_attr={'fontname': 'Menlo'},
                               edge_attr={'fontname': 'Menlo'})

    for state in machine._possibleStates():
        if state == machine._getInitialState():
            stateShape = "bold"
            fontName = "Menlo-Bold"
        else:
            stateShape = ""
            fontName = "Menlo"
        digraph.node(_stateAsString(state),
                     fontame=fontName,
                     shape="ellipse",
                     style=stateShape,
                     color="blue")

    for n, eachTransition in enumerate(machine._allTransitions()):
        from_, input_, to, outputs = eachTransition
        thisTransition = "t{}".format(n)

        port = "tableport"
        table = tableMaker(
            input_._method.__name__,
            [output._method.__name__ for output in outputs],
            port=port,
        )

        digraph.node(thisTransition,
                     label=_gvhtml(table),
                     margin="0.2",
                     shape="none")

        digraph.edge(_stateAsString(from_),
                     '{}:{}:w'.format(thisTransition, port),
                     arrowhead="none")
        digraph.edge('{}:{}:e'.format(thisTransition, port),
                     _stateAsString(to))

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
