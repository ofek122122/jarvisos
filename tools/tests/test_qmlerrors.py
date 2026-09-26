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

THE SECOND ENGINE (PLAN D38) is plain `qml`: `tools/qmlprobe/Probe.qml` loads
the same staged scene under it, and it installs no handler and prints the
engine's own line with nothing in front of it — so the same rule reads both,
and the prefix that looked like the shape of a fault turns out to be optional.

AND A THIRD (PLAN D39), whose tests are at the foot of this file too: the real
`.#jv-hud`, quickshell, photographed through a real compositor by
`ops/ralph/hudscreens.sh`. It writes a level, a CATEGORY and `@path[line:col]`
rather than `QWARN :` and `file://…:line:`, it separates `console.*` from the
engine's own errors at the source, and it colours its output with ANSI escapes
whether or not anything is watching — which is the one thing that could have
made this gate green forever over a HUD that threw on every frame.
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
    "ops/ralph/wallshots.sh",
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


def test_the_four_shot_gates_read_this_scanner_and_no_other_qml_gate_does():
    """`tools/verify.py` derives which gates to run from what changed, and the
    only way it can learn that a shot harness now reads a Python file is the
    `also` table in `dependents`. A scanner whose change ran no shot harness
    would be a scanner nobody could safely edit.

    There is a FIFTH reader since D39 — `hudscreens.sh`, the only gate that
    loads `shell.qml` at all — and it is not here because it is not derived
    from any import graph: it is a declared gate, and the test for it is at
    the foot of this file. The fourth of the derived ones is `wallshots.sh`
    (PLAN E8), which is the sheet of the wallpaper."""
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
# uncovered one is `tst_fit`, `tst_settle`, `tst_settle`, `tst_shots` — the
# wallpaper's harness has ONE driver, so the uncovered surface there is the
# whole of it. The other half is a
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


def test_the_four_gates_read_the_shared_probe_body():
    """`tools/qmlprobe/Probe.qml` is staged into all four harnesses and lives
    in none of them, so nothing about its path says which gates open it. The
    mount table in `dependents` is what says so, and this is what holds the
    table to it — a change to the probe that ran no harness would be a change
    nobody could verify."""
    got = dependents.qml_readers(ROOT, ["tools/qmlprobe/Probe.qml"])
    assert set(got) == set(SCRIPTS), got


# ---------------------------------------------------- the third engine (D39)
#
# The only one that ever draws the REAL HUD. `ops/ralph/hudscreens.sh` runs
# `.#jv-hud` — quickshell, its layer-shell surface, its own bus bridge —
# through a real compositor twelve times in a run, and until D39 nothing had
# ever read a line of what it said.
#
# D38 predicted the obstacle would be `QT_FORCE_STDERR_LOGGING`: this Qt is
# built with the journald backend, so a Qt program whose stderr is not a
# terminal prints nothing. MEASURED, and that is not what happens — quickshell
# installs a message handler of its OWN, and its output reaches a redirected
# file regardless. What it writes there is a third shape, and the fixtures
# below are it, recorded from quickshell 0.3.0 under
# `QT_QPA_PLATFORM=offscreen` with a probe shell whose bindings read a
# property of `undefined` and an undeclared name.

QS_THREW = """\
  INFO: Launching config: "/tmp/qsy/shell.qml"
  INFO: Shell ID: "0865055f43ce53d7ea30bc3ec59129c7" Path ID "0865055f43ce53d7ea30bc3ec59129c7"
  INFO: Saving logs to "/tmp/qsy/run/quickshell/by-id/tlda15qzxlt/log.qslog"
  WARN scene: @sub/Thing.qml[4:-1]: TypeError: Cannot read property 'nothingHere' of undefined
  INFO: Configuration Loaded
  WARN scene: @sub/Thing.qml[5:-1]: ReferenceError: undefinedThing is not defined
Shell cwd was reset to /home/ofek/jarvisos-ralph
"""

# Every `console.*` a QML file can call, through quickshell's handler. Note
# that `console.log` arrives as DEBUG and `console.error` as ERROR: the level
# is not the discriminator, the CATEGORY is.
QS_VOICES = """\
 DEBUG qml: a log
  INFO qml: an info
 DEBUG qml: a debug
  WARN qml: a warn
 ERROR qml: an error
  INFO: Configuration Loaded
"""

# The same fault as the first line of QS_THREW, as quickshell writes it when
# nothing has told it not to colour its output. This is why the harness sets
# NO_COLOR=1, and it is a fixture rather than a sentence because the failure
# it prevents is silent: every line reads as unprefixed noise and the scan
# comes back clean.
QS_COLOURED = (
    "\x1b[33m  WARN\x1b[97m scene\x1b[0m: @shell.qml[8:-1]: "
    "TypeError: Cannot read property 'count' of undefined\n"
)


def test_the_third_engines_errors_are_the_same_rule():
    threw = qmlerrors.scan(QS_THREW)
    assert [t.error for t in threw] == ["TypeError", "ReferenceError"]
    assert [t.where for t in threw] == ["sub/Thing.qml:4", "sub/Thing.qml:5"]
    assert threw[0].message == "Cannot read property 'nothingHere' of undefined"


def test_quickshells_own_narration_is_not_a_fault():
    """`INFO: Launching config`, `INFO: Configuration Loaded` — the lines the
    harness already waits for. A gate that refused its own readiness signal
    would never have run at all."""
    assert qmlerrors.scan(QS_THREW)[0].where == "sub/Thing.qml:4"
    quiet = "\n".join(l for l in QS_THREW.splitlines() if "scene:" not in l)
    assert qmlerrors.scan(quiet) == []


def test_every_console_voice_survives_the_third_engine_too():
    """The category is what separates them, and it is quickshell's own: every
    `console.*` goes out under `qml` and the engine's errors under `scene`.
    The LEVEL is not the discriminator — `console.error` is ERROR and
    `console.log` is DEBUG, and neither is a throw."""
    assert qmlerrors.scan(QS_VOICES) == []


def test_a_voice_that_quotes_a_throw_is_still_a_voice():
    """The `qml` category holds whatever this repo's QML chose to say, which
    can include the text of an error it handled itself."""
    voice = "  WARN qml: @Corner.qml[4:-1]: TypeError: handled, and reported\n"
    assert qmlerrors.scan(voice) == []


def test_the_colour_escapes_are_why_the_harness_sets_no_color():
    """Recorded, because the failure is silent. Quickshell colours its output
    whether or not anything is watching, and a coloured log scans clean — so
    the gate would pass forever with a HUD that threw on every frame."""
    assert qmlerrors.scan(QS_COLOURED) == []
    assert qmlerrors.scan(QS_COLOURED.replace("\x1b[33m", "").replace(
        "\x1b[97m", ""
    ).replace("\x1b[0m", ""))


def test_a_column_the_engine_did_not_have_is_not_printed():
    """`[8:-1]` is quickshell saying it has a line and no column. A report
    that printed `shell.qml:8:-1` would be naming a position no file has."""
    (throw,) = qmlerrors.scan("  WARN scene: @shell.qml[8:-1]: TypeError: x\n")
    assert throw.where == "shell.qml:8"
    (known,) = qmlerrors.scan("  WARN scene: @shell.qml[8:22]: TypeError: x\n")
    assert known.where == "shell.qml:8:22"


def test_the_third_engines_paths_are_reported_under_the_root_they_are_under():
    """Quickshell's paths are relative to the directory holding `shell.qml`,
    which at runtime is a store path. Told where that lives in this
    repository, the report names a file a reader can open."""
    (throw,) = qmlerrors.scan(
        "  WARN scene: @core/BusModel.qml[113:-1]: TypeError: x\n",
        prefix="shell/jv-hud",
    )
    assert throw.where == "shell/jv-hud/core/BusModel.qml:113"


def test_an_absolute_path_is_left_where_the_engine_put_it():
    """A path that is already absolute is not relative to the shell's root,
    so putting the root in front of it would invent a place."""
    (throw,) = qmlerrors.scan(
        "  WARN scene: @/nix/store/abc-jv-hud/Corner.qml[7:-1]: TypeError: x\n",
        prefix="shell/jv-hud",
    )
    assert throw.where == "/nix/store/abc-jv-hud/Corner.qml:7"


def test_every_log_of_a_run_is_scanned_and_the_report_names_which(tmp_path):
    """`hudscreens.sh` starts a fresh jv-hud per shot and per idle window, so
    a scan of one of them would have been the harness choosing which surface
    to believe."""
    clean = tmp_path / "01-quiet-hud.log"
    clean.write_text(QS_VOICES, "utf-8")
    dirty = tmp_path / "idle-lit-hud.log"
    dirty.write_text(QS_THREW, "utf-8")
    got = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "qmlerrors.py"),
            str(clean),
            str(dirty),
            "--prefix",
            "shell/jv-hud",
        ],
        capture_output=True,
        text=True,
    )
    assert got.returncode == 1, got.stdout + got.stderr
    assert "idle-lit-hud.log" in got.stdout
    assert "01-quiet-hud.log" not in got.stdout, "a clean log is not a finding"
    assert "shell/jv-hud/sub/Thing.qml:4" in got.stdout


def test_two_clean_logs_are_one_verdict(tmp_path):
    for name in ("a-hud.log", "b-hud.log"):
        (tmp_path / name).write_text(QS_VOICES, "utf-8")
    got = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "qmlerrors.py"),
            str(tmp_path / "a-hud.log"),
            str(tmp_path / "b-hud.log"),
        ],
        capture_output=True,
        text=True,
    )
    assert got.returncode == 0, got.stdout + got.stderr
    assert "across 2 logs" in got.stdout


# ------------------------------------------------------- the seam, once more

HUDSCREENS = "ops/ralph/hudscreens.sh"


def test_the_real_hud_gate_hands_every_shells_log_to_this():
    """The D36 seam for the third engine. `hudscreens.sh` is the only gate in
    this repo that loads `shell.qml` at all, and the three things it must do
    are all silent when they are missing: capture the logs (it already does —
    `Proc` writes each to a file), turn quickshell's colour off, and hand the
    lot here."""
    text = (ROOT / HUDSCREENS).read_text("utf-8")
    assert "tools/qmlerrors.py" in text, "the real HUD's gate does not run the scanner"
    assert "NO_COLOR" in text, (
        "without NO_COLOR quickshell's ANSI escapes make every line unprefixed "
        "noise, and the scan comes back clean whatever the HUD did"
    )
    assert "-hud.log" in text, "the gate does not hand the scanner the shells' logs"
    assert "--prefix" in text, "the report would name paths relative to a store path"


def test_every_gate_that_runs_a_real_quickshell_declares_that_it_reads_this():
    """They are DECLARED gates — what they read is a derivation, not an import
    graph — so nothing can derive that either now opens a Python file. The
    declaration is what makes a change to this scanner say so.

    Two of them since D41: `hudscreens.sh` photographs the HUD and
    `shellload.sh` loads all three shells, and they are the only things in this
    repo that ever run quickshell at all. A third would be a third
    declaration."""
    got = dict(dependents.declared_readers(ROOT, ["tools/qmlerrors.py"]))
    assert sorted(g.script for g in got) == sorted(
        [HUDSCREENS, "ops/ralph/shellload.sh"]
    ), got
