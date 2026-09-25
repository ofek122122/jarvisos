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
from jv_guard.scan import MockScanner, ScanHit, ScanReport, decide, sha256_file
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
              hits=[ScanHit("clamav", "Eicar-Test")])])
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
    assert report.hits
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


async def test_guard_publishes_suspicious_for_a_packed_binary(bus_addr, tmp_path):
    """The middle rung, end to end and on a real bus: a signature engine
    that recognises nothing plus a shape engine that does not like what
    it sees is `suspicious` — the verdict jv-compat refuses with an
    override message and the HUD draws in `warn`."""
    from jv_guard.heuristics import PEHeuristicScanner
    from test_pe_heuristics import TEXT, build_pe, packed

    f = tmp_path / "packed.exe"
    f.write_bytes(build_pe([(".text", TEXT, packed(8192), None)]))

    watcher = await BusClient.connect(bus_addr, src="t")
    await watcher.subscribe(["guard.verdict"])
    svc_bus = await BusClient.connect(bus_addr, src="jv-guard")
    svc = GuardService(svc_bus, [MockScanner(), PEHeuristicScanner()])
    task = asyncio.create_task(svc.run())
    await asyncio.sleep(0.2)

    await watcher.publish(
        "compat.install",
        {"event": "fingerprinted", "app": "packed", "sha256": sha256_file(f),
         "path": str(f)},
    )
    frame = await asyncio.wait_for(watcher.next_frame(), timeout=5)
    body = frame["body"]
    assert body["verdict"] == "suspicious"
    assert "packed" in body["reasons"][0]
    assert body["scanned_by"] == ["mock", "pe-shape"]

    task.cancel()
    await svc_bus.close()
    await watcher.close()


async def test_guard_stays_silent_when_only_the_shape_engine_ran(bus_addr, tmp_path):
    """A ClamAV outage must not become a verdict just because an advisory
    engine had something to say. This is the fail-closed path the new
    rung could most easily have deleted."""
    from jv_guard.heuristics import PEHeuristicScanner
    from test_pe_heuristics import TEXT, build_pe, packed

    f = tmp_path / "packed.exe"
    f.write_bytes(build_pe([(".text", TEXT, packed(8192), None)]))

    watcher = await BusClient.connect(bus_addr, src="t")
    await watcher.subscribe(["guard.verdict", "sys.health"])
    svc_bus = await BusClient.connect(bus_addr, src="jv-guard")
    svc = GuardService(svc_bus, [MockScanner(broken=True), PEHeuristicScanner()])
    task = asyncio.create_task(svc.run())
    await asyncio.sleep(0.2)

    await watcher.publish(
        "compat.install",
        {"event": "fingerprinted", "app": "packed", "sha256": sha256_file(f),
         "path": str(f)},
    )
    saw_degraded = False
    for _ in range(20):
        frame = await asyncio.wait_for(watcher.next_frame(), timeout=5)
        assert frame["topic"] != "guard.verdict", "shape alone is not a verdict"
        if frame["topic"] == "sys.health" and frame["body"].get("state") == "degraded":
            # the health note names the outage precisely: an advisory
            # engine DID run, and that is not the same as being screened
            assert "no signature scan engine available" in frame["body"]["notes"]
            assert "pe-shape" in frame["body"]["notes"]
            saw_degraded = True
            break
    assert saw_degraded

    task.cancel()
    await svc_bus.close()
    await watcher.close()


# --------------------------------------- the period an off-schedule beat owns

async def next_health(watcher, timeout=5.0, state=None):
    """The next sys.health frame (of `state`, if given), and the moment it
    arrived. Skipping to a state rather than asserting the next one is it
    is deliberate: what this section is about is the beat AFTER the fault,
    and a test that could not reach the fault would say nothing about it."""

    async def inner():
        while True:
            frame = await watcher.next_frame()
            assert frame is not None
            if frame["topic"] == "sys.health":
                if state is None or frame["body"].get("state") == state:
                    return frame, asyncio.get_running_loop().time()

    return await asyncio.wait_for(inner(), timeout)


async def test_the_degraded_beat_owns_the_period_it_lands_in(bus_addr, tmp_path):
    """jv-guard beats `degraded` the instant a scan finds no engine, which
    is right — and then left its period timer alone, so the `ok` that
    erases that report went out with whatever was left on the old timer.
    Land the fault three quarters of the way through a period and the
    report had a quarter of one to live; land it at the boundary and it
    had none. `bus.latest()` keeps one frame per publisher, so that is an
    outage the HUD and `jv health --check` can both miss entirely.

    The beat is the schedule now: the next one is a full period after the
    fault, not after the beat the fault interrupted. Asserted as a gap and
    not as a silence, because a heartbeat that stopped would pass that.
    """
    f = tmp_path / "app.exe"
    f.write_bytes(b"MZ payload")
    period = 1.2
    watcher = await BusClient.connect(bus_addr, src="t")
    await watcher.subscribe(["sys.health"])
    svc_bus = await BusClient.connect(bus_addr, src="jv-guard")
    svc = GuardService(svc_bus, [MockScanner(broken=True)], health_period_s=period)
    task = asyncio.create_task(svc.run())

    first, at_first = await next_health(watcher)
    assert first["body"]["period_s"] == period  # the body declares what is enforced
    assert first["body"]["state"] == "ok"

    # Three quarters of the way through the period the startup beat began.
    await asyncio.sleep(period * 0.75)
    await watcher.publish(
        "compat.install",
        {"event": "fingerprinted", "app": "app", "sha256": sha256_file(f), "path": str(f)},
    )
    fault, at_fault = await next_health(watcher, state="degraded")
    # A fault that arrived after the beat it was supposed to interrupt would
    # make the rest of this test measure nothing and still pass.
    assert at_fault - at_first < period, "the scan outran the period it was to land in"

    nxt, at_next = await next_health(watcher, timeout=period * 3)
    assert nxt["body"]["state"] == "ok"  # it does come back, this is not a latch
    assert at_next - at_fault >= period * 0.6, (
        f"the beat after the fault came {at_next - at_fault:.3f}s later, "
        f"on the schedule the fault should have taken over"
    )

    task.cancel()
    await svc_bus.close()
    await watcher.close()
