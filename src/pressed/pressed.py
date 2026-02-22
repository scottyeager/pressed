from threading import Timer


class Action:
    """Base class for button action patterns.

    Actions are defined by two dimensions:
    - count: number of consecutive presses (1 = single, 2 = double, etc.)
    - hold: duration in seconds the final press must be held (0 = fire on release)

    The window parameter controls the maximum time between consecutive presses
    for multi-press detection.

    Named subclasses like Press, Hold, and DoublePress cover common cases.
    Use Action directly for custom patterns without modifying the library:

        # Quintuple press then hold for 2 seconds
        Action(callback, count=5, hold=2.0, window=0.3)
    """

    def __init__(self, callback, *, count=1, hold=0, window=0.3):
        self.callback = callback
        self.count = count
        self.hold = hold
        self.window = window

    def __repr__(self):
        return f"{type(self).__name__}(count={self.count}, hold={self.hold}, window={self.window})"


class Press(Action):
    """Single press. Fires on release, or immediately if unambiguous."""

    def __init__(self, callback):
        super().__init__(callback, count=1, hold=0)


class Release(Action):
    """Fires on every release regardless of other actions."""

    def __init__(self, callback):
        super().__init__(callback)


class Hold(Action):
    """Fires when button is held for the specified duration."""

    def __init__(self, duration, callback):
        super().__init__(callback, count=1, hold=duration)


class MultiPress(Action):
    """Fires when button is pressed count times in quick succession."""

    def __init__(self, count, window, callback):
        super().__init__(callback, count=count, hold=0, window=window)


class DoublePress(MultiPress):
    """Double press."""

    def __init__(self, window, callback):
        super().__init__(2, window, callback)


class TriplePress(MultiPress):
    """Triple press."""

    def __init__(self, window, callback):
        super().__init__(3, window, callback)


class Button:
    """A button that dispatches actions based on press patterns.

    Actions are passed as positional arguments and describe what patterns
    the button should recognize:

        button = Button(
            Press(on_press),
            Hold(1.0, on_hold),
            DoublePress(0.3, on_double),
            name="my_button",
        )

    Call press() when the button goes down and release() when it comes up.
    The button handles all timing and disambiguation internally.
    """

    def __init__(self, *actions, name=None, number=None, **kwds):
        self.name = name
        self.number = number
        self.__dict__.update(kwds)

        # Categorize actions
        self._tap_actions = []  # hold == 0, fire on release/window expiry
        self._hold_actions = []  # hold > 0, fire on timer
        self._release_action = None

        for action in actions:
            if isinstance(action, Release):
                self._release_action = action
            elif action.hold > 0:
                self._hold_actions.append(action)
            else:
                self._tap_actions.append(action)

        self._hold_actions.sort(key=lambda a: a.hold)

        self._has_multi = any(
            a.count > 1 for a in self._tap_actions + self._hold_actions
        )
        self._max_window = max(
            (a.window for a in self._tap_actions + self._hold_actions if a.count > 1),
            default=0,
        )

        # State
        self.pressed = False
        self.held = False
        self._press_count = 0
        self._resolved = False
        self._hold_timers = []
        self._window_timer = None

        # Combo support
        self._combos = []
        self._combo_claimed = False

    def __repr__(self):
        return f"Button({self.name!r}, {self.number!r})"

    def press(self):
        """Call when the button is physically pressed down."""
        if self.pressed:
            return

        self._press_count += 1
        self._resolved = False
        self._combo_claimed = False
        self.pressed = True

        # Cancel window timer (another press arrived)
        if self._window_timer is not None and self._window_timer.is_alive():
            self._window_timer.cancel()
        self._window_timer = None

        # Cancel old hold timers
        for timer in self._hold_timers:
            if timer.is_alive():
                timer.cancel()
        self._hold_timers.clear()

        # Start hold timers for actions matching current press count
        for action in self._hold_actions:
            if action.count == self._press_count:
                timer = Timer(action.hold, self._fire_hold, args=[action])
                timer.daemon = True
                timer.start()
                self._hold_timers.append(timer)

        # Notify combos
        for combo in self._combos:
            combo._notify_press(self)

        if self._combo_claimed:
            self._resolved = True
            return

        # Fire immediately if unambiguous
        if (
            not self._hold_actions
            and not self._has_multi
            and not self._combos
            and self._press_count == 1
        ):
            action = self._find_tap_action(1)
            if action:
                action.callback(self)
            self._resolved = True

    def release(self):
        """Call when the button is physically released."""
        if not self.pressed:
            return

        self.pressed = False

        # Cancel hold timers
        for timer in self._hold_timers:
            if timer.is_alive():
                timer.cancel()
        self._hold_timers.clear()

        # Release action fires on every release
        if self._release_action:
            self._release_action.callback(self)

        # Notify combos
        for combo in self._combos:
            combo._notify_release(self)

        # Already resolved (immediate fire, combo claimed, or hold fired)
        if self._resolved or self.held or self._combo_claimed:
            self.held = False
            self._press_count = 0
            self._resolved = False
            self._combo_claimed = False
            return

        # Wait for more presses if multi-press actions exist
        if self._has_multi:
            self._window_timer = Timer(self._max_window, self._resolve)
            self._window_timer.daemon = True
            self._window_timer.start()
        else:
            self._resolve()

    def _fire_hold(self, action):
        self.held = True
        action.callback(self)

    def _resolve(self):
        action = self._find_tap_action(self._press_count)
        if action:
            action.callback(self)
        self._press_count = 0

    def _find_tap_action(self, count):
        """Find tap action with highest registered count <= given count."""
        best = None
        for action in self._tap_actions:
            if action.count <= count:
                if best is None or action.count > best.count:
                    best = action
        return best


class Combo:
    """Fires when multiple buttons are pressed simultaneously.

    Registers itself with each button. When all buttons in the combo
    are pressed at the same time, the callback fires and individual
    button actions are suppressed.

        left = Button(Press(on_left), name="left")
        right = Button(Press(on_right), name="right")
        both = Combo(left, right, callback=on_both)
    """

    def __init__(self, *buttons, callback):
        self.buttons = buttons
        self.callback = callback

        for button in buttons:
            button._combos.append(self)

    def _notify_press(self, button):
        if all(b.pressed for b in self.buttons):
            self.callback(*self.buttons)
            for b in self.buttons:
                b._combo_claimed = True

    def _notify_release(self, button):
        pass


class Knob:
    def __init__(self, initial_value=0, name=None, number=None, **kwds):
        self.value = initial_value
        self.name = name
        self.number = number
        self.__dict__.update(kwds)

    def __repr__(self):
        return f"Knob({self.value}, {self.name!r}, {self.number!r})"

    def update(self, new_value):
        if self.value != new_value:
            self.value = new_value
            self.value_change_action(self)

    def value_change_action(self, self2):
        pass
