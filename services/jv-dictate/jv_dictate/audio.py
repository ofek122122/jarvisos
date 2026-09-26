"""Buffers int16 mono audio for exactly one recording: start() opens a
stream, stop() closes it and hands back everything it saw. Unlike jv-ears'
MicSource (services/jv-ears/jv_ears/audio.py) this is not a continuous
source feeding a pipeline — jv-dictate has no VAD and no wake word, the key
IS the gate — so there is nothing here shaped like CaptureMeter. One
recording, one buffer, one answer.

`sounddevice` is imported lazily, inside `_real_stream`, the same discipline
jv_ears.audio.MicSource follows and for the same reason: a checkout with no
audio libraries installed (this loop's own test venv, before jv-dictate is
ever built and switched on the host) must still be able to import this
module and run PushToTalk's tests. The `stream_factory` seam is what makes
the buffering logic itself testable without a sound card at all — see
tests/test_audio.py, which drives a fake stream by calling the callback the
same way PortAudio would.
"""

from __future__ import annotations

from typing import Callable, Optional

import numpy as np


class AudioRecorder:
    def __init__(
        self,
        sample_rate: int = 16_000,
        *,
        stream_factory: Optional[Callable] = None,
    ) -> None:
        self.sample_rate = sample_rate
        self._factory = stream_factory or self._real_stream
        self._chunks: list[np.ndarray] = []
        self._stream = None

    def _real_stream(self, callback):
        import sounddevice as sd

        return sd.InputStream(
            samplerate=self.sample_rate, channels=1, dtype="int16", callback=callback
        )

    def start(self) -> None:
        self._chunks = []

        def _on_audio(indata, frames, time_info, status) -> None:
            # .copy(): PortAudio (and any well-behaved fake standing in for
            # it) reuses this buffer on the next callback, so a bare slice
            # would be rewritten under us before stop() ever reads it.
            self._chunks.append(np.asarray(indata)[:, 0].copy())

        self._stream = self._factory(_on_audio)
        self._stream.start()

    def stop(self) -> np.ndarray:
        """Closes the stream and returns everything captured since start(),
        as one int16 mono array. Safe to call without a prior start()."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if not self._chunks:
            return np.zeros(0, dtype=np.int16)
        return np.concatenate(self._chunks)
