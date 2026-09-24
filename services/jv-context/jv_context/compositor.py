"""Compositor seam (BRIEF-phase2 §1): jv-context never knows which
compositor it's on. NiriBackend speaks the niri event-stream IPC;
MockBackend scripts events for CI; a Smithay backend slots in at
blueprint Phase 5. Events, never polling."""

from __future__ import annotations

import dataclasses
import json
import os
from typing import AsyncIterator, Optional


@dataclasses.dataclass
class WindowEvent:
    kind: str  # focus_changed | opened | closed | title_changed
    window_id: int
    app_id: str = ""
    title: Optional[str] = None
    workspace: Optional[str] = None
    focused: bool = False


class CompositorBackend:
    async def events(self) -> AsyncIterator[WindowEvent]:  # pragma: no cover
        raise NotImplementedError
        yield  # makes this an async generator for type purposes


class MockBackend(CompositorBackend):
    """Replays a scripted list of WindowEvents — CI's compositor.
    `linger_s` keeps the stream open after the last event so the
    service's other pumps (system snapshot) get to run in tests."""

    def __init__(self, scripted: list[WindowEvent], linger_s: float = 0.0) -> None:
        self.scripted = scripted
        self.linger_s = linger_s

    async def events(self) -> AsyncIterator[WindowEvent]:
        import asyncio

        for ev in self.scripted:
            yield ev
        if self.linger_s:
            await asyncio.sleep(self.linger_s)


@dataclasses.dataclass
class NiriState:
    """What the parser has to remember between lines of the stream.

    `windows` is id -> (app_id, title): niri names a window in full when
    it opens or changes and by id alone when it closes or takes focus, so
    without this cache those frames reach the bus anonymous — and the
    schema says focus_changed frames are what jv-act resolves "this
    window" against. `focused` is the id the last published frame said
    had focus; it exists only so a RESYNC can tell whether it has news.

    Titles live here raw and are redacted on the way out (service.py):
    this dict never leaves the process, and holding the real title is what
    lets a close or a focus of a password manager be redacted at all.
    """

    windows: dict[int, tuple[str, Optional[str]]] = dataclasses.field(default_factory=dict)
    focused: Optional[int] = None


class NiriBackend(CompositorBackend):
    """niri event-stream IPC over $NIRI_SOCKET (JSON lines).

    Two kinds of line come down this socket and they are not the same
    kind of thing. `WindowOpenedOrChanged` / `WindowClosed` /
    `WindowFocusChanged` are EVENTS — something happened, and each one
    becomes a frame. `WindowsChanged` is a RESYNC: niri's complete window
    list, sent on connect and again whenever it wants to restate the
    world. It is a state dump with no timestamps in it, so it publishes
    only what it CHANGES — never `opened` for a window that has been up
    since before this process started, never `closed` for one that left
    while nobody was listening. What it does do is seed the cache (so the
    frames above can name windows that predate the service) and, when it
    names a focused window nothing has reported yet, publish the one
    `focus_changed` that makes "this window" resolvable at all. Without
    it, jv-act had no answer to "this" until the user switched windows.

    FIELD-VERIFIED on ares against the live niri-26.04 session
    (2026-09-24, read-only: connect, request, read, disconnect). What the
    real stream answered, and it is why this class changed:

      * the reply to the request is `{"Ok": ...}`, then
        `WorkspacesChanged`, then `WindowsChanged` — the full list, third
        line, before any event. It listed the 3 windows that were open,
        with exactly one `is_focused`. Every one of them was invisible to
        the old parser.
      * `struct Window` on the wire carries `app_id, focus_timestamp, id,
        is_floating, is_focused, is_urgent, layout, pid, title,
        workspace_id`; `id` is an int and `app_id`/`title` are present on
        every entry. The four fields read here are all there.
      * `Ok`, `WorkspacesChanged`, `KeyboardLayoutsChanged`,
        `OverviewOpenedOrClosed`, `ConfigLoaded` and `CastsChanged` all
        arrive on a quiet desktop and all pass through with no frame.

    TODO(machine): what a capture with nobody touching the keyboard
    cannot show is the per-window events — `WindowOpenedOrChanged` /
    `WindowClosed` / `WindowFocusChanged` — and whether niri ever sends a
    SECOND `WindowsChanged` mid-session. Those want a human moving
    windows for a minute with `niri msg -j event-stream` running; exit
    item 3 ('close this') is where that belongs.
    """

    def __init__(self, socket_path: Optional[str] = None) -> None:
        self.socket_path = socket_path or os.environ.get("NIRI_SOCKET", "")

    async def events(self) -> AsyncIterator[WindowEvent]:
        import asyncio

        if not self.socket_path:
            raise RuntimeError("NIRI_SOCKET not set — is this a niri session?")
        reader, writer = await asyncio.open_unix_connection(self.socket_path)
        writer.write(b'"EventStream"\n')
        await writer.drain()
        state = NiriState()
        while True:
            line = await reader.readline()
            if not line:
                break
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            for ev in self._translate(event, state):
                yield ev

    def _translate(self, event: dict, state: NiriState) -> list[WindowEvent]:
        out: list[WindowEvent] = []
        windows = state.windows
        if "WindowsChanged" in event:
            listed = event["WindowsChanged"].get("windows") or []
            focused: Optional[int] = None
            fresh: dict[int, tuple[str, Optional[str]]] = {}
            for w in listed:
                wid = int(w["id"])
                fresh[wid] = (w.get("app_id") or "", w.get("title"))
                if focused is None and w.get("is_focused"):
                    focused = wid
            # Authoritative: what it does not list is not open.
            windows.clear()
            windows.update(fresh)
            if focused is not None and focused != state.focused:
                app_id, title = windows[focused]
                out.append(
                    WindowEvent(
                        kind="focus_changed",
                        window_id=focused,
                        app_id=app_id,
                        title=title,
                        focused=True,
                    )
                )
            state.focused = focused
        elif "WindowOpenedOrChanged" in event:
            w = event["WindowOpenedOrChanged"]["window"]
            wid = int(w["id"])
            app_id = w.get("app_id") or ""
            title = w.get("title")
            known = wid in windows
            changed_title = known and windows[wid][1] != title
            windows[wid] = (app_id, title)
            kind = "title_changed" if changed_title else ("opened" if not known else "focus_changed")
            is_focused = bool(w.get("is_focused"))
            if is_focused:
                state.focused = wid
            out.append(
                WindowEvent(
                    kind=kind,
                    window_id=wid,
                    app_id=app_id,
                    title=title,
                    focused=is_focused,
                )
            )
        elif "WindowClosed" in event:
            wid = int(event["WindowClosed"]["id"])
            app_id, title = windows.pop(wid, ("", None))
            if state.focused == wid:
                state.focused = None
            out.append(WindowEvent(kind="closed", window_id=wid, app_id=app_id, title=title))
        elif "WindowFocusChanged" in event:
            wid = event["WindowFocusChanged"].get("id")
            # `id: null` is "nothing has focus now". `window_id` is
            # required and non-negative in the frozen schema, so there is
            # no frame for it — but it must still be FORGOTTEN, or the
            # next resync would dedup against an answer that has expired.
            state.focused = None if wid is None else int(wid)
            if wid is not None:
                app_id, title = windows.get(int(wid), ("", None))
                out.append(
                    WindowEvent(
                        kind="focus_changed",
                        window_id=int(wid),
                        app_id=app_id,
                        title=title,
                        focused=True,
                    )
                )
        return out
