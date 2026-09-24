"""tools/mutate.py — the loop's own mutation harness (PLAN B48).

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
    assert run(mutate.run_env(fresh)) == "new"


def test_run_env_names_a_fresh_cache_dir_and_forbids_writing_beside_the_source(tmp_path):
    env = mutate.run_env(tmp_path / "c")
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
        self.seen: list[str] = []

    def __call__(self, env: dict[str, str]) -> bool:
        self.envs.append(dict(env))
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
        mutate.run(mutate.parse_spec(SPEC), lambda env: False, root=root)
    assert src.read_bytes() == before


def test_a_canary_the_suite_survives_aborts_the_whole_run(tree):
    """The control. A suite that stays green with the target file unimportable
    does not execute that file, so no mutation of it can mean anything."""
    root, src = tree
    runs: list[str] = []

    def blind(env: dict[str, str]) -> bool:
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

    def boom(env: dict[str, str]) -> bool:
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

    def flaky(env: dict[str, str]) -> bool:
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
        mutate.run(spec, lambda env: calls.append("ran") or True, root=root)
    assert calls == []


def test_an_empty_spec_is_an_error_rather_than_a_perfect_score(tree):
    root, _ = tree
    with pytest.raises(mutate.HarnessError, match="no mutations"):
        mutate.run([], lambda env: True, root=root)


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
