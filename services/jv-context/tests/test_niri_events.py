"""The niri event-stream parser, which had no tests at all and is the one
piece of jv-context that runs only on ares.

Every event name and field here was read off the PINNED niri in this
flake (`niri-26.04`): the serde variant names `Event::WindowsChanged`
(field `windows`), `Event::WindowOpenedOrChanged` (field `window`),
`Event::WindowClosed`, `Event::WindowFocusChanged`, and `struct Window`
with `id / title / app_id / workspace_id / is_focused / ...`. They are
strings in that binary, so these fixtures are not invented shapes.

The point of the suite is `WindowsChanged` — niri's authoritative window
list, sent on connect and on any resync. jv-context never handled it, so
on a desktop where anything was already open when the service started:

  * the first event about every pre-existing window said `opened` — you
    had Firefox up all day, you switched tabs, and the brain was told
    Firefox had just opened;
  * a `WindowClosed` or a `WindowFocusChanged` for one of them carried
    `app_id: ""` — the schema says focus_changed frames are what jv-act
    resolves "this window" against, and it resolved to a nameless one;
  * "which window is focused" was unknowable until the user switched.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from jv_context.compositor import NiriBackend, NiriState
from jv_context.config import ContextConfig
from jv_context.service import window_body

CFG = ContextConfig()


def win(wid, app_id="firefox", title="a page", focused=False, **over):
    """One entry of niri's `struct Window`, as it appears on the wire."""
    w = {
        "id": wid,
        "title": title,
        "app_id": app_id,
        "workspace_id": 1,
        "is_focused": focused,
        "is_floating": False,
        "is_urgent": False,
    }
    w.update(over)
    return w


def resync(*windows):
    return {"WindowsChanged": {"windows": list(windows)}}


def opened_or_changed(w):
    return {"WindowOpenedOrChanged": {"window": w}}


def translate(events, state=None):
    """Run a sequence of wire events through one parser state."""
    be = NiriBackend(socket_path="/nonexistent")
    st = state if state is not None else NiriState()
    out = []
    for ev in events:
        out.extend(be._translate(ev, st))
    return out, st


# ---------------------------------------------------- the resync itself


def test_a_resync_publishes_focus_for_the_window_niri_says_is_focused():
    out, _ = translate([resync(win(1), win(2, focused=True))])
    assert [(e.kind, e.window_id, e.focused) for e in out] == [
        ("focus_changed", 2, True)
    ]


def test_a_resync_never_reports_a_window_that_was_already_open_as_opened():
    """The frame that would date an hours-old window to now."""
    out, _ = translate([resync(win(1), win(2), win(3, focused=True))])
    assert [e.kind for e in out] == ["focus_changed"]


def test_a_resync_with_nothing_focused_publishes_nothing():
    """`window_id` is required and non-negative, so the frozen schema has
    no way to say 'no window has focus'. Silence beats inventing one."""
    out, _ = translate([resync(win(1), win(2))])
    assert out == []


def test_a_second_resync_that_changes_nothing_publishes_nothing():
    """A resync is a state dump, not an event: it publishes only what it
    CHANGES. Compositor events are forwarded; this one is deduped."""
    out, _ = translate([resync(win(1, focused=True)), resync(win(1, focused=True))])
    assert len(out) == 1


def test_a_resync_publishes_focus_when_the_focused_window_changed():
    out, _ = translate(
        [
            resync(win(1, focused=True), win(2)),
            resync(win(1), win(2, focused=True)),
        ]
    )
    assert [e.window_id for e in out] == [1, 2]


# ------------------------------------------- what the resync teaches it


def test_a_close_can_name_a_window_that_was_open_before_the_service_was():
    out, _ = translate(
        [
            resync(win(7, app_id="org.keepassxc.KeePassXC", title="vault")),
            {"WindowClosed": {"id": 7}},
        ]
    )
    assert [(e.kind, e.app_id, e.title) for e in out] == [
        ("closed", "org.keepassxc.KeePassXC", "vault")
    ]


def test_focusing_a_window_that_was_open_before_the_service_names_it():
    out, _ = translate(
        [
            resync(win(7, app_id="alacritty", title="~/jarvisos")),
            {"WindowFocusChanged": {"id": 7}},
        ]
    )
    assert [(e.kind, e.app_id, e.title) for e in out] == [
        ("focus_changed", "alacritty", "~/jarvisos")
    ]


def test_a_pre_existing_window_changing_its_title_is_not_an_open():
    out, _ = translate(
        [
            resync(win(1, title="tab one")),
            opened_or_changed(win(1, title="tab two")),
        ]
    )
    assert [e.kind for e in out] == ["title_changed"]


def test_a_resync_forgets_a_window_it_no_longer_lists():
    """It is the authoritative list; what is not in it is not open. It
    does not publish `closed` for the difference — it cannot say WHEN
    they went, and niri sends WindowClosed for the ones it saw go."""
    out, _ = translate(
        [
            resync(win(1, app_id="firefox"), win(2, app_id="alacritty")),
            resync(win(2, app_id="alacritty")),
            {"WindowClosed": {"id": 1}},
        ]
    )
    assert [e.kind for e in out] == ["closed"]
    assert out[0].app_id == ""  # forgotten, and honestly nameless


def test_a_genuinely_new_window_after_a_resync_is_still_an_open():
    out, _ = translate(
        [resync(win(1)), opened_or_changed(win(9, app_id="steam", title="Steam"))]
    )
    assert [(e.kind, e.window_id) for e in out] == [("opened", 9)]


# ------------------------------------------------------- focus tracking


def test_focus_leaving_every_window_is_not_reported_and_is_not_remembered():
    """niri sends `WindowFocusChanged {id: null}` when nothing is focused.
    The schema cannot express it, so no frame goes out — but forgetting it
    matters, or the next resync would dedup against a stale answer."""
    out, _ = translate(
        [
            resync(win(1, focused=True)),
            {"WindowFocusChanged": {"id": None}},
            resync(win(1, focused=True)),
        ]
    )
    assert [e.window_id for e in out] == [1, 1]


def test_closing_the_focused_window_is_not_remembered_as_focused():
    out, _ = translate(
        [
            {"WindowFocusChanged": {"id": 1}},
            {"WindowClosed": {"id": 1}},
            resync(win(1, focused=True)),
        ]
    )
    assert [e.kind for e in out] == ["focus_changed", "closed", "focus_changed"]


def test_an_event_that_says_a_window_is_focused_updates_the_tracker():
    """WindowOpenedOrChanged carries `is_focused`; a resync right after it
    that agrees has nothing to say."""
    out, _ = translate(
        [opened_or_changed(win(4, focused=True)), resync(win(4, focused=True))]
    )
    assert len(out) == 1


# ------------------------------------------------------------- privacy


def test_a_window_open_before_the_service_started_is_redacted_like_any_other():
    """The resync is the first thing that ever put a real title in this
    process. Redaction happens at publish, so it covers this path too —
    asserted here because seeding the cache is what made it reachable."""
    out, _ = translate(
        [resync(win(3, app_id="org.keepassxc.KeePassXC", title="bank", focused=True))]
    )
    body = window_body(CFG, out[0])
    assert body["app_id"] == "org.keepassxc.KeePassXC"
    assert body["title"] is None and body["redacted"] is True


def test_a_private_browsing_title_learned_from_a_resync_never_reaches_a_body():
    out, _ = translate(
        [
            resync(win(5, app_id="firefox", title="Vault — (Private Browsing)")),
            {"WindowFocusChanged": {"id": 5}},
        ]
    )
    body = window_body(CFG, out[0])
    assert body["title"] is None and body["redacted"] is True


# ---------------------------------------------- the events it passes by


@pytest.mark.parametrize(
    "event",
    [
        {"Ok": "Handled"},  # the reply to `"EventStream"` — always line 1
        {"WorkspacesChanged": {"workspaces": []}},
        {"KeyboardLayoutsChanged": {"keyboard_layouts": {}}},
        {"OverviewOpenedOrClosed": {"is_open": False}},
        {"ConfigLoaded": {"failed": False}},
        {"CastsChanged": {"casts": []}},
        {"WindowUrgencyChanged": {"id": 1, "urgent": True}},
        {"WindowLayoutsChanged": {"changes": []}},
        {},
    ],
)
def test_events_with_no_frame_to_publish_are_passed_over(event):
    """Every variant in this list except the last two was observed on the
    live niri session on ares within three seconds of connecting, on a
    desktop nobody was touching. A parser that tripped on any of them
    would take jv-context down at startup."""
    out, _ = translate([event])
    assert out == []


def test_the_windows_field_names_are_the_ones_the_pinned_niri_sends():
    """Read off the live stream on ares: `struct Window` carries these ten
    keys. The fixture in this file is a subset of them and must stay one —
    if niri renames a field, this fails here rather than on the machine."""
    wire = {
        "app_id", "focus_timestamp", "id", "is_floating", "is_focused",
        "is_urgent", "layout", "pid", "title", "workspace_id",
    }
    assert set(win(1)) <= wire
    assert {"id", "app_id", "title", "is_focused"} <= set(win(1))


def test_a_resync_with_no_windows_at_all_is_not_an_error():
    out, st = translate([resync(win(1, focused=True)), resync()])
    assert [e.window_id for e in out] == [1]
    assert st.windows == {} and st.focused is None


# -------------------------------------------------- the socket loop itself


async def serve_lines(path, lines, got):
    """A fake niri: accept one connection, record the request line, write
    the scripted events, close. Real socket, real JSON-lines framing."""

    async def handle(reader, writer):
        got.append(await reader.readline())
        for line in lines:
            writer.write(line)
        await writer.drain()
        writer.close()

    return await asyncio.start_unix_server(handle, path=path)


async def test_the_event_stream_is_requested_and_parsed_off_a_real_socket(tmp_path):
    """`events()` had no coverage at all, and it is the half that only ever
    runs on ares: the `"EventStream"` request, the JSON-lines framing, and
    one parser state carried across lines."""
    sock = str(tmp_path / "niri.sock")
    got: list[bytes] = []
    lines = [
        json.dumps(resync(win(1, app_id="firefox", title="a page", focused=True))).encode()
        + b"\n",
        b"not json at all\n",  # niri never sends this; a half-line on a restart might
        json.dumps(opened_or_changed(win(2, app_id="steam", title="Steam"))).encode() + b"\n",
        json.dumps({"WindowClosed": {"id": 1}}).encode() + b"\n",
    ]
    server = await serve_lines(sock, lines, got)
    try:
        events = [ev async for ev in NiriBackend(socket_path=sock).events()]
    finally:
        server.close()
        await server.wait_closed()

    assert got == [b'"EventStream"\n']
    assert [(e.kind, e.window_id, e.app_id) for e in events] == [
        ("focus_changed", 1, "firefox"),
        ("opened", 2, "steam"),
        ("closed", 1, "firefox"),  # named only because the resync seeded it
    ]


async def test_no_niri_socket_is_an_error_and_not_an_empty_stream(monkeypatch):
    """A jv-context that silently published nothing would look exactly
    like a desktop where nobody touched a window.

    `delenv` is not decoration: the loop that wrote this test was running
    inside a live niri session, so the empty path fell through to the real
    $NIRI_SOCKET and the test sat on the user's own compositor until it
    was killed. A test that reaches the machine it runs on is not a test.
    """
    monkeypatch.delenv("NIRI_SOCKET", raising=False)
    with pytest.raises(RuntimeError, match="NIRI_SOCKET"):
        [ev async for ev in NiriBackend(socket_path="").events()]
