from threading import Thread, Timer

class Button:
    def __init__(self, hold_time=0, double_time=0, wait_hold=True,
                simultaneous=False, name=None, number=None, **kwds):
        self.hold_time = hold_time
        self.double_time = double_time
        self.wait_hold = wait_hold
        self.simultaneous = simultaneous
        self.name = name
        self.number = number

        self.__dict__.update(kwds)

        self.pressed = False
        self.held = False
        self.pressed_double = False
        self.pressed_simultaneous = False

        if self.hold_time:
            self.hold_timer = Thread()

        if self.double_time:
            self.double_timer = Thread()

    def __repr__(self):
        return 'Button({}, {}, {}, {}, {})'.format(self.hold_time, self.double_time, self.simultaneous, self.name, self.number)

    def press(self):
        if self.pressed: #Some devices send 'down' continually while pressed
            return

        if not (self.hold_time or self.double_time or self.simultaneous):
            self.press_action(self)

        elif self.double_time and self.double_timer.is_alive():
            self.double_timer.cancel()
            self.pressed_double = True
            self.double_action(self)

        elif self.hold_time and not self.pressed_double:
            if not self.wait_hold:
                self.press_action(self)
            self.hold_timer = Timer(self.hold_time, self.hold)
            self.hold_timer.start()

        self.pressed = True

    def release(self):
        if not self.pressed:
            return

        if not (self.hold_time or self.double_time):
            self.press_action
            self.pressed = False
            self.pressed_simultaneous = False
            return

        starting_double = self.double_time and not self.pressed_double

        if self.hold_time and not self.held:
            # print('canceling hold timer')
            self.hold_timer.cancel()

            if not (starting_double or self.pressed_double):
                self.press_action(self)

        if self.double_time and not (self.held or self.pressed_double or self.pressed_simultaneous):
            self.double_timer = Timer(self.double_time, self.press_action)
            self.double_timer.start()

        self.held = False
        self.pressed = False
        self.pressed_double = False
        self.pressed_simultaneous = False

    def hold(self):
        self.held = True
        self.hold_action(self)

    def press_simultaneous(self, button):
        if self.hold_timer.is_alive():
            self.hold_timer.cancel()
            self.simultaneous_action(self, button)
            self.pressed_simultaneous = True

    def press_action(self, self2):
        print('Pressed: ' + str(self))

    def hold_action(self, self2):
        print('Held: ' + str(self))

    def double_action(self, self2):
        print('Double pressed: ' + str(self))

    def simultaneous_action(self, self2, button):
        print('Simultaneous: {} and {}'.format(self, button))






if __name__ == '__main__':
    b = Button(2,2)

    b.press()
    b.release()
    b.press()
    b.release()
