"""jv-guard service: reacts to compat.install{event=fingerprinted} by
screening the binary and publishing guard.verdict. The trigger IS the
bus (invariant 1) — compat never imports guard."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Sequence

from jarvis_bus import BusClient

from .scan import Scanner, decide, sha256_file

HEALTH_PERIOD_S = 5.0


class GuardService:
    def __init__(self, bus: BusClient, scanners: Sequence[Scanner]) -> None:
        self.bus = bus
        self.scanners = scanners
        self._started = time.monotonic()

    async def _screen(self, path_str: str, claimed_sha: str) -> None:
        path = Path(path_str)
        loop = asyncio.get_running_loop()
        try:
            actual_sha = await loop.run_in_executor(None, sha256_file, path)
        except OSError as exc:
            await self._health("degraded", f"cannot read {path}: {exc}")
            return
        if claimed_sha and actual_sha != claimed_sha:
            # The file changed between fingerprint and screen — treat as
            # blocked, that is exactly what a dropper does.
            await self.bus.publish(
                "guard.verdict",
                {
                    "sha256": actual_sha,
                    "verdict": "blocked",
                    "reasons": ["file hash changed between fingerprint and screening"],
                    "scanned_by": [],
                    "path": str(path),
                },
            )
            return
        reports = [
            await loop.run_in_executor(None, s.scan, path) for s in self.scanners
        ]
        verdict = decide(actual_sha, reports)
        if verdict is None:
            # No engine ran: publish NOTHING (compat fails closed), but
            # say so on health — outages must be visible.
            await self._health("degraded", "no scan engine available")
            return
        await self.bus.publish(
            "guard.verdict",
            {
                "sha256": verdict.sha256,
                "verdict": verdict.verdict,
                "reasons": verdict.reasons,
                "scanned_by": verdict.scanned_by,
                "path": str(path),
            },
        )

    async def _health(self, state: str = "ok", notes: str | None = None) -> None:
        body: dict = {
            "service": "jv-guard",
            "state": state,
            "uptime_s": time.monotonic() - self._started,
            "period_s": HEALTH_PERIOD_S,
        }
        if notes:
            body["notes"] = notes
        await self.bus.publish("sys.health", body)

    async def run(self) -> None:
        await self.bus.subscribe(["compat.install"])
        await self._health()
        health_at = time.monotonic()
        while True:
            if time.monotonic() - health_at >= HEALTH_PERIOD_S:
                health_at = time.monotonic()
                await self._health()
            try:
                frame = await asyncio.wait_for(self.bus.next_frame(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            if frame is None:
                break
            body = frame["body"]
            if body.get("event") == "fingerprinted" and body.get("path"):
                await self._screen(body["path"], body.get("sha256", ""))
