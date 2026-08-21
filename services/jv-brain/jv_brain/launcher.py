"""jv-llm-launch — the VRAM guard. Runs as the ExecStart of the
llama-server systemd unit: measures FREE VRAM at launch (desktop already
up on all three monitors), walks Ofek's fallback ladder, records the
chosen rung to the rung file (jv-brain reports it on sys.health), and
execs llama-server with the rung's shape.

Ladder: (0) full → (1) KV q8 → (2) ctx 2k → (3) Q4_K_S → (4) CPU.
The budget includes weights + KV cache + compute overhead + a safety
margin; rung 4 (CPU) always fits by construction — slow but alive.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

from .config import (
    COMPUTE_OVERHEAD_BYTES,
    LADDER,
    SAFETY_MARGIN_BYTES,
    WEIGHT_BYTES,
    BrainConfig,
    Rung,
)


def probe_free_vram_bytes() -> Optional[int]:
    """Free VRAM right now, via nvidia-smi. None = no usable GPU."""
    try:
        out = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    try:
        return int(out.stdout.strip().splitlines()[0]) * 1024 * 1024
    except (ValueError, IndexError):
        return None


def rung_budget_bytes(rung: Rung) -> int:
    return WEIGHT_BYTES[rung.model_file] + rung.kv_bytes() + COMPUTE_OVERHEAD_BYTES


def pick_rung(free_vram: Optional[int], ladder: tuple[Rung, ...] = LADDER) -> Rung:
    """First rung that fits free VRAM minus the safety margin; the CPU
    rung is the unconditional floor."""
    for rung in ladder:
        if not rung.gpu:
            return rung
        if free_vram is not None and rung_budget_bytes(rung) <= free_vram - SAFETY_MARGIN_BYTES:
            return rung
    return ladder[-1]


def llama_args(cfg: BrainConfig, rung: Rung, port: int) -> list[str]:
    args = [
        "llama-server",
        "--model",
        str(cfg.models_dir / "llm" / rung.model_file),
        "--ctx-size",
        str(rung.ctx),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--jinja",  # Qwen3 chat template; thinking disabled per-request
        "--n-gpu-layers",
        "99" if rung.gpu else "0",
    ]
    if rung.kv_type != "f16":
        args += ["--cache-type-k", rung.kv_type, "--cache-type-v", rung.kv_type]
    return args


def write_rung_file(path: Path, rung: Rung, free_vram: Optional[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    free_mb = -1 if free_vram is None else free_vram // (1024 * 1024)
    path.write_text(
        f"rung={rung.index}\nlabel={rung.label}\nbackend={'gpu' if rung.gpu else 'cpu'}\n"
        f"free_vram_mb={free_mb}\n",
        encoding="utf-8",
    )


def launch(
    cfg: BrainConfig,
    port: int = 8080,
    probe: Callable[[], Optional[int]] = probe_free_vram_bytes,
    exec_fn: Callable[[list[str]], None] | None = None,
) -> Rung:
    free = probe()
    rung = pick_rung(free)
    write_rung_file(cfg.rung_file, rung, free)
    print(
        f"jv-llm-launch: free_vram={'-' if free is None else free // 2**20}MB "
        f"-> rung {rung.index} ({rung.label})",
        file=sys.stderr,
    )
    args = llama_args(cfg, rung, port)
    if exec_fn is None:
        os.execvp(args[0], args)  # becomes llama-server; systemd tracks it
    else:
        exec_fn(args)
    return rung


def cli() -> None:
    ap = argparse.ArgumentParser(prog="jv-llm-launch")
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()
    launch(BrainConfig(), port=args.port)


if __name__ == "__main__":
    cli()
