"""jv-ears entrypoint: pipeline in a worker thread, bus + health on the
asyncio loop. Mic by default; --wav plays fixture/recorded files through
the same pipeline (no microphone involved)."""

from __future__ import annotations

import argparse
import asyncio
import threading
import time
from pathlib import Path
from typing import Optional

from jarvis_bus import BusClient

from .audio import MicSource, WavSource
from .config import EarsConfig
from .pipeline import EarsPipeline

HEALTH_PERIOD_S = 5.0


async def amain(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="jv-ears")
    ap.add_argument("--bus", default=None, help="bus address (default: $JARVIS_BUS)")
    ap.add_argument(
        "--wav",
        nargs="*",
        type=Path,
        default=None,
        help="run these WAV files through the pipeline instead of the mic",
    )
    args = ap.parse_args(argv)

    cfg = EarsConfig()
    bus = await BusClient.connect(args.bus, src="jv-ears")
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    started = time.monotonic()
    done = threading.Event()

    def publish(topic: str, conf: float, v: int, body: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, (topic, conf, v, body))

    source = WavSource(args.wav, cfg.chunk_samples) if args.wav else MicSource(
        cfg.chunk_samples, cfg.sample_rate
    )
    pipeline = EarsPipeline(cfg, publish)

    def run_pipeline() -> None:
        try:
            pipeline.run(source)
        finally:
            done.set()
            loop.call_soon_threadsafe(queue.put_nowait, None)

    worker = threading.Thread(target=run_pipeline, name="ears-pipeline", daemon=True)
    worker.start()

    async def health() -> None:
        while not done.is_set():
            await bus.publish(
                "sys.health",
                {
                    "service": "jv-ears",
                    "state": "ok",
                    "uptime_s": time.monotonic() - started,
                    "period_s": HEALTH_PERIOD_S,
                },
            )
            await asyncio.sleep(HEALTH_PERIOD_S)

    health_task = asyncio.create_task(health())
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            topic, conf, v, body = item
            await bus.publish(topic, body, conf=conf, v=v)
    finally:
        health_task.cancel()
        await bus.close()
    return 0


def cli() -> None:
    raise SystemExit(asyncio.run(amain()))


if __name__ == "__main__":
    cli()
