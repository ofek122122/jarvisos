"""tools/dependents.py — which suites read the thing you just changed (PLAN B68).

Three iterations in a row got this wrong, and the third one is why this file
exists. B65 (e36eee5) changed `services/jv-compat/jv_compat/prefix.py` and ran
`runtests.sh jv-compat`, which was green. B66 (a0d02ef) did the same. Both were
red in `tools`, because `tools/tests/test_hudshots.py` lifts jv-compat's own
refusal expressions out of its source and evaluates them over a photographed
verdict — and a fourth refusal naming `problems` had nothing to bind. A71
(d049a9c) found and fixed that, then committed its 31 files without the ONE
line that made `tools` green again, and reported the green it had in its
working tree.

The interesting part is not any of those bugs. It is that every author was
right about which suite was "relevant" to what they touched, and every author
was wrong — because invariant 1 forbids one service importing another, so
every relation this repo asserts BETWEEN two parts of itself is asserted by a
THIRD suite that READS them both as source. `tools` reads jv-compat, jv-guard,
jv-brain, jv-act, the schemas, the personality and the whole HUD. Nothing told
anybody that, so the verify gate's "the relevant test suite(s)" was a guess
made fresh each iteration by someone who could not see the readers.

So the map is derived, never written down: a suite reads what it NAMES, if
what it names exists. That rule is deliberately generous in one direction —
naming `services` (which `test_hudshots.py` does, to enumerate the services)
claims everything under it — because the cost of one extra 5-second suite is
nothing and the cost of a missed reader is a red commit that nobody sees for
two days.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import dependents  # noqa: E402

RUNTESTS = ROOT / "ops" / "ralph" / "runtests.sh"


# ------------------------------------------------------------- a repo, by hand


def mkrepo(tmp_path: Path) -> Path:
    """A repo with the shape this tool reads: two services with a package and
    a suite each, a `tools` suite that is nobody's service, and a directory of
    files that is not code at all."""
    root = tmp_path / "repo"
    for rel in (
        "services/svc-a/pkg_a/__init__.py",
        "services/svc-a/pkg_a/thing.py",
        "services/svc-a/tests/test_a.py",
        "services/svc-b/pkg_b/__init__.py",
        "services/svc-b/pkg_b/other.py",
        "services/svc-b/tests/test_b.py",
        "tools/atool.py",
        "tools/tests/test_atool.py",
        "docs/pics/01.png",
        "README.md",
    ):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("", "utf-8")
    return root


def write(root: Path, rel: str, src: str) -> None:
    (root / rel).write_text(src, "utf-8")


def reads_of(root: Path, name: str) -> frozenset[str]:
    found = {s.name: s for s in dependents.suites(root)}
    assert name in found, f"{name} is not a suite in this repo: {sorted(found)}"
    return found[name].reads


def reads_apart_from_this_file(name: str) -> frozenset[str]:
    """What a suite of the REAL repo reads, with this file's own contribution
    left out.

    Without this, every regression below would prove itself: the rule is that
    a suite reads what it names, and the test asserting that `tools` reads
    `docs/hud/14-cut-off.png` names `docs/hud/14-cut-off.png`. The claim worth
    making is about the suite that was ALREADY there — `test_hudshots.py`,
    `test_hudsheet.py` — so this file is excluded and no single sibling is
    pinned in its place.
    """
    suite = {s.name: s for s in dependents.suites(ROOT)}[name]
    me = Path(__file__).resolve()
    out: set[str] = set()
    for py in sorted(suite.tests.rglob("*.py")):
        if py.resolve() == me or "__pycache__" in py.parts:
            continue
        out |= dependents.names(ROOT, py)
    return frozenset(out)


# --------------------------------------------------------------- what counts


def test_a_path_named_as_a_slash_chain_is_read(tmp_path):
    """The form every suite in this repo actually uses: a module-level constant
    built out of `ROOT`, then joined again at each use. Only the constant is
    resolvable, and it does not have to be the file that changed — it has to
    be a directory ABOVE it."""
    root = mkrepo(tmp_path)
    write(
        root,
        "tools/tests/test_atool.py",
        'from pathlib import Path\n'
        'ROOT = Path(__file__).resolve().parents[2]\n'
        'A = ROOT / "services" / "svc-a"\n'
        'def test_x():\n'
        '    assert (A / "pkg_a" / "thing.py").read_text()\n',
    )
    got = dependents.readers(root, ["services/svc-a/pkg_a/thing.py"])
    assert got == {"tools": ["services/svc-a/pkg_a/thing.py"]}, got


def test_only_the_longest_chain_counts_not_every_prefix_of_it(tmp_path):
    """`ROOT / "services" / "svc-a"` contains the sub-expression `ROOT /
    "services"`, and recording both would claim that this suite reads every
    service in the repo — which would make the answer "run everything" and
    the tool worthless. A suite that really does name `services` (to walk it)
    still claims all of it; that is a different thing and it is tested below."""
    root = mkrepo(tmp_path)
    write(
        root,
        "tools/tests/test_atool.py",
        'from pathlib import Path\n'
        'ROOT = Path(__file__).resolve().parents[2]\n'
        'A = ROOT / "services" / "svc-a"\n',
    )
    assert reads_of(root, "tools") == frozenset({"services/svc-a"})


def test_a_directory_named_whole_claims_everything_under_it(tmp_path):
    """`(ROOT / "services").iterdir()` is `test_hudshots.py`'s own line, and
    what it asserts really does depend on what is in there. The generous
    reading is deliberate: the tool would rather name a suite that did not
    need running than miss the one that did."""
    root = mkrepo(tmp_path)
    write(
        root,
        "tools/tests/test_atool.py",
        'from pathlib import Path\n'
        'ROOT = Path(__file__).resolve().parents[2]\n'
        'def test_x():\n'
        '    assert [d.name for d in (ROOT / "services").iterdir()]\n',
    )
    got = dependents.readers(root, ["services/svc-b/pkg_b/other.py"])
    assert got == {"tools": ["services/svc-b/pkg_b/other.py"]}, got


def test_a_path_named_as_one_string_is_read(tmp_path):
    """`tools/tests/test_mutate.py` writes them out whole, both as arguments
    and inside the multi-line specs it feeds the harness — so a path-shaped
    token anywhere in a string literal counts, not only a literal that is
    exactly a path."""
    root = mkrepo(tmp_path)
    write(
        root,
        "tools/tests/test_atool.py",
        'SPEC = """\n'
        'services/svc-b/pkg_b/other.py\n'
        '  1  x -> y\n'
        '"""\n',
    )
    got = dependents.readers(root, ["services/svc-b/pkg_b/other.py"])
    assert got == {"tools": ["services/svc-b/pkg_b/other.py"]}, got


def test_a_bare_word_that_happens_to_be_a_directory_is_not_a_path(tmp_path):
    """Found by pointing the finished tool at this repo: jv-brain's suite has
    `assert ("tools" in warm)` — a key in a warm-up set — and reading that as
    a path made every edit under `tools/` name jv-brain's suite, which reads
    nothing of the kind.

    So a plain string must carry a slash to be a path. An expression built
    with `/` does not need one: `str(ROOT / "tools")` is a path because of how
    it was written, not because of what is in it."""
    root = mkrepo(tmp_path)
    write(root, "tools/tests/test_atool.py", 'def test_x():\n    assert "docs" in {"docs": 1}\n')
    assert reads_of(root, "tools") == frozenset()

    write(
        root,
        "tools/tests/test_atool.py",
        'from pathlib import Path\nROOT = Path(__file__).resolve().parents[2]\nD = ROOT / "docs"\n',
    )
    assert reads_of(root, "tools") == frozenset({"docs"})


def test_a_name_this_repo_does_not_have_is_not_a_dependency(tmp_path):
    """The whole rule is "names it AND it exists". Without the second half,
    prose about a service that was renamed or never existed would pin a suite
    to a file nobody has, and the tool would start inventing work."""
    root = mkrepo(tmp_path)
    write(
        root,
        "tools/tests/test_atool.py",
        'PATH = "services/svc-z/pkg_z/gone.py"\n',
    )
    assert reads_of(root, "tools") == frozenset()
    assert dependents.readers(root, ["services/svc-z/pkg_z/gone.py"]) == {}


def test_an_import_counts_even_when_the_directory_is_never_named(tmp_path):
    """A suite may reach another part of the repo without writing a path at
    all: `from jv_compat import fingerprint` (tools) and `import jarvis_bus`
    (every service) both read source that the suite never spells out. The
    package name is resolved to the directory it actually lives in."""
    root = mkrepo(tmp_path)
    write(root, "tools/tests/test_atool.py", "import pkg_b\nimport json\n")
    assert reads_of(root, "tools") == frozenset({"services/svc-b/pkg_b"})
    got = dependents.readers(root, ["services/svc-b/pkg_b/other.py"])
    assert got == {"tools": ["services/svc-b/pkg_b/other.py"]}, got


def test_an_import_carries_what_the_imported_file_imports(tmp_path):
    """The hole the real repo found while this was being written: `jv-ears`'
    suite names `jarvis_bus` NOWHERE — not a path, not an import — and a
    change to the bus codec still runs inside it, because the suite imports
    `jv_ears` and `jv_ears/main.py` imports the client. A map that stopped at
    the first edge would have called that suite safe.

    Only imports are followed. A suite that reads another service's source as
    TEXT (which is how this repo asserts every cross-service relation) does
    not thereby depend on what that service imports — it depends on the
    characters in the file, and those are already covered by naming it."""
    root = mkrepo(tmp_path)
    write(root, "services/svc-a/pkg_a/thing.py", "import pkg_b\n")
    write(root, "services/svc-a/tests/test_a.py", "import pkg_a\n")
    got = dependents.readers(root, ["services/svc-b/pkg_b/other.py"])
    assert got == {"svc-a": ["services/svc-b/pkg_b/other.py"]}, got


def test_an_import_cycle_does_not_hang(tmp_path):
    """Python allows it, this repo has none today, and a closure that trusts
    that is a tool that stops running the day somebody writes one."""
    root = mkrepo(tmp_path)
    write(root, "services/svc-a/pkg_a/thing.py", "import pkg_b\n")
    write(root, "services/svc-b/pkg_b/other.py", "import pkg_a\n")
    write(root, "tools/tests/test_atool.py", "import pkg_a\n")
    assert reads_of(root, "tools") == frozenset(
        {"services/svc-a/pkg_a", "services/svc-b/pkg_b"}
    )


def test_a_module_that_is_a_single_file_resolves_to_that_file(tmp_path):
    """`import hudsheet` is `tools/hudsheet.py`, not a package — and it should
    claim that file and not the whole of `tools/`."""
    root = mkrepo(tmp_path)
    write(root, "tools/tests/test_atool.py", "import atool\n")
    assert reads_of(root, "tools") == frozenset({"tools/atool.py"})


def test_a_comment_names_nothing(tmp_path):
    """This repo's suites carry more prose than code, and a great deal of it
    names other services while asserting nothing about them (`# jv-compat's
    installer publishes ...`). Comments are not in the tree this reads, which
    is the one place the generous rule is narrowed — and it is narrowed by
    construction rather than by a list of words."""
    root = mkrepo(tmp_path)
    write(
        root,
        "tools/tests/test_atool.py",
        "# services/svc-a/pkg_a/thing.py is the interesting one\n"
        "def test_x():\n    assert True\n",
    )
    assert reads_of(root, "tools") == frozenset()


def test_the_repo_root_is_never_a_dependency(tmp_path):
    """`Path(".")`, `""`, `".."` and `"../.."` all resolve to something that
    exists, and every one of them would claim the entire repository — after
    which the tool says "run every suite" forever and stops being read. Same
    shape as the grant bug B66 refused, one directory up."""
    root = mkrepo(tmp_path)
    write(
        root,
        "tools/tests/test_atool.py",
        'from pathlib import Path\n'
        'A = Path(".")\nB = ""\nC = ".."\nD = "../.."\nE = "./"\n',
    )
    assert reads_of(root, "tools") == frozenset()


def test_an_absolute_path_is_not_this_repo(tmp_path):
    """`/run/jarvis/bus.sock`, `/etc` and `/nix/store/...` are named all over
    these suites, and none of them is a file this repo can change. Treating a
    leading slash as repo-relative is how `/etc` becomes `<root>/etc`.

    The absolute path here has to be one that WOULD resolve if the slash were
    ignored, or the test passes for the wrong reason — which is how the first
    draft of it let that mutation live: `/run/jarvis/bus.sock` names nothing
    under a repo either way, so it proved nothing about the rule."""
    root = mkrepo(tmp_path)
    write(
        root,
        "tools/tests/test_atool.py",
        'REAL = "/docs/pics/01.png"\nS = "/run/jarvis/bus.sock"\nE = "/etc"\n',
    )
    assert reads_of(root, "tools") == frozenset()


def test_a_suite_reads_its_own_service_and_is_still_offered_the_exclusion(tmp_path):
    """Its own service is a true reading and the map says so. It is the CALLER
    — `runtests.sh`, which has just run that very suite — that does not want
    to be told to run it again."""
    root = mkrepo(tmp_path)
    write(
        root,
        "services/svc-a/tests/test_a.py",
        'from pathlib import Path\n'
        'ROOT = Path(__file__).resolve().parents[3]\n'
        'A = ROOT / "services" / "svc-a"\n',
    )
    write(
        root,
        "tools/tests/test_atool.py",
        'from pathlib import Path\n'
        'ROOT = Path(__file__).resolve().parents[2]\n'
        'A = ROOT / "services" / "svc-a"\n',
    )
    p = ["services/svc-a/pkg_a/thing.py"]
    assert sorted(dependents.readers(root, p)) == ["svc-a", "tools"]
    assert sorted(dependents.readers(root, p, exclude=["svc-a"])) == ["tools"]


def test_a_deleted_file_still_finds_its_readers(tmp_path):
    """A change is not always an edit. The path that changed does not have to
    exist any more — only the directory the suite named above it does."""
    root = mkrepo(tmp_path)
    write(
        root,
        "tools/tests/test_atool.py",
        'from pathlib import Path\n'
        'ROOT = Path(__file__).resolve().parents[2]\n'
        'A = ROOT / "services" / "svc-a"\n',
    )
    (root / "services/svc-a/pkg_a/thing.py").unlink()
    got = dependents.readers(root, ["services/svc-a/pkg_a/thing.py"])
    assert got == {"tools": ["services/svc-a/pkg_a/thing.py"]}, got


def test_a_changed_directory_is_every_file_in_it(tmp_path):
    """`git status` reports an untracked directory as one entry, `docs/pics/`,
    and the suites name files inside it. Expanding is the difference between
    "a new shot was added" being seen and being missed — which is exactly
    what A71 did to the contact sheet."""
    root = mkrepo(tmp_path)
    write(
        root,
        "tools/tests/test_atool.py",
        'from pathlib import Path\n'
        'ROOT = Path(__file__).resolve().parents[2]\n'
        'def test_x():\n    assert (ROOT / "docs" / "pics" / "01.png").exists()\n',
    )
    got = dependents.readers(root, ["docs/pics/"])
    assert got == {"tools": ["docs/pics/01.png"]}, got


def test_a_file_that_does_not_parse_is_reported_and_not_skipped_quietly(tmp_path):
    """A suite this cannot read is a suite whose dependencies are unknown, and
    an unknown that prints nothing is how the original bug worked. It does not
    raise — one unparseable helper must not take the notice down — but it says
    so, and it says which file."""
    root = mkrepo(tmp_path)
    write(root, "tools/tests/test_atool.py", "def test_x(:\n")
    said: list[str] = []
    dependents.suites(root, warn=said.append)
    assert len(said) == 1, said
    assert "tools/tests/test_atool.py" in said[0]


# ------------------------------------------------------ the suites, discovered


def test_the_suites_are_exactly_the_ones_runtests_says_it_runs():
    """The map is derived so that it cannot go stale — but "which directories
    are suites" is still a rule, and `runtests.sh` states the same thing in
    prose for a human. A tenth service with a Python suite must not be
    discovered by one and missing from the other."""
    doc = RUNTESTS.read_text("utf-8")
    m = re.search(r"# Services: ((?:.|\n)*?)\n#\n", doc)
    assert m, "runtests.sh no longer lists the services it runs"
    listed = set(m.group(1).replace("#", " ").split())
    assert {s.name for s in dependents.suites(ROOT)} == listed


def test_a_rust_test_directory_is_not_a_python_suite():
    """`services/jarvisd/tests` and `services/jv-act/tests` are `.rs`, and
    `runtests.sh` exits 2 on either. They are discovered by the same glob as
    everything else and must be dropped by having no `test_*.py` in them."""
    names = {s.name for s in dependents.suites(ROOT)}
    assert (ROOT / "services" / "jarvisd" / "tests").is_dir()
    assert "jarvisd" not in names and "jv-act" not in names


# --------------------------------------------- the three iterations that lied


def test_a_change_to_jv_compats_source_names_tools():
    """B65 and B66, straight out of the journal: a `prefix.py` change whose
    only red suite was one that reads jv-compat from the outside."""
    assert dependents.is_read(
        reads_apart_from_this_file("tools"), "services/jv-compat/jv_compat/prefix.py"
    )


def test_a_new_shot_in_the_contact_sheet_names_tools():
    """A71: a fourteenth PNG under `docs/hud/`, and a `tools` test that had
    the number thirteen written down."""
    assert dependents.is_read(
        reads_apart_from_this_file("tools"), "docs/hud/14-cut-off.png"
    )


def test_a_change_to_the_hud_surface_names_tools():
    """Nothing in `shell/jv-hud` is Python and none of it is a service, yet
    `test_hudshots.py` reads `shell.qml` for the plate stack, the surface box
    and the safety properties. This is the reading an author is least likely
    to guess, because the suite is in a different language from the file."""
    assert dependents.is_read(
        reads_apart_from_this_file("tools"), "shell/jv-hud/shell.qml"
    )


def test_a_change_to_the_bus_library_names_every_service_that_speaks_on_it():
    """The other direction, and the expensive one: every service runs on the
    bus (invariant 1), so a change to the codec is one of the few honest "run
    everything" answers in this repo (B60's subject) — and one of those suites
    reaches it only through its own service's `main.py`."""
    got = dependents.readers(ROOT, ["services/pylib/jarvis_bus/client.py"])
    assert {
        "jv-brain",
        "jv-ears",
        "jv-voice",
        "jv-guard",
        "jv-compat",
        "jv-context",
        "jv-hud-bridge",
    } <= set(got), got


def test_a_change_to_a_frozen_schema_names_its_readers():
    """Schemas are law (invariant 2) and a schema change is the one thing a
    human must review — so if it ever happens, the suites that pin themselves
    to the file should be named rather than remembered."""
    assert dependents.is_read(
        reads_apart_from_this_file("tools"), "schemas/brain.response.json"
    )


# ----------------------------------------------------------------- the CLI


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "dependents.py"), *args],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )


def test_the_cli_prints_the_command_to_run_and_why():
    """What the author reads at the moment they would otherwise commit. A
    suite name is a fact; a command is something a tired loop will actually
    run, so it prints the command — and the path that pulled it in, because a
    notice nobody can check is a notice nobody trusts."""
    done = run_cli("--root", str(ROOT), "services/jv-compat/jv_compat/prefix.py")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "bash ops/ralph/runtests.sh tools" in done.stdout
    assert "bash ops/ralph/runtests.sh jv-compat" in done.stdout
    assert "services/jv-compat/jv_compat/prefix.py" in done.stdout


def test_the_cli_says_what_it_cannot_see():
    """The QML gates (`qmltest.sh`, `hudshots.sh`) name their subjects by QML
    type, not by path, so nothing here can find them — and a tool that lists
    "the suites that read this" while silently omitting two of the repo's
    gates is worse than no tool. It says so whenever it has anything to say."""
    done = run_cli("--root", str(ROOT), "shell/jv-hud/shell.qml")
    assert "qmltest.sh" in done.stdout and "hudshots.sh" in done.stdout


def test_the_cli_says_so_when_nothing_reads_what_changed(tmp_path):
    """The ordinary answer for a change inside one service, and it has to be
    unmistakable: an empty stdout reads exactly like a tool that failed.

    In a fresh repo rather than this one, because naming a path of the real
    repo here would make `tools` a reader of it and there would be nothing
    left to ask about."""
    root = mkrepo(tmp_path)
    done = run_cli("--root", str(root), "README.md")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "no Python suite" in done.stdout


def test_the_cli_reads_the_working_tree_when_asked(tmp_path):
    """`--changed` is the form the gate uses, because the question is never
    "what about this path" — it is "what about what I have done", and the
    author who has to list their own changes is the author who forgets one."""
    root = mkrepo(tmp_path)
    write(
        root,
        "tools/tests/test_atool.py",
        'from pathlib import Path\n'
        'ROOT = Path(__file__).resolve().parents[2]\n'
        'A = ROOT / "services" / "svc-a"\n',
    )
    git = ["git", "-C", str(root)]
    subprocess.run(git + ["init", "-q"], check=True)
    subprocess.run(git + ["add", "-A"], check=True)
    subprocess.run(
        git + ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x"],
        check=True,
    )
    (root / "services/svc-a/pkg_a/thing.py").write_text("# changed\n", "utf-8")
    (root / "services/svc-a/pkg_a/new.py").write_text("# new\n", "utf-8")

    done = run_cli("--root", str(root), "--changed")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "runtests.sh tools" in done.stdout
    assert "services/svc-a/pkg_a/thing.py" in done.stdout
    assert "services/svc-a/pkg_a/new.py" in done.stdout


def test_the_cli_excludes_the_suite_that_has_just_run(tmp_path):
    """`runtests.sh jv-compat` has this second: it just ran jv-compat and the
    only useful half of the answer is the suites it did NOT run."""
    root = mkrepo(tmp_path)
    write(
        root,
        "services/svc-a/tests/test_a.py",
        'from pathlib import Path\n'
        'ROOT = Path(__file__).resolve().parents[3]\n'
        'A = ROOT / "services" / "svc-a"\n',
    )
    done = run_cli(
        "--root", str(root), "--exclude", "svc-a", "services/svc-a/pkg_a/thing.py"
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "no Python suite" in done.stdout


def test_the_cli_says_nothing_at_all_when_nothing_changed(tmp_path):
    """`runtests.sh` prints whatever this says, so on a clean tree it must
    print NOTHING — a gate that decorates every run with a paragraph about
    having no news is a gate people learn to scroll past."""
    root = mkrepo(tmp_path)
    git = ["git", "-C", str(root)]
    subprocess.run(git + ["init", "-q"], check=True)
    subprocess.run(git + ["add", "-A"], check=True)
    subprocess.run(
        git + ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x"],
        check=True,
    )
    done = run_cli("--root", str(root), "--changed", "--quiet-when-empty")
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout == "", done.stdout


# ------------------------------------------------------------- and the gate


def test_runtests_asks_this_question_itself():
    """The rule that failed was a human one — "run the relevant suites" — and
    (c) in B68 was to write it down again, which is what had already not
    worked. So the script that runs a suite is the thing that names the rest:
    whoever runs the gate gets the answer whether or not they thought to ask
    for it."""
    doc = RUNTESTS.read_text("utf-8")
    assert "dependents.py" in doc
    assert "--exclude" in doc and "--changed" in doc
    assert "--quiet-when-empty" in doc, (
        "runtests.sh would print a paragraph about nothing on a clean tree"
    )


def test_the_gate_still_reports_pytests_verdict_and_asks_anyway(tmp_path):
    """The tail of `runtests.sh`, run for real with a stub interpreter.

    Two things could go wrong with bolting a second command onto the end of a
    gate, and both are silent. Under `set -e` a plain `rc=$?` after a failing
    pytest never executes — the script is already gone, with pytest's status,
    and the notice is missing from exactly the run that most needed it. And an
    advisory command that is allowed to fail loudly, or whose status becomes
    the script's, would turn a green suite red or a red one green. So: the
    suite fails, the notice is still printed, and the exit status is still the
    suite's."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "python"
    stub.write_text(
        "#!/bin/sh\ncase \"$*\" in\n"
        "  *pytest*) exit $STUB_PYTEST ;;\n"
        "  *dependents.py*) echo ASKED ;;\n"
        "esac\n",
        "utf-8",
    )
    stub.chmod(0o755)

    doc = RUNTESTS.read_text("utf-8")
    tail = doc[doc.index("rc=0\n") :]
    assert "exit $rc" in tail
    script = (
        f'set -euo pipefail\nvenv="{tmp_path}"\nroot="{ROOT}"\nsvc=tools\n' + tail
    )

    for verdict in (0, 1):
        done = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            env={**os.environ, "STUB_PYTEST": str(verdict)},
        )
        assert done.returncode == verdict, (verdict, done.stdout, done.stderr)
        assert "ASKED" in done.stdout, (verdict, done.stdout, done.stderr)
