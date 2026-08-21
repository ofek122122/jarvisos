"""openWakeWord hey_jarvis detector with pinned model paths (no silent
auto-downloads — models come from models/fetch.sh)."""

from __future__ import annotations

from .config import EarsConfig

import numpy as np


class WakeDetector:
    def __init__(self, cfg: EarsConfig) -> None:
        from openwakeword.model import Model

        self._model = Model(
            wakeword_models=[str(cfg.wake_model)],
            melspec_model_path=str(cfg.melspec_model),
            embedding_model_path=str(cfg.embedding_model),
            inference_framework="onnx",
        )
        self.threshold = cfg.wake_threshold

    def feed(self, chunk_i16: np.ndarray) -> float:
        """Feed one 80 ms chunk; returns the hey_jarvis score for it."""
        scores = self._model.predict(chunk_i16)
        return float(max(scores.values()))

    def reset(self) -> None:
        self._model.reset()
