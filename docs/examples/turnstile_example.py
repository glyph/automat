from automat import MethodicalMachine


class Turnstile(object):
    machine = MethodicalMachine()

    def __init__(self, lock):
        self.lock = lock

    @machine.input()
    def arm_turned(self):
        "The arm was turned."

    @machine.input()
    def fare_paid(self):
        "The fare was paid."

    @machine.output()
    def _engage_lock(self):
        self.lock.engage()

    @machine.output()
    def _disengage_lock(self):
        self.lock.disengage()

    @machine.output()
    def _nope(self):
        print("**Clunk!**  The turnstile doesn't move.")

    @machine.flag(states=[True, False], initial=True)
    def _locked(self):
        "Indicates whether turnstile is locked."

    machine.transition(
        from_={'_locked': True},
        to={'_locked': False},
        input=fare_paid,
        outputs=[_disengage_lock],
    )
    machine.transition(
        from_={'_locked': False},
        to={'_locked': True},
        input=arm_turned,
        outputs=[_engage_lock],
    )
    machine.transition(
        from_={'_locked': True},
        to={'_locked': True},
        input=arm_turned,
        outputs=[_nope],
    )


class Lock(object):
    "A sample I/O device."

    def engage(self):
        print("Locked.")

    def disengage(self):
        print("Unlocked.")


turner = Turnstile(Lock())
turner.fare_paid()
turner.arm_turned()
turner.arm_turned()
turner.fare_paid()
turner.arm_turned()
