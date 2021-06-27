===========
Quick Start
===========
.. people like things that are quick and easy


What makes Automat different?
=============================
There are `dozens of libraries on PyPI implementing state machines
<https://pypi.org/search/?q=finite+state+machine>`_.
So it behooves me to say why yet another one would be a good idea.

Automat is designed around this principle:
while organizing your code around state machines is a good idea,
your callers don't, and shouldn't have to, care that you've done so.
In Python, the "input" to a stateful system is a method call;
the "output" may be a method call, if you need to invoke a side effect,
or a return value, if you are just performing a computation in memory.
Most other state-machine libraries require you to explicitly create an input object,
provide that object to a generic "input" method, and then receive results,
sometimes in terms of that library's interfaces and sometimes in terms of
classes you define yourself.

For example, a snippet of the coffee-machine example above might be implemented
as follows in naive Python:


.. code-block:: python

    class CoffeeMachine(object):
        def brew_button(self):
            if self.has_water and self.has_beans and not self.is_lid_open:
                self.heat_the_heating_element()
                # ...


With Automat, you'd create a class with a :py:class:`automat.MethodicalMachine` attribute:


.. code-block:: python

    from automat import MethodicalMachine

    class CoffeeBrewer(object):
        _machine = MethodicalMachine()


and then you would break the above logic into two pieces - the `brew_button`
*input*, declared like so:


.. code-block:: python

    class CoffeeBrewer(object):
        _machine = MethodicalMachine()

        @_machine.input()
        def brew_button(self):
            "The user pressed the 'brew' button."


It wouldn't do any good to declare a method *body* on this, however,
because input methods don't actually execute their bodies when called;
doing actual work is the *output*'s job:


.. code-block:: python

    class CoffeeBrewer(object):
        _machine = MethodicalMachine()

        # ...

        @_machine.output()
        def _heat_the_heating_element(self):
            "Heat up the heating element, which should cause coffee to happen."
            self._heating_element.turn_on()


As well as a couple of *states* - and for simplicity's sake let's say that the
only two states are `have_beans` and `dont_have_beans`:


.. code-block:: python

    class CoffeeBrewer(object):
        _machine = MethodicalMachine()

        # ...

        @_machine.state()
        def have_beans(self):
            "In this state, you have some beans."

        @_machine.state(initial=True)
        def dont_have_beans(self):
            "In this state, you don't have any beans."


`dont_have_beans` is the `initial` state
because `CoffeeBrewer` starts without beans in it.

(And another input to put some beans in:)

.. code-block:: python

    class CoffeeBrewer(object):
        _machine = MethodicalMachine()

        # ...

        @_machine.input()
        def put_in_beans(self):
            "The user put in some beans."


Finally, you hook everything together with the :py:meth:`.upon` method
of the functions decorated with `_machine.state`:

.. code-block:: python

    class CoffeeBrewer(object):
        _machine = MethodicalMachine()

        # ...

        # When we don't have beans, upon putting in beans, we will then have beans
        # (and produce no output)
        dont_have_beans.upon(put_in_beans, enter=have_beans, outputs=[])

        # When we have beans, upon pressing the brew button, we will then not have
        # beans any more (as they have been entered into the brewing chamber) and
        # our output will be heating the heating element.
        have_beans.upon(brew_button, enter=dont_have_beans,
                        outputs=[_heat_the_heating_element])


To *users* of this coffee machine class though, it still looks like a POPO
(Plain Old Python Object):


>>> coffee_machine = CoffeeMachine()
>>> coffee_machine.put_in_beans()
>>> coffee_machine.brew_button()


All of the *inputs* are provided by calling them like methods,
all of the *outputs* are automatically invoked when they are produced
according to the outputs specified to :py:meth:`automat.MethodicalState.upon`
and all of the states are simply opaque tokens -
although the fact that they're defined as methods like inputs and outputs
allows you to put docstrings on them easily to document them.


How do I get the current state of a state machine?
==================================================

Don't do that.

One major reason for having a state machine is that you want the callers of the
state machine to just provide the appropriate input to the machine at the
appropriate time, and *not have to check themselves* what state the machine is
in.  So if you are tempted to write some code like this:


.. code-block:: python

    if connection_state_machine.state == "CONNECTED":
        connection_state_machine.send_message()
    else:
        print("not connected")


Instead, just make your calling code do this:


.. code-block:: python

    connection_state_machine.send_message()


and then change your state machine to look like this:


.. code-block:: python

    class CoffeeBrewer(object):
        _machine = MethodicalMachine()

        # ...

        @_machine.state()
        def connected(self):
            "connected"
        @_machine.state()
        def not_connected(self):
            "not connected"
        @_machine.input()
        def send_message(self):
            "send a message"
        @_machine.output()
        def _actually_send_message(self):
            self._transport.send(b"message")
        @_machine.output()
        def _report_sending_failure(self):
            print("not connected")
        connected.upon(send_message, enter=connected, [_actually_send_message])
        not_connected.upon(send_message, enter=not_connected, [_report_sending_failure])


so that the responsibility for knowing which state the state machine is in
remains within the state machine itself.

Input for Inputs and Output for Outputs
=======================================

Quite often you want to be able to pass parameters to your methods,
as well as inspecting their results.
For example, when you brew the coffee,
you might expect a cup of coffee to result,
and you would like to see what kind of coffee it is.
And if you were to put delicious hand-roasted small-batch artisanal
beans into the machine, you would expect a *better* cup of coffee
than if you were to use mass-produced beans.
You would do this in plain old Python by adding a parameter,
so that's how you do it in Automat as well.


.. code-block:: python

    class CoffeeBrewer(object):
        _machine = MethodicalMachine()

        # ...

        @_machine.input()
        def put_in_beans(self, beans):
            "The user put in some beans."


However, one important difference here is that
*we can't add any implementation code to the input method*.
Inputs are purely a declaration of the interface;
the behavior must all come from outputs.
Therefore, the change in the state of the coffee machine
must be represented as an output.
We can add an output method like this:


.. code-block:: python

    class CoffeeBrewer(object):
        _machine = MethodicalMachine()

        # ...

        @_machine.output()
        def _save_beans(self, beans):
            "The beans are now in the machine; save them."
            self._beans = beans


and then connect it to the `put_in_beans` by changing the transition from
`dont_have_beans` to `have_beans` like so:


.. code-block:: python

    class CoffeeBrewer(object):
        _machine = MethodicalMachine()

        # ...

        dont_have_beans.upon(put_in_beans, enter=have_beans,
                             outputs=[_save_beans])


Now, when you call:


.. code-block:: python

    coffee_machine.put_in_beans("real good beans")


the machine will remember the beans for later.

So how do we get the beans back out again?
One of our outputs needs to have a return value.
It would make sense if our `brew_button` method
returned the cup of coffee that it made, so we should add an output.
So, in addition to heating the heating element,
let's add a return value that describes the coffee.
First a new output:


.. code-block:: python

    class CoffeeBrewer(object):
        _machine = MethodicalMachine()

        # ...

        @_machine.output()
        def _describe_coffee(self):
            return "A cup of coffee made with {}.".format(self._beans)


Note that we don't need to check first whether `self._beans` exists or not,
because we can only reach this output method if the state machine says we've
gone through a set of states that sets this attribute.

Now, we need to hook up `_describe_coffee` to the process of brewing,
so change the brewing transition to:


.. code-block:: python

    class CoffeeBrewer(object):
        _machine = MethodicalMachine()

        # ...

        have_beans.upon(brew_button, enter=dont_have_beans,
                        outputs=[_heat_the_heating_element,
                                 _describe_coffee])


Now, we can call it:


>>> coffee_machine.brew_button()
[None, 'A cup of coffee made with real good beans.']


Except... wait a second, what's that `None` doing there?

Since every input can produce multiple outputs, in automat,
the default return value from every input invocation is a `list`.
In this case, we have both `_heat_the_heating_element`
and `_describe_coffee` outputs, so we're seeing both of their return values.
However, this can be customized, with the `collector` argument to :py:meth:`.upon`;
the `collector` is a callable which takes an iterable of all the outputs'
return values and "collects" a single return value
to return to the caller of the state machine.

In this case, we only care about the last output,
so we can adjust the call to :py:meth:`.upon` like this:

.. code-block:: python

    class CoffeeBrewer(object):
        _machine = MethodicalMachine()

        # ...

        have_beans.upon(brew_button, enter=dont_have_beans,
                        outputs=[_heat_the_heating_element,
                                 _describe_coffee],
                        collector=lambda iterable: list(iterable)[-1]
        )


And now, we'll get just the return value we want:


>>> coffee_machine.brew_button()
'A cup of coffee made with real good beans.'


If I can't get the state of the state machine, how can I save it to (a database, an API response, a file on disk...)
====================================================================================================================
There are APIs for serializing the state machine.

First, you have to decide on a persistent representation of each state,
via the `serialized=` argument to the `MethodicalMachine.state()` decorator.

Let's take this very simple "light switch" state machine,
which can be on or off, and flipped to reverse its state:


.. code-block:: python

    class LightSwitch(object):
        _machine = MethodicalMachine()

        @_machine.state(serialized="on")
        def on_state(self):
            "the switch is on"

        @_machine.state(serialized="off", initial=True)
        def off_state(self):
            "the switch is off"

        @_machine.input()
        def flip(self):
            "flip the switch"

        on_state.upon(flip, enter=off_state, outputs=[])
        off_state.upon(flip, enter=on_state, outputs=[])


In this case, we've chosen a serialized representation for each state
via the `serialized` argument.
The on state is represented by the string `"on"`,
and the off state is represented by the string `"off"`.

Now, let's just add an input that lets us tell if the switch is on or not.


.. code-block:: python

    from operator import itemgetter

    first = itemgetter(0)

    class LightSwitch(object):
        _machine = MethodicalMachine()

        # ...

        @_machine.input()
        def query_power(self):
            "return True if powered, False otherwise"

        @_machine.output()
        def _is_powered(self):
            return True

        @_machine.output()
        def _not_powered(self):
            return False

        on_state.upon(
            query_power, enter=on_state, outputs=[_is_powered], collector=first
        )
        off_state.upon(
            query_power, enter=off_state, outputs=[_not_powered], collector=first
        )


To save the state, we have the `MethodicalMachine.serializer()` method.
A method decorated with `@serializer()` gets an extra argument injected
at the beginning of its argument list: the serialized identifier for the state.
In this case, either `"on"` or `"off"`.
Since state machine output methods can also affect other state on the object,
a serializer method is expected to return *all* relevant state for serialization.

For our simple light switch, such a method might look like this:

.. code-block:: python

    class LightSwitch(object):
        _machine = MethodicalMachine()

        # ...

        @_machine.serializer()
        def save(self, state):
            return {"is-it-on": state}


Serializers can be public methods, and they can return whatever you like.
If necessary, you can have different serializers -
just multiple methods decorated with `@_machine.serializer()` -
for different formats;
return one data-structure for JSON, one for XML, one for a database row, and so on.

When it comes time to unserialize, though, you generally want a private method,
because an unserializer has to take a not-fully-initialized instance
and populate it with state.
It is expected to *return* the serialized machine state token
that was passed to the serializer, but it can take whatever arguments you like.
Of course, in order to return that,
it probably has to take it somewhere in its arguments,
so it will generally take whatever a paired serializer has returned as an argument.

So our unserializer would look like this:


.. code-block:: python

    class LightSwitch(object):
        _machine = MethodicalMachine()

        # ...

        @_machine.unserializer()
        def _restore(self, blob):
            return blob["is-it-on"]


Generally you will want a classmethod deserialization constructor
which you write yourself to call this,
so that you know how to create an instance of your own object, like so:


.. code-block:: python

    class LightSwitch(object):
        _machine = MethodicalMachine()

        # ...

        @classmethod
        def from_blob(cls, blob):
            self = cls()
            self._restore(blob)
            return self


Saving and loading our `LightSwitch`
along with its state-machine state can now be accomplished as follows:


>>> switch1 = LightSwitch()
>>> switch1.query_power()
False
>>> switch1.flip()
[]
>>> switch1.query_power()
True
>>> blob = switch1.save()
>>> switch2 = LightSwitch.from_blob(blob)
>>> switch2.query_power()
True


More comprehensive (tested, working) examples are present in `docs/examples`.

Go forth and machine all the state!
