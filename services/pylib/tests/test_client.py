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
