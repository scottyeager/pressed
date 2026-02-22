import time

from pressed import (
    Action,
    Press,
    Release,
    Hold,
    MultiPress,
    DoublePress,
    TriplePress,
    Button,
    Combo,
    Knob,
)


# Helpers

HOLD_DUR = 0.05  # 50ms hold duration for tests
WINDOW = 0.05  # 50ms multi-press window for tests
SETTLE = 0.12  # time to wait for timers to expire


def make_log():
    """Return a list and a callback factory that appends labels to it."""
    log = []

    def cb(label):
        return lambda *args: log.append(label)

    return log, cb


# --- Press ---


class TestPress:
    def test_simple_press_fires_immediately(self):
        log, cb = make_log()
        b = Button(Press(cb("press")))
        b.press()
        assert log == ["press"]

    def test_press_does_not_refire_on_release(self):
        log, cb = make_log()
        b = Button(Press(cb("press")))
        b.press()
        b.release()
        assert log == ["press"]

    def test_repeated_press_down_ignored(self):
        log, cb = make_log()
        b = Button(Press(cb("press")))
        b.press()
        b.press()
        b.press()
        assert log == ["press"]

    def test_release_without_press_ignored(self):
        log, cb = make_log()
        b = Button(Press(cb("press")))
        b.release()
        assert log == []

    def test_press_receives_button(self):
        received = []
        b = Button(Press(lambda btn: received.append(btn)), name="test")
        b.press()
        assert received == [b]

    def test_press_release_press_cycle(self):
        log, cb = make_log()
        b = Button(Press(cb("press")))
        b.press()
        b.release()
        b.press()
        b.release()
        assert log == ["press", "press"]


# --- Release ---


class TestRelease:
    def test_release_action_fires_on_release(self):
        log, cb = make_log()
        b = Button(Press(cb("press")), Release(cb("release")))
        b.press()
        b.release()
        assert log == ["press", "release"]

    def test_release_fires_even_with_hold(self):
        log, cb = make_log()
        b = Button(Hold(HOLD_DUR, cb("hold")), Release(cb("release")))
        b.press()
        time.sleep(SETTLE)
        b.release()
        assert "release" in log
        assert "hold" in log

    def test_release_fires_every_time(self):
        log, cb = make_log()
        b = Button(Press(cb("press")), Release(cb("release")))
        b.press()
        b.release()
        b.press()
        b.release()
        assert log == ["press", "release", "press", "release"]


# --- Hold ---


class TestHold:
    def test_hold_fires_after_duration(self):
        log, cb = make_log()
        b = Button(Hold(HOLD_DUR, cb("hold")))
        b.press()
        time.sleep(SETTLE)
        assert "hold" in log

    def test_hold_does_not_fire_if_released_early(self):
        log, cb = make_log()
        b = Button(Hold(HOLD_DUR, cb("hold")))
        b.press()
        b.release()
        time.sleep(SETTLE)
        assert "hold" not in log

    def test_press_waits_for_hold_disambiguation(self):
        """Press fires on release when hold actions are registered."""
        log, cb = make_log()
        b = Button(Press(cb("press")), Hold(HOLD_DUR, cb("hold")))
        b.press()
        # Press should NOT have fired yet (waiting to see if it's a hold)
        assert "press" not in log
        b.release()
        assert log == ["press"]

    def test_press_suppressed_when_held(self):
        log, cb = make_log()
        b = Button(Press(cb("press")), Hold(HOLD_DUR, cb("hold")))
        b.press()
        time.sleep(SETTLE)
        b.release()
        assert "hold" in log
        assert "press" not in log

    def test_multiple_hold_durations(self):
        log, cb = make_log()
        b = Button(
            Hold(HOLD_DUR, cb("short")),
            Hold(HOLD_DUR * 3, cb("long")),
        )
        b.press()
        time.sleep(SETTLE)
        assert "short" in log
        time.sleep(HOLD_DUR * 3)
        assert "long" in log

    def test_hold_sets_held_state(self):
        b = Button(Hold(HOLD_DUR, lambda btn: None))
        b.press()
        time.sleep(SETTLE)
        assert b.held is True
        b.release()
        assert b.held is False


# --- Double Press ---


class TestDoublePress:
    def test_double_press_fires(self):
        log, cb = make_log()
        b = Button(Press(cb("press")), DoublePress(WINDOW, cb("double")))
        b.press()
        b.release()
        b.press()
        b.release()
        time.sleep(SETTLE)
        assert log == ["double"]

    def test_single_press_fires_after_window(self):
        log, cb = make_log()
        b = Button(Press(cb("press")), DoublePress(WINDOW, cb("double")))
        b.press()
        b.release()
        time.sleep(SETTLE)
        assert log == ["press"]

    def test_double_press_without_press_action(self):
        log, cb = make_log()
        b = Button(DoublePress(WINDOW, cb("double")))
        b.press()
        b.release()
        b.press()
        b.release()
        time.sleep(SETTLE)
        assert log == ["double"]


# --- Triple Press ---


class TestTriplePress:
    def test_triple_press_fires(self):
        log, cb = make_log()
        b = Button(
            Press(cb("press")),
            DoublePress(WINDOW, cb("double")),
            TriplePress(WINDOW, cb("triple")),
        )
        b.press()
        b.release()
        b.press()
        b.release()
        b.press()
        b.release()
        time.sleep(SETTLE)
        assert log == ["triple"]

    def test_triple_fires_double_when_no_triple_registered(self):
        """Three presses with only DoublePress registered fires double."""
        log, cb = make_log()
        b = Button(Press(cb("press")), DoublePress(WINDOW, cb("double")))
        b.press()
        b.release()
        b.press()
        b.release()
        b.press()
        b.release()
        time.sleep(SETTLE)
        assert log == ["double"]


# --- MultiPress ---


class TestMultiPress:
    def test_quad_press(self):
        log, cb = make_log()
        b = Button(MultiPress(4, WINDOW, cb("quad")))
        for _ in range(4):
            b.press()
            b.release()
        time.sleep(SETTLE)
        assert log == ["quad"]

    def test_excess_presses_match_highest(self):
        """5 presses with only quad registered fires quad."""
        log, cb = make_log()
        b = Button(Press(cb("press")), MultiPress(4, WINDOW, cb("quad")))
        for _ in range(5):
            b.press()
            b.release()
        time.sleep(SETTLE)
        assert log == ["quad"]


# --- Custom Action ---


class TestCustomAction:
    def test_custom_count_and_hold(self):
        """Action with count=2, hold > 0: double press then hold."""
        log, cb = make_log()
        b = Button(Action(cb("dph"), count=2, hold=HOLD_DUR, window=WINDOW))
        b.press()
        b.release()
        b.press()
        # Now holding on the second press
        time.sleep(SETTLE)
        assert log == ["dph"]

    def test_custom_action_hold_not_reached(self):
        """Double press then release before hold duration."""
        log, cb = make_log()
        b = Button(
            Press(cb("press")),
            Action(cb("dph"), count=2, hold=HOLD_DUR, window=WINDOW),
        )
        b.press()
        b.release()
        b.press()
        b.release()
        time.sleep(SETTLE)
        # No tap action with count=2, falls back to Press
        assert log == ["press"]


# --- Hold + DoublePress combined ---


class TestHoldAndDouble:
    def test_tap_fires_press(self):
        log, cb = make_log()
        b = Button(
            Press(cb("press")),
            Hold(HOLD_DUR, cb("hold")),
            DoublePress(WINDOW, cb("double")),
        )
        b.press()
        b.release()
        time.sleep(SETTLE)
        assert log == ["press"]

    def test_hold_fires_hold(self):
        log, cb = make_log()
        b = Button(
            Press(cb("press")),
            Hold(HOLD_DUR, cb("hold")),
            DoublePress(WINDOW, cb("double")),
        )
        b.press()
        time.sleep(SETTLE)
        b.release()
        assert "hold" in log
        assert "press" not in log

    def test_double_fires_double(self):
        log, cb = make_log()
        b = Button(
            Press(cb("press")),
            Hold(HOLD_DUR, cb("hold")),
            DoublePress(WINDOW, cb("double")),
        )
        b.press()
        b.release()
        b.press()
        b.release()
        time.sleep(SETTLE)
        assert log == ["double"]


# --- Combo ---


class TestCombo:
    def test_combo_fires_when_both_pressed(self):
        log, cb = make_log()
        a = Button(Press(cb("a")), name="a")
        b = Button(Press(cb("b")), name="b")
        Combo(a, b, callback=cb("combo"))
        a.press()
        b.press()
        assert "combo" in log

    def test_combo_suppresses_individual_actions(self):
        log, cb = make_log()
        a = Button(Press(cb("a")), name="a")
        b = Button(Press(cb("b")), name="b")
        Combo(a, b, callback=cb("combo"))
        a.press()
        b.press()
        a.release()
        b.release()
        assert log == ["combo"]

    def test_no_combo_when_not_simultaneous(self):
        log, cb = make_log()
        a = Button(Press(cb("a")), name="a")
        b = Button(Press(cb("b")), name="b")
        Combo(a, b, callback=cb("combo"))
        a.press()
        a.release()
        b.press()
        b.release()
        assert "combo" not in log
        assert "a" in log
        assert "b" in log

    def test_combo_three_buttons(self):
        log, cb = make_log()
        a = Button(name="a")
        b = Button(name="b")
        c = Button(name="c")
        Combo(a, b, c, callback=cb("combo"))
        a.press()
        b.press()
        assert "combo" not in log
        c.press()
        assert "combo" in log

    def test_combo_callback_receives_buttons(self):
        received = []
        a = Button(name="a")
        b = Button(name="b")
        Combo(a, b, callback=lambda *btns: received.extend(btns))
        a.press()
        b.press()
        assert received == [a, b]


# --- Knob ---


class TestKnob:
    def test_value_change(self):
        values = []
        k = Knob(name="vol")
        k.value_change_action = lambda knob: values.append(knob.value)
        k.update(50)
        k.update(50)  # no change
        k.update(100)
        assert values == [50, 100]


# --- Button metadata ---


class TestButtonMeta:
    def test_name_and_number(self):
        b = Button(name="kick", number=7)
        assert b.name == "kick"
        assert b.number == 7

    def test_extra_kwargs(self):
        b = Button(name="test", color="red")
        assert b.color == "red"

    def test_repr(self):
        b = Button(name="kick", number=7)
        assert "kick" in repr(b)

    def test_no_actions_button(self):
        """A button with no actions shouldn't error."""
        b = Button(name="empty")
        b.press()
        b.release()
