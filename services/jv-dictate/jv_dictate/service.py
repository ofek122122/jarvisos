"""The service: owns the state (PushToTalk, AudioRecorder, a HealthBeat)
and the pure transitions between them. `main.py` wires this to a real bus,
real evdev devices and a real microphone; tests drive `on_key_event()` and
`poll_expiry()` directly against fakes, so the whole start -> record ->
transcribe -> sink -> heartbeat path is exercised without hardware.

Uses jarvis_bus.HealthBeat (services/pylib/jarvis_bus/health.py) — the
shared "beat every period, and immediately on state change, and an
off-schedule beat resets the period" rule jv-guard already follows, named
so a new service does not reinvent jv-ears' own pump_health by hand.
"""

from __future__ import annotations

import asyncio
import time
from typing import Callable, Optional

from jarvis_bus import HealthBeat

from .asr import Transcriber
from .audio import AudioRecorder
from .injector import Sink
from .pipeline import transcribe_and_send
from .ptt import PushToTalk


class DictateService:
    def __init__(
        self,
        bus,
        transcriber: Transcriber,
        recorder: AudioRecorder,
        sink: Sink,
        ptt: PushToTalk,
        *,
        health_period_s: float = 5.0,
        executor: Optional[Callable] = None,
        clock=time.monotonic,
    ) -> None:
        self.bus = bus
        self.transcriber = transcriber
        self.recorder = recorder
        self.sink = sink
        self.ptt = ptt
        self._beats = HealthBeat(health_period_s, now=clock)
        self._clock = clock
        self._started = clock()
        # Injectable so tests run transcription synchronously, in-process,
        # rather than on a real thread pool: None -> the real event loop
        # executor, exactly the way jv-guard's scanners run (invariant 5 —
        # transcription is CPU work and must never block the bus).
        self._executor = executor

    async def start(self) -> None:
        """The hello beat — said once, before the first event, so a
        process that never sees a key press still tells the bus it is up
        (the same reasoning jv-ears' main.py gives for beating before its
        frame loop starts)."""
        await self._health()

    async def on_key_event(self, keycode: int, pressed: bool) -> None:
        transition = self.ptt.feed(keycode, pressed)
        if transition == "start":
            self.recorder.start()
            await self._health()
        elif transition == "stop":
            await self._finish_recording()

    async def poll_expiry(self) -> None:
        """Call on whatever cadence main.py chooses (it polls every 0.5 s).
        The hard safety cap, PushToTalk.MAX_RECORDING_S: a key that never
        reports its own release must not become an open mic."""
        if self.ptt.expired():
            self.ptt.force_stop()
            await self._finish_recording()

    async def maybe_beat(self) -> None:
        """Call on whatever cadence main.py chooses. A no-op unless a full
        period has elapsed since the last beat (HealthBeat.due) — the
        periodic half of the heartbeat; on_key_event/poll_expiry cover the
        state-change half."""
        if self._beats.due:
            await self._health()

    async def _finish_recording(self) -> None:
        audio = self.recorder.stop()
        await self._transcribe(audio)
        await self._health()

    async def _transcribe(self, audio) -> None:
        if self._executor is not None:
            self._executor(transcribe_and_send, audio, self.transcriber, self.sink)
            return
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, transcribe_and_send, audio, self.transcriber, self.sink)

    async def _health(self) -> None:
        self._beats.beat()  # before the publish, not after — see HealthBeat
        await self.bus.publish(
            "sys.health",
            {
                "service": "jv-dictate",
                "state": "ok",
                "uptime_s": self._clock() - self._started,
                "period_s": self._beats.period_s,
                # sys.health's `metrics` is free-form and service-local
                # (schemas/sys.health.json) — the same extension point
                # jv-ears' `mic_open` already rides on, so a future HUD
                # plate needs no schema change to read this.
                "metrics": {"recording": 1.0 if self.ptt.active else 0.0},
            },
        )
