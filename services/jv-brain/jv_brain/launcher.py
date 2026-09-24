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
import dataclasses
import math
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


# How the free-VRAM number was arrived at. It is not decoration: the
# ladder lands on the same CPU rung for all three, and only this word
# says whether that was a measurement, a fact about the machine, or a
# guess nobody could check.
MEASURED = "measured"
ABSENT = "absent"
UNREADABLE = "unreadable"


class VramUnreadable(RuntimeError):
    """There is an NVIDIA driver on this machine and it would not answer.

    Raised, never returned as `None`. `pick_rung` reads `None` as "no
    usable GPU" and drops Jarvis to the CPU rung for the life of that
    llama-server, so folding a timeout, a non-zero exit and an `[N/A]`
    into the same `None` made a driver hiccup at launch indistinguishable
    from a machine with no card — a permanent, invisible downgrade.

    The floor is the same either way (you cannot allocate VRAM you could
    not count). What differs is what anyone is allowed to conclude, so
    this travels as far as the heartbeat.
    """


def parse_nvidia_smi_vram_mb(text: str) -> float:
    """`nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits`
    stdout -> free MiB.

    One line per GPU; ares has one and the first line is it. `[N/A]` and
    `[Not Supported]` are what nvidia-smi prints when a device cannot
    answer the query, and NVML's own initialisation errors arrive on
    stdout. None of those is a number — and neither is `nan`, which
    float() accepts happily and which would walk the ladder comparing
    false to every rung budget, i.e. exactly like a full card.
    """
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        raise VramUnreadable("nvidia-smi printed nothing")
    try:
        mb = float(lines[0])
    except ValueError as exc:
        raise VramUnreadable(f"nvidia-smi said {lines[0]!r}") from exc
    if not math.isfinite(mb) or mb < 0:
        raise VramUnreadable(f"nvidia-smi VRAM {mb!r} is out of range")
    return mb


def probe_free_vram_bytes() -> Optional[int]:
    """Free VRAM right now, via nvidia-smi.

    None means one specific thing: there is no nvidia-smi here, so there
    is no NVIDIA driver and no GPU rung to want. Every other way this can
    go wrong raises VramUnreadable.

    This runs ONCE per llama-server launch, so the fork costs nothing
    worth counting (unlike jv-context's 1 Hz probe, backlog 14) and there
    is nothing to latch.
    """
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
    except FileNotFoundError:
        return None
    except (OSError, subprocess.SubprocessError) as exc:
        raise VramUnreadable(f"nvidia-smi did not run: {exc}") from exc
    if out.returncode != 0:
        # A number on stdout alongside a failure exit is still a failure.
        raise VramUnreadable(f"nvidia-smi exited {out.returncode}")
    return int(parse_nvidia_smi_vram_mb(out.stdout)) * 1024 * 1024


@dataclasses.dataclass(frozen=True)
class VramReading:
    """A free-VRAM answer, plus how it was come by and (when it went
    wrong) nvidia-smi's own words for why."""

    free_bytes: Optional[int] = None
    source: str = ABSENT
    detail: Optional[str] = None

    @property
    def free_mb(self) -> int:
        """-1 when there is no number. Both silences write -1, which is
        why `source` has to be written down separately."""
        return -1 if self.free_bytes is None else self.free_bytes // (1024 * 1024)


def read_vram(probe: Callable[[], Optional[int]] = probe_free_vram_bytes) -> VramReading:
    """Run the probe seam and classify its three outcomes."""
    try:
        free = probe()
    except VramUnreadable as exc:
        return VramReading(None, UNREADABLE, str(exc))
    if free is None:
        return VramReading(None, ABSENT)
    return VramReading(free, MEASURED)


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
        # One conversation, one slot: the default -np 4 round-robins
        # requests across slots (full re-prefill on every switch) and
        # splits ctx-size four ways. --cache-reuse lets the KV cache
        # survive jv-brain's batched history trims via chunk shifting.
        "--parallel",
        "1",
        "--cache-reuse",
        "256",
    ]
    if rung.kv_type != "f16":
        args += ["--cache-type-k", rung.kv_type, "--cache-type-v", rung.kv_type]
    return args


@dataclasses.dataclass(frozen=True)
class RungRecord:
    """The rung file, parsed. This file is the launcher's ONLY channel:
    it execs into llama-server and is gone, so anything it learned that
    nobody else can re-derive has to be written here or be lost."""

    index: Optional[int]
    backend: str
    vram: VramReading


def write_rung_file(path: Path, rung: Rung, vram: VramReading) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"rung={rung.index}",
        f"label={rung.label}",
        f"backend={'gpu' if rung.gpu else 'cpu'}",
        f"free_vram_mb={vram.free_mb}",
        f"vram={vram.source}",
    ]
    if vram.detail:
        # nvidia-smi's own words, flattened: the reader is line-oriented.
        lines.append(f"vram_note={' '.join(vram.detail.split())}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_rung_file(path: Path) -> RungRecord:
    """Parse the rung file, or say so. Unreadable/absent file -> index
    None, which is how jv-brain has always spelled "llama-server has not
    told me anything yet"."""
    try:
        data = dict(
            line.split("=", 1)
            for line in path.read_text(encoding="utf-8").splitlines()
            if "=" in line
        )
        index: Optional[int] = int(data.get("rung", -1))
    except (OSError, ValueError):
        return RungRecord(None, "gpu", VramReading())
    try:
        free_mb = int(data.get("free_vram_mb", -1))
    except ValueError:
        free_mb = -1
    # A file written before `vram=` existed says only -1 or a number, and
    # must not be able to invent a fault nobody observed.
    source = data.get("vram") or (MEASURED if free_mb >= 0 else ABSENT)
    if source not in (MEASURED, ABSENT, UNREADABLE):
        source = ABSENT
    return RungRecord(
        index,
        data.get("backend", "gpu"),
        VramReading(
            free_bytes=free_mb * 1024 * 1024 if free_mb >= 0 else None,
            source=source,
            detail=data.get("vram_note") if source == UNREADABLE else None,
        ),
    )


def launch(
    cfg: BrainConfig,
    port: int = 8080,
    probe: Callable[[], Optional[int]] = probe_free_vram_bytes,
    exec_fn: Callable[[list[str]], None] | None = None,
) -> Rung:
    vram = read_vram(probe)
    rung = pick_rung(vram.free_bytes)
    write_rung_file(cfg.rung_file, rung, vram)
    said = f"{vram.free_mb}MB" if vram.source == MEASURED else vram.source
    print(
        f"jv-llm-launch: free_vram={said} -> rung {rung.index} ({rung.label})"
        + (f" [{vram.detail}]" if vram.detail else ""),
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
