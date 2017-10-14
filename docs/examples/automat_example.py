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

    @machine.flag(states=['initial', 'empty', 'ready', 'serving'],
                  initial='initial')
    def state(self):
        """
        The possible states that a food slot can have.

        Note that applications never see the "initial" state,
        because the constructor provides an input
        to transition out of it immediately.
        """

    @machine.input()
    def start(self):
        """
        A private input, for transitioning to the initial blank state to
        'empty', making sure the door and light are properly configured.
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

    @machine.input()
    def closeDoor(self):
        """
        The door was closed.
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

    machine.transition(
        from_={'state': 'initial'},
        to={'state': 'empty'},
        input=start,
        outputs=[lockDoor, turnOnFoodLight]
    )
    machine.transition(
        from_={'state': 'empty'},
        to={'state': 'ready'},
        input=food,
        outputs=[turnOffFoodLight],
    )
    machine.transition(
        from_={'state': 'ready'},
        to={'state': 'serving'},
        input=coin,
        outputs=[unlockDoor],
    )
    machine.transition(
        from_={'state': 'serving'},
        to={'state': 'empty'},
        input=closeDoor,
        outputs=[lockDoor, turnOnFoodLight]
    )


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
