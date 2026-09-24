"""The install pipeline (BRIEF-phase2 §4):

  fingerprint -> publish fingerprinted -> AWAIT guard.verdict
  -> fail closed on timeout/no-verdict (approved policy)
  -> blocked: refuse, always
  -> suspicious: allowed only through the confirmation flow (jv-act
     owns confirmations; v0 compat treats suspicious as refuse-with-
     override-instructions, the wired override arrives with the HUD)
  -> clean: prefix -> silent install (Runner seam; wine only on ares)
  -> publish installed / failed

Every stage is a compat.install frame — the lifecycle is observable.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import time
from pathlib import Path
from typing import Optional, Protocol

from jarvis_bus import BusClient

from .fingerprint import fingerprint, silent_args
from .prefix import bwrap_args, create_prefix_layout
from .recipes import Recipe, find_recipe, load_recipes

# How long we wait for jv-guard's verdict before failing closed. It must
# OUTLAST jv-guard's own worst case, because the screening we give up on is
# still running: ClamAVScanner gives clamscan 120 s, and a verdict published
# after we stopped listening is a clean binary refused with "screening
# unavailable" while the engine that cleared it was working the whole time.
# The slack on top covers the re-hash of a large installer and jv-guard's
# 0.1 s poll of `compat.install`. Pinned against that number by
# `test_the_wait_for_a_verdict_outlasts_the_scan_it_is_waiting_for`.
VERDICT_TIMEOUT_S = 180.0


def sha256_file(path: Path) -> str:
    # Duplicated 6-liner rather than importing from jv-guard: services
    # never import each other (invariant 1).
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Runner(Protocol):
    """Executes the confined installer. RealRunner = wine via umu inside
    bwrap (machine only); MockRunner for tests/CI."""

    async def install(self, argv: list[str]) -> tuple[bool, str]: ...


class MockRunner:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.argv_log: list[list[str]] = []

    async def install(self, argv: list[str]) -> tuple[bool, str]:
        self.argv_log.append(argv)
        return self.ok, "mock install" if self.ok else "mock failure"


class RealRunner:
    """TODO(machine): umu-run/wine inside bwrap; exit item 5."""

    async def install(self, argv: list[str]) -> tuple[bool, str]:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await proc.communicate()
        return proc.returncode == 0, out.decode(errors="replace")[-2000:]


def app_slug(path: Path) -> str:
    stem = re.sub(r"(?i)[-_. ]?(setup|installer|install|x64|x86|win64|win32)", "", path.stem)
    slug = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
    return slug or "unknown-app"


class Installer:
    def __init__(
        self,
        bus: BusClient,
        runner: Runner,
        recipes_dir: Optional[Path] = None,
    ) -> None:
        self.bus = bus
        self.runner = runner
        self.recipes = load_recipes(recipes_dir)

    async def _event(self, event: str, app: str, sha256: str, **extra) -> None:
        await self.bus.publish(
            "compat.install", {"event": event, "app": app, "sha256": sha256, **extra}
        )

    async def _await_verdict(self, sha256: str) -> Optional[dict]:
        deadline = time.monotonic() + VERDICT_TIMEOUT_S
        while time.monotonic() < deadline:
            try:
                frame = await asyncio.wait_for(
                    self.bus.next_frame(), timeout=max(0.1, deadline - time.monotonic())
                )
            except asyncio.TimeoutError:
                return None
            if frame is None:
                return None
            if frame["topic"] == "guard.verdict" and frame["body"]["sha256"] == sha256:
                return frame["body"]
        return None

    async def install(self, path: Path) -> str:
        """Run the pipeline; returns the terminal event name."""
        await self.bus.subscribe(["guard.verdict"])
        app = app_slug(path)
        # hashing + header read are blocking file I/O — keep them off the
        # event loop so the bus/other coroutines aren't stalled on a big installer.
        loop = asyncio.get_running_loop()
        sha = await loop.run_in_executor(None, sha256_file, path)
        fp = await loop.run_in_executor(None, fingerprint, path)
        await self._event(
            "fingerprinted", app, sha,
            path=str(path), installer=fp.installer, arch=fp.arch,
        )

        verdict = await self._await_verdict(sha)
        if verdict is None:
            # FAIL CLOSED (approved 2026-08-22): no verdict, no prefix.
            await self._event(
                "blocked", app, sha,
                error="screening unavailable — refusing to install (fail closed)",
            )
            return "blocked"
        await self._event("screened", app, sha)

        if verdict["verdict"] == "blocked":
            await self._event(
                "blocked", app, sha, error="; ".join(verdict["reasons"]) or "blocked",
            )
            return "blocked"
        if verdict["verdict"] == "suspicious":
            # Override path arrives with the HUD confirm surface; v0
            # refuses and says how it would be overridden.
            await self._event(
                "blocked", app, sha,
                error="suspicious: " + "; ".join(verdict["reasons"])
                + " (override requires explicit confirmation — not wired in v0)",
            )
            return "blocked"

        recipe = find_recipe(self.recipes, sha, fp.installer) or Recipe(
            app=app, match_sha256=[], match_installer=fp.installer
        )
        prefix = create_prefix_layout(recipe.app or app)
        await self._event("prefix_created", app, sha, recipe=recipe.app)

        if fp.installer == "msi":
            inner = ["msiexec", "/i", str(path), *silent_args("msi"), *recipe.extra_args]
        else:
            inner = ["wine", str(path), *silent_args(fp.installer), *recipe.extra_args]
        argv = bwrap_args(recipe, prefix, inner)
        ok, detail = await self.runner.install(argv)
        if ok:
            await self._event("installed", app, sha, recipe=recipe.app)
            return "installed"
        await self._event("failed", app, sha, error=detail[-500:])
        return "failed"
