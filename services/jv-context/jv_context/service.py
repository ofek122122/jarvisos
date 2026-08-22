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
from .system import AudioProbe, snapshot


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
    if ev.workspace is not None:
        body["workspace"] = ev.workspace
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
    ) -> None:
        self.bus = bus
        self.backend = backend
        self.audio = audio
        self.cfg = cfg or ContextConfig()
        self._started = time.monotonic()

    async def _pump_windows(self) -> None:
        async for ev in self.backend.events():
            await self.bus.publish("context.window", window_body(self.cfg, ev))

    async def _pump_system(self) -> None:
        while True:
            body = await asyncio.get_running_loop().run_in_executor(
                None, snapshot, self.audio
            )
            await self.bus.publish("context.system", body)
            await asyncio.sleep(self.cfg.system_period_s)

    async def _pump_health(self) -> None:
        while True:
            await self.bus.publish(
                "sys.health",
                {
                    "service": "jv-context",
                    "state": "ok",
                    "uptime_s": time.monotonic() - self._started,
                    "period_s": self.cfg.health_period_s,
                },
            )
            await asyncio.sleep(self.cfg.health_period_s)

    async def run(self) -> None:
        health = asyncio.create_task(self._pump_health())
        system = asyncio.create_task(self._pump_system())
        try:
            await self._pump_windows()  # ends when the backend ends (mock/EOF)
        finally:
            health.cancel()
            system.cancel()
