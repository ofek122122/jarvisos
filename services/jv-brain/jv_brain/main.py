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


def onboard_cli() -> None:
    """`jv-onboard --reset` — wipe the profile (with confirmation) and
    let the next session re-run the meeting. Works even if the brain is
    stopped (it just deletes the file)."""
    import argparse as _ap

    from .profile import Profile, default_profile_path

    p = _ap.ArgumentParser(prog="jv-onboard")
    p.add_argument("--reset", action="store_true", help="wipe the user profile")
    p.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    a = p.parse_args()
    if not a.reset:
        path = default_profile_path()
        print(f"profile: {path}" if path.exists() else "no profile yet (first boot pending)")
        return
    if not a.yes:
        ans = input("Erase everything Jarvis has learned about you? [y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            print("cancelled")
            return
    removed = Profile.reset()
    print("profile erased — next session re-runs onboarding" if removed else "nothing to erase")


if __name__ == "__main__":
    cli()
