"""jv-voice configuration: identity from personality/voice.toml,
engineering knobs here."""

from __future__ import annotations

import dataclasses
import os
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # 3.10
    import tomli as tomllib  # type: ignore[no-redef]

REPO = Path(__file__).resolve().parents[3]


def default_models_dir() -> Path:
    if env := os.environ.get("JARVIS_MODELS_DIR"):
        return Path(env)
    if sys.platform != "win32":
        return Path("/var/lib/jarvis/models")
    return REPO / "models-cache"


def default_personality() -> Path:
    if env := os.environ.get("JARVIS_PERSONALITY_DIR"):
        return Path(env)
    return REPO / "personality"


@dataclasses.dataclass
class ChainParams:
    intensity: float = 0.4
    highpass_hz: float = 120.0
    shimmer_base: float = 0.10
    reverb_seconds: float = 0.2
    reverb_wet_base: float = 0.35
    ringmod_hz: float = 55.0
    limiter_drive: float = 1.5


@dataclasses.dataclass
class VoiceConfig:
    models_dir: Path = dataclasses.field(default_factory=default_models_dir)
    voice_model: str = "en_US-ryan-high"
    chain: ChainParams = dataclasses.field(default_factory=ChainParams)

    @classmethod
    def load(cls, personality_dir: Path | None = None) -> "VoiceConfig":
        cfg = cls()
        toml_path = (personality_dir or default_personality()) / "voice.toml"
        if toml_path.exists():
            data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
            cfg.voice_model = data.get("voice", {}).get("model", cfg.voice_model)
            chain = data.get("chain", {})
            for f in dataclasses.fields(ChainParams):
                if f.name in chain:
                    setattr(cfg.chain, f.name, float(chain[f.name]))
        return cfg

    @property
    def piper_onnx(self) -> Path:
        return self.models_dir / "piper" / f"{self.voice_model}.onnx"

    @property
    def piper_json(self) -> Path:
        return self.models_dir / "piper" / f"{self.voice_model}.onnx.json"
