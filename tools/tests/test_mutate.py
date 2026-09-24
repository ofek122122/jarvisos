"""tools/mutate.py — the loop's own mutation harness (PLAN B48, B49).

Every iteration of the Ralph loop claims a number like "six mutations, six
caught". That claim is only worth the paper it is written on if the mutant
actually EXECUTED, and in iteration 70 one of them did not: CPython validates
a cached `.pyc` against the source's (mtime *seconds*, size), so an
equal-length edit landing in the same second as the write before it reuses
stale bytecode and the suite reports a PASS for code that never ran. The
mutation "survived", and the tell only arrived later, as a full-suite failure
on a RESTORED file that was still running the mutant.

These tests are the harness's spine, and two of them are the point:

* `test_a_stale_pyc_is_read_without_the_harness_env_and_cannot_be_with_it`
  reproduces that bug in a subprocess, with the un-fixed run as its control —
  and it records a correction to B48's stated fix. `python -B` alone does
  NOTHING here: it stops bytecode being WRITTEN, not read. What worked in
  iteration 70 was the other half, clearing `__pycache__`. This harness uses
  a fresh `PYTHONPYCACHEPREFIX` per suite run instead, which is the same
  guarantee made per-run and impossible to forget.

* `test_a_canary_the_suite_survives_aborts_the_whole_run` holds the control
  that makes every other number honest. Before trusting a single mutation,
  the harness makes importing the target file impossible and demands that the
  suite go RED. If it does not, the tests do not execute that file at all,
  every mutation would be a silent survivor, and the harness refuses to
  report anything.

B49 adds QML and Rust, and its own premise was the thing that turned out to
be wrong: it said the stale-cache half "cannot bite" them.
`test_a_stale_qmlc_is_read_without_the_harness_env_and_cannot_be_with_it`
reproduces it in QML with the real `qmltestrunner` — Qt caches compiled QML
in the user's HOME and validates it against (mtime, size) exactly like a
`.pyc` — which is why every language now gets a private cache and every
write this harness makes gets a whole second strictly newer than the last.

B55 adds the second control. The canary above proves EXECUTION, and the five
claims this repo makes about a relation between two services are not made by
executing anything — invariant 1 forbids the import, so they are made by
matching a line in the other file's source. The unloadable canary lives on
every one of them. `test_a_file_the_suite_reads_instead_of_importing_is_
graded_after_it_is_erased` is the new one, and the pair of sentences it
protects is the point: the report says which control killed the suite, so a
score against a file the suite only greps cannot be read as a score against
one it runs.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import mutate  # noqa: E402

# --------------------------------------------------------------- spec parsing

ONE = """\
# a comment, and a blank line follow

@ the turn gap widened
services/jv-voice/jv_voice/service.py
- TURN_GAP_S = 0.5
+ TURN_GAP_S = 0.9
"""


def test_a_spec_parses_into_a_label_a_path_and_one_hunk():
    (m,) = mutate.parse_spec(ONE)
    assert m.label == "the turn gap widened"
    assert m.path == "services/jv-voice/jv_voice/service.py"
    assert m.old == "TURN_GAP_S = 0.5"
    assert m.new == "TURN_GAP_S = 0.9"


def test_hunk_lines_join_in_order_and_keep_their_indentation():
    (m,) = mutate.parse_spec(
        "@ the guard dropped\n"
        "a/b.py\n"
        "-     if not ok:\n"
        "-         return None\n"
        "+     if False:\n"
        "+         return None\n"
    )
    assert m.old == "    if not ok:\n        return None"
    assert m.new == "    if False:\n        return None"


def test_a_hunk_with_no_plus_lines_is_a_deletion():
    (m,) = mutate.parse_spec("@ gone\na/b.py\n- os.fchmod(fd, 0o640)\n")
    assert m.new == ""


def test_two_blocks_parse_as_two_mutations_in_file_order():
    muts = mutate.parse_spec(
        "@ one\na/b.py\n- x = 1\n+ x = 2\n\n@ two\na/c.py\n- y = 1\n+ y = 2\n"
    )
    assert [(m.label, m.path) for m in muts] == [("one", "a/b.py"), ("two", "a/c.py")]


def test_a_hunk_before_any_label_is_an_error():
    with pytest.raises(mutate.SpecError, match="before any"):
        mutate.parse_spec("- x = 1\n+ x = 2\n")


def test_a_block_with_no_minus_lines_is_an_error():
    # `old` is what locates the edit; an empty one would match everywhere.
    with pytest.raises(mutate.SpecError, match="no `-`"):
        mutate.parse_spec("@ nothing\na/b.py\n+ x = 2\n")


def test_a_block_with_no_path_is_an_error():
    with pytest.raises(mutate.SpecError, match="no file"):
        mutate.parse_spec("@ nothing\n- x = 1\n+ x = 2\n")


def test_a_second_path_line_in_one_block_is_an_error():
    with pytest.raises(mutate.SpecError, match="two file"):
        mutate.parse_spec("@ two paths\na/b.py\na/c.py\n- x = 1\n+ x = 2\n")


def test_an_empty_label_is_an_error():
    with pytest.raises(mutate.SpecError, match="label"):
        mutate.parse_spec("@\na/b.py\n- x = 1\n+ x = 2\n")


def test_a_path_that_escapes_the_repo_is_refused(tmp_path):
    (m,) = mutate.parse_spec("@ out\n../../etc/passwd\n- root\n+ toor\n")
    with pytest.raises(mutate.HarnessError, match="outside"):
        mutate.resolve(m, root=tmp_path)


def test_an_absolute_path_is_refused(tmp_path):
    (m,) = mutate.parse_spec("@ out\n/etc/passwd\n- root\n+ toor\n")
    with pytest.raises(mutate.HarnessError, match="outside|absolute"):
        mutate.resolve(m, root=tmp_path)


# ------------------------------------------------------------ applying a hunk


def test_a_hunk_that_matches_once_is_applied():
    assert mutate.apply_once("a\nx = 1\nb\n", "x = 1", "x = 2") == "a\nx = 2\nb\n"


def test_a_hunk_that_matches_twice_is_an_error_not_a_coin_flip():
    with pytest.raises(mutate.HarnessError, match="2 times"):
        mutate.apply_once("x = 1\nx = 1\n", "x = 1", "x = 2")


def test_a_hunk_that_matches_nothing_is_an_error():
    with pytest.raises(mutate.HarnessError, match="does not appear"):
        mutate.apply_once("y = 1\n", "x = 1", "x = 2")


def test_a_hunk_that_changes_nothing_is_an_error():
    # A mutation equal to the original tests nothing and would be reported
    # as "caught" or "survived" all the same.
    with pytest.raises(mutate.HarnessError, match="identical"):
        mutate.apply_once("x = 1\n", "x = 1", "x = 1")


# ------------------------------------------------------------------- canary


def test_the_canary_is_appended_and_leaves_the_original_text_alone():
    out = mutate.with_canary("import os\nVALUE = 1\n")
    assert out.startswith("import os\nVALUE = 1\n")
    assert mutate.CANARY_MARK in out
    assert out.endswith("\n")


def test_the_canary_adds_the_newline_a_file_without_one_is_missing():
    out = mutate.with_canary("VALUE = 1")
    assert out.splitlines()[0] == "VALUE = 1"
    assert mutate.CANARY_MARK in out.splitlines()[-1]


def test_the_canary_is_a_module_level_statement_at_column_zero():
    # It has to run on IMPORT, from inside any trailing indented block.
    line = [l for l in mutate.with_canary("if True:\n    pass\n").splitlines() if mutate.CANARY_MARK in l][0]
    assert not line.startswith((" ", "\t"))


# ---------------------------------------------------- the stale bytecode bug


def test_a_stale_pyc_is_read_without_the_harness_env_and_cannot_be_with_it(tmp_path):
    """B48, reproduced, with the un-fixed run as the control.

    The edit below is EQUAL LENGTH and the mtime is put back to the second it
    had before, which is what "landed in the same second" means to CPython's
    (mtime, size) check. Without the harness's env the second run prints the
    OLD value out of a cached `.pyc` for source that no longer exists.
    """
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    src = pkg / "m.py"
    src.write_text('VALUE = "old"\n', encoding="utf-8")
    (pkg / "run.py").write_text("import m; print(m.VALUE)\n", encoding="utf-8")

    def run(env_extra: dict[str, str]) -> str:
        env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), **env_extra}
        out = subprocess.run(
            [sys.executable, "run.py"],
            cwd=pkg,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()

    assert run({}) == "old"  # writes pkg/__pycache__/m.*.pyc
    assert (pkg / "__pycache__").is_dir(), "no cache was written; the control is void"

    was = src.stat().st_mtime
    src.write_text('VALUE = "new"\n', encoding="utf-8")  # same length
    import os

    os.utime(src, (was, was))

    # The control: this is the loop's pre-iteration-70 practice, and it grades
    # code that never ran.
    assert run({}) == "old"
    # And the correction to B48: `-B` alone does not fix it. It stops the
    # cache being WRITTEN, which is not the half that bites.
    assert run({"PYTHONDONTWRITEBYTECODE": "1"}) == "old"
    # What the harness actually does: a cache directory of its own, empty.
    fresh = tmp_path / "fresh"
    assert run(mutate.python_env(fresh)) == "new"


def test_python_env_names_a_fresh_cache_dir_and_forbids_writing_beside_the_source(tmp_path):
    env = mutate.python_env(tmp_path / "c")
    assert env["PYTHONPYCACHEPREFIX"] == str(tmp_path / "c")
    assert env["PYTHONDONTWRITEBYTECODE"] == "1"


# ----------------------------------------------------------------- the run


@pytest.fixture(autouse=True)
def _harness_logs_under_tmp(tmp_path_factory, monkeypatch):
    """`run()` KEEPS its run tree whenever a mutation survived or it aborted
    (B56), and these tests do both dozens of times. Left alone that is a
    directory per test in the real /tmp, forever — 189 of them after twelve
    suite runs, which is how this was found.

    The harness is right to keep them: the caller is told where the tree is
    and owns it from there. So the fix belongs here, in the caller. Redirect
    `mkdtemp`'s default parent at pytest's own temporary directory and the
    trees are still real, still inspectable while a test runs, and swept with
    everything else pytest makes."""
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path_factory.mktemp("harness-logs")))


class FakeSuite:
    """A test suite that fails when the file says MUTANT — i.e. one that
    catches everything. Records the env of every run it is handed."""

    def __init__(self, path: Path, catches: bool = True) -> None:
        self.path = path
        self.catches = catches
        self.envs: list[dict[str, str]] = []
        self.scratches: list[Path] = []
        self.scratch_fresh: list[bool] = []
        self.seen: list[str] = []

    def __call__(self, env: dict[str, str], scratch: Path) -> bool:
        self.envs.append(dict(env))
        # Checked HERE and not afterwards: the whole scratch tree is thrown
        # away when the run ends, so "it was a fresh empty directory" is only
        # answerable while the suite is being handed it.
        self.scratches.append(scratch)
        # "Empty" means empty of any SUITE's leavings. The harness plants one
        # file of its own before it calls, naming the run (B56), and that is
        # what the run dir is allowed to hold and nothing else.
        self.scratch_fresh.append(
            scratch.is_dir()
            and sorted(p.name for p in scratch.iterdir()) == [mutate.WHAT]
        )
        text = self.path.read_text(encoding="utf-8")
        self.seen.append(text)
        if mutate.CANARY_MARK in text:
            return False  # the file is imported, so the canary kills the run
        if self.catches and "MUTANT" in text:
            return False
        return True


@pytest.fixture
def tree(tmp_path):
    (tmp_path / "svc").mkdir()
    src = tmp_path / "svc" / "thing.py"
    src.write_text("VALUE = 1\nOTHER = 2\n", encoding="utf-8")
    return tmp_path, src


SPEC = "@ value mutated\nsvc/thing.py\n- VALUE = 1\n+ VALUE = 'MUTANT'\n"


def test_a_caught_mutation_is_reported_and_the_file_comes_back_byte_identical(tree):
    root, src = tree
    before = src.read_bytes()
    suite = FakeSuite(src)
    report = mutate.run(mutate.parse_spec(SPEC), suite, root=root)
    assert [(o.label, o.status) for o in report.outcomes] == [("value mutated", "caught")]
    assert report.caught == 1 and report.survived == 0
    assert src.read_bytes() == before
    assert "1/1" in report.summary()


def test_a_missed_mutation_is_reported_as_a_survivor(tree):
    root, src = tree
    report = mutate.run(mutate.parse_spec(SPEC), FakeSuite(src, catches=False), root=root)
    assert [o.status for o in report.outcomes] == ["survived"]
    assert report.survived == 1
    assert "survived" in report.summary()
    assert "value mutated" in report.summary()


def test_every_suite_run_gets_its_own_empty_cache_dir(tree):
    root, src = tree
    suite = FakeSuite(src)
    mutate.run(mutate.parse_spec(SPEC), suite, root=root)
    dirs = [e["PYTHONPYCACHEPREFIX"] for e in suite.envs]
    assert len(dirs) == len(set(dirs)) >= 4  # baseline, canary, mutation, baseline
    for d in dirs:
        assert not list(Path(d).iterdir()) if Path(d).exists() else True


def test_the_run_is_baseline_canary_mutation_baseline_in_that_order(tree):
    root, src = tree
    suite = FakeSuite(src)
    mutate.run(mutate.parse_spec(SPEC), suite, root=root)
    shape = [
        "canary" if mutate.CANARY_MARK in t else "mutant" if "MUTANT" in t else "clean"
        for t in suite.seen
    ]
    assert shape == ["clean", "canary", "mutant", "clean"]


def test_a_red_baseline_aborts_before_anything_is_touched(tree):
    root, src = tree
    before = src.read_bytes()
    with pytest.raises(mutate.HarnessError, match="baseline"):
        mutate.run(mutate.parse_spec(SPEC), lambda env, scratch: False, root=root)
    assert src.read_bytes() == before


def test_a_canary_the_suite_survives_aborts_the_whole_run(tree):
    """The control. A suite that stays green with the target file unimportable
    does not execute that file, so no mutation of it can mean anything."""
    root, src = tree
    runs: list[str] = []

    def blind(env: dict[str, str], scratch: Path) -> bool:
        runs.append(src.read_text(encoding="utf-8"))
        return True  # green no matter what the file says

    with pytest.raises(mutate.HarnessError, match="svc/thing.py"):
        mutate.run(mutate.parse_spec(SPEC), blind, root=root)
    assert not any("MUTANT" in t for t in runs), "a mutation ran after a dead canary"
    assert src.read_bytes() == b"VALUE = 1\nOTHER = 2\n"


def test_one_canary_per_file_not_per_mutation(tree):
    root, src = tree
    two = SPEC + "\n@ other mutated\nsvc/thing.py\n- OTHER = 2\n+ OTHER = 'MUTANT2'\n"
    suite = FakeSuite(src)
    report = mutate.run(mutate.parse_spec(two), suite, root=root)
    assert report.caught == 2
    assert sum(1 for t in suite.seen if mutate.CANARY_MARK in t) == 1


def test_the_file_is_restored_when_the_suite_raises(tree):
    root, src = tree
    before = src.read_bytes()

    def boom(env: dict[str, str], scratch: Path) -> bool:
        if "MUTANT" in src.read_text(encoding="utf-8"):
            raise RuntimeError("the runner died")
        return mutate.CANARY_MARK not in src.read_text(encoding="utf-8")

    with pytest.raises(RuntimeError):
        mutate.run(mutate.parse_spec(SPEC), boom, root=root)
    assert src.read_bytes() == before


def test_a_tree_still_red_after_the_last_restore_is_an_error(tree):
    """Iteration 70's real tell: the suite failed on a file that had already
    been put back. The harness asks once more at the end, so the next thing
    the loop does is not built on a tree it has quietly broken."""
    root, src = tree
    state = {"n": 0}

    def flaky(env: dict[str, str], scratch: Path) -> bool:
        state["n"] += 1
        text = src.read_text(encoding="utf-8")
        if mutate.CANARY_MARK in text:
            return False
        if "MUTANT" in text:
            return False
        return state["n"] == 1  # green as a baseline, red at the end

    with pytest.raises(mutate.HarnessError, match="after"):
        mutate.run(mutate.parse_spec(SPEC), flaky, root=root)


def test_a_missing_target_file_is_an_error_before_the_baseline(tree):
    root, _ = tree
    spec = mutate.parse_spec("@ nope\nsvc/absent.py\n- x = 1\n+ x = 2\n")
    calls: list[str] = []
    with pytest.raises(mutate.HarnessError, match="absent.py"):
        mutate.run(spec, lambda env, scratch: calls.append("ran") or True, root=root)
    assert calls == []


def test_an_empty_spec_is_an_error_rather_than_a_perfect_score(tree):
    root, _ = tree
    with pytest.raises(mutate.HarnessError, match="no mutations"):
        mutate.run([], lambda env, scratch: True, root=root)


# ------------------------------------------------------------- the exit code

# The loop reads `$?`, not the prose. These four were written because the
# harness's own first self-run left exactly one survivor: a `main` that
# returned 0 with a mutation still standing, which would have told the loop
# "all caught" in the one case that matters.


@pytest.fixture
def spec_file(tmp_path):
    p = tmp_path / "spec"
    p.write_text("@ x\nsvc/thing.py\n- VALUE = 1\n+ VALUE = 2\n", encoding="utf-8")
    return str(p)


def _report(*statuses: str) -> mutate.Report:
    return mutate.Report([mutate.Outcome(s, "svc/thing.py", s) for s in statuses])


def test_a_survivor_exits_non_zero(spec_file, monkeypatch, capsys):
    monkeypatch.setattr(mutate, "run", lambda *a, **k: _report("caught", "survived"))
    assert mutate.main(["tools", spec_file]) == 1
    assert "survived" in capsys.readouterr().out


def test_a_clean_sweep_exits_zero(spec_file, monkeypatch):
    monkeypatch.setattr(mutate, "run", lambda *a, **k: _report("caught"))
    assert mutate.main(["tools", spec_file]) == 0


def test_a_harness_that_cannot_make_a_claim_exits_two(spec_file, monkeypatch):
    def refuse(*a, **k):
        raise mutate.HarnessError("the canary lived")

    monkeypatch.setattr(mutate, "run", refuse)
    assert mutate.main(["tools", spec_file]) == 2


def test_an_unreadable_spec_exits_two_without_running_anything(tmp_path, monkeypatch):
    bad = tmp_path / "spec"
    bad.write_text("- x = 1\n", encoding="utf-8")
    monkeypatch.setattr(mutate, "run", lambda *a, **k: pytest.fail("ran on a bad spec"))
    assert mutate.main(["tools", str(bad)]) == 2


# ======================================================================= B49
# Three languages, three canaries. Until now the harness graded PYTHON only,
# so the loop's QML numbers ("nine mutations, all caught") and its Rust ones
# were still produced by the hand practice iteration 70 caught out — and the
# question the canary answers is exactly as open there: nothing had ever
# asked whether `qmltest.sh` executes the file an A-track iteration was
# mutating. A `shell/jv-hud/` element no test imports would have graded as
# immune.


def test_each_language_has_a_canary_that_makes_its_file_unloadable():
    py = mutate.with_canary("VALUE = 1\n", mutate.PYTHON)
    qml = mutate.with_canary("import QtQuick\nQtObject {}\n", mutate.QML)
    rs = mutate.with_canary("pub fn f() {}\n", mutate.CARGO)
    assert py.splitlines()[-1].startswith("raise ImportError(")
    assert qml.splitlines()[-1].startswith("***")      # a QML syntax error
    assert rs.splitlines()[-1].startswith("compile_error!(")
    for out in (py, qml, rs):
        assert mutate.CANARY_MARK in out.splitlines()[-1]
        assert not out.splitlines()[-1].startswith((" ", "\t"))


def test_every_language_canary_keeps_the_original_text_byte_for_byte():
    for lang in mutate.LANGUAGES.values():
        src = "a\n  b\n"
        assert mutate.with_canary(src, lang).startswith(src)


def test_the_qml_canary_is_appended_after_the_root_objects_closing_brace():
    # The one place it must land: outside the object, where nothing can read
    # it as a property. Inside, `***` might parse as a binding expression.
    out = mutate.with_canary("import QtQuick\nQtObject {\n  x: 1\n}\n", mutate.QML)
    assert out.splitlines()[-2] == "}"


# ------------------------------------------------- the stale QML cache bug

QML_STORE_GLOB = "/nix/store/*-qtdeclarative-*/bin/qmltestrunner"


def _qmltestrunner() -> str:
    import glob

    found = sorted(glob.glob(QML_STORE_GLOB))
    if not found:
        pytest.skip("no qmltestrunner in the store; this reproduction needs the real Qt")
    return found[-1]


def test_a_stale_qmlc_is_read_without_the_harness_env_and_cannot_be_with_it(tmp_path):
    """B49 assumed the stale-cache half "cannot bite" QML. It does.

    `qmltestrunner` writes compiled QML to
    `$XDG_CACHE_HOME/qmltestrunner/qmlcache/*.qmlc`, validated against
    (mtime, size) exactly like a `.pyc`. The edit below is EQUAL LENGTH
    (`"old"` -> `"new"`) with the mtime put back, and the second run — the
    control, the loop's hand practice — passes a test that asserts the OLD
    value against source that no longer says it. A mutation graded that way
    reads as "survived" and never ran.

    It is arguably worse than the Python case: that cache lives in the
    user's home, where nothing in this repo would ever think to clear it.
    """
    import os

    runner = _qmltestrunner()
    qtdecl = Path(runner).parents[1]
    t = tmp_path / "t"
    t.mkdir()
    thing = t / "Thing.qml"
    thing.write_text('import QtQuick\nQtObject { readonly property string value: "old" }\n')
    (t / "qmldir").write_text("Thing 1.0 Thing.qml\n")
    (t / "tst_thing.qml").write_text(
        "import QtQuick\nimport QtTest\n"
        'TestCase {\n  name: "Thing"\n  Thing { id: thing }\n'
        '  function test_value() { compare(thing.value, "old") }\n}\n'
    )

    def run(env_extra: dict[str, str]) -> bool:
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
            "QT_QPA_PLATFORM": "offscreen",
            "XDG_CACHE_HOME": str(tmp_path / "shared"),
            **env_extra,
        }
        return subprocess.run(
            [runner, "-input", str(t), "-import", str(qtdecl / "lib/qt-6/qml")],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
        ).returncode == 0

    assert run({}), "the baseline is red; the control is void"
    cached = list((tmp_path / "shared" / "qmltestrunner" / "qmlcache").glob("*.qmlc"))
    assert cached, "no .qmlc was written; the control is void"

    was = thing.stat().st_mtime
    thing.write_text('import QtQuick\nQtObject { readonly property string value: "new" }\n')
    os.utime(thing, (was, was))

    # The control: the loop's pre-B49 practice, grading QML that never ran.
    assert run({}), "expected a STALE green — the .qmlc should have been reused"
    # What the harness does instead, and either half of it is enough.
    assert not run(mutate.qml_env(tmp_path / "fresh")), "the mutant should have been caught"
    assert not run({"QML_DISABLE_DISK_CACHE": "1"})


def test_qml_env_moves_the_qml_cache_somewhere_empty_and_disables_it(tmp_path):
    env = mutate.qml_env(tmp_path / "c")
    assert env["XDG_CACHE_HOME"] == str(tmp_path / "c")
    assert env["QML_DISABLE_DISK_CACHE"] == "1"


def test_cargo_env_is_empty_on_purpose(tmp_path):
    # A private CARGO_TARGET_DIR would recompile the crate once per suite run.
    # Rust's staleness control is the always-newer mtime, not a fresh cache.
    assert mutate.cargo_env(tmp_path / "c") == {}


# --------------------------------------------------- always-newer mtimes


def test_every_write_gets_a_strictly_newer_whole_second(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.write_text("x")
    b.write_text("y")
    stamps = mutate.Stamps(1_000_000.4, now=lambda: 900_000.0)
    first = stamps.stamp(a)
    second = stamps.stamp(b)
    third = stamps.stamp(a)
    assert first == 1_000_001.0
    assert (second, third) == (1_000_002.0, 1_000_003.0)
    assert a.stat().st_mtime == third and b.stat().st_mtime == second


def test_a_stamp_keeps_ahead_of_a_clock_that_moved_on_during_a_slow_suite(tmp_path):
    """The bug this class shipped with, caught by the first real cargo run.

    A counter that only ever adds a second per write falls behind a suite
    that takes forty seconds to compile: the restore claimed start+5 s while
    the artifacts cargo had just produced said start+35 s, cargo read the
    restored file as OLDER than its own output, skipped the rebuild, and a
    test failed on a byte-for-byte clean tree. Every stamp re-reads the
    clock, so a write is always in the future no matter how slow the suite.
    """
    f = tmp_path / "f"
    f.write_text("x")
    clock = {"t": 1_000.0}
    stamps = mutate.Stamps(1_000.0, now=lambda: clock["t"])
    assert stamps.stamp(f) == 1_001.0
    clock["t"] = 1_040.0  # the suite spent forty seconds compiling
    assert stamps.stamp(f) == 1_041.0, "the stamp fell behind the build it has to invalidate"
    assert stamps.stamp(f) == 1_042.0, "and it is still strictly increasing"


def test_the_run_never_writes_an_mtime_older_than_what_it_started_with(tree):
    """Backwards is the dangerous direction: cargo decides to rebuild from
    "is any source newer than my fingerprint", so a restore that put an OLD
    mtime back would leave the final clean baseline running the mutant."""
    root, src = tree
    import os

    os.utime(src, (2_000_000_000, 2_000_000_000))  # a source from the future
    seen: list[float] = []

    def watch(env: dict[str, str], scratch: Path) -> bool:
        seen.append(src.stat().st_mtime)
        text = src.read_text(encoding="utf-8")
        return mutate.CANARY_MARK not in text and "MUTANT" not in text

    mutate.run(mutate.parse_spec(SPEC), watch, root=root)
    assert seen == sorted(seen) and len(set(seen)) == len(seen)
    assert seen[0] == 2_000_000_000, "the baseline runs on an untouched file"
    assert all(m > 2_000_000_000 for m in seen[1:]), "a write landed in the past"


def test_the_restore_leaves_the_bytes_identical_and_the_mtime_newer(tree):
    root, src = tree
    before_bytes, before_mtime = src.read_bytes(), src.stat().st_mtime
    mutate.run(mutate.parse_spec(SPEC), FakeSuite(src), root=root)
    assert src.read_bytes() == before_bytes
    assert src.stat().st_mtime > before_mtime


# ----------------------------------------------- the right grader per file


def test_a_file_in_this_runners_language_is_offered_the_execution_control_first():
    """This used to be a REFUSAL — a `.qml` path under `--runner tests` was an
    error before any suite ran. B55 took that away, because the refusal was
    wrong about a real case (`tools`' pytest suite matches lines in
    `Bus.qml`). What the suffix decides now is which canaries can mean
    anything, which is still the whole of the old rule's reasoning."""
    (m,) = mutate.parse_spec("@ qml via pytest\nshell/jv-hud/core/X.qml\n- a: 1\n+ a: 2\n")
    assert mutate.controls_for(m, mutate.QML) == (mutate.EXECUTED, mutate.READ)
    assert mutate.controls_for(m, mutate.PYTHON) == (mutate.READ,)


def test_an_off_language_file_is_never_handed_the_wrong_languages_canary(tmp_path):
    """Not pedantry: a Python `raise` appended to QML parses as nothing, so
    the canary would LIVE and the abort would blame the tests."""
    (tmp_path / "shell").mkdir()
    (tmp_path / "shell" / "X.qml").write_text("import QtQuick\nQtObject { property int a: 1 }\n")
    spec = mutate.parse_spec("@ x\nshell/X.qml\n- a: 1\n+ a: 2\n")
    seen: list[str] = []

    def green(env, scratch):
        seen.append((tmp_path / "shell" / "X.qml").read_text(encoding="utf-8"))
        return True

    with pytest.raises(mutate.HarnessError, match="not a .py file"):
        mutate.run(spec, green, root=tmp_path, lang=mutate.PYTHON)
    assert not any(mutate.CANARY_MARK in t for t in seen)


# ------------------------------------------------------ the language table


def test_every_language_names_a_runner_script_the_loop_actually_has():
    for lang in mutate.LANGUAGES.values():
        assert (ROOT / "ops" / "ralph" / lang.script).is_file(), lang.runner


def test_the_two_hud_runners_take_no_target_and_the_other_two_do(tmp_path):
    assert mutate.QML.command(ROOT, "hud", tmp_path)[-1].endswith("qmltest.sh")
    assert mutate.PYTHON.command(ROOT, "jv-ears", tmp_path)[-1] == "jv-ears"
    assert mutate.CARGO.command(ROOT, "jarvisd", tmp_path)[-1] == "jarvisd"
    assert "hud" not in mutate.SHOTS.command(ROOT, "hud", tmp_path)


# ------------------------------------------------- the shots runner (B51)
#
# The fourth runner, and the only one that can grade a PLATE. B49 measured
# what `qmltest.sh` covers and the answer was `shell/jv-hud/core/` and
# nothing else: the tests import "../core", so a canary on StatePlate.qml
# LIVES and the harness refuses the file. `hudshots.sh` stages the whole
# shell — every plate, the generated Theme, the two Quickshell singletons
# substituted — and drives the real plates through tst_shots.qml and
# tst_sequence.qml, which is the only place in this repo a plate is
# instantiated at all.
#
# It needed one thing the other three did not: somewhere to put its output.
# It writes thirteen PNGs and DEFAULTS to docs/hud — the committed contact
# sheet — so an ungoverned grading run would rewrite the sheet a dozen
# times over, half of those from a mutant, and the loop would commit
# whichever one the last run happened to leave behind.


def test_the_shots_runner_writes_into_the_runs_own_scratch_and_never_the_sheet(tmp_path):
    cmd = mutate.SHOTS.command(ROOT, "hud", tmp_path)
    assert cmd[-1] == str(tmp_path / "shots")
    assert not any(str(ROOT / "docs") in part for part in cmd)


def test_only_the_shots_runner_asks_for_a_scratch_output_dir(tmp_path):
    assert [l.runner for l in mutate.LANGUAGES.values() if l.scratch_out] == ["shots"]
    for lang in (mutate.PYTHON, mutate.QML, mutate.CARGO):
        assert lang.command(ROOT, "x", tmp_path) == lang.command(ROOT, "x", tmp_path / "other")


def test_every_shots_run_is_handed_a_scratch_dir_no_run_has_used_before(tree):
    """The same guarantee the cache dirs get, for the same reason: a sheet
    written by the mutant run must not be what the next run finds."""
    root, src = tree
    suite = FakeSuite(src)
    mutate.run(mutate.parse_spec(SPEC), suite, root=root)
    assert len(suite.scratches) == len(set(suite.scratches)) >= 4
    assert all(suite.scratch_fresh)


def test_shots_env_disables_the_disk_cache_the_script_does_not(tmp_path):
    """Not a copy of qml_env: hudshots.sh exports its own XDG_CACHE_HOME
    inside its mktemp stage, so setting that here would be overwritten and
    would read as a control that is not one. QML_DISABLE_DISK_CACHE is not
    set anywhere in that script, so it survives and is real."""
    env = mutate.SHOTS.env(tmp_path)
    assert env == {"QML_DISABLE_DISK_CACHE": "1"}
    script = (ROOT / "ops" / "ralph" / "hudshots.sh").read_text()
    assert "XDG_CACHE_HOME" in script          # it gives itself a fresh one
    assert "QML_DISABLE_DISK_CACHE" not in script


def test_the_shots_runner_can_execute_qml_and_could_only_ever_read_python():
    (py,) = mutate.parse_spec("@ x\nsvc/thing.py\n- A = 1\n+ A = 2\n")
    assert mutate.controls_for(py, mutate.SHOTS) == (mutate.READ,)
    (qml,) = mutate.parse_spec("@ x\nshell/jv-hud/StatePlate.qml\n- a: 1\n+ a: 2\n")
    assert mutate.controls_for(qml, mutate.SHOTS) == (mutate.EXECUTED, mutate.READ)


def test_a_canary_that_lived_under_the_core_runner_names_the_one_that_would_run_it(tmp_path):
    """The abort a plate mutation hits, and it used to end at "check the
    runner, the target...". The answer is now a fact about this repo and
    worth printing: qmltest.sh cannot run a plate, hudshots.sh can."""
    (tmp_path / "shell").mkdir()
    (tmp_path / "shell" / "P.qml").write_text("import QtQuick\nQtObject { property int a: 1 }\n")
    spec = mutate.parse_spec("@ x\nshell/P.qml\n- a: 1\n+ a: 2\n")
    with pytest.raises(mutate.HarnessError, match="--runner shots"):
        mutate.run(spec, lambda env, scratch: True, root=tmp_path, lang=mutate.QML)


def test_the_shots_abort_names_the_two_things_its_stage_drops(tmp_path):
    """Proved by running it: `--runner shots` on shell/jv-hud/shell.qml
    aborts with exit 2 after two suite runs, because hudshots.sh copies the
    shell and then removes shell.qml and tests/. That is the right answer —
    no runner in this harness can grade shell.qml, and the abort should say
    so rather than leave the reader checking a target that is correct."""
    assert "shell.qml" in mutate.SHOTS.canary_hint
    assert "tests/" in mutate.SHOTS.canary_hint
    script = (ROOT / "ops" / "ralph" / "hudshots.sh").read_text()
    assert 'rm -f "$stage/shell.qml"' in script
    assert 'rm -rf "$stage/tests"' in script


# ------------------------------------------ what a RED baseline means (B53)


def _repo(tmp_path, plate="import QtQuick\nQtObject { property int a: 1 }\n"):
    """A throwaway git repo with one committed plate and one committed sheet.

    The hint below is a MEASUREMENT of the working tree against HEAD, so it
    cannot be tested against a bare directory: `git status` has to have
    something to answer."""
    git = ["git", "-C", str(tmp_path), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run(git + ["init", "-q", "-b", "main"], check=True)
    (tmp_path / "shell" / "jv-hud").mkdir(parents=True)
    (tmp_path / "shell" / "jv-hud" / "P.qml").write_text(plate, encoding="utf-8")
    (tmp_path / "docs" / "hud").mkdir(parents=True)
    (tmp_path / "docs" / "hud" / "state-idle.png").write_bytes(b"\x89PNG committed")
    subprocess.run(git + ["add", "-A"], check=True)
    subprocess.run(git + ["commit", "-qm", "sheet"], check=True)
    return tmp_path / "shell" / "jv-hud" / "P.qml"


SHOTS_SPEC = "@ x\nshell/jv-hud/P.qml\n- a: 1\n+ a: 2\n"


def test_a_red_baseline_under_the_shots_runner_says_the_sheet_is_stale(tmp_path):
    """B53, measured rather than reasoned: with an uncommitted edit to a plate,
    `--runner shots` renders a sheet that differs from `HEAD:docs/hud`,
    tools/hudsheet.py exits 1, the BASELINE run is red and the harness aborts.
    The refusal is right and the sentence was wrong — the suite is fine, the
    SHEET is stale — and the comparator's four lines saying so are the tail of
    a log `script_runner` prints one line of."""
    plate = _repo(tmp_path)
    plate.write_text("import QtQuick\nQtObject { property int a: 1 }\n// edited\n", encoding="utf-8")
    with pytest.raises(mutate.HarnessError) as exc:
        mutate.run(
            mutate.parse_spec(SHOTS_SPEC),
            lambda env, scratch: False,
            root=tmp_path,
            lang=mutate.SHOTS,
        )
    said = str(exc.value)
    assert "baseline" in said                       # still the same abort
    assert "shell/jv-hud/P.qml" in said             # and it names what moved
    assert "hudshots.sh" in said and "commit" in said
    assert "docs/hud" in said


def test_the_stale_sheet_hint_is_not_printed_when_the_plates_match_head(tmp_path):
    """The other half, and the reason the hint is a measurement: with the tree
    at HEAD a red baseline is NOT a stale sheet, and a harness that blamed one
    anyway would send the reader to run `hudshots.sh` over a suite that is
    genuinely broken."""
    _repo(tmp_path)
    with pytest.raises(mutate.HarnessError) as exc:
        mutate.run(
            mutate.parse_spec(SHOTS_SPEC),
            lambda env, scratch: False,
            root=tmp_path,
            lang=mutate.SHOTS,
        )
    said = str(exc.value)
    assert "hudshots.sh" not in said
    assert "matches HEAD" in said


def test_an_uncommitted_sheet_is_still_a_stale_sheet(tmp_path):
    """The gotcha worth one sentence: hudsheet.py compares against
    `HEAD:docs/hud`, so PNGs that were re-rendered and not COMMITTED leave the
    baseline exactly as red as before. The advice has to say commit."""
    plate = _repo(tmp_path)
    plate.write_text("import QtQuick\nQtObject { property int a: 2 }\n", encoding="utf-8")
    (tmp_path / "docs" / "hud" / "state-idle.png").write_bytes(b"\x89PNG refreshed")
    with pytest.raises(mutate.HarnessError) as exc:
        mutate.run(
            mutate.parse_spec(SHOTS_SPEC),
            lambda env, scratch: False,
            root=tmp_path,
            lang=mutate.SHOTS,
        )
    said = str(exc.value)
    assert "hudshots.sh" in said
    assert "not committed" in said


def test_the_red_baseline_abort_says_nothing_about_the_sheet_for_other_runners(tree):
    """Only one of the four runners reads a committed artifact back, so only
    one of them has this failure mode. The Python abort stays what it was."""
    root, _ = tree
    with pytest.raises(mutate.HarnessError) as exc:
        mutate.run(mutate.parse_spec(SPEC), lambda env, scratch: False, root=root)
    assert "hudshots" not in str(exc.value)
    assert mutate.PYTHON.baseline_hint is None


def test_a_hint_that_cannot_run_git_says_nothing_at_all(tmp_path):
    """The hint shells out to git, and the abort it decorates must survive a
    root that is not a repository — the harness has one job at that moment and
    it is to refuse, not to raise a second exception about the first.

    It must also not fill the silence: "I could not look" is not "nothing is
    modified", and printing the tree-matches-HEAD sentence here would be the
    harness asserting something it did not measure."""
    (tmp_path / "shell" / "jv-hud").mkdir(parents=True)
    (tmp_path / "shell" / "jv-hud" / "P.qml").write_text(
        "import QtQuick\nQtObject { property int a: 1 }\n", encoding="utf-8"
    )
    assert mutate._modified(tmp_path, "shell/jv-hud") is None      # could not look
    assert mutate.shots_baseline_hint(tmp_path) == ""
    with pytest.raises(mutate.HarnessError, match="baseline") as exc:
        mutate.run(
            mutate.parse_spec(SHOTS_SPEC),
            lambda env, scratch: False,
            root=tmp_path,
            lang=mutate.SHOTS,
        )
    said = str(exc.value)
    assert "B53" not in said and "matches HEAD" not in said
    # Split off the sentence every abort now ends with (B56, the kept run) so
    # this still holds the strong claim: the hint added NOTHING, not merely
    # nothing recognisable.
    bare, _, kept = said.partition(" That run was kept in ")
    assert bare.endswith("fix the suite first.") and kept


def test_nothing_modified_and_could_not_look_are_different_answers(tmp_path, tmp_path_factory):
    """The distinction the sentence above rests on, held on its own: a clean
    repository answers `[]` and a directory that is not one answers `None`."""
    _repo(tmp_path)
    assert mutate._modified(tmp_path, "shell/jv-hud") == []
    assert mutate._modified(tmp_path_factory.mktemp("plain"), "shell/jv-hud") is None


def test_a_target_the_shots_runner_does_not_grade_exits_two(spec_file, monkeypatch):
    monkeypatch.setattr(mutate, "run", lambda *a, **k: pytest.fail("ran on a bad target"))
    assert mutate.main(["--runner", "shots", "jv-ears", spec_file]) == 2


def test_the_run_count_is_printed_before_a_fifty_second_suite_starts(spec_file, monkeypatch, capsys):
    """The shots runner costs ~53 s a run on this machine, so a three-mutation
    grading is five minutes. Knowing the count before it starts is the
    difference between sending fewer mutations and abandoning a grading half
    way through."""
    two_files = "@ a\nsvc/thing.py\n- A = 1\n+ A = 2\n@ b\nsvc/other.py\n- B = 1\n+ B = 2\n"
    assert mutate.suite_runs(mutate.parse_spec(two_files)) == 6     # 1 + 2 files + 2 + 1
    two_in_one = "@ a\nsvc/thing.py\n- A = 1\n+ A = 2\n@ b\nsvc/thing.py\n- B = 1\n+ B = 2\n"
    assert mutate.suite_runs(mutate.parse_spec(two_in_one)) == 5    # one canary, not two
    monkeypatch.setattr(mutate, "run", lambda *a, **k: _report("caught"))
    mutate.main(["tools", spec_file])
    assert "4 suite runs" in capsys.readouterr().out


def test_a_canary_planted_by_the_qml_language_is_the_qml_one(tmp_path):
    (tmp_path / "shell").mkdir()
    src = tmp_path / "shell" / "X.qml"
    src.write_text("import QtQuick\nQtObject { property int a: 1 }\n")
    suite = FakeSuite(src)
    report = mutate.run(
        mutate.parse_spec("@ a mutated\nshell/X.qml\n- a: 1\n+ a: MUTANT\n"),
        suite,
        root=tmp_path,
        lang=mutate.QML,
    )
    assert report.caught == 1
    canaried = [t for t in suite.seen if mutate.CANARY_MARK in t]
    assert len(canaried) == 1 and canaried[0].splitlines()[-1].startswith("***")


# ------------------------------------------------------------ the --runner flag


def test_the_runner_flag_picks_the_language_the_run_is_given(spec_file, monkeypatch):
    seen: list[str] = []
    monkeypatch.setattr(
        mutate, "run", lambda *a, **k: seen.append(k["lang"].runner) or _report("caught")
    )
    assert mutate.main(["--runner", "cargo", "jarvisd", spec_file]) == 0
    assert mutate.main(["tools", spec_file]) == 0
    assert seen == ["cargo", "tests"]


def test_a_target_the_qml_runner_does_not_grade_exits_two(spec_file, monkeypatch):
    monkeypatch.setattr(mutate, "run", lambda *a, **k: pytest.fail("ran on a bad target"))
    assert mutate.main(["--runner", "qml", "jv-ears", spec_file]) == 2


# ============================================================ B56: the logs
#
# Every suite run's output was captured and dropped: `script_runner` printed
# the LAST LINE of stdout and kept nothing. For `--runner tests` that line is
# a pytest summary and is roughly the right line; for `--runner shots` it is
# whatever the comparator's closing paragraph happened to end with, and while
# closing B53 the printed line was the sentence for the case that was NOT what
# happened. B53 fixed the one abort where the loop was actively misled. What
# is left is the general shape: a survivor, a canary that lived, or a red
# baseline could not be investigated without re-running a 53 s suite by hand.
#
# Each run already gets a private scratch directory. These tests hold the
# three things that turn it into evidence: the whole output lands in it, the
# tree is KEPT when something needs looking at (and swept when nothing does),
# and every run says which of the four things it was.


def _script_repo(tmp_path, body: str) -> Path:
    (tmp_path / "ops" / "ralph").mkdir(parents=True)
    (tmp_path / "ops" / "ralph" / "runtests.sh").write_text(body, encoding="utf-8")
    return tmp_path


def test_a_runs_whole_output_is_kept_where_the_one_printed_line_came_from(tmp_path, capsys):
    """The printed line is a progress indicator. The LOG is the evidence, and
    B53's lesson is why they must not be the same thing: choosing one line out
    of a suite's output is a guess, and that guess was wrong the one time it
    mattered."""
    root = _script_repo(
        tmp_path,
        "#!/usr/bin/env bash\nfor i in $(seq 1 30); do echo \"line $i\"; done\n"
        "echo 'and a word to stderr' >&2\nexit 1\n",
    )
    scratch = tmp_path / "run001"
    scratch.mkdir()
    assert mutate.script_runner(root, mutate.PYTHON, "svc")({}, scratch) is False

    log = (scratch / mutate.SUITE_LOG).read_text(encoding="utf-8")
    assert "line 1\n" in log and "line 30" in log      # all of it, not the tail
    assert "and a word to stderr" in log               # including the other stream
    assert "exit 1" in log                             # and how it ended

    printed = capsys.readouterr().out
    assert "line 30" in printed and "line 1\n" not in printed
    assert "run001" in printed, "the printed line must name the log it came from"


def test_a_survivor_keeps_the_logs_and_says_which_run_graded_it(tree):
    root, src = tree
    report = mutate.run(mutate.parse_spec(SPEC), FakeSuite(src, catches=False), root=root)
    assert report.logs is not None and report.logs.is_dir()
    (o,) = report.outcomes
    assert o.status == "survived"
    assert Path(o.logs).is_dir() and Path(o.logs).parent == report.logs
    assert o.logs in report.summary()


def test_a_clean_sweep_throws_the_logs_away(tree):
    """The kept tree is a cost — under `--runner shots` it is a dozen runs of
    thirteen PNGs — and a grading where every mutation was caught has nothing
    in it anyone will ever open."""
    root, src = tree
    suite = FakeSuite(src)
    report = mutate.run(mutate.parse_spec(SPEC), suite, root=root)
    assert report.survived == 0 and report.logs is None
    assert not suite.scratches[0].parent.exists()


def test_the_index_names_every_run_in_order_with_what_it_was(tree):
    root, src = tree
    report = mutate.run(mutate.parse_spec(SPEC), FakeSuite(src, catches=False), root=root)
    lines = (report.logs / mutate.INDEX).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4
    assert lines[0].startswith("run001  pass  baseline")
    assert "canary" in lines[1] and "svc/thing.py" in lines[1] and "  fail  " in lines[1]
    assert "mutation" in lines[2] and "value mutated" in lines[2] and "  pass  " in lines[2]
    assert lines[3].startswith("run004  pass  closing baseline")


def test_a_run_says_what_it_is_before_it_runs_and_not_after(tree):
    """A runner that dies takes its INDEX line with it, and the run nobody can
    name is exactly the one being investigated."""
    root, src = tree
    seen: list[Path] = []

    def explode(env, scratch):
        seen.append(scratch)
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        mutate.run(mutate.parse_spec(SPEC), explode, root=root)
    (scratch,) = seen
    assert (scratch / mutate.WHAT).read_text(encoding="utf-8").strip() == "baseline"
    assert scratch.parent.is_dir(), "a run that crashed is a run worth keeping"


def test_the_red_baseline_abort_names_the_run_whose_output_was_kept(tree):
    root, src = tree
    seen: list[Path] = []

    def red(env, scratch):
        seen.append(scratch)
        return False

    with pytest.raises(mutate.HarnessError) as exc:
        mutate.run(mutate.parse_spec(SPEC), red, root=root)
    (scratch,) = seen
    assert str(scratch) in str(exc.value)
    assert scratch.is_dir()


def test_a_canary_that_lived_names_its_own_run_and_not_the_baselines(tree):
    root, src = tree
    seen: list[Path] = []

    def green(env, scratch):
        seen.append(scratch)
        return True

    with pytest.raises(mutate.HarnessError) as exc:
        mutate.run(mutate.parse_spec(SPEC), green, root=root)
    msg = str(exc.value)
    assert "canaries lived" in msg
    # Both canary runs are named — two live canaries are two suite logs — and
    # the baseline, which was fine, is not.
    assert str(seen[1]) in msg and str(seen[2]) in msg and str(seen[0]) not in msg


def test_a_tree_still_red_after_the_last_restore_names_that_run_too(tree):
    root, src = tree
    seen: list[Path] = []
    results = iter([True, False, False, False])

    def suite(env, scratch):
        seen.append(scratch)
        return next(results)

    with pytest.raises(mutate.HarnessError) as exc:
        mutate.run(mutate.parse_spec(SPEC), suite, root=root)
    msg = str(exc.value)
    assert "RED after the last restore" in msg
    assert str(seen[3]) in msg


def test_the_cli_says_where_the_logs_were_kept(spec_file, monkeypatch, capsys, tmp_path):
    kept = tmp_path / "jv-mutate-kept"
    (kept / "run003").mkdir(parents=True)
    monkeypatch.setattr(
        mutate,
        "run",
        lambda *a, **k: mutate.Report(
            [mutate.Outcome("x", "svc/thing.py", "survived", str(kept / "run003"))],
            logs=kept,
        ),
    )
    assert mutate.main(["tools", spec_file]) == 1
    # `kept: ` and not merely the path: `summary()` prints the SURVIVOR's run
    # dir, which contains this path as a prefix, so the looser assertion was
    # satisfied by a different mechanism and graded the CLI's own line immune.
    # Found by mutating that line to `if False:` and watching it survive.
    assert f"kept: {kept}" in capsys.readouterr().out


def test_a_clean_sweep_says_nothing_about_logs_there_are_none(spec_file, monkeypatch, capsys):
    monkeypatch.setattr(mutate, "run", lambda *a, **k: _report("caught"))
    assert mutate.main(["tools", spec_file]) == 0
    assert "logs" not in capsys.readouterr().out


def test_an_abort_before_the_first_suite_run_leaves_no_tree_at_all(tree, tmp_path_factory):
    """The line the kept tree rests on: nothing is created until a suite has
    actually run, so a spec the harness rejects on sight costs nothing to
    clean up. `tempfile.tempdir` is where the fixture above pointed `mkdtemp`,
    which makes "no tree" something this can count rather than assume."""
    root, _ = tree
    parent = Path(tempfile.tempdir)
    before = list(parent.iterdir())
    with pytest.raises(mutate.HarnessError, match="no such file"):
        mutate.run(
            mutate.parse_spec("@ x\nsvc/absent.py\n- A = 1\n+ A = 2\n"),
            lambda env, scratch: pytest.fail("ran a suite for a file that is not there"),
            root=root,
        )
    assert list(parent.iterdir()) == before


# ------------------------------------ the file the suite READS, never runs (B55)
#
# Invariant 1 forbids one service importing another, so every claim this repo
# makes about a relation BETWEEN two services is made by reading the other's
# source and matching a line in it. There are four such relations today
# (BUDGET_MIRRORS x2 and RECONNECT_CADENCES x2 in test_gen_theme_qml.py, plus
# jv-compat's copy of jv-guard's scan budget, B50) and the harness declined to
# grade every one of them: the load canary makes the file impossible to
# IMPORT, a suite that only greps it never notices, the canary lives and the
# run aborts. The refusal was right and the gap was real. A canary for a
# source-read relation has to make the file unMATCHABLE instead.


class ReadingSuite:
    """A suite that never imports its target — it reads the source and matches
    a line, the way `test_gen_theme_qml.py` reads jv-ears' `config.py` and
    jv-compat's suite reads jv-guard's scanner budget. Red when the needle is
    gone; nothing appended to the file can make it red."""

    def __init__(self, path: Path, needle: str = "OTHER = 2") -> None:
        self.path = path
        self.needle = needle
        self.seen: list[str] = []

    def __call__(self, env: dict[str, str], scratch: Path) -> bool:
        text = self.path.read_text(encoding="utf-8")
        self.seen.append(text)
        return self.needle in text


READ_SPEC = "@ the mirrored constant moved\nsvc/thing.py\n- OTHER = 2\n+ OTHER = 3\n"


def test_the_erasure_canary_leaves_nothing_at_all_to_match():
    """unMATCHABLE, not unloadable. Anything kept in the file is something a
    regex somewhere might still find, so the only honest erasure is the empty
    one — and it is the same control in every language, which is the point:
    the suite that reads `shell/jv-hud/Bus.qml` is written in Python."""
    assert mutate.erased("VALUE = 1\nOTHER = 2\n") == ""


def test_a_file_the_suite_reads_instead_of_importing_is_graded_after_it_is_erased(tree):
    root, src = tree
    suite = ReadingSuite(src)
    report = mutate.run(mutate.parse_spec(READ_SPEC), suite, root=root)
    assert report.caught == 1 and report.survived == 0
    # Both controls were tried, in this order: the load canary lived (the file
    # is never imported), the erasure killed the suite.
    assert any(mutate.CANARY_MARK in t for t in suite.seen), "no load canary was tried"
    assert "" in suite.seen, "the file was never erased"
    assert suite.seen.index(next(t for t in suite.seen if mutate.CANARY_MARK in t)) < suite.seen.index("")
    assert src.read_bytes() == b"VALUE = 1\nOTHER = 2\n"


def test_the_report_says_the_suite_only_READ_the_file_so_a_score_is_not_overclaimed(tree):
    """"one mutation, one caught" means something weaker here than it does on
    an imported file, and the harness is the only thing that knows which. It
    says so in the summary whether or not anything survived."""
    root, src = tree
    report = mutate.run(mutate.parse_spec(READ_SPEC), ReadingSuite(src), root=root)
    assert report.relations == {"svc/thing.py": mutate.READ}
    summary = report.summary()
    assert "svc/thing.py" in summary
    assert "reads" in summary


def test_a_file_the_suite_imports_costs_one_canary_and_keeps_the_stronger_claim(tree):
    root, src = tree
    suite = FakeSuite(src)
    report = mutate.run(mutate.parse_spec(SPEC), suite, root=root)
    assert report.relations == {"svc/thing.py": mutate.EXECUTED}
    assert "" not in suite.seen, "an imported file was erased for nothing"
    assert "reads" not in report.summary()


def test_a_survivor_on_a_read_relation_is_not_reported_as_a_file_that_never_ran(tree):
    """The sentence a survivor means here is "no test MATCHES this text", and
    it is not the sentence the harness's other survivors mean."""
    root, src = tree
    # Reads the file, matches a line the mutation does not touch.
    report = mutate.run(mutate.parse_spec(READ_SPEC), ReadingSuite(src, needle="VALUE = 1"), root=root)
    assert report.survived == 1
    assert "no test matches" in report.summary()


def test_a_file_the_suite_neither_runs_nor_reads_aborts_naming_both_controls(tree):
    root, src = tree
    runs: list[str] = []

    def blind(env: dict[str, str], scratch: Path) -> bool:
        runs.append(src.read_text(encoding="utf-8"))
        return True

    with pytest.raises(mutate.HarnessError, match="neither executes .* nor reads"):
        mutate.run(mutate.parse_spec(SPEC), blind, root=root)
    assert any(mutate.CANARY_MARK in t for t in runs) and "" in runs
    assert not any("MUTANT" in t for t in runs), "a mutation ran after two live canaries"
    assert src.read_bytes() == b"VALUE = 1\nOTHER = 2\n"


def test_an_off_language_file_is_only_ever_erased_never_given_the_wrong_canary(tmp_path):
    """A Python `raise` appended to QML parses as nothing, so the load canary
    would be noise there — it would live for a reason that says nothing about
    the suite. But the relation is real: `tools`' suite matches a line in
    `shell/jv-hud/Bus.qml` (RECONNECT_CADENCES). So an off-language file is
    not refused any more; it is offered the ONE control it could ever fail."""
    (tmp_path / "shell").mkdir()
    qml = tmp_path / "shell" / "Bus.qml"
    qml.write_text("import QtQuick\nQtObject { interval: 2000 }\n", encoding="utf-8")
    suite = ReadingSuite(qml, needle="interval: 2000")
    spec = mutate.parse_spec("@ the respawn cadence moved\nshell/Bus.qml\n- interval: 2000\n+ interval: 9000\n")
    report = mutate.run(spec, suite, root=tmp_path, lang=mutate.PYTHON)
    assert report.caught == 1
    assert report.relations == {"shell/Bus.qml": mutate.READ}
    assert not any(mutate.CANARY_MARK in t for t in suite.seen), "a Python canary was appended to QML"
    assert suite.seen.count("") == 1
    assert qml.read_text(encoding="utf-8") == "import QtQuick\nQtObject { interval: 2000 }\n"


def test_an_off_language_file_the_suite_does_not_read_either_says_which_it_is(tmp_path):
    (tmp_path / "shell").mkdir()
    (tmp_path / "shell" / "Bus.qml").write_text("import QtQuick\nQtObject { interval: 2000 }\n")
    spec = mutate.parse_spec("@ x\nshell/Bus.qml\n- interval: 2000\n+ interval: 9000\n")
    calls: list[str] = []
    with pytest.raises(mutate.HarnessError, match="not a .py file"):
        mutate.run(spec, lambda env, scratch: calls.append("ran") or True, root=tmp_path, lang=mutate.PYTHON)
    # The baseline and ONE canary. There is no load canary to try on a file
    # this runner could never execute, so the abort costs one run, not two.
    assert calls == ["ran", "ran"]


def test_the_controls_a_file_is_offered_follow_from_its_suffix():
    (py,) = mutate.parse_spec("@ x\nsvc/thing.py\n- A = 1\n+ A = 2\n")
    (qml,) = mutate.parse_spec("@ x\nshell/jv-hud/core/X.qml\n- a: 1\n+ a: 2\n")
    assert mutate.controls_for(py, mutate.PYTHON) == (mutate.EXECUTED, mutate.READ)
    assert mutate.controls_for(qml, mutate.PYTHON) == (mutate.READ,)
    assert mutate.controls_for(qml, mutate.SHOTS) == (mutate.EXECUTED, mutate.READ)
    assert mutate.controls_for(py, mutate.SHOTS) == (mutate.READ,)
