"""PushToTalk — the whole push-to-talk contract, without a keyboard.

Mirrors how services/jv-ears/jv_ears/tests exercise dialog.ListenWindow:
pure logic, a fake clock, and every edge a real keyboard can actually
deliver (autorepeat, a stray release, a key that never comes back up)."""

from jv_dictate.ptt import PushToTalk

TRIGGER = 99
OTHER = 1


def make(now):
    clock = {"t": now}
    ptt = PushToTalk(TRIGGER, clock=lambda: clock["t"])
    return ptt, clock


def test_pressing_the_trigger_starts_and_reports_active():
    ptt, _ = make(0.0)
    assert ptt.feed(TRIGGER, True) == "start"
    assert ptt.active


def test_releasing_the_trigger_stops():
    ptt, _ = make(0.0)
    ptt.feed(TRIGGER, True)
    assert ptt.feed(TRIGGER, False) == "stop"
    assert not ptt.active


def test_autorepeat_press_while_active_is_a_no_op():
    ptt, _ = make(0.0)
    assert ptt.feed(TRIGGER, True) == "start"
    assert ptt.feed(TRIGGER, True) is None
    assert ptt.active


def test_a_stray_release_with_nothing_active_is_ignored():
    ptt, _ = make(0.0)
    assert ptt.feed(TRIGGER, False) is None
    assert not ptt.active


def test_other_keys_never_reach_the_state_machine():
    ptt, _ = make(0.0)
    assert ptt.feed(OTHER, True) is None
    assert not ptt.active
    ptt.feed(TRIGGER, True)
    assert ptt.feed(OTHER, False) is None
    assert ptt.active


def test_a_second_press_after_a_full_cycle_starts_again():
    ptt, _ = make(0.0)
    ptt.feed(TRIGGER, True)
    ptt.feed(TRIGGER, False)
    assert ptt.feed(TRIGGER, True) == "start"


def test_not_expired_before_the_hard_cap():
    ptt, clock = make(0.0)
    ptt.feed(TRIGGER, True)
    clock["t"] = PushToTalk.MAX_RECORDING_S - 0.001
    assert not ptt.expired()


def test_expired_at_the_hard_cap():
    # Mirrors dialog.listen's own `window_s <= 60` — a key stuck down (or a
    # dropped release event) must not become an open mic.
    ptt, clock = make(0.0)
    ptt.feed(TRIGGER, True)
    clock["t"] = PushToTalk.MAX_RECORDING_S
    assert ptt.expired()


def test_expired_is_false_when_nothing_is_active():
    ptt, clock = make(0.0)
    clock["t"] = 10_000.0
    assert not ptt.expired()


def test_force_stop_clears_active_and_expired():
    ptt, clock = make(0.0)
    ptt.feed(TRIGGER, True)
    clock["t"] = PushToTalk.MAX_RECORDING_S
    ptt.force_stop()
    assert not ptt.active
    assert not ptt.expired()
    # And a fresh press afterwards works exactly like any other start.
    assert ptt.feed(TRIGGER, True) == "start"
