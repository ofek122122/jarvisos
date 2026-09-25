"""Prefix layout + bubblewrap confinement (blueprint §08: one prefix
per app, cattle not pets; Wine is not a sandbox — bwrap is).

Confinement is DEFAULT DENY: no network, no real home. A recipe grants
exactly what an app needs, and only a reviewed recipe commit can widen
a grant (invariant 8).

THE SANDBOX'S VIEW IS FIXED, THE HOST'S IS NOT. The prefix and the
installer are bound at constant paths under `/jarvis`, chosen so that
what the app sees never depends on where this machine keeps its files.
That is not tidiness: the first version bound the prefix at its own host
path and then bound the app's private home over `$HOME`, and because
`prefixes_root()` puts every prefix UNDER `$HOME`, the second mount hid
the first — `$WINEPREFIX` named a path that did not exist inside. A
constant destination outside `$HOME` makes that whole class impossible
rather than merely fixed. `tests/test_sandbox.py` enters the sandbox and
asks a shell what it can see; both bugs were argv-invisible.

WHAT AN UNTRUSTED APP GETS TO READ. This is NixOS, so the FHS is a
rumour: `/usr` holds one file, `/bin` is a symlink to bash, and every
binary on the machine — wine included — is in `/nix/store`, which is
world-readable by design. The read-only set is therefore the store, the
machine's `/etc`, whatever FHS stubs exist, and the system profile that
resolves a bare `wine` on `PATH`. Nothing writable is shared except the
prefix and what a recipe explicitly grants.

WHAT IT DOES NOT GET, BEYOND FILES. Its own PID, IPC and UTS namespaces,
no network unless granted, and — because a human runs `jv-compat install`
from a shell — no controlling terminal. Every one of those is executed in
`tests/test_sandbox.py`, each against a CONTROL that runs the same probe
with that single flag removed: B63 found two fatal bugs in an argv that
had been read many times and entered never, so a flag here lands with the
thing that watches it or does not land.
"""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

from .recipes import Recipe

# Where the app sees its own two things, always.
SANDBOX_PREFIX = PurePosixPath("/jarvis/prefix")
SANDBOX_INSTALLER_DIR = PurePosixPath("/jarvis/installer")

# What the app thinks this computer is called. One constant for every prefix:
# a Windows binary that writes down its host writes down the same nothing
# every time, and `ares` is not an untrusted installer's business.
SANDBOX_HOSTNAME = "jarvis-sandbox"

# Read-only host paths, bound if they exist. Order is irrelevant — none of
# them is inside another — but existence is not: `--ro-bind` on a missing
# source aborts the sandbox, and these differ between NixOS and everything
# else.
SYSTEM_RO = (
    "/nix",  # every binary on this machine, wine's included
    "/etc",
    "/bin",  # NixOS: one symlink, and it is /bin/sh
    "/lib",
    "/lib64",  # the FHS loader stub
    "/usr",
    "/run/current-system/sw",  # what resolves a bare `wine` on PATH
)


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


def sandbox_installer_path(installer: Path) -> PurePosixPath:
    """Where the file being installed appears INSIDE the confinement.

    The name is kept: wine and msiexec both dispatch on the extension, and
    an installer that can read its own filename is reading something it
    already knew. The directory is not kept — the app has no business
    learning where on this disk the user keeps downloads."""
    name = installer.name
    if not name or name in (".", ".."):
        raise ValueError(f"cannot install a path with no filename: {installer}")
    return SANDBOX_INSTALLER_DIR / name


def grant_dest(home: Path, rel: str) -> Path:
    """Join one `home_paths` grant onto the home, refusing a grant whose
    WORDS leave the private home.

    `home / rel` was taken on trust. `home_paths = ["."]` therefore mounted
    the user's whole home over the app's private one — invariant 8 inverted
    by one line of TOML — and `["../.."]` reached past it entirely. Recipes
    are reviewed like code, which is a reason to catch a mistake, not a
    reason to assume there will not be one.

    WHAT THIS DOES NOT BOUND (PLAN B66). It reads the recipe's words and
    nothing else — it is pure, it is asked by `bwrap_args` on a machine it
    knows nothing about, and the path it returns is under `home` by
    construction. What that path RESOLVES to is a fact about the user's
    home, not about the recipe, and `--bind` resolves its source for real:
    if `~/Documents` is a symlink, the grant is exactly as wide as whatever
    it points at. That question belongs to `grant_problems`, which is where
    a recipe meets a machine, and it is asked there."""
    p = PurePosixPath(rel)
    if p.is_absolute() or ".." in p.parts or not p.parts:
        raise ValueError(
            f"recipe grant {rel!r} leaves the app's private home; a grant is a "
            "relative path under it, with no '..' components"
        )
    return home / p


def grant_problems(recipe: Recipe) -> list[str]:
    """Every reason THIS machine cannot honour this recipe's grants, one
    sentence each — empty if it can. Asked before any work is done.

    A grant is a fact about two things: the recipe (reviewed, in this repo)
    and the user's home (not this repo's business). `--bind` resolves its
    SOURCE on the host, so a grant naming a folder that is not there does not
    degrade the install, it ABORTS it — bwrap exits before exec, and until
    this gate existed its message reached the user through a `failed` frame
    after screening and after the prefix had been built, about a path they
    never typed. `tests/test_sandbox.py` executes that premise.

    THE REFUSAL IS THE DECISION (PLAN B65), and the three ways out are not
    equal:

      * `--bind-try` is the quiet one and it is worse. The app finds an empty
        folder — indistinguishable from "no saves yet" — writes into its
        private home instead, and the user's real folder stays empty. The
        failure then surfaces days later as missing work, which is the worst
        possible place for it.
      * Creating it is forbidden: only `jv-act` writes outside a service's
        own state dir (invariant 3), and `~/Documents/MyAppSaves` is the
        user's. Routing it through jv-act would put a second confirmation
        into an install that already has one, for something one `mkdir`
        fixes.
      * So: refuse, name the absolute path, and say what fixes it.

    NOT at recipe-DB load, which is where B65 first guessed this belonged: a
    recipe for an app nobody is installing must not stop `find_recipe` from
    answering about the one that is. A grant's absence is a fact about this
    machine, checked where the recipe meets it.

    `exists()` FOLLOWS symlinks, deliberately, because `--bind` does: a grant
    pointing at a broken link is absent to bwrap and has to be absent here.
    Nothing is said about what KIND of thing it is — a grant naming one file
    is narrower than one naming the folder around it, and bwrap binds either,
    so demanding a directory would refuse the more conservative recipe. And
    nothing here closes the window between this answer and the exec: a folder
    deleted inside it is a raw bwrap error again, which is a race worth a
    sentence and not machinery.

    A GRANT IS AS WIDE AS WHAT IT RESOLVES TO (PLAN B66), and following the
    links in B65 is what made that sayable. `grant_dest` bounds the recipe's
    WORDS; bwrap resolves the source. So `home_paths = ["Documents"]` on a
    home where `~/Documents` is a symlink to `/` binds the whole machine,
    read-write, into an untrusted Wine prefix — executed in
    `tests/test_sandbox.py`, not argued.

    The obvious fix is WRONG and that is the whole difficulty: a user whose
    `~/Documents` genuinely lives on another disk is an ordinary setup, and
    refusing every grant that resolves outside the home refuses it. So the
    refusal here is drawn at the only line that needs no judgement — a grant
    resolving to the real home ITSELF, or to an ancestor of it. That is not a
    new policy, it is the EXISTING one arriving by a different road: `["."]`
    and `["../.."]` are refused as words, and a symlink says the same two
    things on this machine. Nothing legitimate needs to grant an app the home
    the confinement just covered.

    What is deliberately still ACCEPTED is a grant resolving to a sibling of
    the home (another disk, `/etc`, another app's prefix). Refusing those
    means choosing a property — "the user owns it", say — and every candidate
    refuses some real setup, so it is a decision with a human in it and not a
    patch. Until then the width is documented in `recipes/README.md` and a
    reviewer of a recipe is reviewing the user's symlinks with it.
    """
    home = Path.home()
    home_real = home.resolve()
    problems: list[str] = []
    for rel in recipe.home_paths:
        try:
            dest = grant_dest(home, rel)
        except ValueError as exc:
            problems.append(str(exc))
            continue
        if not dest.exists():
            problems.append(
                f"grant {rel!r} names {dest}, which is not on this machine — "
                "create it, or have the recipe grant one that exists, noting "
                "that a parent grants more than the folder asked for"
            )
            continue
        dest_real = dest.resolve()
        if home_real == dest_real or home_real.is_relative_to(dest_real):
            problems.append(
                f"grant {rel!r} names {dest}, which resolves to {dest_real} — "
                "the user's real home, or a parent of it, so binding it would "
                "put the whole home back over the app's private one. That is "
                "the grant '.' refuses, reaching the same place through a "
                "symlink instead of through the recipe's words"
            )
    return problems


def bwrap_args(
    recipe: Recipe,
    prefix: Path,
    extra_cmd: list[str],
    installer: Path | None = None,
) -> list[str]:
    """Build the bubblewrap argv confining one Wine invocation.

    `installer` is the file being installed on the HOST; it is bound
    read-only at `sandbox_installer_path(installer)`, which is the path the
    inner command must name.
    """
    home = Path.home()
    args = [
        "bwrap",
        "--die-with-parent",
        "--unshare-pid",
        # The terminal the human started this from is NOT the app's. Without
        # a session of its own the confined process inherits the controlling
        # terminal, can write to it, and on a kernel with `legacy_tiocsti` on
        # can push characters into its INPUT — a command the user's shell
        # runs the moment wine exits. `jv-compat install` is a CLI a human
        # runs from a terminal (main.py), so this is not hypothetical. It
        # costs nothing here because RealRunner pipes both streams and the
        # install is silent: nothing inside ever wanted a tty.
        "--new-session",
        # SysV shared memory is a two-way channel with anything else on this
        # machine holding a segment. Default deny means an empty table.
        "--unshare-ipc",
        # ...and the app is told the same nothing about this computer that
        # every other prefix is told.
        "--unshare-uts", "--hostname", SANDBOX_HOSTNAME,
        "--proc", "/proc",
        "--dev", "/dev",
    ]
    for ro in SYSTEM_RO:
        if os.path.exists(ro):
            args += ["--ro-bind", ro, ro]
    args += ["--tmpfs", "/tmp"]
    # The private home goes on FIRST, at the user's own home path: it covers
    # the real one, and everything bound afterwards stays reachable through
    # it. Nothing the app needs is mounted under it by default.
    args += ["--bind", str(prefix / "home"), str(home), "--setenv", "HOME", str(home)]
    # ...and the app's disk goes somewhere this cannot reach.
    args += ["--bind", str(prefix), str(SANDBOX_PREFIX)]
    if installer is not None:
        args += ["--ro-bind", str(installer), str(sandbox_installer_path(installer))]
    if not recipe.network:
        args += ["--unshare-net"]
    for rel in recipe.home_paths:
        dest = grant_dest(home, rel)
        args += ["--bind", str(dest), str(dest)]
    args += ["--setenv", "WINEPREFIX", str(SANDBOX_PREFIX)]
    return args + extra_cmd
