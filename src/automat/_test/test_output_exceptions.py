"""
Tests demonstrating behavior when user-defined output methods raise exceptions.
"""

import dataclasses
from typing import Callable, Protocol
from unittest import TestCase

from automat import NoTransition

from .. import TypeMachineBuilder, pep614


class SimpleController(Protocol):
    def trigger(self) -> None:
        "Trigger a transition"

    def recover(self) -> str:
        "Recover from error state"

    def get_state(self) -> str:
        "Get current state"


class OutputTransitions:
    def process(self, value: int) -> int:
        "Process a value"
        return 0


@dataclasses.dataclass
class SimpleMachine:
    outputs: OutputTransitions


class OutputExceptionTests(TestCase):
    def setUp(self):
        self.builder = TypeMachineBuilder(SimpleController, SimpleMachine)

        def problematic_data_provider(
            inputs: SimpleController, core: SimpleMachine
        ) -> int:
            raise RuntimeError("Data factory failed!")
            return 0

        # Define three states
        self.start = self.builder.state("start")
        self.fallback = self.builder.error_state("fallback")
        self.recovered = self.builder.state("recovered")
        self.state_expecting_data = self.builder.state(
            "state_expecting_data", problematic_data_provider
        )

        # State observers
        self.start.upon(SimpleController.get_state).loop().returns("start")
        self.fallback.upon(SimpleController.get_state).loop().returns("fallback")
        self.recovered.upon(SimpleController.get_state).loop().returns("recovered")
        self.state_expecting_data.upon(SimpleController.get_state).loop().returns(
            "state_expecting_data"
        )

    def test_exception_in_output_propagates_to_caller(self):
        @pep614(self.start.upon(SimpleController.trigger).loop())
        def failing_output(machine: SimpleController, core: SimpleMachine) -> None:
            raise ValueError("Output failed!")

        machineFactory = self.builder.build()
        machine = machineFactory(SimpleMachine(OutputTransitions()))

        with self.assertRaises(ValueError) as cm:
            machine.trigger()
        self.assertEqual(str(cm.exception), "Output failed!")
        with self.assertRaises(NoTransition) as cm:
            machine.recover()
        self.assertEqual(
            str(cm.exception),
            "no transition for recover in TypedState(name='fallback')",
        )
        self.assertEqual(machine.get_state(), "fallback")
        with self.assertRaises(NoTransition) as cm:
            machine.trigger()
        self.assertEqual(
            str(cm.exception),
            "no transition for trigger in TypedState(name='fallback')",
        )
        self.assertEqual(machine.get_state(), "fallback")

    def test_can_recover_from_error_state(self):
        # Transition that fails
        @pep614(self.start.upon(SimpleController.trigger).loop())
        def failing_output(machine: SimpleController, core: SimpleMachine) -> None:
            raise ValueError("Output failed!")

        # Recovery transition
        self.fallback.upon(SimpleController.recover).to(self.recovered).returns(
            "success"
        )
        machineFactory = self.builder.build()
        machine = machineFactory(SimpleMachine(OutputTransitions()))

        self.assertEqual(machine.get_state(), "start")
        with self.assertRaises(ValueError):
            machine.trigger()
        self.assertEqual(machine.get_state(), "fallback")
        with self.assertRaises(NoTransition) as cm:
            machine.trigger()
        result = machine.recover()
        self.assertEqual(result, "success")
        self.assertEqual(machine.get_state(), "recovered")

    def test_can_recover_from_data_factory_error(self):
        # Transition to data state
        self.start.upon(SimpleController.trigger).to(self.state_expecting_data).returns(
            None
        )
        self.fallback.upon(SimpleController.recover).to(self.recovered).returns(
            "success"
        )
        machineFactory = self.builder.build()
        machine = machineFactory(SimpleMachine(OutputTransitions()))

        self.assertEqual(machine.get_state(), "start")
        with self.assertRaises(RuntimeError) as cm:
            machine.trigger()
        self.assertEqual(machine.get_state(), "fallback")
        with self.assertRaises(NoTransition) as cm:
            machine.trigger()

        result = machine.recover()
        self.assertEqual(result, "success")
        self.assertEqual(machine.get_state(), "recovered")
