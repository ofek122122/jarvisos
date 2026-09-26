"""faster-whisper (CTranslate2, CPU int8) transcription — the SAME engine
and the SAME weights jv-ears already runs (services/jv-ears/jv_ears/asr.py),
pointed at the same JARVIS_MODELS_DIR. Invariant 1 forbids one service
importing another directly, so this is a second small wrapper rather than a
cross-service import; it is not a second ASR in the sense PLAN F5b's own
gate means (no second model, no second engine, no second set of weights to
keep in VRAM or on disk)."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np


class Transcriber:
    def __init__(self, model_dir: Path, beam_size: int = 1) -> None:
        from faster_whisper import WhisperModel

        self._model = WhisperModel(str(model_dir), device="cpu", compute_type="int8")
        self._beam = beam_size

    def transcribe(self, audio_i16: np.ndarray):
        """Returns (text, lang, conf). No word timing — dictation wants the
        sentence, not a subtitle track."""
        f32 = audio_i16.astype(np.float32) / 32768.0
        segments, info = self._model.transcribe(
            f32,
            beam_size=self._beam,
            word_timestamps=False,
            condition_on_previous_text=False,
            vad_filter=False,
        )
        texts: list[str] = []
        logprobs: list[float] = []
        for seg in segments:
            texts.append(seg.text.strip())
            logprobs.append(seg.avg_logprob)
        text = " ".join(t for t in texts if t).strip()
        conf = 0.0
        if logprobs:
            conf = max(0.0, min(1.0, math.exp(sum(logprobs) / len(logprobs))))
        lang = (info.language or "en") if text else "en"
        return text, lang, conf
