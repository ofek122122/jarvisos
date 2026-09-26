#!/usr/bin/env python3
"""Put the HUD's frames on the bus and keep them there, until killed (D43).

Started by `tools/shellload/load.py` once `jv-hud` has said it loaded, and
stopped by it once the compositor has been asked its questions. What it
publishes is `shells.HUD_FRAMES`, in that order, once per round — see the
comment above `HUD_ROUND_S` for why a round repeats and why re-sending the
whole set in order is safe for the two plates that latch.

ITS OWN PROCESS, and that is not incidental. This half is asyncio (the bus
client is), the driver is not, and a driver that grew an event loop to keep one
plate fresh would be a driver whose measurements ran inside somebody else's
scheduler. Out here it is a process the driver starts, waits one line of, and
kills — the same shape every shell in this gate already is.

IT IS A PUBLISHER AND NOTHING ELSE. It never subscribes, never reads a frame
back, and asserts nothing: whether the frames arrived is the HUD's own account
of its corner, which `load.py` reads out of the shell's log. A harness that
graded itself on what it had just sent would be grading the bus.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "pylib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import shells  # noqa: E402
from jarvis_bus import BusClient  # noqa: E402


async def amain() -> int:
    # One client per publisher, and the `src` is the SERVICE's rather than this
    # harness's: core/HealthState.qml refuses a `sys.health` body naming a
    # service other than the envelope's sender, and every state machine that
    # pairs two topics does it by `src`. A frame published under a harness name
    # would be a frame about a machine that does not exist.
    #
    # Reused across rounds rather than reconnected per frame, because `seq` is
    # per-connection and strictly increasing — which is how the HUD notices a
    # dropped frame at all, and how `HeardState` tells one utterance from the
    # same one sent again.
    clients = {}
    for frame in shells.HUD_FRAMES:
        src = frame["src"]
        if src not in clients:
            clients[src] = await BusClient.connect(None, src=src)
    try:
        rounds = 0
        while True:
            for frame in shells.HUD_FRAMES:
                await clients[frame["src"]].publish(
                    frame["topic"],
                    frame["body"],
                    conf=float(frame.get("conf", 1.0)),
                )
            rounds += 1
            # The line `load.py` waits for before it starts watching the HUD's
            # log: until one whole round is out, a corner that names nothing is
            # a corner nobody has told anything.
            print(f"publish: round {rounds}, {len(shells.HUD_FRAMES)} frames", flush=True)
            await asyncio.sleep(shells.HUD_ROUND_S)
    finally:
        for client in clients.values():
            await client.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(amain()))
    except KeyboardInterrupt:  # pragma: no cover — the driver's terminate()
        raise SystemExit(0)
