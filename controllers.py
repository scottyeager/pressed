import time, hid, rtmidi
from threading import Thread
from evdev import InputDevice, categorize, ecodes as e
from pressed.pressed import Button


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
            self.dev.grab() #This requires user in input group or run as root

    def loop(self):
        for event in self.dev.read_loop():
            if event.type == e.EV_KEY:
                event = categorize(event)
                if self.verbose:
                    print(event)

                if event.keycode in self.key_map:
                    if event.keystate == 1: # Key down event
                        print('pressing button: ' + event.keycode)
                        self.buttons[event.keycode].press()

                    elif event.keystate == 0: # Key up event, not key specific
                        for b in dict.values(self.buttons):
                            if b.pressed:
                                b.release()

# Foot controller keyboard
#dev = InputDevice('/dev/input/by-id/usb-05a4_USB_Compliant_Keyboard-event-kbd')

# Desk keyboard
#dev = InputDevice('/dev/input/by-path/pci-0000:00:14.0-usb-0:1.1:1.0-event-kbd')

# Laptop keyboard
path = '/dev/input/by-path/platform-i8042-serio-0-event-kbd'

# Any ol' event
#dev = InputDevice('/dev/input/event0')

#dev.grab() # Capture input, so we're not typing

# Infinity Transcription Footpedal

class Infinity:
    button_map = {1: 'left', 2: 'center', 4:'right'}

    def __init__(self, hold=.45, double=0): #.25 works for double
        self.open()

        self.buttons = {name: Button(hold, double, True, False, name, number)
                        for number, name in self.button_map.items()}

    def open(self):
        try:
            self.dev = hid.device()
            self.dev.open(0x05f3, 0x00ff) # VendorId/ProductId

            print("Connected to Infinity")

            # Clear any input waiting in queue
            while self.dev.read(8,1):
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
        self.midi_in = rtmidi.MidiIn(name='lpd8')
        self.midi_in.open_virtual_port('lpd8')

        self.midi_out = rtmidi.MidiOut(name='lpd8')
        self.midi_out.open_virtual_port('lpd8')

        self.callbacks = []
        self.midi_in.set_callback(self.respond)

        self.pads = [Button(name='pad', number=i, lit='off') for i in range(8)]
        self.ccs = [Button(name='cc', number=i, lit='off') for i in range(8)]

        self.midi_root = 36
        self.blink_time = .4

    def send(self, *msg):
        self.midi_out.send_message(msg)

    def respond(self, data, extra):
        msg = data[0]
        if msg[1] in range(36, 44):
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
            if (b.lit == 'on' or (b.lit == 'blink_fast' and blink_fast)
                              or (b.lit == 'blink_slow' and blink_slow)):
                self.send(144, self.midi_root + b.number, 127)
            else:
                self.send(128, self.midi_root + b.number, 0)

        for b in self.ccs:
            if (b.lit == 'on' or (b.lit == 'blink_fast' and blink_fast)
                              or (b.lit == 'blink_slow' and blink_slow)):
                self.send(176, self.midi_root + b.number, 127)
            else:
                self.send(176, self.midi_root + b.number, 0)

    def light_loop(self):
        while 1:
            self.light()
            time.sleep(.1)

    def start_light_thread(self):
        self.light_thread = Thread(target=self.light_loop)
        self.light_thread.start()

class APCMini:
    light_codes = {'off': 0, 'on': 1, 'blink': 2,
                    'green': 1, 'blink_green': 2, 
                    'red': 3, 'blink_red': 4, 
                    'orange': 5, 'blink_orange': 6}
    
    def __init__(self):
        self.midi_in = rtmidi.MidiIn(name='apc')
        self.midi_in.open_virtual_port('apc')

        self.midi_out = rtmidi.MidiOut(name='apc')
        self.midi_out.open_virtual_port('apc')

        self.callbacks = []
        self.midi_in.set_callback(self.respond)

        # Number attribute here refers to the midi note used for I/O
        # Grid is indexed left to right, bottom to top
        # Right column is indexed top to bottom
        self.grid = [Button(number=i, lit='off') for i in range(64)]
        self.bottom_row = [Button(number=64 + i, lit='off') for i in range(8)]
        self.right_column = [Button(number=82 + i, lit='off') for i in range(8)]
        self.shift = Button(number=98)

        # For 2D indexing, left to right and top to bottom
        self.grid_columns = [[] for i in range(8)]
        for i in range(64):
            self.grid_columns[i % 8].insert(0, self.grid[i])

    def light(self, button, state):
        "Controls lighting of buttons to the following states: off, green, blink_green, red, blink_red, orange, blink_orange."

        self.send(144, button.number, self.light_codes[state])


    def respond(self, data, extra):
        """
        Dispatches incoming midi messages and calls any additional callbacks. Designed to be passed to rtmidi as a callback.
        """

        msg = data[0]
        if msg[1] >= 0 and msg[1] < 64:
            if msg[0] == 144:
                self.grid[msg[1]].press()
            elif msg[0] == 128:
                self.grid[msg[1]].release()

        elif msg[1] >= 64 and msg[1] < 72:
            if msg[0] == 144:
                self.bottom_row[msg[1] - 64].press()
            elif msg[0] == 128:
                self.bottom_row[msg[1] - 64].release()

        elif msg[1] >= 82 and msg[1] < 90:
            if msg[0] == 144:
                self.right_column[msg[1] - 82].press()
            elif msg[0] == 128:
                self.right_column[msg[1] - 82].release()

        elif msg[1] == 98:
            if msg[0] == 144:
                self.shift.press()
            elif msg[0] == 128:
                self.shift.release()


        for f in self.callbacks:
            f(msg)

    def send(self, *msg):
        self.midi_out.send_message(msg)