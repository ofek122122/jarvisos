#!/usr/bin/env python3
"""harness/replay.py — replay a recorded session onto the bus with the
original inter-frame timing (from envelope ts deltas).

By default each frame's `ts` is rewritten to the current monotonic clock
at publish (so live consumers compute sane hop latencies); `--keep-ts`
republishes verbatim. `--speed 10` replays 10x faster; `--instant`
ignores timing entirely.

Usage:
  python harness/replay.py session.jsonl [--speed 1.0 | --instant]
                           [--bus ADDR] [--keep-ts]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "pylib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import session  # noqa: E402
from jarvis_bus import BusClient, mono_now  # noqa: E402


async def replay(
    path: Path,
    bus_addr: Optional[str] = None,
    speed: float = 1.0,
    instant: bool = False,
    keep_ts: bool = False,
) -> int:
    frames = session.load(path).frames
    bus = await BusClient.connect(bus_addr, src="harness-replay")
    sent = 0
    try:
        prev_ts: Optional[float] = None
        for frame in frames:
            if not instant and prev_ts is not None:
                delta = max(0.0, (frame["ts"] - prev_ts) / speed)
                if delta:
                    await asyncio.sleep(delta)
            prev_ts = frame["ts"]
            out = frame if keep_ts else {**frame, "ts": mono_now()}
            await bus.publish_env(out)
            sent += 1
    finally:
        await bus.close()
    return sent


async def amain() -> int:
    ap = argparse.ArgumentParser(prog="replay.py")
    ap.add_argument("session", type=Path)
    ap.add_argument("--bus", default=None)
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--instant", action="store_true")
    ap.add_argument("--keep-ts", action="store_true")
    args = ap.parse_args()
    n = await replay(args.session, args.bus, args.speed, args.instant, args.keep_ts)
    print(f"replayed {n} frames from {args.session}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(amain()))
