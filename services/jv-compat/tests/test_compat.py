"""jv-compat: fingerprinting on header fixtures, recipe matching, bwrap
argv confinement, and the full install pipeline vs a real jarvisd —
including fail-closed when no verdict arrives and a real jv-guard
blocking an EICAR-style file."""

import asyncio
import os
import re
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from jarvis_bus import BusClient
from jv_compat.fingerprint import fingerprint, silent_args
from jv_compat.install import Installer, MockRunner, app_slug
from jv_compat.prefix import SANDBOX_PREFIX, bwrap_args, sandbox_installer_path
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
    """The argv's shape. What the argv MEANS is tests/test_sandbox.py,
    which runs it — these two tests passed against a confinement that
    could not start a process (PLAN B63)."""
    r = Recipe(app="x", match_sha256=[], match_installer="")
    argv = bwrap_args(r, Path("/prefixes/x"), ["wine", "setup.exe"])
    assert "--unshare-net" in argv  # network denied by default
    i = argv.index("WINEPREFIX")
    assert argv[i - 1] == "--setenv" and argv[i + 1] == str(SANDBOX_PREFIX)
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
    argv = runner.argv_log[0]
    assert "--unshare-net" in argv
    # ...and the two halves agree about where the installer is: the inner
    # command names the SANDBOX path, and the host path appears exactly once
    # in the whole argv — as the read-only bind that puts the file there.
    # These are built in different modules and were free to disagree.
    inside = str(sandbox_installer_path(installer_file))
    assert inside in argv
    assert argv.count(str(installer_file)) == 1
    assert argv[argv.index(str(installer_file)) - 1] == "--ro-bind"
    assert argv[argv.index(str(installer_file)) + 1] == inside

    gtask.cancel()
    await guard.close()
    await compat_bus.close()
    await watcher.close()


async def test_fail_closed_when_no_verdict(bus_addr, tmp_path, monkeypatch):
    """No guard on the bus -> no verdict -> compat blocks. This is the
    invariant-8 guarantee; we shorten the timeout so the test is not the
    real wait.

    The shortening is a monkeypatch and not an assignment: the module global
    was rewritten in place here and never put back, so every test after this
    one silently ran with a one-second screening window and the suite's
    result depended on its own order (PLAN B50)."""
    import jv_compat.install as inst_mod

    monkeypatch.setattr(inst_mod, "VERDICT_TIMEOUT_S", 1.0)
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


# ------------------------------------- B50: the wait, not just its effect


def test_the_wait_for_a_verdict_outlasts_the_scan_it_is_waiting_for():
    """`VERDICT_TIMEOUT_S` had no claim on it anywhere.

    The one test that names it REPLACES it (a screening window of one second,
    so fail-closed does not cost the suite a minute), so the shipped number
    was never exercised by anything: mutated 60.0 -> 300.0 against this
    suite, it survived (PLAN B50).

    Asking what the number has to be true FOR found a real disagreement
    between two services that never read each other. jv-compat stops
    listening for `guard.verdict` after this long and then fails closed
    (invariant 8, approved 2026-08-22); jv-guard's `ClamAVScanner` gives
    clamscan 120 s before it gives up. At the shipped 60 s, an installer
    whose scan ran 70 s was refused with "screening unavailable — refusing to
    install" while the only authoritative engine on this machine was still
    scanning it and about to publish `clean` onto a topic nobody was reading.
    That is not the fail-closed guarantee working; it is a clean binary
    refused for a reason that was not true.

    Read out of jv-guard's source rather than imported: services never import
    each other (invariant 1), and this is the same shape
    `RECONNECT_CADENCES` uses in tools/tests/test_gen_theme_qml.py for the
    two cadences `LinkState.qml` depends on.
    """
    import jv_compat.install as inst_mod

    scan_py = (REPO / "services" / "jv-guard" / "jv_guard" / "scan.py").read_text("utf-8")
    m = re.search(
        r"\[\"clamscan\".*?timeout=(\d+)", scan_py, re.S
    )
    assert m, (
        "cannot find clamscan's timeout in jv-guard/scan.py — if it moved or "
        "was renamed, this relation is unchecked, which is how it drifted"
    )
    scan_budget = float(m.group(1))

    assert inst_mod.VERDICT_TIMEOUT_S > scan_budget, (
        f"jv-compat gives up after {inst_mod.VERDICT_TIMEOUT_S}s but jv-guard "
        f"lets a scan run {scan_budget}s — a verdict published in between is "
        "thrown away and a clean installer is refused as unscreened"
    )
    # And the wait is not unbounded: past a few minutes the install has
    # stopped looking like a machine working and started looking like one
    # that hung, with nothing on `compat.install` since `fingerprinted`.
    assert inst_mod.VERDICT_TIMEOUT_S <= 300.0
