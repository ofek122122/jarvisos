"""jv-voice state machine: consumes speech.say (+ audio.wake for
barge-in), speaks through the Player, publishes speech.state on every
transition.

**The unit is the TURN, not the sentence.** jv-brain streams the LLM and
publishes one speech.say per sentence, all carrying the same `reply_group`
(schemas/speech.say.json). Those sentences are ONE thing the user hears,
so they get one `speaking` and one `idle`: a sentence ending is not the
answer ending, and reporting it as one made jv-ears open its half-duplex
gate mid-reply and the HUD blink off and on once per sentence.

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

# How long a streamed reply may go quiet between sentences before jv-voice
# calls the turn over. The brain publishes sentence N+1 while N is still
# playing, so it is normally already queued; this only bridges the bus,
# not the brain — the frame that was published as the previous sentence
# ended and is still in flight. Bounded on purpose: past it we stop
# asserting a turn we can no longer see, which is what a brain that died
# mid-answer looks like.
TURN_GAP_S = 0.5

# Groups we refuse to speak any more of. jv-brain does not watch
# audio.wake, so it keeps publishing the sentences of a reply the user
# already interrupted; purging what is QUEUED only silences the ones that
# had arrived. Bounded — this service runs for weeks, and a group older
# than the last handful is long over.
DROPPED_GROUPS = 8


class VoiceService:
    def __init__(self, bus: BusClient, synth: Synthesizer, player: Player) -> None:
        self.bus = bus
        self.synth = synth
        self.player = player
        self._queue: deque[dict] = deque()
        self._abort = asyncio.Event()
        # Set whenever something a waiting turn cares about happens (a new
        # item queued, an interruption). Lets the inter-sentence gap react
        # immediately instead of polling.
        self._nudge = asyncio.Event()
        self._speaking: Optional[dict] = None
        self._interrupt_reason: Optional[str] = None
        self._dropped: deque[str] = deque(maxlen=DROPPED_GROUPS)
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
        group = body.get("reply_group")
        if group and group in self._dropped:
            return  # a turn the user already interrupted; see DROPPED_GROUPS
        prio = body.get("priority", "normal")
        if prio == "low" and (self._speaking or self._queue):
            return  # low is droppable by contract
        if prio == "urgent":
            self._queue.appendleft(body)
            if self._speaking and self._speaking.get("interruptible", True):
                self._interrupt("preempted")
        else:
            self._queue.append(body)
        self._nudge.set()

    def _interrupt(self, reason: str) -> None:
        """End the turn in progress: the rest of it must not be spoken."""
        self._interrupt_reason = reason
        self._drop_group((self._speaking or {}).get("reply_group"))
        self._abort.set()
        self._nudge.set()

    def _drop_group(self, reply_group: Optional[str]) -> None:
        """Purge a streamed reply — when one of its sentences is interrupted,
        the rest of the turn must go too, or Jarvis talks over the user who
        just barged in. Both the sentences already queued and the ones the
        brain has not published yet (it does not know about the wake)."""
        if not reply_group:
            return
        if reply_group not in self._dropped:
            self._dropped.append(reply_group)
        self._queue = deque(
            item for item in self._queue if item.get("reply_group") != reply_group
        )

    def _on_wake(self) -> None:
        if self._speaking and self._speaking.get("interruptible", True):
            self._interrupt("wake")

    # ------------------------------------------------------------- speak

    async def _speak_turn(self, item: dict) -> None:
        """Speak one turn: `item`, then the rest of its reply_group as the
        sentences arrive. `self._speaking` stays set across the gaps between
        them, so a barge-in landing between two sentences still ends the
        whole turn rather than being ignored."""
        try:
            while True:
                if not await self._speak_one(item):
                    return  # its terminal state is already published
                nxt = await self._next_in_turn(item)
                if nxt is None:
                    await self._state("idle", item["say_id"], "completed")
                    return
                item = nxt
        finally:
            self._speaking = None

    async def _speak_one(self, item: dict) -> bool:
        """Speak ONE utterance. True if it played to its end and the turn may
        continue; False if the turn is over, in which case the state saying
        so has been published here."""
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
                return False
            if await self.player.play(audio, rate, self._abort):
                return True
            await self._state("interrupted", say_id, self._interrupt_reason or "wake")
            await self._state("idle")
            return False
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
            return False

    async def _next_in_turn(self, spoken: dict) -> Optional[dict]:
        """The next sentence of this turn, or None if the turn is over.

        Waits up to TURN_GAP_S for it, because the brain may still be
        generating it. An interruption arriving in that gap ends the turn
        (the utterance that just finished completed, so it is not reported
        as interrupted — but the rest of its group is dropped).

        Sentences of the turn are taken out of FIFO order if something
        unrelated is queued behind them: a turn is one thing, and an
        announcement from elsewhere belongs after it, not inside it.
        """
        group = spoken.get("reply_group")
        if not group:
            return None
        deadline = time.monotonic() + TURN_GAP_S
        while True:
            self._nudge.clear()
            if self._abort.is_set():
                return None
            for i, candidate in enumerate(self._queue):
                if candidate.get("reply_group") == group:
                    del self._queue[i]
                    return candidate
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            try:
                await asyncio.wait_for(self._nudge.wait(), timeout=remaining)
            except asyncio.TimeoutError:
                pass

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
                speak_task = asyncio.create_task(self._speak_turn(self._queue.popleft()))

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
            self._nudge.set()
            await speak_task
