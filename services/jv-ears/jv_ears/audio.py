"""Audio sources. The pipeline consumes int16 mono chunks at 16 kHz from
anything implementing chunks() — the mic on ares, WAV files in tests and
the replay harness. This is the seam the brief demands."""

from __future__ import annotations

import dataclasses
import queue
import time
from pathlib import Path
from typing import Iterable, Iterator, Optional, Sequence

import numpy as np


@dataclasses.dataclass(frozen=True)
class Loss:
    """Audio the room produced that the pipeline never saw.

    Two different facts with two different fixes, so they are two different
    fields rather than one total — the same reasoning that keeps the HUD's
    OutputState saying "muted" and "zero" instead of "silent":

      samples   frames jv-ears itself discarded because its queue was full,
                i.e. this process was too slow. The size is known exactly:
                PortAudio tells the callback how many frames it is holding.
      overruns  times the DEVICE discarded input before the callback ran.
                How much is not knowable — PortAudio reports the event and
                not its length — so it is a count and never a duration. A
                number that stops meaning its label is worse than no number.

    `last_at` is a reading of the source's clock at the most recent loss of
    either kind, and None when there has never been one. "Never" is not a
    time, exactly as `CaptureMeter.age_s` is None rather than infinite
    before the first chunk: a zero stamp would make every brand-new
    microphone look like one that just lost audio.
    """

    samples: int = 0
    overruns: int = 0
    last_at: Optional[float] = None


class AudioSource:
    """Yields consecutive int16 mono chunks of exactly chunk_samples."""

    def loss(self) -> Loss:
        """What this source discarded before the pipeline could have it.

        Nothing, for every source that reads from a disk: a WAV file cannot
        fall behind. Overridden by MicSource, which can and does. Reported
        rather than assumed — a source that cannot answer is not a source
        that lost nothing, but for the one claim this feeds (is the
        microphone losing audio right now) they are the same silence, and
        silence is the direction every claim about the microphone errs in.
        """
        return Loss()

    def chunks(self) -> Iterator[np.ndarray]:  # pragma: no cover - interface
        raise NotImplementedError


class WavSource(AudioSource):
    """Reads WAV file(s) as one continuous stream. Files must be 16 kHz
    mono 16-bit (the fixture generator guarantees this). Pads the tail
    with silence so trailing speech still flushes through VAD."""

    def __init__(
        self,
        paths: Sequence[Path] | Iterable[Path],
        chunk_samples: int = 1280,
        tail_silence_s: float = 3.0,
        sample_rate: int = 16_000,
    ) -> None:
        self.paths = [Path(p) for p in paths]
        self.chunk = chunk_samples
        self.rate = sample_rate
        self.tail = int(tail_silence_s * sample_rate)

    def chunks(self) -> Iterator[np.ndarray]:
        import soundfile as sf

        buf = np.zeros(0, dtype=np.int16)
        for path in self.paths:
            data, rate = sf.read(path, dtype="int16", always_2d=True)
            if rate != self.rate:
                raise ValueError(f"{path}: {rate} Hz, expected {self.rate}")
            mono = data[:, 0]
            buf = np.concatenate([buf, mono])
            while len(buf) >= self.chunk:
                yield buf[: self.chunk]
                buf = buf[self.chunk :]
        buf = np.concatenate([buf, np.zeros(self.tail, dtype=np.int16)])
        while len(buf) >= self.chunk:
            yield buf[: self.chunk]
            buf = buf[self.chunk :]


class MicSource(AudioSource):
    """Live microphone via sounddevice (PortAudio -> PipeWire on ares).
    TODO(machine): exit-checklist runs use this; fixture tests never do.

    The queue between PortAudio's thread and the pipeline is bounded and
    drop-newest, which is the right policy — blocking in an audio callback
    is how a device stops working altogether — but for a long time the two
    discards under it were `pass` with nothing counting them, and the
    `status` one carried a comment saying "overruns are logged by the
    caller via health" while nothing anywhere logged one. So a pipeline
    that fell behind lost whole chunks of the room and `CaptureMeter`, which
    counts what it was HANDED, went on reporting a fresh, flowing, healthy
    microphone. That is the 2026-09-15 field bug's twin: jv-ears up and
    cheerful with the audio gone.

    Now both are counted, and `loss()` is how the meter above sees them.
    The queue policy is unchanged — this is a measurement, not a fix.

    Threading: the counters have exactly one writer, PortAudio's callback
    thread, and are read from the asyncio loop. Plain integers and a plain
    float, so the reads are GIL-atomic — the same rule CaptureMeter's own
    gauges and the pipeline's suppression flags follow.
    """

    # How deep the hand-off queue is. 64 chunks of 80 ms is over five
    # seconds of slack; past that the pipeline is not late, it is stuck.
    QUEUE_CHUNKS = 64

    def __init__(
        self,
        chunk_samples: int = 1280,
        sample_rate: int = 16_000,
        *,
        clock=None,
    ) -> None:
        self.chunk = chunk_samples
        self.rate = sample_rate
        # Defaults to the same clock CaptureMeter defaults to, which is what
        # makes the meter's "how long ago" arithmetic legal: it subtracts a
        # stamp taken here from a reading taken there. Injectable so a test
        # can hand both of them one clock it winds by hand.
        self.clock = clock or time.monotonic
        self.lost_samples = 0
        self.overruns = 0
        self.last_loss_at: Optional[float] = None

    def loss(self) -> Loss:
        return Loss(self.lost_samples, self.overruns, self.last_loss_at)

    def callback(self, q: "queue.Queue[np.ndarray]"):
        """The PortAudio callback, built against one queue.

        A method rather than a closure inside `chunks()` so that the only
        code on this machine which decides what counts as lost audio can be
        called without a sound card. It must never raise: an exception on
        PortAudio's thread does not reach a log, it ends the stream — the
        one outcome worse than a dropped chunk.
        """

        def on_audio(indata, frames, time_info, status) -> None:
            if _overflowed(status):
                # The device discarded input before we ran. Counted, never
                # converted into seconds — see Loss.
                self.overruns += 1
                self.last_loss_at = self.clock()
            try:
                # .copy() is load-bearing: PortAudio reuses this buffer
                # between callbacks, so a view would be rewritten under the
                # pipeline thread.
                q.put_nowait(indata[:, 0].copy())
            except queue.Full:
                # drop-oldest is the bus policy; here we drop-newest, and
                # `frames` is PortAudio's own count of what went with it.
                self.lost_samples += int(frames)
                self.last_loss_at = self.clock()

        return on_audio

    def chunks(self) -> Iterator[np.ndarray]:
        import sounddevice as sd

        q: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=self.QUEUE_CHUNKS)

        with sd.InputStream(
            samplerate=self.rate,
            channels=1,
            dtype="int16",
            blocksize=self.chunk,
            callback=self.callback(q),
        ):
            while True:
                yield q.get()


def _overflowed(status) -> bool:
    """Did PortAudio tell us it threw input away?

    `sounddevice.CallbackFlags` is truthy for output underflows and for
    priming too, and neither is audio this machine failed to hear. Reading
    the one flag that means discarded input keeps a fault off the heartbeat
    that never happened; `getattr` keeps a status object shaped differently
    from being an exception on the audio thread.
    """
    return bool(getattr(status, "input_overflow", False))


class CaptureMeter(AudioSource):
    """Proof that audio is actually arriving from the device.

    Wraps any AudioSource and counts what it delivers, so sys.health can
    report the one thing only jv-ears can see: whether the microphone is
    open AND flowing. The HUD's live-mic indicator rides on these gauges
    (CLAUDE.md invariant 10 — not optional, and not fakeable), and an
    indicator fed by "the process is alive" would have stayed lit through
    the 2026-09-15 field bug, where PortAudio opened nothing and the
    stream delivered silence forever.

    Gauges go out on sys.health.metrics, which the schema declares
    free-form and service-local on purpose: nothing frozen changes here.

    Threading: the pipeline thread writes, the asyncio loop reads. Each
    field has exactly one writer and is a plain attribute, so reads are
    GIL-atomic — the same rule the pipeline's suppression flags follow.
    """

    # How long a live microphone may deliver nothing before the heartbeat
    # stops calling itself "ok". Chunks arrive every ~80 ms, so a full
    # second of nothing is a stream that has stopped, not a slow one.
    STALL_S = 1.0

    # How long a discarded chunk keeps meaning "this microphone is losing
    # audio". A DIFFERENT budget from STALL_S and deliberately not derived
    # from it: that one bounds how long nothing arriving is still a slow
    # stream, this one bounds how long a hole in the recording is still
    # news. It happens to be the same second, for a different reason — one
    # lost chunk is 80 ms of a room, and a second of honesty about it is
    # the smallest window in which a reader can see that it happened at all.
    #
    # It rides on the heartbeat beside STALL_S, and it did not always: B7
    # held it off the bus for one iteration, because a gauge nobody consumes
    # is noise and a second thing to keep true. What reads it now is the
    # HUD's MicState (PLAN A84), which draws a fourth word for a device that
    # is open, delivering, and losing chunks — and which has to judge the
    # same boundary this class judges, from the same number, or the plate
    # will one day contradict the heartbeat it was drawn from.
    LOSS_S = 1.0

    def __init__(
        self,
        source: AudioSource,
        *,
        mic: bool,
        sample_rate: int = 16_000,
        clock=None,
    ) -> None:
        self.source = source
        self.mic = mic
        self.rate = sample_rate
        self.clock = clock or time.monotonic
        self.samples = 0
        # None until the device has delivered anything at all. "Never" is
        # not an age, and it must never be published as one.
        self.last_at: Optional[float] = None

    def chunks(self) -> Iterator[np.ndarray]:
        for chunk in self.source.chunks():
            self.samples += len(chunk)
            self.last_at = self.clock()
            yield chunk

    @property
    def captured_s(self) -> float:
        """Seconds of audio the device has handed us since start."""
        return self.samples / self.rate

    @property
    def age_s(self) -> Optional[float]:
        """Seconds since the last chunk, or None if there has never been one."""
        return None if self.last_at is None else self.clock() - self.last_at

    def metrics(self) -> dict:
        """The free-form numeric gauges for sys.health.

        `capture_age_s` is absent rather than infinite when nothing has
        arrived: the HUD bridge serializes frames with json.dumps, which
        writes a bare `Infinity` that no JSON parser accepts — the line
        would be dropped whole and the HUD would go blind.

        `capture_stall_s` is the budget this meter judges by, not a
        measurement, so it rides along from the very first heartbeat —
        before any audio has arrived is exactly when a consumer needs it.
        The HUD used to keep its own copy of STALL_S with a "keep this in
        step with jv-ears" comment; only the service that enforces a
        budget can state it (PLAN A14).

        `capture_loss_age_s` and `capture_loss_window_s` are the same pair
        one fault along: the measurement is absent until there is something
        to measure, the budget ships from the first beat. What is NOT here
        is how much audio was lost. It is in `notes`, named by culprit,
        because half of it can never be a number — a device overrun has no
        length (see Loss) — and a gauge that reads zero through a run that
        lost audio only that way would be a number that stopped meaning its
        label.
        """
        out = {
            "mic_open": 1.0 if self.mic else 0.0,
            "captured_s": float(self.captured_s),
            "capture_stall_s": float(self.STALL_S),
            "capture_loss_window_s": float(self.LOSS_S),
        }
        age = self.age_s
        if age is not None:
            out["capture_age_s"] = float(age)
        loss_age = self.loss_age_s()
        if loss_age is not None:
            out["capture_loss_age_s"] = float(loss_age)
        return out

    def loss(self) -> Loss:
        """What the source under this meter threw away. See AudioSource.loss."""
        return self.source.loss() if hasattr(self.source, "loss") else Loss()

    def loss_age_s(self) -> Optional[float]:
        """Seconds since the last lost chunk, or None if none was ever lost."""
        at = self.loss().last_at
        return None if at is None else self.clock() - at

    def health(self) -> tuple:
        """(state, notes) for the heartbeat — see schemas/sys.health.json.

        Only a microphone can stall or lose chunks. A --wav run has no
        device to lose and no queue to overflow: the file ends, the process
        exits, and calling that "degraded" would cry wolf on every fixture
        run in the replay harness.

        The order of the two faults is a decision. A stall outranks a loss
        because "no audio at all" is the bigger fact and the reader needs it
        first — they are both `degraded`, so the only thing at stake is
        which note goes out. And a LOSS outranks `starting`, which reads
        backwards until you see the case: the queue can fill before the
        pipeline thread has pulled its first chunk, so `capture_age_s` is
        still absent while audio is already being discarded. A discard is
        evidence the device is delivering; refusing it there would be the
        meter throwing away the only thing it knows.

        Why `degraded` at all, rather than a gauge nobody has to act on:
        jv-ears already calls a silent device degraded, this is the same
        publisher reporting the same class of fault — audio that did not
        reach the pipeline — and `degraded` is in the frozen enum, so
        nothing about the schema moves. The flapping worry that stalls the
        same question for the broker (PLAN A76) does not apply here:
        `main.HEALTH_MIN_GAP_S` already floors the transition beat at one
        second, so a device dropping chunks in bursts cannot turn
        `sys.health` into a 4 Hz topic.
        """
        if not self.mic:
            return "ok", None
        age = self.age_s
        if age is not None and age > self.STALL_S:
            return "degraded", f"microphone open but no audio for {age:.1f}s"
        loss_age = self.loss_age_s()
        if loss_age is not None and loss_age <= self.LOSS_S:
            return "degraded", self.loss_note()
        if age is None:
            return "starting", None
        return "ok", None

    def loss_note(self) -> str:
        """Who lost the audio and how much of it, in one line.

        Both halves are cumulative since start, which is said out loud: the
        reader is being told a total, while the STATE beside it is what says
        it is still happening. The two losses are named separately because
        they send you to different places — jv-ears dropping chunks is this
        process falling behind (the partial re-transcribe on the perception
        thread, docs/optimization-backlog.md §2 and §6), and a device
        overrun is the machine or the driver. A single number would average
        two different bug reports into one.
        """
        lost = self.loss()
        parts = []
        if lost.samples:
            parts.append(f"jv-ears dropped {lost.samples / self.rate:.1f}s")
        if lost.overruns:
            plural = "" if lost.overruns == 1 else "s"
            parts.append(f"{lost.overruns} device overrun{plural} (length unknown)")
        return "microphone losing audio: " + " and ".join(parts) + " since start"
