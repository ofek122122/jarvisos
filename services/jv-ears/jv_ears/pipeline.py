"""The ears pipeline: wake + VAD run continuously; ASR is wake-gated.

Design (departure Q&A + announced defaults):
- VAD events publish continuously — free presence signal for later phases.
- Whisper transcribes ONLY wake-gated utterances; wake word required
  every time (v0, no follow-up window).
- All timing decisions use the SAMPLE clock (samples consumed / rate),
  never the wall clock — the same fixture always produces the same
  events, which is what makes CI meaningful.

Events are emitted through a publish callback `(topic, conf, v, body)`;
main.py bridges that to the bus, tests collect it into a list.
"""

from __future__ import annotations

import uuid
from typing import Callable, Optional

import numpy as np

from .asr import Transcriber
from .config import EarsConfig
from .vad import SileroVad
from .wake import WakeDetector

Publish = Callable[[str, float, int, dict], None]


class EarsPipeline:
    def __init__(self, cfg: EarsConfig, publish: Publish) -> None:
        self.cfg = cfg
        self.publish = publish
        self.wake = WakeDetector(cfg)
        self.vad = SileroVad(cfg.vad_model)
        self.asr = Transcriber(cfg.whisper_dir, beam_size=cfg.asr_beam_size)

        r = cfg.sample_rate
        self._min_speech = cfg.vad_min_speech_ms * r // 1000
        self._min_silence = cfg.vad_min_silence_ms * r // 1000
        self._pre_roll = cfg.pre_roll_ms * r // 1000
        self._partial_hop = int(cfg.partial_interval_s * r)
        self._wake_timeout = int(cfg.wake_timeout_s * r)
        self._wake_refractory = int(cfg.wake_refractory_s * r)

        # sample clock
        self._pos = 0
        # wake state
        self._armed_at: Optional[int] = None
        self._last_wake: int = -(10**12)
        # VAD segmentation state
        self._speech_run = 0
        self._silence_run = 0
        self._in_speech = False
        self._utt_id: Optional[str] = None
        self._utt_started_at = 0
        self._utt_gated = False  # was a wake active when speech started?
        # audio buffers
        self._ring = np.zeros(0, dtype=np.int16)  # pre-roll keeper
        self._utt_audio = np.zeros(0, dtype=np.int16)
        self._next_partial = 0

    # ------------------------------------------------------------ helpers

    def _t(self) -> float:
        """Sample clock in seconds (fixture-deterministic)."""
        return self._pos / self.cfg.sample_rate

    # ------------------------------------------------------------- events

    def _on_wake(self, score: float) -> None:
        self._last_wake = self._pos
        self._armed_at = self._pos
        self.publish(
            "audio.wake",
            score,
            1,
            {"model": "hey_jarvis", "score": score, "threshold": self.cfg.wake_threshold},
        )
        # The wake phrase lives INSIDE the utterance: VAD confirms speech
        # ~200 ms in, while "hey jarvis" needs ~1 s of audio to score —
        # so gate the in-flight utterance retroactively.
        if self._in_speech and not self._utt_gated:
            self._utt_gated = True
            self._next_partial = self._pos + self._partial_hop

    def _on_speech_start(self) -> None:
        self._in_speech = True
        self._utt_id = str(uuid.uuid4())
        self._utt_started_at = self._pos
        self._utt_gated = self._armed_at is not None
        # utterance audio begins pre-roll earlier than the confirm point
        self._utt_audio = self._ring[-(self._pre_roll + self._min_speech) :].copy()
        self._next_partial = self._pos + self._partial_hop
        self.publish(
            "audio.vad", 1.0, 1, {"event": "speech_start", "utterance_id": self._utt_id}
        )

    def _on_speech_end(self) -> None:
        dur = (self._pos - self._utt_started_at) / self.cfg.sample_rate
        self.publish(
            "audio.vad",
            1.0,
            1,
            {"event": "speech_end", "utterance_id": self._utt_id, "duration_s": dur},
        )
        if self._utt_gated:
            self._emit_transcript(kind="final")
            self._armed_at = None  # one utterance per wake (v0)
        self._in_speech = False
        self._utt_id = None
        self._utt_audio = np.zeros(0, dtype=np.int16)

    def _emit_transcript(self, kind: str) -> None:
        want_words = kind == "final"
        text, lang, conf, words = self.asr.transcribe(self._utt_audio, words=want_words)
        if not text:
            return
        body = {
            "kind": kind,
            "utterance_id": self._utt_id,
            "text": text,
            "lang": lang,
            "t0": 0.0,
            "t1": len(self._utt_audio) / self.cfg.sample_rate,
        }
        if want_words and words:
            body["words"] = words
        self.publish("audio.transcript", conf, 1, body)

    # --------------------------------------------------------------- feed

    def feed(self, chunk: np.ndarray) -> None:
        """Consume one chunk (any length; canonical is 80 ms)."""
        # Wake — continuous, with refractory.
        score = self.wake.feed(chunk)
        if (
            score >= self.cfg.wake_threshold
            and self._pos - self._last_wake >= self._wake_refractory
        ):
            self._on_wake(score)

        # Wake timeout: armed but nothing said.
        if (
            self._armed_at is not None
            and not self._in_speech
            and self._pos - self._armed_at > self._wake_timeout
        ):
            self._armed_at = None

        # VAD — continuous.
        n = len(chunk)
        for prob in self.vad.feed(chunk):
            speech = prob >= self.cfg.vad_threshold
            if speech:
                self._speech_run += SileroVad.WINDOW
                self._silence_run = 0
            else:
                self._silence_run += SileroVad.WINDOW
                self._speech_run = 0
            if not self._in_speech and self._speech_run >= self._min_speech:
                self._on_speech_start()
            elif self._in_speech and self._silence_run >= self._min_silence:
                self._on_speech_end()

        # Buffers + partials.
        keep = self._pre_roll + self._min_speech + n
        self._ring = np.concatenate([self._ring, chunk])[-keep:]
        if self._in_speech:
            self._utt_audio = np.concatenate([self._utt_audio, chunk])
            if self._utt_gated and self._pos >= self._next_partial:
                self._emit_transcript(kind="partial")
                self._next_partial = self._pos + self._partial_hop

        self._pos += n

    def run(self, source) -> None:
        """Drive the pipeline from an AudioSource until it ends."""
        for chunk in source.chunks():
            self.feed(chunk)
