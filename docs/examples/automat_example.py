
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

    machine = MethodicalMachine()

    def __init__(self, door, light):
        self._door = door
        self._light = light
        self.start()

    @machine.state(initial=True)
    def initial(self):
        """
        The initial state when we are constructed.

        Note that applications never see this state, because the constructor
        provides an input to transition out of it immediately.
        """

    @machine.state()
    def empty(self):
        """
        The machine is empty (and the light asking for food is on).
        """

    @machine.input()
    def start(self):
        """
        A private input, for transitioning to the initial blank state to
        'empty', making sure the door and light are properly configured.
        """

    @machine.state()
    def ready(self):
        """
        We've got some food and we're ready to serve it.
        """

    @machine.state()
    def serving(self):
        """
        The door is open, we're serving food.
        """

    @machine.input()
    def coin(self):
        """
        A coin (of the appropriate denomination) was inserted.
        """

    @machine.input()
    def food(self):
        """
        Food was prepared and inserted into the back of the machine.
        """

    @machine.output()
    def turnOnFoodLight(self):
        """
        Turn on the 'we need food' light.
        """
        self._light.on()

    @machine.output()
    def turnOffFoodLight(self):
        """
        Turn off the 'we need food' light.
        """
        self._light.off()

    @machine.output()
    def lockDoor(self):
        """
        Lock the door, we don't need food.
        """
        self._door.lock()

    @machine.output()
    def unlockDoor(self):
        """
        Unock the door, it's chow time!.
        """
        self._door.unlock()

    @machine.input()
    def closeDoor(self):
        """
        The door was closed.
        """

    initial.upon(start, enter=empty, outputs=[lockDoor, turnOnFoodLight])
    empty.upon(food, enter=ready, outputs=[turnOffFoodLight])
    ready.upon(coin, enter=serving, outputs=[unlockDoor])
    serving.upon(closeDoor, enter=empty, outputs=[lockDoor,
                                                  turnOnFoodLight])



slot = FoodSlot(Door(), Light())

if __name__ == '__main__':
    import sys
    sys.stdout.writelines(FoodSlot.machine.asDigraph())
    # raw_input("Hit enter to make some food and put it in the slot: ")
    # slot.food()
    # raw_input("Hit enter to insert a coin: ")
    # slot.coin()
    # raw_input("Hit enter to retrieve the food and close the door: ")
    # slot.closeDoor()
    # raw_input("Hit enter to make some more food: ")
    # slot.food()

