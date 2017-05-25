from automat import MethodicalMachine
from automat._core import NoTransition
import math


class Player(object):
    def __init__(self):
        self._position = (0, 0)

    def update(self, t):
        # The player is simulated by moving left and right
        self._position = (math.sin(t/10.0)*15.0, 0)


class Goblin(object):
    _machine = MethodicalMachine()

    def __init__(self):
        self._position = (0, 0)

    @_machine.input()
    def player_visible(self):
        "The player is out of sight"

    @_machine.input()
    def player_not_visible(self):
        "The player is not visible"

    @_machine.input()
    def player_inside_range(self):
        "Player inside range"

    @_machine.input()
    def player_outside_range(self):
        "player outside range"

    @_machine.input()
    def timestep(self):
        "timestep"

    @_machine.output()
    def print_idle(self):
        print("transition_idle")

    @_machine.output()
    def print_chase(self):
        print("transition_chase")

    @_machine.output()
    def print_attack(self):
        print("transition_attack")

    @_machine.output()
    def do_idle(self):
        print("idling")
        # todo: make the goblin move around randomly

    @_machine.output()
    def do_chase(self):
        print("chasing")
        # todo: make the goblin move towards the player

    @_machine.output()
    def do_attack(self):
        print("attacking")
        # todo: make the goblin attack the player

    @_machine.state(initial=True)
    def idle(self):
        "Idling around"

    @_machine.state()
    def chase(self):
        "chasing"

    @_machine.state()
    def attack(self):
        "attacking"

    def _compute_range(self, p1, p2):
        """Compute the distance to the player"""
        xd = p2[0]-p1[0]
        yd = p2[1]-p1[1]
        d = math.sqrt(xd**2.0 + yd**2.0)
        return d

    def update(self, player, t):
        """Update the goblins "perception" of the world and
           change states accordingly
        """
        d = self._compute_range(self._position, player._position)
        print("Distance:", d)
        # Goblin is close enough to attack player
        if d < 1.0:
            # Use Try Catch to accept any transition within a state
            try:
                self.player_inside_range()
            except NoTransition as nte:
                pass
        # Goblin is not close enough to attack player
        if d >= 1.0 and d < 10.0:
            # Use Try Catch to accept any transition within a state
            try:
                self.player_outside_range()
            except NoTransition as nte:
                pass
        # Goblin is close enough to see the player
        if d <= 10.0:
            # Use Try Catch to accept any transition within a state
            try:
                self.player_visible()
            except NoTransition as nte:
                pass
        # Goblin is 10 units away and can no longer see player
        if d >= 10.0:
            # Use Try Catch to accept any transition within a state
            try:
                self.player_not_visible()
            except NoTransition as nte:
                pass

    # Transitions which cause the goblin to change behaviour given the players
    # current state.
    idle.upon(player_visible, enter=chase, outputs=[print_chase])
    chase.upon(player_inside_range, enter=attack, outputs=[print_attack])
    attack.upon(player_outside_range, enter=chase, outputs=[print_chase])
    chase.upon(player_not_visible, enter=idle, outputs=[print_idle])
    # Timestep transitions which return to the current state but execute
    # behaviour
    idle.upon(timestep, enter=idle, outputs=[do_idle])
    chase.upon(timestep, enter=chase, outputs=[do_chase])
    attack.upon(timestep, enter=attack, outputs=[do_attack])


if __name__ == "__main__":
    # Create the Goblin agent which has a state machine
    g = Goblin()
    # Create the simulated player object
    p = Player()
    # Simulate a game loop for 1000 timesteps
    t = 0
    while t < 1000:
        # Update the goblin and the player for this timestep
        p.update(t)
        g.update(p, t)
        # The timestep transition is executed every timestep
        # The timestep transition always returns the goblin to the state it is
        # currently in but allows the goblin to perform a behaviour each
        # timestep.  This could be moving its position by a fixed velocity, or
        # swinging an axe to attack a player.
        g.timestep()
        # increment the timestep for the game loop
        t = t + 1
