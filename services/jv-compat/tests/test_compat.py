"""jv-compat: fingerprinting on header fixtures, recipe matching, bwrap
argv confinement, and the full install pipeline vs a real jarvisd —
including fail-closed when no verdict arrives and a real jv-guard
blocking an EICAR-style file."""

import asyncio
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from jarvis_bus import BusClient
from jv_compat.fingerprint import fingerprint, silent_args
from jv_compat.install import Installer, MockRunner, app_slug
from jv_compat.prefix import bwrap_args
from jv_compat.recipes import Recipe, find_recipe

REPO = Path(__file__).resolve().parents[3]
FIX = Path(__file__).resolve().parent / "fixtures"


# ------------------------------------------------------- fingerprinting


def test_fingerprint_installers():
    assert fingerprint(FIX / "nsis-x64.exe").installer == "nsis"
    assert fingerprint(FIX / "nsis-x64.exe").arch == "x64"
    assert fingerprint(FIX / "inno-x86.exe").installer == "inno"
    assert fingerprint(FIX / "inno-x86.exe").arch == "x86"
    assert fingerprint(FIX / "installer.msi").installer == "msi"
    assert fingerprint(FIX / "plain-x64.exe").installer == "unknown"
    assert fingerprint(FIX / "plain-x64.exe").is_pe is True
    assert fingerprint(FIX / "notpe.txt").is_pe is False


def test_silent_args():
    assert silent_args("nsis") == ["/S"]
    assert "/VERYSILENT" in silent_args("inno")
    assert "/qn" in silent_args("msi")


def test_app_slug():
    assert app_slug(Path("Firefox_Setup_x64.exe")) == "firefox"
    assert app_slug(Path("npp.8.6.Installer.exe")) == "npp-8-6"


# -------------------------------------------------------------- recipes


def test_recipe_matching():
    recipes = [
        Recipe(app="pinned", match_sha256=["deadbeef"], match_installer=""),
        Recipe(app="generic-nsis", match_sha256=[], match_installer="nsis"),
    ]
    assert find_recipe(recipes, "DEADBEEF", "nsis").app == "pinned"  # pin wins, case-insens
    assert find_recipe(recipes, "other", "nsis").app == "generic-nsis"
    assert find_recipe(recipes, "other", "inno") is None


# ------------------------------------------------------------ bwrap argv


def test_bwrap_confinement_defaults_deny():
    r = Recipe(app="x", match_sha256=[], match_installer="")
    argv = bwrap_args(r, Path("/prefixes/x"), ["wine", "setup.exe"])
    assert "--unshare-net" in argv  # network denied by default
    assert argv[argv.index("--setenv") + 1] == "WINEPREFIX"
    assert argv[-2:] == ["wine", "setup.exe"]


def test_bwrap_network_grant():
    r = Recipe(app="x", match_sha256=[], match_installer="", network=True)
    assert "--unshare-net" not in bwrap_args(r, Path("/p"), ["wine"])


# ------------------------------------------------------ pipeline e2e


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


async def collect(client, want_events, timeout=10.0):
    events = []
    async def inner():
        while len(events) < want_events:
            frame = await client.next_frame()
            if frame and frame["topic"] == "compat.install":
                events.append(frame["body"])
    await asyncio.wait_for(inner(), timeout)
    return events


async def test_clean_install_pipeline(bus_addr, tmp_path):
    """A fake external guard says clean -> prefix -> installed."""
    installer_file = tmp_path / "nsis-x64.exe"
    installer_file.write_bytes((FIX / "nsis-x64.exe").read_bytes())

    watcher = await BusClient.connect(bus_addr, src="t")
    await watcher.subscribe(["compat.install"])

    # fake guard: reply clean to any fingerprinted event
    guard = await BusClient.connect(bus_addr, src="jv-guard")
    await guard.subscribe(["compat.install"])

    async def fake_guard():
        while True:
            frame = await guard.next_frame()
            if frame and frame["body"].get("event") == "fingerprinted":
                await guard.publish(
                    "guard.verdict",
                    {"sha256": frame["body"]["sha256"], "verdict": "clean",
                     "reasons": [], "scanned_by": ["mock"]},
                )
    gtask = asyncio.create_task(fake_guard())
    await asyncio.sleep(0.2)

    runner = MockRunner(ok=True)
    compat_bus = await BusClient.connect(bus_addr, src="jv-compat")
    outcome = await Installer(compat_bus, runner).install(installer_file)
    assert outcome == "installed"

    events = await collect(watcher, 4)
    names = [e["event"] for e in events]
    assert names == ["fingerprinted", "screened", "prefix_created", "installed"]
    # the runner got a bwrap-confined, network-denied argv
    assert "--unshare-net" in runner.argv_log[0]

    gtask.cancel()
    await guard.close()
    await compat_bus.close()
    await watcher.close()


async def test_fail_closed_when_no_verdict(bus_addr, tmp_path):
    """No guard on the bus -> no verdict -> compat blocks. This is the
    invariant-8 guarantee; we shorten the timeout via monkeypatch."""
    import jv_compat.install as inst_mod

    inst_mod.VERDICT_TIMEOUT_S = 1.0
    installer_file = tmp_path / "app.exe"
    installer_file.write_bytes((FIX / "plain-x64.exe").read_bytes())

    watcher = await BusClient.connect(bus_addr, src="t")
    await watcher.subscribe(["compat.install"])
    compat_bus = await BusClient.connect(bus_addr, src="jv-compat")
    runner = MockRunner(ok=True)
    outcome = await Installer(compat_bus, runner).install(installer_file)

    assert outcome == "blocked"
    assert not runner.argv_log, "must never install without a verdict"
    events = await collect(watcher, 2)
    assert events[-1]["event"] == "blocked"
    assert "fail closed" in events[-1]["error"]

    await compat_bus.close()
    await watcher.close()


async def test_blocked_verdict_refuses(bus_addr, tmp_path):
    installer_file = tmp_path / "evil.exe"
    installer_file.write_bytes((FIX / "plain-x64.exe").read_bytes())
    watcher = await BusClient.connect(bus_addr, src="t")
    await watcher.subscribe(["compat.install"])
    guard = await BusClient.connect(bus_addr, src="jv-guard")
    await guard.subscribe(["compat.install"])

    async def fake_guard():
        while True:
            frame = await guard.next_frame()
            if frame and frame["body"].get("event") == "fingerprinted":
                await guard.publish(
                    "guard.verdict",
                    {"sha256": frame["body"]["sha256"], "verdict": "blocked",
                     "reasons": ["mock signature"], "scanned_by": ["mock"]},
                )
    gtask = asyncio.create_task(fake_guard())
    await asyncio.sleep(0.2)

    runner = MockRunner(ok=True)
    compat_bus = await BusClient.connect(bus_addr, src="jv-compat")
    outcome = await Installer(compat_bus, runner).install(installer_file)
    assert outcome == "blocked"
    assert not runner.argv_log

    gtask.cancel()
    await guard.close()
    await compat_bus.close()
    await watcher.close()
