"""jv-brain v0: conversation only (BRIEF-phase1 task 5 — do not
gold-plate). Consumes audio.transcript finals + brain.request, calls the
llama-server OpenAI endpoint, publishes brain.response and (for spoken
inputs) speech.say. NO tools, NO memory writes — Phases 2 and 4."""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from collections import deque
from typing import Optional

import httpx

from jarvis_bus import BusClient

from .config import BrainConfig

HEALTH_PERIOD_S = 5.0

# "Hey Jarvis," / "hey jarvis." / "Jarvis," etc. at the start of an
# utterance — ears publishes what was said; stripping the address is ours.
_WAKE_PREFIX = re.compile(r"^\s*(hey|okay|ok)?[\s,]*jarvis[\s,.!?]*", re.IGNORECASE)
_THINK_BLOCK = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


def strip_wake_prefix(text: str) -> str:
    stripped = _WAKE_PREFIX.sub("", text, count=1).strip()
    return stripped if stripped else text.strip()


class Conversation:
    """Rolling context: bounded turns + crude char cap + idle reset."""

    def __init__(self, cfg: BrainConfig) -> None:
        self.cfg = cfg
        self.messages: deque[dict] = deque()
        self.last_activity = 0.0

    def add(self, role: str, content: str, now: float) -> None:
        if self.last_activity and now - self.last_activity > self.cfg.idle_reset_s:
            self.messages.clear()
        self.last_activity = now
        self.messages.append({"role": role, "content": content})
        while len(self.messages) > self.cfg.max_turns * 2:
            self.messages.popleft()
        while sum(len(m["content"]) for m in self.messages) > self.cfg.max_context_chars:
            if len(self.messages) <= 1:
                break
            self.messages.popleft()


class BrainService:
    def __init__(self, bus: BusClient, cfg: BrainConfig) -> None:
        self.bus = bus
        self.cfg = cfg
        self.system_prompt = self._load_system_prompt()
        self.conversations: dict[str, Conversation] = {}
        self._started = time.monotonic()
        self._http = httpx.AsyncClient(timeout=cfg.request_timeout_s)

    def _load_system_prompt(self) -> str:
        path = self.cfg.personality_dir / "system.md"
        text = path.read_text(encoding="utf-8")
        # Strip HTML comments (repo annotations, not personality).
        return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()

    def _rung(self) -> tuple[Optional[int], str]:
        """(rung index, backend) as recorded by jv-llm-launch."""
        try:
            data = dict(
                line.split("=", 1)
                for line in self.cfg.rung_file.read_text(encoding="utf-8").splitlines()
                if "=" in line
            )
            return int(data.get("rung", -1)), data.get("backend", "gpu")
        except (OSError, ValueError):
            return None, "gpu"

    async def _complete(self, conv: Conversation) -> tuple[str, str]:
        """-> (text, finish_reason)."""
        resp = await self._http.post(
            f"{self.cfg.llm_url}/v1/chat/completions",
            json={
                "model": self.cfg.model_name,
                "messages": [{"role": "system", "content": self.system_prompt}]
                + list(conv.messages),
                "temperature": self.cfg.temperature,
                "max_tokens": self.cfg.max_tokens,
                # Qwen3: keep the thinking mode off for voice latency.
                "chat_template_kwargs": {"enable_thinking": False},
            },
        )
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]
        text = _THINK_BLOCK.sub("", choice["message"]["content"] or "").strip()
        finish = choice.get("finish_reason") or "stop"
        return text, ("length" if finish == "length" else "stop")

    async def _handle_input(
        self,
        text: str,
        conversation_id: str,
        utterance_id: Optional[str],
        speak: bool,
        in_reply_to: dict,
    ) -> None:
        conv = self.conversations.setdefault(conversation_id, Conversation(self.cfg))
        conv.add("user", text, time.monotonic())
        t0 = time.monotonic()
        rung, backend = self._rung()
        try:
            reply, finish = await self._complete(conv)
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            await self.bus.publish(
                "brain.response",
                {
                    "text": "",
                    "finish_reason": "error",
                    "conversation_id": conversation_id,
                    "in_reply_to": in_reply_to,
                    **({"utterance_id": utterance_id} if utterance_id else {}),
                },
            )
            await self._health("degraded", notes=f"llm error: {exc}")
            return
        conv.add("assistant", reply, time.monotonic())

        body = {
            "text": reply,
            "finish_reason": finish,
            "conversation_id": conversation_id,
            "in_reply_to": in_reply_to,
            "model": self.cfg.model_name,
            "backend": backend,
            "latency_ms": (time.monotonic() - t0) * 1e3,
        }
        if utterance_id:
            body["utterance_id"] = utterance_id
        await self.bus.publish("brain.response", body)

        if speak and reply:
            await self.bus.publish(
                "speech.say",
                {
                    "text": reply,
                    "say_id": str(uuid.uuid4()),
                    "in_reply_to_utterance": utterance_id,
                },
            )

    async def _health(self, state: str = "ok", notes: Optional[str] = None) -> None:
        rung, backend = self._rung()
        body: dict = {
            "service": "jv-brain",
            "state": state,
            "uptime_s": time.monotonic() - self._started,
            "period_s": HEALTH_PERIOD_S,
        }
        metrics: dict = {}
        if rung is not None:
            metrics["llm_rung"] = float(rung)  # Ofek: rung visible in jv health
            metrics["llm_gpu"] = 1.0 if backend == "gpu" else 0.0
        if metrics:
            body["metrics"] = metrics
        if notes:
            body["notes"] = notes
        await self.bus.publish("sys.health", body)

    async def run(self) -> None:
        await self.bus.subscribe(["audio.transcript", "brain.request"])
        await self._health()
        health_at = time.monotonic()
        while True:
            if time.monotonic() - health_at >= HEALTH_PERIOD_S:
                health_at = time.monotonic()
                await self._health()
            try:
                frame = await asyncio.wait_for(self.bus.next_frame(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            if frame is None:
                break
            topic, body = frame["topic"], frame["body"]
            in_reply_to = {"src": frame["src"], "seq": frame["seq"]}
            if topic == "audio.transcript":
                if body.get("kind") != "final":
                    continue  # partials are for the HUD, not for acting on
                await self._handle_input(
                    strip_wake_prefix(body["text"]),
                    "voice",
                    body.get("utterance_id"),
                    speak=True,
                    in_reply_to=in_reply_to,
                )
            elif topic == "brain.request":
                await self._handle_input(
                    body["text"],
                    body.get("conversation_id", "default"),
                    body.get("utterance_id"),
                    speak=body.get("speak", True),
                    in_reply_to=in_reply_to,
                )

    async def close(self) -> None:
        await self._http.aclose()
