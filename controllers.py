import time
from threading import Thread

import hid
import rtmidi
from evdev import InputDevice, categorize
from evdev import ecodes as e

# Our "packaging" solution. We can just copy/clone the top level "pressed"
# folder into our project
try:
    from pressed.digit_bitmaps import digit_bitmaps
except ModuleNotFoundError:
    from digit_bitmaps import digit_bitmaps

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

    def __init__(self):
        self.midi_in = rtmidi.MidiIn(name="apc")
        self.midi_in.open_virtual_port("apc")

        self.midi_out = rtmidi.MidiOut(name="apc")
        self.midi_out.open_virtual_port("apc")

        self.callbacks = []
        self.midi_in.set_callback(self.respond)

        buttons = APCMiniButtons(self)
        self.button_sets = [buttons]
        # The activate function expects an existing set to compare with
        self.buttons = buttons
        self.activate_button_set(buttons)

        # Add sliders
        self.sliders = [Knob(name=f"slider_{i}", number=i) for i in range(9)]

    def add_button_set(self, **kwargs):
        button_set = APCMiniButtons(self, **kwargs)
        self.button_sets.append(button_set)
        return button_set

    def activate_button_set(self, button_set):
        # If button_set is an int, use as an index to our list of sets
        # Otherwise, we assume it's a set of buttons
        try:
            button_set = self.button_sets[button_set]
        except TypeError:
            pass

        old_buttons = self.buttons

        # Set all the subgroups on self
        self.buttons = button_set
        self.grid = button_set.grid
        self.bottom_row = button_set.bottom_row
        self.right_column = button_set.right_column
        self.grid_columns = button_set.grid_columns
        self.shift = button_set.shift

        # We can't relight the buttons until after reassigning them, because we
        # also check if a button is part of the active set before lighting it
        for old_button, new_button in zip(old_buttons, button_set):
            if old_button.lit != new_button.lit:
                self.light_button(new_button)

    def light(self, number, state):
        "Controls lighting of buttons to the following states: off, green, blink_green, red, blink_red, orange, blink_orange."
        self.send(144, number, self.light_codes[state])

    def light_button(self, button):
        if button in self.buttons:
            self.light(button.number, button.lit)

    def clear_lights(self):
        for button in self.buttons:
            self.light(button.number, "off")

        # Sending a large amount of MIDI events to the APC Mini will cause it to ignore future events for a while.
        time.sleep(0.005)

    def clear_lights_grid(self):
        for button in self.grid:
            self.light(button.number, "off")

        # Sending a large amount of MIDI events to the APC Mini will cause it to ignore future events for a while.
        time.sleep(0.005)

    def respond(self, data, extra):
        """
        Dispatches incoming midi messages and calls any additional callbacks. Designed to be passed to rtmidi as a callback.
        """

        msg = data[0]

        # Handle sliders
        if msg[0] == 176 and msg[1] >= 48 and msg[1] <= 56:
            self.sliders[msg[1] - 48].update(msg[2] / 127)
            for f in self.callbacks:
                f(self.sliders[msg[1] - 48], msg[2])
            return

        if msg[0] == 144:
            button = self.buttons[msg[1]]
            button.press()
        elif msg[0] == 128:
            # On release, we need to trigger all sets, because a press might
            # have switched the button set. Releasing an inactive button
            # shouldn't have any bad effects (I hope!)
            for set in self.button_sets:
                button = set[msg[1]]
                button.release()

        for f in self.callbacks:
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
        if self.number == 98 and state != "off":
            raise ValueError("Cannot light the shift button")
        self.lit = state
        self.apc.light_button(self)


class APCMiniButtons:
    """
    Abstract the set of buttons, to allow multiple "screens" with independent button actions and lighting states
    """

    def __init__(self, apc, grid=None, bottom_row=None, right_column=None, shift=None):
        self.apc = apc
        # Number attribute here refers to the midi note used for I/O
        # Grid is indexed left to right, bottom to top
        # Right column is indexed top to bottom
        self.grid = grid or [APCMiniButton(apc, number=i) for i in range(64)]
        self.bottom_row = bottom_row or [
            APCMiniButton(apc, number=64 + i) for i in range(8)
        ]
        self.right_column = right_column or [
            APCMiniButton(apc, number=82 + i) for i in range(8)
        ]

        self.shift = shift or APCMiniButton(apc, number=98)

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

    def __iter__(self):
        """Iterate over all buttons in this set."""
        for button in self.grid:
            yield button
        for button in self.bottom_row:
            yield button
        for button in self.right_column:
            yield button
        yield self.shift

    def render_digits(self, digits):
        """
        Render digits on the APC Mini's 8x8 grid.
        Digits are rendered using the defined bitmaps, but since we only have 8 columns,
        the first column is only 2 wide (perfect for displaying '1').
        """
        if not digits:
            return

        # Clear the grid first
        self.apc.clear_lights_grid()

        start_col = max(0, 8 - (len(digits) * 3))
        col = start_col

        # Define colors for each digit position
        colors = ["green", "red", "orange"]

        # Render each digit
        for i, digit in enumerate(digits):
            bitmap = digit_bitmaps[int(digit)]
            color = colors[i % 3]

            # Handle special case for digit 1 in leftmost position of 3 digits (compressed)
            if digit == "1" and len(digits) == 3 and i == 0:
                for row in range(8):
                    for bit in range(
                        2
                    ):  # Drop rightmost column (only use first 2 bits)
                        if col + bit < 8 and bitmap[7 - row][bit]:
                            button_index = row * 8 + (col + bit)
                            self.grid[button_index].light(color)
                col += 2
            else:
                # All other digits are 3 columns wide
                for row in range(8):
                    for bit in range(3):
                        if col + bit < 8 and bitmap[7 - row][bit]:
                            button_index = row * 8 + (col + bit)
                            self.grid[button_index].light(color)
                col += 3

            # Apparently the APC Mini crashes if we send too many MIDI messages
            # too fast, under certain circumstances. Turning the lights off
            # doesn't cause a problem, and turning them all to the same color
            # doesn't seem to cause a problem
            time.sleep(0.005)
