"""Prefix layout + bubblewrap confinement (blueprint §08: one prefix
per app, cattle not pets; Wine is not a sandbox — bwrap is).

Confinement is DEFAULT DENY: no network, no real home. A recipe grants
exactly what an app needs, and only a reviewed recipe commit can widen
a grant (invariant 8)."""

from __future__ import annotations

import os
from pathlib import Path

from .recipes import Recipe


def prefixes_root() -> Path:
    if env := os.environ.get("JARVIS_PREFIXES_DIR"):
        return Path(env)
    return Path.home() / ".local" / "share" / "jarvis" / "prefixes"


def prefix_dir(app: str) -> Path:
    return prefixes_root() / app


def create_prefix_layout(app: str) -> Path:
    """Directory skeleton only — wineboot runs through the Runner (and
    only on the machine)."""
    p = prefix_dir(app)
    (p / "drive_c").mkdir(parents=True, exist_ok=True)
    (p / "home").mkdir(parents=True, exist_ok=True)  # the app's fake home
    return p


def bwrap_args(recipe: Recipe, prefix: Path, extra_cmd: list[str]) -> list[str]:
    """Build the bubblewrap argv confining one Wine invocation.

    TODO(machine): argv construction is tested; actually spawning bwrap
    happens only on ares (exit item 5).
    """
    args = [
        "bwrap",
        "--die-with-parent",
        "--unshare-pid",
        "--proc", "/proc",
        "--dev", "/dev",
        "--ro-bind", "/usr", "/usr",
        "--ro-bind", "/etc", "/etc",
        "--ro-bind", "/nix", "/nix",  # store paths for wine itself
        "--symlink", "usr/bin", "/bin",
        "--symlink", "usr/lib", "/lib64",
        "--tmpfs", "/tmp",
        # the app sees ONLY its prefix and its private fake home
        "--bind", str(prefix), str(prefix),
        "--bind", str(prefix / "home"), str(Path.home()),
    ]
    if not recipe.network:
        args += ["--unshare-net"]
    for rel in recipe.home_paths:
        real = Path.home() / rel
        args += ["--bind", str(real), str(Path.home() / rel)]
    args += ["--setenv", "WINEPREFIX", str(prefix)]
    return args + extra_cmd
