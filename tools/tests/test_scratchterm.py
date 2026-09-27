"""pkgs/jv-scratchterm — a drop-down scratchpad terminal (PLAN H1).

niri's own wiki (Configuration: Window Rules > default-floating-position)
documents the "dropdown terminal" shape this leans on wholesale: a floating
window anchored to the top edge, sized to a proportion of the output, matched
by a dedicated app-id. What niri does not ship is the toggle itself — show it
if it's hidden, hide it if it's shown, spawn it once if it has never run — so
that is the whole of this script: two `niri msg` reads and one action, plus
one spawn, driving the window-rule + named workspace pair `modules/niri.nix`
declares (PLAN H1's own commit; see its own comment for why the keybind lives
in a second, `include`d KDL file rather than a second `binds { }` block).

THE NAMED WORKSPACE IS THE STATE. niri's own wiki: "named workspaces always
exist, even when they have no windows" — so the workspace's own `is_active`
on its output already answers "is the terminal on screen right now", and the
script needs no state file of its own the way PLAN G4's disk warning does.

Like test_update_notifier.py/test_disk_space_warning.py, the script is pulled
straight out of pkgs/jv-scratchterm/default.nix's own `text` attribute, and
both `niri` and `alacritty` are stubbed on PATH — `jq` is the real one, since
parsing the stub's own JSON is exactly the thing under test.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from test_gen_theme_qml import ROOT

MODULE = ROOT / "pkgs" / "jv-scratchterm" / "default.nix"
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
    p = tmp_path / "jv-scratchterm"
    p.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + script_text() + "\n")
    p.chmod(0o755)
    return p


def stub_niri(bindir: Path, state: Path) -> Path:
    """A fake `niri` answering only the two questions the real script ever
    asks it: is the "jv-scratch" workspace active, and does a
    "jv-scratchterm" window already exist. Both come out of a tiny JSON
    state file the test rewrites between runs."""
    calls = bindir / "niri-calls.txt"
    stub = bindir / "niri"
    script = (
        "#!/usr/bin/env bash\n"
        f'printf \'%s\\n\' "$*" >> {calls}\n'
        f'state="{state}"\n'
        'if [ "$1" = "msg" ] && [ "$2" = "--json" ] && [ "$3" = "workspaces" ]; then\n'
        '  active=$(jq -r .active "$state")\n'
        '  printf \'[{"id":1,"idx":1,"name":"jv-scratch","output":"HDMI-A-1",'
        '"is_urgent":false,"is_active":%s,"is_focused":%s,'
        '"active_window_id":null}]\' "$active" "$active"\n'
        "  exit 0\n"
        "fi\n"
        'if [ "$1" = "msg" ] && [ "$2" = "--json" ] && [ "$3" = "windows" ]; then\n'
        '  exists=$(jq -r .exists "$state")\n'
        '  if [ "$exists" = "true" ]; then\n'
        '    printf \'[{"id":99,"title":null,"app_id":"jv-scratchterm","pid":1,'
        '"workspace_id":1,"is_focused":false,"is_floating":true,'
        '"is_urgent":false}]\'\n'
        "  else\n"
        "    printf '[]'\n"
        "  fi\n"
        "  exit 0\n"
        "fi\n"
        "exit 0\n"
    )
    stub.write_text(script)
    stub.chmod(0o755)
    return calls


def stub_alacritty(bindir: Path) -> Path:
    calls = bindir / "alacritty-calls.txt"
    stub = bindir / "alacritty"
    stub.write_text(f"#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >> {calls}\n")
    stub.chmod(0o755)
    return calls


class Rig:
    def __init__(self, script_path: Path, tmp_path: Path):
        bindir = tmp_path / "bin"
        bindir.mkdir()
        self.state = tmp_path / "state.json"
        self.set_state(exists=False, active=False)
        self.niri_calls = stub_niri(bindir, self.state)
        self.alacritty_calls = stub_alacritty(bindir)
        self.script_path = script_path

        self.env = dict(os.environ)
        self.env["PATH"] = f"{bindir}:{self.env.get('PATH', '')}"

    def set_state(self, *, exists: bool, active: bool) -> None:
        self.state.write_text(json.dumps({"exists": exists, "active": active}))

    def run(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            [str(self.script_path)],
            env=self.env,
            capture_output=True,
            text=True,
        )

    def action_calls(self) -> list[str]:
        if not self.niri_calls.exists():
            return []
        return [
            line
            for line in self.niri_calls.read_text().splitlines()
            if line.startswith("msg action")
        ]


@pytest.fixture()
def rig(script_path: Path, tmp_path: Path) -> Rig:
    return Rig(script_path, tmp_path)


# ------------------------------------------------------------ behaviour


def test_first_press_spawns_the_terminal_and_shows_it(rig: Rig):
    rig.set_state(exists=False, active=False)

    result = rig.run()

    assert result.returncode == 0, result.stderr
    assert rig.alacritty_calls.exists(), "never spawned a terminal"
    assert "--class jv-scratchterm" in rig.alacritty_calls.read_text()
    assert "msg action focus-workspace jv-scratch" in rig.action_calls()


def test_press_while_hidden_shows_it_without_spawning_a_second_one(rig: Rig):
    rig.set_state(exists=True, active=False)

    result = rig.run()

    assert result.returncode == 0, result.stderr
    assert not rig.alacritty_calls.exists(), "spawned a second terminal"
    assert "msg action focus-workspace jv-scratch" in rig.action_calls()


def test_press_while_shown_hides_it(rig: Rig):
    rig.set_state(exists=True, active=True)

    result = rig.run()

    assert result.returncode == 0, result.stderr
    assert not rig.alacritty_calls.exists()
    calls = rig.action_calls()
    assert "msg action focus-workspace-previous" in calls
    assert not any("focus-workspace jv-scratch" in c for c in calls)


def test_hiding_never_queries_whether_the_window_exists(rig: Rig):
    # Once the scratch workspace is known active there is nothing left to ask
    # `niri msg --json windows` for, and nothing to spawn.
    rig.set_state(exists=True, active=True)

    rig.run()

    queries = rig.niri_calls.read_text().splitlines()
    assert not any("windows" in q for q in queries)


# --------------------------------------------------------------- static


def test_never_spawns_anything_but_the_one_terminal():
    src = script_text()
    assert "alacritty" in src
    for other in ("kitty", "wezterm", "foot", "xterm"):
        assert other not in src


def test_the_app_id_and_workspace_name_are_the_ones_the_niri_config_names():
    niri_module = NIRI_MODULE.read_text("utf-8")
    src = script_text()

    m = re.search(r'app_id="([^"]+)"', src)
    assert m, "script never names its own app_id"
    assert f'app-id=r#"^{m.group(1)}$"#' in niri_module, (
        "modules/niri.nix's window-rule does not match the script's own app_id"
    )

    m = re.search(r'workspace="([^"]+)"', src)
    assert m, "script never names its own workspace"
    assert f'workspace "{m.group(1)}"' in niri_module, (
        "modules/niri.nix declares no workspace by the script's own name"
    )


def test_module_wires_the_bind_through_an_included_file_not_a_second_binds_block():
    # A second top-level `binds { }` node in the SAME niri config file is a
    # hard parse error (checked by hand against a real `niri validate` before
    # this suite was written) — the bind must come from an `include`d file.
    niri_module = NIRI_MODULE.read_text("utf-8")
    assert "include \"scratchterm-binds.kdl\"" in niri_module
    assert "scratchterm-binds.kdl\".text" in niri_module
    # The include path is relative (no leading "/"), so the same two files
    # validate together out of any throwaway directory, not only /etc/niri.
    assert 'include "/' not in niri_module
