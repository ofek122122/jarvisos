"""CaptureMeter — the only truthful answer to "is the microphone open?".

The HUD must show a live mic indicator that is not fakeable (CLAUDE.md
invariant 10), and jv-ears is the only process that can see the device, so
it is the only one that can answer. The answer has to survive the failure
mode this repo has already met once (2026-09-15): PortAudio opened nothing,
the stream delivered no audio, and everything downstream stayed cheerfully
quiet. A heartbeat that only says "the process is alive" would have lit a
mic indicator through all of it.

So the meter counts what the DEVICE actually delivered and stamps when the
last chunk arrived. The gauges ride on sys.health.metrics, which the schema
declares free-form on purpose — no schema change, nothing frozen touched.

No hardware here: the source is a list of arrays and the clock is a list of
numbers.
"""

from __future__ import annotations

import numpy as np
import pytest

from jv_ears.audio import CaptureMeter
from jv_ears.main import HEALTH_PERIOD_S, health_body

RATE = 16_000


class FakeSource:
    """An AudioSource that yields exactly what it was given."""

    def __init__(self, chunks):
        self._chunks = list(chunks)
        self.entered = 0

    def chunks(self):
        self.entered += 1
        for c in self._chunks:
            yield c


class FakeClock:
    """A monotonic clock the test winds by hand."""

    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def chunk(n: int = 1280) -> np.ndarray:
    return np.zeros(n, dtype=np.int16)


def meter_on(chunks, *, mic=True, clock=None):
    return CaptureMeter(
        FakeSource(chunks), mic=mic, sample_rate=RATE, clock=clock or FakeClock()
    )


# --- pass-through: a meter must not change what the pipeline hears --------


def test_chunks_pass_through_untouched_and_in_order():
    a, b = chunk(), chunk(640)
    a[0], b[0] = 7, 9
    m = meter_on([a, b])
    out = list(m.chunks())
    assert [id(x) for x in out] == [id(a), id(b)]


def test_counts_the_samples_the_device_delivered():
    m = meter_on([chunk(), chunk(640)])
    assert m.captured_s == 0.0
    list(m.chunks())
    assert m.samples == 1280 + 640
    assert m.captured_s == pytest.approx(1920 / RATE)


def test_the_clock_is_read_per_chunk_not_per_stream():
    clock = FakeClock()
    m = meter_on([chunk(), chunk()], clock=clock)
    ages = []
    for _ in m.chunks():
        ages.append(m.age_s)
        clock.now += 3.0
    assert ages == [0.0, 0.0]
    assert m.age_s == 3.0


# --- "nothing has arrived yet" is not an age -----------------------------


def test_age_is_none_until_the_first_chunk_arrives():
    m = meter_on([chunk()])
    assert m.age_s is None
    assert m.metrics()["captured_s"] == 0.0
    # Never published as infinity: json.dumps would emit `Infinity`, which
    # is not JSON, and the HUD's bridge line would be dropped whole.
    assert "capture_age_s" not in m.metrics()


def test_the_gauge_appears_once_there_is_something_to_gauge():
    clock = FakeClock()
    m = meter_on([chunk()], clock=clock)
    list(m.chunks())
    clock.now += 0.25
    assert m.metrics()["capture_age_s"] == pytest.approx(0.25)


# --- what the gauges claim -----------------------------------------------


def test_mic_open_is_one_only_for_a_real_microphone():
    assert meter_on([], mic=True).metrics()["mic_open"] == 1.0
    assert meter_on([], mic=False).metrics()["mic_open"] == 0.0


def test_every_metric_is_a_float_because_the_schema_says_numbers():
    clock = FakeClock()
    m = meter_on([chunk()], clock=clock)
    list(m.chunks())
    assert all(isinstance(v, float) for v in m.metrics().values())


# --- health: a stalled stream is degraded, not ok ------------------------


def test_a_microphone_that_has_delivered_nothing_yet_is_starting():
    assert meter_on([], mic=True).health() == ("starting", None)


def test_a_flowing_microphone_is_ok():
    clock = FakeClock()
    m = meter_on([chunk()], clock=clock)
    list(m.chunks())
    assert m.health() == ("ok", None)


def test_a_microphone_that_stopped_delivering_is_degraded_with_a_note():
    clock = FakeClock()
    m = meter_on([chunk()], clock=clock)
    list(m.chunks())
    clock.now += CaptureMeter.STALL_S + 0.5
    state, notes = m.health()
    assert state == "degraded"
    assert notes and "no audio" in notes


def test_a_wav_run_is_never_degraded_because_there_is_no_microphone():
    # --wav has no device to stall: the file simply ends, and the process
    # exits. Calling that "degraded" would cry wolf on every fixture run.
    m = meter_on([chunk()], mic=False, clock=FakeClock())
    assert m.health() == ("ok", None)
    m.clock.now += 3600.0
    assert m.health() == ("ok", None)


# --- the heartbeat body --------------------------------------------------


def test_health_body_carries_the_gauges_and_the_required_fields():
    clock = FakeClock()
    m = meter_on([chunk()], clock=clock)
    list(m.chunks())
    body = health_body(m, 12.5, {})
    assert body["service"] == "jv-ears"
    assert body["state"] == "ok"
    assert body["uptime_s"] == 12.5
    assert body["period_s"] == HEALTH_PERIOD_S
    assert body["metrics"]["mic_open"] == 1.0
    assert body["metrics"]["capture_age_s"] == 0.0
    assert "notes" not in body


def test_health_body_reports_a_stall_with_its_note():
    clock = FakeClock()
    m = meter_on([chunk()], clock=clock)
    list(m.chunks())
    clock.now += 5.0
    body = health_body(m, 20.0, {})
    assert body["state"] == "degraded"
    assert "no audio" in body["notes"]


def test_health_body_keys_stay_inside_the_frozen_schema():
    allowed = {"service", "state", "uptime_s", "period_s", "drops", "metrics", "notes"}
    body = health_body(meter_on([], mic=True), 1.0, {"wake_timeout_s": 8.0})
    assert set(body) <= allowed
    # metrics is free-form but not lawless: the schema says every value is
    # a number, and the bridge serializes the frame with json.dumps.
    assert all(isinstance(v, float) for v in body["metrics"].values())


# --- the budgets the HUD used to mirror by hand (A14) ---------------------


def test_the_gauges_carry_the_stall_budget_they_are_judged_by():
    """The HUD had `stallS = 1.0` copied into QML with a "keep this at or
    above jv-ears" comment, because nothing published ears' tuning. A
    comment is not a gate: change STALL_S here and the copy over there
    would have gone on being wrong quietly. So the meter reports the
    budget it judges by, in the same frame as the age it judges."""
    m = meter_on([], mic=True, clock=FakeClock())
    assert m.metrics()["capture_stall_s"] == CaptureMeter.STALL_S


def test_the_stall_budget_is_there_before_any_audio_has_arrived():
    # `capture_age_s` is absent until the first chunk (never is not an
    # age). The budget is not a measurement and must not wait for one:
    # a mic that has NEVER delivered is exactly when the HUD needs it.
    body = health_body(meter_on([], mic=True), 0.5, {})
    assert "capture_age_s" not in body["metrics"]
    assert body["metrics"]["capture_stall_s"] == CaptureMeter.STALL_S


def test_a_wav_run_still_reports_the_budget_with_no_microphone():
    # mic_open 0 means the HUD draws nothing, but the budget is a fact
    # about jv-ears, not about the device, and stays readable.
    m = meter_on([], mic=False, clock=FakeClock())
    assert m.metrics()["capture_stall_s"] == CaptureMeter.STALL_S
    assert m.metrics()["mic_open"] == 0.0


def test_health_body_publishes_the_budgets_it_is_handed():
    body = health_body(meter_on([], mic=True), 1.0, {"wake_timeout_s": 8.0})
    assert body["metrics"]["wake_timeout_s"] == 8.0


def test_a_budget_that_is_not_a_number_never_reaches_the_bus():
    # sys.health.metrics is free-form but every value is a number, and the
    # HUD bridge writes the frame with json.dumps. A budget that is not a
    # number is a bug in jv-ears and must fail here, loudly, rather than
    # ride out as a string the HUD will refuse in silence.
    with pytest.raises((TypeError, ValueError)):
        health_body(meter_on([], mic=True), 1.0, {"wake_timeout_s": "eight"})


# --- and it is actually wired to the bus ---------------------------------


def test_the_heartbeat_jv_ears_publishes_carries_the_mic_gauges(monkeypatch):
    """The unit tests above are worth nothing if main() never calls them."""
    import asyncio

    import jv_ears.main as main_mod

    published = []

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
            pass  # a source that ends immediately, like --wav running out

        def budgets(self):
            return {"wake_timeout_s": 8.0}

    monkeypatch.setattr(main_mod, "BusClient", Client)
    monkeypatch.setattr(main_mod, "MicSource", lambda *a, **k: FakeSource([]))
    monkeypatch.setattr(main_mod, "EarsPipeline", Pipeline)
    assert asyncio.run(main_mod.amain([])) == 0

    health = [b for t, b in published if t == "sys.health"]
    assert health, "jv-ears published no heartbeat at all"
    assert health[0]["metrics"]["mic_open"] == 1.0
    assert health[0]["metrics"]["captured_s"] == 0.0
    # ...and the pipeline's own budgets, or the HUD is back to guessing.
    assert health[0]["metrics"]["wake_timeout_s"] == 8.0
    assert health[0]["metrics"]["capture_stall_s"] == CaptureMeter.STALL_S
