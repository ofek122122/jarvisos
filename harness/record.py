#!/usr/bin/env python3
"""harness/record.py — dump bus topics to a session file (JSONL).

Line 1: the session header required by schemas/README.md —
  {"boot_id": ..., "wall_time_utc": ..., "monotonic_now": ...}
so monotonic `ts` values stay datable across reboots.
Following lines: one envelope frame per line, verbatim.

Usage:
  python harness/record.py -o session.jsonl [--topics 'audio.*' ...]
                           [--duration 30] [--bus ADDR]
Stop with Ctrl+C if no --duration.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import sys
import time
from pathlib import Path
from typing import Optional, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "pylib"))
from jarvis_bus import BusClient, mono_now  # noqa: E402


def boot_id() -> str:
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return "dev-no-boot-id"


def session_header() -> dict:
    return {
        "boot_id": boot_id(),
        "wall_time_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "monotonic_now": mono_now(),
    }


async def record(
    out: TextIO,
    topics: list[str],
    bus_addr: Optional[str] = None,
    duration_s: Optional[float] = None,
    frame_limit: Optional[int] = None,
) -> int:
    """Record until duration/limit/EOF. Returns number of frames written."""
    bus = await BusClient.connect(bus_addr, src="harness-record")
    await bus.subscribe(topics)
    out.write(json.dumps(session_header()) + "\n")
    out.flush()
    n = 0
    deadline = time.monotonic() + duration_s if duration_s else None
    try:
        while frame_limit is None or n < frame_limit:
            timeout = None if deadline is None else max(0.0, deadline - time.monotonic())
            try:
                frame = await asyncio.wait_for(
                    bus.next_frame(), timeout if timeout is not None else None
                )
            except asyncio.TimeoutError:
                break
            if frame is None:
                break
            out.write(json.dumps(frame) + "\n")
            n += 1
    finally:
        out.flush()
        await bus.close()
    return n


async def amain() -> int:
    ap = argparse.ArgumentParser(prog="record.py")
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--topics", nargs="*", default=["*"])
    ap.add_argument("--duration", type=float, default=None)
    ap.add_argument("--bus", default=None)
    args = ap.parse_args()
    with args.out.open("w", encoding="utf-8", newline="\n") as fh:
        try:
            n = await record(fh, args.topics, args.bus, args.duration)
        except KeyboardInterrupt:
            n = -1
    print(f"recorded to {args.out}")
    return 0 if n != 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(amain()))
