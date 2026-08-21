"""Piper synthesis + the signature chain. Blocking — callers run it in
an executor."""

from __future__ import annotations

import io
import wave

import numpy as np

from .chain import apply_chain
from .config import VoiceConfig


class Synthesizer:
    def __init__(self, cfg: VoiceConfig) -> None:
        from piper import PiperVoice

        self.cfg = cfg
        self._voice = PiperVoice.load(str(cfg.piper_onnx), str(cfg.piper_json))

    def synth(self, text: str) -> tuple[np.ndarray, int]:
        """Text -> (float32 mono with chain applied, sample_rate)."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            self._voice.synthesize_wav(text, w)
        buf.seek(0)
        with wave.open(buf, "rb") as w:
            rate = w.getframerate()
            pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        f32 = pcm.astype(np.float32) / 32768.0
        return apply_chain(f32, rate, self.cfg.chain), rate
