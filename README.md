# Automat #

[![Build Status](https://travis-ci.org/glyph/automat.svg?branch=master)](https://travis-ci.org/glyph/automat)
[![Coverage Status](https://coveralls.io/repos/glyph/automat/badge.png)](https://coveralls.io/r/glyph/automat)

## Self-service finite-state machines for the programmer on the go. ##

Automat is a library for concise, idiomatic Python expression of finite-state
automata (particularly deterministic finite-state transducers).

### Why use state machines? ###

Sometimes you have to create an object whose behavior varies with its state,
but still wishes to present a consistent interface to its callers.

For example, let's say you're writing the software for a coffee machine.  It
has a lid that can be opened or closed, a chamber for water, a chamber for
coffee beans, and a button for "brew".

There are a number of possible states for the coffee machine.  It might or
might not have water.  It might or might not have beans.  The lid might be open
or closed.  The "brew" button should only actually attempt to brew coffee in
one of these configurations, and the "open lid" button should only work if the
coffee is not, in fact, brewing.

With diligence and attention to detail, you can implement this correctly using
a collection of attributes on an object; `has_water`, `has_beans`,
`is_lid_open` and so on.  However, you have to keep all these attributes
consistent.  As the coffee maker becomes more complex - perhaps you add an
additional chamber for flavorings so you can make hazelnut coffee, for
example - you have to keep adding more and more checks and more and more
reasoning about which combinations of states are allowed.

Rather than adding tedious 'if' checks to every single method to make sure that
each of these flags are exactly what you expect, you can use a state machine to
ensure that if your code runs at all, it will be run with all the required
values initialized, because they have to be called in the order you declare
them.

You can read about state machines and their advantages for Python programmers
in considerably more detail
[in this excellent series of articles from ClusterHQ](https://clusterhq.com/blog/what-is-a-state-machine/).

### What makes Automat different? ###

There are
[dozens of libraries on PyPI implementing state machines](https://warehouse.python.org/search/project/?q=finite+state+machine).
So it behooves me to say why yet another one would be a good idea.

Automat is designed around this principle: while organizing your code around
state machines is a good idea, your callers don't, and shouldn't have to, care
that you've done so.  In Python, the "input" to a stateful system is a method
call; the "output" may be a method call, if you need to invoke a side effect,
or a return value, if you are just performing a computation in memory.  Most
other state-machine libraries require you to explicitly create an input object,
provide that object to a generic "input" method, and then receive results,
sometimes in terms of that library's interfaces and sometimes in terms of
classes you define yourself.

For example, a snippet of the coffee-machine example above might be implemented
as follows in naive Python:

```python
class CoffeeMachine(object):
    def brew_button(self):
        if self.has_water and self.has_beans and not self.is_lid_open:
            self.heat_the_heating_element()
            # ...
```

With Automat, you'd create a class with a `MethodicalMachine` attribute:

```python
from automat import MethodicalMachine

class CoffeeBrewer(object):
    _machine = MethodicalMachine()
```

and then you would break the above logic into two pieces - the `brew_button`
*input*, declared like so:

```python
    @_machine.input()
    def brew_button(self):
        "The user pressed the 'brew' button."
```

It wouldn't do any good to declare a method *body* on this, however, because
input methods don't actually execute their bodies when called; doing actual
work is the *output*'s job:

```python
    @_machine.output()
    def _heat_the_heating_element(self):
        "Heat up the heating element, which should cause coffee to happen."
        self._heating_element.turn_on()
```

As well as a couple of *states* - and for simplicity's sake let's say that the
only two states are `have_beans` and `dont_have_beans`:

```python
    @_machine.state()
    def have_beans(self):
        "In this state, you have some beans."
    @_machine.state(initial=True)
    def dont_have_beans(self):
        "In this state, you don't have any beans."
```

`have_beans` is the `initial` state because `CoffeeBrewer` starts without beans
in it.

(And another input to put some beans in:)

```python
    @_machine.input()
    def put_in_beans(self):
        "The user put in some beans."
```

Finally, you hook everything together with the `upon` method of the functions
decorated with `machine.state`:

```python

    # When we don't have beans, upon putting in beans, we will then have beans
    # (and produce no output)
    dont_have_beans.upon(put_in_beans, enter=have_beans, outputs=[])

    # When we have beans, upon pressing the brew button, we will then not have
    # beans any more (as they have been entered into the brewing chamber) and
    # our output will be heating the heating element.
    have_beans.upon(brew_button, enter=dont_have_beans,
                    outputs=[_heat_the_heating_element])
```

To *users* of this coffee machine class though, it still looks like a POPO
(Plain Old Python Object):

```python
>>> coffee_machine = CoffeeMachine()
>>> coffee_machine.put_in_beans()
>>> coffee_machine.brew_button()
```

All of the *inputs* are provided by calling them like methods, all of the
*outputs* are automatically invoked when they are produced according to the
outputs specified to `upon` and all of the states are simply opaque tokens -
although the fact that they're defined as methods like inputs and outputs
allows you to put docstrings on them easily to document them.

## Input for Inputs and Output for Outputs

Quite often you want to be able to pass parameters to your methods, as well as
inspecting their results.  For example, when you brew the coffee, you might
expect a cup of coffee to result, and you would like to see what kind of coffee
it is.  And if you were to put delicious hand-roasted small-batch artisanal
beans into the machine, you would expect a *better* cup of coffee than if you
were to use mass-produced beans.  You would do this in plain old Python by
adding a parameter, so that's how you do it in Automat as well.

```python
    @_machine.input()
    def put_in_beans(self, beans):
        "The user put in some beans."
```

However, one important difference here is that *we can't add any
implememntation code to the input method*.  Inputs are purely a declaration of
the interface; the behavior must all come from outputs.  Therefore, the change
in the state of the coffee machine must be represented as an output.  We can
add an output method like this:

```python
    @_machine.output()
    def _save_beans(self, beans):
        "The beans are now in the machine; save them."
        self._beans = beans
```

and then connect it to the `put_in_beans` by changing the transition from
`dont_have_beans` to `have_beans` like so:

```python
    dont_have_beans.upon(put_in_beans, enter=have_beans,
                         outputs=[_save_beans])
```

Now, when you call:

```python
coffee_machine.put_in_beans("real good beans")
```

the machine will remember the beans for later.

So how do we get the beans back out again?  One of our outputs needs to have a
return value.  It would make sense if our `brew_button` method returned the cup
of coffee that it made, so we should add an output.  So, in addition to heating
the heating element, let's add a return value that describes the coffee.  First
a new output:

```python
    @_machine.output()
    def _describe_coffee(self):
        return "A cup of coffee made with {}.".format(self._beans)
```

Note that we don't need to check first whether `self._beans` exists or not,
because we can only reach this output method if the state machine says we've
gone through a set of states that sets this attribute.

Now, we need to hook up `_describe_coffee` to the process of brewing, so change
the brewing transition to:

```python
    have_beans.upon(brew_button, enter=dont_have_beans,
                    outputs=[_heat_the_heating_element,
                             _describe_coffee])
```

Now, we can call it:

```python
>>> coffee_machine.brew_button()
[None, 'A cup of coffee made with real good beans.']
```

Except... wait a second, what's that `None` doing there?

Since every input can produce multiple outputs, in automat, the default return
value from every input invocation is a `list`.  In this case, we have both
`_heat_the_heating_element` and `_describe_coffee` outputs, so we're seeing
both of their return values.  However, this can be customized, with the
`collector` argument to `upon`; the `collector` is a callable which takes an
iterable of all the outputs' return values and "collects" a single return value
to return to the caller of the state machine.

In this case, we only care about the last output, so we can adjust the call to
`upon` like this:

```python
    have_beans.upon(brew_button, enter=dont_have_beans,
                    outputs=[_heat_the_heating_element,
                             _describe_coffee],
                    collector=lambda iterable: list(iterable)[-1]
    )
```

And now, we'll get just the return value we want:

```python
>>> coffee_machine.brew_button()
'A cup of coffee made with real good beans.'
```

More comprehensive (tested, working) examples are present in `docs/examples`.

Go forth and machine all the state!
