"""Record/replay roundtrip against a real jarvisd: what goes in comes
back out, with timing preserved (scaled) and the session header intact."""

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

HARNESS = Path(__file__).resolve().parents[1]
REPO = HARNESS.parent
sys.path.insert(0, str(HARNESS))
sys.path.insert(0, str(REPO / "services" / "pylib"))

import record  # noqa: E402
import replay  # noqa: E402
from jarvis_bus import BusClient  # noqa: E402


def jarvisd_bin() -> Path:
    if env := os.environ.get("JARVISD_BIN"):
        return Path(env)
    exe = "jarvisd.exe" if sys.platform == "win32" else "jarvisd"
    for profile in ("debug", "release"):
        p = REPO / "services" / "jarvisd" / "target" / profile / exe
        if p.exists():
            return p
    pytest.skip("jarvisd binary not built")


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


async def test_record_then_replay_roundtrip(bus_addr, tmp_path):
    session = tmp_path / "session.jsonl"

    # --- record 3 frames with real gaps
    with session.open("w", encoding="utf-8", newline="\n") as fh:
        rec_task = asyncio.create_task(
            record.record(fh, ["audio.*"], bus_addr, duration_s=5.0, frame_limit=3)
        )
        await asyncio.sleep(0.3)  # let the subscription land
        pub = await BusClient.connect(bus_addr, src="t-orig")
        for i in range(3):
            await pub.publish("audio.vad", {"event": "speech_start"}, conf=1.0)
            await asyncio.sleep(0.25)
        assert await rec_task == 3
        await pub.close()

    lines = [json.loads(x) for x in session.read_text().splitlines()]
    header, frames = lines[0], lines[1:]
    assert set(header) == {"boot_id", "wall_time_utc", "monotonic_now"}
    assert len(frames) == 3
    assert all(f["topic"] == "audio.vad" and f["src"] == "t-orig" for f in frames)
    # ts deltas captured the real ~0.25s publish gaps
    deltas = [frames[i + 1]["ts"] - frames[i]["ts"] for i in range(2)]
    assert all(0.1 < d < 1.0 for d in deltas), deltas

    # --- replay at 5x and confirm arrival + scaled timing
    sub = await BusClient.connect(bus_addr, src="t-sub")
    await sub.subscribe(["audio.*"])
    await asyncio.sleep(0.3)

    t0 = time.monotonic()
    sent = await replay.replay(session, bus_addr, speed=5.0)
    assert sent == 3

    got = []
    while len(got) < 3:
        frame = await asyncio.wait_for(sub.next_frame(), timeout=5)
        got.append(frame)
    elapsed = time.monotonic() - t0

    assert [g["body"] for g in got] == [f["body"] for f in frames]
    assert all(g["src"] == "t-orig" for g in got)  # replay preserves src
    # ~0.5s of gaps replayed at 5x ≈ 0.1s; generous ceiling for CI jitter
    assert elapsed < 2.0
    await sub.close()


async def test_replay_rejects_headerless_file(bus_addr, tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"topic": "audio.vad"}\n')
    with pytest.raises(ValueError, match="session header"):
        await replay.replay(bad, bus_addr)
