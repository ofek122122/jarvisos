"""Barge-in: when the user wakes Jarvis while Jarvis is still answering,
the answer in flight must STOP — the generation, the GPU it is holding,
and the sentences jv-brain would otherwise keep publishing at a user who
has stopped listening (jv-voice can only drop what reaches it).

The turn is not allowed to vanish either: what was said is recorded as
interrupted, so the next request does not show the model an answer it
never finished as if it had been delivered whole.

Real jarvisd, a stub LLM that streams SLOWLY (so a wake can land
mid-reply), no GPU and no weights — as everywhere else in this suite.
"""

import asyncio
import json
import subprocess

import pytest

from jarvis_bus import BusClient
from jv_brain.config import BrainConfig
from jv_brain.service import BrainService, interrupted_record, wake_contradicts_itself

from test_brain_service import REPO, free_port, jarvisd_bin, next_topic, sse

# Three sentences, each several tokens long: with DELAY_S per token the
# test can receive sentence 1, publish a wake, and still be well inside
# sentence 2 (jv-brain polls the bus every 0.1 s).
REPLY = "Sentence one here. Sentence two here. Sentence three here."
DELAY_S = 0.25


class SlowLLM:
    """OpenAI-compatible stub whose stream arrives one token at a time,
    `delay` seconds apart. Tolerates the client vanishing mid-stream —
    that is exactly what a barge-in does to it."""

    def __init__(self, reply: str = REPLY, delay: float = DELAY_S) -> None:
        self.reply = reply
        self.delay = delay
        self.requests: list[dict] = []
        self.server: asyncio.AbstractServer | None = None
        self.port = 0
        self.disconnected = 0  # streams the client hung up on

    async def start(self) -> None:
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            head = await reader.readuntil(b"\r\n\r\n")
            length = 0
            for line in head.decode("latin1").split("\r\n"):
                if line.lower().startswith("content-length:"):
                    length = int(line.split(":", 1)[1])
            payload = json.loads(await reader.readexactly(length))
            self.requests.append(payload)
            if payload.get("stream"):
                await self._stream(writer)
            else:
                body = json.dumps(
                    {"choices": [{"message": {"role": "assistant", "content": self.reply},
                                  "finish_reason": "stop"}]}
                ).encode()
                writer.write(
                    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                    + f"Content-Length: {len(body)}\r\n\r\n".encode()
                    + body
                )
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError, OSError):
            self.disconnected += 1
        finally:
            writer.close()

    async def _stream(self, writer: asyncio.StreamWriter) -> None:
        """Chunked SSE, one token per write, `delay` apart."""
        writer.write(
            b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
            b"Transfer-Encoding: chunked\r\n\r\n"
        )
        await writer.drain()
        deltas = [{"choices": [{"delta": {"role": "assistant"}}]}]
        for tok in self.reply.split(" "):
            deltas.append({"choices": [{"delta": {"content": tok + " "}}]})
        deltas.append({"choices": [{"delta": {}, "finish_reason": "stop"}]})
        try:
            for i, delta in enumerate(deltas):
                piece = sse([delta])[: -len(b"data: [DONE]\r\n\r\n")]
                writer.write(b"%x\r\n" % len(piece) + piece + b"\r\n")
                await writer.drain()
                if i:
                    await asyncio.sleep(self.delay)
            done = b"data: [DONE]\r\n\r\n"
            writer.write(b"%x\r\n" % len(done) + done + b"\r\n0\r\n\r\n")
            await writer.drain()
        except (ConnectionError, OSError):
            self.disconnected += 1


@pytest.fixture
async def stack(tmp_path):
    """jarvisd + slow stub LLM + BrainService. Yields the service too: a
    barge-in is counted in-process before it reaches the next heartbeat."""
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

    stub = SlowLLM()
    await stub.start()
    rung_file = tmp_path / "llm-rung"
    rung_file.write_text("rung=1\nlabel=KV q8\nbackend=gpu\nfree_vram_mb=5800\n")
    cfg = BrainConfig(
        llm_url=f"http://127.0.0.1:{stub.port}",
        rung_file=rung_file,
        personality_dir=REPO / "personality",
    )
    svc_bus = await BusClient.connect(addr, src="jv-brain")
    svc = BrainService(svc_bus, cfg)
    task = asyncio.create_task(svc.run())
    await asyncio.sleep(0.2)
    watcher = await BusClient.connect(addr, src="t-watch")
    yield stub, watcher, svc
    task.cancel()
    await svc.close()
    await svc_bus.close()
    await watcher.close()
    stub.server.close()
    proc.kill()
    proc.wait(timeout=10)


async def speak_to(watcher, text: str, utterance_id: str = "utt-1") -> None:
    await watcher.publish(
        "audio.transcript",
        {"kind": "final", "utterance_id": utterance_id, "text": text, "lang": "en"},
        conf=0.9,
    )


async def wake(watcher, score: float = 0.71, threshold: float = 0.6) -> None:
    await watcher.publish(
        "audio.wake",
        {"model": "hey_jarvis", "score": score, "threshold": threshold},
        conf=score,
    )


def test_interrupted_record_keeps_what_was_said_and_says_it_was_cut():
    rec = interrupted_record("Sentence one here.")
    assert rec.startswith("Sentence one here.")
    assert "interrupt" in rec.lower()
    # Nothing was said at all: still a turn, still truthful about it.
    assert "interrupt" in interrupted_record("").lower()
    assert interrupted_record("") != ""


def test_only_a_self_contradicting_wake_is_refused():
    """The narrow rule: a frame is refused only when it reports a score
    below the threshold it says it fired against. Anything else — an
    unreadable score, a missing threshold — is unverifiable, not
    contradictory, and jv-voice acts on every wake it sees."""
    assert wake_contradicts_itself({"score": 0.2, "threshold": 0.6})
    assert not wake_contradicts_itself({"score": 0.71, "threshold": 0.6})
    assert not wake_contradicts_itself({"score": 0.6, "threshold": 0.6})  # cleared it
    assert not wake_contradicts_itself({"score": 0.2})  # nothing to contradict
    assert not wake_contradicts_itself({"score": "0.2", "threshold": 0.6})
    assert not wake_contradicts_itself({})
    # A bool is not a number: `False < 0.6` is true in Python, so letting
    # one reach the comparison would turn a field we cannot read into a
    # refusal — and `threshold: true` would refuse almost every wake.
    assert not wake_contradicts_itself({"score": False, "threshold": 0.6})
    assert not wake_contradicts_itself({"score": 0.2, "threshold": True})


async def test_a_wake_stops_the_rest_of_the_answer(stack):
    stub, watcher, svc = stack
    await watcher.subscribe(["brain.response", "speech.say"])
    await asyncio.sleep(0.1)

    await speak_to(watcher, "Tell me a long thing")
    say1 = await next_topic(watcher, "speech.say")
    assert say1["body"]["text"] == "Sentence one here."

    await wake(watcher)
    # No further sentence of this reply, and no brain.response claiming a
    # finished answer: the frozen finish_reason enum has no word for what
    # happened (see the proposal in docs/optimization-backlog.md).
    with pytest.raises(asyncio.TimeoutError):
        await next_topic(watcher, "speech.say", timeout=1.5)
    with pytest.raises(asyncio.TimeoutError):
        await next_topic(watcher, "brain.response", timeout=1.0)
    assert svc._barge_ins == 1
    # the generation itself was dropped, not just the speaking of it
    assert stub.disconnected >= 1


async def test_the_interrupted_turn_is_recorded_as_interrupted(stack):
    """The next request must show the model a turn that was cut off — not
    a missing answer (two user messages in a row), and not a whole one."""
    stub, watcher, svc = stack
    await watcher.subscribe(["speech.say", "brain.response"])
    await asyncio.sleep(0.1)

    await speak_to(watcher, "Tell me a long thing")
    await next_topic(watcher, "speech.say")
    await wake(watcher)
    await asyncio.sleep(0.5)

    stub.delay = 0.0  # the follow-up need not crawl
    await watcher.publish(
        "brain.request",
        {"text": "and now this", "source": "cli", "conversation_id": "voice",
         "speak": False},
    )
    await next_topic(watcher, "brain.response")

    msgs = stub.requests[-1]["messages"]
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"]
    assert msgs[1]["content"] == "Tell me a long thing"
    assert msgs[2]["content"].startswith("Sentence one here.")
    assert "interrupt" in msgs[2]["content"].lower()
    assert "Sentence three" not in msgs[2]["content"]


async def test_a_wake_with_nothing_in_flight_changes_nothing(stack):
    stub, watcher, svc = stack
    await watcher.subscribe(["brain.response"])
    await asyncio.sleep(0.1)

    await wake(watcher)
    await asyncio.sleep(0.3)
    stub.delay = 0.0
    await speak_to(watcher, "Anything at all")
    resp = await next_topic(watcher, "brain.response")
    assert resp["body"]["text"] == REPLY
    assert svc._barge_ins == 0


async def test_a_wake_after_the_answer_does_not_cancel_the_next_turn(stack):
    """A stale wake must not reach through a finished turn into the one
    after it — the wake's own utterance IS the next turn."""
    stub, watcher, svc = stack
    await watcher.subscribe(["brain.response"])
    await asyncio.sleep(0.1)

    stub.delay = 0.0
    await speak_to(watcher, "First question", "utt-1")
    await next_topic(watcher, "brain.response")
    await wake(watcher)
    await asyncio.sleep(0.2)
    await speak_to(watcher, "Second question", "utt-2")
    resp = await next_topic(watcher, "brain.response")
    assert resp["body"]["text"] == REPLY
    assert resp["body"]["utterance_id"] == "utt-2"
    assert svc._barge_ins == 0


async def test_a_wake_under_its_own_threshold_is_refused(stack):
    """jv-ears publishes the threshold that was configured when a wake
    fired. A frame that does not clear it is not evidence of anything, and
    losing an answer to one would be worse than the bug being fixed."""
    stub, watcher, svc = stack
    await watcher.subscribe(["brain.response", "speech.say"])
    await asyncio.sleep(0.1)

    await speak_to(watcher, "Tell me a long thing")
    await next_topic(watcher, "speech.say")
    await wake(watcher, score=0.2, threshold=0.6)
    resp = await next_topic(watcher, "brain.response")
    assert resp["body"]["text"] == REPLY
    assert resp["body"]["finish_reason"] == "stop"
    assert svc._barge_ins == 0


async def test_an_unreadable_score_still_stops_the_answer(stack):
    """A wake whose score cannot be read is still a wake: it is acted on,
    and the comparison must not raise on the frame-reading loop (which
    would take every future turn with it)."""
    stub, watcher, svc = stack
    await watcher.subscribe(["brain.response", "speech.say"])
    await asyncio.sleep(0.1)

    await speak_to(watcher, "Tell me a long thing")
    await next_topic(watcher, "speech.say")
    await watcher.publish(
        "audio.wake", {"model": "hey_jarvis", "score": "0.9", "threshold": 0.6}, conf=0.9
    )
    with pytest.raises(asyncio.TimeoutError):
        await next_topic(watcher, "brain.response", timeout=1.5)
    assert svc._barge_ins == 1
    # the loop is alive: the next turn is answered normally
    stub.delay = 0.0
    await speak_to(watcher, "Still there?", "utt-2")
    resp = await next_topic(watcher, "brain.response")
    assert resp["body"]["utterance_id"] == "utt-2"


async def test_a_silent_turn_is_not_barged_in(stack):
    """A wake says the user is talking to Jarvis. It does not say the HUD
    or the CLI stopped wanting the answer it asked for — and nothing is
    being spoken over, so there is nothing to stop."""
    stub, watcher, svc = stack
    await watcher.subscribe(["brain.response"])
    await asyncio.sleep(0.1)

    await watcher.publish(
        "brain.request",
        {"text": "quietly please", "source": "cli", "conversation_id": "t",
         "speak": False},
    )
    await asyncio.sleep(0.4)  # mid-stream
    await wake(watcher)
    resp = await next_topic(watcher, "brain.response")
    assert resp["body"]["text"] == REPLY
    assert svc._barge_ins == 0


async def test_barge_ins_are_reported_in_sys_health(stack):
    """A count nobody can see is not observable. sys.health's metrics map
    is free-form (no schema change), which is where jv-brain already
    reports hallucinated tool calls."""
    stub, watcher, svc = stack
    await watcher.subscribe(["sys.health", "speech.say"])
    await asyncio.sleep(0.1)

    await speak_to(watcher, "Tell me a long thing")
    await next_topic(watcher, "speech.say")
    await wake(watcher)

    async def with_barge_ins():
        while True:
            frame = await next_topic(watcher, "sys.health")
            metrics = frame["body"].get("metrics") or {}
            if "barge_ins" in metrics:
                return metrics["barge_ins"]

    assert await asyncio.wait_for(with_barge_ins(), 12.0) == 1.0
