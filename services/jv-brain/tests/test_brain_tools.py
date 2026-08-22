"""Brain v1 tool-calling tests: real jarvisd, scripted OpenAI stub, a
fake 'act' implemented by the test. Covers the happy path, the
hallucination rule, and the 5-calls-per-turn cap (BRIEF-phase2 §3)."""

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
from jv_brain.service import BrainService

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


def tool_call(name: str, args: dict, tc_id: str = "tc1") -> dict:
    return {
        "id": tc_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)},
    }


class ScriptedLLM:
    """OpenAI-compatible stub that plays back a scripted list of
    assistant messages, recording every request."""

    def __init__(self, script: list[dict]) -> None:
        self.script = list(script)
        self.requests: list[dict] = []
        self.server: asyncio.AbstractServer | None = None
        self.port = 0

    async def start(self) -> None:
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def _handle(self, reader, writer):
        try:
            head = await reader.readuntil(b"\r\n\r\n")
            length = 0
            for line in head.decode("latin1").split("\r\n"):
                if line.lower().startswith("content-length:"):
                    length = int(line.split(":", 1)[1])
            self.requests.append(json.loads(await reader.readexactly(length)))
            message = (
                self.script.pop(0)
                if self.script
                else {"role": "assistant", "content": "script exhausted"}
            )
            body = json.dumps(
                {"choices": [{"message": message, "finish_reason": "stop"}]}
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
async def bus_addr():
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
    yield addr
    proc.kill()
    proc.wait(timeout=10)


async def start_brain(bus_addr, script, tmp_path):
    stub = ScriptedLLM(script)
    await stub.start()
    rung_file = tmp_path / "llm-rung"
    rung_file.write_text("rung=0\nlabel=full\nbackend=gpu\nfree_vram_mb=9999\n")
    cfg = BrainConfig(
        llm_url=f"http://127.0.0.1:{stub.port}",
        rung_file=rung_file,
        personality_dir=REPO / "personality",
    )
    svc_bus = await BusClient.connect(bus_addr, src="jv-brain")
    svc = BrainService(svc_bus, cfg)
    assert svc.tools, "registry tools must load (services/jv-act/tools.toml)"
    task = asyncio.create_task(svc.run())
    await asyncio.sleep(0.2)
    return stub, svc, svc_bus, task


async def next_topic(client, topic, timeout=10.0):
    async def inner():
        while True:
            frame = await client.next_frame()
            assert frame is not None
            if frame["topic"] == topic:
                return frame
    return await asyncio.wait_for(inner(), timeout)


async def test_tool_roundtrip_and_spoken_summary(bus_addr, tmp_path):
    script = [
        {"role": "assistant", "content": None,
         "tool_calls": [tool_call("app.launch", {"app": "firefox"})]},
        {"role": "assistant", "content": "Firefox is open."},
    ]
    stub, svc, svc_bus, task = await start_brain(bus_addr, script, tmp_path)
    watcher = await BusClient.connect(bus_addr, src="t-act")
    await watcher.subscribe(["intent.action", "brain.response", "speech.say"])
    await asyncio.sleep(0.1)

    await watcher.publish(
        "audio.transcript",
        {"kind": "final", "utterance_id": "u1", "text": "Hey Jarvis, open Firefox", "lang": "en"},
        conf=0.9,
    )

    intent = await next_topic(watcher, "intent.action")
    assert intent["body"]["tool"] == "app.launch"
    assert intent["body"]["args"] == {"app": "firefox"}
    assert intent["body"]["capability"] == "benign"  # from the registry
    assert intent["body"]["utterance_id"] == "u1"

    # the test plays jv-act
    await watcher.publish(
        "action.result",
        {"request_id": intent["body"]["request_id"], "ok": True,
         "duration_ms": 5.0, "output": "launched firefox"},
    )

    resp = await next_topic(watcher, "brain.response")
    assert resp["body"]["text"] == "Firefox is open."
    say = await next_topic(watcher, "speech.say")
    assert say["body"]["in_reply_to_utterance"] == "u1"

    # the tool result reached the second LLM call as a tool message
    tool_msgs = [m for m in stub.requests[1]["messages"] if m["role"] == "tool"]
    assert tool_msgs and "launched firefox" in tool_msgs[0]["content"]

    task.cancel()
    await svc.close()
    await svc_bus.close()
    await watcher.close()


async def test_hallucinated_tool_never_reaches_act(bus_addr, tmp_path):
    script = [
        {"role": "assistant", "content": None,
         "tool_calls": [tool_call("files.nuke_everything", {"path": "/"})]},
        {"role": "assistant", "content": "I don't have a tool for that."},
    ]
    stub, svc, svc_bus, task = await start_brain(bus_addr, script, tmp_path)
    watcher = await BusClient.connect(bus_addr, src="t-act")
    await watcher.subscribe(["intent.action", "brain.response"])
    await asyncio.sleep(0.1)

    await watcher.publish(
        "brain.request", {"text": "wipe the disk", "source": "cli", "speak": False}
    )
    resp = await next_topic(watcher, "brain.response")
    assert resp["body"]["text"] == "I don't have a tool for that."

    # no intent.action was ever published
    with pytest.raises(asyncio.TimeoutError):
        await next_topic(watcher, "intent.action", timeout=0.8)

    # the rejection went back to the LLM, and the counter shows in health
    tool_msgs = [m for m in stub.requests[1]["messages"] if m["role"] == "tool"]
    assert "unknown_tool" in tool_msgs[0]["content"]
    assert svc._hallucinated_calls == 1

    task.cancel()
    await svc.close()
    await svc_bus.close()
    await watcher.close()


async def test_five_call_cap_per_turn(bus_addr, tmp_path):
    # 6 rounds of tool calls + a final answer; only 5 may execute.
    script = [
        {"role": "assistant", "content": None,
         "tool_calls": [tool_call("app.launch", {"app": f"app{i}"}, f"tc{i}")]}
        for i in range(6)
    ] + [{"role": "assistant", "content": "Done what I could."}]
    stub, svc, svc_bus, task = await start_brain(bus_addr, script, tmp_path)
    watcher = await BusClient.connect(bus_addr, src="t-act")
    await watcher.subscribe(["intent.action", "brain.response"])
    await asyncio.sleep(0.1)

    await watcher.publish(
        "brain.request", {"text": "open everything", "source": "cli", "speak": False}
    )

    executed = 0

    async def fake_act():
        nonlocal executed
        while True:
            intent = await next_topic(watcher, "intent.action", timeout=15)
            executed += 1
            await watcher.publish(
                "action.result",
                {"request_id": intent["body"]["request_id"], "ok": True,
                 "duration_ms": 1.0, "output": "ok"},
            )

    act_task = asyncio.create_task(fake_act())
    # wait for the final response by polling the stub's script drain
    for _ in range(200):
        if not stub.script:
            break
        await asyncio.sleep(0.05)
    await asyncio.sleep(0.3)
    act_task.cancel()

    assert executed == 5, f"cap violated: {executed} tool calls executed"
    # the 6th call got a limit rejection as its tool message
    last_tools = [m for m in stub.requests[-1]["messages"] if m["role"] == "tool"]
    assert any("tool_call_limit" in m["content"] for m in last_tools)

    task.cancel()
    await svc.close()
    await svc_bus.close()
    await watcher.close()
