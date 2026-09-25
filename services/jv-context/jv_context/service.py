"""jv-context service: compositor events -> context.window (with the
privacy blocklist applied), system snapshot -> context.system at 1 Hz."""

from __future__ import annotations

import asyncio
import fnmatch
import time
from typing import Optional

from jarvis_bus import BusClient

from .compositor import CompositorBackend, WindowEvent
from .config import ContextConfig
from .system import AudioProbe, GpuProbe, snapshot


def redact_title(
    cfg: ContextConfig, app_id: str, title: Optional[str]
) -> tuple[Optional[str], bool]:
    """(title-to-publish, redacted). Blocklisted app_ids and private
    browser surfaces never leak titles onto the bus."""
    if title is None:
        return None, False
    app = app_id.lower()
    if any(fnmatch.fnmatch(app, pat) for pat in cfg.app_blocklist):
        return None, True
    low = title.lower()
    if any(marker in low for marker in cfg.title_markers):
        return None, True
    return title, False


def window_body(cfg: ContextConfig, ev: WindowEvent) -> dict:
    title, redacted = redact_title(cfg, ev.app_id, ev.title)
    body: dict = {
        "kind": ev.kind,
        "window_id": ev.window_id,
        "app_id": ev.app_id,
        "title": title,
    }
    # Absent, not empty: the schema's `workspace`/`monitor` are optional
    # and a window whose workspace nothing has described says nothing
    # about where it is rather than guessing.
    if ev.workspace is not None:
        body["workspace"] = ev.workspace
    if ev.monitor is not None:
        body["monitor"] = ev.monitor
    if ev.focused:
        body["focused"] = True
    if redacted:
        body["redacted"] = True
    return body


class ContextService:
    def __init__(
        self,
        bus: BusClient,
        backend: CompositorBackend,
        audio: AudioProbe,
        cfg: Optional[ContextConfig] = None,
        gpu: Optional[GpuProbe] = None,
    ) -> None:
        self.bus = bus
        self.backend = backend
        self.audio = audio
        self.gpu = gpu
        self.cfg = cfg or ContextConfig()
        self._started = time.monotonic()
        # None while the snapshot is whole; the note to beat out, when it
        # is not. Read by the heartbeat, written by the system pump.
        self._system_fault: Optional[str] = None
        # Set when that answer CHANGES, so the heartbeat does not have to
        # wait out its period to say so.
        self._health_now = asyncio.Event()

    async def _pump_windows(self) -> None:
        async for ev in self.backend.events():
            await self.bus.publish("context.window", window_body(self.cfg, ev))

    async def _pump_system(self) -> None:
        """One snapshot per period, forever.

        A tick that cannot be taken publishes NOTHING. Every field a
        probe feeds is required by schemas/context.system.json, so there
        is no legal partial frame, and the two ways of filling the gap
        are both worse than the gap: a substituted number is a reading
        nobody took, and restating the last good snapshot dates it NOW.
        The bus's last word simply ages out, which consumers already
        handle — the HUD stops believing a snapshot after three periods.

        The failure is not swallowed, it MOVES: to the heartbeat, as
        `degraded` with a note. Before this, one exception out of a probe
        killed this task for the life of the process — jv-context stayed
        alive pumping window events, so `Restart=on-failure` never fired,
        and `_pump_health` went on saying `ok` about a service that had
        stopped publishing half of what it exists for.

        The catch is broad on purpose: the point is that no probe, present
        or future, can end this loop. It is not silent, which is the thing
        a broad catch is usually guilty of — every failure ends up on the
        bus, named by its exception type.
        """
        while True:
            try:
                snap = await asyncio.get_running_loop().run_in_executor(
                    None, snapshot, self.audio, self.gpu
                )
            except Exception as exc:  # noqa: BLE001 - report, stay alive
                self._set_fault(
                    f"no context.system snapshot: {type(exc).__name__}: {exc}"
                )
            else:
                # A whole frame can still be missing an OPTIONAL field, and
                # `gpu_vram_free_mb` absent because nobody could read the
                # card looks exactly like a machine that has none. The
                # frame goes out either way; the difference is said here.
                self._set_fault(snap.gpu_note)
                await self.bus.publish("context.system", snap.body)
            await asyncio.sleep(self.cfg.system_period_s)

    def _set_fault(self, fault: Optional[str]) -> None:
        """Record what the snapshot is doing — as the note to publish,
        not as a reason to be wrapped later — and wake the heartbeat if
        that CHANGED. schemas/sys.health.json asks for a beat every
        period "and immediately on state change"; on a 5 s beat, a
        jv-context that had just gone blind was up to 5 s of silence
        about itself. Only the transition wakes it — a probe failing the
        same way twice running is not news, and a beat per failed tick
        would put jv-context's 1 Hz onto a topic that is meant to be
        quiet (invariant 5). A fault whose TEXT changes while the state
        does not (the card goes quiet while the mixer already had) waits
        for the next periodic beat: the bus already says `degraded`, and
        waking on every new string is how a message that embeds a
        changing number becomes a 1 Hz heartbeat.
        """
        if (fault is None) != (self._system_fault is None):
            self._health_now.set()
        self._system_fault = fault

    def _health_body(self) -> dict:
        fault = self._system_fault
        body: dict = {
            "service": "jv-context",
            "state": "ok" if fault is None else "degraded",
            "uptime_s": time.monotonic() - self._started,
            "period_s": self.cfg.health_period_s,
        }
        if fault is not None:
            # `degraded` = alive but impaired, which is exactly this:
            # either the window half of jv-context is still running while
            # the snapshot is not, or the snapshot is running a field
            # short. The note says which.
            body["notes"] = fault
        return body

    async def _pump_health(self) -> None:
        while True:
            # Cleared before the body is read and with no await between
            # the two, so a fault raised during the publish below sets the
            # event again and is beaten out on the next pass rather than
            # waiting a period.
            self._health_now.clear()
            body = self._health_body()
            await self.bus.publish("sys.health", body)
            try:
                await asyncio.wait_for(
                    self._health_now.wait(), self.cfg.health_period_s
                )
            except asyncio.TimeoutError:
                pass

    async def run(self) -> None:
        health = asyncio.create_task(self._pump_health())
        system = asyncio.create_task(self._pump_system())
        try:
            await self._pump_windows()  # ends when the backend ends (mock/EOF)
        finally:
            health.cancel()
            system.cancel()
