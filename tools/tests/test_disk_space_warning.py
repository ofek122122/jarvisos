"""pkgs/jv-disk-space-warning — the periodic disk-full check (PLAN G4).

GUARDRAILS.md: this loop must never garbage-collect or delete generations,
and that discipline extends to what it builds — freeing space is a human's
decision, so the shipped script may only ever READ `df` and write its own
one-line state file. The heaviest thing this suite proves is the negative:
no `nix-collect-garbage`, no `delete-generations`, no `rm -rf` on anything
but its own state file.

The dedupe behaviour (notify once per crossing, not once per timer tick) is
the other thing worth proving hard, so most cases here are a small state
machine: under threshold -> over -> still over -> back under -> over again.

Like test_update_notifier.py, the script is pulled straight out of
pkgs/jv-disk-space-warning/default.nix's own `text` attribute rather than
duplicated here, and both `df` and `notify-send` are stubbed on PATH so the
real behaviour is exercised without touching the real disk.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

from test_gen_theme_qml import ROOT

MODULE = ROOT / "pkgs" / "jv-disk-space-warning" / "default.nix"


def module_src() -> str:
    return MODULE.read_text("utf-8")


def script_text() -> str:
    src = module_src()
    m = re.search(r"text = ''\n(.*?)\n  '';\n", src, re.S)
    assert m, "no text = '' ... ''; script body found in default.nix"
    return m.group(1).replace("''${", "${")


@pytest.fixture()
def script_path(tmp_path: Path) -> Path:
    p = tmp_path / "jv-disk-space-warning"
    p.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + script_text() + "\n")
    p.chmod(0o755)
    return p


def stub_notify_send(bindir: Path) -> Path:
    calls = bindir / "notify-send-calls.txt"
    stub = bindir / "notify-send"
    stub.write_text(f'#!/usr/bin/env bash\nprintf \'%s\\n\' "$*" >> {calls}\n')
    stub.chmod(0o755)
    return calls


def stub_df(bindir: Path, pct_file: Path) -> None:
    # Real `df --output=pcent <path>` prints a header line then " NN%"; the
    # real `-h --output=avail` prints a header then a human-readable size.
    # The stub ignores its actual arguments and always answers from
    # pct_file, which the test rewrites between runs to walk the disk
    # through a sequence of usage levels.
    stub = bindir / "df"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        f'pct=$(cat "{pct_file}")\n'
        'if [[ "$*" == *--output=avail* ]]; then\n'
        '  echo "Avail"\n'
        '  echo " 42G"\n'
        "else\n"
        '  echo "Use%"\n'
        '  echo " ${pct}%"\n'
        "fi\n"
    )
    stub.chmod(0o755)


class Rig:
    def __init__(self, script_path: Path, tmp_path: Path):
        bindir = tmp_path / "bin"
        bindir.mkdir()
        self.pct_file = tmp_path / "pct"
        self.pct_file.write_text("10")
        stub_df(bindir, self.pct_file)
        self.calls = stub_notify_send(bindir)
        self.statefile = tmp_path / "state" / "over-threshold"
        self.script_path = script_path

        self.env = dict(os.environ)
        self.env["PATH"] = f"{bindir}:{self.env.get('PATH', '')}"

    def set_pct(self, pct: int) -> None:
        self.pct_file.write_text(str(pct))

    def run(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            [str(self.script_path), "/fake/path", str(self.statefile)],
            env=self.env,
            capture_output=True,
            text=True,
        )


@pytest.fixture()
def rig(script_path: Path, tmp_path: Path) -> Rig:
    return Rig(script_path, tmp_path)


# --------------------------------------------------------------- static


def test_never_invokes_gc_or_deletes_generations_or_rebuilds():
    src = script_text()
    for forbidden in (
        "nix-collect-garbage",
        "delete-generations",
        "nixos-rebuild",
    ):
        assert forbidden not in src, f"the script invokes {forbidden}"


def test_the_only_rm_in_the_script_targets_the_state_file():
    src = script_text()
    rms = re.findall(r"rm\s+[^\n]*", src)
    assert rms, "expected an `rm` clearing the state file when usage drops"
    for call in rms:
        assert "$statefile" in call, f"an rm does not name $statefile: {call}"
        assert "$path" not in call, f"an rm touches $path (the disk itself): {call}"


# ------------------------------------------------------------ behaviour


def test_quiet_when_comfortably_under_threshold(rig: Rig):
    rig.set_pct(10)

    result = rig.run()

    assert result.returncode == 0, result.stderr
    assert not rig.calls.exists()
    assert not rig.statefile.exists()


def test_notifies_once_on_crossing_the_threshold(rig: Rig):
    rig.set_pct(90)

    result = rig.run()

    assert result.returncode == 0, result.stderr
    assert rig.calls.exists()
    text = rig.calls.read_text()
    assert "90%" in text, text
    assert rig.statefile.exists()


def test_does_not_renotify_while_still_over_threshold(rig: Rig):
    rig.set_pct(90)
    rig.run()
    assert rig.calls.read_text().count("\n") == 1

    rig.set_pct(92)
    result = rig.run()

    assert result.returncode == 0, result.stderr
    assert rig.calls.read_text().count("\n") == 1, "renotified without a fresh crossing"


def test_clears_state_and_renotifies_after_dropping_back_under(rig: Rig):
    rig.set_pct(90)
    rig.run()
    assert rig.statefile.exists()

    rig.set_pct(50)
    result = rig.run()
    assert result.returncode == 0, result.stderr
    assert not rig.statefile.exists(), "state not cleared once back under threshold"

    rig.set_pct(90)
    rig.run()
    assert rig.calls.read_text().count("\n") == 2, "did not renotify on a second crossing"


def test_respects_a_custom_threshold_env_var(rig: Rig):
    rig.env["JV_DISK_WARN_PCT"] = "50"
    rig.set_pct(60)

    result = rig.run()

    assert result.returncode == 0, result.stderr
    assert rig.calls.exists(), "60% did not trip a 50% threshold"


def test_quiet_and_clean_exit_when_df_fails(rig: Rig, tmp_path: Path):
    # A path df cannot answer for at all (stub emits nothing) — the real
    # script must not crash under `set -euo pipefail`.
    broken_df = tmp_path / "bin" / "df"
    broken_df.write_text("#!/usr/bin/env bash\nexit 1\n")
    broken_df.chmod(0o755)

    result = rig.run()

    assert result.returncode == 0, result.stderr
    assert not rig.calls.exists()
