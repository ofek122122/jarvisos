"""When the next `sys.health` beat is due.

`schemas/sys.health.json` asks every service for a heartbeat "every fixed
period, and immediately on state change". Those are two rules, and where
they meet is a third question the schema never asks out loud: what does
an off-schedule beat do to the schedule? It ENDS it and starts a new one.
A beat is a beat — the period belongs to the beat, not to the clock it
interrupted.

Getting that wrong is not cosmetic. A service that beats `degraded` at
the instant of a fault and leaves its period timer alone publishes the
`ok` that erases it however long was left on that timer, which can be
milliseconds. `bus.latest()` keeps ONE frame per topic per publisher, so
the HUD's HealthPlate (invariant 10) and `jv health --check` both read
the newest one: a fault that was truthfully announced can be gone before
anything could show it. Resetting the timer gives every off-schedule beat
a full period of life on the bus, and it can only ever REDUCE the frames
published — it delays the periodic beat, it never adds one. Consumers
that presume a service dead after two missed periods are untouched: two
consecutive beats are still never more than one period apart.

jv-ears and jv-context already obey this in two different shapes, and
jv-ears wrote down the reason once (`pump_health`: "the period is the
beat's, not the bus's"). This is that rule, named, for the three services
whose heartbeat is a deadline inside a polling loop.
"""

from __future__ import annotations

from typing import Callable

from .client import mono_now


class HealthBeat:
    """The heartbeat deadline for one service. Owns no bus and publishes
    nothing: a service still decides WHAT to say, this decides WHEN it is
    owed, and the whole point is that both kinds of beat go through it."""

    def __init__(self, period_s: float, *, now: Callable[[], float] = mono_now) -> None:
        if period_s <= 0:
            # schemas/sys.health.json: `period_s` is exclusiveMinimum 0.
            # A zero period would beat on every pass of a 100 ms poll loop
            # and every frame would validate, so it is refused here.
            raise ValueError(f"health period must be positive, got {period_s!r}")
        self.period_s = period_s
        self._now = now
        self._last: float | None = None

    @property
    def due(self) -> bool:
        """True when a beat is owed. A clock nobody has beaten yet is due:
        the first thing a service says about itself is that it is up, and
        it says it on its first pass rather than one period in.

        The comparison is `>=`, because `period_s` is the NOMINAL interval
        the schema asks for and consumers time out against — a
        strictly-greater test would land every beat one poll late, for the
        life of the process."""
        return self._last is None or self._now() - self._last >= self.period_s

    def beat(self) -> None:
        """A heartbeat is going out NOW.

        Call this BEFORE the publish, not after. The period is the beat's,
        and awaiting the bus first would push every subsequent beat out by
        however long that publish took — a drift that compounds, on the
        one number consumers use to decide a service is dead."""
        self._last = self._now()
