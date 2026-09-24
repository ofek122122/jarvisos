"""jv-guard service: reacts to compat.install{event=fingerprinted} by
screening the binary and publishing guard.verdict. The trigger IS the
bus (invariant 1) — compat never imports guard."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Sequence

from jarvis_bus import BusClient, HealthBeat

from .scan import Scanner, decide, sha256_file

HEALTH_PERIOD_S = 5.0


class GuardService:
    def __init__(
        self,
        bus: BusClient,
        scanners: Sequence[Scanner],
        health_period_s: float = HEALTH_PERIOD_S,
    ) -> None:
        self.bus = bus
        self.scanners = scanners
        self._started = time.monotonic()
        # Every beat goes through this — the periodic one and the degraded
        # one a failed scan publishes — so a fault report gets a whole
        # period on the bus instead of whatever was left of the one it
        # interrupted. See jarvis_bus.health.
        self._beats = HealthBeat(health_period_s)

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
        # scanners are independent + CPU-bound — run them concurrently
        # (order preserved for decide(); a no-op with a single engine).
        reports = list(
            await asyncio.gather(
                *(loop.run_in_executor(None, s.scan, path) for s in self.scanners)
            )
        )
        verdict = decide(actual_sha, reports)
        if verdict is None:
            # No AUTHORITATIVE engine ran: publish NOTHING (compat fails
            # closed), but say so on health — outages must be visible.
            # An advisory engine may well have run and had opinions; it
            # cannot clear a binary, so this is still an outage.
            ran = [r.engine for r in reports if r.ran]
            note = "no signature scan engine available"
            if ran:
                note += f" (only advisory: {', '.join(ran)})"
            await self._health("degraded", note)
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
        self._beats.beat()  # before the publish, not after
        body: dict = {
            "service": "jv-guard",
            "state": state,
            "uptime_s": time.monotonic() - self._started,
            "period_s": self._beats.period_s,
        }
        if notes:
            body["notes"] = notes
        await self.bus.publish("sys.health", body)

    async def run(self) -> None:
        await self.bus.subscribe(["compat.install"])
        await self._health()
        while True:
            if self._beats.due:
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
