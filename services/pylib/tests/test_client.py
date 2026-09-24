"""Integration tests for the Python bus client against a REAL jarvisd.

Requires the broker binary: cargo build in services/jarvisd first (CI
does; locally: cargo build). Set JARVISD_BIN to override the path.
"""

import asyncio
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from jarvis_bus import BusClient, BusError
from jarvis_bus.client import DEFAULT_UNIX, MAX_FRAME, default_addr
from jarvis_bus.schema import AudioWake, from_body, to_body

REPO = Path(__file__).resolve().parents[3]


def jarvisd_bin() -> Path:
    if env := os.environ.get("JARVISD_BIN"):
        return Path(env)
    exe = "jarvisd.exe" if sys.platform == "win32" else "jarvisd"
    for profile in ("debug", "release"):
        p = REPO / "services" / "jarvisd" / "target" / profile / exe
        if p.exists():
            return p
    pytest.skip("jarvisd binary not built (run cargo build in services/jarvisd)")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
async def bus_addr():
    addr = f"127.0.0.1:{free_port()}"
    proc = subprocess.Popen(
        [str(jarvisd_bin()), "--bus", addr, "--health-period", "0.2"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Wait for the listener to come up.
    for _ in range(100):
        try:
            _, w = await asyncio.open_connection(*addr.rsplit(":", 1))
            w.close()
            break
        except OSError:
            await asyncio.sleep(0.05)
    else:
        proc.kill()
        pytest.fail("jarvisd did not start")
    yield addr
    proc.kill()
    proc.wait(timeout=10)


async def test_roundtrip_and_prefix(bus_addr):
    sub = await BusClient.connect(bus_addr, src="t-sub")
    await sub.subscribe(["audio.*"])
    await asyncio.sleep(0.05)

    pub = await BusClient.connect(bus_addr, src="t-pub")
    body = to_body(AudioWake(model="hey_jarvis", score=0.93, threshold=0.5))
    await pub.publish("audio.wake", body, conf=0.93)

    frame = await asyncio.wait_for(sub.next_frame(), timeout=2)
    assert frame["topic"] == "audio.wake"
    assert frame["src"] == "t-pub"
    wake = from_body(AudioWake, frame["body"])
    assert wake.model == "hey_jarvis"
    assert abs(wake.score - 0.93) < 1e-9
    await sub.close()
    await pub.close()


async def test_the_publishers_confidence_reaches_the_subscriber_verbatim(bus_addr):
    """Invariant 4 — "every producer publishes confidence" — is implemented
    for the whole of Python by one line in `BusClient.publish`, and nothing
    held it: the round-trip above publishes `conf=0.93` and never looks at
    what arrived, so `"conf": 1.0` passed every suite in the repo. Found by
    tools/mutate.py the first time the gate could really reach this file
    (B58); a consumer that must "handle low-confidence input" has to be given
    it first.
    """
    sub = await BusClient.connect(bus_addr, src="t-conf-sub")
    await sub.subscribe(["audio.*"])
    await asyncio.sleep(0.05)

    pub = await BusClient.connect(bus_addr, src="t-conf-pub")
    body = to_body(AudioWake(model="hey_jarvis", score=0.31, threshold=0.5))
    await pub.publish("audio.wake", body, conf=0.31)

    frame = await asyncio.wait_for(sub.next_frame(), timeout=2)
    assert frame["conf"] == pytest.approx(0.31)
    await sub.close()
    await pub.close()


async def test_each_publish_from_one_client_gets_the_next_seq(bus_addr):
    """`seq` is the envelope's only ordering handle — every consumer that
    notices a dropped or reordered frame does it with this number, and a
    client that published the same one forever would be invisible to all of
    them. Two publishes, two consecutive numbers, in the order they were sent.
    """
    sub = await BusClient.connect(bus_addr, src="t-seq-sub")
    await sub.subscribe(["audio.*"])
    await asyncio.sleep(0.05)

    pub = await BusClient.connect(bus_addr, src="t-seq-pub")
    body = to_body(AudioWake(model="hey_jarvis", score=0.9, threshold=0.5))
    first = await pub.publish("audio.wake", body)
    second = await pub.publish("audio.wake", body)
    assert second == first + 1, "publish() returned the same seq twice"

    got = [
        (await asyncio.wait_for(sub.next_frame(), timeout=2))["seq"] for _ in range(2)
    ]
    assert got == [first, second]
    await sub.close()
    await pub.close()


async def test_broker_rejects_invalid_envelope(bus_addr):
    c = await BusClient.connect(bus_addr, src="t-bad")
    await c.publish_env({"topic": "audio.wake"})  # missing everything else
    with pytest.raises(BusError):
        await asyncio.wait_for(c.next_frame(), timeout=2)
    await c.close()


async def test_health_heartbeat_arrives(bus_addr):
    c = await BusClient.connect(bus_addr, src="t-health")
    await c.subscribe(["sys.health"])
    frame = await asyncio.wait_for(c.next_frame(), timeout=3)
    assert frame["topic"] == "sys.health"
    assert frame["body"]["service"] == "jarvisd"
    await c.close()


def test_to_body_wire_rules():
    # Optional-and-absent omitted; required fields present.
    b = to_body(AudioWake(model="m", score=0.5, threshold=0.4))
    assert b == {"model": "m", "score": 0.5, "threshold": 0.4}


# --- the rest of the envelope, and the transport under it (PLAN B59) ---------
#
# B58 gave the gate its first real reach into this file and the first two
# mutations it graded survived (`seq`, `conf`). The mutations below were run
# too, one per claim, and five of six survived: only `src` was held. This
# file is imported by every Python service on the bus, so a silent survivor
# here is wrong in eight places at once.


async def test_the_envelope_ts_is_stamped_from_this_processs_monotonic_clock(bus_addr):
    """`ts` is CLOCK_MONOTONIC seconds (schemas/README.md), and it is what
    every latency number in this repo is subtracted from — `jv tap --latency`,
    HeardState's anchor, HealthState's expiry. The broker validates it as a
    NUMBER and nothing more, so `"ts": 0.0` and a wall-clock `time.time()`
    both routed fine and passed every suite. Bracketing the publish is the
    strongest claim available from outside: the stamp is taken during the
    call, on this clock.
    """
    sub = await BusClient.connect(bus_addr, src="t-ts-sub")
    await sub.subscribe(["audio.*"])
    await asyncio.sleep(0.05)

    pub = await BusClient.connect(bus_addr, src="t-ts-pub")
    body = to_body(AudioWake(model="hey_jarvis", score=0.9, threshold=0.5))
    before = time.monotonic()
    await pub.publish("audio.wake", body)
    after = time.monotonic()

    frame = await asyncio.wait_for(sub.next_frame(), timeout=2)
    assert before <= frame["ts"] <= after, (
        f"ts {frame['ts']} is not a monotonic reading taken during the publish "
        f"({before} .. {after})"
    )
    await sub.close()
    await pub.close()


async def test_the_envelope_version_is_the_callers_and_not_a_constant(bus_addr):
    """`v` is how a schema migration begins: a producer bumps it and
    consumers that only understand the old one hedge or drop (HealthState
    already refuses a wrong `v`). The broker only checks `v >= 1`, so a
    client that pinned every frame at 1 would make that migration
    impossible and break nothing today.
    """
    sub = await BusClient.connect(bus_addr, src="t-v-sub")
    await sub.subscribe(["audio.*"])
    await asyncio.sleep(0.05)

    pub = await BusClient.connect(bus_addr, src="t-v-pub")
    body = to_body(AudioWake(model="hey_jarvis", score=0.9, threshold=0.5))
    await pub.publish("audio.wake", body, v=2)

    frame = await asyncio.wait_for(sub.next_frame(), timeout=2)
    assert frame["v"] == 2
    await sub.close()
    await pub.close()


async def test_a_pong_does_not_look_like_the_end_of_the_stream(bus_addr):
    """`next_frame` skips pongs. Nothing has ever sent one: the Python
    client has no `ping()`, so the branch was dead code as far as this suite
    knew, and a client that returned None on a pong would report the bus
    GONE — LinkPlate's blind state, every consumer's reconnect — the moment
    anything started pinging. The first half of this test is the control
    that a pong is a real thing this broker really sends; the second half is
    the claim.
    """
    ctl = await BusClient.connect(bus_addr, src="t-pong-ctl")
    await ctl._send({"op": "ping"})
    assert (await asyncio.wait_for(ctl.next_event(), timeout=2))["op"] == "pong"
    await ctl.close()

    sub = await BusClient.connect(bus_addr, src="t-pong-sub")
    await sub.subscribe(["audio.*"])
    await sub._send({"op": "ping"})
    await asyncio.sleep(0.05)  # the pong is queued ahead of the frame

    pub = await BusClient.connect(bus_addr, src="t-pong-pub")
    body = to_body(AudioWake(model="hey_jarvis", score=0.9, threshold=0.5))
    await pub.publish("audio.wake", body)

    frame = await asyncio.wait_for(sub.next_frame(), timeout=2)
    assert frame is not None, "a pong was read as EOF"
    assert frame["topic"] == "audio.wake"
    await sub.close()
    await pub.close()


async def test_a_length_prefix_over_max_frame_is_refused_before_the_body():
    """The u32 length prefix is attacker- and corruption-controlled: it is
    read before anything is known about what follows, and `readexactly(n)`
    on a bad `n` allocates that many bytes. The guard must fire on the
    PREFIX ALONE — so this feeds the prefix and then EOF, and nothing else.
    No broker: jarvisd caps its own writes at the same number, so the only
    way to reach this branch is to be the thing on the other end.
    """
    reader = asyncio.StreamReader()
    reader.feed_data((MAX_FRAME + 1).to_bytes(4, "big"))
    reader.feed_eof()
    c = BusClient(reader, None, "t-max")
    with pytest.raises(BusError):
        await c.next_event()


def test_the_clients_frame_cap_is_the_brokers():
    """jarvisd declares the same cap in services/jarvisd/src/proto.rs and
    enforces it on both directions. If the two ever disagree, the smaller
    one silently becomes the real limit and the larger one's error message
    is a lie about why the connection died. This test READS the Rust source
    — it does not run it (invariant 1: no service imports another).
    """
    proto = (REPO / "services" / "jarvisd" / "src" / "proto.rs").read_text()
    decl = "pub const MAX_FRAME: u32 = 16 * 1024 * 1024;"
    assert decl in proto, (
        "jarvisd's MAX_FRAME declaration moved or changed; the Python "
        "client's cap is pinned to it and must move with it"
    )
    assert MAX_FRAME == 16 * 1024 * 1024


def test_jarvis_bus_in_the_environment_chooses_the_address(monkeypatch):
    """`default_addr()` is what every service uses when nothing passes an
    address, so `JARVIS_BUS` is the only handle the harness and the replay
    rig have for pointing a whole service at a test broker. Nothing held
    it: every test in this file passes an address explicitly.
    """
    if sys.platform == "win32":  # pragma: no cover — JarvisOS is NixOS
        pytest.skip("the unset branch differs on Windows")
    monkeypatch.setenv("JARVIS_BUS", "127.0.0.1:7999")
    assert default_addr() == "127.0.0.1:7999"
    monkeypatch.setenv("JARVIS_BUS", "")  # set-but-empty is not an address
    assert default_addr() == DEFAULT_UNIX
    monkeypatch.delenv("JARVIS_BUS")
    assert default_addr() == DEFAULT_UNIX
