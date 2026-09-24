"""Audio sources. The pipeline consumes int16 mono chunks at 16 kHz from
anything implementing chunks() — the mic on ares, WAV files in tests and
the replay harness. This is the seam the brief demands."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable, Iterator, Optional, Sequence

import numpy as np


class AudioSource:
    """Yields consecutive int16 mono chunks of exactly chunk_samples."""

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
    TODO(machine): exit-checklist runs use this; fixture tests never do."""

    def __init__(self, chunk_samples: int = 1280, sample_rate: int = 16_000) -> None:
        self.chunk = chunk_samples
        self.rate = sample_rate

    def chunks(self) -> Iterator[np.ndarray]:
        import queue

        import sounddevice as sd

        q: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=64)

        def on_audio(indata, frames, time_info, status) -> None:
            if status:
                # Overruns are logged by the caller via health; never block.
                pass
            try:
                q.put_nowait(indata[:, 0].copy())
            except queue.Full:
                pass  # drop-oldest is the bus policy; here we drop-newest

        with sd.InputStream(
            samplerate=self.rate,
            channels=1,
            dtype="int16",
            blocksize=self.chunk,
            callback=on_audio,
        ):
            while True:
                yield q.get()


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
        """
        out = {
            "mic_open": 1.0 if self.mic else 0.0,
            "captured_s": float(self.captured_s),
            "capture_stall_s": float(self.STALL_S),
        }
        age = self.age_s
        if age is not None:
            out["capture_age_s"] = float(age)
        return out

    def health(self) -> tuple:
        """(state, notes) for the heartbeat — see schemas/sys.health.json.

        Only a microphone can stall. A --wav run has no device to lose:
        the file ends, the process exits, and calling that "degraded"
        would cry wolf on every fixture run in the replay harness.
        """
        if not self.mic:
            return "ok", None
        age = self.age_s
        if age is None:
            return "starting", None
        if age > self.STALL_S:
            return "degraded", f"microphone open but no audio for {age:.1f}s"
        return "ok", None
