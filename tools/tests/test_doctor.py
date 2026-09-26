"""`jarvis-doctor`'s monitor check, run against a fake session (PLAN E13).

Check 5 of the Phase 0 verifier used to be two greps:

    n_primary=$(grep -cE '2560x1440 @ 14[0-9]' <<<"$current")
    n_secondary=$(grep -cE '1920x1080 @ (59|60)' <<<"$current")

which is ares' three monitors written a FOURTH time — after CLAUDE.md's prose,
`hosts/ares/outputs.nix` and the contact sheet — in a regex, in a shell script,
where the primary's 144.006 had become a character class. PLAN E10 had just
finished making the wallpaper compose for the declaration instead of a list
somebody typed; this was the last place on the machine still asking "is this
the hardware somebody typed in August" rather than "is this the machine the
flake declares".

So the expectation is generated now: `pkgs/jarvis-doctor/default.nix` writes
the declaration out as a TSV in the store and hands the doctor its path in
`$JARVIS_OUTPUTS`, the same file-not-string hop `jv-wall` makes with
`JV_WALL_DIR` (PLAN E12) and for the same reason — bytes in the store can be
read back by `ops/ralph/nixtest.sh`, and an interpolation that evaluated to the
wrong list cannot look right in the source.

WHY THIS SUITE RUNS THE CHECK INSTEAD OF READING IT. Everything the old greps
could get wrong, they got wrong SILENTLY: they counted matching lines, so they
could not see a connector name, could not see a position, and would have passed
a session in which all three monitors were stacked at x=0, or in which a fourth
monitor nobody declared was attached at a refresh rate the counts ignored. A
test that grepped the new check for `JARVIS_OUTPUTS` would pass on a rewrite
that read the file and then compared nothing. So the section is LIFTED out of
the shipped script and executed against a fake `niri` and a fake declaration,
once per outcome — including the three ways the declaration itself can fail to
arrive, which are three different sentences and not one.

What is NOT here: the check's green path against the real compositor. That is
the doctor, run on ares inside the session, and `ops/ralph/nixtest.sh` asserts
the other half — that the TSV inside the BUILT package is the host's own
declaration, both directions.
"""

from __future__ import annotations

import os
import re
import subprocess
import textwrap
from pathlib import Path

from test_gen_theme_qml import ROOT
from test_outputs import ARES_OUTPUTS, declared_outputs

DOCTOR_SH = ROOT / "pkgs" / "jarvis-doctor" / "doctor.sh"
DOCTOR_NIX = ROOT / "pkgs" / "jarvis-doctor" / "default.nix"
FLAKE = ROOT / "flake.nix"

SECTION = 'section "Monitors (Wayland, via niri)"'


# ------------------------------------------------------------ lifting the check


def monitor_check() -> str:
    """The lines of the doctor that decide check 5, verbatim.

    Cut from the `section` line that names it to the banner comment that opens
    check 6 — the whole section and not a chosen part of it, because the guards
    that decide whether the declaration ARRIVED are as much the check as the
    comparison is, and three of the cases below are about them. Lifting rather
    than re-implementing is the point: what runs below is the shipped text, so
    a rewrite that stops doing what E13 asked fails here even if it reads
    perfectly well.
    """
    lines = DOCTOR_SH.read_text("utf-8").splitlines()
    starts = [i for i, ln in enumerate(lines) if ln.strip() == SECTION]
    assert len(starts) == 1, (
        f"{DOCTOR_SH.relative_to(ROOT)} opens the monitor section {len(starts)} times; "
        "this test lifts exactly one block out of it"
    )
    start = starts[0]
    ends = [i for i, ln in enumerate(lines) if i > start and re.match(r"^# -{4,}", ln)]
    assert ends, "nothing follows the monitor section, so its end cannot be found"
    body = "\n".join(lines[start : ends[0]]).rstrip()
    assert body.endswith("\nfi"), (
        "the monitor check no longer ends with an unindented `fi`; the lift above "
        f"would carry loose statements into every case:\n{body[-200:]}"
    )
    return body


PRELUDE = r"""
set -uo pipefail
FAILURES=0
pass() { printf 'PASS\t%s\n' "$*"; }
fail() { printf 'FAIL\t%s\n' "$*"; FAILURES=$((FAILURES + 1)); }
section() { :; }
# The real check calls the `niri` on $PATH; a function shadows it, so the block
# under test cannot reach a compositor.
niri() { eval "$FAKE_NIRI"; }
"""


class Run:
    def __init__(self, stdout: str) -> None:
        self.stdout = stdout

    @property
    def passes(self) -> list[str]:
        return [ln.split("\t", 1)[1] for ln in self.stdout.splitlines() if ln.startswith("PASS\t")]

    @property
    def failures(self) -> list[str]:
        return [ln.split("\t", 1)[1] for ln in self.stdout.splitlines() if ln.startswith("FAIL\t")]

    def only_failure(self) -> str:
        assert len(self.failures) == 1, f"expected one failure, got {self.failures}"
        return self.failures[0]


def run_check(
    tmp_path: Path,
    *,
    declared: str | None = "",
    niri_out: str | None = "",
    declared_path: Path | None = None,
) -> Run:
    """Execute the lifted check against a fake declaration and a fake `niri`.

    `declared=None` leaves $JARVIS_OUTPUTS unset; `declared_path` points it at a
    path of your choosing (a missing one, say) instead of writing the TSV.
    `niri_out=None` makes the compositor call fail the way it does outside a
    session.
    """
    env = dict(os.environ)
    if declared_path is not None:
        env["JARVIS_OUTPUTS"] = str(declared_path)
    elif declared is not None:
        tsv = tmp_path / "declared-outputs.tsv"
        tsv.write_text(declared, "utf-8")
        env["JARVIS_OUTPUTS"] = str(tsv)
    else:
        env.pop("JARVIS_OUTPUTS", None)
    env["FAKE_NIRI"] = (
        "return 1" if niri_out is None else "printf '%s' \"$NIRI_OUT\"; " "return 0"
    )
    env["NIRI_OUT"] = niri_out or ""

    program = PRELUDE + "\n" + monitor_check() + '\nprintf "done\\n"\n'
    proc = subprocess.run(
        ["bash", "-c", program], capture_output=True, text=True, env=env, timeout=60
    )
    assert "done" in proc.stdout, (
        f"the lifted check did not run to the end:\n{proc.stdout}\n{proc.stderr}"
    )
    return Run(proc.stdout)


# -------------------------------------------------------------- the fake world


def tsv(*rows: tuple[str, int, int, str, int, int]) -> str:
    return "".join(f"{n}\t{w}\t{h}\t{hz}\t{x}\t{y}\n" for n, w, h, hz, x, y in rows)


def block(
    conn: str, mode: str | None, x: int | None, y: int = 0, *, preferred: bool = False
) -> str:
    """One output as `niri msg outputs` prints it. `mode=None` is a DISABLED
    output, which has a block and no `Current mode:` line."""
    out = f'Output "Some Vendor Some Model SN{conn}" ({conn})\n'
    if mode is not None:
        out += f"  Current mode: {mode} Hz{' (preferred)' if preferred else ''}\n"
    out += "  Variable refresh rate: not supported\n"
    if x is not None:
        out += f"  Logical position: {x}, {y}\n"
    out += "  Scale: 1\n  Transform: normal\n"
    return out


# The session ares really has, captured from the machine on 2026-09-26, and the
# declaration it must agree with.
ARES_LIVE = (
    block("HDMI-A-1", "2560x1440 @ 144.006", 0)
    + "\n"
    + block("DP-1", "1920x1080 @ 60.000", 2560, preferred=True)
    + "\n"
    + block("DP-2", "1920x1080 @ 60.000", 4480, preferred=True)
)
ARES_TSV = tsv(
    ("HDMI-A-1", 2560, 1440, "144.006", 0, 0),
    ("DP-1", 1920, 1080, "60.000", 2560, 0),
    ("DP-2", 1920, 1080, "60.000", 4480, 0),
)


# -------------------------------------------------------- the machine it wants


def test_the_session_ares_really_has_passes_every_arm(tmp_path):
    """The green path, against `niri msg outputs` as ares actually prints it —
    three named outputs plus the claim that there is no fourth."""
    run = run_check(tmp_path, declared=ARES_TSV, niri_out=ARES_LIVE)
    assert run.failures == []
    assert len(run.passes) == 4, run.passes
    assert "HDMI-A-1 at 2560x1440 @ 144.006 Hz, at 0,0 in the layout" in run.passes


def test_the_check_is_the_declaration_and_carries_no_monitor_of_its_own(tmp_path):
    """E13 itself, and the only test that can show it: a declaration of one
    monitor no machine in this repo has ever had is satisfied by a session with
    that monitor. A check with ares' geometry still hidden in it cannot be
    green here, and a check that merely counted outputs could not be red on the
    case below."""
    run = run_check(
        tmp_path,
        declared=tsv(("eDP-1", 3440, 1440, "99.981", 0, 0)),
        niri_out=block("eDP-1", "3440x1440 @ 99.981", 0),
    )
    assert run.failures == [], run.failures
    assert run.passes == [
        "eDP-1 at 3440x1440 @ 99.981 Hz, at 0,0 in the layout",
        "the session has no output beyond the 1 this flake declares",
    ]


# ------------------------------------------- the ways a session can be wrong


def test_a_declared_output_that_is_not_there_is_named(tmp_path):
    run = run_check(
        tmp_path,
        declared=ARES_TSV,
        niri_out=block("HDMI-A-1", "2560x1440 @ 144.006", 0) + "\n" + block("DP-1", "1920x1080 @ 60.000", 2560),
    )
    assert run.only_failure() == (
        "DP-2 is declared (1920x1080 @ 60.000 Hz at 4480,0) and the session has no such output"
    )


def test_a_rounded_refresh_rate_is_a_different_mode(tmp_path):
    """The old regex asked for `1920x1080 @ (59|60)` and the primary for
    `14[0-9]`, so 59.939 — a real mode on these panels, and not the one the
    flake declares — counted as the declared one. The declaration carries the
    exact decimal because that is what has to be ASKED for."""
    run = run_check(
        tmp_path,
        declared=ARES_TSV,
        niri_out=ARES_LIVE.replace("1920x1080 @ 60.000 Hz (preferred)\n  Variable refresh rate: not supported\n  Logical position: 2560", "1920x1080 @ 59.939 Hz\n  Variable refresh rate: not supported\n  Logical position: 2560"),
    )
    assert run.only_failure() == (
        "DP-1 is declared as 'DP-1 1920x1080 60.000 2560 0' and is live as "
        "'DP-1 1920x1080 59.939 2560 0'"
    )


def test_a_smaller_mode_on_the_right_connector_is_caught(tmp_path):
    run = run_check(
        tmp_path,
        declared=ARES_TSV,
        niri_out=ARES_LIVE.replace("2560x1440 @ 144.006", "1920x1080 @ 60.000"),
    )
    # The primary dropped to 1080p60: one output is not what it should be, and
    # the old counts would have said "found 0" for the primary and "found 3"
    # for the secondaries — two failures about one monitor and neither naming it.
    assert run.only_failure() == (
        "HDMI-A-1 is declared as 'HDMI-A-1 2560x1440 144.006 0 0' and is live as "
        "'HDMI-A-1 1920x1080 60.000 0 0'"
    )


def test_three_monitors_stacked_on_top_of_each_other_is_a_failure(tmp_path):
    """Every output at x=0 is a desktop where the bar, the HUD and the
    wallpaper all land on one panel. Nothing in this repo could see it before:
    the modes are right, the counts are right, and `Logical position` was a
    line the check never read."""
    run = run_check(
        tmp_path,
        declared=ARES_TSV,
        niri_out=ARES_LIVE.replace("Logical position: 2560", "Logical position: 0").replace(
            "Logical position: 4480", "Logical position: 0"
        ),
    )
    assert len(run.failures) == 2, run.failures
    assert all("is declared as" in f and "is live as" in f for f in run.failures)
    assert "DP-1 1920x1080 60.000 0 0" in run.failures[0]


def test_a_side_panel_that_slid_below_the_primary_is_caught(tmp_path):
    """The other half of `Logical position` (PLAN E14). Until the declaration
    carried a `y` this check read the line and threw half of it away, so a
    session whose side panel sat a screen-height too low — the bar on the wrong
    edge of the desktop, the wallpaper composed for a row of three that is not a
    row — was three passes and no finding. The modes are right; the LAYOUT is
    not."""
    run = run_check(
        tmp_path,
        declared=ARES_TSV,
        niri_out=ARES_LIVE.replace("Logical position: 2560, 0", "Logical position: 2560, 1080"),
    )
    assert run.only_failure() == (
        "DP-1 is declared as 'DP-1 1920x1080 60.000 2560 0' and is live as "
        "'DP-1 1920x1080 60.000 2560 1080'"
    )


def test_a_monitor_mounted_above_another_is_a_layout_this_repo_can_describe(tmp_path):
    """The capability, not the failure: a monitor stacked above the primary is a
    legal desk, and until E14 nothing in this repo could say so — the
    declaration had no `y` to put it at. Both directions in one test, because
    the green half alone would also pass on a check that ignores the vertical
    entirely: the pass has to NAME the position it verified, and the same
    session against a declaration that puts that panel at y=0 has to be red."""
    live = block("HDMI-A-1", "2560x1440 @ 144.006", 0) + "\n" + block(
        "DP-1", "1920x1080 @ 60.000", 320, -1080
    )
    stacked = run_check(
        tmp_path,
        declared=tsv(
            ("HDMI-A-1", 2560, 1440, "144.006", 0, 0),
            ("DP-1", 1920, 1080, "60.000", 320, -1080),
        ),
        niri_out=live,
    )
    assert stacked.failures == [], stacked.failures
    assert "DP-1 at 1920x1080 @ 60.000 Hz, at 320,-1080 in the layout" in stacked.passes

    beside = run_check(
        tmp_path,
        declared=tsv(
            ("HDMI-A-1", 2560, 1440, "144.006", 0, 0),
            ("DP-1", 1920, 1080, "60.000", 320, 0),
        ),
        niri_out=live,
    )
    assert beside.only_failure() == (
        "DP-1 is declared as 'DP-1 1920x1080 60.000 320 0' and is live as "
        "'DP-1 1920x1080 60.000 320 -1080'"
    )


def test_a_disabled_output_is_a_mismatch_and_not_a_skip(tmp_path):
    """A disabled output still has a block; what it has no line of is
    `Current mode:`. The parser gives it `?` rather than dropping it, because
    "the monitor is off" and "the monitor is fine" must not be the same row."""
    run = run_check(
        tmp_path,
        declared=ARES_TSV,
        niri_out=ARES_LIVE.replace(
            "  Current mode: 1920x1080 @ 60.000 Hz (preferred)\n  Variable refresh rate: not supported\n  Logical position: 4480, 0\n",
            "  Disabled\n",
        ),
    )
    assert run.only_failure() == (
        "DP-2 is declared as 'DP-2 1920x1080 60.000 4480 0' and is live as 'DP-2 ? ? ? ?'"
    )


def test_an_undeclared_monitor_is_reported_rather_than_ignored(tmp_path):
    """The other direction, and the one the counts were blind to by
    construction. A fourth panel at a geometry neither grep matched — here a
    1440p one at 60 Hz — passed both of them: nothing composed art for it,
    nothing placed a bar on it, and nothing said so."""
    run = run_check(
        tmp_path,
        declared=ARES_TSV,
        niri_out=ARES_LIVE + "\n" + block("DP-3", "2560x1440 @ 59.951", 6400),
    )
    assert run.only_failure() == (
        "the session also has DP-3 (2560x1440 @ 59.951 Hz) — hosts/ares/outputs.nix "
        "does not declare them, so nothing composed art or placed a bar for them"
    )
    assert len(run.passes) == 3, run.passes


def test_no_session_at_all_is_still_the_old_sentence(tmp_path):
    run = run_check(tmp_path, declared=ARES_TSV, niri_out=None)
    assert run.only_failure() == "niri msg outputs failed — run inside the niri session"


# ------------------------------- the three ways the declaration can not arrive


def test_an_unset_variable_is_not_reported_as_a_missing_compositor(tmp_path):
    """`doctor.sh` run directly, outside its wrapper. Under `set -u` an unset
    $JARVIS_OUTPUTS would abort the whole doctor mid-file; reported as "niri
    failed" it would send somebody to the compositor. It is neither."""
    run = run_check(tmp_path, declared=None, niri_out=ARES_LIVE)
    assert "JARVIS_OUTPUTS is unset" in run.only_failure()
    assert "niri" not in run.only_failure()


def test_an_unreadable_declaration_is_not_reported_as_an_empty_one(tmp_path):
    """PLAN E12's lesson, one package along: a file that cannot be OPENED and a
    file whose CONTENTS are empty are different findings, and the second is a
    claim about bytes nobody read."""
    missing = tmp_path / "never-built" / "declared-outputs.tsv"
    run = run_check(tmp_path, declared_path=missing, niri_out=ARES_LIVE)
    assert run.only_failure() == (
        f"JARVIS_OUTPUTS points at {missing}, which cannot be read — the declaration "
        "never reached the built package"
    )


def test_an_empty_declaration_fails_instead_of_verifying_nothing(tmp_path):
    """The vacuous pass. With no rows the loop runs zero times and the
    undeclared-output arm has nothing to compare against, so the check would
    report four successes' worth of silence on any screen at all."""
    run = run_check(tmp_path, declared="\n  \n", niri_out=ARES_LIVE)
    assert run.passes == []
    assert "declares no monitors" in run.only_failure()


# -------------------------------------------- the package that generates it


def doctor_nix() -> str:
    return DOCTOR_NIX.read_text("utf-8")


def test_the_package_takes_the_outputs_it_checks_for_and_defaults_nothing():
    """Same claim `test_outputs.py` makes about the wallpaper, and for the same
    reason: a default would be ares' monitors guessed a fourth time, supplied
    by `callPackage` without a word, in the one file nobody reads."""
    src = doctor_nix()
    args = src[src.index("{", src.index("PLAN E10")) : src.index("}:")]
    assert re.search(r"^\s*outputs,\s*$", args, re.M), (
        f"pkgs/jarvis-doctor does not take an `outputs` argument, or gives it a "
        f"default: {args.strip()!r}"
    )


def test_the_package_refuses_an_empty_declaration():
    """Evaluation-time, because the runtime arm above can only fire if the file
    got built: an empty list is a doctor that passes check 5 on any hardware,
    and that is a silent success — the only kind of bug this check has had."""
    assert re.search(r"if outputs == \[ \] then\s*\n\s*throw", doctor_nix()), (
        "pkgs/jarvis-doctor no longer refuses an empty `outputs` list"
    )


def test_the_generated_row_has_exactly_the_columns_the_check_reads():
    """The two halves of E13 are in different languages and neither can see the
    other: Nix writes the row, bash splits it. A column added to one and not
    the other shifts every field after it — `x` would be read as a refresh rate
    and compared against one, which reads like a monitor problem."""
    src = doctor_nix()
    # `o:` and its row may be on one line or two — nixfmt breaks the line once
    # the row is long enough, and it got long enough when PLAN E14 added `y`.
    row = re.search(
        r'writeText "jarvis-declared-outputs\.tsv"[\s\S]*?\n\s*o:\s*"(?P<row>[^"]*)"', src
    )
    assert row, "pkgs/jarvis-doctor no longer writes one interpolated row per output"
    written = row.group("row").rstrip("\\n").split(r"\t")
    read = re.search(r"while IFS=\$'\\t' read -r (?P<vars>[^\n;]*); do", DOCTOR_SH.read_text("utf-8"))
    assert read, "doctor.sh no longer splits the declaration into fields"
    assert len(written) == len(read.group("vars").split()), (
        f"pkgs/jarvis-doctor writes {len(written)} columns "
        f"({row.group('row')!r}) and doctor.sh reads "
        f"{read.group('vars').split()} out of them"
    )
    # …and they are the attributes the declaration actually carries, so a typo
    # is an evaluation error and never a column of empty strings.
    fields = {f.strip("${}").removeprefix("toString ").removeprefix("o.") for f in written}
    for field in fields:
        assert all(field in out for out in declared_outputs(ARES_OUTPUTS)), (
            f"the generated row spends `{field}`, which hosts/ares/outputs.nix "
            "does not declare on every output"
        )


def test_the_flake_fills_the_doctor_from_the_host_that_owns_the_monitors():
    """The connection, in the one file that can make it — and the same
    declaration `jarvis-wallpaper` is built from two attributes above, which is
    what makes "the machine is the machine this flake declares" one list."""
    assert re.search(
        r"jarvis-doctor = pkgs\.callPackage \./pkgs/jarvis-doctor \{\s*"
        r"outputs = import \./hosts/ares/outputs\.nix;",
        FLAKE.read_text("utf-8"),
    ), "flake.nix does not build jarvis-doctor from hosts/ares/outputs.nix"


def test_no_geometry_is_written_in_the_doctor_any_more():
    """The absence E13 is. Every `WxH` left in `doctor.sh` must be in a comment
    — the section explains the old greps and quotes a block of real `niri`
    output, and both are worth keeping — so the code itself is stripped of its
    comments before it is searched. A regression here does not fail; it just
    goes back to describing a machine that was true in August."""
    code = re.sub(r"(?m)^\s*#.*$", "", DOCTOR_SH.read_text("utf-8"))
    code = re.sub(r"(?m)\s#[^\"']*$", "", code)
    stray = re.findall(r"\b\d{3,4}x\d{3,4}\b", code)
    assert stray == [], (
        f"pkgs/jarvis-doctor/doctor.sh still spells the geometry {stray} in its code; "
        "it is supposed to get every one of them from $JARVIS_OUTPUTS"
    )


def test_the_doctors_own_summary_still_describes_what_it_checks():
    """The header comment is the first thing a human reads and the last thing
    anybody updates. It said "all three monitors run at native resolution" —
    a count, from when the check was one."""
    head = DOCTOR_SH.read_text("utf-8").split("FAILURES=0")[0]
    line = next((ln for ln in head.splitlines() if re.match(r"#\s+5\.", ln)), None)
    assert line, "doctor.sh no longer lists check 5 in its summary"
    assert "declares" in line, (
        f"doctor.sh's summary of check 5 is {line.strip()!r}, which does not say the "
        "expectation comes from the host's declaration"
    )


def test_the_wrapper_is_what_supplies_the_expectation():
    """`runtimeEnv`, not an interpolation into the script: the doctor's text is
    `builtins.readFile ./doctor.sh`, so a `${}` written in it would be a
    literal. This is the test that notices somebody switching to a substitution
    that silently does nothing."""
    src = doctor_nix()
    assert re.search(r"JARVIS_OUTPUTS = \"\$\{declared\}\";", src), (
        "pkgs/jarvis-doctor no longer exports JARVIS_OUTPUTS from runtimeEnv"
    )
    assert "builtins.readFile ./doctor.sh" in src, (
        "the doctor's text is no longer read verbatim; if it is interpolated now, "
        "the environment hop this test guards is not the one that matters"
    )


def test_the_check_claims_the_whole_position_the_declaration_carries():
    """PLAN E14, in the three files it takes: the declaration grows a `y`, the
    package spends it in the row, and the parser takes BOTH halves of niri's
    `Logical position: X, Y`. This test's ancestor was
    `test_the_check_does_not_claim_a_vertical_position` — the note that existed
    to go red the day the declaration grew one, which is today."""
    for out in declared_outputs(ARES_OUTPUTS):
        assert isinstance(out.get("y"), int), (
            f"{out.get('name')} declares no vertical position, so the check below "
            "is comparing a column the declaration cannot fill"
        )
    assert re.search(r"toString o\.y", doctor_nix()), (
        "pkgs/jarvis-doctor does not write the declared `y` into the row, so the "
        "column doctor.sh reads is empty on every output"
    )
    sh = DOCTOR_SH.read_text("utf-8")
    assert re.search(r'x = \$3; sub\(/,\$/, "", x\); y = \$4', sh), (
        "doctor.sh no longer takes both halves of niri's `Logical position` — the "
        "vertical one is the half it used to drop"
    )
    assert "deliberately does not claim" not in sh, (
        "doctor.sh still carries the paragraph explaining that it does not check "
        "the vertical position; it checks it now, and that comment is the first "
        "thing a human reads about what this check believes"
    )


def test_the_awk_block_is_reachable_from_the_shipped_niri_format():
    """The fixture above is not a guess: it is the shape `niri msg outputs`
    printed on ares. Parsing it is the only part of this check that could rot
    against a niri upgrade with nothing else changing, so the fixture is held
    to the one property the parser depends on — a header line naming the
    connector in parentheses, and indented `Current mode:`/`Logical position:`
    lines under it."""
    assert re.match(r'^Output "[^"]*" \([\w-]+\)$', ARES_LIVE.splitlines()[0])
    assert [ln for ln in ARES_LIVE.splitlines() if re.match(r"^  Current mode: ", ln)]
    assert [ln for ln in ARES_LIVE.splitlines() if re.match(r"^  Logical position: ", ln)]
    lifted = monitor_check()
    for needle in ("/^Output /", "Current mode:", "Logical position:"):
        assert needle in lifted, f"the parser no longer looks for {needle!r}"


def test_the_lifted_block_is_the_whole_check_and_not_a_fragment():
    """The lift is by line shape, so it is worth one assertion that it caught
    the arms this file tests rather than the first three lines of them."""
    lifted = monitor_check()
    assert lifted.startswith(SECTION) and lifted.endswith("\nfi")
    assert lifted.count("fail ") >= 6, textwrap.shorten(lifted, 200)
    assert 'niri msg outputs' in lifted
