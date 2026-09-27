"""pkgs/jv-power-menu — a themed lock/suspend/reboot/shut-down menu (PLAN H2).

`--dmenu` mode reads this script's four labels off stdin and, with no
`--config` flag, picks up the SAME `/etc/xdg/fuzzel/fuzzel.ini`
`modules/theme.nix` already declares for the plain Mod+D launcher, so there
is no second palette for this menu to keep in step.

"Boot Windows" is deliberately not one of the four options — see
pkgs/jv-power-menu/default.nix's own comment and PLAN H2b/docs/
optimization-backlog.md R12 for why that half needs a human decision.

Like test_scratchterm.py, the script is pulled straight out of
pkgs/jv-power-menu/default.nix's own `text` attribute and run against fake
`fuzzel`/`systemctl`/`jv-lock` stubs on PATH.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

from test_gen_theme_qml import ROOT

MODULE = ROOT / "pkgs" / "jv-power-menu" / "default.nix"
NIRI_MODULE = ROOT / "modules" / "niri.nix"


def module_src() -> str:
    return MODULE.read_text("utf-8")


def script_text() -> str:
    src = module_src()
    m = re.search(r"text = ''\n(.*?)\n  '';\n", src, re.S)
    assert m, "no text = '' ... ''; script body found in default.nix"
    return m.group(1).replace("''${", "${")


@pytest.fixture()
def script_path(tmp_path: Path) -> Path:
    p = tmp_path / "jv-power-menu"
    p.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + script_text() + "\n")
    p.chmod(0o755)
    return p


def stub_fuzzel(bindir: Path, *, answer: str | None, rc: int = 0) -> tuple[Path, Path]:
    """A fake `fuzzel --dmenu` answering with a fixed choice (or refusing,
    the way a real Escape-to-cancel exits non-zero with nothing printed)."""
    calls = bindir / "fuzzel-calls.txt"
    stdin_capture = bindir / "fuzzel-stdin.txt"
    stub = bindir / "fuzzel"
    body = [
        "#!/usr/bin/env bash",
        f'printf \'%s\\n\' "$*" >> {calls}',
        f"cat > {stdin_capture}",
    ]
    if answer is not None:
        body.append(f'printf \'%s\\n\' "{answer}"')
    body.append(f"exit {rc}")
    stub.write_text("\n".join(body) + "\n")
    stub.chmod(0o755)
    return calls, stdin_capture


def stub_recorder(bindir: Path, name: str) -> Path:
    calls = bindir / f"{name}-calls.txt"
    stub = bindir / name
    stub.write_text(f"#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >> {calls}\n")
    stub.chmod(0o755)
    return calls


class Rig:
    def __init__(self, script_path: Path, tmp_path: Path, *, answer: str | None, rc: int = 0):
        bindir = tmp_path / "bin"
        bindir.mkdir()
        self.fuzzel_calls, self.fuzzel_stdin = stub_fuzzel(bindir, answer=answer, rc=rc)
        self.systemctl_calls = stub_recorder(bindir, "systemctl")
        self.jvlock_calls = stub_recorder(bindir, "jv-lock")
        self.script_path = script_path

        self.env = dict(os.environ)
        self.env["PATH"] = f"{bindir}:{self.env.get('PATH', '')}"

    def run(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            [str(self.script_path)],
            env=self.env,
            capture_output=True,
            text=True,
        )

    def systemctl_argv(self) -> list[str]:
        if not self.systemctl_calls.exists():
            return []
        return self.systemctl_calls.read_text().splitlines()


def make_rig(script_path: Path, tmp_path: Path, *, answer: str | None, rc: int = 0) -> Rig:
    return Rig(script_path, tmp_path, answer=answer, rc=rc)


# ------------------------------------------------------------ behaviour


def test_lock_calls_jv_lock_and_nothing_else(script_path: Path, tmp_path: Path):
    rig = make_rig(script_path, tmp_path, answer="Lock")

    result = rig.run()

    assert result.returncode == 0, result.stderr
    assert rig.jvlock_calls.exists(), "never called jv-lock"
    assert not rig.systemctl_calls.exists(), "lock should never touch systemctl"


def test_suspend_calls_systemctl_suspend(script_path: Path, tmp_path: Path):
    rig = make_rig(script_path, tmp_path, answer="Suspend")

    result = rig.run()

    assert result.returncode == 0, result.stderr
    assert rig.systemctl_argv() == ["suspend"]
    assert not rig.jvlock_calls.exists()


def test_reboot_calls_systemctl_reboot(script_path: Path, tmp_path: Path):
    rig = make_rig(script_path, tmp_path, answer="Reboot")

    result = rig.run()

    assert result.returncode == 0, result.stderr
    assert rig.systemctl_argv() == ["reboot"]


def test_shut_down_calls_systemctl_poweroff(script_path: Path, tmp_path: Path):
    rig = make_rig(script_path, tmp_path, answer="Shut Down")

    result = rig.run()

    assert result.returncode == 0, result.stderr
    assert rig.systemctl_argv() == ["poweroff"]


def test_cancelling_the_menu_does_nothing(script_path: Path, tmp_path: Path):
    # Escape in a real dmenu exits non-zero with nothing on stdout.
    rig = make_rig(script_path, tmp_path, answer=None, rc=1)

    result = rig.run()

    assert result.returncode == 0, result.stderr
    assert not rig.systemctl_calls.exists()
    assert not rig.jvlock_calls.exists()


def test_an_unrecognised_answer_does_nothing(script_path: Path, tmp_path: Path):
    rig = make_rig(script_path, tmp_path, answer="Something Else")

    result = rig.run()

    assert result.returncode == 0, result.stderr
    assert not rig.systemctl_calls.exists()
    assert not rig.jvlock_calls.exists()


def test_the_four_options_are_offered_in_order(script_path: Path, tmp_path: Path):
    rig = make_rig(script_path, tmp_path, answer="Lock")

    rig.run()

    offered = rig.fuzzel_stdin.read_text().splitlines()
    assert offered == ["Lock", "Suspend", "Reboot", "Shut Down"]


def test_fuzzel_is_invoked_in_dmenu_mode(script_path: Path, tmp_path: Path):
    rig = make_rig(script_path, tmp_path, answer="Lock")

    rig.run()

    argv = rig.fuzzel_calls.read_text()
    assert "--dmenu" in argv


# --------------------------------------------------------------- static


def test_never_invokes_a_boot_loader_tool():
    # "Boot Windows" is deliberately not built here — see PLAN H2b — so
    # nothing in this script should reach for a way to pick it either.
    src = script_text()
    for forbidden in ("grub-reboot", "efibootmgr", "grub-set-default", "shutdown", "loginctl", "halt"):
        assert forbidden not in src, f"unexpected reference to {forbidden!r}"


def test_never_names_windows():
    assert "Windows" not in script_text()


def test_the_menu_spawn_name_is_the_one_niri_config_binds():
    niri_src = NIRI_MODULE.read_text("utf-8")
    assert 'spawn "jv-power-menu"' in niri_src
    assert "jv-power-menu" in module_src()
