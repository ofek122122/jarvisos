"""jv-brain configuration, including the VRAM fallback ladder
(Ofek's spec, 2026-08-21): budget TOTAL headroom — free VRAM measured
live with the desktop up — including the KV cache, not just weights."""

from __future__ import annotations

import dataclasses
import os
import sys
from pathlib import Path

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


def default_rung_file() -> Path:
    if env := os.environ.get("JARVIS_LLM_RUNG_FILE"):
        return Path(env)
    if sys.platform != "win32":
        return Path("/run/jarvis/llm-rung")
    return REPO / "models-cache" / "llm-rung"


@dataclasses.dataclass(frozen=True)
class Rung:
    """One step of the fallback ladder → llama-server launch shape."""

    index: int
    label: str
    model_file: str  # under models_dir/llm/
    ctx: int
    kv_type: str  # "f16" | "q8_0"
    gpu: bool

    # Qwen3-8B geometry: 36 layers × 8 KV heads × 128 head-dim × 2 (K+V).
    KV_BYTES_PER_TOKEN_F16 = 36 * 8 * 128 * 2 * 2  # ≈ 147 KB/token

    def kv_bytes(self) -> int:
        per_tok = self.KV_BYTES_PER_TOKEN_F16
        if self.kv_type == "q8_0":
            per_tok //= 2
        return self.ctx * per_tok


# Ofek's ladder, in order. Weights sizes from models/fetch.sh pins.
LADDER: tuple[Rung, ...] = (
    Rung(0, "full: Q4_K_M, f16 KV, 4k ctx", "Qwen3-8B-Q4_K_M.gguf", 4096, "f16", True),
    Rung(1, "KV q8", "Qwen3-8B-Q4_K_M.gguf", 4096, "q8_0", True),
    Rung(2, "ctx 2k", "Qwen3-8B-Q4_K_M.gguf", 2048, "q8_0", True),
    Rung(3, "Q4_K_S weights", "Qwen3-8B-Q4_K_S.gguf", 2048, "q8_0", True),
    Rung(4, "CPU fallback", "Qwen3-8B-Q4_K_M.gguf", 4096, "f16", False),
)

WEIGHT_BYTES = {
    "Qwen3-8B-Q4_K_M.gguf": 5_027_783_488,
    "Qwen3-8B-Q4_K_S.gguf": 4_802_012_704,
}

# llama.cpp compute buffers + CUDA runtime slop, plus a hard safety
# margin so the desktop compositor never gets starved.
COMPUTE_OVERHEAD_BYTES = 400 * 1024 * 1024
SAFETY_MARGIN_BYTES = 300 * 1024 * 1024


@dataclasses.dataclass
class BrainConfig:
    models_dir: Path = dataclasses.field(default_factory=default_models_dir)
    personality_dir: Path = dataclasses.field(default_factory=default_personality)
    rung_file: Path = dataclasses.field(default_factory=default_rung_file)

    llm_url: str = dataclasses.field(
        default_factory=lambda: os.environ.get("JARVIS_LLM_URL", "http://127.0.0.1:8080")
    )
    model_name: str = "qwen3-8b"
    temperature: float = 0.6
    max_tokens: int = 320  # spoken replies are short by charter

    max_turns: int = 16  # rolling window, user+assistant pairs counted singly
    max_context_chars: int = 12_000  # crude token cap (≈3k tokens)
    idle_reset_s: float = 600.0  # fresh conversation after 10 min silence

    request_timeout_s: float = 120.0
