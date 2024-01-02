from automat import TypicalMachine
from typing import Protocol
from dataclasses import dataclass


class Lock:
    "A sample I/O device."

    def engage(self):
        print("Locked.")

    def disengage(self):
        print("Unlocked.")


class Turnstile(Protocol):
    def arm_turned(self) -> None:
        "The arm was turned."

    def fare_paid(self) -> None:
        "The fare was paid."


TurnstileImpl = TypicalMachine[Turnstile, Lock](Lock)


@TurnstileImpl.initial
@dataclass
class _Locked(object):
    lock: Lock
    @TurnstileImpl.handle(Turnstile.fare_paid, enter=lambda: _Unlocked)
    def fare_paid(self) -> None:
        self.lock.disengage()

    @TurnstileImpl.handle(Turnstile.arm_turned)
    def arm_turned(self) -> None:
        print("**Clunk!**  The turnstile doesn't move.")


@dataclass
@TurnstileImpl.state
class _Unlocked:
    lock: Lock
    @TurnstileImpl.handle(Turnstile.arm_turned, enter=lambda: _Locked)
    def arm_turned(self) -> None:
        self.lock.engage()


turner = TurnstileImpl.build()
print("Paying fare 1.")
turner.fare_paid()
print("Walking through.")
turner.arm_turned()
print("Jumping.")
turner.arm_turned()
print("Paying fare 2.")
turner.fare_paid()
print("Walking through 2.")
turner.arm_turned()
print("Done.")
