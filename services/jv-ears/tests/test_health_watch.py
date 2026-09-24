"""The heartbeat says "degraded" when it happens, not up to 5 s later.

`schemas/sys.health.json` asks every service for a beat "every fixed
period, and immediately on state change". jv-ears published on a timer
alone, so the one failure it exists to report — a live microphone that
has stopped delivering audio (the 2026-09-15 field bug) — was up to a
full HEALTH_PERIOD_S of silence, and `jv health --check` reads a 6 s
window: one nominal period plus a margin, so a change landing just after
a beat is a change that check can miss.

jv-context solved the same problem with an `asyncio.Event` set by the
writer (PLAN B35), and that shape does not fit here: jv-ears' state is a
function of a CLOCK. Nothing calls a setter when a stream stalls — the
age of the last chunk simply crosses CaptureMeter.STALL_S while no code
of ours runs. A state nobody announces has to be WATCHED, so
`pump_health` re-reads it on a short interval and publishes when the
bus's last word has stopped being true.

No mic, no bus, no real time: the state is a script, the clock is a
counter the fake sleep winds by hand, so every assertion below is about
seconds without spending any.
"""

from __future__ import annotations

import asyncio

import pytest

from jv_ears.main import (
    HEALTH_MIN_GAP_S,
    HEALTH_PERIOD_S,
    HEALTH_WATCH_S,
    pump_health,
)

TICKS_PER_PERIOD = int(HEALTH_PERIOD_S / HEALTH_WATCH_S)
TICKS_PER_FLOOR = int(HEALTH_MIN_GAP_S / HEALTH_WATCH_S)
# Long enough after the caller's own hello beat that the floor is not the
# rule under test.
QUIET = ["ok"] * (TICKS_PER_FLOOR + 1)


class Ticker:
    """A monotonic clock wound by the sleeps the pump itself awaits.

    `await sleep(s)` advances the clock by exactly s and yields to the
    event loop, so the pump runs its whole schedule in no real time and
    every beat can be dated to the millisecond.
    """

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += seconds
        await asyncio.sleep(0)


class Script:
    """The states the meter reports, one per watch tick, then the end.

    `is_set` is the `done` protocol main.py hands the pump (the pipeline
    thread's exit flag): it goes true when the script runs out, so the
    pump returns on its own and no test has to cancel a task. State `j`
    is what the meter says at t = (j + 1) * watch_s.
    """

    def __init__(self, states: list[str], first: str) -> None:
        self.remaining = list(states)
        self.current = first

    def state(self) -> str:
        return self.current

    def is_set(self) -> bool:
        return not self.remaining

    def tick(self) -> None:
        self.current = self.remaining.pop(0)


async def run_pump(states: list[str], *, first: str = "ok"):
    """Drive the pump through `states` and return [(t, state), ...].

    `first` is both the meter's state before the first tick and the state
    the caller's own hello beat carried — main.py beats once before
    starting the pump, so the bus already has a last word.
    """
    script = Script(states, first)
    clock = Ticker()
    beats: list[tuple[float, str]] = []
    said = [first]

    async def beat() -> None:
        # What a real beat does: read the state, publish it, and that
        # frame is now the bus's last word.
        said[0] = script.state()
        beats.append((clock.now, said[0]))

    async def sleep(seconds: float) -> None:
        await clock.sleep(seconds)
        script.tick()

    await pump_health(
        beat,
        script.state,
        said=lambda: said[0],
        done=script,
        now=clock,
        sleep=sleep,
    )
    return beats


# --- the reason this exists ----------------------------------------------


def test_a_stalled_microphone_is_published_on_the_tick_it_is_seen():
    # The whole point: the mic dies mid-period and the bus hears about it
    # now, on the watch tick that saw it, not at the end of the period.
    beats = asyncio.run(run_pump(QUIET + ["degraded"] * 3))
    seen_at = (len(QUIET) + 1) * HEALTH_WATCH_S
    assert beats == [(pytest.approx(seen_at), "degraded")]
    assert seen_at < HEALTH_PERIOD_S


def test_the_microphone_coming_back_is_news_too():
    # A degraded service that recovers in silence leaves the HUD and
    # `jv health` red until the next periodic beat.
    quiet = ["degraded"] * (TICKS_PER_FLOOR + 1)
    beats = asyncio.run(run_pump(quiet + ["ok"] * 3, first="degraded"))
    assert beats == [(pytest.approx((len(quiet) + 1) * HEALTH_WATCH_S), "ok")]


def test_the_first_audio_ends_starting_on_its_own_tick():
    # `starting` -> `ok` is the transition that tells every consumer the
    # microphone is really live (invariant 10); on a device that takes a
    # moment to open, that news used to wait out a period.
    quiet = ["starting"] * (TICKS_PER_FLOOR + 1)
    beats = asyncio.run(run_pump(quiet + ["ok"], first="starting"))
    assert [s for _, s in beats] == ["ok"]


# --- and it is still a quiet topic --------------------------------------


def test_a_steady_state_beats_once_a_period_and_no_more():
    # Two periods of watch ticks with nothing changing: two beats, on the
    # period. Anything more and the watch has turned a 0.2 Hz heartbeat
    # into a busy topic (invariant 5).
    beats = asyncio.run(run_pump(["ok"] * (2 * TICKS_PER_PERIOD)))
    assert [t for t, _ in beats] == [
        pytest.approx(HEALTH_PERIOD_S),
        pytest.approx(2 * HEALTH_PERIOD_S),
    ]


def test_a_state_change_resets_the_period():
    # The beat that reported the change IS this period's beat. Leaving the
    # timer alone would publish the same frame again moments later,
    # whenever the change happened to land near a period boundary.
    change_at = HEALTH_PERIOD_S - 4 * HEALTH_WATCH_S
    ticks = ["ok"] * (TICKS_PER_PERIOD - 5) + ["degraded"] * 8
    beats = asyncio.run(run_pump(ticks))
    assert beats == [(pytest.approx(change_at), "degraded")]
    # ...and specifically NOT a second beat at the period it pre-empted.
    assert all(t != pytest.approx(HEALTH_PERIOD_S) for t, _ in beats)


def test_a_flapping_microphone_cannot_beat_faster_than_the_floor():
    # A device delivering a chunk just either side of STALL_S flaps
    # between ok and degraded, and every flap is a real state change.
    # Without a floor that is a heartbeat at the watch rate — 4 Hz on a
    # topic meant to be quiet. Each flap still gets out; it gets out at
    # the floor.
    beats = asyncio.run(run_pump(["degraded", "ok"] * 12))
    assert beats, "a flapping mic published nothing"
    gaps = [b[0] - a[0] for a, b in zip(beats, beats[1:])]
    assert all(g >= HEALTH_MIN_GAP_S - 1e-9 for g in gaps), gaps
    assert HEALTH_MIN_GAP_S < HEALTH_PERIOD_S  # or the floor IS the timer


def test_a_change_that_undoes_itself_inside_the_floor_is_not_news():
    # It flickered to degraded and back while the floor held the beat.
    # The bus's last word is `ok` and still true, so there is nothing to
    # say: a beat here would report a state that has already ended.
    beats = asyncio.run(run_pump(["degraded", "ok"] + ["ok"] * 4))
    assert beats == []


def test_the_note_is_not_watched_only_the_state():
    # jv-ears' degraded note embeds the age of the last chunk ("no audio
    # for 3.2s"), so a pump that woke on the NOTE changing would beat on
    # every tick for as long as the fault lasted. Only the enum is
    # compared; the growing note rides out on the periodic beat.
    beats = asyncio.run(run_pump(["degraded"] * TICKS_PER_PERIOD, first="degraded"))
    assert [t for t, _ in beats] == [pytest.approx(HEALTH_PERIOD_S)]


def test_a_finished_pipeline_stops_the_pump():
    # `done` is the pipeline thread's exit flag. A --wav run that ends
    # must not leave a task beating about a microphone that was never
    # there.
    assert asyncio.run(run_pump([])) == []  # returns, rather than hanging


# --- and main() actually uses it ----------------------------------------


def test_main_watches_the_real_meter(monkeypatch):
    """The pump above is worth nothing if amain() feeds it a constant.

    Captures what main.py hands the pump: the state it watches, the state
    it compares against, and the body it publishes must all come from the
    SAME meter — otherwise the watch is watching something the HUD is not
    shown.
    """
    import jv_ears.main as main_mod

    published: list[tuple[str, dict]] = []
    seen: dict = {}

    class RecordingBus:
        async def publish(self, topic, body, **kw):
            published.append((topic, body))

        async def subscribe(self, topics):
            pass

        async def next_frame(self):
            await asyncio.Event().wait()

        async def close(self):
            pass

    class Client:
        @staticmethod
        async def connect(*a, **k):
            return RecordingBus()

    class Pipeline:
        def __init__(self, cfg, publish):
            pass

        def run(self, source):
            pass  # ends at once, like --wav running out of files

        def budgets(self):
            return {"wake_timeout_s": 8.0}

    async def fake_pump(beat, state_of, *, said, done, **kw):
        seen["state"] = state_of()
        seen["said_before"] = said()
        await beat()
        seen["said_after"] = said()

    # Make the pump's own beat report something the meter does NOT say, so
    # `said` cannot pass this test by reading the meter twice.
    real_body = main_mod.health_body
    bodies: list[dict] = []

    def counting_body(meter, uptime_s, budgets):
        body = real_body(meter, uptime_s, budgets)
        bodies.append(body)
        if len(bodies) > 1:
            body["state"] = "degraded"
        return body

    monkeypatch.setattr(main_mod, "health_body", counting_body)
    monkeypatch.setattr(main_mod, "BusClient", Client)
    monkeypatch.setattr(main_mod, "MicSource", lambda *a, **k: object())
    monkeypatch.setattr(main_mod, "EarsPipeline", Pipeline)
    monkeypatch.setattr(main_mod, "pump_health", fake_pump)
    assert asyncio.run(main_mod.amain([])) == 0

    health = [b for t, b in published if t == "sys.health"]
    assert len(health) >= 2, "the pump's own beat never reached the bus"
    # A microphone that has delivered nothing yet is `starting`, and that
    # is what the watch must be reading.
    assert seen["state"] == "starting"
    assert health[0]["state"] == "starting"
    # `said` is the hello beat that went out before the pump existed...
    assert seen["said_before"] == health[0]["state"]
    # ...and then the frame the pump's own beat published — the bus's word,
    # not a second look at the meter (which still says `starting`).
    assert health[1]["state"] == "degraded"
    assert seen["said_after"] == "degraded"
