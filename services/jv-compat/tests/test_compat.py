"""jv-compat: fingerprinting on header fixtures, recipe matching, bwrap
argv confinement, and the full install pipeline vs a real jarvisd —
including fail-closed when no verdict arrives and a real jv-guard
blocking an EICAR-style file."""

import asyncio
import hashlib
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
from jv_compat.prefix import (
    SANDBOX_PREFIX,
    bwrap_args,
    grant_problems,
    prefix_dir,
    sandbox_installer_path,
)
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


# ------------------------------- B65: can THIS machine honour the recipe?
#
# A grant is a fact about two things: a recipe (reviewed, in this repo) and a
# home directory (the user's, and not this repo's business). `--bind` resolves
# its source on the host, so a grant naming a folder that is not there aborts
# bwrap — which `tests/test_sandbox.py` executes. These tests are about the
# answer to that: the recipe is refused BEFORE any work, naming the path.


def _r(**kw) -> Recipe:
    kw.setdefault("app", "demo")
    kw.setdefault("match_sha256", [])
    kw.setdefault("match_installer", "")
    return Recipe(**kw)


@pytest.fixture
def home(tmp_path, monkeypatch) -> Path:
    """The user's home, somewhere this test owns. `prefixes_root()` hangs off
    `Path.home()` too, so this also keeps a prefix out of the real one."""
    h = tmp_path / "home" / "user"
    h.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.delenv("JARVIS_PREFIXES_DIR", raising=False)
    return h


def test_a_grant_the_machine_can_honour_is_not_a_problem(home):
    (home / "Documents" / "AppSaves").mkdir(parents=True)
    assert grant_problems(_r(home_paths=["Documents/AppSaves"])) == []
    assert grant_problems(_r()) == []  # no grants at all: nothing to check


def test_a_grant_naming_a_folder_this_machine_does_not_have_is_refused(home):
    """The whole point: the sentence names the ABSOLUTE path, because the
    recipe's `Documents/MyAppSaves` is not what the user has to look for,
    and it says what fixes it — jv-compat must not create it itself
    (invariant 3: only jv-act writes outside a service's own state dir,
    and this folder is the user's)."""
    (home / "Documents").mkdir()
    problems = grant_problems(_r(home_paths=["Documents/MyAppSaves"]))
    assert len(problems) == 1
    assert str(home / "Documents" / "MyAppSaves") in problems[0]
    assert "Documents/MyAppSaves" in problems[0]  # ...and the recipe's own words


def test_a_grant_naming_one_file_is_honoured_and_not_widened_to_its_folder(home):
    """The pre-flight deliberately says nothing about what KIND of thing a
    grant is: one file is a NARROWER grant than the folder around it, and
    bwrap binds either — so demanding a directory would refuse the more
    conservative of two recipes. `test_sandbox.py` runs the bwrap half of
    this same claim; without this line here, swapping the predicate for
    `is_dir()` changes nothing any test can see."""
    (home / "Documents").mkdir()
    (home / "Documents" / "settings.ini").write_text("theme=dark\n")
    assert grant_problems(_r(home_paths=["Documents/settings.ini"])) == []


def test_every_grant_the_machine_cannot_honour_is_named_not_just_the_first(home):
    """A recipe with three bad grants must not cost three installs to fix."""
    problems = grant_problems(
        _r(home_paths=["Documents/A", "..", "Music/B"])
    )
    assert len(problems) == 3
    assert str(home / "Documents" / "A") in problems[0]
    assert "grant" in problems[1]
    assert str(home / "Music" / "B") in problems[2]


def test_a_grant_that_leaves_the_private_home_is_a_problem_and_not_a_traceback(home):
    """`grant_dest` raises, and the raise happened inside `bwrap_args` —
    which the pipeline calls with no guard, so a malformed recipe left
    `jv-compat install` with a ValueError traceback and published no
    terminal frame at all. The same refusal is now an answer."""
    problems = grant_problems(_r(home_paths=["."]))
    assert len(problems) == 1 and "grant" in problems[0]


def test_a_grant_pointing_at_a_broken_symlink_is_absent_like_bwrap_reads_it(home):
    """`--bind` follows the link, so bwrap calls this missing. The check has
    to agree with the thing it is standing in front of, which is why the
    predicate is `exists()` (follows) and not `lstat` (does not)."""
    (home / "Documents").mkdir()
    (home / "Documents" / "AppSaves").symlink_to(home / "gone")
    problems = grant_problems(_r(home_paths=["Documents/AppSaves"]))
    assert len(problems) == 1
    assert str(home / "Documents" / "AppSaves") in problems[0]


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


async def test_a_recipe_this_machine_cannot_honour_is_refused_before_the_prefix(
    bus_addr, tmp_path, home
):
    """Screened clean, and still nothing runs: a grant naming a folder the
    user does not have is known before any work is done, so it is a REFUSAL
    (`blocked`, as fail-closed already is) and not a `failed` install that
    never started. Before this, bwrap's own message reached the user through
    `failed`, after the prefix had been built."""
    installer_file = tmp_path / "nsis-x64.exe"
    installer_file.write_bytes((FIX / "nsis-x64.exe").read_bytes())
    sha = hashlib.sha256(installer_file.read_bytes()).hexdigest()

    recipes_dir = tmp_path / "recipes"
    recipes_dir.mkdir()
    (recipes_dir / "demo.toml").write_text(
        "[recipe]\n"
        f'app = "demo"\nmatch_sha256 = ["{sha}"]\n'
        '[grants]\nhome_paths = ["Documents/MyAppSaves"]\n'
    )

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
                    {"sha256": frame["body"]["sha256"], "verdict": "clean",
                     "reasons": [], "scanned_by": ["mock"]},
                )
    gtask = asyncio.create_task(fake_guard())
    await asyncio.sleep(0.2)

    runner = MockRunner(ok=True)
    compat_bus = await BusClient.connect(bus_addr, src="jv-compat")
    outcome = await Installer(compat_bus, runner, recipes_dir=recipes_dir).install(
        installer_file
    )
    assert outcome == "blocked"
    assert not runner.argv_log, "nothing may run under a grant that cannot be bound"
    assert not prefix_dir("demo").exists(), "the prefix was built for an install that cannot happen"

    events = await collect(watcher, 3)
    assert [e["event"] for e in events] == ["fingerprinted", "screened", "blocked"]
    assert str(home / "Documents" / "MyAppSaves") in events[-1]["error"]
    assert events[-1]["recipe"] == "demo"  # ...and WHICH recipe to fix

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
