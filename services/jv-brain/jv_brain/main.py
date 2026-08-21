"""jv-brain entrypoint."""

from __future__ import annotations

import argparse
import asyncio
from typing import Optional

from jarvis_bus import BusClient

from .config import BrainConfig
from .service import BrainService


async def amain(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="jv-brain")
    ap.add_argument("--bus", default=None, help="bus address (default: $JARVIS_BUS)")
    args = ap.parse_args(argv)

    cfg = BrainConfig()
    bus = await BusClient.connect(args.bus, src="jv-brain")
    svc = BrainService(bus, cfg)
    try:
        await svc.run()
    finally:
        await svc.close()
        await bus.close()
    return 0


def cli() -> None:
    raise SystemExit(asyncio.run(amain()))


if __name__ == "__main__":
    cli()
