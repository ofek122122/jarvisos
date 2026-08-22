"""jv-guard entrypoint (real ClamAV engine)."""

from __future__ import annotations

import argparse
import asyncio
from typing import Optional

from jarvis_bus import BusClient

from .scan import ClamAVScanner
from .service import GuardService


async def amain(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="jv-guard")
    ap.add_argument("--bus", default=None)
    args = ap.parse_args(argv)
    bus = await BusClient.connect(args.bus, src="jv-guard")
    try:
        await GuardService(bus, [ClamAVScanner()]).run()
    finally:
        await bus.close()
    return 0


def cli() -> None:
    raise SystemExit(asyncio.run(amain()))


if __name__ == "__main__":
    cli()
