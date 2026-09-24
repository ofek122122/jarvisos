"""Invariant 8's confinement, EXECUTED — the first tests in this repo that
actually run `bwrap`.

`bwrap_args` has been argv-shaped since Phase 2 and `RealRunner` says
`TODO(machine)`, so the sandbox this whole service is built around had
never once been entered. The two tests it did have built it around
`Path("/prefixes/x")` and `Path("/p")` — paths the code cannot produce,
because `prefixes_root()` puts every prefix under `$HOME` — and asserted
three strings were present. Everything a sandbox is for was unasserted.

Running it found two failures, both fatal, neither visible in an argv:

  1. `--symlink usr/bin /bin` is an FHS distro's layout. This machine is
     NixOS: `/usr` holds exactly one file (`bin/env`), `/bin` is a single
     symlink to bash, and every real binary — wine included — lives in
     `/nix/store`. The sandbox therefore had no `/bin/sh` and could not
     execvp anything at all.
  2. The prefix was bound at its own host path and the app's private home
     was then bound over `$HOME` — and the prefix lives UNDER `$HOME`, so
     the second mount hid the first. `$WINEPREFIX` pointed at a path that
     does not exist inside the sandbox.

Both are argv-invisible and both are caught by starting the thing. So
these tests execute: they run a real `/bin/sh` inside the real sandbox and
ask it what it can see. The inner script is POSIX shell using builtins
only (`[ -e ]`, `read`, `echo`, globs) — no coreutils — so a sandbox that
does not bind the system profile is still measurable.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from jv_compat.prefix import (
    SANDBOX_PREFIX,
    bwrap_args,
    create_prefix_layout,
    sandbox_installer_path,
)
from jv_compat.recipes import Recipe

pytestmark = pytest.mark.skipif(
    not shutil.which("bwrap") or not os.path.exists("/bin/sh"),
    reason="needs bubblewrap and a host /bin/sh (ares has both — "
    "modules/windows-compat.nix installs bubblewrap)",
)


def recipe(**kw) -> Recipe:
    kw.setdefault("app", "demo")
    kw.setdefault("match_sha256", [])
    kw.setdefault("match_installer", "")
    return Recipe(**kw)


@pytest.fixture
def home(tmp_path, monkeypatch) -> Path:
    """A real home for the user, laid out the way ares is: the prefix root
    is UNDER it, which is the case the old tests' `/prefixes/x` could not
    express and the one the shadowing bug needed."""
    h = tmp_path / "home" / "user"
    h.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.delenv("JARVIS_PREFIXES_DIR", raising=False)
    return h


def setenv(argv: list[str], name: str) -> str:
    """The value of one `--setenv NAME VALUE` in the argv (there are several,
    so an `index("--setenv")` reads whichever comes first)."""
    for i, a in enumerate(argv):
        if a == "--setenv" and argv[i + 1] == name:
            return argv[i + 2]
    raise AssertionError(f"{name} is never set in the sandbox")


def sh(argv_tail: str, recipe_: Recipe, prefix: Path, installer=None):
    """Run one POSIX shell inside the confinement and hand back what it saw."""
    argv = bwrap_args(recipe_, prefix, ["/bin/sh", "-c", argv_tail], installer=installer)
    return subprocess.run(argv, capture_output=True, text=True, timeout=60)


# --------------------------------------------- it starts at all


def test_the_confinement_can_start_a_process_on_this_machine(home):
    """The whole service rests on this and nothing asserted it."""
    p = create_prefix_layout("demo")
    r = sh("echo alive", recipe(), p)
    assert r.returncode == 0, f"the sandbox did not start: {r.stderr.strip()}"
    assert r.stdout.strip() == "alive"


# --------------------------------------------- the app's own prefix


def test_the_app_can_reach_and_write_the_prefix_wineprefix_names(home):
    """`$WINEPREFIX` must name a directory that exists INSIDE, and writes
    to it must land in the real prefix on the host — it is the app's disk."""
    p = create_prefix_layout("demo")
    r = sh(
        '[ -d "$WINEPREFIX/drive_c" ] || { echo NO-DRIVE-C; exit 3; };'
        'echo written > "$WINEPREFIX/drive_c/probe" || { echo READ-ONLY; exit 4; };'
        "echo ok",
        recipe(),
        p,
    )
    assert r.returncode == 0, f"{r.stdout.strip()} {r.stderr.strip()}"
    assert (p / "drive_c" / "probe").read_text().strip() == "written"


def test_the_prefixs_place_in_the_sandbox_does_not_depend_on_the_host(home):
    """A fixed sandbox path is what makes the shadowing bug unrepeatable:
    wherever this machine keeps prefixes, the app sees one place, and it is
    not under `$HOME`, so the private-home mount can never cover it."""
    p = create_prefix_layout("demo")
    argv = bwrap_args(recipe(), p, ["true"])
    assert setenv(argv, "WINEPREFIX") == str(SANDBOX_PREFIX)
    assert str(home) not in str(SANDBOX_PREFIX)


# --------------------------------------------- the installer itself


def test_the_installer_the_argv_names_is_readable_inside(home, tmp_path):
    """`install()` puts the installer's path in the inner argv. Nothing
    bound the file, so wine was being handed a path to a file the sandbox
    could not see — and the only test of the pipeline used a MockRunner,
    which never opens anything."""
    src = tmp_path / "Setup_x64.exe"
    src.write_bytes(b"MZ-not-really")
    p = create_prefix_layout("demo")
    inside = sandbox_installer_path(src)
    r = sh(
        f'[ -r "{inside}" ] || {{ echo UNREACHABLE; exit 3; }};'
        f'read line < "{inside}"; echo "$line"',
        recipe(),
        p,
        installer=src,
    )
    assert r.returncode == 0, f"{r.stdout.strip()} {r.stderr.strip()}"
    assert r.stdout.strip() == "MZ-not-really"


def test_the_installer_is_read_only_inside(home, tmp_path):
    """It is evidence, and jv-guard's verdict is about the bytes that were
    hashed. An app that can rewrite its own installer invalidates both."""
    src = tmp_path / "Setup_x64.exe"
    src.write_bytes(b"MZ-not-really")
    p = create_prefix_layout("demo")
    inside = sandbox_installer_path(src)
    r = sh(f'echo tampered > "{inside}" 2>/dev/null && echo WRITABLE || echo refused',
           recipe(), p, installer=src)
    assert r.stdout.strip() == "refused"
    assert src.read_bytes() == b"MZ-not-really"


# --------------------------------------------- the user's home


def test_home_is_the_apps_private_one_and_not_the_users(home):
    """DEFAULT DENY, executed: the app's `$HOME` shows what is in the
    prefix's `home/`, and the user's own files are not there."""
    (home / "tax-return.pdf").write_text("secret")
    p = create_prefix_layout("demo")
    (p / "home" / "marker").write_text("private")
    r = sh(
        'for f in "$HOME"/* ; do echo "${f##*/}" ; done',
        recipe(),
        p,
    )
    assert r.returncode == 0, r.stderr
    seen = set(r.stdout.split())
    assert "marker" in seen, "the app's private home is not mounted at $HOME"
    assert "tax-return.pdf" not in seen, "the user's home leaked into the sandbox"


def test_a_granted_home_path_is_the_users_real_directory(home):
    """A grant is the only way in, and it must reach the REAL folder —
    a grant that mounted a private copy would silently lose the user's work."""
    (home / "Documents").mkdir()
    (home / "Documents" / "AppSaves").mkdir()
    (home / "Documents" / "AppSaves" / "save.dat").write_text("level-9")
    (home / "Documents" / "tax-return.pdf").write_text("secret")
    p = create_prefix_layout("demo")
    r = sh(
        'read line < "$HOME/Documents/AppSaves/save.dat"; echo "$line";'
        '[ -e "$HOME/Documents/tax-return.pdf" ] && echo SIBLING-LEAKED || echo sibling-hidden',
        recipe(home_paths=["Documents/AppSaves"]),
        p,
    )
    assert r.returncode == 0, f"{r.stdout.strip()} {r.stderr.strip()}"
    assert r.stdout.split() == ["level-9", "sibling-hidden"]


@pytest.mark.parametrize(
    "bad", ["..", "../..", "../../etc", "/etc", "", ".", "Documents/../../.ssh"]
)
def test_a_grant_that_leaves_the_private_home_is_refused(home, bad):
    """`home_paths` was joined onto `Path.home()` and bound with no check
    at all, so a recipe reading `home_paths = ["."]` mounted the user's
    entire home over the private one — invariant 8 inverted by one line of
    TOML. Recipes are reviewed, which is a reason to catch this, not a
    reason to assume it."""
    p = create_prefix_layout("demo")
    with pytest.raises(ValueError, match="grant"):
        bwrap_args(recipe(home_paths=[bad]), p, ["true"])


# --------------------------------------------- the network


def ifaces(proc_net_dev: str) -> set[str]:
    out = set()
    for line in proc_net_dev.splitlines()[2:]:
        name, _, _ = line.partition(":")
        if name.strip():
            out.add(name.strip())
    return out


def test_denying_the_network_leaves_only_loopback(home):
    """`--unshare-net` was asserted as a STRING. This asks the kernel."""
    p = create_prefix_layout("demo")
    r = sh(
        'while IFS= read -r l; do echo "$l"; done < /proc/net/dev',
        recipe(),
        p,
    )
    assert r.returncode == 0, r.stderr
    assert ifaces(r.stdout) == {"lo"}


def test_granting_the_network_gives_the_app_this_machines(home):
    """The grant is real and not cosmetic: the app sees exactly the
    interfaces the host has. (On a host with only `lo` this says the same
    thing as the test above — which is honest, not vacuous: the claim is
    equality with the host, whatever the host is.)"""
    p = create_prefix_layout("demo")
    r = sh(
        'while IFS= read -r l; do echo "$l"; done < /proc/net/dev',
        recipe(network=True),
        p,
    )
    assert r.returncode == 0, r.stderr
    assert ifaces(r.stdout) == ifaces(Path("/proc/net/dev").read_text())


# --------------------------------------------- nothing else is exposed


def test_nothing_is_bound_that_the_confinement_did_not_name(home, tmp_path):
    """A whitelist, so a bind added later has to be argued for here. Every
    destination is a read-only system path, the app's own two places, or a
    path under the private home (which is where a grant lands)."""
    src = tmp_path / "Setup.exe"
    src.write_bytes(b"MZ")
    p = create_prefix_layout("demo")
    argv = bwrap_args(
        recipe(home_paths=["Documents/AppSaves"]), p, ["true"], installer=src
    )
    allowed_roots = ("/nix", "/etc", "/bin", "/lib", "/lib64", "/usr", "/run/current-system/sw")
    dests = [
        argv[i + 2]
        for i, a in enumerate(argv)
        if a in ("--bind", "--ro-bind", "--dev-bind")
    ]
    assert dests, "no binds at all"
    for d in dests:
        ok = (
            d.startswith(str(SANDBOX_PREFIX))
            or d.startswith("/jarvis/")
            or d == str(home)
            or d.startswith(str(home) + "/")
            or any(d == r or d.startswith(r + "/") for r in allowed_roots)
        )
        assert ok, f"{d} is bound into an untrusted app's sandbox and nothing says why"
