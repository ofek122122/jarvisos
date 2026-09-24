"""Integration tests for the Python bus client against a REAL jarvisd.

Requires the broker binary: cargo build in services/jarvisd first (CI
does; locally: cargo build). Set JARVISD_BIN to override the path.
"""

import asyncio
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from jarvis_bus import BusClient, BusError
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
