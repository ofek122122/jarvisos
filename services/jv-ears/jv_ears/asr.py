"""faster-whisper (CTranslate2, CPU int8) transcription.

Departure-Q&A decision: faster-whisper over whisper.cpp — same distil
weights, better CPU throughput on the i5, GPU stays with the brain."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np


class Transcriber:
    def __init__(self, model_dir: Path, beam_size: int = 1) -> None:
        from faster_whisper import WhisperModel

        self._model = WhisperModel(str(model_dir), device="cpu", compute_type="int8")
        self._beam = beam_size

    def transcribe(self, audio_i16: np.ndarray, words: bool = False):
        """Returns (text, lang, conf, word_list). Confidence is
        exp(mean avg_logprob) over segments, clamped to [0, 1]."""
        f32 = audio_i16.astype(np.float32) / 32768.0
        segments, info = self._model.transcribe(
            f32,
            beam_size=self._beam,
            word_timestamps=words,
            condition_on_previous_text=False,
            vad_filter=False,  # segmentation is Silero's job upstream
        )
        texts: list[str] = []
        logprobs: list[float] = []
        word_list: list[dict] = []
        for seg in segments:
            texts.append(seg.text.strip())
            logprobs.append(seg.avg_logprob)
            if words and seg.words:
                for w in seg.words:
                    word_list.append(
                        {"w": w.word.strip(), "t0": w.start, "t1": w.end, "p": w.probability}
                    )
        text = " ".join(t for t in texts if t).strip()
        conf = 0.0
        if logprobs:
            conf = max(0.0, min(1.0, math.exp(sum(logprobs) / len(logprobs))))
        lang = (info.language or "en") if text else "en"
        return text, lang, conf, word_list
