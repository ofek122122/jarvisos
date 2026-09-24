"""jv-brain service tests: real jarvisd + a stub OpenAI-compatible LLM
server (no GPU, no model — per the brief, CI never loads weights)."""

import asyncio
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from jarvis_bus import BusClient
from jv_brain.config import BrainConfig
from jv_brain.service import HEALTH_PERIOD_S, BrainService, strip_wake_prefix
from jv_brain.tools import load_tools

REPO = Path(__file__).resolve().parents[3]


def jarvisd_bin() -> Path:
    if env := os.environ.get("JARVISD_BIN"):
        return Path(env)
    exe = "jarvisd.exe" if sys.platform == "win32" else "jarvisd"
    for profile in ("debug", "release"):
        p = REPO / "services" / "jarvisd" / "target" / profile / exe
        if p.exists():
            return p
    pytest.skip("jarvisd binary not built")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def sse(chunks: list[dict]) -> bytes:
    """OpenAI streaming wire format: one `data: {json}` per line, [DONE] last."""
    body = b""
    for ch in chunks:
        body += b"data: " + json.dumps(ch).encode() + b"\r\n\r\n"
    body += b"data: [DONE]\r\n\r\n"
    return body


class StubLLM:
    """Minimal OpenAI-compatible /v1/chat/completions responder. Supports
    both non-streaming and stream=true. Reply text is
    'You said: <last user message>'; every request is recorded."""

    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.server: asyncio.AbstractServer | None = None
        self.port = 0

    async def start(self) -> None:
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    def _reply_for(self, payload: dict) -> str:
        users = [m for m in payload["messages"] if m["role"] == "user"]
        return f"You said: {users[-1]['content']}" if users else ""

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            head = await reader.readuntil(b"\r\n\r\n")
            length = 0
            for line in head.decode("latin1").split("\r\n"):
                if line.lower().startswith("content-length:"):
                    length = int(line.split(":", 1)[1])
            payload = json.loads(await reader.readexactly(length))
            self.requests.append(payload)
            text = self._reply_for(payload)
            if payload.get("stream"):
                # deltas word-by-word so a multi-sentence reply arrives in pieces
                deltas = [{"choices": [{"delta": {"role": "assistant"}}]}]
                for tok in _tokenize(text):
                    deltas.append({"choices": [{"delta": {"content": tok}}]})
                deltas.append({"choices": [{"delta": {}, "finish_reason": "stop"}]})
                body = sse(deltas)
                writer.write(
                    b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
                    + f"Content-Length: {len(body)}\r\n\r\n".encode()
                    + body
                )
            else:
                body = json.dumps(
                    {"choices": [{"message": {"role": "assistant", "content": text},
                                  "finish_reason": "stop"}]}
                ).encode()
                writer.write(
                    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                    + f"Content-Length: {len(body)}\r\n\r\n".encode()
                    + body
                )
            await writer.drain()
        finally:
            writer.close()


def _tokenize(text: str) -> list[str]:
    """Split into whitespace-preserving tokens so reassembly is exact."""
    import re as _re

    return _re.findall(r"\S+\s*", text) or ([text] if text else [])


@pytest.fixture
async def stack(tmp_path, request):
    """jarvisd + stub LLM + BrainService, wired together.

    Indirectly parametrizable with a heartbeat period, for the tests that
    are about WHEN jv-brain beats rather than what it says."""
    addr = f"127.0.0.1:{free_port()}"
    proc = subprocess.Popen(
        [str(jarvisd_bin()), "--bus", addr],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(100):
        try:
            _, w = await asyncio.open_connection(*addr.rsplit(":", 1))
            w.close()
            break
        except OSError:
            await asyncio.sleep(0.05)

    stub = StubLLM()
    await stub.start()
    rung_file = tmp_path / "llm-rung"
    rung_file.write_text("rung=1\nlabel=KV q8\nbackend=gpu\nfree_vram_mb=5800\n")
    cfg = BrainConfig(
        llm_url=f"http://127.0.0.1:{stub.port}",
        rung_file=rung_file,
        personality_dir=REPO / "personality",
    )
    svc_bus = await BusClient.connect(addr, src="jv-brain")
    svc = BrainService(
        svc_bus, cfg, health_period_s=getattr(request, "param", HEALTH_PERIOD_S)
    )
    task = asyncio.create_task(svc.run())
    await asyncio.sleep(0.2)

    watcher = await BusClient.connect(addr, src="t-watch")
    yield addr, stub, watcher
    task.cancel()
    await svc.close()
    await svc_bus.close()
    await watcher.close()
    stub.server.close()
    proc.kill()
    proc.wait(timeout=10)


def user_requests(stub: StubLLM) -> list[dict]:
    """LLM requests that carry a user turn — i.e. not the startup warmup."""
    return [
        r for r in stub.requests if any(m["role"] == "user" for m in r["messages"])
    ]


async def next_topic(client, topic, timeout=10.0):
    async def inner():
        while True:
            frame = await client.next_frame()
            assert frame is not None
            if frame["topic"] == topic:
                return frame
    return await asyncio.wait_for(inner(), timeout)


async def test_voice_final_gets_response_and_speech(stack):
    addr, stub, watcher = stack
    await watcher.subscribe(["brain.response", "speech.say"])
    await asyncio.sleep(0.1)

    await watcher.publish(
        "audio.transcript",
        {
            "kind": "final",
            "utterance_id": "utt-1",
            "text": "Hey Jarvis, what time is it?",
            "lang": "en",
        },
        conf=0.9,
    )
    # streaming: speech.say now arrives BEFORE brain.response (piper starts
    # while the reply is still being finalized). Single-sentence reply here.
    say = await next_topic(watcher, "speech.say")
    assert say["body"]["in_reply_to_utterance"] == "utt-1"  # the E2E thread
    assert say["body"]["text"] == "You said: what time is it?"

    resp = await next_topic(watcher, "brain.response")
    assert resp["body"]["text"] == "You said: what time is it?"  # wake prefix stripped
    assert resp["body"]["utterance_id"] == "utt-1"
    assert resp["body"]["backend"] == "gpu"
    assert resp["body"]["in_reply_to"]["src"] == "t-watch"

    # system prompt reached the LLM (requests[0] is the startup warmup)
    req = user_requests(stub)[0]
    assert req["messages"][0]["role"] == "system"
    assert "Jarvis" in req["messages"][0]["content"]
    assert req["chat_template_kwargs"] == {"enable_thinking": False}
    # prompt-cache contract with llama-server: explicit reuse, pinned slot
    # (2026-09-15: slot roulette forced a full re-prefill nearly every turn)
    assert req["cache_prompt"] is True
    assert req["id_slot"] == 0


async def test_warmup_prefills_system_prompt_at_startup(stack):
    """The 10.5 s cold prefill (1415 tokens, measured 2026-09-16) must be
    paid at service start, not on the user's first exchange: on startup
    the brain sends one system-prompt-only request into the pinned slot."""
    addr, stub, watcher = stack
    # no user input at all — the fixture's startup settle is enough
    assert len(stub.requests) == 1
    warm = stub.requests[0]
    assert [m["role"] for m in warm["messages"]] == ["system"]
    assert warm["max_tokens"] == 1
    assert warm["cache_prompt"] is True and warm["id_slot"] == 0
    # identical prefix contract: warmup must carry the same tool defs
    # the real requests carry, or the rendered prompt won't match
    assert ("tools" in warm) == bool(load_tools())


async def test_reply_is_spoken_sentence_by_sentence(stack):
    """The latency win: a multi-sentence reply must produce one speech.say
    PER sentence (so piper starts on sentence 1 while the LLM finishes),
    all threaded to the utterance, and one brain.response with the full
    text. Stub reply 'You said: <text>' — feed a 2-sentence user line."""
    addr, stub, watcher = stack
    await watcher.subscribe(["brain.response", "speech.say"])
    await asyncio.sleep(0.1)

    await watcher.publish(
        "audio.transcript",
        {"kind": "final", "utterance_id": "utt-s",
         "text": "First thing. Second thing.", "lang": "en"},
        conf=0.9,
    )
    # reply echoes: "You said: First thing. Second thing." -> 2 sentences
    say1 = await next_topic(watcher, "speech.say")
    say2 = await next_topic(watcher, "speech.say")
    assert say1["body"]["text"] == "You said: First thing."
    assert say2["body"]["text"] == "Second thing."
    assert say1["body"]["in_reply_to_utterance"] == "utt-s"
    assert say2["body"]["in_reply_to_utterance"] == "utt-s"
    # distinct say_ids, shared chunk group so voice keeps them in one turn
    assert say1["body"]["say_id"] != say2["body"]["say_id"]
    assert say1["body"]["reply_group"] == say2["body"]["reply_group"]

    resp = await next_topic(watcher, "brain.response")
    assert resp["body"]["text"] == "You said: First thing. Second thing."
    # streaming was actually requested
    assert user_requests(stub)[0]["stream"] is True


async def test_partials_are_ignored(stack):
    addr, stub, watcher = stack
    await watcher.subscribe(["brain.response"])
    await asyncio.sleep(0.1)
    await watcher.publish(
        "audio.transcript",
        {"kind": "partial", "utterance_id": "u", "text": "Hey Jarvis", "lang": "en"},
        conf=0.5,
    )
    with pytest.raises(asyncio.TimeoutError):
        await next_topic(watcher, "brain.response", timeout=1.0)
    assert user_requests(stub) == []


async def test_cli_request_silent_and_context_grows(stack):
    addr, stub, watcher = stack
    await watcher.subscribe(["brain.response", "speech.say"])
    await asyncio.sleep(0.1)

    for i, text in enumerate(["first message", "second message"]):
        await watcher.publish(
            "brain.request",
            {"text": text, "source": "cli", "conversation_id": "t", "speak": False},
        )
        await next_topic(watcher, "brain.response")

    # rolling context: second request carries the first exchange
    msgs = user_requests(stub)[1]["messages"]
    roles = [m["role"] for m in msgs]
    assert roles == ["system", "user", "assistant", "user"]
    assert msgs[1]["content"] == "first message"

    # speak=False -> no speech.say ever
    with pytest.raises(asyncio.TimeoutError):
        await next_topic(watcher, "speech.say", timeout=1.0)


def test_strip_wake_prefix():
    assert strip_wake_prefix("Hey Jarvis, what time is it?") == "what time is it?"
    assert strip_wake_prefix("hey jarvis. turn it down") == "turn it down"
    assert strip_wake_prefix("Jarvis, hello") == "hello"
    assert strip_wake_prefix("What about jarvis?") == "What about jarvis?"
    # An utterance that is ONLY the wake word survives as itself.
    assert strip_wake_prefix("Hey Jarvis.") == "Hey Jarvis."


# --------------------------------------------- the model's share of `think`

def first_say_gauge(frame) -> tuple[float, float] | None:
    """(count, ms) off one jv-brain sys.health frame, or None."""
    m = (frame["body"].get("metrics") or {}) if frame["topic"] == "sys.health" else {}
    if "llm_first_say_ms" not in m:
        return None
    return m["llm_first_says"], m["llm_first_say_ms"]


async def test_brain_states_the_models_share_of_think(stack):
    """`jv tap --latency` can see the final transcript and the first
    `speech.say`; it cannot see where between them the completion request
    went out. jv-brain states that on its own heartbeat — and publishes one
    IMMEDIATELY after the first word, on the same connection the word went
    out on, so the frame order binds the gauge to the turn (the tap has no
    utterance_id on sys.health to bind it with)."""
    addr, stub, watcher = stack
    await watcher.subscribe(["speech.say", "sys.health"])
    await asyncio.sleep(0.1)

    # A reply of SEVERAL sentences: the gauge is time-to-FIRST-word, so the
    # later sentences must not each restate it as a new turn.
    await watcher.publish(
        "audio.transcript",
        {
            "kind": "final",
            "utterance_id": "utt-g",
            "text": "Hey Jarvis, one. Two. Three.",
            "lang": "en",
        },
        conf=0.9,
    )
    say = await next_topic(watcher, "speech.say")
    assert say["body"]["in_reply_to_utterance"] == "utt-g"

    # read IN ORDER from here: the gauge frame must follow the FIRST word,
    # and every later frame must re-state the same turn rather than count a
    # new one. (This is the whole binding: a reader tells a fresh gauge from
    # a re-stated one by the count, and nothing else.)
    says = 1
    gauges: list[tuple[float, float]] = []

    async def drain():
        nonlocal says
        while True:
            frame = await watcher.next_frame()
            assert frame is not None
            if frame["topic"] == "speech.say":
                says += 1
            if (g := first_say_gauge(frame)) is not None:
                gauges.append(g)

    try:
        await asyncio.wait_for(drain(), 1.5)
    except asyncio.TimeoutError:
        pass
    assert says >= 3, f"a multi-sentence reply should be several says, got {says}"
    assert gauges, "no sys.health carried llm_first_say_ms after the first word"
    count, ms = gauges[0]
    assert count == 1.0, "the first turn of this process is turn 1"
    assert 0.0 <= ms < 5_000.0
    assert all(c == 1.0 for c, _ in gauges), gauges


async def test_the_turn_counter_rises_so_a_second_turn_is_not_read_as_stale(stack):
    """The counter beside the gauge is the whole binding: a reader applies a
    gauge to the turn it just saw only when the count has RISEN since the
    last one. A counter that stayed at 1 would leave every turn after the
    first looking like a re-statement, and `jv tap --latency` would quietly
    stop dividing `think` after one turn."""
    addr, stub, watcher = stack
    await watcher.subscribe(["speech.say", "sys.health"])
    await asyncio.sleep(0.1)

    counts: list[float] = []
    for n in (1, 2, 3):
        await watcher.publish(
            "audio.transcript",
            {"kind": "final", "utterance_id": f"utt-{n}", "text": f"Hey Jarvis, {n}",
             "lang": "en"},
            conf=0.9,
        )

        async def until_gauge():
            while True:
                frame = await watcher.next_frame()
                assert frame is not None
                if (g := first_say_gauge(frame)) is not None and g[0] not in counts:
                    return g

        count, ms = await asyncio.wait_for(until_gauge(), 10.0)
        counts.append(count)
        assert 0.0 <= ms < 5_000.0
    assert counts == [1.0, 2.0, 3.0], counts


async def test_a_silent_turn_publishes_no_first_say_gauge(stack):
    """The gauge ends at a `speech.say`. A brain.request answered silently
    never publishes one, so there is nothing to time and no number to
    state — not a zero."""
    addr, stub, watcher = stack
    await watcher.subscribe(["brain.response", "sys.health"])
    await asyncio.sleep(0.1)

    await watcher.publish(
        "brain.request",
        {"text": "what time is it", "conversation_id": "cli", "speak": False},
    )
    # collect WHILE the turn runs: a gauge is published mid-turn, right
    # after the word it measures, so waiting for brain.response first would
    # throw away the only frame that could fail this.
    seen: list[tuple[float, float]] = []

    async def drain_until_done():
        while True:
            frame = await watcher.next_frame()
            assert frame is not None
            if (g := first_say_gauge(frame)) is not None:
                seen.append(g)
            if frame["topic"] == "brain.response":
                return frame

    done = await asyncio.wait_for(drain_until_done(), 10.0)
    assert done["body"]["text"] == "You said: what time is it"
    assert seen == []


# --------------------------------------- the period an off-schedule beat owns


async def next_health(watcher, timeout=10.0, gauge=False):
    """The next sys.health frame, and the moment it arrived. With
    `gauge=True`, the next one carrying `llm_first_say_ms` — i.e. the
    off-schedule beat a spoken turn publishes."""

    async def inner():
        while True:
            frame = await watcher.next_frame()
            assert frame is not None
            if frame["topic"] != "sys.health":
                continue
            if not gauge or first_say_gauge(frame) is not None:
                return frame, asyncio.get_running_loop().time()

    return await asyncio.wait_for(inner(), timeout)


@pytest.mark.parametrize("stack", [1.6], indirect=True)
async def test_the_first_say_beat_owns_the_period_it_lands_in(stack):
    """jv-brain publishes a heartbeat the instant the first word of a turn
    goes out, and one the instant the LLM errors — both right, and both
    used to leave the period timer alone. Two costs. The `degraded` a dead
    llama-server reports was erased by the next periodic `ok` after
    whatever was left of the period it interrupted, which near the
    boundary is nothing: `bus.latest()` keeps one frame per publisher, so
    the HUD and `jv health --check` read the erasure and never the report.
    And on an ordinary busy machine the gauge beat ADDED a frame per turn
    to a topic meant to be quiet (invariant 5), instead of being the beat.

    The off-schedule beat is this period's beat now. Asserted as a gap
    rather than a silence, because a heartbeat that stopped would pass a
    silence.
    """
    addr, stub, watcher = stack
    period = 1.6
    await watcher.subscribe(["sys.health"])

    first, at_first = await next_health(watcher)
    assert first["body"]["period_s"] == period  # the body declares what is enforced

    await asyncio.sleep(period * 0.6)
    await watcher.publish(
        "audio.transcript",
        {"kind": "final", "utterance_id": "utt-p", "text": "Hey Jarvis, hello",
         "lang": "en"},
        conf=0.9,
    )
    gauge, at_gauge = await next_health(watcher, gauge=True)
    # A turn slower than the period would make the rest of this measure
    # nothing and still pass.
    assert at_gauge - at_first < period, "the turn outran the period it was to land in"

    nxt, at_next = await next_health(watcher, timeout=period * 3)
    assert at_next - at_gauge >= period * 0.6, (
        f"the beat after the turn came {at_next - at_gauge:.3f}s later, "
        f"on the schedule that turn's beat should have taken over"
    )
