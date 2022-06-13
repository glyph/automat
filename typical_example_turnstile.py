import traceback
from dataclasses import dataclass
from typing import Callable, List, Protocol

from automat import TypicalBuilder


class Turnstile(Protocol):
    def kick(self) -> None:
        ...

    def token_inserted(self) -> None:
        ...

    def arm_rotated(self) -> None:
        ...

    def arm_lock_engaged(self) -> None:
        ...

    def arm_lock_disengaged(self) -> None:
        ...

    def repair(self) -> None:
        ...


@dataclass
class ControlPlane(object):
    _cb: Callable[[Callable[[Turnstile], None]], None]
    _pending_operation: str | None = None
    _money_counter: int = 0

    def __post_init__(self) -> None:
        # Hmm. Don't love this pattern for handing portions of the state
        # core back to the caller...
        @self._cb
        def complete_operation(t: Turnstile) -> None:
            o, self._pending_operation = self._pending_operation, None
            match o:
                case "lock":
                    t.arm_lock_engaged()
                case "unlock":
                    t.arm_lock_disengaged()
                    t.arm_rotated()
                case None:
                    t.token_inserted()

    def lock(self) -> None:
        assert self._pending_operation is None
        self._pending_operation = "lock"

    def unlock(self) -> None:
        assert self._pending_operation is None
        self._pending_operation = "unlock"

    def reset(self) -> None:
        self._pending_operation = None


turn = TypicalBuilder(Turnstile, ControlPlane)

# You can use .implement to have wrapper implementations that apply in all
# states.  Note that these methods will execute even in error states, so if
# you need to bail out in error conditions make sure to call something on
# your public-protocol first argument.


@turn.implement(Turnstile.kick)
def kick(t: Turnstile, p: ControlPlane) -> None:
    print("BANG")


# You can also define *internal* protocols that your state classes can use.
# Mypy will not make these methods visible to your callers, although they
# are present at runtime.
class InternalTurnstile(Protocol):
    def _add_token(self) -> int:
        pass

    def _enough_tokens(self) -> None:
        ...


# If you ask for an internal interface, it will be passed along with the
# public interface and state core.  Internal interfaces like this can be
# used for "private" inputs; i.e. inputs to the state machine which should
# only be generated when certain conditions are met, such as a counter
# exceeding a threshold as shown here.
@turn.implement(Turnstile.token_inserted, InternalTurnstile)
def count_money(t: Turnstile, p: ControlPlane, private: InternalTurnstile) -> None:
    print("**plink**")
    if private._add_token() == 3:
        private._enough_tokens()


@turn.state(persist=False)
@dataclass
class Unpaid(object):
    "Locked, not paid"
    plane: ControlPlane
    # persist=False above means this gets reset every time we exit this
    # state.
    money: int = 0

    @turn.handle2(InternalTurnstile._add_token)
    def pay(self, t: Turnstile) -> int:
        self.money += 1
        return self.money

    @turn.handle(InternalTurnstile._enough_tokens, enter=lambda: Unlocking)
    def paid(self) -> None:
        print("requesting unlock")
        self.plane.unlock()


@turn.state()
class Unlocking(object):
    "Paid, not unlocked yet."

    @turn.handle(Turnstile.arm_lock_disengaged, enter=lambda: Paid)
    def ready(self) -> None:
        print("unlocked, waiting for customer to walk through")


@turn.state()
@dataclass
class Paid(object):
    "Paid and unlocked."
    plane: ControlPlane

    @turn.handle(Turnstile.arm_rotated, enter=lambda: Locking)
    def relock(self) -> None:
        print("customer walked through, locking")
        self.plane.lock()


@turn.state()
class Locking(object):
    "Fare consumed, not yet locked."

    @turn.handle(Turnstile.arm_lock_engaged, enter=lambda: Unpaid)
    def engaged(self) -> None:
        print("finished locking")


@turn.state(error=True)
@dataclass
class Broken(object):
    plane: ControlPlane

    @turn.handle(Turnstile.repair, enter=lambda: Unpaid)
    def repair(self) -> None:
        self.plane.reset()


Turner = turn.buildClass()
loops: List[Callable[[Turnstile], None]] = []
t = Turner(loops.append)
[loop] = loops
print()
print("turnstile example:")
t.kick()
for _ in range(10):
    loop(t)

print("haywire messages from microcontroller")
import traceback

try:
    t.arm_rotated()
except:
    traceback.print_exc()
    print("handled")
try:
    t.arm_rotated()
except:
    traceback.print_exc()
    print("still broken, fixing")
    t.repair()
# fixed now
for _ in range(10):
    loop(t)
