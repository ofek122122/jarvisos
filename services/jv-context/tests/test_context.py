"""jv-context tests: redaction rules (the pre-seeded blocklist), window
event translation, and the service against a real jarvisd with the mock
compositor + stub audio probe."""

import asyncio
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from jarvis_bus import BusClient
from jarvis_bus.schema import ContextSystem, ContextWindow, from_body
from jv_context.compositor import MockBackend, WindowEvent
from jv_context.config import ContextConfig
from jv_context.service import ContextService, redact_title, window_body
from jv_context.system import (
    ProbeUnavailable,
    StubAudioProbe,
    WpctlProbe,
    parse_wpctl_volume,
    snapshot,
)

REPO = Path(__file__).resolve().parents[3]
CFG = ContextConfig()


# ------------------------------------------------------------- redaction


def test_blocklist_ships_preseeded():
    """Ofek's requirement: never empty-by-default."""
    assert CFG.app_blocklist, "blocklist must not ship empty"
    joined = " ".join(CFG.app_blocklist)
    for must in ("keepass", "bitwarden", "1password", "private"):
        assert must in joined


@pytest.mark.parametrize(
    "app_id,title,expect_redacted",
    [
        ("org.keepassxc.KeePassXC", "bank vault - KeePassXC", True),
        ("Bitwarden", "Login — Bitwarden", True),
        ("1password", "1Password — Unlock", True),
        ("com.example.PrivateNotes", "diary", True),
        ("firefox", "Mozilla Firefox (Private Browsing)", True),
        ("chromium", "secret tab - Incognito", True),
        ("msedge", "[InPrivate] search", True),
        ("firefox", "JarvisOS blueprint — Mozilla Firefox", False),
        ("alacritty", "~/jarvisos", False),
    ],
)
def test_redaction_rules(app_id, title, expect_redacted):
    published, redacted = redact_title(CFG, app_id, title)
    assert redacted is expect_redacted
    assert (published is None) is expect_redacted


def test_redacted_window_body_carries_null_title_and_flag():
    ev = WindowEvent(kind="focus_changed", window_id=7, app_id="bitwarden", title="Vault")
    body = window_body(CFG, ev)
    assert body["title"] is None
    assert body["redacted"] is True
    # round-trips through the generated binding (required-nullable title)
    win = from_body(ContextWindow, body)
    assert win.title is None and win.redacted is True


# ------------------------------------------------------------- snapshot


def test_snapshot_shape():
    body = snapshot(StubAudioProbe(vol=0.5, muted=False))
    sys_ = from_body(ContextSystem, body)
    assert sys_.audio_volume == 0.5
    assert 0 <= sys_.mem_used_pct <= 100
    assert isinstance(sys_.net_online, bool)


# ------------------------------------------------- the probe cannot guess


@pytest.mark.parametrize(
    "text,vol,muted",
    [
        ("Volume: 0.45\n", 0.45, False),
        ("Volume: 0.45 [MUTED]\n", 0.45, True),
        ("Volume: 1.00\n", 1.0, False),
        ("Volume: 1.40\n", 1.4, False),  # over 100% is legal (schema has no max)
        ("Volume: 0.00\n", 0.0, False),  # a REAL zero still reads as zero
    ],
)
def test_wpctl_parses_what_wpctl_actually_prints(text, vol, muted):
    assert parse_wpctl_volume(text) == (vol, muted)


@pytest.mark.parametrize(
    "text",
    [
        "",  # wpctl printed nothing at all
        "\n",
        "Node 42 not found\n",  # wpctl's own error, on stdout
        "no such id 42\n",  # used to raise ValueError out of the 1 Hz pump
        "Volume:\n",  # the word and no number
        "Volume: loud\n",
        "Volume: nan\n",  # parses as a float and is not a measurement
        "Volume: inf\n",
        "Volume: -0.5\n",  # below the schema's own minimum
        "Balance: 0.45\n",  # a future wpctl wording this differently
    ],
)
def test_wpctl_never_invents_a_reading(text):
    """The bug this closes: an unreadable mixer read as (0.0, False), and
    the HUD draws `audio_volume <= 0` as YOU CANNOT HEAR THIS."""
    with pytest.raises(ProbeUnavailable):
        parse_wpctl_volume(text)


class _FakeRun:
    def __init__(self, stdout="", returncode=0):
        self.stdout, self.returncode = stdout, returncode


def test_wpctl_missing_binary_is_unavailable(monkeypatch):
    """wpctl lives in wireplumber, not in this service's closure."""

    def missing(*a, **k):
        raise FileNotFoundError(2, "No such file or directory", "wpctl")

    monkeypatch.setattr("jv_context.system.subprocess.run", missing)
    with pytest.raises(ProbeUnavailable):
        WpctlProbe().volume()


def test_wpctl_timeout_is_unavailable(monkeypatch):
    def hang(*a, **k):
        raise subprocess.TimeoutExpired(cmd="wpctl", timeout=5)

    monkeypatch.setattr("jv_context.system.subprocess.run", hang)
    with pytest.raises(ProbeUnavailable):
        WpctlProbe().volume()


def test_wpctl_nonzero_exit_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        "jv_context.system.subprocess.run",
        lambda *a, **k: _FakeRun("Volume: 0.45\n", returncode=1),
    )
    with pytest.raises(ProbeUnavailable):
        WpctlProbe().volume()


def test_wpctl_happy_path_still_reads_the_sink(monkeypatch):
    monkeypatch.setattr(
        "jv_context.system.subprocess.run",
        lambda *a, **k: _FakeRun("Volume: 0.32 [MUTED]\n"),
    )
    assert WpctlProbe().volume() == (0.32, True)


class FailingProbe(StubAudioProbe):
    """A mixer that cannot be read. `heal()` makes it readable again."""

    def __init__(self, vol=0.5, muted=False):
        super().__init__(vol, muted)
        self.broken = True
        self.calls = 0

    def heal(self):
        self.broken = False

    def volume(self):
        self.calls += 1
        if self.broken:
            raise ProbeUnavailable("wpctl did not run: no such file")
        return super().volume()


def test_snapshot_publishes_nothing_rather_than_half_a_machine():
    """Every field a probe feeds is REQUIRED by the schema, so there is
    no legal partial frame — snapshot() raises instead of substituting."""
    with pytest.raises(ProbeUnavailable):
        snapshot(FailingProbe())


# ------------------------------------------------------------ e2e on bus


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


async def test_service_publishes_events_and_snapshots(bus_addr):
    watcher = await BusClient.connect(bus_addr, src="t-watch")
    await watcher.subscribe(["context.*"])
    await asyncio.sleep(0.2)

    scripted = [
        WindowEvent("opened", 1, "firefox", "JarvisOS blueprint", focused=True),
        WindowEvent("focus_changed", 2, "org.keepassxc.KeePassXC", "vault", focused=True),
        WindowEvent("closed", 1, "firefox", "JarvisOS blueprint"),
    ]
    svc_bus = await BusClient.connect(bus_addr, src="jv-context")
    svc = ContextService(svc_bus, MockBackend(scripted, linger_s=1.5), StubAudioProbe())
    await svc.run()  # mock backend ends -> run returns

    windows, systems = [], 0
    # 3 window frames + at least one 1 Hz snapshot, in whatever order
    while len(windows) < 3 or systems < 1:
        frame = await asyncio.wait_for(watcher.next_frame(), timeout=5)
        if frame["topic"] == "context.window":
            windows.append(frame["body"])
        elif frame["topic"] == "context.system":
            systems += 1

    assert [w["kind"] for w in windows] == ["opened", "focus_changed", "closed"]
    assert windows[0]["title"] == "JarvisOS blueprint"  # not blocklisted
    assert windows[1]["title"] is None and windows[1]["redacted"] is True

    await svc_bus.close()
    await watcher.close()


# --------------------------------------- a blind probe is news, not death


async def watch(addr, topics):
    w = await BusClient.connect(addr, src="t-watch")
    await w.subscribe(topics)
    await asyncio.sleep(0.2)
    return w


async def drain(watcher, deadline_s=1.0):
    """Every frame the watcher can hand over within the window."""
    frames = []
    loop = asyncio.get_running_loop()
    end = loop.time() + deadline_s
    while (left := end - loop.time()) > 0:
        try:
            frames.append(await asyncio.wait_for(watcher.next_frame(), timeout=left))
        except asyncio.TimeoutError:
            break
    return frames


BLIND_CFG = ContextConfig(system_period_s=0.05, health_period_s=30.0)


async def test_a_failing_probe_does_not_kill_the_snapshot_pump(bus_addr):
    """The bug: one exception out of a probe killed `_pump_system` for
    the life of the process. jv-context stayed alive pumping windows, so
    `Restart=on-failure` never fired, and the heartbeat went on saying
    `ok` while half of what the service exists to publish was gone."""
    watcher = await watch(bus_addr, ["context.*", "sys.health"])
    probe = FailingProbe()
    svc_bus = await BusClient.connect(bus_addr, src="jv-context")
    svc = ContextService(svc_bus, MockBackend([], linger_s=0.8), probe, BLIND_CFG)
    await svc.run()

    frames = await drain(watcher, 0.5)
    await svc_bus.close()
    await watcher.close()

    # it kept ticking rather than dying on the first failure
    assert probe.calls > 3, f"pump stopped after {probe.calls} attempt(s)"
    # and published no frame about a machine it could not read
    assert [f for f in frames if f["topic"] == "context.system"] == []

    beats = [f["body"] for f in frames if f["topic"] == "sys.health"]
    degraded = [b for b in beats if b["state"] == "degraded"]
    assert degraded, f"nothing on the bus says jv-context is blind: {beats}"
    assert "context.system" in degraded[0]["notes"]
    # ...and said it ONCE. ~16 ticks failed the same way in this window;
    # the period is 30 s, so only the transition may beat, or jv-context's
    # 1 Hz lands on a topic that is meant to be quiet (invariant 5).
    assert [b["state"] for b in beats] == ["ok", "degraded"], beats


async def test_the_blind_heartbeat_does_not_wait_for_the_period(bus_addr):
    """schemas/sys.health.json: every fixed period AND immediately on
    state change. BLIND_CFG's period is 30 s; the whole test is 1.3 s."""
    watcher = await watch(bus_addr, ["sys.health"])
    svc_bus = await BusClient.connect(bus_addr, src="jv-context")
    svc = ContextService(svc_bus, MockBackend([], linger_s=0.8), FailingProbe(), BLIND_CFG)
    await svc.run()

    states = [f["body"]["state"] for f in await drain(watcher, 0.5)]
    await svc_bus.close()
    await watcher.close()
    assert states[:2] == ["ok", "degraded"], states


async def test_the_snapshot_returns_and_the_heartbeat_says_so(bus_addr):
    """A mixer that comes back (wireplumber restarting) must not leave
    jv-context reporting degraded for the rest of the day."""
    watcher = await watch(bus_addr, ["context.*", "sys.health"])
    probe = FailingProbe(vol=0.4, muted=True)
    svc_bus = await BusClient.connect(bus_addr, src="jv-context")
    svc = ContextService(svc_bus, MockBackend([], linger_s=0.8), probe, BLIND_CFG)

    async def heal_later():
        await asyncio.sleep(0.4)
        probe.heal()

    healer = asyncio.create_task(heal_later())
    await svc.run()
    await healer

    frames = await drain(watcher, 0.5)
    await svc_bus.close()
    await watcher.close()

    states = [f["body"]["state"] for f in frames if f["topic"] == "sys.health"]
    assert "degraded" in states
    assert states.index("degraded") < states.index("ok", states.index("degraded"))

    snaps = [f["body"] for f in frames if f["topic"] == "context.system"]
    assert snaps, "the pump never resumed"
    assert snaps[0]["audio_volume"] == 0.4 and snaps[0]["audio_muted"] is True
    # and every snapshot on the bus is a whole one
    for body in snaps:
        from_body(ContextSystem, body)
