"""The bridge against a REAL jarvisd, as a real subprocess.

The unit tests prove the bridge's logic; this proves the pipe. It runs the
actual broker, publishes actual frames from a second client, and reads the
bridge's stdout the way Quickshell's SplitParser does: one line, one
JSON.parse. If this passes, everything between a service's `publish` and
QML's `onRead` has been exercised except QML itself.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from jarvis_bus import BusClient

REPO = Path(__file__).resolve().parents[3]


def jarvisd_bin() -> Path:
    if env := os.environ.get("JARVISD_BIN"):
        return Path(env)
    for profile in ("debug", "release"):
        p = REPO / "services" / "jarvisd" / "target" / profile / "jarvisd"
        if p.exists():
            return p
    pytest.skip("jarvisd binary not built (set JARVISD_BIN)")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def start_broker(addr):
    proc = subprocess.Popen(
        [str(jarvisd_bin()), "--bus", addr, "--health-period", "0.2"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    host, port = addr.rsplit(":", 1)
    for _ in range(200):  # ~10 s; the broker binds in milliseconds
        try:
            _, w = await asyncio.open_connection(host, int(port))
            w.close()
            return proc
        except OSError:
            await asyncio.sleep(0.05)
    proc.kill()
    pytest.fail("jarvisd did not start")


@pytest.fixture
async def broker():
    """A real jarvisd on a free port. Yields (addr, restart) so a test can
    kill the bus under a running bridge and bring it back on the same
    address — which is what a `systemctl restart jarvisd` looks like."""
    addr = f"127.0.0.1:{free_port()}"
    running = [await start_broker(addr)]

    async def restart():
        running[0].kill()
        running[0].wait(timeout=10)
        running[0] = await start_broker(addr)

    yield addr, restart
    running[0].kill()
    running[0].wait(timeout=10)


async def read_line(proc, timeout=10.0):
    line = await asyncio.wait_for(proc.stdout.readline(), timeout)
    assert line, "the bridge closed stdout"
    return json.loads(line)


async def start_bridge(addr, *topics):
    return await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "jv_hud_bridge.main",
        "--bus",
        addr,
        *[a for t in topics for a in ("--topic", t)],
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        cwd=str(REPO / "services" / "jv-hud-bridge"),
    )


async def test_a_published_frame_arrives_as_one_parseable_line(broker):
    bus_addr, _ = broker
    bridge = await start_bridge(bus_addr, "speech.state")
    try:
        assert await read_line(bridge) == {"t": "link", "up": False, "err": "connecting"}
        assert await read_line(bridge) == {"t": "link", "up": True}

        voice = await BusClient.connect(bus_addr, src="jv-voice")
        try:
            await voice.publish("speech.state", {"state": "speaking", "say_id": "s1"})
            msg = await read_line(bridge)
        finally:
            await voice.close()

        assert msg["t"] == "frame"
        frame = msg["frame"]
        assert frame["topic"] == "speech.state"
        assert frame["body"] == {"state": "speaking", "say_id": "s1"}
        assert frame["src"] == "jv-voice"
        assert frame["conf"] == 1.0  # a state topic is always certain
        assert isinstance(frame["ts"], float) and isinstance(frame["seq"], int)
    finally:
        bridge.kill()
        await bridge.wait()


async def test_topics_outside_the_subscription_never_reach_the_hud(broker):
    bus_addr, _ = broker
    bridge = await start_bridge(bus_addr, "speech.state")
    try:
        await read_line(bridge)
        await read_line(bridge)
        pub = await BusClient.connect(bus_addr, src="jv-ears")
        try:
            await pub.publish("audio.vad", {"event": "speech_start"}, conf=0.9)
            await pub.publish("speech.state", {"state": "idle"})
            msg = await read_line(bridge)
        finally:
            await pub.close()
        # The vad frame was published first; the HUD must only see the one
        # it asked for.
        assert msg["frame"]["topic"] == "speech.state"
    finally:
        bridge.kill()
        await bridge.wait()


async def test_the_broker_going_away_is_reported_down_and_then_recovered(broker):
    """Kill the bus under a running bridge: the HUD is told the link died,
    and gets told again when it comes back — never left holding stale state."""
    bus_addr, restart = broker
    bridge = await start_bridge(bus_addr, "speech.state")
    try:
        await read_line(bridge)
        assert (await read_line(bridge))["up"] is True

        await restart()
        down = await read_line(bridge)
        assert down["t"] == "link" and down["up"] is False and down["err"]

        # Retries are backed off, so give it room; every line until the
        # link returns must still be an honest "down".
        for _ in range(40):
            msg = await read_line(bridge, timeout=15.0)
            if msg["up"]:
                break
            assert msg["t"] == "link" and msg["up"] is False
        else:
            pytest.fail("the bridge never recovered the link")

        voice = await BusClient.connect(bus_addr, src="jv-voice")
        try:
            await voice.publish("speech.state", {"state": "idle"})
            frame = await read_line(bridge)
        finally:
            await voice.close()
        assert frame["frame"]["body"] == {"state": "idle"}
    finally:
        bridge.kill()
        await bridge.wait()
