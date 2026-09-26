"""`ops/ralph/nixtest.sh`'s one check that reads a file instead of a string.

PLAN E12. Every other case in that gate asks an EVALUATION a question: the
answer is text `nix eval` printed, and text is always there. One case is not
like that. "The lock screen shows art the wallpaper unit would draw" has to
follow the unit's `ExecStart` into the jv-wall wrapper and read `JV_WALL_DIR`
out of its BYTES — deliberately, because an interpolation that evaluated to the
wrong store path looks perfectly right in `pkgs/jv-wall/default.nix` — and a
store path an evaluation produced is not a store path that was BUILT.

So the gate had a third outcome it did not know about. Guarded by
`[ -r "$wall_bin" ]`, an unrealized wrapper fell into the `-z "$art"` branch
and was reported as *"…/bin/jv-wall sets no JV_WALL_DIR, so nothing says which
art it draws"* — an accusation against a file that did not exist. E11 moved
the `jarvis-wallpaper` hash, which moved jv-wall's, and the gate went red;
`verify.sh --baseline` said NEW, correctly, because the change really did cause
it; `nixos-rebuild build` made it green with nothing else touched. Any change
under `pkgs/` that jv-wall depends on reproduces it, and it costs the iteration
a `--baseline` run and a wrong answer to "whose red is this".

The fix is that the gate REALIZES what it is about to read, and says so plainly
when it still cannot. Both halves are asserted here by RUNNING the case, not by
reading it: the block is lifted out of the script and executed against a fake
`nix`, a fake unit and a fake store, once per outcome it can reach. A test that
only grepped the script for `nix build` would pass on a gate that built the
wrong attribute, built it after the read, or built it and then still printed
the accusation.

The seam that makes that possible is `$store`, and it is not a test hook: the
three `/nix/store` literals in the lock-screen section were a guess about where
this machine's store lives, and Nix's own `NIX_STORE_DIR` is the thing that
decides. A relocated store made every one of those greps match nothing, which
in the `wall_bin` case is the "the wallpaper unit does not start jv-wall"
branch — a second sentence the gate would have said with confidence and no
basis.

What is NOT here: the case's green path against the real ares evaluation. That
is the gate itself, `ops/ralph/nixtest.sh`, and `verify.sh` runs it whenever
the flake moves.
"""

from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "ops" / "ralph" / "nixtest.sh"

CASE = "the lock screen shows art the wallpaper unit would draw"


# ------------------------------------------------------------ lifting the case


def script_text() -> str:
    return SCRIPT.read_text("utf-8")


def lock_art_case() -> str:
    """The lines of the gate that decide this one case, verbatim.

    Cut from the `t='…'` that names it to the end of the `if [ -x "$script" ]`
    block it lives in — the first line that is an unindented `fi`. Lifting
    rather than re-implementing is the whole point: what runs below is the
    shipped text, so a rewrite of the case that stops doing what E12 asked
    fails here even if it still looks reasonable.
    """
    lines = script_text().splitlines()
    starts = [i for i, ln in enumerate(lines) if ln.strip() == f"t='{CASE}'"]
    assert len(starts) == 1, (
        f"{SCRIPT.relative_to(ROOT)} names the case {CASE!r} {len(starts)} times; "
        "this test lifts exactly one block out of it"
    )
    start = starts[0]
    ends = [i for i, ln in enumerate(lines) if i > start and ln == "fi"]
    assert ends, "the case is not closed by an unindented `fi`"
    return "\n".join(lines[start : ends[0]])


# ------------------------------------------------------------- running it once

PRELUDE = r"""
set -uo pipefail
pass=0; fail=0
ok()   { pass=$((pass+1)); printf 'OK\t%s\n' "$1"; }
bad()  { fail=$((fail+1)); printf 'BAD\t%s\t%s\n' "$1" "$2"; }
is_unit() { grep -q '^\[Service\]$' <<<"$1"; }
unit() { cat "$UNIT_FILE"; }
# The real gate calls the `nix` on $PATH; a function shadows it, so the case
# under test cannot reach a store, an evaluation or the network.
nix() { printf '%s\n' "$*" >>"$NIX_LOG"; eval "$FAKE_NIX"; }
script="$LOCK_SCRIPT"
store="$STORE"
"""


class Run:
    def __init__(self, stdout: str, nix_calls: list[str]) -> None:
        self.stdout = stdout
        self.nix_calls = nix_calls

    @property
    def verdict(self) -> str:
        """'OK' or 'BAD' — which arm of the case fired."""
        for line in self.stdout.splitlines():
            if line.startswith(("OK\t", "BAD\t")):
                return line.split("\t")[0]
        raise AssertionError(f"the case reported nothing:\n{self.stdout}")

    @property
    def message(self) -> str:
        for line in self.stdout.splitlines():
            if line.startswith("BAD\t"):
                return line.split("\t", 2)[2]
        raise AssertionError(f"the case did not fail:\n{self.stdout}")


def run_case(
    tmp_path: Path,
    *,
    unit_text: str,
    lock_script: str,
    fake_nix: str = 'echo "error: no such attribute" >&2; return 1',
) -> Run:
    """Execute the lifted case against a fake store, unit and `nix`."""
    unit_file = tmp_path / "unit.txt"
    unit_file.write_text(unit_text, "utf-8")
    lock_file = tmp_path / "jv-lock"
    lock_file.write_text(lock_script, "utf-8")
    nix_log = tmp_path / "nix.log"
    nix_log.write_text("", "utf-8")

    program = PRELUDE + "\n" + lock_art_case() + '\nprintf "done\\n"\n'
    env = dict(os.environ)
    env.update(
        UNIT_FILE=str(unit_file),
        LOCK_SCRIPT=str(lock_file),
        NIX_LOG=str(nix_log),
        FAKE_NIX=fake_nix,
        STORE=str(tmp_path / "store"),
    )
    proc = subprocess.run(
        ["bash", "-c", program], capture_output=True, text=True, env=env, timeout=60
    )
    assert "done" in proc.stdout, (
        f"the lifted case did not run to the end:\n{proc.stdout}\n{proc.stderr}"
    )
    calls = [ln for ln in nix_log.read_text("utf-8").splitlines() if ln]
    return Run(proc.stdout, calls)


# -------------------------------------------------------------- the fake world


def fake_store(tmp_path: Path) -> Path:
    return tmp_path / "store"


def wall_bin(tmp_path: Path, hash_: str = "aaaa") -> Path:
    return fake_store(tmp_path) / f"{hash_}-jv-wall-0.1.0" / "bin" / "jv-wall"


def art_dir(tmp_path: Path, hash_: str = "bbbb") -> Path:
    return fake_store(tmp_path) / f"{hash_}-jarvis-wallpaper" / "share" / "backgrounds"


def wallpaper_unit(tmp_path: Path, **kw) -> str:
    return textwrap.dedent(
        f"""\
        [Unit]
        Description=JarvisOS wallpaper
        [Service]
        ExecStart={wall_bin(tmp_path, **kw)}
        """
    )


def lock_script(tmp_path: Path, png_dir: Path | None = None) -> str:
    png = (png_dir if png_dir is not None else art_dir(tmp_path)) / "2560x1440.png"
    return f"#!/bin/sh\nexec swaylock --image {png}\n"


def write_wrapper(path: Path, art: Path | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "#!/bin/sh\nexport QT_QPA_PLATFORM='wayland'\n"
    if art is not None:
        body += f"export JV_WALL_DIR='{art}'\n"
    body += "exec quickshell\n"
    path.write_text(body, "utf-8")


# ---------------------------------------------- the outcome E12 was reported as


def test_an_unrealized_wrapper_is_not_accused_of_setting_no_variable(tmp_path):
    """The bug, in one assertion: a path that was never built is reported as
    a path that was never built.

    The old text named the wrapper and said it "sets no JV_WALL_DIR" — a claim
    about the contents of a file the gate could not open. An iteration reading
    that goes looking at `pkgs/jv-wall/default.nix`, where the `--set` is right
    there in front of it, and the thirty minutes after that are spent on a
    wrapper that is innocent.
    """
    run = run_case(
        tmp_path,
        unit_text=wallpaper_unit(tmp_path),
        lock_script=lock_script(tmp_path),
    )
    assert run.verdict == "BAD", "a wrapper that is not in the store cannot be read"
    assert "sets no JV_WALL_DIR" not in run.message, (
        "the gate still accuses a file that does not exist of what is inside it: "
        + run.message
    )
    assert str(wall_bin(tmp_path)) in run.message, (
        "the message does not say which path is missing: " + run.message
    )


def test_the_unrealized_message_hands_over_what_nix_said(tmp_path):
    """…and it is `nix`'s own words, because the two ways this ends are not
    the same problem.

    A build that FAILED is a broken flake. A build that SUCCEEDED and left the
    wrapper still unreadable means the attribute the gate builds is not the
    derivation `modules/theme.nix` installs — the unit and `.#jv-wall` have
    drifted apart, which is a real finding and invisible if the message is a
    fixed sentence.
    """
    run = run_case(
        tmp_path,
        unit_text=wallpaper_unit(tmp_path),
        lock_script=lock_script(tmp_path),
        fake_nix='echo "/nix/store/zzzz-jv-wall-0.1.0"',
    )
    assert run.verdict == "BAD"
    assert "zzzz-jv-wall-0.1.0" in run.message, (
        "what nix printed is not in the message, so a build that produced a "
        "DIFFERENT path than the unit names reads as a build that failed: "
        + run.message
    )


def test_the_gate_tries_to_realize_the_wrapper_before_reading_it(tmp_path):
    """The other half of E12: it is not enough to report the absence politely.

    `.#jv-wall` is the same derivation `modules/theme.nix` installs, and the
    expensive part of it — `jarvis-wallpaper`, six rasterized renders — has
    already been built by this point in the gate, because `.#jv-lock` embeds
    one of those PNGs. So realizing it costs a wrapper, and the gate goes green
    on its own instead of sending the iteration to run `nixos-rebuild build`
    and come back.
    """
    run = run_case(
        tmp_path,
        unit_text=wallpaper_unit(tmp_path),
        lock_script=lock_script(tmp_path),
    )
    assert run.nix_calls, "the gate read a store path it never asked anyone to build"
    built = " ".join(run.nix_calls)
    assert ".#jv-wall" in built, f"it builds something else: {run.nix_calls}"
    assert "--no-link" in built, (
        "a gate that leaves a ./result in the worktree is a gate that shows up "
        f"in `git status`: {run.nix_calls}"
    )


def test_realizing_it_is_enough_to_make_the_case_pass(tmp_path):
    """And when the build does land the wrapper, the case answers the question
    it was always for, in the same run. No second invocation, no rebuild."""
    art = art_dir(tmp_path)
    wrapper = wall_bin(tmp_path)
    creates = (
        f'mkdir -p "{wrapper.parent}"; '
        f"printf '%s\\n' \"export JV_WALL_DIR='{art}'\" > \"{wrapper}\"; "
        f'echo "{wrapper.parent.parent}"'
    )
    run = run_case(
        tmp_path,
        unit_text=wallpaper_unit(tmp_path),
        lock_script=lock_script(tmp_path),
        fake_nix=creates,
    )
    assert run.verdict == "OK", run.stdout


# ------------------------------- the outcomes that were always right, still are


def test_a_built_wrapper_with_no_variable_is_still_accused_and_rightly(tmp_path):
    """The sentence E12 took away from the absent case is the TRUE sentence
    here, and it has to survive: a wrapper that exists and sets nothing is
    exactly "nothing says which art it draws"."""
    write_wrapper(wall_bin(tmp_path), art=None)
    run = run_case(
        tmp_path,
        unit_text=wallpaper_unit(tmp_path),
        lock_script=lock_script(tmp_path),
    )
    assert run.verdict == "BAD"
    assert "sets no JV_WALL_DIR" in run.message, run.message
    assert not run.nix_calls, (
        "the gate rebuilt a wrapper it could already read — that is 3 s of "
        f"evaluation on every green run: {run.nix_calls}"
    )


def test_two_surfaces_one_set_of_art_is_the_thing_being_asserted(tmp_path):
    """The case's actual subject, unchanged by any of the above: the lock
    screen's PNG comes out of the directory the wallpaper draws from. Point it
    at a different directory and the gate says which is which."""
    art = art_dir(tmp_path)
    write_wrapper(wall_bin(tmp_path), art=art)

    ok_run = run_case(
        tmp_path,
        unit_text=wallpaper_unit(tmp_path),
        lock_script=lock_script(tmp_path, png_dir=art),
    )
    assert ok_run.verdict == "OK", ok_run.stdout

    other = art_dir(tmp_path, hash_="cccc")
    bad_run = run_case(
        tmp_path,
        unit_text=wallpaper_unit(tmp_path),
        lock_script=lock_script(tmp_path, png_dir=other),
    )
    assert bad_run.verdict == "BAD"
    assert str(art) in bad_run.message and str(other) in bad_run.message, (
        bad_run.message
    )


def test_a_unit_that_does_not_start_jv_wall_is_named_before_anything_is_built(
    tmp_path,
):
    """The order matters for the same reason E12 does. If the ExecStart names
    no jv-wall there is nothing to realize, and a gate that built first would
    spend an evaluation to arrive at a verdict it already had."""
    unit_text = "[Unit]\n[Service]\nExecStart=/usr/bin/swaybg -i /tmp/x.png\n"
    run = run_case(
        tmp_path, unit_text=unit_text, lock_script=lock_script(tmp_path)
    )
    assert run.verdict == "BAD"
    assert "does not start jv-wall" in run.message, run.message
    assert not run.nix_calls, run.nix_calls


def test_an_evaluation_that_refused_is_not_read_as_a_missing_wrapper(tmp_path):
    """`unit()` prints an ERROR where the unit text should be when the
    evaluation fails, and an error names no jv-wall either. `is_unit` has to
    come first or every broken flake is reported as a wallpaper problem."""
    run = run_case(
        tmp_path,
        unit_text="error: attribute 'jarvis-wallpaper' missing\n",
        lock_script=lock_script(tmp_path),
    )
    assert run.verdict == "BAD"
    assert "no wallpaper unit" in run.message, run.message
    assert not run.nix_calls, run.nix_calls


# ------------------------------------------------------------- the store itself


def test_the_lock_section_asks_where_the_store_is_rather_than_assuming(tmp_path):
    """Nix decides where the store lives (`NIX_STORE_DIR`), and three greps in
    this section used to decide it themselves. On a relocated store every one
    of them matched nothing — and a `grep -o` that matches nothing is not an
    error here, it is the empty string, which each of those checks reads as a
    different confident sentence about the flake.
    """
    text = script_text()
    assert 'store="${NIX_STORE_DIR:-/nix/store}"' in text, (
        "nothing in the gate reads NIX_STORE_DIR"
    )
    # Every path pattern in the lock-screen section goes through it.
    section = text[text.index("--------- the lock screen") :]
    stray = [
        ln
        for ln in section.splitlines()
        if "/nix/store" in ln
        and not ln.lstrip().startswith("#")
        and "NIX_STORE_DIR" not in ln
    ]
    assert not stray, f"these still hardcode the store: {stray}"


def test_the_gate_still_declares_what_it_reads():
    """`tools/dependents.py` holds `DECLARED_GATES` equal to the `# reads:`
    header of this script, and `test_dependents.py` is where that is checked.
    Repeated here only as a tripwire: E12 touched the gate's behaviour and not
    its subject, so the header must not have moved."""
    header = [ln for ln in script_text().splitlines() if ln.startswith("# reads:")]
    assert header == ["# reads: flake.lock flake.nix hosts/ares modules nix pkgs"], header


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
