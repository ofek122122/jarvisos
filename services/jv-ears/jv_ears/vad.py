"""Silero VAD v5 (ONNX, streaming) — thin stateful wrapper.

The model consumes 512-sample windows at 16 kHz and keeps a recurrent
state; we buffer arbitrary chunk sizes down to that hop."""

from __future__ import annotations

from pathlib import Path

import numpy as np


class SileroVad:
    WINDOW = 512  # 32 ms @ 16 kHz — fixed by the model
    CONTEXT = 64  # v5 wants the last 64 samples of the previous window
    # prepended to each 512-window (input length 576) — without it the
    # model silently returns near-zero probabilities.

    def __init__(self, model_path: Path) -> None:
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        self._sess = ort.InferenceSession(
            str(model_path), opts, providers=["CPUExecutionProvider"]
        )
        self.reset()

    def reset(self) -> None:
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._ctx = np.zeros(self.CONTEXT, dtype=np.float32)
        self._buf = np.zeros(0, dtype=np.float32)

    def feed(self, chunk_i16: np.ndarray) -> list[float]:
        """Feed any-length int16 audio; returns one speech probability per
        consumed 512-sample window (possibly empty)."""
        f32 = chunk_i16.astype(np.float32) / 32768.0
        self._buf = np.concatenate([self._buf, f32])
        probs: list[float] = []
        while len(self._buf) >= self.WINDOW:
            win = self._buf[: self.WINDOW]
            self._buf = self._buf[self.WINDOW :]
            inp = np.concatenate([self._ctx, win])[np.newaxis, :]
            out, self._state = self._sess.run(
                None,
                {
                    "input": inp,
                    "state": self._state,
                    "sr": np.array(16_000, dtype=np.int64),
                },
            )
            self._ctx = win[-self.CONTEXT :]
            probs.append(float(out[0][0]))
        return probs
