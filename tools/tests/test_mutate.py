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
"""

from __future__ import annotations

import subprocess
import sys
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
        self.scratch_fresh.append(scratch.is_dir() and not list(scratch.iterdir()))
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


def test_a_file_this_runner_could_not_be_grading_is_refused():
    (m,) = mutate.parse_spec("@ qml via pytest\nshell/jv-hud/core/X.qml\n- a: 1\n+ a: 2\n")
    with pytest.raises(mutate.HarnessError, match="wrong grader"):
        mutate.check_language(m, mutate.PYTHON)
    mutate.check_language(m, mutate.QML)  # and the right one is fine


def test_the_wrong_grader_is_refused_before_any_suite_runs(tmp_path):
    """Not pedantry: a Python `raise` appended to QML parses as nothing, so
    the canary would LIVE and the abort would blame the tests."""
    (tmp_path / "shell").mkdir()
    (tmp_path / "shell" / "X.qml").write_text("import QtQuick\nQtObject { property int a: 1 }\n")
    spec = mutate.parse_spec("@ x\nshell/X.qml\n- a: 1\n+ a: 2\n")
    calls: list[str] = []
    with pytest.raises(mutate.HarnessError, match="wrong grader"):
        mutate.run(spec, lambda env, scratch: calls.append("ran") or True, root=tmp_path, lang=mutate.PYTHON)
    assert calls == []


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


def test_the_shots_runner_grades_qml_and_nothing_else():
    (py,) = mutate.parse_spec("@ x\nsvc/thing.py\n- A = 1\n+ A = 2\n")
    with pytest.raises(mutate.HarnessError, match="wrong grader"):
        mutate.check_language(py, mutate.SHOTS)
    (qml,) = mutate.parse_spec("@ x\nshell/jv-hud/StatePlate.qml\n- a: 1\n+ a: 2\n")
    mutate.check_language(qml, mutate.SHOTS)


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
