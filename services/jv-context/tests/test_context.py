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
from jv_context.system import StubAudioProbe, snapshot

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
