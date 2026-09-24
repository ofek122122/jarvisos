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
from jv_voice.service import TURN_GAP_S, VoiceService
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


async def collect_health(client, n, timeout=30.0):
    """Collect n sys.health bodies from jv-voice."""
    out = []
    async def inner():
        while len(out) < n:
            frame = await client.next_frame()
            if frame is None:
                break
            if frame["topic"] == "sys.health":
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


async def test_wake_drops_the_rest_of_the_streamed_group(bus_addr, synth):
    """A streamed reply arrives as several speech.say with one reply_group.
    A wake mid-sentence must drop the WHOLE group's queued sentences, not
    just the one playing — otherwise Jarvis talks over the user who just
    interrupted (the point of barge-in)."""
    watcher = await BusClient.connect(bus_addr, src="t-watch")
    await watcher.subscribe(["speech.state"])
    player = FakePlayer(clip_seconds=5.0)
    svc_bus, task = await start_service(bus_addr, synth, player)
    await asyncio.sleep(0.2)

    grp = str(uuid.uuid4())
    s1 = await say(watcher, "First sentence playing now.", reply_group=grp)
    await say(watcher, "Second sentence queued.", reply_group=grp)
    await say(watcher, "Third sentence queued.", reply_group=grp)

    states = await collect_states(watcher, 2)  # idle, speaking(s1)
    assert states[-1] == {"state": "speaking", "say_id": s1}
    await asyncio.wait_for(player.started.wait(), timeout=20)

    await watcher.publish(
        "audio.wake", {"model": "hey_jarvis", "score": 0.9, "threshold": 0.5}, conf=0.9
    )
    states = await collect_states(watcher, 2)
    assert states[0] == {"state": "interrupted", "say_id": s1, "reason": "wake"}
    assert states[1]["state"] == "idle"

    # sentences 2 and 3 must NOT play — no further 'speaking' state
    with pytest.raises(asyncio.TimeoutError):
        await collect_states(watcher, 1, timeout=1.5)
    assert player.played == [player.played[0]]  # only sentence 1 ever synthed to play

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


async def test_streamed_reply_is_one_speaking_idle_pair(bus_addr, synth):
    """jv-brain emits one speech.say per SENTENCE, so a single answer used to
    make speech.state blink speaking->idle->speaking->idle once per sentence.
    One answer is one thing the user hears: one speaking, one idle."""
    watcher = await BusClient.connect(bus_addr, src="t-watch")
    await watcher.subscribe(["speech.state"])
    svc_bus, task = await start_service(bus_addr, synth, FakePlayer(0.2))
    await asyncio.sleep(0.2)

    grp = str(uuid.uuid4())
    s1 = await say(watcher, "First sentence.", reply_group=grp)
    s2 = await say(watcher, "Second sentence.", reply_group=grp)
    s3 = await say(watcher, "Third sentence.", reply_group=grp)

    states = await collect_states(watcher, 5)
    assert [s["state"] for s in states] == [
        "idle", "speaking", "speaking", "speaking", "idle",
    ]
    assert [s.get("say_id") for s in states] == [None, s1, s2, s3, s3]
    assert states[-1]["reason"] == "completed"

    task.cancel()
    await watcher.close()
    await svc_bus.close()


async def test_unrelated_utterances_still_get_their_own_pair(bus_addr, synth):
    """Only a reply_group makes sentences one turn. Two separate utterances
    are two separate things Jarvis said, and each still reports its own end."""
    watcher = await BusClient.connect(bus_addr, src="t-watch")
    await watcher.subscribe(["speech.state"])
    svc_bus, task = await start_service(bus_addr, synth, FakePlayer(0.2))
    await asyncio.sleep(0.2)

    a = await say(watcher, "Good morning.")
    b = await say(watcher, "The kettle is on.")

    states = await collect_states(watcher, 5)
    assert states[1] == {"state": "speaking", "say_id": a}
    assert states[2] == {"state": "idle", "say_id": a, "reason": "completed"}
    assert states[3] == {"state": "speaking", "say_id": b}
    assert states[4] == {"state": "idle", "say_id": b, "reason": "completed"}

    task.cancel()
    await watcher.close()
    await svc_bus.close()


async def test_a_sentence_arriving_in_the_gap_keeps_the_turn(bus_addr, synth):
    """The next sentence is not always queued when the previous one ends —
    the brain may still be generating it. A gap shorter than TURN_GAP_S is
    the same turn's next breath, not the end of the answer."""
    watcher = await BusClient.connect(bus_addr, src="t-watch")
    await watcher.subscribe(["speech.state"])
    player = FakePlayer(0.2)
    svc_bus, task = await start_service(bus_addr, synth, player)
    await asyncio.sleep(0.2)

    grp = str(uuid.uuid4())
    s1 = await say(watcher, "First sentence.", reply_group=grp)
    states = await collect_states(watcher, 2)
    assert states[-1] == {"state": "speaking", "say_id": s1}

    await asyncio.wait_for(player.finished.wait(), timeout=20)
    sent_at = asyncio.get_running_loop().time()
    s2 = await say(watcher, "Second sentence, a little late.", reply_group=grp)

    # No idle in between: the very next state is the second sentence speaking,
    # and it happens when the sentence LANDS, not when the gap budget runs out
    # (waiting TURN_GAP_S out would be half a second of added silence).
    states = await collect_states(watcher, 1)
    assert asyncio.get_running_loop().time() - sent_at < TURN_GAP_S / 2
    assert states[0] == {"state": "speaking", "say_id": s2}
    states = await collect_states(watcher, 1)
    assert states[0] == {"state": "idle", "say_id": s2, "reason": "completed"}

    task.cancel()
    await watcher.close()
    await svc_bus.close()


async def test_the_gap_is_bounded(bus_addr, synth):
    """A brain that dies mid-answer must not leave speech.state asserting
    'speaking' forever — silence past TURN_GAP_S is the turn ending."""
    watcher = await BusClient.connect(bus_addr, src="t-watch")
    await watcher.subscribe(["speech.state"])
    player = FakePlayer(0.2)
    svc_bus, task = await start_service(bus_addr, synth, player)
    await asyncio.sleep(0.2)

    grp = str(uuid.uuid4())
    s1 = await say(watcher, "First sentence.", reply_group=grp)
    states = await collect_states(watcher, 3)
    assert states[2] == {"state": "idle", "say_id": s1, "reason": "completed"}

    task.cancel()
    await watcher.close()
    await svc_bus.close()


async def test_a_sentence_published_after_a_barge_in_never_speaks(bus_addr, synth):
    """jv-brain stops generating an interrupted reply, but a sentence it
    published in the moment before that still arrives. Purging what is
    QUEUED is not enough — the turn stays dropped, or Jarvis talks over the
    user a second later with the tail of an answer nobody is listening
    to."""
    watcher = await BusClient.connect(bus_addr, src="t-watch")
    await watcher.subscribe(["speech.state"])
    player = FakePlayer(clip_seconds=5.0)
    svc_bus, task = await start_service(bus_addr, synth, player)
    await asyncio.sleep(0.2)

    grp = str(uuid.uuid4())
    s1 = await say(watcher, "A long first sentence to interrupt.", reply_group=grp)
    states = await collect_states(watcher, 2)
    assert states[-1] == {"state": "speaking", "say_id": s1}
    await asyncio.wait_for(player.started.wait(), timeout=20)

    await watcher.publish(
        "audio.wake", {"model": "hey_jarvis", "score": 0.9, "threshold": 0.5}, conf=0.9
    )
    states = await collect_states(watcher, 2)
    assert states[0] == {"state": "interrupted", "say_id": s1, "reason": "wake"}
    assert states[1]["state"] == "idle"

    # The brain, still streaming, publishes the rest of the dropped turn.
    await say(watcher, "The rest of the abandoned answer.", reply_group=grp)
    with pytest.raises(asyncio.TimeoutError):
        await collect_states(watcher, 1, timeout=1.5)
    assert player.played == [player.played[0]]

    task.cancel()
    await watcher.close()
    await svc_bus.close()


async def test_a_wake_between_sentences_still_drops_the_turn(bus_addr, synth):
    """The gaps between a streamed reply's sentences are inside the turn, so
    barging in there must end it like barging in mid-sentence does. (The
    sentence that just played did complete — it is the TURN that was cut, and
    speech.state's `reason` is about the utterance, so it reads completed.)"""
    watcher = await BusClient.connect(bus_addr, src="t-watch")
    await watcher.subscribe(["speech.state"])
    player = FakePlayer(0.2)
    svc_bus, task = await start_service(bus_addr, synth, player)
    await asyncio.sleep(0.2)

    grp = str(uuid.uuid4())
    s1 = await say(watcher, "First sentence.", reply_group=grp)
    states = await collect_states(watcher, 2)
    assert states[-1] == {"state": "speaking", "say_id": s1}

    await asyncio.wait_for(player.finished.wait(), timeout=20)
    woke_at = asyncio.get_running_loop().time()
    await watcher.publish(
        "audio.wake", {"model": "hey_jarvis", "score": 0.9, "threshold": 0.5}, conf=0.9
    )
    await say(watcher, "Second sentence, no longer wanted.", reply_group=grp)

    states = await collect_states(watcher, 1)
    # Immediately, not when the gap budget expires: jv-ears reopens its
    # half-duplex gate on this frame, and the user is already speaking.
    assert asyncio.get_running_loop().time() - woke_at < TURN_GAP_S / 2
    assert states[0] == {"state": "idle", "say_id": s1, "reason": "completed"}
    with pytest.raises(asyncio.TimeoutError):
        await collect_states(watcher, 1, timeout=1.5)

    task.cancel()
    await watcher.close()
    await svc_bus.close()


async def test_an_unrelated_utterance_waits_for_the_turn_to_end(bus_addr, synth):
    """FIFO is between turns, not inside one: an announcement published while
    Jarvis is mid-answer is spoken after the answer, never wedged between two
    of its sentences."""
    watcher = await BusClient.connect(bus_addr, src="t-watch")
    await watcher.subscribe(["speech.state"])
    svc_bus, task = await start_service(bus_addr, synth, FakePlayer(0.2))
    await asyncio.sleep(0.2)

    grp = str(uuid.uuid4())
    s1 = await say(watcher, "First sentence.", reply_group=grp)
    other = await say(watcher, "The kettle is on.")
    s2 = await say(watcher, "Second sentence.", reply_group=grp)

    states = await collect_states(watcher, 6)
    assert [s.get("say_id") for s in states] == [None, s1, s2, s2, other, other]
    assert [s["state"] for s in states[1:]] == [
        "speaking", "speaking", "idle", "speaking", "idle",
    ]

    task.cancel()
    await watcher.close()
    await svc_bus.close()


# --- the one fact about jv-voice another service reads (PLAN A41) --------
#
# The HUD's OutputPlate says OUTPUT MUTED while Jarvis is speaking, off
# jv-context's reading of the DEFAULT SINK. That the default sink is what
# jv-voice plays into is true only while no device is pinned here — so
# jv-voice states it, in the one place the schema leaves for a service's
# own gauges. `sys.health.metrics` is numbers only
# (schemas/sys.health.json), which is why this is a 1/0 and not a name: the
# HUD does not need to know WHICH device, only whether the sink it can see
# is the one that matters.


async def test_the_heartbeat_states_that_playback_took_the_default(bus_addr, synth):
    watcher = await BusClient.connect(bus_addr, src="t-watch")
    await watcher.subscribe(["sys.health"])
    svc_bus, task = await start_service(bus_addr, synth, FakePlayer(0.1))

    beat = (await collect_health(watcher, 1))[0]
    assert beat["service"] == "jv-voice"
    assert beat["metrics"] == {"output_device_pinned": 0.0}

    task.cancel()
    await watcher.close()
    await svc_bus.close()


async def test_the_heartbeat_states_a_pinned_device(bus_addr, synth):
    """The day somebody points jv-voice at a device, the HUD must stop
    reading the default sink as a statement about Jarvis."""
    watcher = await BusClient.connect(bus_addr, src="t-watch")
    await watcher.subscribe(["sys.health"])
    svc_bus, task = await start_service(bus_addr, synth, FakePlayer(0.1, pinned=True))

    beat = (await collect_health(watcher, 1))[0]
    assert beat["metrics"] == {"output_device_pinned": 1.0}

    task.cancel()
    await watcher.close()
    await svc_bus.close()


async def test_a_degraded_heartbeat_carries_it_too(bus_addr, synth):
    """The heartbeat that reports a playback failure is exactly the one the
    HUD is most likely to be reading when it matters, and a body that drops
    the gauge would read as "unknown device" — silencing the plate for the
    wrong reason."""

    class BrokenPlayer(FakePlayer):
        async def play(self, audio, rate, abort):
            raise RuntimeError("no such device")

    watcher = await BusClient.connect(bus_addr, src="t-watch")
    await watcher.subscribe(["sys.health"])
    svc_bus, task = await start_service(bus_addr, synth, BrokenPlayer(0.1, pinned=True))
    await asyncio.sleep(0.2)
    await say(watcher, "Anything at all.")

    beats = await collect_health(watcher, 2)
    degraded = [b for b in beats if b["state"] == "degraded"]
    assert degraded, f"no degraded heartbeat: {beats}"
    assert degraded[0]["metrics"] == {"output_device_pinned": 1.0}
    assert "no such device" in degraded[0]["notes"]

    task.cancel()
    await watcher.close()
    await svc_bus.close()
