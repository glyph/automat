Static Typing
--------------

When writing an output for a given state,
you can assume the finite state machine will be in that state.
This might mean that specific object attributes will have values
of speciifc types.
Those attributes might,
in general,
be of some :code:`Union` type:
frequently,
an :code:`Option` type
(which is a :code:`Union[T, None]`).

It is an *anti-pattern* to check for these things inside the output.
The reason for a state machine is for the outputs to avoid checking.
However,
if the output is type annotated,
often :code:`mypy`
will complain that it cannot validate the types.
The recommended solution is to
:code:`assert`
the types inside the code.
This aligns
the assumptions
:code:`mypy`
makes
with the assumptions
:code:`automat`
makes.

For example,
consider the following:

.. code::

    import attr
    import automat
    from typing import Optional

    @attr.s(auto_attribs=True)
    class MaybeValue:
        _machine = automat.MethodicalMachine()
        _value: Optional[float] = attr.ib(default=None)

        @_machine.input()
        def set_value(self, value: float) -> None:
            "The value has been measured"

        @_machine.input()
        def get_value(self) -> float:
            "Return the value if it has been measured"

        @_machine.output()
        def _set_value_when_unset(self, value: float) -> None:
            self._value = value

        @_machine.output()
        def _get_value_when_set(self) -> float:
            """mypy will complain here:

            Incompatible return value type
            (got "Optional[float]", expected "float")
            """
            return self._value

        @_machine.state()
        def value_is_set(self):
            "The value is set"

        @_machine.state(initial=True)
        def value_is_unset(self):
            "The value is not set"

        value_is_unset.upon(
            set_value,
            enter=value_is_set,
            outputs=[_set_value_when_unset],
            collector=lambda x: None,
        )
        value_is_set.upon(
            get_value,
            enter=value_is_set,
            outputs=[_get_value_when_set],
            collector=lambda x: next(iter(x)),
        )

In this case
starting
:code:`_get_value_when_set`
with a line
:code:`assert self._value is not None`
will satisfy
:code:`mypy`.

