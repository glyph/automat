
from automat import MethodicalMachine

class Door(object):
    def unlock(self):
        print("Opening the door so you can get your food.")

    def lock(self):
        print("Locking the door so you can't steal the food.")

class Light(object):
    def on(self):
        print("Need some food over here.")

    def off(self):
        print("We're good on food for now.")

class FoodSlot(object):
    """
    Automats were a popular kind of business in the 1950s and 60s; a sort of
    restaurant-sized vending machine that served cooked food out of a
    coin-operated dispenser.

    This class represents the logic associated with a single food slot.
    """

    _machine = MethodicalMachine()

    def __init__(self, door, light):
        self._door = door
        self._light = light
        self._start()

    @_machine.state(initial=True)
    def _initial(self):
        """
        The initial state when we are constructed.

        Note that applications never see this state, because the constructor
        provides an input to transition out of it immediately.
        """

    @_machine.state()
    def _empty(self):
        """
        The machine is empty (and the light asking for food is on).
        """

    @_machine.input()
    def _start(self):
        """
        A private input, for transitioning to the initial blank state to
        'empty', making sure the door and light are properly configured.
        """

    @_machine.state()
    def _ready(self):
        """
        We've got some food and we're ready to serve it.
        """

    @_machine.state()
    def _serving(self):
        """
        The door is open, we're serving food.
        """

    @_machine.input()
    def coin(self):
        """
        A coin (of the appropriate denomination) was inserted.
        """

    @_machine.input()
    def food(self):
        """
        Food was prepared and inserted into the back of the machine.
        """

    @_machine.output()
    def _turnOnFoodLight(self):
        """
        Turn on the 'we need food' light.
        """
        self._light.on()

    @_machine.output()
    def _turnOffFoodLight(self):
        """
        Turn off the 'we need food' light.
        """
        self._light.off()

    @_machine.output()
    def _lockDoor(self):
        """
        Lock the door, we don't need food.
        """
        self._door.lock()

    @_machine.output()
    def _unlockDoor(self):
        """
        Lock the door, we don't need food.
        """
        self._door.unlock()

    @_machine.input()
    def closeDoor(self):
        """
        The door was closed.
        """

    _machine.transitions([
        (_initial, _start, _empty, [_lockDoor, _turnOnFoodLight]),
        (_empty, food, _ready, [_turnOffFoodLight]),
        (_ready, coin, _serving, [_unlockDoor]),
        (_serving, closeDoor, _empty, [_lockDoor, _turnOnFoodLight]),
    ])


slot = FoodSlot(Door(), Light())
if __name__ == '__main__':
    raw_input("Hit enter to make some food and put it in the slot: ")
    slot.food()
    raw_input("Hit enter to insert a coin: ")
    slot.coin()
    raw_input("Hit enter to retrieve the food and close the door: ")
    slot.closeDoor()
    raw_input("Hit enter to make some more food: ")
    slot.food()

