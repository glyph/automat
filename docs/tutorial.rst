********
Tutorial
********

.. note::

   Automat 24.8 is a *major* change to the public API - effectively a whole new
   library.  For ease of migration, the code and API documentation still
   contains ``MethodicalMachine``, effectively the previous version of the
   library.  However, for readability, the narrative documentation now *only*
   documents ``TypeMachineBuilder``.  If you need documentation for that
   earlier version, you can find it as v22.10.0 on readthedocs.

The Basics: a Garage Door Opener
================================


Describing the State Machine
----------------------------

Let's consider :ref:`the garage door example from the
introduction<Garage-Example>`.

Automat takes great care to present a state machine as a collection of regular
methods.  So we define what those methods *are* with a
:py:class:`typing.Protocol` that describes them.

.. literalinclude:: examples/garage_door.py
   :pyobject: GarageController

This protocol tells us that only 3 things can happen to our controller from the
outside world (its inputs): the user can push the button, the "door is all the
way up" sensor can emit a signal, or the "door is all the way down" sensor can
emit a signal.  So those are our inputs.

However, our state machine also needs to be able to *affect* things in the
world (its outputs). As we are writing a program in Python, these come in the
form of a Python object that can be shared between all the states that
implement our controller, and for this purpose we define a simple shared-data
class:

.. literalinclude:: examples/garage_door.py
   :pyobject: DoorDevices

Here we have a reference to a ``Motor`` that can open and close the door, and
an ``Alarm`` that can beep to alert people that the door is closing.

Next we need to combine those together, using a
:py:class:`automat.TypeMachineBuilder`.

.. literalinclude:: examples/garage_door.py
   :start-after: start building
   :end-before: build states

Next we have to define our states.  Let's start with four simple ones:

1. closed - the door is closed and idle
2. opening - the door is actively opening
3. opened - the door is open and idle
4. closing - the door is actively closing

.. literalinclude:: examples/garage_door.py
   :start-after: build states
   :end-before: end states

To describe the state machine, we define a series of transitions, using the
method ``.upon()``:

.. literalinclude:: examples/garage_door.py
   :start-after: build methods
   :end-before: end methods

Building and using the state machine
------------------------------------

Now that we have described all the inputs, states, and output behaviors, it's
time to actually build the state machine:

.. literalinclude:: examples/garage_door.py
   :start-after: do build
   :end-before: end building

The :py:meth:`automat.TypeMachineBuilder.build` method creates a callable that
takes an instance of its state core (``DoorDevices``) and returns an object
that conforms to its inputs protocol (``GarageController``).  We can then take
this ``machineFactory`` and call it, like so:

.. literalinclude:: examples/garage_door.py
   :start-after: do instantiate
   :end-before: end instantiate

Because we defined ``closed`` as our first state above, the machine begins in
that state by default.  So the first thing we'll do is to open the door:

.. literalinclude:: examples/garage_door.py
   :start-after: do open
   :end-before: end open

If we run this, we will then see some output, indicating that the motor is
running:

.. code-block::

   motor running up

If we press the button again, rather than silently double-starting the motor,
we will get an error, since we haven't yet defined a state transition for this
state yet.  The traceback looks like this:

.. code-block::

    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
        machine.pushButton()
      File ".../automat/_typed.py", line 419, in implementation
        [outputs, tracer] = transitioner.transition(methodInput)
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
      File ".../automat/_core.py", line 196, in transition
        outState, outputSymbols = self._automaton.outputForInput(
                                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
      File ".../automat/_core.py", line 169, in outputForInput
        raise NoTransition(state=inState, symbol=inputSymbol)
    automat._core.NoTransition: no transition for pushButton in TypedState(name='opening')

At first, this might seem like it's making more work for you.  If you don't
want to crash the code that calls your methods, you need to provide many more
implementations of the same method for each different state.  But, in this
case, by causing this exception *before* running any of your code, Automat is
protecting your internal state: although client code will get an exception, the
*internal* state of your garage door controller will remain consistent.

If you did not explicitly take a specific state into consideration while
implementing some behavior, that behavior will never be invoked.  Therefore, it
cannot do something potentially harmful like double-starting the motor.

If we trigger the open sensor so that the door completes its transition to the
'open' state, then push the button again, the buzzer will sound and the door
will descend:

.. literalinclude:: examples/garage_door.py
   :start-after: sensor and close
   :end-before: end close

.. code-block::

   motor stopped
   beep beep beep
   motor running down

Try these exercises to get to to know Automat a little bit better:

- When the button is pushed while the door is opening, the motor should stop,
  and if it's pressed again, the door should go in the reverse direction; for
  exmaple, if it's opening, it should pause and then close again, and if it's
  closing, it should pause and then open again.  Make it do this rather than
  raise an exception.
- Add a 'safety sensor' input, that refuses to close the door while it is
  tripped.

Taking, Storing, and Returning Data
-----------------------------------

Any method defined by the input protocol can take arguments and return values,
just like any Python method.  In order to facilitate this, all transition
behavior methods must be able to accept any signature that their input can.

To demonstrate this, let's add a feature to our door.  Instead of a single
button, let's add the ability to pair multiple remotes to open the door, so we
can note which remote was used in a security log.  For starters, we will need
to modify our ``pushButton`` method to accept a ``remoteID`` argument, which we
can print out.

.. literalinclude:: examples/garage_door_security.py
   :pyobject: GarageController.pushButton

If you're using ``mypy``, you will immediately see a type error when making
this change, as all the calls to ``<state>.upon(GarageController.pushButton)``
now complain something like this:

.. code-block::

   garage_door_security.py:75:2: error: Argument 1 to "__call__" of "TransitionRegistrar"
        has incompatible type "Callable[[GarageController, DoorDevices], None]";
        expected "Callable[[GarageController, DoorDevices, str], None]"  [arg-type]

The ``TransitionRegistrar`` object is the result of calling ``.to(...)``, so
what this is saying is that your function that is decorated with, say,
``@closed.upon(GarageController.pushButton).to(opening)``, takes your input
protocol and your shared core object (as all transition behavior functions
must), but does *not* take the ``str`` argument that ``pushButton`` takes.  To
fix it, we can add that parameter everywhere, and print it out, like so:

.. literalinclude:: examples/garage_door_security.py
   :pyobject: startOpening

Obviously, mypy will also complain that our test callers are missing the
``remoteID`` argument as well, so if we change them to pass along some value
like so:

.. literalinclude:: examples/garage_door_security.py
   :start-after: do open
   :end-before: end open

Then we will see it in our output:

.. code-block::

   opened by alice

Return values are treated in the same way as parameters.  If your input
protocol specifies a return type, then all behavior methods must also return
that type.  Your type checker will help ensure that these all line up for you
as well.

You can download the full examples here:

- :download:`examples/garage_door.py`
- :download:`examples/garage_door_security.py`

More Advanced Usage: a Membership Card Automat Restaurant
=========================================================

Setting Up the Example
----------------------

We will have to shift to a slightly more complex example to demonstrate
Automat's more sophisticated features.  Rather than opening the single door on
our garage, let's implement the payment machine for an Automat - a food vending
machine.

Our automat operates on a membership system.  You buy an AutoBux card, load it
up, and then once you are at the machine, you swipe your card, make a
selection, your account is debited, and your food is dispensed.

State-specific Data
-------------------

One of the coolest feature of Automat is not merely enforcing state
transitions, but ensuring that the right data is always available in the right
state.  For our membership-card example, will start in an "idle" state, but
when a customer swipes their card and starts to make their food selection, we
have now entered the "choosing" state, it is crucial that *if we are in the
choosing state, then we* **must** *know which customer's card we will charge*.

We set up the state machine in much the same way as before: a state core:

.. literalinclude:: examples/automat_card.py
   :pyobject: AutomatCore

And an inputs protocol:

.. literalinclude:: examples/automat_card.py
   :pyobject: Automat

It may jump out at you that the ``_dispenseFood`` method is private.  That's a
bit unusual for a ``Protocol``, which is usually used to describe a
publicly-facing API.  Indeed, you might even want a *second* ``Protocol`` to
hide this away from your public documentation.  But for Automat, this is
important because it's what lets us implement a *conditional state transition*,
something commonly associated with state-specific data.

We will get to that in a moment, but first, let's define that data.  We'll
begin with a function that, like transition behavior functions, takes our input
protocol and core type.  Its job will be to build our state-specific data for
the "choosing" state, i.e. payment details.  Entering this state requires an
``accountID`` as supplied by our ``swipeCard`` input, so we will require that
as a parameter as well:

.. literalinclude:: examples/automat_card.py
   :pyobject: rememberAccount

Next, let's actually build the machine.  We will use ``rememberAccount`` as the
second parameter to ``TypeMachineBuilder.state()``, which defines ``choosing``
as a data state:

.. literalinclude:: examples/automat_card.py
   :start-after: define machine
   :end-before: end define

.. note::

   Here, because swipeCard doesn't need any behavior and returns a static,
   immutable type (None), we define the transition with ``.returns(None)``
   rather than giving it a behavior function.  This is the same as using
   ``@idle.upon(Automat.swipeCard).to(choosing)`` as a decorator on an empty
   function, but a lot faster to type and to read.

The fact that ``choosing`` is a data state adds two new requirements to its
transitions:x

1. First, for every transition defined *to* the ``choosing`` state, the data
   factory function -- ``rememberAccount`` -- must be callable with whatever
   parameters defined in the input.  If you want to make a lenient data factory
   that supports multiple signatures, you can always add ``*args: object,
   **kwargs: object`` to its signature, but any parameters it requires (in this
   case, ``accountID``) *must* be present in any input protocol methods that
   transition *to* ``choosing`` so that they can be passed along to the
   factory.

2. Second, for every transition defined *from* the ``choosing`` state, behavior
   functions will accept an additional parameter, of the same type returned by
   their state-specific data factory function.  In other words, we will build a
   ``PaymentDetails`` object on every transition *to* ``choosing``, and then
   remember and pass that object to every behavior function as long as the
   machine remains in that state.

Conditional State Transitions
-----------------------------

Formally, in a deterministic finite-state automaton, an input in one state must
result in the same transition to the same output state.  When you define
transitions statically, Automat adheres to this rule.  However, in many
real-world cases, which state you end up in after a particular event depends on
things like the input data or internal state.  In this example, if the user's
AutoBux™ account balance is too low, then the food should not be dispensed; it
should prompt the user to make another selection.

Because it must be static, this means that the transition we will define from
the ``choosing`` state upon ``selectFood`` will actually be a ``.loop()`` -- in
other words, back to ``choosing`` -- rather than ``.to(idle)``.  Within the
behavior function of that transition, if we have determined that the user's
card has been charged properly, we will call *back* into the ``Automat``
protocol via the ``_dispenseFood`` private input, like so:

.. literalinclude:: examples/automat_card.py
   :pyobject: selected

And since we want *that* input to transition us back to ``idle`` once the food
has been dispensed, once again, we register a static transition, and this one's
behavior is much simpler:

.. literalinclude:: examples/automat_card.py
   :pyobject: doOpen

You can download the full example here:

- :download:`examples/automat_card.py`

Reentrancy
----------

Observant readers may have noticed a slightly odd detail in the previous
section.

If our ``selected`` behavior function can cause a transition to another state
before it's completed, but that other state's behaviors may require invariants
that are maintained by previous behavior (i.e. ``selected`` itself) having
completed, doesn't that create a paradox?  How can we just invoke
``inputs._dispenseFood`` and have it work?

In fact, you can't.  This is an unresolvable paradox, and automat does a little
trick to allow this convenient illusion, but it only works in some cases.

Problems that lend themselves to state machines often involve setting up state
to generate inputs back to the state machine in the future.  For example, in
the garage door example above, we implicitly registered sensors to call the
``openSensor`` and ``closeSensor`` methods.  A more complete implementation in
the behavior might need to set a timeout with an event loop, to automatically
close the door after a certain amount of time.  Being able to treat the state
machines inputs as regular bound methods that can be used in callbacks is
extremely convenient for this sort of thing.  For those use cases, there are no
particular limits on what can be called; once the behavior itself is finished
and it's no longer on the stack, the object will behave exactly as its
``Protocol`` describes.

One constraint is that any method you invoke in this way cannot return any
value except None.  This very simple machine, for example, that attempts to
invoke a behavior that returns an integer:

.. literalinclude:: examples/feedback_errors.py
   :start-after: #begin
   :end-before: #end

will result in a traceback like so:

.. code-block::

      File "feedback_errors.py", line 24, in behave
        print("computed:", inputs.compute())
                           ^^^^^^^^^^^^^^^^
      File ".../automat/_typed.py", line 406, in implementation
        raise RuntimeError(
    RuntimeError: attempting to reentrantly run Inputs.compute
        but it wants to return <class 'int'> not None

However, if instead of calling the method *immediately*, we save the method
away to invoke later, it works fine once the current behavior function has
completed:

.. literalinclude:: examples/feedback_order.py
   :start-after: begin computations
   :end-before: end computations

This simply prints ``3``, as expected.

But why is there a constraint on return type?  Surely a ``None``-returning
method with side effects depends on its internal state just as much as
something that returns a value?  Running it re-entrantly before finishing the
previous behavior would leave things in an invalid state, so how can it run at
all?

The magic that makes this work is that Automat automatically makes the
invocation *not reentrant*, by re-ordering it for you.  It can *re-order a
second behavior that returns None to run at the end of your current behavior*,
but it cannot steal a return value from the future, so it raises an exception
to avoid confusion.

But there is still the potentially confusing edge-case of re-ordering.  A
machine that contains these two behaviors:

.. literalinclude:: examples/feedback_debugging.py
   :pyobject: one
.. literalinclude:: examples/feedback_debugging.py
   :pyobject: two

will, when ``.behavior1()`` is invoked on it, print like so:

.. code-block::

   starting behavior 1
   ending behavior 1
   behavior 2

In general, this re-ordering *is* what you want idiomatically when working with
a state machine, but it is important to know that it can happen.  If you have
code that you do want to invoke side effects in a precise order, put it in a
function or into a method on your shared core.

How do I get the current state of a state machine?
==================================================

Don't do that.

One major reason for having a state machine is that you want the callers of the
state machine to just provide the appropriate input to the machine at the
appropriate time, and *not have to check themselves* what state the machine is
in.

The *whole point* of Automat is to never, ever write code that looks like this,
and places the burden on the caller:


.. code-block:: python

    if connectionMachine.state == "CONNECTED":
        connectionMachine.sendMessage()
    else:
        print("not connected")

Instead, just make your calling code do this:

.. code-block:: python

    connectionMachine.sendMessage()

and then change your state machine to look like this:

.. literalinclude:: examples/dont_get_state.py
   :start-after: begin salient
   :end-before: end salient

so that the responsibility for knowing which state the state machine is in
remains within the state machine itself.


If I can't get the state of the state machine, how can I save it to (a database, an API response, a file on disk...)
====================================================================================================================

On the serialization side, you can build inputs that return a type that every
state can respond to.  For example, here's a machine that maintains an ``int``
value in its core, and a ``str`` value in a piece of state-specific data.  This
really just works like implementing any other return value.

.. literalinclude:: examples/serialize_machine.py
   :start-after: begin salient
   :end-before: end salient

getting the data out then looks like this:

.. literalinclude:: examples/serialize_machine.py
   :start-after: build and serialize
   :end-before: end build

which produces:

.. code-block::

   (3, None)
   (3, DataObj(datum='hi'))

Future versions of automat may include some utility functionaity here to reduce
boilerplate, but no additional features are required to address this half of
the problem.

However, for *de*serialization, we do need the ability to start in a different
initial state.  For non-data states, it's simple enough; construct an
appropriate shared core, and just pass the state that you want; in our case,
``nodata``:

.. literalinclude:: examples/serialize_machine.py
   :pyobject: deserializeWithoutData

Finally, all we need to deserialize a state with state-specific data is to pass
a factory function which takes ``inputs, core`` as arguments, just like
behavior and data-factory functions.  Since we are skipping *directly* to the
data state, we will skip the data factory declared on the state itself, and
call this one:

.. literalinclude:: examples/serialize_machine.py
   :pyobject: deserialize

.. note::

   In this specific deserialization context, since the object isn't even really
   constructed yet, the ``inputs`` argument is in a *totally* invalid state and
   cannot be invoked reentrantly at all; any method will raise an exception if
   called during the duration of this special deserialization data factory.
   You can only use it to save it away on your state-specific data for future
   invocations once the state machine instance is built.

You can download the full example here:

- :download:`examples/serialize_machine.py`

And that's pretty much all you need to know in order to build type-safe state
machines with Automat!
