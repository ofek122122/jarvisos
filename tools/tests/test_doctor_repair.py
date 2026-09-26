"""`jarvis-doctor --repair` (PLAN G6): diagnose a crashed Jarvis systemd
--user unit and, only when asked, restart it.

Same lifting technique `test_doctor.py` uses for check 5 (PLAN E13): the
block under test is cut verbatim out of `doctor.sh` and run against a fake
`systemctl`, so a rewrite that stops doing what this test asks fails here
even if it reads well. Two blocks are lifted, because the flag and the check
it drives are not adjacent in the file — `--repair` is parsed once, at the
top, long before check 8 reads `$REPAIR`:

  - `arg_parsing()` — the `usage()`/`case` block that turns argv into
    `$REPAIR`, exercised by running the REAL `doctor.sh` head (not a
    reimplementation) with real argv.
  - `user_units_check()` — check 8 itself, exercised with `$REPAIR` supplied
    directly (the way `arg_parsing()` proves it would have been) and a fake
    `systemctl` standing in for the real one.

What is NOT here: the real `systemctl --user` talking to a real, once-crashed
Jarvis unit. That needs ares' own session — see `ops/ralph/HUMAN-VERIFY.md`.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from test_gen_theme_qml import ROOT

DOCTOR_SH = ROOT / "pkgs" / "jarvis-doctor" / "doctor.sh"

SECTION = 'section "Jarvis user services (systemd --user)"'


# ------------------------------------------------------------ lifting the check


def user_units_check() -> str:
    """Check 8, verbatim: from the line naming its section to the summary
    banner that follows it — check 8 is the last check in the file, so its
    end is the one place left that is not another check's start."""
    lines = DOCTOR_SH.read_text("utf-8").splitlines()
    starts = [i for i, ln in enumerate(lines) if ln.strip() == SECTION]
    assert len(starts) == 1, (
        f"{DOCTOR_SH.relative_to(ROOT)} opens the user-units section {len(starts)} times; "
        "this test lifts exactly one block out of it"
    )
    start = starts[0]
    ends = [i for i, ln in enumerate(lines) if i > start and re.match(r"^# -{4,}", ln)]
    assert ends, "nothing follows the user-units section, so its end cannot be found"
    body = "\n".join(lines[start : ends[0]]).rstrip()
    assert body.endswith("\nfi"), (
        "check 8 no longer ends with an unindented `fi`; the lift above would "
        f"carry loose statements into every case:\n{body[-200:]}"
    )
    return body


def arg_parsing() -> str:
    """`usage()` through the `case` that sets `$REPAIR` from argv — the real
    text, not a re-typed copy of what it is supposed to do."""
    src = DOCTOR_SH.read_text("utf-8")
    start = src.index("usage() {")
    end = src.index("\nFAILURES=0")
    assert start < end, "doctor.sh no longer has an argv-parsing block before FAILURES=0"
    return src[start:end]


PRELUDE = r"""
set -uo pipefail
FAILURES=0
pass() { printf 'PASS\t%s\n' "$*"; }
fail() { printf 'FAIL\t%s\n' "$*"; FAILURES=$((FAILURES + 1)); }
section() { :; }
# A fake `systemctl` standing in for the real one: it never touches a real
# unit, and every call it receives is appended to $CALL_LOG so a test can
# assert restart/reset-failed were (or were not) attempted, and against which
# unit.
systemctl() {
  if [ "${1-}" = "--user" ]; then shift; fi
  sub="${1-}"; shift || true
  printf '%s %s\n' "$sub" "$*" >>"$CALL_LOG"
  case "$sub" in
    list-units)
      printf '%s' "$LIST_UNITS_OUT"
      return "${LIST_UNITS_RC:-0}"
      ;;
    reset-failed) return 0 ;;
    restart) return 0 ;;
    is-active)
      printf '%s' "$IS_ACTIVE_OUT"
      return "${IS_ACTIVE_RC:-0}"
      ;;
    *) return 1 ;;
  esac
}
"""


class Run:
    def __init__(self, stdout: str, call_log: str) -> None:
        self.stdout = stdout
        self.call_log = call_log

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
    repair: bool,
    list_units_out: str,
    list_units_rc: int = 0,
    is_active_out: str = "",
    is_active_rc: int = 0,
) -> Run:
    call_log = tmp_path / "calls.log"
    call_log.write_text("", "utf-8")
    env = dict(os.environ)
    env["LIST_UNITS_OUT"] = list_units_out
    env["LIST_UNITS_RC"] = str(list_units_rc)
    env["IS_ACTIVE_OUT"] = is_active_out
    env["IS_ACTIVE_RC"] = str(is_active_rc)
    env["CALL_LOG"] = str(call_log)

    program = (
        PRELUDE
        + f"\nREPAIR={1 if repair else 0}\n"
        + user_units_check()
        + '\nprintf "done\\n"\n'
    )
    proc = subprocess.run(
        ["bash", "-c", program], capture_output=True, text=True, env=env, timeout=60
    )
    assert "done" in proc.stdout, (
        f"check 8 did not run to the end:\n{proc.stdout}\n{proc.stderr}"
    )
    return Run(proc.stdout, call_log.read_text("utf-8"))


def unit_line(name: str, active: str, sub: str = "running") -> str:
    return f"{name} loaded {active} {sub} Some Jarvis unit\n"


# -------------------------------------------------------------- check 8 itself


def test_no_units_found_is_a_failure_not_a_vacuous_pass(tmp_path):
    """Same lesson E13 already forced on check 5: zero units checked would
    otherwise be zero failures, which reads as ALL PASS on a machine that
    never switched this flake at all."""
    run = run_check(tmp_path, repair=False, list_units_out="")
    assert run.passes == []
    assert "no jv-*/jarvis-* units" in run.only_failure()


def test_systemctl_itself_failing_is_the_same_finding_as_no_units(tmp_path):
    run = run_check(tmp_path, repair=False, list_units_out="", list_units_rc=1)
    assert "no jv-*/jarvis-* units" in run.only_failure()


def test_every_unit_active_is_every_unit_a_pass(tmp_path):
    run = run_check(
        tmp_path,
        repair=False,
        list_units_out=unit_line("jv-hud.service", "active") + unit_line("jv-idle.service", "active", "waiting"),
    )
    assert run.failures == []
    assert run.passes == ["jv-hud.service (active)", "jv-idle.service (active)"]


def test_a_failed_unit_without_repair_is_named_and_nothing_is_touched(tmp_path):
    run = run_check(
        tmp_path,
        repair=False,
        list_units_out=unit_line("jv-hud.service", "failed", "failed"),
    )
    assert "jv-hud.service has FAILED" in run.only_failure()
    assert "--repair" in run.only_failure()
    # list-units is the only call the fake logged — nothing restarted or reset.
    assert "restart" not in run.call_log
    assert "reset-failed" not in run.call_log


def test_a_mixed_batch_flags_only_the_failed_unit(tmp_path):
    run = run_check(
        tmp_path,
        repair=False,
        list_units_out=unit_line("jv-hud.service", "active") + unit_line("jv-idle.service", "failed", "failed"),
    )
    assert run.passes == ["jv-hud.service (active)"]
    assert "jv-idle.service has FAILED" in run.only_failure()


def test_repair_that_recovers_the_unit_is_a_pass_and_is_logged(tmp_path):
    run = run_check(
        tmp_path,
        repair=True,
        list_units_out=unit_line("jv-hud.service", "failed", "failed"),
        is_active_out="active",
    )
    assert run.failures == []
    assert run.passes == ["jv-hud.service was FAILED, --repair restarted it and it is now active"]
    assert "reset-failed jv-hud.service" in run.call_log
    assert "restart jv-hud.service" in run.call_log
    assert "is-active jv-hud.service" in run.call_log


def test_repair_that_does_not_help_is_still_a_failure(tmp_path):
    run = run_check(
        tmp_path,
        repair=True,
        list_units_out=unit_line("jv-hud.service", "failed", "failed"),
        is_active_out="failed",
    )
    assert run.passes == []
    failure = run.only_failure()
    assert "jv-hud.service" in failure
    assert "could not bring it back" in failure
    assert "journalctl --user -u jv-hud.service" in failure


def test_repair_where_is_active_itself_cannot_answer_is_not_read_as_fixed(tmp_path):
    """`is-active` failing outright (unit gone, systemctl error) prints
    nothing — `$fixed` is empty, and empty must read as "still broken", not
    as a silent success."""
    run = run_check(
        tmp_path,
        repair=True,
        list_units_out=unit_line("jv-hud.service", "failed", "failed"),
        is_active_out="",
        is_active_rc=1,
    )
    assert run.passes == []
    assert "could not bring it back" in run.only_failure()


# ------------------------------------------------------- the --repair flag itself


def run_argv(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    program = arg_parsing() + '\nprintf "REPAIR=%s\\n" "$REPAIR"\n'
    return subprocess.run(
        ["bash", "-c", program, "jarvis-doctor", *args],
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_no_argv_leaves_repair_off(tmp_path):
    proc = run_argv(tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "REPAIR=0" in proc.stdout


def test_the_repair_flag_turns_repair_on(tmp_path):
    proc = run_argv(tmp_path, "--repair")
    assert proc.returncode == 0, proc.stderr
    assert "REPAIR=1" in proc.stdout


def test_an_unknown_flag_is_refused_with_a_usage_message_not_a_silent_ignore(tmp_path):
    proc = run_argv(tmp_path, "--bogus")
    assert proc.returncode == 2
    assert "REPAIR=" not in proc.stdout
    assert "usage: jarvis-doctor [--repair]" in proc.stderr


# --------------------------------------------- the doctor's own header comment


def test_the_summary_comment_names_check_8_and_the_repair_flag():
    head = DOCTOR_SH.read_text("utf-8").split("usage() {")[0]
    line = next((ln for ln in head.splitlines() if re.match(r"#\s+8\.", ln)), None)
    assert line, "doctor.sh no longer lists check 8 in its summary"
    assert "--repair" in "\n".join(head.splitlines())
