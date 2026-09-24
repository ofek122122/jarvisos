"""HealthBeat — what an off-schedule `sys.health` beat does to the schedule.

The clock is injected, so every case here is exact rather than nearly:
no sleeping, no tolerance windows, and a boundary that is asserted ON the
boundary instead of either side of it.
"""

import pytest

from jarvis_bus import HealthBeat


class Clock:
    """A monotonic clock a test can drive."""

    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def test_a_clock_nobody_has_beaten_is_due():
    """The first thing a service says about itself is that it is up, and it
    says it on its first pass rather than one period in."""
    beats = HealthBeat(5.0, now=Clock())
    assert beats.due


def test_nothing_is_owed_until_the_period_has_run():
    clock = Clock()
    beats = HealthBeat(5.0, now=clock)
    beats.beat()
    assert not beats.due
    clock.advance(4.999)
    assert not beats.due


def test_the_period_is_a_deadline_and_not_a_gap():
    """`period_s` is the NOMINAL interval (schemas/sys.health.json), so the
    beat is owed AT it, not after it — a strictly-greater test would make
    every beat land one poll late, forever."""
    clock = Clock()
    beats = HealthBeat(5.0, now=clock)
    beats.beat()
    clock.advance(5.0)
    assert beats.due


def test_an_off_schedule_beat_takes_over_the_period():
    """THE RULE. A state change beats immediately; that beat is this
    period's beat. A service that left the timer alone would publish the
    next periodic frame however long was left on it — which is what erases
    a `degraded` milliseconds after announcing it."""
    clock = Clock()
    beats = HealthBeat(5.0, now=clock)
    beats.beat()            # periodic
    clock.advance(4.9)
    beats.beat()            # the fault, 100 ms before the periodic was due
    clock.advance(0.1)
    assert not beats.due, "the periodic beat still fired on the old schedule"
    clock.advance(4.9)
    assert beats.due, "the fault beat did not start a period of its own"


def test_two_consecutive_beats_are_never_more_than_a_period_apart():
    """The reset can only ever DELAY a beat, so a consumer that presumes a
    service dead after two missed periods must not be able to see one —
    whatever the faults do, some beat lands within every period."""
    clock = Clock()
    beats = HealthBeat(5.0, now=clock)
    last = clock.t
    beats.beat()
    for step in (1.0, 0.2, 5.0, 4.9, 0.1, 3.3, 5.0):
        clock.advance(step)
        if beats.due:
            beats.beat()
            last = clock.t
        assert clock.t - last <= 5.0


def test_the_period_rides_on_the_object_because_the_body_must_declare_it():
    """Every heartbeat body carries `period_s`, and a beat whose declared
    period disagreed with the clock enforcing it would send consumers
    timing out against a number nothing honours."""
    assert HealthBeat(0.75, now=Clock()).period_s == 0.75


def test_a_period_of_zero_is_refused_here_rather_than_on_the_bus():
    """The schema's `exclusiveMinimum: 0` is the contract; a clock that
    accepted 0 would beat every pass of a 100 ms poll loop and the frames
    would validate."""
    with pytest.raises(ValueError):
        HealthBeat(0.0, now=Clock())
    with pytest.raises(ValueError):
        HealthBeat(-1.0, now=Clock())
