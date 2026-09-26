"""jv-dictate entrypoint: hold a key, speak, release — the transcript goes
to a Sink (injector.py; a fake one until PLAN F5's jv-act tool is reviewed).

No wake word, no VAD: the key IS the gate, so this owns none of jv-ears'
continuous-listening machinery and asks jv-ears for nothing over the bus —
it opens its own short-lived capture stream only while the key is held,
which is the whole reason this can exist without a schema change: nobody
outside this process needs to know a recording happened except through
sys.health's already-free-form `metrics` (see service.DictateService).

All the state and the transitions live in service.py, unit-tested without
hardware. This file is just wiring: real evdev devices, a real microphone,
a real bus — `evdev` and `sounddevice` are imported lazily, only here, so
the rest of the package (and its tests) import cleanly on a machine that
has not yet built/switched this service, the same discipline jv_ears.audio
follows for the same reason.
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Optional

from jarvis_bus import BusClient

from .asr import Transcriber
from .audio import AudioRecorder
from .config import DictateConfig
from .injector import LogSink, Sink
from .ptt import PushToTalk
from .service import DictateService

EXPIRY_POLL_S = 0.5
BEAT_POLL_S = 0.5


def resolve_keycode(name: str) -> int:
    """"KEY_PAUSE" -> evdev.ecodes.KEY_PAUSE. A KeyError here is a config
    typo, not a hardware fault, so it is left to raise past this function
    rather than silently falling back to a key nobody chose."""
    from evdev import ecodes

    return ecodes.ecodes[name]


async def watch_device(dev, service: DictateService) -> None:
    """One evdev device's key events, filtered to edges (press/release) —
    value 2 is autorepeat, and PushToTalk only wants to hear about a key
    actually changing state. Runs until the device disappears (unplugged,
    or the process is stopping)."""
    from evdev import categorize, ecodes
    from evdev.events import KeyEvent

    async for event in dev.async_read_loop():
        if event.type != ecodes.EV_KEY:
            continue
        key = categorize(event)
        if key.keystate == KeyEvent.key_hold:
            continue
        await service.on_key_event(event.code, key.keystate == KeyEvent.key_down)


async def watch_expiry(service: DictateService) -> None:
    while True:
        await asyncio.sleep(EXPIRY_POLL_S)
        await service.poll_expiry()


async def watch_health(service: DictateService) -> None:
    while True:
        await asyncio.sleep(BEAT_POLL_S)
        await service.maybe_beat()


def devices_with_key(keycode: int):
    """Every input device that can report `keycode` — mirrors keyd's own
    `ids = ["*"]` wildcard (modules/super-menu.nix): this machine's
    keyboard is whatever is plugged in, not one hardcoded /dev/input path."""
    from evdev import InputDevice, ecodes, list_devices

    for path in list_devices():
        dev = InputDevice(path)
        if keycode in dev.capabilities().get(ecodes.EV_KEY, []):
            yield dev


async def amain(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="jv-dictate")
    ap.add_argument("--bus", default=None, help="bus address (default: $JARVIS_BUS)")
    args = ap.parse_args(argv)

    cfg = DictateConfig()
    bus = await BusClient.connect(args.bus, src="jv-dictate")

    transcriber = Transcriber(cfg.whisper_dir, beam_size=cfg.asr_beam_size)
    recorder = AudioRecorder(sample_rate=cfg.sample_rate)
    sink: Sink = LogSink()
    keycode = resolve_keycode(cfg.trigger_key)
    ptt = PushToTalk(keycode)
    service = DictateService(bus, transcriber, recorder, sink, ptt, health_period_s=cfg.health_period_s)

    await service.start()

    watchers = [asyncio.create_task(watch_device(dev, service)) for dev in devices_with_key(keycode)]
    background = [
        asyncio.create_task(watch_expiry(service)),
        asyncio.create_task(watch_health(service)),
    ]

    try:
        await asyncio.gather(*watchers, *background)
    finally:
        for t in (*watchers, *background):
            t.cancel()
        await bus.close()
    return 0


def cli() -> None:
    raise SystemExit(asyncio.run(amain()))


if __name__ == "__main__":
    cli()
