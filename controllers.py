import time, hid, rtmidi
from threading import Thread
from evdev import InputDevice, categorize, ecodes as e

# Since this isn't a package yet, support a couple ways of including it
try:
    from pressed.pressed import Button, Knob
except ModuleNotFoundError:
    from pressed import Button, Knob


class Qwerty:
    """
    See here for code to make lights blink: https://stackoverflow.com/questions/854393/change-keyboard-locks-in-python/858992#858992
    """

    def __init__(self, path, key_map, grab=False, verbose=False):
        self.dev = InputDevice(path)
        self.key_map = key_map
        self.grab = grab
        self.verbose = verbose
        self.buttons = {key: Button(name=key) for key in key_map}

        if self.grab:
            self.dev.grab()  # This requires user in input group or run as root

    def loop(self):
        for event in self.dev.read_loop():
            if event.type == e.EV_KEY:
                event = categorize(event)
                if self.verbose:
                    print(event)

                if event.keycode in self.key_map:
                    if event.keystate == 1:  # Key down event
                        print("pressing button: " + event.keycode)
                        self.buttons[event.keycode].press()

                    elif event.keystate == 0:  # Key up event, not key specific
                        for b in dict.values(self.buttons):
                            if b.pressed:
                                b.release()


# Foot controller keyboard
# dev = InputDevice('/dev/input/by-id/usb-05a4_USB_Compliant_Keyboard-event-kbd')

# Desk keyboard
# dev = InputDevice('/dev/input/by-path/pci-0000:00:14.0-usb-0:1.1:1.0-event-kbd')

# Laptop keyboard
# path = "/dev/input/by-path/platform-i8042-serio-0-event-kbd"

# Any ol' event
# dev = InputDevice('/dev/input/event0')

# dev.grab() # Capture input, so we're not typing

# Infinity Transcription Footpedal


class Infinity:
    button_map = {1: "left", 2: "center", 4: "right"}

    def __init__(self, hold=0.45, double=0):  # .25 works for double
        self.open()

        self.buttons = {
            name: Button(hold, double, True, name, number)
            for number, name in self.button_map.items()
        }

    def open(self):
        try:
            self.dev = hid.device()
            self.dev.open(0x05F3, 0x00FF)  # VendorId/ProductId

            print("Connected to Infinity")

            # Clear any input waiting in queue
            while self.dev.read(8, 1):
                pass

            return True

        except OSError:
            print("Couldn't open Infinity")
            return False

    def loop(self):
        while 1:
            try:
                press = self.dev.read(8)[0]
            except (OSError, ValueError):
                print("Not connected to Infinity, trying to open again")
                if self.open():
                    continue
                else:
                    time.sleep(2)
                    continue

            if press == 0:
                for button in self.buttons.values():
                    if button.pressed:
                        button.release()

            elif press in [1, 2, 4]:
                name = self.button_map[press]
                self.buttons[name].press()

            else:
                for button in self.buttons.values():
                    if button.pressed and button.simultaneous:
                        new_button = self.button_map(press - button.number)
                        button.simultaneous_press(new_button)

    def start_loop_thread(self):
        self.loop_thread = Thread(target=self.loop)
        self.loop_thread.daemon = True
        self.loop_thread.start()


class LPD8:
    def __init__(self):
        self.midi_in = rtmidi.MidiIn(name="lpd8")
        self.midi_in.open_virtual_port("lpd8")

        self.midi_out = rtmidi.MidiOut(name="lpd8")
        self.midi_out.open_virtual_port("lpd8")

        self.callbacks = []
        self.midi_in.set_callback(self.respond)

        self.pads = [Button(name="pad", number=i, lit="off") for i in range(8)]
        self.ccs = [Button(name="cc", number=i, lit="off") for i in range(8)]
        self.knobs = [Knob(name="knob", number=i) for i in range(8)]

        self.midi_root = 36
        self.blink_time = 0.4

    def send(self, *msg):
        self.midi_out.send_message(msg)

    def respond(self, data, extra):
        msg = data[0]
        if msg[0] == 176 and msg[1] in range(1, 9):  # CC messages for knobs
            self.knobs[msg[1] - 1].update(msg[2] / 127)
        elif msg[1] in range(36, 44):
            if msg[0] == 144:
                self.pads[msg[1] - self.midi_root].press()
            elif msg[0] == 128:
                self.pads[msg[1] - self.midi_root].release()
            elif msg[0] == 176:
                if msg[2] > 0:
                    self.ccs[msg[1] - self.midi_root].press()
                else:
                    self.ccs[msg[1] - self.midi_root].release()

            self.light()

        for f in self.callbacks:
            f(msg)

    def light(self):
        if time.time() % (self.blink_time) > self.blink_time / 2:
            blink_slow = True
            blink_fast = True
        elif time.time() % (self.blink_time * 2) > self.blink_time:
            blink_slow = True
            blink_fast = False
        else:
            blink_slow = False
            blink_fast = False

        for b in self.pads:
            if (
                b.lit == "on"
                or (b.lit == "blink_fast" and blink_fast)
                or (b.lit == "blink_slow" and blink_slow)
            ):
                self.send(144, self.midi_root + b.number, 127)
            else:
                self.send(128, self.midi_root + b.number, 0)

        for b in self.ccs:
            if (
                b.lit == "on"
                or (b.lit == "blink_fast" and blink_fast)
                or (b.lit == "blink_slow" and blink_slow)
            ):
                self.send(176, self.midi_root + b.number, 127)
            else:
                self.send(176, self.midi_root + b.number, 0)

    def light_loop(self):
        while 1:
            self.light()
            time.sleep(0.1)

    def start_light_thread(self):
        self.light_thread = Thread(target=self.light_loop)
        self.light_thread.start()


class APCMini:
    light_codes = {
        "off": 0,
        "on": 1,
        "blink": 2,
        "green": 1,
        "blink_green": 2,
        "red": 3,
        "blink_red": 4,
        "orange": 5,
        "blink_orange": 6,
    }

    def __init__(self, shifting=False):
        """
        If shifting is True, then we'll create a separate set of buttons and call their actions while the shift key is held down. Otherwise, shift just acts as another button.
        """

        self.shifting = shifting

        self.midi_in = rtmidi.MidiIn(name="apc")
        self.midi_in.open_virtual_port("apc")

        self.midi_out = rtmidi.MidiOut(name="apc")
        self.midi_out.open_virtual_port("apc")

        self.callbacks = []
        self.midi_in.set_callback(self.respond)

        self.buttons = APCMiniButtons(self)
        self.grid = self.buttons.grid
        self.bottom_row = self.buttons.bottom_row
        self.right_column = self.buttons.right_column
        self.grid_columns = self.buttons.grid_columns
        self.shift = self.buttons.shift

        if shifting:
            self.shifted_buttons = APCMiniButtons(self)
            self.shifted_grid = self.shifted_buttons.grid
            self.shifted_bottom_row = self.shifted_buttons.bottom_row
            self.shifted_right_column = self.shifted_buttons.right_column
            self.shifted_grid_columns = self.shifted_buttons.grid_columns

            # Just need one shift button, not attached to other sets
            del self.buttons.shift
            del self.shifted_buttons.shift
            self.shift = Button(number=98)

    def light(self, button, state):
        "Controls lighting of buttons to the following states: off, green, blink_green, red, blink_red, orange, blink_orange."

        button.lit = state
        self.send(144, button.number, self.light_codes[state])

    def relight(self, buttons):
        """
        For shifting, to reset all lights to saved states
        """
        for b in buttons:
            self.send(144, b.number, self.light_codes[b.lit])

    def respond(self, data, extra):
        """
        Dispatches incoming midi messages and calls any additional callbacks. Designed to be passed to rtmidi as a callback.
        """

        # Check shifting so we can be lazy below and always set shifted
        if self.shifting and self.shifted:
            buttons = self.shifted_buttons
        else:
            buttons = self.buttons

        msg = data[0]
        if msg[1] >= 0 and msg[1] < 64:
            button = buttons.grid[msg[1]]

        elif msg[1] >= 64 and msg[1] < 72:
            button = buttons.bottom_row[msg[1] - 64]

        elif msg[1] >= 82 and msg[1] < 90:
            button = buttons.right_column[msg[1] - 82]

        elif msg[1] == 98:
            button = self.shift
            if self.shifting:
                if msg[0] == 144:
                    self.shifted = True
                    self.relight(self.shifted_buttons)
                elif msg[0] == 128:
                    self.shifted = False
                    self.relight(self.buttons)

        if msg[0] == 144:
            button.press()
        elif msg[0] == 128:
            button.release()

        if self.shifting and self.shifted:
            callbacks = self.shifted_callbacks
        else:
            callbacks = self.callbacks

        for f in callbacks:
            f(button, {144: True, 128: False}[msg[0]])

    def send(self, *msg):
        self.midi_out.send_message(msg)


class APCMiniButton(Button):
    def __init__(
        self,
        apc,
        lit="off",
        hold_time=0,
        double_time=0,
        wait_hold=True,
        name=None,
        number=None,
    ):
        self.apc = apc
        self.lit = lit
        super().__init__(hold_time, double_time, wait_hold, name, number)

    def light(self, state):
        self.apc.light(self, state)
        self.lit = state


class APCMiniButtons:
    """
    Abstract the set of buttons, to duplicate for shift function.
    """

    def __init__(self, apc):
        self.apc = apc
        # Number attribute here refers to the midi note used for I/O
        # Grid is indexed left to right, bottom to top
        # Right column is indexed top to bottom
        self.grid = [APCMiniButton(apc, number=i) for i in range(64)]
        self.bottom_row = [APCMiniButton(apc, number=64 + i) for i in range(8)]
        self.right_column = [APCMiniButton(apc, number=82 + i) for i in range(8)]

        # Shift button has no light, so it's a regular Button
        self.shift = Button(number=98)

        # For 2D indexing, left to right and top to bottom
        self.grid_columns = [[] for i in range(8)]
        for i in range(64):
            self.grid_columns[i % 8].insert(0, self.grid[i])

    def __getitem__(self, number):
        try:
            if number >= 0 and number < 64:
                return self.grid[number]
            elif number >= 64 and number < 72:
                return self.bottom_row[number - 64]
            elif number >= 82 and number < 90:
                return self.right_column[number - 82]
            elif number == 98:
                return self.shift
            else:
                raise IndexError
        except:
            raise IndexError from None
