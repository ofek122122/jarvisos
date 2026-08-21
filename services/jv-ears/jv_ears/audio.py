"""Audio sources. The pipeline consumes int16 mono chunks at 16 kHz from
anything implementing chunks() — the mic on ares, WAV files in tests and
the replay harness. This is the seam the brief demands."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Iterator, Sequence

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
