"""jv-compat CLI: `jv-compat install <path>` runs the pipeline once.
(Daemon/watch-folder mode is a later refinement; installs are on-demand
in v0 — decision in DECISIONS-pending.md.)"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Optional

from jarvis_bus import BusClient

from .install import Installer, RealRunner


async def amain(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="jv-compat")
    sub = ap.add_subparsers(dest="cmd", required=True)
    inst = sub.add_parser("install", help="screen + install one Windows installer")
    inst.add_argument("path", type=Path)
    inst.add_argument("--bus", default=None)
    args = ap.parse_args(argv)

    bus = await BusClient.connect(args.bus, src="jv-compat")
    try:
        outcome = await Installer(bus, RealRunner()).install(args.path)
    finally:
        await bus.close()
    print(f"jv-compat: {args.path} -> {outcome}")
    return 0 if outcome == "installed" else 1


def cli() -> None:
    raise SystemExit(asyncio.run(amain()))


if __name__ == "__main__":
    cli()
