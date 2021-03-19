from threading import Thread, Timer

class Button:
    def __init__(self, hold_time=0, double_time=0, wait_hold=True,
                name=None, number=None, **kwds):
        self.hold_time = hold_time
        self.double_time = double_time
        self.wait_hold = wait_hold
        self.name = name
        self.number = number

        self.__dict__.update(kwds)

        self.pressed = False
        self.held = False
        self.pressed_double = False

        if self.hold_time:
            self.hold_timer = Thread()

        if self.double_time:
            self.double_timer = Thread()

    def __repr__(self):
        return 'Button({}, {}, {}, {}, {})'.format(self.hold_time, self.double_time, self.name, self.number)

    def press(self):
        if self.pressed: #Some devices send 'down' continually while pressed
            return

        if not (self.hold_time or self.double_time):
            self.press_action(self)

        elif self.double_time and self.double_timer.is_alive():
            self.double_timer.cancel()
            self.pressed_double = True
            self.double_action(self)

        elif self.hold_time:
            # wait_hold means don't do press action if hold time is reached
            if not self.wait_hold:
                self.press_action(self)
            self.hold_timer = Timer(self.hold_time, self.hold)
            self.hold_timer.start()

        self.pressed = True

    def release(self):
        if not self.pressed:
            return

        # Wait, doesn't this cause press action to trigger on both press and release in this case? Yeah, it does. Not sure why I thought this was a good idea...?
        # if not (self.hold_time or self.double_time): 
        #     self.press_action 
        #     self.pressed = False
        #     self.pressed_simultaneous = False
        #     return

        starting_double = self.double_time and not (self.held or self.pressed_double)

        if self.hold_time and self.hold_timer.is_alive():
            # print('canceling hold timer')
            self.hold_timer.cancel()

            if not (starting_double or self.pressed_double) and self.wait_hold:
                self.press_action(self)

        if starting_double:
            self.double_timer = Timer(self.double_time, self.press_action)
            self.double_timer.start()

        self.release_action(self) # Only useful when not using any of the fancy stuff, probably, but fire on every release for now

        self.held = False
        self.pressed = False
        self.pressed_double = False

    def hold(self):
        self.held = True
        self.hold_action(self)

    # Default actions take a self and second self, because they get passed
    # self as methods, while assigned functions are not methods and need
    # to be passed the button to reference stored state.
    def press_action(self, self2):
        print('Pressed: ' + str(self))

    def hold_action(self, self2):
        print('Held: ' + str(self))

    def double_action(self, self2):
        print('Double pressed: ' + str(self))

    def release_action(self, self2):
        print('Released: ' + str(self))
