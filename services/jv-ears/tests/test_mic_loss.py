"""The audio this machine captured and then threw away.

`CaptureMeter` counts what the DEVICE delivered, which is the wrong side of
the queue. Between PortAudio and the pipeline sits a `queue.Queue(maxsize=64)`
with `except queue.Full: pass` under it, and above that PortAudio's own
`status` flags — which were ignored under a comment claiming "overruns are
logged by the caller via health" while nothing logged anything. So a pipeline
that fell behind (the O(n^2) partial re-transcribe, optimization-backlog §2)
lost whole chunks of the room and the heartbeat went on saying `ok` with a
fresh `capture_age_s` and a rising `captured_s`: the 2026-09-15 field bug's
twin, ears up and cheerful with the audio gone.

Two losses, and they are NOT the same fact:

  jv-ears dropped it   the queue was full because this process was too slow.
                       We know exactly how much: the callback is told how
                       many frames it is holding.
  the device dropped it PortAudio discarded input before the callback ran.
                       We know it happened and never how much.

They have different fixes, so they are different words in the note — the same
reason OutputState says "muted" and "zero" rather than "silent".

No hardware here: the callback is called by hand with a fake queue, a fake
status object and a clock the test winds.
"""

from __future__ import annotations

import queue

import numpy as np
import pytest

from jv_ears.audio import CaptureMeter, Loss, MicSource

RATE = 16_000


class FakeClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class FakeStatus:
    """Stands in for sounddevice's CallbackFlags: truthy if any flag is set."""

    def __init__(self, *, input_overflow=False, output_underflow=False) -> None:
        self.input_overflow = input_overflow
        self.output_underflow = output_underflow

    def __bool__(self) -> bool:
        return self.input_overflow or self.output_underflow


class LosingSource:
    """An AudioSource that yields what it was given and reports a loss."""

    def __init__(self, loss: Loss, chunks=()) -> None:
        self._loss = loss
        self._chunks = list(chunks)

    def chunks(self):
        return iter(self._chunks)

    def loss(self) -> Loss:
        return self._loss


class MuteSource:
    """An AudioSource with no opinion about loss at all — a WAV file, the
    replay harness, anything that cannot lose audio it reads off a disk."""

    def chunks(self):
        return iter(())


def indata(frames: int = 1280, channels: int = 2) -> np.ndarray:
    return np.zeros((frames, channels), dtype=np.int16)


def mic(clock=None) -> MicSource:
    return MicSource(chunk_samples=1280, sample_rate=RATE, clock=clock or FakeClock())


def meter(source, *, mic=True, clock=None) -> CaptureMeter:
    return CaptureMeter(source, mic=mic, sample_rate=RATE, clock=clock or FakeClock())


# --- the callback: what it keeps, and what it admits losing ---------------


def test_a_fresh_microphone_claims_no_loss_at_all():
    # "Never lost any" has to be distinguishable from "lost some at time 0",
    # or a meter reading the stamp would call a brand-new device degraded.
    assert mic().loss() == Loss()
    assert mic().loss().last_at is None


def test_a_chunk_that_fits_is_queued_and_nothing_is_counted_as_lost():
    m = mic()
    q: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=2)
    m.callback(q)(indata(), 1280, None, None)
    assert q.qsize() == 1
    assert m.loss() == Loss()


def test_the_queue_receives_channel_zero_as_a_copy_not_a_view():
    # PortAudio reuses its buffer between callbacks, so a view would be
    # rewritten under the pipeline. `.copy()` is load-bearing.
    m = mic()
    q: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=2)
    buf = indata(4)
    buf[:, 0] = [1, 2, 3, 4]
    buf[:, 1] = 9
    m.callback(q)(buf, 4, None, None)
    got = q.get_nowait()
    assert got.tolist() == [1, 2, 3, 4]
    buf[:, 0] = 0
    assert got.tolist() == [1, 2, 3, 4]


def test_a_full_queue_counts_the_frames_it_discarded_and_stamps_when():
    clock = FakeClock(5.0)
    m = mic(clock)
    q: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=1)
    cb = m.callback(q)
    cb(indata(), 1280, None, None)  # fills it
    cb(indata(640), 640, None, None)  # dropped
    assert m.loss() == Loss(samples=640, overruns=0, last_at=5.0)


def test_every_discard_moves_the_stamp_forward():
    # The stamp is what says the fault is CURRENT, so a stamp that only ever
    # records the first loss makes a microphone that has been dropping chunks
    # for an hour look like one that dropped one at startup.
    #
    # The clock starts away from zero on purpose: a mutation run caught this
    # test passing for the wrong reason at `FakeClock()`, because 0.0 is falsy
    # in Python and `self.last_loss_at or self.clock()` therefore restamped
    # the first loss anyway. A window whose first reading is 0 cannot tell a
    # kept stamp from a replaced one.
    clock = FakeClock(4.0)
    m = mic(clock)
    q: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=1)
    cb = m.callback(q)
    cb(indata(), 1280, None, None)
    cb(indata(), 1280, None, None)
    assert m.loss().last_at == 4.0
    clock.now = 12.0
    cb(indata(), 1280, None, None)
    assert m.loss().samples == 2560
    assert m.loss().last_at == 12.0


def test_a_device_overflow_is_counted_but_never_converted_into_seconds():
    # PortAudio says input was discarded and not how much of it. A duration
    # invented here would be a number that stops meaning its label.
    clock = FakeClock(3.0)
    m = mic(clock)
    q: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=4)
    m.callback(q)(indata(), 1280, None, FakeStatus(input_overflow=True))
    assert m.loss() == Loss(samples=0, overruns=1, last_at=3.0)
    assert q.qsize() == 1  # the chunk we DID get still goes through


def test_a_flag_that_is_not_about_discarded_input_claims_nothing():
    # CallbackFlags is truthy for output underflows and priming too. Calling
    # those lost audio would put a fault on screen that never happened.
    m = mic()
    q: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=4)
    m.callback(q)(indata(), 1280, None, FakeStatus(output_underflow=True))
    assert m.loss() == Loss()


def test_an_overflow_and_a_full_queue_in_one_callback_count_once_each():
    clock = FakeClock(2.0)
    m = mic(clock)
    q: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=1)
    cb = m.callback(q)
    cb(indata(), 1280, None, None)
    cb(indata(320), 320, None, FakeStatus(input_overflow=True))
    assert m.loss() == Loss(samples=320, overruns=1, last_at=2.0)


def test_the_callback_never_raises_whatever_it_is_handed():
    # It runs on PortAudio's thread. An exception there does not reach a
    # log, it ends the stream — the one outcome worse than a dropped chunk.
    m = mic()
    q: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=1)
    cb = m.callback(q)
    cb(indata(), 1280, None, object())  # a status with no flags on it
    cb(indata(), 1280, None, object())  # ...onto a full queue
    assert m.loss().samples == 1280


# --- the meter: a source that cannot lose audio, and one that did ---------


def test_a_source_that_cannot_report_loss_is_never_said_to_have_lost_any():
    # A WAV file does not drop chunks. The meter under-claims here, which is
    # the direction every claim about the microphone errs in.
    m = meter(MuteSource())
    assert m.loss() == Loss()
    assert m.health() == ("starting", None)


def test_a_microphone_losing_audio_right_now_is_degraded():
    clock = FakeClock(10.0)
    m = meter(LosingSource(Loss(samples=1600, last_at=9.5)), clock=clock)
    state, notes = m.health()
    assert state == "degraded"
    assert notes and "losing audio" in notes


def test_a_loss_older_than_the_window_stops_being_news():
    # The hole in the recording is still in `lost_samples` forever — it is a
    # total since start. What ends is the CLAIM that it is happening now.
    clock = FakeClock(10.0)
    src = LosingSource(
        Loss(samples=1600, last_at=10.0 - CaptureMeter.LOSS_S - 0.1),
        chunks=[np.zeros(1280, dtype=np.int16)],
    )
    m = meter(src, clock=clock)
    list(m.chunks())
    assert m.loss().samples == 1600
    assert m.health() == ("ok", None)


def test_a_loss_exactly_at_the_window_is_still_news():
    # The same boundary the stall rule draws: `> STALL_S` is a stall, so a
    # device that has just reached the budget is still ok. Here a loss that
    # has just reached LOSS_S is still being reported. Pinned because an
    # off-by-one on a window is invisible in every test that uses a margin.
    clock = FakeClock(10.0)
    m = meter(LosingSource(Loss(samples=800, last_at=10.0 - CaptureMeter.LOSS_S)), clock=clock)
    assert m.health()[0] == "degraded"


def test_a_clock_that_ran_backwards_is_not_a_loss_from_the_future():
    # Two readings of one monotonic clock cannot invert, but the stamp is
    # taken on PortAudio's thread and read on the asyncio loop, and a
    # negative age must not fall through the `<=` as "not recent".
    clock = FakeClock(1.0)
    m = meter(LosingSource(Loss(samples=800, last_at=2.0)), clock=clock)
    assert m.health()[0] == "degraded"


def test_the_note_says_jv_ears_dropped_it_and_how_much():
    clock = FakeClock(1.0)
    m = meter(LosingSource(Loss(samples=RATE // 2, last_at=1.0)), clock=clock)
    _, notes = m.health()
    assert "jv-ears dropped 0.5s" in notes
    assert "overrun" not in notes


def test_the_note_says_the_device_dropped_it_and_admits_it_cannot_say_how_much():
    clock = FakeClock(1.0)
    m = meter(LosingSource(Loss(overruns=2, last_at=1.0)), clock=clock)
    _, notes = m.health()
    assert "2 device overrun" in notes
    assert "unknown" in notes
    assert "dropped 0.0s" not in notes


def test_the_note_names_both_losses_when_both_happened():
    clock = FakeClock(1.0)
    m = meter(LosingSource(Loss(samples=RATE, overruns=3, last_at=1.0)), clock=clock)
    _, notes = m.health()
    assert "jv-ears dropped 1.0s" in notes
    assert "3 device overrun" in notes


def test_a_stall_outranks_a_loss_because_a_deaf_microphone_is_the_bigger_fact():
    # Both are degraded; only one note goes out, and "no audio at all" is
    # what the reader needs first.
    clock = FakeClock()
    src = LosingSource(
        Loss(samples=800, last_at=0.0), chunks=[np.zeros(1280, dtype=np.int16)]
    )
    m = meter(src, clock=clock)
    list(m.chunks())  # one chunk arrived, at t=0
    clock.now = CaptureMeter.STALL_S + 0.1
    src._loss = Loss(samples=800, last_at=clock.now)  # and a loss just now
    state, notes = m.health()
    assert state == "degraded"
    assert "no audio" in notes


def test_a_loss_outranks_starting_because_a_discard_proves_audio_arrived():
    # The queue can fill before the pipeline thread has pulled anything, so
    # `capture_age_s` is absent while audio is already being lost. "Starting"
    # there would be the meter refusing evidence it has.
    clock = FakeClock(0.2)
    m = meter(LosingSource(Loss(samples=1280, last_at=0.2)), clock=clock)
    assert m.age_s is None
    state, notes = m.health()
    assert state == "degraded"
    assert "losing audio" in notes


def test_a_wav_run_is_never_degraded_by_a_loss_it_could_not_have_had():
    clock = FakeClock(1.0)
    m = meter(LosingSource(Loss(samples=1600, last_at=1.0)), mic=False, clock=clock)
    assert m.health() == ("ok", None)


def test_the_loss_puts_no_new_gauge_on_the_bus_yet():
    """B7: a gauge nobody consumes is noise on the bus and a second thing to
    keep true. The HUD's MicState has no word for a device that is losing
    audio (PLAN A84), so the fault ships on `state` and `notes` — which every
    consumer already reads — and the numbers arrive the day something draws
    them. This test is here so that day is a decision and not a diff."""
    clock = FakeClock(1.0)
    m = meter(LosingSource(Loss(samples=1600, overruns=1, last_at=1.0)), clock=clock)
    assert set(m.metrics()) == {"mic_open", "captured_s", "capture_stall_s"}


# --- and it is actually wired to the bus ----------------------------------


def test_the_heartbeat_jv_ears_publishes_says_it_is_losing_audio(monkeypatch):
    """The unit tests above are worth nothing if main() never calls them."""
    import asyncio
    import time

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
            pass

        def budgets(self):
            return {"wake_timeout_s": 8.0}

    losing = LosingSource(Loss(samples=RATE // 4, overruns=1, last_at=time.monotonic()))
    monkeypatch.setattr(main_mod, "BusClient", Client)
    monkeypatch.setattr(main_mod, "MicSource", lambda *a, **k: losing)
    monkeypatch.setattr(main_mod, "EarsPipeline", Pipeline)
    assert asyncio.run(main_mod.amain([])) == 0

    health = [b for t, b in published if t == "sys.health"]
    assert health, "jv-ears published no heartbeat at all"
    assert health[0]["state"] == "degraded"
    assert "losing audio" in health[0]["notes"]
    assert "jv-ears dropped 0.2s" in health[0]["notes"]
    assert "1 device overrun" in health[0]["notes"]
