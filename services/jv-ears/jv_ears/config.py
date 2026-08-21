"""jv-ears configuration. Perception tuning lives here (service config),
NOT in personality/ — thresholds are engineering, identity is identity."""

from __future__ import annotations

import dataclasses
import os
import sys
from pathlib import Path


def default_models_dir() -> Path:
    if env := os.environ.get("JARVIS_MODELS_DIR"):
        return Path(env)
    if sys.platform != "win32":
        return Path("/var/lib/jarvis/models")
    # Windows dev: repo-local cache (models/fetch.sh default).
    # parents[3] of services/jv-ears/jv_ears/config.py = the repo root.
    return Path(__file__).resolve().parents[3] / "models-cache"


@dataclasses.dataclass
class EarsConfig:
    models_dir: Path = dataclasses.field(default_factory=default_models_dir)

    sample_rate: int = 16_000
    chunk_samples: int = 1280  # 80 ms — openWakeWord's preferred hop

    # Wake (openWakeWord hey_jarvis)
    wake_threshold: float = 0.5
    wake_refractory_s: float = 2.0
    # Disarm if no speech follows a wake within this window.
    wake_timeout_s: float = 8.0

    # VAD (Silero v5). min_silence bridges natural mid-sentence pauses —
    # the pause fixture holds 1.2 s and must NOT split the utterance.
    vad_threshold: float = 0.5
    vad_min_speech_ms: int = 200
    vad_min_silence_ms: int = 1500
    pre_roll_ms: int = 400  # audio kept from before speech_start

    # ASR
    partial_interval_s: float = 0.7
    asr_beam_size: int = 1

    @property
    def wake_model(self) -> Path:
        return self.models_dir / "openwakeword" / "hey_jarvis_v0.1.onnx"

    @property
    def melspec_model(self) -> Path:
        return self.models_dir / "openwakeword" / "melspectrogram.onnx"

    @property
    def embedding_model(self) -> Path:
        return self.models_dir / "openwakeword" / "embedding_model.onnx"

    @property
    def vad_model(self) -> Path:
        return self.models_dir / "silero" / "silero_vad.onnx"

    @property
    def whisper_dir(self) -> Path:
        return self.models_dir / "whisper" / "faster-distil-small.en"
