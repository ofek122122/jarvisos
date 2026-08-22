"""Onboarding + greeting tests. The meeting runs against the stub LLM
and scripted 'voice' answers (as WavSource->ears would produce), so
install day is not its first execution (requirement 6). No name is
hardcoded anywhere — a fresh profile path per test proves it."""

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
from jv_brain.onboarding import detect_name_correction, extract_name
from jv_brain.profile import Profile
from jv_brain.service import BrainService, _yes_no

REPO = Path(__file__).resolve().parents[3]


# ------------------------------------------------------- pure helpers


def test_extract_name_rules():
    assert extract_name("Call me Ofek") == "Ofek"
    assert extract_name("my name is Dana") == "Dana"
    assert extract_name("I'm Sam") == "Sam"
    assert extract_name("Ofek") == "Ofek"  # bare
    assert extract_name("yes") is None  # stopword
    assert extract_name("um, well, hello there friend") is None


def test_name_correction():
    assert detect_name_correction("actually call me Ben") == "Ben"
    assert detect_name_correction("it's pronounced Yo-av") == "Yo-av"
    assert detect_name_correction("open firefox") is None


def test_yes_no():
    assert _yes_no("yes") is True
    assert _yes_no("yes that's right") is True
    assert _yes_no("no") is False
    assert _yes_no("maybe later") is None


def test_fresh_profile_knows_nothing(tmp_path):
    prof = Profile.load(tmp_path / "p.json")
    assert prof.name is None
    assert not prof.onboarding_complete
    assert "not met your user yet" in prof.render_about_user()
    assert prof.pending_questions  # seeded trickle list


def test_profile_reset(tmp_path):
    path = tmp_path / "p.json"
    prof = Profile.load(path)
    prof.set_fact("name", "Ofek", "name", "2026-08-22T00:00:00Z", "onboarding")
    prof.save()
    assert path.exists()
    assert Profile.reset(path) is True
    assert not path.exists()
    assert Profile.reset(path) is False


# ------------------------------------------------------- meeting e2e


def jarvisd_bin() -> Path:
    if env := os.environ.get("JARVISD_BIN"):
        return Path(env)
    exe = "jarvisd.exe" if sys.platform == "win32" else "jarvisd"
    for profile in ("debug", "release"):
        p = REPO / "services" / "jarvisd" / "target" / profile / exe
        if p.exists():
            return p
    pytest.skip("jarvisd binary not built")


class StubLLM:
    """Only used as the name-extraction fallback here; the scripted
    answers are rule-extractable so it mostly won't be hit."""

    def __init__(self):
        self.server = None
        self.port = 0

    async def start(self):
        self.server = await asyncio.start_server(self._h, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def _h(self, r, w):
        try:
            head = await r.readuntil(b"\r\n\r\n")
            length = next(
                (int(l.split(":", 1)[1]) for l in head.decode("latin1").split("\r\n")
                 if l.lower().startswith("content-length:")), 0
            )
            await r.readexactly(length)
            body = json.dumps(
                {"choices": [{"message": {"role": "assistant", "content": "NONE"},
                              "finish_reason": "stop"}]}
            ).encode()
            w.write(b"HTTP/1.1 200 OK\r\nContent-Length: " + str(len(body)).encode()
                    + b"\r\n\r\n" + body)
            await w.drain()
        finally:
            w.close()


@pytest.fixture
async def bus_addr():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        addr = f"127.0.0.1:{s.getsockname()[1]}"
    proc = subprocess.Popen(
        [str(jarvisd_bin()), "--bus", addr],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
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


async def brain(bus_addr, tmp_path):
    stub = StubLLM()
    await stub.start()
    rung = tmp_path / "rung"
    rung.write_text("rung=0\nbackend=gpu\n")
    cfg = BrainConfig(
        llm_url=f"http://127.0.0.1:{stub.port}",
        rung_file=rung,
        personality_dir=REPO / "personality",
    )
    cfg_profile = tmp_path / "profile.json"
    svc_bus = await BusClient.connect(bus_addr, src="jv-brain")
    svc = BrainService(svc_bus, cfg)
    # redirect the profile to a temp path (no hardcoded user, no real state)
    svc.profile = Profile.load(cfg_profile)
    task = asyncio.create_task(svc.run())
    await asyncio.sleep(0.2)
    return svc, svc_bus, task


async def next_say(client, timeout=10.0):
    async def inner():
        while True:
            f = await client.next_frame()
            if f and f["topic"] == "speech.say":
                return f["body"]["text"]
    return await asyncio.wait_for(inner(), timeout)


async def wait_listen(client, timeout=10.0):
    async def inner():
        while True:
            f = await client.next_frame()
            if f and f["topic"] == "dialog.listen":
                return f["body"]["reason"]
    return await asyncio.wait_for(inner(), timeout)


async def say_as_user(client, text):
    await client.publish(
        "audio.transcript",
        {"kind": "final", "utterance_id": "u", "text": text, "lang": "en"},
        conf=0.9,
    )


async def test_first_boot_meets_the_user(bus_addr, tmp_path):
    svc, svc_bus, task = await brain(bus_addr, tmp_path)
    watcher = await BusClient.connect(bus_addr, src="w")
    await watcher.subscribe(["speech.say", "dialog.listen"])
    await asyncio.sleep(0.1)

    # session start (as the greeting oneshot unit would send)
    await watcher.publish("brain.request",
                          {"text": "session_start", "source": "system",
                           "conversation_id": "system", "speak": False})

    intro = await next_say(watcher)
    assert "jarvis" in intro.lower()
    assert "don't know anything about you" in intro.lower()
    assert await wait_listen(watcher) == "onboarding"

    # the user answers with a name (no wake word — a dialog window)
    await say_as_user(watcher, "Call me Ofek")
    pron = await next_say(watcher)
    assert "Ofek" in pron and "right" in pron.lower()
    await wait_listen(watcher)

    # confirms pronunciation
    await say_as_user(watcher, "yes")
    welcome = await next_say(watcher)
    assert "Ofek" in welcome

    # profile persisted, name learned, no longer first boot
    saved = Profile.load(svc.profile.path)
    assert saved.name == "Ofek"
    assert saved.onboarding_complete
    # and the system prompt now speaks the user's name
    assert "Ofek" in svc.system_prompt

    task.cancel()
    await svc.close()
    await svc_bus.close()
    await watcher.close()


async def test_greeting_uses_name_when_known(bus_addr, tmp_path):
    svc, svc_bus, task = await brain(bus_addr, tmp_path)
    # pre-seed a known user
    svc.profile.set_fact("name", "Dana", "name", "2026-08-22T00:00:00Z", "onboarding")
    svc.profile.onboarding_complete = True
    svc.profile.save()

    watcher = await BusClient.connect(bus_addr, src="w")
    await watcher.subscribe(["speech.say"])
    await asyncio.sleep(0.1)

    await watcher.publish("brain.request",
                          {"text": "session_start", "source": "system",
                           "conversation_id": "system", "speak": False})
    greeting = await next_say(watcher)
    assert "Dana" in greeting
    assert greeting.lower().startswith("good ")

    task.cancel()
    await svc.close()
    await svc_bus.close()
    await watcher.close()


async def test_name_correction_updates_profile(bus_addr, tmp_path):
    svc, svc_bus, task = await brain(bus_addr, tmp_path)
    svc.profile.set_fact("name", "Ofek", "name", "2026-08-22T00:00:00Z", "onboarding")
    svc.profile.onboarding_complete = True
    svc.profile.save()

    watcher = await BusClient.connect(bus_addr, src="w")
    await watcher.subscribe(["speech.say"])
    await asyncio.sleep(0.1)

    await say_as_user(watcher, "actually call me Ben")
    ack = await next_say(watcher)
    assert "Ben" in ack
    saved = Profile.load(svc.profile.path)
    assert saved.name == "Ben"
    # correction kept the original first_seen (it's the same fact)
    assert saved.facts["name"]["source"] == "correction"

    task.cancel()
    await svc.close()
    await svc_bus.close()
    await watcher.close()
