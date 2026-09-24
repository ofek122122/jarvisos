"""jv-guard entrypoint: the engines that actually run on ares.

ClamAV is the authoritative one — its silence is what `clean` means. The
shape engine is advisory and exists so the approved policy's middle rung
(`suspicious`) has a producer: a packed or self-modifying binary that no
signature matches is the case ClamAV structurally cannot see, and the
case a confirmation prompt is for. Order matters only for how
`scanned_by` reads."""

from __future__ import annotations

import argparse
import asyncio
from typing import Optional

from jarvis_bus import BusClient

from .heuristics import PEHeuristicScanner
from .scan import ClamAVScanner
from .service import GuardService


async def amain(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="jv-guard")
    ap.add_argument("--bus", default=None)
    args = ap.parse_args(argv)
    bus = await BusClient.connect(args.bus, src="jv-guard")
    try:
        engines = [ClamAVScanner(), PEHeuristicScanner()]
        await GuardService(bus, engines).run()
    finally:
        await bus.close()
    return 0


def cli() -> None:
    raise SystemExit(asyncio.run(amain()))


if __name__ == "__main__":
    cli()
