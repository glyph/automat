=========================================================================
Automat: Self-service finite-state machines for the programmer on the go.
=========================================================================

.. image:: https://upload.wikimedia.org/wikipedia/commons/d/db/Automat.jpg
   :width: 250
   :align: right

Automat is a library for concise, idiomatic Python expression
of finite-state automata
(particularly deterministic finite-state transducers).


Why use state machines?
=======================
Sometimes you have to create an object whose behavior varies with its state,
but still wishes to present a consistent interface to its callers.

For example, let's say you're writing the software for a coffee machine.
It has a lid that can be opened or closed, a chamber for water,
a chamber for coffee beans, and a button for "brew".

There are a number of possible states for the coffee machine.
It might or might not have water.
It might or might not have beans.
The lid might be open or closed.
The "brew" button should only actually attempt to brew coffee in one of these configurations,
and the "open lid" button should only work if the coffee is not, in fact, brewing.

With diligence and attention to detail,
you can implement this correctly using a collection of attributes on an object;
has_water, has_beans, is_lid_open and so on.
However, you have to keep all these attributes consistent.
As the coffee maker becomes more complex -
perhaps you add an additional chamber for flavorings so you can make hazelnut coffee,
for example - you have to keep adding more and more checks
and more and more reasoning about which combinations of states are allowed.

Rather than adding tedious 'if' checks to every single method
to make sure that each of these flags are exactly what you expect,
you can use a state machine to ensure that if your code runs at all,
it will be run with all the required values initialized,
because they have to be called in the order you declare them.

You can read more about state machines and their advantages for Python programmers
`in an excellent article by J.P. Calderone. <http://archive.is/oWpiI>`_



.. toctree::
   :maxdepth: 2
   :caption: Contents:

   about
   visualize
   api
   debugging
   typing
