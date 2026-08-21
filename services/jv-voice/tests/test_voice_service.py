"""jv-voice service tests: real jarvisd, real Piper synthesis, fake
player (deterministic timing, no sound card)."""

import asyncio
import os
import socket
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from jarvis_bus import BusClient
from jv_voice.config import VoiceConfig
from jv_voice.player import FakePlayer
from jv_voice.service import VoiceService
from jv_voice.tts import Synthesizer

REPO = Path(__file__).resolve().parents[3]

CFG = VoiceConfig.load()
if not CFG.piper_onnx.exists():
    pytest.skip(
        "voice model missing — run ./models/fetch.sh --only voice",
        allow_module_level=True,
    )


def jarvisd_bin() -> Path:
    if env := os.environ.get("JARVISD_BIN"):
        return Path(env)
    exe = "jarvisd.exe" if sys.platform == "win32" else "jarvisd"
    for profile in ("debug", "release"):
        p = REPO / "services" / "jarvisd" / "target" / profile / exe
        if p.exists():
            return p
    pytest.skip("jarvisd binary not built")


@pytest.fixture(scope="module")
def synth() -> Synthesizer:
    return Synthesizer(CFG)


@pytest.fixture
async def bus_addr():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        addr = f"127.0.0.1:{s.getsockname()[1]}"
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


async def start_service(bus_addr, synth, player):
    svc_bus = await BusClient.connect(bus_addr, src="jv-voice")
    svc = VoiceService(svc_bus, synth, player)
    task = asyncio.create_task(svc.run())
    return svc_bus, task


async def collect_states(client, n, timeout=30.0):
    """Collect n speech.state bodies."""
    out = []
    async def inner():
        while len(out) < n:
            frame = await client.next_frame()
            if frame is None:
                break
            if frame["topic"] == "speech.state":
                out.append(frame["body"])
    await asyncio.wait_for(inner(), timeout)
    return out


async def say(client, text, say_id=None, **extra):
    body = {
        "text": text,
        "say_id": say_id or str(uuid.uuid4()),
        "in_reply_to_utterance": None,
        **extra,
    }
    await client.publish("speech.say", body)
    return body["say_id"]


async def test_say_speaks_and_completes(bus_addr, synth):
    watcher = await BusClient.connect(bus_addr, src="t-watch")
    await watcher.subscribe(["speech.*"])
    svc_bus, task = await start_service(bus_addr, synth, FakePlayer(0.3))
    await asyncio.sleep(0.2)

    sid = await say(watcher, "All systems online.")
    states = await collect_states(watcher, 3)
    # initial idle, speaking(sid), idle(completed, sid)
    assert states[0]["state"] == "idle"
    assert states[1] == {"state": "speaking", "say_id": sid}
    assert states[2] == {"state": "idle", "say_id": sid, "reason": "completed"}

    task.cancel()
    await watcher.close()
    await svc_bus.close()


async def test_wake_interrupts_mid_playback(bus_addr, synth):
    """BRIEF-phase1 exit item 3, minus the microphone."""
    watcher = await BusClient.connect(bus_addr, src="t-watch")
    await watcher.subscribe(["speech.state"])
    player = FakePlayer(clip_seconds=5.0)  # long enough to interrupt
    svc_bus, task = await start_service(bus_addr, synth, player)
    await asyncio.sleep(0.2)

    sid = await say(watcher, "This is a long announcement that should be cut off.")
    # wait until PLAYBACK started (not just synthesis), then barge in
    states = await collect_states(watcher, 2)
    assert states[-1]["state"] == "speaking"
    await asyncio.wait_for(player.started.wait(), timeout=20)
    await watcher.publish(
        "audio.wake", {"model": "hey_jarvis", "score": 0.9, "threshold": 0.5}, conf=0.9
    )
    states = await collect_states(watcher, 2)
    assert states[0] == {"state": "interrupted", "say_id": sid, "reason": "wake"}
    assert states[1]["state"] == "idle"
    assert player.aborted == 1

    task.cancel()
    await watcher.close()
    await svc_bus.close()


async def test_urgent_preempts_and_low_is_dropped(bus_addr, synth):
    watcher = await BusClient.connect(bus_addr, src="t-watch")
    await watcher.subscribe(["speech.state"])
    svc_bus, task = await start_service(bus_addr, synth, FakePlayer(5.0))
    await asyncio.sleep(0.2)

    normal = await say(watcher, "A long normal message playing first.")
    states = await collect_states(watcher, 2)
    assert states[-1] == {"state": "speaking", "say_id": normal}

    low = await say(watcher, "Low priority chatter.", priority="low")
    urgent = await say(watcher, "Urgent override.", priority="urgent")

    states = await collect_states(watcher, 3)
    assert states[0] == {"state": "interrupted", "say_id": normal, "reason": "preempted"}
    assert states[1]["state"] == "idle"
    assert states[2] == {"state": "speaking", "say_id": urgent}
    # the low item must never speak
    assert all(s.get("say_id") != low for s in states)

    task.cancel()
    await watcher.close()
    await svc_bus.close()
