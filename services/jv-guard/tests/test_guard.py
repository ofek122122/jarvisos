"""jv-guard: verdict logic (incl. EICAR + fail-closed) and the service
against a real jarvisd with a mock scanner."""

import asyncio
import base64
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from jarvis_bus import BusClient
from jv_guard.scan import MockScanner, ScanReport, decide, sha256_file
from jv_guard.service import GuardService

REPO = Path(__file__).resolve().parents[3]

# The standard EICAR test string, assembled at runtime so this file
# itself never trips a scanner.
EICAR = (
    base64.b64decode(
        "WDVPIVAlQEFQWzRcUFpYNTQoUF4pN0NDKTd9JEVJQ0FSLVNU"
        "QU5EQVJELUFOVElWSVJVUy1URVNULUZJTEUhJEgrSCo="
    )
).decode()


def test_signature_hit_blocks():
    v = decide("abc", [ScanReport("clamav", ran=True,
              hit=__import__("jv_guard.scan", fromlist=["ScanHit"]).ScanHit("clamav", "Eicar-Test"))])
    assert v.verdict == "blocked"
    assert "Eicar-Test" in v.reasons[0]


def test_all_clean_is_clean():
    v = decide("abc", [ScanReport("clamav", ran=True)])
    assert v.verdict == "clean"
    assert v.scanned_by == ["clamav"]


def test_no_engine_ran_is_no_verdict():
    """Fail-closed hinges on this: no engine -> None -> compat publishes
    nothing -> compat times out and refuses."""
    assert decide("abc", [ScanReport("clamav", ran=False)]) is None
    assert decide("abc", []) is None


def test_eicar_file_flagged_by_mock(tmp_path):
    f = tmp_path / "eicar.com"
    f.write_text(EICAR)
    scanner = MockScanner(infected={"eicar.com": "Eicar-Test-Signature"})
    report = scanner.scan(f)
    assert report.hit is not None
    v = decide(sha256_file(f), [report])
    assert v.verdict == "blocked"


# --------------------------------------------------------- service e2e


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
    addr = f"127.0.0.1:0"
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


async def test_guard_publishes_blocked_for_infected(bus_addr, tmp_path):
    f = tmp_path / "evil.exe"
    f.write_bytes(b"MZ payload")
    watcher = await BusClient.connect(bus_addr, src="t")
    await watcher.subscribe(["guard.verdict"])
    svc_bus = await BusClient.connect(bus_addr, src="jv-guard")
    svc = GuardService(svc_bus, [MockScanner(infected={"evil.exe": "Win.Test"})])
    task = asyncio.create_task(svc.run())
    await asyncio.sleep(0.2)

    await watcher.publish(
        "compat.install",
        {"event": "fingerprinted", "app": "evil", "sha256": sha256_file(f), "path": str(f)},
    )
    frame = await asyncio.wait_for(watcher.next_frame(), timeout=5)
    assert frame["body"]["verdict"] == "blocked"
    assert "Win.Test" in frame["body"]["reasons"][0]

    task.cancel()
    await svc_bus.close()
    await watcher.close()


async def test_guard_silent_when_no_engine(bus_addr, tmp_path):
    """Broken scanner -> NO guard.verdict at all (fail-closed contract)."""
    f = tmp_path / "app.exe"
    f.write_bytes(b"MZ payload")
    watcher = await BusClient.connect(bus_addr, src="t")
    await watcher.subscribe(["guard.verdict", "sys.health"])
    svc_bus = await BusClient.connect(bus_addr, src="jv-guard")
    svc = GuardService(svc_bus, [MockScanner(broken=True)])
    task = asyncio.create_task(svc.run())
    await asyncio.sleep(0.2)

    await watcher.publish(
        "compat.install",
        {"event": "fingerprinted", "app": "app", "sha256": sha256_file(f), "path": str(f)},
    )
    # a degraded health note appears; a verdict never does
    saw_degraded = False
    for _ in range(20):
        frame = await asyncio.wait_for(watcher.next_frame(), timeout=5)
        assert frame["topic"] != "guard.verdict", "must not emit a verdict with no engine"
        if frame["topic"] == "sys.health" and frame["body"].get("state") == "degraded":
            saw_degraded = True
            break
    assert saw_degraded

    task.cancel()
    await svc_bus.close()
    await watcher.close()
