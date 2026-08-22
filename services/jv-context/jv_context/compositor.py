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


class NiriBackend(CompositorBackend):
    """niri event-stream IPC over $NIRI_SOCKET (JSON lines).

    TODO(machine): parser written against niri's documented event stream
    (WindowsChanged / WindowOpenedOrChanged / WindowClosed /
    WindowFocusChanged); verify field-for-field against the pinned niri
    version on ares before trusting it — exit item 3 ('close this')
    depends on it.
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
        # id -> (app_id, title) cache so Closed events can name the app
        windows: dict[int, tuple[str, Optional[str]]] = {}
        while True:
            line = await reader.readline()
            if not line:
                break
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            for ev in self._translate(event, windows):
                yield ev

    def _translate(
        self, event: dict, windows: dict[int, tuple[str, Optional[str]]]
    ) -> list[WindowEvent]:
        out: list[WindowEvent] = []
        if "WindowOpenedOrChanged" in event:
            w = event["WindowOpenedOrChanged"]["window"]
            wid = int(w["id"])
            app_id = w.get("app_id") or ""
            title = w.get("title")
            known = wid in windows
            changed_title = known and windows[wid][1] != title
            windows[wid] = (app_id, title)
            kind = "title_changed" if changed_title else ("opened" if not known else "focus_changed")
            out.append(
                WindowEvent(
                    kind=kind,
                    window_id=wid,
                    app_id=app_id,
                    title=title,
                    focused=bool(w.get("is_focused")),
                )
            )
        elif "WindowClosed" in event:
            wid = int(event["WindowClosed"]["id"])
            app_id, title = windows.pop(wid, ("", None))
            out.append(WindowEvent(kind="closed", window_id=wid, app_id=app_id, title=title))
        elif "WindowFocusChanged" in event:
            wid = event["WindowFocusChanged"].get("id")
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
