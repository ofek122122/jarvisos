"""jv-voice entrypoint."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Optional

from jarvis_bus import BusClient

from .config import VoiceConfig
from .player import SoundDevicePlayer
from .service import VoiceService
from .tts import Synthesizer


async def amain(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="jv-voice")
    ap.add_argument("--bus", default=None, help="bus address (default: $JARVIS_BUS)")
    ap.add_argument("--personality-dir", type=Path, default=None)
    args = ap.parse_args(argv)

    cfg = VoiceConfig.load(args.personality_dir)
    synth = Synthesizer(cfg)
    bus = await BusClient.connect(args.bus, src="jv-voice")
    try:
        player = SoundDevicePlayer(cfg.output_device)
        await VoiceService(bus, synth, player).run()
    finally:
        await bus.close()
    return 0


def cli() -> None:
    raise SystemExit(asyncio.run(amain()))


if __name__ == "__main__":
    cli()
