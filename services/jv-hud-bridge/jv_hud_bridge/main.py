"""jv-hud-bridge entrypoint. Reads the bus, writes JSON lines to stdout."""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import List, Optional

from jarvis_bus import BusClient

from .bridge import DEFAULT_TOPICS, run


async def amain(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="jv-hud-bridge",
        description="Forward bus frames to the HUD as one line of JSON each.",
    )
    ap.add_argument("--bus", default=None, help="bus address (default: $JARVIS_BUS)")
    ap.add_argument(
        "--topic",
        action="append",
        dest="topics",
        metavar="TOPIC",
        help=f"topic to subscribe to; repeatable (default: {' '.join(DEFAULT_TOPICS)})",
    )
    args = ap.parse_args(argv)

    # src is set for symmetry with the other services, but nothing the
    # bridge sends ever carries it: it only ever sends `sub`.
    async def connect():
        return await BusClient.connect(args.bus, src="jv-hud")

    await run(connect, sys.stdout, args.topics or DEFAULT_TOPICS)
    return 0


def cli() -> None:
    try:
        raise SystemExit(asyncio.run(amain()))
    except KeyboardInterrupt:  # pragma: no cover - Ctrl-C is not a failure
        raise SystemExit(0)


if __name__ == "__main__":
    cli()
