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

    @machine.state(initial=True)
    def _locked(self):
        "The turnstile is locked."

    @machine.state()
    def _unlocked(self):
        "The turnstile is unlocked."

    _locked.upon(fare_paid, enter=_unlocked, outputs=[_disengage_lock])
    _unlocked.upon(arm_turned, enter=_locked, outputs=[_engage_lock])
    _locked.upon(arm_turned, enter=_locked, outputs=[_nope])

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
