"""pkgs/jv-emoji-menu — a themed emoji picker over a curated table
(PLAN H3b, the second "super-menu mode").

Like test_clip_menu.py, the script is pulled straight out of
pkgs/jv-emoji-menu/default.nix's own `text` attribute and run against fake
`fuzzel`/`wl-copy` stubs on PATH. Unlike H3a there is no daemon and no
"decode" step: fuzzel already hands back the exact line offered to it, and
the picker only needs to keep the glyph before the first space.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

from test_gen_theme_qml import ROOT

MODULE = ROOT / "pkgs" / "jv-emoji-menu" / "default.nix"
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
    p = tmp_path / "jv-emoji-menu"
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


def make_rig(script_path: Path, tmp_path: Path, *, answer: str | None, rc: int = 0) -> Rig:
    return Rig(script_path, tmp_path, answer=answer, rc=rc)


# ------------------------------------------------------------ behaviour


def test_selecting_an_entry_copies_only_the_glyph(script_path: Path, tmp_path: Path):
    rig = make_rig(script_path, tmp_path, answer="😀 grinning face")

    result = rig.run()

    assert result.returncode == 0, result.stderr
    assert rig.wlcopy_stdin.read_text() == "😀"


def test_a_multi_word_name_still_yields_only_the_glyph(script_path: Path, tmp_path: Path):
    rig = make_rig(script_path, tmp_path, answer="🤣 rolling on the floor laughing")

    rig.run()

    assert rig.wlcopy_stdin.read_text() == "🤣"


def test_cancelling_the_menu_does_nothing(script_path: Path, tmp_path: Path):
    # Escape in a real dmenu exits non-zero with nothing on stdout.
    rig = make_rig(script_path, tmp_path, answer=None, rc=1)

    result = rig.run()

    assert result.returncode == 0, result.stderr
    assert not rig.wlcopy_calls.exists()


def test_an_empty_selection_does_nothing(script_path: Path, tmp_path: Path):
    rig = make_rig(script_path, tmp_path, answer="", rc=0)

    result = rig.run()

    assert result.returncode == 0, result.stderr
    assert not rig.wlcopy_calls.exists()


def test_fuzzel_is_invoked_in_dmenu_mode(script_path: Path, tmp_path: Path):
    rig = make_rig(script_path, tmp_path, answer="😀 grinning face")

    rig.run()

    argv = rig.fuzzel_calls.read_text()
    assert "--dmenu" in argv


def test_the_table_offers_more_than_a_handful_of_entries(script_path: Path, tmp_path: Path):
    rig = make_rig(script_path, tmp_path, answer="😀 grinning face")

    rig.run()

    offered = [line for line in rig.fuzzel_stdin.read_text().splitlines() if line]
    assert len(offered) >= 50
    assert all(" " in line for line in offered), "every entry needs a glyph and a name"


# --------------------------------------------------------------- static


def test_never_uses_an_x11_clipboard_tool():
    # CLAUDE.md: "Wayland only, never X11-first" — wl-copy, never xclip/xsel.
    src = script_text()
    for forbidden in ("xclip", "xsel", "xdotool"):
        assert forbidden not in src, f"unexpected reference to {forbidden!r}"


def test_never_injects_a_synthetic_keystroke():
    # Invariant 3: only jv-act injects input. A picker that types the glyph
    # in with wtype/ydotool would cross that line; it only ever writes the
    # clipboard, same as jv-clip-menu.
    src = script_text()
    for forbidden in ("wtype", "ydotool"):
        assert forbidden not in src, f"unexpected reference to {forbidden!r}"


def test_the_menu_spawn_name_is_the_one_niri_config_binds():
    niri_src = NIRI_MODULE.read_text("utf-8")
    assert 'spawn "jv-emoji-menu"' in niri_src
    assert "jv-emoji-menu" in module_src()
