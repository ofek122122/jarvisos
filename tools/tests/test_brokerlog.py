"""A run whose BROKER went wrong is not a HUD that ignored its frames (D51).

`ops/ralph/shellload.sh` starts two `jarvisd` — one for the frames run and one
for the blind HUD's relink (PLAN D49) — and every claim that gate makes about
the HUD is a reading of what they did: ten plates lit, then a corner that goes
dark, then ten plates again. Until `tools/brokerlog.py` the only thing that had
ever opened either log was the failure message D49 quotes it into, so a broker
that came up and then refused the bridge's subscription, or answered every
publish with an error, read from the corner as a HUD that ignored its frames.
That is the wrong repair by a whole process.

`tools/qmlerrors.py` cannot be pointed at them, and the test at the foot of
this file is the measurement of why: it knows three QML engines' prefixes, a
tracing line is none of them, and over a broker's log it says "nothing threw"
whatever the log says.

THE RULE this file holds:

    every line is a tracing line the broker wrote at INFO or below,
    and one of them says it is listening on the socket it was told to bind.

The census is the floor — it is what keeps an empty log, which has no ERROR
lines in it either, from grading itself clean the way the three staged
harnesses did before D38. And refusing a line it CANNOT parse is what makes the
first half cover more than the two `tracing::error!` sites in `broker.rs`: what
a Rust process writes when it is not well is mostly not tracing at all, and
neither an anyhow `Error:` nor a panicking task has a level to filter on.

WHERE THE FIXTURES COME FROM. Every broker line quoted here was recorded from
the binary this flake builds (`nix build .#jarvisd`, jarvisd 0.1.0) on
2026-09-26 — the clean pair from a broker started on a socket in /tmp, the
`conn 0:` line by connecting to it and sending four 0xff bytes, the anyhow
`Error:` by pointing `--bus` at a directory the process may not write, and the
coloured one by running the same broker with NO_COLOR unset. They are not
invented, because the whole value of this reader is that it matches what the
broker really writes.
"""

import subprocess
import sys
from pathlib import Path

from test_gen_theme_qml import ROOT

sys.path.insert(0, str(ROOT / "tools"))

import brokerlog  # noqa: E402
import qmlerrors  # noqa: E402

BUS = "/tmp/jdtest/bus.sock"

# A broker that came up, bound, and had nothing else to say. Two lines is the
# whole of a well broker's account at the level it ships at.
CLEAN = """\
2026-09-26T02:20:57.087052Z  INFO jarvisd: jarvisd listening on /tmp/jdtest/bus.sock
"""

# The same broker with `RUST_LOG=jarvisd=debug` and one client that sent four
# 0xff bytes: the decode error PLAN D51 names, at the level `broker.rs` really
# logs it. Note the target — `jarvisd::broker` rather than `jarvisd` — and see
# `test_the_decode_error_this_reader_was_named_for_is_below_the_level_it_runs_at`.
DEBUG = """\
2026-09-26T02:24:56.031997Z  INFO jarvisd: jarvisd listening on /tmp/jdtest/bus.sock
2026-09-26T02:24:58.048969Z DEBUG jarvisd::broker: conn 0: frame too large: 4294967295 bytes
"""

# What `main` returning `Err` prints. Not a tracing line at all: no timestamp,
# no level, nothing to filter on — which is why the rule is about every line
# rather than about the two levels above INFO.
ANYHOW = "Error: Permission denied (os error 13)\n"

# The listening line as tracing writes it when nothing has told it not to
# colour its output. The level arrives as `\x1b[32m INFO\x1b[0m`, so the whole
# file parses as no lines at all — which is why the census matters even more
# here than the fault rule does.
COLOURED = (
    "\x1b[2m2026-09-26T02:21:04.344175Z\x1b[0m \x1b[32m INFO\x1b[0m "
    "\x1b[2mjarvisd\x1b[0m\x1b[2m:\x1b[0m jarvisd listening on "
    "/tmp/jdtest/bus.sock\n"
)

# The two `tracing::error!` sites in `services/jarvisd/src/broker.rs`, in the
# layout recorded above. The message texts are the crate's own format strings.
LOUD = """\
2026-09-26T02:20:57.087052Z  INFO jarvisd: jarvisd listening on /tmp/jdtest/bus.sock
2026-09-26T02:20:59.100000Z ERROR jarvisd::broker: accept: Too many open files (os error 24)
"""


def run(text: str | None, *args: str, tmp_path: Path) -> subprocess.CompletedProcess:
    log = tmp_path / "jarvisd.log"
    if text is not None:
        log.write_text(text, "utf-8")
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "brokerlog.py"), str(log), *args],
        capture_output=True,
        text=True,
    )


# ------------------------------------------------------------------ the rule


def test_a_broker_that_bound_and_said_nothing_else_is_accepted(tmp_path):
    """The green case, and it has to be green over the real thing: a reader
    that refused a well broker would be switched off within one iteration."""
    done = run(CLEAN, "--listening", BUS, tmp_path=tmp_path)
    assert done.returncode == 0, done.stdout + done.stderr
    assert BUS in done.stdout


def test_an_empty_log_is_not_a_clean_one(tmp_path):
    """The D38 hole, one harness further out. A log nobody wrote has no ERROR
    lines in it either, so a reader that only looked for faults would grade a
    broker that never started as the healthiest in the run — which is exactly
    how the three staged harnesses graded themselves before they grew a
    census. `--listening` IS the census."""
    done = run("", "--listening", BUS, tmp_path=tmp_path)
    assert done.returncode == 1
    assert "never said it was listening" in done.stdout
    assert "named nothing" in done.stdout


def test_a_broker_that_bound_some_other_socket_is_refused(tmp_path):
    """The census is the PATH and not merely the sentence. A `--bus` that
    silently did not apply, or a log left behind by a previous run in a stage
    that was not cleaned, is a broker the HUD of THIS run cannot reach — and
    from the corner that is indistinguishable from a shell that never lit."""
    done = run(CLEAN, "--listening", "/tmp/jdtest/other.sock", tmp_path=tmp_path)
    assert done.returncode == 1
    assert "it named ['/tmp/jdtest/bus.sock']" in done.stdout


def test_a_line_above_info_is_the_fault_this_reader_is_for(tmp_path):
    """`tracing::error!("accept: {e}")` in `broker.rs` fires when the listener
    stops accepting, and the loop BREAKS — so every client that connects after
    it hangs. The process stays up, the socket stays bound, and the only
    evidence anywhere is this line."""
    done = run(LOUD, "--listening", BUS, tmp_path=tmp_path)
    assert done.returncode == 1
    assert "1 line(s) at a level above INFO" in done.stdout
    assert "ERROR jarvisd::broker: accept:" in done.stdout


def test_a_line_tracing_did_not_write_is_refused_too(tmp_path):
    """The half that makes this more than a level filter. What a Rust process
    says when it is NOT well is mostly not tracing: an anyhow `Error:` from
    `main`, and a panic in a spawned task — which does not end the process, so
    the run goes on waiting on a broker whose accept loop is dead. Neither has
    a level, and this reader does not have to have predicted either shape."""
    done = run(CLEAN + ANYHOW, "--listening", BUS, tmp_path=tmp_path)
    assert done.returncode == 1
    assert "1 line(s) tracing did not write" in done.stdout
    assert "Error: Permission denied (os error 13)" in done.stdout


def test_a_coloured_log_is_refused_rather_than_read_clean(tmp_path):
    """`NO_COLOR=1` is load-bearing for the same reason `tools/qmlerrors.py`
    needs it — tracing colours its level whether or not anything is watching.
    The failure DIRECTION is the safe one here, and that is worth a test
    rather than a sentence: the coloured log parses as no lines at all, so the
    census fails and the run goes red. Red for the wrong reason, which is
    still the right way round."""
    done = run(COLOURED, "--listening", BUS, tmp_path=tmp_path)
    assert done.returncode == 1
    assert "never said it was listening" in done.stdout


def test_a_log_that_is_not_there_is_not_a_pass(tmp_path):
    """The same answer `qmlerrors.py` gives, for one more reason of its own:
    this runs after the driver, so a broker log that does not exist means the
    run ended before the act that starts that broker. A reader that saw no
    file and said "clean" would put a green line under that."""
    done = run(None, "--listening", BUS, tmp_path=tmp_path)
    assert done.returncode == 2
    assert "cannot read" in done.stderr
    assert "did not reach the act" in done.stderr


def test_blank_lines_are_not_lines_tracing_did_not_write(tmp_path):
    """A process that ended with a newline has not said anything. A rule about
    every line that refused whitespace would be a gate about whitespace."""
    done = run(CLEAN + "\n\n", "--listening", BUS, tmp_path=tmp_path)
    assert done.returncode == 0, done.stdout


# ------------------------------------------------------- what it can and cannot see


def test_the_quiet_levels_are_every_level_that_is_not_a_complaint():
    """Spelled as the complement rather than as `("WARN", "ERROR")`, so a
    level tracing gains is a fault here until somebody decides otherwise.
    That is the direction a gate should fail in."""
    assert set(brokerlog.LEVELS) - set(brokerlog.QUIET) == {"WARN", "ERROR"}
    assert brokerlog.complaints(brokerlog.scan(DEBUG)[0]) == []


def test_the_decode_error_this_reader_was_named_for_is_below_the_level_it_runs_at():
    """The limit, measured rather than assumed, and it is the follow-up D51
    leaves behind. PLAN D51 names "a broker logging a decode error per frame"
    as one of the two faults this reader is for — and `broker.rs` logs exactly
    that at DEBUG (`conn {id}: {e}`), while `jarvisd` defaults its filter to
    `info`. So the line below is real, this reader parses it correctly, and in
    a shellload run it is never written at all.

    What IS covered is the other fault in that sentence and more of it than
    the levels suggest: a broker that never bound, one that bound the wrong
    socket, one whose accept loop died, one that failed to encode a frame, and
    anything it printed that tracing did not format."""
    said, other = brokerlog.scan(DEBUG)
    assert other == []
    assert [line.level for line in said] == ["INFO", "DEBUG"]
    assert said[1].target == "jarvisd::broker"
    assert "frame too large" in said[1].message
    filt = (ROOT / "services" / "jarvisd" / "src" / "bin" / "jarvisd.rs").read_text(
        "utf-8"
    )
    assert '"info".into()' in filt
    broker = (ROOT / "services" / "jarvisd" / "src" / "broker.rs").read_text("utf-8")
    assert 'tracing::debug!("conn {id}: {e}")' in broker


def test_the_two_readers_are_deaf_to_each_others_logs_and_that_is_the_point():
    """The mirror of `test_the_late_broker_is_not_graded_as_a_qml_engine` in
    `test_shellload.py`, and the measurement under both. `qmlerrors.py` over a
    broker's log reports nothing threw — including over the one with an ERROR
    in it — and this reader over a quickshell's log refuses it rather than
    grading it. Two readers is not duplication; it is the only way either log
    gets read by something that speaks its language."""
    assert qmlerrors.scan(LOUD) == []
    assert qmlerrors.scan(ANYHOW) == []
    quickshell = (
        '  INFO: Launching config: "/tmp/qsy/shell.qml"\n'
        "  WARN scene: @sub/Thing.qml[4:-1]: TypeError: Cannot read property "
        "'nothingHere' of undefined\n"
        "  INFO: Configuration Loaded\n"
    )
    said, other = brokerlog.scan(quickshell)
    assert said == []
    assert len(other) == 3


# ------------------------------------------------------------------ the report


def test_the_report_quotes_the_line_a_reader_has_to_go_and_look_at(tmp_path):
    """A verdict that says "the broker was not well" and not WHICH line said
    so sends the reader back to a file in a stage directory the trap has
    already deleted."""
    done = run(CLEAN + ANYHOW + LOUD, "--listening", BUS, tmp_path=tmp_path)
    assert done.returncode == 1
    assert "Too many open files" in done.stdout
    assert "Permission denied" in done.stdout


def test_the_refusal_names_the_command_that_would_run_it_again(tmp_path):
    """The same courtesy `qmlerrors.py` carries: this reader runs inside a
    gate, and its output is read by somebody who did not type the command."""
    done = run(ANYHOW, "--listening", BUS, "--rerun", "bash ops/ralph/shellload.sh",
               tmp_path=tmp_path)
    assert "bash ops/ralph/shellload.sh" in done.stdout


def test_the_socket_it_must_have_bound_is_required_and_not_defaulted():
    """A `--listening` with a default would be a census that passed whenever
    the caller forgot it, which is the one failure a census cannot have."""
    done = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "brokerlog.py"), "/dev/null"],
        capture_output=True,
        text=True,
    )
    assert done.returncode == 2
    assert "--listening" in done.stderr
