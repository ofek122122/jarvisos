"""jv-brain v0: conversation only (BRIEF-phase1 task 5 — do not
gold-plate). Consumes audio.transcript finals + brain.request, calls the
llama-server OpenAI endpoint, publishes brain.response and (for spoken
inputs) speech.say. NO tools, NO memory writes — Phases 2 and 4.

Barge-in: `audio.wake` while a SPOKEN answer is streaming cancels that
answer (see `_barge_in`). jv-voice stops playing what already reached it,
but only the brain can stop generating — and a reply nobody is listening
to holds the GPU, keeps publishing sentences, and would otherwise be
recorded as if it had been delivered whole."""

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
from .launcher import UNREADABLE, RungRecord, read_rung_file
from .profile import Profile
from .tools import load_tools, openai_tool_defs

HEALTH_PERIOD_S = 5.0

# Hard rules (BRIEF-phase2 §3)
MAX_TOOL_CALLS_PER_TURN = 5
# Tool round-trip budget: registry timeout + the 15s confirm window +
# margin. A stuck act must not wedge the conversation forever.
ACTION_RESULT_TIMEOUT_S = 60.0

# Internal finish marker for a turn the user barged in on. Deliberately
# NOT a bus word: brain.response's `finish_reason` enum is frozen at
# stop|length|error (schemas/brain.response.json), and "stop" would claim
# the answer ran to its end. So an interrupted turn publishes no
# brain.response at all, is counted in sys.health's free-form metrics, and
# proposal R3 in docs/optimization-backlog.md asks a human for the word.
INTERRUPTED = "interrupted"

# What the conversation keeps for an interrupted turn. The text is what
# jv-brain SENT — jv-voice drops the tail of the group it never played, so
# this is the upper bound of what the user heard, and the marker is what
# stops the model from treating a half-answer as a delivered one.
_INTERRUPTED_NOTE = "[interrupted here by the user]"
_INTERRUPTED_SILENT = "[interrupted by the user before any of this was said]"


def interrupted_record(said: str) -> str:
    said = said.strip()
    return f"{said} {_INTERRUPTED_NOTE}" if said else _INTERRUPTED_SILENT


def _is_number(value: object) -> bool:
    """A JSON number, and not a bool. `False < 0.6` is true in Python, so a
    bool reaching the comparison below would make `score: false` look like
    a wake jv-ears scored below threshold — a refusal, off a field we
    cannot read at all."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def wake_contradicts_itself(body: dict) -> bool:
    """A wake frame we must NOT act on, because it disagrees with itself:
    it reports a score below the threshold it says was configured when it
    fired (schemas/audio.wake.json carries both).

    The rule is deliberately narrow — act on a wake unless the frame
    refutes itself. The frame's EXISTENCE is jv-ears asserting a detection;
    `score`/`threshold` are there so tuning is auditable. An unreadable
    score is then unverifiable, not contradictory, so it is still acted on
    (as jv-voice acts on every wake) — and read through `_is_number` so
    the comparison can never raise on the frame-reading loop."""
    score, threshold = body.get("score"), body.get("threshold")
    return _is_number(score) and _is_number(threshold) and score < threshold


# "Hey Jarvis," / "hey jarvis." / "Jarvis," etc. at the start of an
# utterance — ears publishes what was said; stripping the address is ours.
_WAKE_PREFIX = re.compile(r"^\s*(hey|okay|ok)?[\s,]*jarvis[\s,.!?]*", re.IGNORECASE)
_THINK_BLOCK = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


def strip_wake_prefix(text: str) -> str:
    stripped = _WAKE_PREFIX.sub("", text, count=1).strip()
    return stripped if stripped else text.strip()


# A sentence closes on . ! ? or … (with optional closing quote/bracket)
# followed by whitespace, or on a newline.
_SENTENCE_BREAK = re.compile(r'(.*?[.!?…][")\]]?)(\s)|(.*?)(\n)', re.DOTALL)


class SentenceChunker:
    """Feed it streamed LLM text; it hands back complete sentences the
    moment each one closes, so jv-voice can start speaking sentence 1
    while the LLM still writes sentence 2. `flush()` returns the trailing
    partial at end of stream. `min_chars` holds back tiny fragments so
    piper never voices a lone 'K.'."""

    def __init__(self, min_chars: int = 0) -> None:
        self.min_chars = min_chars
        self._buf = ""
        self._pending = ""  # a too-small fragment, held to lead the next sentence

    def push(self, text: str) -> list[str]:
        self._buf += text
        out: list[str] = []
        while True:
            m = _SENTENCE_BREAK.match(self._buf)
            if not m:
                break
            sentence = (m.group(1) or m.group(3) or "").strip()
            self._buf = self._buf[m.end():]
            if not sentence:
                continue
            if self._pending:
                sentence = f"{self._pending} {sentence}"
                self._pending = ""
            if len(sentence) < self.min_chars:
                self._pending = sentence  # too small to speak alone; lead-in
                continue
            out.append(sentence)
        return out

    def flush(self) -> Optional[str]:
        rest = " ".join(p for p in (self._pending, self._buf.strip()) if p).strip()
        self._pending = ""
        self._buf = ""
        return rest or None


_YES = {"yes", "yeah", "yep", "yup", "correct", "right", "that's right", "perfect"}
_NO = {"no", "nope", "wrong", "not quite", "not right", "incorrect"}


class TurnTiming:
    """Where inside one turn the MODEL's share of it began.

    `jv tap --latency` splits a voice turn at the boundaries jv-ears
    publishes, and its last span — `think` — runs from the final transcript
    to the first `speech.say`. That span is the LLM's prefill and
    generation AND a bus hop each way AND whatever the input worker was
    doing when the transcript landed. PHASE1-STATUS wants to optimise the
    LLM's part of it, and one number over all of it cannot say which part a
    change moved.

    Only jv-brain knows where inside `think` the completion request went
    out, so jv-brain states it: `llm_first_say_ms` on its own `sys.health`
    `metrics`, which is free-form and service-local by schema, so this
    costs no schema change (invariant 2).

    The one thing this type is careful about: a turn that ran TOOLS spends
    real time in jv-act — including a confirm window — between its first
    completion and the words the user hears. That time is inside `think`
    and it is not the model's, so such a turn publishes NO gauge at all. A
    `model` number with a tool round-trip inside it is exactly how a number
    stops meaning its label, and the tap's `n` column is what says how many
    turns the number it does print stands on."""

    __slots__ = ("streams", "_request")

    def __init__(self) -> None:
        self.streams = 0
        self._request = 0.0

    def request(self, now: float) -> None:
        """A completion request is going out to llama-server, now."""
        self.streams += 1
        self._request = now

    def model_ms(self, now: float) -> Optional[float]:
        """Milliseconds from this turn's completion request to `now`, or
        None when the turn never reached the LLM, or reached it more than
        once (see the class docstring). The `streams` count is what makes
        `_request` unambiguous: it is only ever read for a turn that issued
        exactly one request, so there is no earlier one to have lost."""
        if self.streams != 1:
            return None
        return (now - self._request) * 1e3


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
        if len(self.messages) > self.cfg.max_turns * 2 or self._chars() > self.cfg.max_context_chars:
            self._trim()

    def repair_open_tool_calls(self, content: str) -> int:
        """Answer every tool_call that never got a result, and return how
        many. A turn cancelled mid-tool (barge-in) leaves an assistant
        tool_calls message with a missing result; a chat template wants one
        result per call, so the next request would be malformed and the
        conversation poisoned for the rest of the session — by an
        interruption. The dispatched action itself is NOT recalled: jv-act
        already has it, and only jv-act's audit log knows how it ended."""
        answered = {
            m.get("tool_call_id") for m in self.messages if m.get("role") == "tool"
        }
        open_ids = [
            tc.get("id")
            for m in self.messages
            if m.get("role") == "assistant"
            for tc in (m.get("tool_calls") or [])
            if tc.get("id") and tc.get("id") not in answered
        ]
        for tc_id in open_ids:
            self.add_raw({"role": "tool", "tool_call_id": tc_id, "content": content})
        return len(open_ids)

    def _chars(self) -> int:
        return sum(len(m.get("content") or "") for m in self.messages)

    def _trim(self) -> None:
        """Batched trim, well past the cap. The llama-server prompt cache
        only reuses an unchanged PREFIX; dropping one message per add
        shifted the prefix every turn and forced a full-history re-prefill
        each exchange (measured 10 s / 1400 tokens on 2026-09-15)."""
        target_msgs = max(2, int(self.cfg.max_turns * 2 * 0.6))
        while len(self.messages) > 1 and (
            len(self.messages) > target_msgs
            or self._chars() > self.cfg.trim_target_chars
        ):
            self.messages.popleft()
        # never open the context mid-exchange (assistant/tool first)
        while len(self.messages) > 1 and self.messages[0].get("role") != "user":
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
        # The model's share of `think`, for the turn most recently spoken,
        # and the count of turns that have had one. The count is how a
        # reader tells a FRESH gauge from the same number re-stated on the
        # next periodic heartbeat (see TurnTiming, and cli::brain_first_say
        # in the jv CLI, which is the reader this exists for).
        self._first_say_ms: Optional[float] = None
        self._first_says = 0
        # barge-in: the spoken turn in flight, and the one task a wake has
        # asked to cancel (so a shutdown cancellation is never mistaken for
        # an interruption).
        self._inflight: Optional[asyncio.Task] = None
        self._barged: Optional[asyncio.Task] = None
        self._barge_ins = 0
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

    def _rung(self) -> RungRecord:
        """What jv-llm-launch recorded: the rung, the backend, and how
        sure it was of the VRAM number it picked them with. That process
        execs into llama-server and cannot reach the bus, so this file is
        the whole of what it got to say."""
        return read_rung_file(self.cfg.rung_file)

    def _payload(self, messages: list[dict], max_tokens: Optional[int] = None) -> dict:
        payload = {
            "model": self.cfg.model_name,
            "messages": messages,
            "temperature": self.cfg.temperature,
            "max_tokens": self.cfg.max_tokens if max_tokens is None else max_tokens,
            # Qwen3: keep the thinking mode off for voice latency.
            "chat_template_kwargs": {"enable_thinking": False},
            # Prompt-cache contract with llama-server (--parallel 1 in
            # jv-llm-launch): one pinned slot, explicit prefix reuse.
            "cache_prompt": True,
            "id_slot": 0,
        }
        if self.tool_defs:
            payload["tools"] = self.tool_defs
            payload["tool_choice"] = "auto"
        return payload

    async def _stream_turn(
        self, conv: Conversation, on_sentence, timing: Optional["TurnTiming"] = None
    ) -> tuple[str, list, str]:
        """Stream one completion. Assemble content + any tool_calls from the
        SSE deltas; call `await on_sentence(str)` for each sentence as it
        closes (so piper starts on sentence 1 while the LLM writes the
        rest). Returns (full_text, tool_calls, finish_reason). Sentences
        are spoken ONLY for a plain-text answer — a tool-call turn carries
        no content, so nothing is voiced before the tools run."""
        payload = self._payload(
            [{"role": "system", "content": self.system_prompt}] + list(conv.messages)
        )
        payload["stream"] = True
        chunker = SentenceChunker(min_chars=self.cfg.tts_min_sentence_chars)
        parts: list[str] = []
        tool_frags: dict[int, dict] = {}
        finish = "stop"
        # The model's clock starts here and not a line earlier: assembling
        # the system prompt and trimming the conversation are jv-brain's
        # work, and `think` is being divided into what the LLM did and what
        # this service did around it.
        if timing is not None:
            timing.request(time.monotonic())
        async with self._http.stream(
            "POST", f"{self.cfg.llm_url}/v1/chat/completions", json=payload
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                choice = json.loads(data)["choices"][0]
                if choice.get("finish_reason"):
                    finish = choice["finish_reason"]
                delta = choice.get("delta") or {}
                for tc in delta.get("tool_calls") or []:
                    slot = tool_frags.setdefault(
                        tc.get("index", 0), {"id": "", "name": "", "args": ""}
                    )
                    if tc.get("id"):
                        slot["id"] = tc["id"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        slot["name"] = fn["name"]
                    if fn.get("arguments"):
                        slot["args"] += fn["arguments"]
                content = delta.get("content")
                if content:
                    parts.append(content)
                    if on_sentence and not tool_frags:
                        for sentence in chunker.push(content):
                            await on_sentence(sentence)
        if on_sentence and not tool_frags:
            tail = chunker.flush()
            if tail:
                await on_sentence(tail)
        tool_calls = [
            {"id": v["id"], "type": "function",
             "function": {"name": v["name"], "arguments": v["args"]}}
            for _, v in sorted(tool_frags.items())
        ]
        text = _THINK_BLOCK.sub("", "".join(parts)).strip()
        reason = "length" if finish == "length" else ("tool_calls" if tool_calls else "stop")
        return text, tool_calls, reason

    WARMUP_TRIES = 24
    WARMUP_RETRY_S = 5.0

    async def _warmup(self) -> None:
        """Pay the cold system-prompt prefill at startup (10.5 s for 1415
        tokens, measured 2026-09-16), not on the user's first exchange.
        The payload must be byte-identical to a real request's prefix —
        same system prompt, same tool defs — or the rendered prompt won't
        match and the cache stays cold. Retries while llama-server is
        still loading weights; gives up quietly (the first exchange then
        just pays the prefill itself)."""
        payload = self._payload(
            [{"role": "system", "content": self.system_prompt}], max_tokens=1
        )
        for _ in range(self.WARMUP_TRIES):
            try:
                resp = await self._http.post(
                    f"{self.cfg.llm_url}/v1/chat/completions", json=payload
                )
                resp.raise_for_status()
                return
            except httpx.HTTPError:
                await asyncio.sleep(self.WARMUP_RETRY_S)

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

    async def _respond(
        self, conv: Conversation, utterance_id: Optional[str], speak: bool
    ) -> tuple[str, str]:
        """Streaming v1 loop: stream a completion (speaking each sentence as
        it closes, for a plain-text answer) -> if it wanted tools, execute
        them and loop; the final text answer then streams+speaks. Hard
        rules unchanged (max 5 calls/turn, hallucinated names rejected
        without ever reaching jv-act). Returns (full_text, finish).

        A barge-in cancels this coroutine wherever it is — mid-stream, or
        waiting on an action.result. It returns (what was said so far,
        INTERRUPTED) rather than propagating, so the caller can record the
        turn; a cancellation this service did not ask for (shutdown) still
        propagates untouched."""
        reply_group = str(uuid.uuid4())
        said: list[str] = []
        timing = TurnTiming()

        async def on_sentence(sentence: str) -> None:
            if not speak:
                return
            said.append(sentence)
            await self._say_chunk(sentence, utterance_id, reply_group)
            if len(said) == 1:
                await self._state_model_share(timing)

        try:
            return await self._respond_loop(conv, utterance_id, on_sentence, timing)
        except asyncio.CancelledError:
            if asyncio.current_task() is not self._barged:
                raise
            return " ".join(said), INTERRUPTED

    async def _respond_loop(
        self,
        conv: Conversation,
        utterance_id: Optional[str],
        on_sentence,
        timing: Optional["TurnTiming"] = None,
    ) -> tuple[str, str]:
        """The tool loop itself, split out only so `_respond` can wrap it in
        one try/except without indenting all of it."""
        calls_used = 0
        while True:
            text, tool_calls, finish = await self._stream_turn(conv, on_sentence, timing)
            if not tool_calls:
                return text, finish
            conv.add_raw(
                {"role": "assistant", "content": text or None, "tool_calls": tool_calls}
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

    async def _stream_reply(
        self, conv: Conversation, utterance_id: Optional[str], speak: bool
    ) -> tuple[str, str]:
        """Run one turn, cancellably. The turn is a CHILD task so a wake can
        end it without touching the worker that must go on to handle the
        utterance that wake belongs to.

        Only a SPOKEN turn is cancellable. A wake says the user is talking
        to Jarvis; it does not say the CLI or the HUD stopped wanting the
        answer it asked for, and a silent reply is not being spoken over."""
        if not speak:
            return await self._respond(conv, utterance_id, speak)
        task = asyncio.create_task(self._respond(conv, utterance_id, speak))
        self._inflight = task
        try:
            return await task
        finally:
            self._inflight = None
            self._barged = None

    def _barge_in(self) -> None:
        """End the answer in flight, if there is one. A wake with nothing
        streaming is not an event here — jv-ears' wake detection runs
        continuously, and the utterance that follows arrives as a transcript
        of its own. A turn that has just finished can still be in
        `_inflight` until its awaiter resumes and clears it; cancelling a
        finished task is a no-op, and it is the INTERRUPTED return that
        counts a barge-in, so that window needs no guard of its own."""
        if (task := self._inflight) is not None:
            self._barged = task
            task.cancel()

    def _on_wake(self, body: dict) -> None:
        """audio.wake — barge-in, unless the frame refutes itself: losing an
        answer to a wake jv-ears itself scored below threshold would be
        worse than the bug this fixes."""
        if not wake_contradicts_itself(body):
            self._barge_in()

    async def _speak(self, text: str, reply_to: Optional[str] = None) -> None:
        await self.bus.publish(
            "speech.say",
            {"text": text, "say_id": str(uuid.uuid4()), "in_reply_to_utterance": reply_to},
        )

    async def _say_chunk(
        self, text: str, utterance_id: Optional[str], reply_group: str
    ) -> None:
        """One sentence of a streamed reply — carries reply_group so
        jv-voice keeps the turn's sentences together (barge-in drops them
        as a unit)."""
        await self.bus.publish(
            "speech.say",
            {
                "text": text,
                "say_id": str(uuid.uuid4()),
                "in_reply_to_utterance": utterance_id,
                "reply_group": reply_group,
            },
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
        rec = self._rung()
        try:
            # streams the reply, speaking each sentence as it closes
            reply, finish = await self._stream_reply(conv, utterance_id, speak)
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
        if finish == INTERRUPTED:
            # No brain.response: `finish_reason` has no word for this (see
            # INTERRUPTED). The turn is still recorded — dropping it would
            # leave two user messages in a row and let the model believe the
            # half-answer it gave was the whole one.
            self._barge_ins += 1
            conv.repair_open_tool_calls(json.dumps({"ok": False, "error": INTERRUPTED}))
            conv.add("assistant", interrupted_record(reply), time.monotonic())
            return
        conv.add("assistant", reply, time.monotonic())

        body = {
            "text": reply,
            "finish_reason": finish,
            "conversation_id": conversation_id,
            "in_reply_to": in_reply_to,
            "model": self.cfg.model_name,
            "backend": rec.backend,
            "latency_ms": (time.monotonic() - t0) * 1e3,
        }
        if utterance_id:
            body["utterance_id"] = utterance_id
        await self.bus.publish("brain.response", body)
        # The reply was already spoken sentence-by-sentence during _respond
        # (streaming); brain.response carries the full text for the record.

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

    async def _state_model_share(self, timing: TurnTiming) -> None:
        """The first word of a turn has just gone out. If the turn is one
        whose `think` can honestly be divided (TurnTiming), record the
        model's share of it and heartbeat IMMEDIATELY.

        The immediacy is the whole binding: `sys.health` carries no
        utterance_id and adding one is a frozen-schema change, so the only
        thing that ties this number to the turn it describes is that the
        gauge frame and the `speech.say` frame leave jv-brain on the SAME
        connection, in that order. A reader that sees a gauge whose count
        has risen since the word it is holding knows which turn it belongs
        to without either frame naming it."""
        if (ms := timing.model_ms(time.monotonic())) is None:
            return
        self._first_say_ms = ms
        self._first_says += 1
        await self._health()

    async def _health(self, state: str = "ok", notes: Optional[str] = None) -> None:
        rec = self._rung()
        if rec.vram.source == UNREADABLE:
            # The ladder was walked blind: nvidia-smi was there and would
            # not answer, so rung 4 was the floor holding, not a choice.
            # "no card" reads identically in every other field, which is
            # why it must not read identically here — and why this is
            # degraded (invariant 6's scheduler is flying) while a machine
            # that genuinely has no GPU is simply a machine with no GPU.
            blind = (
                f"llm rung chosen blind — VRAM unreadable at launch"
                f"{f': {rec.vram.detail}' if rec.vram.detail else ''}"
            )
            notes = blind if not notes else f"{notes}; {blind}"
            if state == "ok":
                state = "degraded"
        body: dict = {
            "service": "jv-brain",
            "state": state,
            "uptime_s": time.monotonic() - self._started,
            "period_s": HEALTH_PERIOD_S,
        }
        metrics: dict = {}
        if rec.index is not None:
            metrics["llm_rung"] = float(rec.index)  # Ofek: rung visible in jv health
            metrics["llm_gpu"] = 1.0 if rec.backend == "gpu" else 0.0
        if self._hallucinated_calls:
            metrics["hallucinated_tool_calls"] = float(self._hallucinated_calls)
        if self._barge_ins:
            metrics["barge_ins"] = float(self._barge_ins)
        if self._first_say_ms is not None:
            # `jv tap --latency` divides `think` with these two (cli.rs).
            metrics["llm_first_say_ms"] = self._first_say_ms
            metrics["llm_first_says"] = float(self._first_says)
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
        await self.bus.subscribe(
            ["audio.transcript", "brain.request", "action.result", "audio.wake"]
        )
        await self._health()
        warmup = asyncio.create_task(self._warmup())
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
                elif topic == "audio.wake":
                    # Handled HERE, not in the worker: the worker is busy
                    # with the very turn this has to cancel.
                    self._on_wake(body)
        finally:
            warmup.cancel()
            worker.cancel()

    async def close(self) -> None:
        await self._http.aclose()
