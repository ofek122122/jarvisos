"""jv-ears entrypoint: pipeline in a worker thread, bus + health on the
asyncio loop. Mic by default; --wav plays fixture/recorded files through
the same pipeline (no microphone involved)."""

from __future__ import annotations

import argparse
import asyncio
import threading
import time
import traceback
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
    await bus.subscribe(["speech.state"])
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

    # A pipeline death must become a non-zero exit, or systemd's
    # Restart=on-failure never fires (2026-09-15 field bug: PortAudio lost
    # the ALSA race against PipeWire at login, the thread died, jv-ears
    # exited 0, and the mic stayed silently dead).
    pipeline_failed = threading.Event()

    def run_pipeline() -> None:
        try:
            pipeline.run(source)
        except Exception:
            pipeline_failed.set()
            traceback.print_exc()
        finally:
            done.set()
            loop.call_soon_threadsafe(queue.put_nowait, None)

    worker = threading.Thread(target=run_pipeline, name="ears-pipeline", daemon=True)
    worker.start()

    async def follow_speech_state() -> None:
        """Half-duplex: close the pipeline's utterance gate while jv-voice
        speaks — Jarvis must not hear Jarvis (see pipeline.set_suppressed)."""
        while True:
            frame = await bus.next_frame()
            if frame is None:
                return
            if frame["topic"] != "speech.state":
                continue
            state = frame["body"].get("state")
            if state == "speaking":
                pipeline.set_suppressed(True)
            elif state in ("idle", "interrupted"):
                pipeline.set_suppressed(False)

    state_task = asyncio.create_task(follow_speech_state())

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
        state_task.cancel()
        await bus.close()
    return 1 if pipeline_failed.is_set() else 0


def cli() -> None:
    raise SystemExit(asyncio.run(amain()))


if __name__ == "__main__":
    cli()
