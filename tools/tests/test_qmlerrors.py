"""A shot run that threw is not a green shot run (PLAN D36).

D34's second fault announced itself exactly once, as

    QWARN  : qmltestrunner::BarSettle::test_the_desk_can_empty_and_come_back()
             file:///tmp/tmp.XXXX/Workspaces.qml:113: TypeError: Value is
             undefined and could not be converted to an object

in the middle of a run that ended `8 passed, 0 failed` and wrote eleven
correct PNGs. A QML handler that throws keeps whatever the property had and
recovers on the next evaluation, so the surface stays plausible, the sheet
stays byte-identical and the gate stays green — the warning line is the ONLY
evidence, in output nobody reads unless something else already went wrong.
All three shot harnesses piped the runner's output straight through.

`tools/qmlerrors.py` reads that output and ends the run non-zero when
something in it threw. What it must NOT do is refuse every warning:
`console.warn` is a legitimate voice in this repo (`NiriModel` uses it for a
line it REFUSES to parse) and three drivers narrate their samples through
`console.log`. So the rule is about a THROW, and the discriminator is the
shape the engine itself prints: an engine error carries a `file:line:` and a
JS error name, while console output carries the `qml:` prefix and no location.

WHERE THE FIXTURES COME FROM. Every runner line quoted in this file was
recorded from a real `qmltestrunner` (Qt 6.11.1, `QT_QPA_PLATFORM=offscreen`)
— the clean ones from `bash ops/ralph/barshots.sh` and
`bash ops/ralph/notifyshots.sh` at d605f4b, the thrown ones from a probe
scene whose handlers read a property of `undefined` and an undeclared name.
They are not invented, because the whole value of this gate is that it
matches what the runner really writes.

AND WHAT THE PROBE ALSO FOUND, which is why this gate is narrower than it
looks: qmltestrunner prints NOTHING that is logged outside a running test
function. A `console.warn` in `Component.onCompleted`, and every error thrown
by a binding evaluated while the scene is being built, are dropped by QtTest's
own message handler before any of this can see them. What reaches the output
is what the engine reports while a test body is running — which is where the
drivers do all of their work, and is exactly where D34's TypeError was.

THE REST IS A SECOND ENGINE (PLAN D38), and the tests for it are at the foot
of this file. `tools/qmlprobe/Probe.qml` loads the same staged scene under
plain `qml`, which installs no handler and prints the engine's own line with
nothing in front of it — so the same rule reads both, and the prefix that
looked like the shape of a fault turns out to be optional.
"""

import subprocess
import sys
from pathlib import Path

from test_gen_theme_qml import ROOT

sys.path.insert(0, str(ROOT / "tools"))

import dependents  # noqa: E402
import qmlerrors  # noqa: E402

SCRIPTS = (
    "ops/ralph/hudshots.sh",
    "ops/ralph/notifyshots.sh",
    "ops/ralph/barshots.sh",
)

# A green run of the notification corner's harness, verbatim, including the
# one sampled line its settle driver narrates.
CLEAN = """\
********* Start testing of qmltestrunner *********
Config: Using QtTest library 6.11.1, Qt 6.11.1 (x86_64-little_endian-lp64 shared (dynamic) release build; by GCC 15.3.0), nixos 26.11
PASS   : qmltestrunner::NotifySettle::initTestCase()
PASS   : qmltestrunner::NotifySettle::test_a_replacement_updates_the_plate_it_is_replacing()
QDEBUG : qmltestrunner::NotifySettle::test_a_second_notification_fades_only_itself() qml: the arrival, sampled: 0.86/0 0.86/0.433 0.86/0.615 0.86/0.73 0.86/0.801 0.86/0.842
PASS   : qmltestrunner::NotifySettle::test_a_second_notification_fades_only_itself()
PASS   : qmltestrunner::NotifySettle::test_a_withdrawal_moves_no_other_plate()
PASS   : qmltestrunner::NotifySettle::cleanupTestCase()
PASS   : qmltestrunner::NotifyShots::initTestCase()
PASS   : qmltestrunner::NotifyShots::test_the_sheet()
PASS   : qmltestrunner::NotifyShots::cleanupTestCase()
Totals: 8 passed, 0 failed, 0 skipped, 0 blacklisted, 4507ms
********* Finished testing of qmltestrunner *********
"""

# The same run with D34's fault back in it: two thrown errors, still eight
# passes. The `file://` paths are inside the stage, which is where the
# harnesses render from.
THREW = """\
********* Start testing of qmltestrunner *********
Config: Using QtTest library 6.11.1, Qt 6.11.1 (x86_64-little_endian-lp64 shared (dynamic) release build; by GCC 15.3.0), nixos 26.11
PASS   : qmltestrunner::NotifySettle::initTestCase()
QWARN  : qmltestrunner::NotifySettle::test_a_second_notification_fades_only_itself() file:///tmp/tmp.DxUhi5als9/core/NotifyModel.qml:113: TypeError: Cannot read property 'count' of undefined
PASS   : qmltestrunner::NotifySettle::test_a_second_notification_fades_only_itself()
QWARN  : qmltestrunner::NotifySettle::test_a_withdrawal_moves_no_other_plate() file:///tmp/tmp.DxUhi5als9/Toast.qml:17: ReferenceError: nosuchthing is not defined
PASS   : qmltestrunner::NotifySettle::test_a_withdrawal_moves_no_other_plate()
Totals: 8 passed, 0 failed, 0 skipped, 0 blacklisted, 4507ms
********* Finished testing of qmltestrunner *********
"""

STAGE = "/tmp/tmp.DxUhi5als9"


def run(text: str, *args: str, tmp_path: Path) -> subprocess.CompletedProcess:
    log = tmp_path / "runner.log"
    log.write_text(text, "utf-8")
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "qmlerrors.py"), str(log), *args],
        capture_output=True,
        text=True,
    )


# ------------------------------------------------------------------ the rule


def test_a_green_run_that_threw_is_refused():
    """The whole point. Eight passes, zero failures, eleven correct PNGs —
    and two handlers that threw on the way there."""
    threw = qmlerrors.scan(THREW)
    assert [t.error for t in threw] == ["TypeError", "ReferenceError"], threw


def test_a_run_that_threw_nothing_is_left_alone():
    """The clean fixture is a REAL run of a real harness, so this is the
    claim that the gate can be added without turning a working sheet red."""
    assert qmlerrors.scan(CLEAN) == []


def test_a_deliberate_console_warn_is_a_voice_and_not_a_fault():
    """`NiriModel` warns about a line of `niri msg --json event-stream` it
    refuses to parse, and that warning is the service doing its job. A rule
    that refused every QWARN would make the shell's own honesty a failure."""
    voice = (
        "QWARN  : qmltestrunner::BarShots::test_the_sheet() qml: "
        "NiriModel: ignoring a line I cannot parse\n"
    )
    assert qmlerrors.scan(voice) == []


def test_a_console_warn_that_quotes_an_error_name_is_still_a_voice():
    """The discriminator is not "does this line contain the word TypeError".
    It is WHERE the line came from: console output arrives with the `qml:`
    prefix and no source location, and the engine's own errors arrive with a
    location and no prefix."""
    voice = (
        "QWARN  : qmltestrunner::BarShots::test_the_sheet() qml: "
        "refusing the frame early, because a TypeError: here would be worse\n"
    )
    assert qmlerrors.scan(voice) == []


def test_a_sampled_console_log_is_not_a_fault():
    """Three drivers narrate their measurements through `console.log` — the
    settle samples and the eleven "px between the workspaces and the clock"
    lines are the readable half of what those gates assert."""
    assert qmlerrors.scan(CLEAN) == []
    sampled = (
        "QDEBUG : qmltestrunner::BarShots::test_the_sheet() qml: "
        "05-starting.png: -1 px between the workspaces and the clock\n"
    )
    assert qmlerrors.scan(sampled) == []


def test_every_ecmascript_error_the_engine_can_name_is_caught():
    """One rule, one list. `TypeError` is what D34 threw and what a property
    of `undefined` throws; `ReferenceError` is the unqualified access §06's
    QML is full of opportunities for; the rest are the same fault with a
    different word in front of it, and a gate that caught only the two seen
    so far would be a gate written from one bug."""
    for name in qmlerrors.ERROR_NAMES:
        line = (
            "QWARN  : qmltestrunner::Suite::test_x() "
            f"file:///stage/Thing.qml:7: {name}: something\n"
        )
        got = qmlerrors.scan(line)
        assert [t.error for t in got] == [name], (name, got)


def test_a_throw_carries_the_file_the_line_and_the_test_it_happened_in():
    """A refusal that says "something threw" is a refusal nobody can act on.
    Everything needed to find it is on the line the engine printed: which
    file, which line of it, and which test body was running."""
    first = qmlerrors.scan(THREW)[0]
    assert first.where == f"file://{STAGE}/core/NotifyModel.qml:113"
    assert first.test == "NotifySettle::test_a_second_notification_fades_only_itself"
    assert first.message == "Cannot read property 'count' of undefined"


def test_the_stage_is_named_relative_to_itself():
    """The harnesses render from a temporary stage, so every path in the
    output is `file:///tmp/tmp.XXXX/…` — a prefix that is different on every
    run and means nothing to a reader. Told where the stage was, the report
    says `core/NotifyModel.qml:113`, which is a path in this repository."""
    threw = qmlerrors.scan(THREW, stage=STAGE)
    assert [t.where for t in threw] == ["core/NotifyModel.qml:113", "Toast.qml:17"]


def test_a_run_whose_totals_are_green_says_so_in_the_refusal():
    """The report has to carry the contradiction it is resolving, because the
    reader has just watched the runner say everything passed."""
    assert qmlerrors.totals(THREW) == "8 passed, 0 failed, 0 skipped, 0 blacklisted"
    assert qmlerrors.totals("nothing like a totals line") is None


def test_one_fault_in_a_delegate_is_one_finding_and_a_count():
    """The first real run of this gate — a throwing handler put into
    `Toast.qml` on purpose — printed the SAME line fourteen times, once per
    plate the sheet builds. The count is worth keeping (a throw per delegate
    and a throw once are different bugs) and fourteen copies of one sentence
    would bury a second fault under the first."""
    per_delegate = "".join(
        "QWARN  : qmltestrunner::NotifyShots::test_the_sheet() "
        "file:///stage/Toast.qml:129: TypeError: Cannot read property 'count' "
        "of undefined\n"
        for _ in range(14)
    )
    assert len(qmlerrors.scan(per_delegate)) == 14
    collapsed = qmlerrors.collapse(qmlerrors.scan(per_delegate))
    assert len(collapsed) == 1
    assert collapsed[0][1] == 14


def test_two_faults_keep_the_order_they_threw_in():
    collapsed = qmlerrors.collapse(qmlerrors.scan(THREW))
    assert [t.error for t, _ in collapsed] == ["TypeError", "ReferenceError"]
    assert [n for _, n in collapsed] == [1, 1]


# --------------------------------------------------------------- the command


def test_the_command_refuses_and_names_what_to_do(tmp_path):
    got = run(THREW, "--stage", STAGE, "--rerun", "bash ops/ralph/notifyshots.sh", tmp_path=tmp_path)
    assert got.returncode == 1, got.stdout + got.stderr
    assert "core/NotifyModel.qml:113" in got.stdout
    assert "TypeError" in got.stdout
    assert "8 passed, 0 failed" in got.stdout
    assert "bash ops/ralph/notifyshots.sh" in got.stdout


def test_the_command_is_quiet_about_a_clean_run(tmp_path):
    got = run(CLEAN, tmp_path=tmp_path)
    assert got.returncode == 0, got.stdout + got.stderr
    assert "qmlerrors" in got.stdout


def test_a_missing_log_is_news_and_not_a_pass(tmp_path):
    """The gate runs after the runner, in a script under `set -e`. If the log
    is not there at all, something went wrong ahead of this — and a scanner
    that read no lines and said "clean" would be the exact silence it exists
    to remove."""
    got = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "qmlerrors.py"), str(tmp_path / "absent.log")],
        capture_output=True,
        text=True,
    )
    assert got.returncode == 2, got.stdout + got.stderr


# ----------------------------------------------------------------- the seam


def test_every_shot_harness_hands_the_runners_output_to_this():
    """The seam, and the reason D36 was one item rather than three: a rule
    that is not wired into a harness is a rule about nothing. Each script has
    to CAPTURE the runner's output — `tee`, so a human still watches it go by
    — and then hand the capture to this scanner."""
    for script in SCRIPTS:
        text = (ROOT / script).read_text("utf-8")
        assert "tools/qmlerrors.py" in text, f"{script} does not run the scanner"
        assert "| tee " in text, f"{script} does not capture the runner's output"
        assert "--stage" in text, f"{script} does not tell the scanner where it staged"


def test_the_three_gates_read_this_scanner_and_nothing_else_does():
    """`tools/verify.py` derives which gates to run from what changed, and the
    only way it can learn that a shot harness now reads a Python file is the
    `also` table in `dependents`. A scanner whose change ran no shot harness
    would be a scanner nobody could safely edit."""
    got = dependents.qml_readers(ROOT, ["tools/qmlerrors.py"])
    assert set(got) == set(SCRIPTS), got


# --------------------------------------------------- the second engine (D38)
#
# What QtTest never showed anybody. The runner drops every message logged
# while no test function is RUNNING, and the narrowing is alphabetical: the
# first driver in a directory has its whole scene built before the run
# begins, and is silent; every later driver's is built between two test
# functions, and is not. Recorded with two identical drivers in one temporary
# directory, and only the second one was heard:
#
#     PASS   : qmltestrunner::Probea::cleanupTestCase()
#     QWARN  : qmltestrunner::UnknownTestFunc() qml: warn from b onCompleted
#     QWARN  : qmltestrunner::UnknownTestFunc() …/tst_b.qml:7: TypeError: …
#     PASS   : qmltestrunner::Probeb::initTestCase()
#
# So which surface of a harness D36 covers was decided by a filename, and the
# uncovered one is `tst_fit`, `tst_settle`, `tst_settle`. The other half is a
# different ENGINE: `tools/qmlprobe/Probe.qml` loads the same staged scene
# under plain `qml`, which installs no handler and writes the engine's line
# bare. Same rule reads both, because the discriminator was never the prefix.

# A clean probe of the bar's strip, verbatim — `bash /tmp/qstage.sh jv-bar
# barshots` over this stage, Qt 6.11.1, QT_QPA_PLATFORM=offscreen,
# QT_FORCE_STDERR_LOGGING=1.
PROBED = """\
qml: qmlprobe: the scene built 11 objects
"""

# The same probe with D38's own shape injected into the strip's root —
# `property int injected: root.desk.nothingHere.count`, a binding evaluated as
# the scene is built. Note what is NOT here: a `QWARN :`, a test name, or a
# `Totals:` line. This engine has none of them.
PROBED_THREW = """\
file:///tmp/tmp.qVTcKjXeZp/shots/Strip.qml:30: TypeError: Cannot read property 'count' of undefined
qml: qmlprobe: the scene built 11 objects
"""


def test_the_second_engine_prints_no_prefix_and_is_still_read():
    """The whole D38 seam. `qml` writes what the engine wrote and nothing in
    front of it, so a scanner that required QtTest's `QWARN :` would read this
    output as an empty one — which is exactly how a fault in the first
    driver's scene stayed invisible for as long as it did."""
    threw = qmlerrors.scan(PROBED_THREW)
    assert [(t.error, t.where) for t in threw] == [
        ("TypeError", "file:///tmp/tmp.qVTcKjXeZp/shots/Strip.qml:30")
    ], threw


def test_a_throw_with_no_test_around_it_names_no_test():
    """There was no test. The report must not invent one — `in ()` would be a
    sentence about a test function that does not exist."""
    (throw,) = qmlerrors.scan(PROBED_THREW)
    assert throw.test == ""
    assert "\n    in" not in str(throw), str(throw)


def test_the_probes_own_census_is_a_voice_and_not_a_fault():
    """The probe says how many objects the scene built, which is the only
    thing distinguishing a clean run from one that loaded nothing. It goes out
    as `console.log`, so it carries the `qml:` prefix and no location — a
    voice, under the same rule that keeps `NiriModel`'s refusal a voice."""
    assert qmlerrors.scan(PROBED) == []


def test_the_second_engines_stage_is_named_relative_to_itself_too():
    """`--stage` is how a `file:///tmp/tmp.XXXX/…` becomes a path someone can
    open. The probe renders from the same stage the runner does, so it gets
    the same treatment."""
    (throw,) = qmlerrors.scan(PROBED_THREW, stage="/tmp/tmp.qVTcKjXeZp")
    assert throw.where == "shots/Strip.qml:30", throw


def test_every_shot_harness_runs_the_second_engine_over_its_own_scene():
    """The seam again, one engine over. A probe that exists and is never run
    is a probe about nothing — and since the shared body lives outside all
    three harnesses, the only thing that can say each of them loads it is
    this."""
    for script in SCRIPTS:
        text = (ROOT / script).read_text("utf-8")
        assert "tools/qmlprobe/Probe.qml" in text, f"{script} does not stage the probe"
        assert "warnprobe.qml" in text, f"{script} does not load its probe document"
        assert "/bin/qml" in text, f"{script} does not run the second engine"
        assert "QT_FORCE_STDERR_LOGGING" in text, (
            f"{script} would read an empty log: this Qt is built with the "
            "journald backend and `tee` makes stderr a pipe"
        )


def test_each_harness_has_a_probe_document_the_test_runner_will_not_run():
    """Both halves share a directory: qmltestrunner is handed `$stage/shots`
    and runs `tst_*.qml`, and the probe document sits right beside them. It is
    lowercase, which is also what keeps it from being a QML type anything can
    name by accident."""
    for scene in ("hudshots", "notifyshots", "barshots"):
        doc = ROOT / "tools" / scene / "scene" / "warnprobe.qml"
        assert doc.is_file(), f"{scene} has no probe document"
        assert doc.name.islower(), doc
        body = doc.read_text("utf-8")
        assert "Probe {" in body, f"{doc} does not instantiate the shared probe"
        assert "subject:" in body, f"{doc} gives the probe nothing to count"


def test_the_three_gates_read_the_shared_probe_body():
    """`tools/qmlprobe/Probe.qml` is staged into all three harnesses and lives
    in none of them, so nothing about its path says which gates open it. The
    mount table in `dependents` is what says so, and this is what holds the
    table to it — a change to the probe that ran no harness would be a change
    nobody could verify."""
    got = dependents.qml_readers(ROOT, ["tools/qmlprobe/Probe.qml"])
    assert set(got) == set(SCRIPTS), got
