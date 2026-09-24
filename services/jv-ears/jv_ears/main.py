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

from .audio import CaptureMeter, MicSource, WavSource
from .config import EarsConfig
from .pipeline import EarsPipeline

HEALTH_PERIOD_S = 5.0


def health_body(meter: CaptureMeter, uptime_s: float, budgets: dict) -> dict:
    """One heartbeat, carrying what the microphone is actually doing.

    `metrics` is the schema's free-form numeric section (service-local by
    design), so the mic gauges cost no schema change — invariant 2 stays
    intact. `state` is the frozen enum: a live mic that has stopped
    delivering audio is `degraded`, which is exactly what the 2026-09-15
    field bug looked like from the outside and what nothing reported.

    `budgets` (EarsPipeline.budgets) rides in the same section: the
    windows jv-ears enforces, stated by the only process that knows them.
    Required, not optional, so a caller that forgets is a TypeError here
    rather than a consumer quietly falling back to a guess (PLAN A14).
    Values are floated on the way out: the schema says every metric is a
    number, and anything else raises here instead of reaching the bus.
    """
    state, notes = meter.health()
    body = {
        "service": "jv-ears",
        "state": state,
        "uptime_s": uptime_s,
        "period_s": HEALTH_PERIOD_S,
        "metrics": {**meter.metrics(), **{k: float(v) for k, v in budgets.items()}},
    }
    if notes:
        body["notes"] = notes
    return body


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
    await bus.subscribe(["speech.state", "dialog.listen"])
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    started = time.monotonic()
    done = threading.Event()

    def publish(topic: str, conf: float, v: int, body: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, (topic, conf, v, body))

    source = WavSource(args.wav, cfg.chunk_samples) if args.wav else MicSource(
        cfg.chunk_samples, cfg.sample_rate
    )
    # Everything the pipeline hears passes through the meter, so the
    # heartbeat can report what the DEVICE delivered rather than what this
    # process hoped it would (see CaptureMeter). This is what makes the
    # HUD's live-mic indicator a reading instead of a guess.
    meter = CaptureMeter(source, mic=args.wav is None, sample_rate=cfg.sample_rate)
    pipeline = EarsPipeline(cfg, publish)

    # A pipeline death must become a non-zero exit, or systemd's
    # Restart=on-failure never fires (2026-09-15 field bug: PortAudio lost
    # the ALSA race against PipeWire at login, the thread died, jv-ears
    # exited 0, and the mic stayed silently dead).
    pipeline_failed = threading.Event()

    def run_pipeline() -> None:
        try:
            pipeline.run(meter)
        except Exception:
            pipeline_failed.set()
            traceback.print_exc()
        finally:
            done.set()
            loop.call_soon_threadsafe(queue.put_nowait, None)

    worker = threading.Thread(target=run_pipeline, name="ears-pipeline", daemon=True)
    worker.start()

    async def follow_bus() -> None:
        """The two things another service can say to the ears.

        `speech.state` — half-duplex: close the pipeline's utterance gate
        while jv-voice speaks, because Jarvis must not hear Jarvis (see
        pipeline.set_suppressed).

        `dialog.listen` — the bounded no-wake window jv-act and jv-brain
        ask for when they need an answer (see pipeline.request_listen).
        The whole frame goes down, envelope and all: `conf` and `v` are
        grounds for refusing to open a microphone, and this loop is not
        where that is decided.
        """
        while True:
            frame = await bus.next_frame()
            if frame is None:
                return
            topic = frame["topic"]
            if topic == "speech.state":
                state = frame["body"].get("state")
                if state == "speaking":
                    pipeline.set_suppressed(True)
                elif state in ("idle", "interrupted"):
                    pipeline.set_suppressed(False)
            elif topic == "dialog.listen":
                pipeline.request_listen(
                    frame.get("body"), conf=frame.get("conf"), v=frame.get("v")
                )

    bus_task = asyncio.create_task(follow_bus())

    async def beat() -> None:
        await bus.publish(
            "sys.health",
            health_body(meter, time.monotonic() - started, pipeline.budgets()),
        )

    # Say hello BEFORE the frame loop, not on the loop's first yield: a
    # pipeline that ends immediately (--wav with nothing to read) used to
    # let the health task be cancelled before it had ever run, so jv-ears
    # came and went without the bus — and the HUD — ever hearing of it.
    await beat()

    async def health() -> None:
        while not done.is_set():
            await asyncio.sleep(HEALTH_PERIOD_S)
            await beat()

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
        bus_task.cancel()
        await bus.close()
    return 1 if pipeline_failed.is_set() else 0


def cli() -> None:
    raise SystemExit(asyncio.run(amain()))


if __name__ == "__main__":
    cli()
