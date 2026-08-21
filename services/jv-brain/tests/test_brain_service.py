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
from jv_brain.service import BrainService, strip_wake_prefix

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


class StubLLM:
    """Minimal OpenAI-compatible /v1/chat/completions responder.
    Replies 'You said: <last user message>' and records every request."""

    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.server: asyncio.AbstractServer | None = None
        self.port = 0

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
            last_user = [m for m in payload["messages"] if m["role"] == "user"][-1]
            body = json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": f"You said: {last_user['content']}",
                            },
                            "finish_reason": "stop",
                        }
                    ]
                }
            ).encode()
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                + f"Content-Length: {len(body)}\r\n\r\n".encode()
                + body
            )
            await writer.drain()
        finally:
            writer.close()


@pytest.fixture
async def stack(tmp_path):
    """jarvisd + stub LLM + BrainService, wired together."""
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
    svc = BrainService(svc_bus, cfg)
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
    resp = await next_topic(watcher, "brain.response")
    assert resp["body"]["text"] == "You said: what time is it?"  # wake prefix stripped
    assert resp["body"]["utterance_id"] == "utt-1"
    assert resp["body"]["backend"] == "gpu"
    assert resp["body"]["in_reply_to"]["src"] == "t-watch"

    say = await next_topic(watcher, "speech.say")
    assert say["body"]["in_reply_to_utterance"] == "utt-1"  # the E2E thread
    assert say["body"]["text"] == resp["body"]["text"]

    # system prompt reached the LLM
    assert stub.requests[0]["messages"][0]["role"] == "system"
    assert "Jarvis" in stub.requests[0]["messages"][0]["content"]
    assert stub.requests[0]["chat_template_kwargs"] == {"enable_thinking": False}


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
    assert stub.requests == []


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
    msgs = stub.requests[1]["messages"]
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
