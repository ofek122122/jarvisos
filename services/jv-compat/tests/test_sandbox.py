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

import ctypes
import fcntl
import os
import pty
import select
import shutil
import subprocess
import termios
from pathlib import Path

import pytest

from jv_compat.prefix import (
    SANDBOX_HOSTNAME,
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


def test_a_grant_whose_folder_is_not_there_aborts_the_whole_sandbox(home):
    """The premise the pre-flight refusal rests on, EXECUTED rather than
    assumed: `--bind` resolves its source on the host and bwrap exits before
    it execs anything if that source is missing. So a grant naming a folder
    the user does not have yet does not degrade the install — it kills it,
    after the screening, with a message about a path the user never typed.

    `bwrap_args` stays willing to build this argv on purpose (whether THIS
    machine can honour a recipe is the pipeline's question — `grant_problems`
    — not the argv's), which is the only reason the premise can be run at
    all rather than argued about."""
    gone = home / "Documents" / "AppSaves"
    gone.mkdir(parents=True)
    p = create_prefix_layout("demo")
    argv = bwrap_args(
        recipe(home_paths=["Documents/AppSaves"]), p, ["/bin/sh", "-c", "echo RAN-ANYWAY"]
    )
    gone.rmdir()  # ...and the grant is the ONLY thing that changed.
    r = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    assert r.returncode != 0, "bwrap accepted a bind of a source that is not there"
    assert "RAN-ANYWAY" not in r.stdout, "the inner command ran anyway"
    assert str(gone) in r.stderr, f"bwrap did not say which path: {r.stderr.strip()!r}"


def test_a_grant_may_name_a_single_file_and_the_app_can_read_it(home):
    """`grant_problems` refuses a grant that is ABSENT and says nothing
    about what kind of thing it is, which is a decision and not an
    oversight: a grant naming one file is NARROWER than one naming the
    folder around it, and bwrap binds either. Requiring a directory would
    refuse the more conservative recipe of the two."""
    (home / "Documents").mkdir()
    one = home / "Documents" / "settings.ini"
    one.write_text("theme=dark\n")
    (home / "Documents" / "tax-return.pdf").write_text("secret")
    p = create_prefix_layout("demo")
    r = sh(
        'read line < "$HOME/Documents/settings.ini"; echo "$line";'
        '[ -e "$HOME/Documents/tax-return.pdf" ] && echo SIBLING-LEAKED || echo sibling-hidden',
        recipe(home_paths=["Documents/settings.ini"]),
        p,
    )
    assert r.returncode == 0, f"{r.stdout.strip()} {r.stderr.strip()}"
    assert r.stdout.split() == ["theme=dark", "sibling-hidden"]


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


# --------------------------------------------- the terminal, the IPC namespace,
# --------------------------------------------- and the machine's name
#
# B63 left three bubblewrap flags out ON PURPOSE, with the reason written into
# the argv: they belong in it, and none of them could be OBSERVED by a suite
# that only knows how to run `/bin/sh` with pipes on both ends. A file that had
# just finished paying for a confinement whose claims nobody ran was not going
# to add three more. So each one lands here WITH the thing that watches it, and
# every claim below is paired with a CONTROL that runs the SAME probe against
# the SAME argv minus that one flag — because a fixture that cannot see the
# unsafe behaviour would report the safe one no matter what the code did.


def without(argv: list[str], *flags: str) -> list[str]:
    """The same argv with one confinement flag (and its value) removed.

    This is the control's whole mechanism, and the assertion at the end is
    load-bearing twice over: it is how a control proves it was really testing
    the absence of the flag, and it is what fails loudly if the flag ever
    leaves `bwrap_args`."""
    takes_a_value = {"--hostname": 1}
    out, i = [], 0
    while i < len(argv):
        if argv[i] in flags:
            i += 1 + takes_a_value.get(argv[i], 0)
            continue
        out.append(argv[i])
        i += 1
    assert len(out) < len(argv), f"{flags} is not in the confinement's argv at all"
    return out


def drain(master_fd: int) -> bytes:
    """Everything that reached the TERMINAL, then hang it up."""
    seen = b""
    try:
        while select.select([master_fd], [], [], 0.2)[0]:
            chunk = os.read(master_fd, 4096)
            if not chunk:
                break
            seen += chunk
    except OSError:
        pass  # EIO once the last slave fd is closed: the terminal is over
    finally:
        os.close(master_fd)
    return seen


def sh_on_a_tty(argv_tail: str, recipe_: Recipe, prefix: Path, *, drop=()):
    """Run the confinement with a REAL terminal on stdin — the way a human
    runs `jv-compat install`, which is a CLI (`main.py`), not only a unit —
    and hand back both what the sandbox printed and what reached the terminal.

    The child becomes the session leader and CLAIMS the pty before bwrap
    starts, so the terminal is genuinely its controlling one; inheriting
    pytest's (which in a headless run is none) would make the control vacuous.
    """
    argv = bwrap_args(recipe_, prefix, ["/bin/sh", "-c", argv_tail])
    if drop:
        argv = without(argv, *drop)
    master, slave = pty.openpty()

    def claim_the_terminal() -> None:  # in the child, before execvp
        os.setsid()
        fcntl.ioctl(slave, termios.TIOCSCTTY, 0)

    try:
        proc = subprocess.run(
            argv,
            stdin=slave,
            capture_output=True,
            text=True,
            timeout=60,
            preexec_fn=claim_the_terminal,
        )
    finally:
        os.close(slave)
    return proc, drain(master)


# What a process asks for when it wants the terminal it was started from,
# whatever that terminal is. Opening it is the capability; TIOCSTI is only the
# most famous thing to do with it (and is off on this kernel —
# `/proc/sys/dev/tty/legacy_tiocsti` is a host setting this repo does not own,
# so the door is what gets measured, not that one burglar).
REACH_FOR_THE_TERMINAL = (
    'if echo INJECTED-FROM-THE-SANDBOX > /dev/tty 2>/dev/null;'
    " then echo REACHED; else echo no-terminal; fi"
)


def test_the_sandbox_cannot_reach_the_terminal_the_install_was_started_from(home):
    """An untrusted Windows installer must not be able to touch the terminal
    the human is sitting at. With a controlling terminal it can write to it,
    and on a host with `legacy_tiocsti` on it can push characters into that
    terminal's INPUT — a command the user's shell runs after wine exits."""
    p = create_prefix_layout("demo")
    proc, terminal = sh_on_a_tty(REACH_FOR_THE_TERMINAL, recipe(), p)
    assert proc.stdout.strip() == "no-terminal", proc.stderr.strip()
    assert b"INJECTED" not in terminal, (
        "the confined process wrote to the human's terminal: " + repr(terminal)
    )


def test_the_terminal_probe_can_see_a_sandbox_that_does_reach_it(home):
    """The control, and it is the reason the test above means anything: the
    same probe, the same argv, `--new-session` alone removed — and the bytes
    arrive at the terminal."""
    p = create_prefix_layout("demo")
    proc, terminal = sh_on_a_tty(
        REACH_FOR_THE_TERMINAL, recipe(), p, drop=("--new-session",)
    )
    assert proc.stdout.strip() == "REACHED", proc.stderr.strip()
    assert b"INJECTED-FROM-THE-SANDBOX" in terminal


@pytest.fixture
def a_sysv_shm_segment():
    """One SysV shared-memory segment, owned by this test.

    The suite MAKES the thing it looks for rather than hoping the host has
    one, which is exactly why B63 refused to ship `--unshare-ipc` blind."""
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    IPC_PRIVATE, IPC_CREAT, IPC_RMID = 0, 0o1000, 0
    shmid = libc.shmget(IPC_PRIVATE, 4096, IPC_CREAT | 0o600)
    if shmid < 0:
        pytest.skip("this host would not give the test a SysV segment")
    try:
        yield shmid
    finally:
        libc.shmctl(shmid, IPC_RMID, None)


READ_THE_IPC_TABLE = 'while IFS= read -r l; do echo "$l"; done < /proc/sysvipc/shm'


def shm_ids(proc_sysvipc_shm: str) -> set[int]:
    ids = set()
    for line in proc_sysvipc_shm.splitlines()[1:]:  # drop the column header
        fields = line.split()
        if len(fields) >= 2 and fields[1].lstrip("-").isdigit():
            ids.add(int(fields[1]))
    return ids


def test_the_app_cannot_see_the_machines_shared_memory(home, a_sysv_shm_segment):
    """SysV IPC is a namespace, and a shared segment is a two-way channel
    with whatever else on this machine holds it. Default deny means the app
    gets its own empty one."""
    p = create_prefix_layout("demo")
    r = sh(READ_THE_IPC_TABLE, recipe(), p)
    assert r.returncode == 0, r.stderr
    assert a_sysv_shm_segment not in shm_ids(r.stdout)


def test_the_ipc_probe_can_see_a_segment_when_the_namespace_is_shared(
    home, a_sysv_shm_segment
):
    """The control: same segment, same reader, `--unshare-ipc` removed."""
    p = create_prefix_layout("demo")
    argv = without(bwrap_args(recipe(), p, ["/bin/sh", "-c", READ_THE_IPC_TABLE]),
                   "--unshare-ipc")
    r = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert a_sysv_shm_segment in shm_ids(r.stdout), (
        "the probe cannot see a segment it made even with the namespace shared"
    )


READ_THE_HOSTNAME = 'read h < /proc/sys/kernel/hostname; echo "$h"'


def test_the_app_does_not_learn_what_this_machine_is_called(home):
    """Every prefix is cattle (§08) and every app sees the same machine: one
    constant name, not `ares`. `--unshare-uts` is what makes `--hostname`
    possible, and the constant is what makes it WORTH doing — a Windows
    binary's first act is often to write down what it is running on."""
    p = create_prefix_layout("demo")
    real = Path("/proc/sys/kernel/hostname").read_text().strip()
    # Stated as a premise rather than assumed, because the whole claim rests
    # on it: a constant that HAPPENS to be this machine's name would make the
    # assertion below true and the confinement pointless.
    assert SANDBOX_HOSTNAME != real, (
        f"this machine is called {real!r} — the sandbox's constant must not be"
    )
    r = sh(READ_THE_HOSTNAME, recipe(), p)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == SANDBOX_HOSTNAME
    assert r.stdout.strip() != real


def test_the_hostname_probe_reads_the_real_one_without_the_namespace(home):
    """The control, and the honest half of the claim above: with the UTS
    namespace shared the same read returns what the host actually calls
    itself. (If that is already `SANDBOX_HOSTNAME`, this says less — which
    is a fact about the host, not a hole in the test.)"""
    p = create_prefix_layout("demo")
    argv = without(bwrap_args(recipe(), p, ["/bin/sh", "-c", READ_THE_HOSTNAME]),
                   "--unshare-uts", "--hostname")
    r = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == Path("/proc/sys/kernel/hostname").read_text().strip()
