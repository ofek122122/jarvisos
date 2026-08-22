"""jv-brain v0: conversation only (BRIEF-phase1 task 5 — do not
gold-plate). Consumes audio.transcript finals + brain.request, calls the
llama-server OpenAI endpoint, publishes brain.response and (for spoken
inputs) speech.say. NO tools, NO memory writes — Phases 2 and 4."""

from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from collections import deque
from typing import Optional

import httpx

from jarvis_bus import BusClient

from . import onboarding
from .config import BrainConfig
from .profile import Profile
from .tools import load_tools, openai_tool_defs

HEALTH_PERIOD_S = 5.0

# Hard rules (BRIEF-phase2 §3)
MAX_TOOL_CALLS_PER_TURN = 5
# Tool round-trip budget: registry timeout + the 15s confirm window +
# margin. A stuck act must not wedge the conversation forever.
ACTION_RESULT_TIMEOUT_S = 60.0

# "Hey Jarvis," / "hey jarvis." / "Jarvis," etc. at the start of an
# utterance — ears publishes what was said; stripping the address is ours.
_WAKE_PREFIX = re.compile(r"^\s*(hey|okay|ok)?[\s,]*jarvis[\s,.!?]*", re.IGNORECASE)
_THINK_BLOCK = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


def strip_wake_prefix(text: str) -> str:
    stripped = _WAKE_PREFIX.sub("", text, count=1).strip()
    return stripped if stripped else text.strip()


_YES = {"yes", "yeah", "yep", "yup", "correct", "right", "that's right", "perfect"}
_NO = {"no", "nope", "wrong", "not quite", "not right", "incorrect"}


def _yes_no(text: str) -> Optional[bool]:
    n = " ".join(
        "".join(c for c in text.lower() if c.isalnum() or c.isspace() or c == "'").split()
    )
    if n in _YES or n.startswith("yes"):
        return True
    if n in _NO or n.startswith("no"):
        return False
    return None


def _now_iso() -> str:
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    except (OSError, ValueError):
        return "1970-01-01T00:00:00Z"


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
        self.add_raw({"role": role, "content": content})

    def add_raw(self, message: dict) -> None:
        """Append a pre-built message (assistant tool_calls, tool results)."""
        self.messages.append(message)
        while len(self.messages) > self.cfg.max_turns * 2:
            self.messages.popleft()
        while (
            sum(len(m.get("content") or "") for m in self.messages)
            > self.cfg.max_context_chars
        ):
            if len(self.messages) <= 1:
                break
            self.messages.popleft()


class BrainService:
    def __init__(self, bus: BusClient, cfg: BrainConfig) -> None:
        self.bus = bus
        self.cfg = cfg
        self.profile = Profile.load()
        self.system_template = self._load_system_template()
        self.conversations: dict[str, Conversation] = {}
        self._started = time.monotonic()
        self._http = httpx.AsyncClient(timeout=cfg.request_timeout_s)
        # Tool calling (v1): defs from the shared registry TOML.
        self.tools = load_tools()
        self.tool_defs = openai_tool_defs(self.tools)
        self._pending_results: dict[str, asyncio.Future] = {}
        self._hallucinated_calls = 0
        # onboarding + follow-up state
        self._onboarding_stage: Optional[str] = None
        self._onboarding_name: Optional[str] = None
        self._followup_asked_this_session = False

    def _load_system_template(self) -> str:
        path = self.cfg.personality_dir / "system.md"
        text = path.read_text(encoding="utf-8")
        # Strip HTML comments (repo annotations, not personality).
        return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()

    @property
    def system_prompt(self) -> str:
        """Template + the profile's 'About your user' block, assembled
        fresh each call so a name learned mid-session takes effect at
        once. Nothing about the user is baked into the template."""
        return (
            f"{self.system_template}\n\n## About your user\n"
            f"{self.profile.render_about_user()}"
        )

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

    async def _complete(self, conv: Conversation) -> tuple[dict, str]:
        """-> (message, finish_reason). message may carry tool_calls."""
        payload = {
            "model": self.cfg.model_name,
            "messages": [{"role": "system", "content": self.system_prompt}]
            + list(conv.messages),
            "temperature": self.cfg.temperature,
            "max_tokens": self.cfg.max_tokens,
            # Qwen3: keep the thinking mode off for voice latency.
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if self.tool_defs:
            payload["tools"] = self.tool_defs
            payload["tool_choice"] = "auto"
        resp = await self._http.post(
            f"{self.cfg.llm_url}/v1/chat/completions", json=payload
        )
        resp.raise_for_status()
        choice = resp.json()["choices"][0]
        finish = choice.get("finish_reason") or "stop"
        return choice["message"], ("length" if finish == "length" else "stop")

    async def _run_tool(self, name: str, args: dict, utterance_id: Optional[str]) -> str:
        """Publish intent.action, await the matching action.result.
        Returns the tool-role content string for the LLM."""
        info = self.tools[name]
        rid = str(uuid.uuid4())
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending_results[rid] = fut
        body = {
            "request_id": rid,
            "tool": name,
            "args": args,
            "capability": info.capability,
            "needs_confirmation": info.capability in ("destructive", "privileged"),
        }
        if utterance_id:
            body["utterance_id"] = utterance_id
        await self.bus.publish("intent.action", body)
        try:
            result = await asyncio.wait_for(fut, ACTION_RESULT_TIMEOUT_S)
        except asyncio.TimeoutError:
            return json.dumps({"ok": False, "error": "act_unresponsive"})
        finally:
            self._pending_results.pop(rid, None)
        keep = {k: result[k] for k in ("ok", "output", "error", "detail") if k in result}
        return json.dumps(keep)

    async def _tool_loop(
        self, conv: Conversation, utterance_id: Optional[str]
    ) -> tuple[str, str]:
        """The v1 loop: complete -> execute tool calls -> feed results ->
        repeat, under the hard rules (max 5 calls/turn, hallucinated
        names rejected without ever reaching jv-act)."""
        calls_used = 0
        while True:
            msg, finish = await self._complete(conv)
            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                text = _THINK_BLOCK.sub("", msg.get("content") or "").strip()
                return text, finish
            conv.add_raw(
                {"role": "assistant", "content": msg.get("content"), "tool_calls": tool_calls}
            )
            for tc in tool_calls:
                tc_id = tc.get("id", "")
                fname = tc.get("function", {}).get("name", "")
                try:
                    fargs = json.loads(tc.get("function", {}).get("arguments") or "{}")
                except json.JSONDecodeError:
                    fargs = None
                if calls_used >= MAX_TOOL_CALLS_PER_TURN:
                    content = json.dumps(
                        {"ok": False, "error": "tool_call_limit",
                         "detail": f"max {MAX_TOOL_CALLS_PER_TURN} tool calls per turn"}
                    )
                elif fname not in self.tools:
                    # Hallucinated tool: never reaches jv-act; logged.
                    self._hallucinated_calls += 1
                    content = json.dumps(
                        {"ok": False, "error": "unknown_tool",
                         "detail": f"'{fname}' does not exist; do not invent tools"}
                    )
                elif fargs is None:
                    content = json.dumps({"ok": False, "error": "unparseable_arguments"})
                else:
                    calls_used += 1
                    content = await self._run_tool(fname, fargs, utterance_id)
                conv.add_raw({"role": "tool", "tool_call_id": tc_id, "content": content})

    async def _speak(self, text: str, reply_to: Optional[str] = None) -> None:
        await self.bus.publish(
            "speech.say",
            {"text": text, "say_id": str(uuid.uuid4()), "in_reply_to_utterance": reply_to},
        )

    async def _request_listen(self, reason: str, window_s: float = 12.0) -> None:
        await self.bus.publish(
            "dialog.listen",
            {"listen_id": str(uuid.uuid4()), "window_s": window_s, "reason": reason},
        )

    # ------------------------------------------------- session start

    async def _handle_session_start(self) -> None:
        """Greeting v0, or first-boot onboarding if we've never met the
        user. Triggered by brain.request(source=system, text=session_start)."""
        if not self.profile.exists() and not self.profile.onboarding_complete:
            self._onboarding_stage = "await_name"
            await self._speak(onboarding.INTRO)
            await self._request_listen("onboarding", 20.0)
            return
        await self._speak(self._greeting_text())

    def _greeting_text(self) -> str:
        """Time-of-day + name if known. Generic until onboarding is done
        (requirement 4). A fuller LLM-phrased greeting is fine later; v0
        keeps it deterministic and testable."""
        try:
            hour = time.localtime().tm_hour
        except (OSError, ValueError):
            hour = 12
        part = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
        name = self.profile.name
        return f"Good {part}, {name}. What can I do for you?" if name else f"Good {part}."

    # ------------------------------------------------- onboarding turns

    async def _handle_onboarding(self, text: str, utterance_id: Optional[str]) -> None:
        stage = self._onboarding_stage
        if stage and stage.startswith("followup:"):
            # A trickle answer: store it as a free-form fact, briefly
            # acknowledge, done. A non-answer ("nothing"/silence handled
            # upstream by the window closing) is simply not stored.
            fid = stage.split(":", 1)[1]
            self._onboarding_stage = None
            if _yes_no(text) is None and text.strip():
                self.profile.set_fact(fid, text.strip(), "preference", _now_iso(), "followup")
                self.profile.save()
                await self._speak("Noted. Thanks.", utterance_id)
            return
        if stage == "await_name":
            name = onboarding.extract_name(text) or await self._llm_extract_name(text)
            if not name:
                await self._speak(onboarding.ask_again(), utterance_id)
                await self._request_listen("onboarding", 20.0)
                return
            self._onboarding_name = name
            self._onboarding_stage = "confirm_pron"
            await self._speak(onboarding.confirm_pronunciation(name), utterance_id)
            await self._request_listen("onboarding", 12.0)
        elif stage == "confirm_pron":
            ans = _yes_no(text)
            if ans is True:
                now = _now_iso()
                self.profile.set_fact("name", self._onboarding_name, "name", now, "onboarding")
                self.profile.set_fact(
                    "pronunciation", self._onboarding_name, "pronunciation", now, "onboarding"
                )
                self.profile.onboarding_complete = True
                self.profile.save()
                self._onboarding_stage = None
                await self._speak(onboarding.welcome(self._onboarding_name), utterance_id)
            else:
                # got it wrong (or unclear) — ask for the name again
                self._onboarding_stage = "await_name"
                await self._speak(onboarding.ask_again(), utterance_id)
                await self._request_listen("onboarding", 20.0)

    async def _llm_extract_name(self, text: str) -> Optional[str]:
        """Fallback name extraction via the LLM when rules miss."""
        try:
            resp = await self._http.post(
                f"{self.cfg.llm_url}/v1/chat/completions",
                json={
                    "model": self.cfg.model_name,
                    "messages": [
                        {"role": "system", "content": "Extract only the person's name "
                         "from the message. Reply with the name alone, or NONE."},
                        {"role": "user", "content": text},
                    ],
                    "max_tokens": 12,
                    "temperature": 0.0,
                    "chat_template_kwargs": {"enable_thinking": False},
                },
            )
            resp.raise_for_status()
            out = (resp.json()["choices"][0]["message"]["content"] or "").strip()
            cand = out.split()[0] if out else ""
            if cand and cand.upper() != "NONE" and cand.isalpha():
                return cand.capitalize()
        except (httpx.HTTPError, KeyError, ValueError, IndexError):
            pass
        return None

    async def _handle_input(
        self,
        text: str,
        conversation_id: str,
        utterance_id: Optional[str],
        speak: bool,
        in_reply_to: dict,
    ) -> None:
        # Session-start trigger (greeting / onboarding).
        if conversation_id == "system" and text == "session_start":
            await self._handle_session_start()
            return
        # Mid-onboarding: answers route to the interview, not the LLM.
        if self._onboarding_stage is not None:
            await self._handle_onboarding(text, utterance_id)
            return
        # A name correction at any time updates the profile (a fact).
        if (corrected := onboarding.detect_name_correction(text)) and self.profile.name:
            now = _now_iso()
            self.profile.set_fact("name", corrected, "name", now, "correction")
            self.profile.set_fact("pronunciation", corrected, "pronunciation", now, "correction")
            self.profile.save()
            await self._speak(f"Got it — {corrected}. I'll remember that.", utterance_id)
            return

        conv = self.conversations.setdefault(conversation_id, Conversation(self.cfg))
        conv.add("user", text, time.monotonic())
        t0 = time.monotonic()
        rung, backend = self._rung()
        try:
            reply, finish = await self._tool_loop(conv, utterance_id)
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

        # Follow-up trickle (v0 heuristic): at most one pending question
        # per session, only via voice, only after a completed exchange —
        # never at greeting or first boot. (§05 pause detection is Phase 4.)
        if (
            speak
            and conversation_id == "voice"
            and not self._followup_asked_this_session
            and self.profile.onboarding_complete
            and self.profile.pending_questions
        ):
            self._followup_asked_this_session = True
            q = self.profile.pop_pending()
            self.profile.save()
            self._followup_id = q["id"]
            self._onboarding_stage = f"followup:{q['id']}"
            await self._speak(q["prompt"])
            await self._request_listen("followup", 15.0)

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
        if self._hallucinated_calls:
            metrics["hallucinated_tool_calls"] = float(self._hallucinated_calls)
        if metrics:
            body["metrics"] = metrics
        if notes:
            body["notes"] = notes
        await self.bus.publish("sys.health", body)

    def _on_action_result(self, body: dict) -> None:
        rid = body.get("request_id", "")
        if (fut := self._pending_results.get(rid)) and not fut.done():
            fut.set_result(body)

    async def _input_worker(self, inputs: asyncio.Queue) -> None:
        """Handles user turns one at a time, OFF the frame-reading loop —
        a turn awaiting an action.result must not stop the loop from
        reading that very result (deadlock otherwise)."""
        while True:
            args = await inputs.get()
            await self._handle_input(*args)

    async def run(self) -> None:
        await self.bus.subscribe(["audio.transcript", "brain.request", "action.result"])
        await self._health()
        inputs: asyncio.Queue = asyncio.Queue()
        worker = asyncio.create_task(self._input_worker(inputs))
        health_at = time.monotonic()
        try:
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
                    inputs.put_nowait(
                        (
                            strip_wake_prefix(body["text"]),
                            "voice",
                            body.get("utterance_id"),
                            True,
                            in_reply_to,
                        )
                    )
                elif topic == "brain.request":
                    inputs.put_nowait(
                        (
                            body["text"],
                            body.get("conversation_id", "default"),
                            body.get("utterance_id"),
                            body.get("speak", True),
                            in_reply_to,
                        )
                    )
                elif topic == "action.result":
                    self._on_action_result(body)
        finally:
            worker.cancel()

    async def close(self) -> None:
        await self._http.aclose()
