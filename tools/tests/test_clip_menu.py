"""pkgs/jv-clip-menu — a themed clipboard-history picker over cliphist
(PLAN H3, the first "super-menu mode").

Like test_power_menu.py, the script is pulled straight out of
pkgs/jv-clip-menu/default.nix's own `text` attribute and run against fake
`cliphist`/`fuzzel`/`wl-copy` stubs on PATH. The picker never calls
`wl-paste` itself — that daemon (modules/clipboard.nix) is what fills
cliphist's store; this script only reads it.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

from test_gen_theme_qml import ROOT

MODULE = ROOT / "pkgs" / "jv-clip-menu" / "default.nix"
NIRI_MODULE = ROOT / "modules" / "niri.nix"

ENTRIES = ["1\tHello world", "2\tSecond item"]


def module_src() -> str:
    return MODULE.read_text("utf-8")


def script_text() -> str:
    src = module_src()
    m = re.search(r"text = ''\n(.*?)\n  '';\n", src, re.S)
    assert m, "no text = '' ... ''; script body found in default.nix"
    return m.group(1).replace("''${", "${")


@pytest.fixture()
def script_path(tmp_path: Path) -> Path:
    p = tmp_path / "jv-clip-menu"
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


def stub_cliphist(bindir: Path, *, entries: list[str]) -> tuple[Path, Path]:
    """A fake `cliphist`: `list` prints a fixed history, `decode` echoes
    "decoded:<stdin>" and records the exact bytes it was fed on stdin — the
    picker must hand it the WHOLE selected line (id and all), not just the
    human-readable preview after the tab."""
    calls = bindir / "cliphist-calls.txt"
    decode_stdin = bindir / "cliphist-decode-stdin.txt"
    stub = bindir / "cliphist"
    entries_block = "\n".join(entries)
    stub.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                f'printf \'%s\\n\' "$*" >> {calls}',
                'case "$1" in',
                "  list)",
                f"    printf '%s\\n' {shell_quote(entries_block)}",
                "    ;;",
                "  decode)",
                "    input=$(cat)",
                f'    printf \'%s\' "$input" > {decode_stdin}',
                '    printf \'decoded:%s\' "$input"',
                "    ;;",
                "esac",
            ]
        )
        + "\n"
    )
    stub.chmod(0o755)
    return calls, decode_stdin


def shell_quote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


def stub_recorder(bindir: Path, name: str) -> tuple[Path, Path]:
    calls = bindir / f"{name}-calls.txt"
    stdin_capture = bindir / f"{name}-stdin.txt"
    stub = bindir / name
    stub.write_text(
        f"#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >> {calls}\ncat > {stdin_capture}\n"
    )
    stub.chmod(0o755)
    return calls, stdin_capture


class Rig:
    def __init__(self, script_path: Path, tmp_path: Path, *, answer: str | None, rc: int = 0):
        bindir = tmp_path / "bin"
        bindir.mkdir()
        self.fuzzel_calls, self.fuzzel_stdin = stub_fuzzel(bindir, answer=answer, rc=rc)
        self.cliphist_calls, self.cliphist_decode_stdin = stub_cliphist(bindir, entries=ENTRIES)
        self.wlcopy_calls, self.wlcopy_stdin = stub_recorder(bindir, "wl-copy")
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

    def cliphist_argv(self) -> list[str]:
        if not self.cliphist_calls.exists():
            return []
        return self.cliphist_calls.read_text().splitlines()


def make_rig(script_path: Path, tmp_path: Path, *, answer: str | None, rc: int = 0) -> Rig:
    return Rig(script_path, tmp_path, answer=answer, rc=rc)


# ------------------------------------------------------------ behaviour


def test_selecting_an_entry_decodes_it_and_copies_the_result(script_path: Path, tmp_path: Path):
    rig = make_rig(script_path, tmp_path, answer=ENTRIES[0])

    result = rig.run()

    assert result.returncode == 0, result.stderr
    assert rig.cliphist_decode_stdin.read_text() == ENTRIES[0]
    assert rig.wlcopy_stdin.read_text() == f"decoded:{ENTRIES[0]}"


def test_cancelling_the_menu_does_nothing(script_path: Path, tmp_path: Path):
    # Escape in a real dmenu exits non-zero with nothing on stdout.
    rig = make_rig(script_path, tmp_path, answer=None, rc=1)

    result = rig.run()

    assert result.returncode == 0, result.stderr
    assert rig.cliphist_argv() == ["list"], "decode must never run on a cancelled menu"
    assert not rig.wlcopy_calls.exists()


def test_an_empty_selection_does_nothing(script_path: Path, tmp_path: Path):
    rig = make_rig(script_path, tmp_path, answer="", rc=0)

    result = rig.run()

    assert result.returncode == 0, result.stderr
    assert rig.cliphist_argv() == ["list"]
    assert not rig.wlcopy_calls.exists()


def test_history_is_listed_before_the_menu_is_shown(script_path: Path, tmp_path: Path):
    rig = make_rig(script_path, tmp_path, answer=ENTRIES[1])

    rig.run()

    offered = rig.fuzzel_stdin.read_text().splitlines()
    assert offered == ENTRIES


def test_fuzzel_is_invoked_in_dmenu_mode(script_path: Path, tmp_path: Path):
    rig = make_rig(script_path, tmp_path, answer=ENTRIES[0])

    rig.run()

    argv = rig.fuzzel_calls.read_text()
    assert "--dmenu" in argv


# --------------------------------------------------------------- static


def test_never_uses_an_x11_clipboard_tool():
    # CLAUDE.md: "Wayland only, never X11-first" — wl-copy, never xclip/xsel.
    src = script_text()
    for forbidden in ("xclip", "xsel", "xdotool"):
        assert forbidden not in src, f"unexpected reference to {forbidden!r}"


def test_never_calls_wl_paste():
    # wl-paste is the STORE daemon's job (modules/clipboard.nix); the picker
    # only ever lists/decodes/copies, or every keypress would clip itself.
    assert "wl-paste" not in script_text()


def test_the_menu_spawn_name_is_the_one_niri_config_binds():
    niri_src = NIRI_MODULE.read_text("utf-8")
    assert 'spawn "jv-clip-menu"' in niri_src
    assert "jv-clip-menu" in module_src()
