"""jv-voice state machine: consumes speech.say (+ audio.wake for
barge-in), speaks through the Player, publishes speech.state on every
transition.

Priority semantics (schemas/speech.say.json):
  low    — dropped unless completely idle with an empty queue
  normal — FIFO
  urgent — preempts an interruptible utterance (reason=preempted);
           the preempted utterance is DROPPED, not resumed (v0)
Interruption: audio.wake while speaking an interruptible utterance stops
playback mid-sentence (reason=wake). BRIEF-phase1 exit item 3.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Optional

from jarvis_bus import BusClient

from .player import Player
from .tts import Synthesizer

HEALTH_PERIOD_S = 5.0


class VoiceService:
    def __init__(self, bus: BusClient, synth: Synthesizer, player: Player) -> None:
        self.bus = bus
        self.synth = synth
        self.player = player
        self._queue: deque[dict] = deque()
        self._abort = asyncio.Event()
        self._speaking: Optional[dict] = None
        self._interrupt_reason: Optional[str] = None
        self._wake_task: Optional[asyncio.Task] = None
        self._started = time.monotonic()

    async def _state(self, state: str, say_id: Optional[str] = None, reason: Optional[str] = None) -> None:
        body: dict = {"state": state}
        if say_id is not None:
            body["say_id"] = say_id
        if reason is not None:
            body["reason"] = reason
        await self.bus.publish("speech.state", body)

    # ------------------------------------------------------------ intake

    def _enqueue(self, body: dict) -> None:
        prio = body.get("priority", "normal")
        if prio == "low" and (self._speaking or self._queue):
            return  # low is droppable by contract
        if prio == "urgent":
            self._queue.appendleft(body)
            if self._speaking and self._speaking.get("interruptible", True):
                self._interrupt_reason = "preempted"
                self._abort.set()
        else:
            self._queue.append(body)

    def _on_wake(self) -> None:
        if self._speaking and self._speaking.get("interruptible", True):
            self._interrupt_reason = "wake"
            self._abort.set()

    # ------------------------------------------------------------- speak

    async def _speak(self, item: dict) -> None:
        say_id = item["say_id"]
        self._speaking = item
        self._abort.clear()
        self._interrupt_reason = None
        await self._state("speaking", say_id)
        try:
            audio, rate = await asyncio.get_running_loop().run_in_executor(
                None, self.synth.synth, item["text"]
            )
            if self._abort.is_set():
                await self._state("interrupted", say_id, self._interrupt_reason or "preempted")
                await self._state("idle")
                return
            completed = await self.player.play(audio, rate, self._abort)
            if completed:
                await self._state("idle", say_id, "completed")
            else:
                await self._state("interrupted", say_id, self._interrupt_reason or "wake")
                await self._state("idle")
        except Exception as exc:  # noqa: BLE001 - report, stay alive
            await self._state("idle", say_id, "error")
            await self.bus.publish(
                "sys.health",
                {
                    "service": "jv-voice",
                    "state": "degraded",
                    "uptime_s": time.monotonic() - self._started,
                    "period_s": HEALTH_PERIOD_S,
                    "notes": f"synthesis/playback error: {exc}",
                },
            )
        finally:
            self._speaking = None

    # --------------------------------------------------------------- run

    async def run(self) -> None:
        await self.bus.subscribe(["speech.say", "audio.wake"])
        await self._state("idle")
        speak_task: Optional[asyncio.Task] = None
        health_at = 0.0
        while True:
            now = time.monotonic()
            if now - health_at >= HEALTH_PERIOD_S:
                health_at = now
                await self.bus.publish(
                    "sys.health",
                    {
                        "service": "jv-voice",
                        "state": "ok",
                        "uptime_s": now - self._started,
                        "period_s": HEALTH_PERIOD_S,
                    },
                )
            if speak_task and speak_task.done():
                speak_task = None
            if speak_task is None and self._queue:
                speak_task = asyncio.create_task(self._speak(self._queue.popleft()))

            try:
                frame = await asyncio.wait_for(self.bus.next_frame(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            if frame is None:
                break
            topic = frame.get("topic")
            if topic == "speech.say":
                self._enqueue(frame["body"])
            elif topic == "audio.wake":
                self._on_wake()
        if speak_task:
            self._abort.set()
            await speak_task
