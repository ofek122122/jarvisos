"""jv-context entrypoint (niri backend + wpctl probe on the machine)."""

from __future__ import annotations

import argparse
import asyncio
from typing import Optional

from jarvis_bus import BusClient

from .compositor import NiriBackend
from .service import ContextService
from .system import WpctlProbe


async def amain(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="jv-context")
    ap.add_argument("--bus", default=None, help="bus address (default: $JARVIS_BUS)")
    args = ap.parse_args(argv)

    bus = await BusClient.connect(args.bus, src="jv-context")
    try:
        await ContextService(bus, NiriBackend(), WpctlProbe()).run()
    finally:
        await bus.close()
    return 0


def cli() -> None:
    raise SystemExit(asyncio.run(amain()))


if __name__ == "__main__":
    cli()
