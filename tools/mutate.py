#!/usr/bin/env python3
"""The Ralph loop's mutation harness — PLAN B48, extended to three languages
by B49 and to the HUD's plates by B51.

Every iteration of this loop writes a sentence like "six mutations, six
caught". The sentence is the loop's only evidence that the tests it just
wrote have teeth, and until B48 it was produced by hand: edit the source,
re-run pytest, read the colour, put the file back. Iteration 70 found the
hole in that practice. CPython validates a cached `.pyc` against the source's
(mtime **in whole seconds**, size), so an equal-length edit written inside
the same second as the write before it reuses stale bytecode: pytest reports
a PASS for a mutant that never executed, the loop writes "survived", and the
only tell arrives later — a full-suite failure on a file that has already
been RESTORED and is still running the mutant out of the cache.

So this harness is not an automation of the old practice. It is the old
practice plus the three controls it never had:

**The canary.** Before a single mutation is graded, the target file is made
impossible to LOAD and the suite MUST go red. If it stays green, the tests do
not execute that file at all — every mutation would be a silent survivor —
and the harness refuses to report anything rather than print a perfect score.
This is the direct test of the assumption the old practice made implicitly,
and it is stronger than reasoning about caches: it asks the suite itself
whether this file is the file it runs. Each language gets its own (see
`LANGUAGES`), and each makes a slightly different claim — the Rust one is
the weakest and says so.

**A cache that cannot be stale.** Every suite run gets its own private,
empty cache directory, so no run can read artifacts compiled by another.
Note for whoever reads B48: `python -B` alone does nothing about this. It
stops bytecode being WRITTEN, not read — the half that worked in iteration
70 was clearing `__pycache__`. `-B` is still set here, so a harness run
leaves no new caches beside the source, but the prefix is the guarantee.

B49 assumed this half "cannot bite" QML and Rust. That was wrong about QML,
and `test_a_stale_qmlc_is_read_...` reproduces it: `qmltestrunner` writes
compiled QML to `$XDG_CACHE_HOME/qmltestrunner/qmlcache/*.qmlc`, validated
against (mtime, size) exactly like a `.pyc`, and an equal-length edit with a
restored mtime is graded GREEN without ever running. It is arguably worse
than the Python case, because that cache lives in the user's home where
nothing in this repo would ever think to clear it.

**A mtime that is always new.** Cargo cannot be given a private cache
cheaply — a fresh `CARGO_TARGET_DIR` per run means recompiling the world a
dozen times — so it gets the other guarantee instead: every file this
harness writes (mutant, canary, and the restore) is stamped with a whole
second strictly newer than the last AND newer than the clock at the moment
of the write. Nothing keyed on mtime can mistake one of this harness's
writes for another, in any language. The tree is left byte-identical; only
the mtimes move forward, which is exactly what makes the next build honest.

Rust made the same lie the other two made, and it took both controls above
to see it: the first cargo grading ended with the tree byte-for-byte clean
and `proto::tests::matching` FAILING, because the restore had been stamped
from a counter that started when the run did and the run had since spent
forty seconds compiling. See `Stamps`.

Usage (spec on stdin is the ergonomic path — no scratch file to clean up):

    bash ops/ralph/mutate.sh jv-voice <<'EOF'
    # one block per mutation
    @ the inter-sentence gap widened
    services/jv-voice/jv_voice/service.py
    - TURN_GAP_S = 0.5
    + TURN_GAP_S = 0.9
    EOF

    bash ops/ralph/mutate.sh --runner qml hud <<'EOF'
    @ the ember lit while merely listening
    shell/jv-hud/core/SpeechState.qml
    - readonly property bool active: mode === "speaking"
    + readonly property bool active: mode !== "idle"
    EOF

    bash ops/ralph/mutate.sh --runner cargo jarvisd <<'EOF'
    @ the seq check dropped
    services/jarvisd/src/broker.rs
    - if frame.seq <= last { return Err(...) }
    + if false { return Err(...) }
    EOF

    bash ops/ralph/mutate.sh --runner shots hud <<'EOF'
    @ the state plate lit while idle
    shell/jv-hud/StatePlate.qml
    - readonly property bool shown: root.voice.known && !root.voice.idle
    + readonly property bool shown: root.voice.known
    EOF

B51 added that fourth runner, and it is the only one that can grade a PLATE.
`qmltest.sh` imports `"../core"` and never a top-level plate, so a canary on
one LIVES and the harness refuses the file — which is what B49 discovered and
what left ten plates ungradeable. `hudshots.sh` stages the whole shell,
substitutes the two Quickshell-bound singletons and drives the real plates
through `tst_shots.qml` and `tst_sequence.qml`. Two things had to be true
before it could be a runner: it must not write its thirteen PNGs over the
COMMITTED contact sheet (it takes an output directory, and `scratch_out`
hands it one inside this run's own scratch), and its cost had to be measured
rather than promised — it is ~53 s a run on this machine, against ~14 s for
`qmltest.sh`, so `main` prints the run count before a grading starts.

B52 is what makes that runner able to grade what a plate LOOKS like. Its own
first run found that `hudshots.sh` wrote thirteen PNGs and read none of them
back, so a mutation that changed a plate's COLOUR survived every suite in the
repo; the script now compares what it rendered against the sheet committed at
HEAD (tools/hudsheet.py). A mutation that moves a pixel is caught by the
picture — which is the only assertion here that is about the HUD's look.

B53 is the bill for that comparison, and it arrived the first time the loop
mutated a plate it had just edited: an uncommitted change to `StatePlate.qml`
makes the rendered sheet differ from `HEAD:docs/hud`, so the BASELINE run is
red and the harness aborts with "fix the suite first" about a suite that is
perfectly fine. The comparator says exactly what happened, in four lines at
the tail of a log `script_runner` prints one line of. So the red-baseline abort
now carries a per-runner hint, and for the only runner that reads a committed
artifact back it is a measurement of the tree rather than a slogan — it names
the plates that differ from HEAD, or says the tree matches HEAD and the red is
real, or (when git cannot answer) says nothing at all.

B56 is what makes any of the above investigable. Every suite run's output was
captured and thrown away: one line was printed — "the last line of stdout" —
and the rest went with the scratch tree, so a survivor, a canary that lived or
a red baseline could only be looked into by re-running a 53 s suite by hand.
Each run now writes its whole output to `suite.log` in the private scratch it
already had, says what it was in `WHAT` BEFORE it starts (so a runner that
dies still leaves its run named), and appends a line to `INDEX` at the top of
the tree. The tree is KEPT when there is a survivor or an abort and swept when
every mutation was caught, and each abort names the one run that went wrong.
The printed line stays one line and now says which run it came from: it is a
progress indicator, and B53 is the record of what happens when one chosen line
is mistaken for the evidence.

B55 is the relation this harness could not grade at all. Invariant 1 forbids
one service importing another, so every claim this repo makes about a relation
BETWEEN two of them is made by READING the other's source and matching a line
in it — jv-compat's copy of jv-guard's scan budget, the HUD's fallback budgets
against the jv-ears that enforces them, LinkPlate's grace against the two
reconnect cadences. Five such relations, and the harness declined to grade
every one: the canary above makes the file impossible to LOAD, a suite that
only greps it never notices, the canary lives and the run aborts. The refusal
was right and the gap was real. So a file is now offered its controls in
order, strongest first — unloadable, then ERASED — and whichever kills the
suite is the relation, which the report then carries: "1 of 1 caught" against
a file the suite greps is a claim about a regex, and a survivor there means
"no test matches this text" rather than "the tests never load this file". A
file that survives every control it was offered still aborts the run, and now
names both suite logs. The suffix that used to REFUSE a file (`--runner tests`
on a `.qml`) chooses the controls instead: the tools suite really does match a
line in `shell/jv-hud/Bus.qml`, so the relation the old rule called impossible
is the one this exists to grade.

B58 is the harness grading its own reach, and it starts from a hole in the
canary above. `runtests.sh` ran pytest from the service's own directory, so
`jv_guard` came from the worktree and `jarvis_bus` came from the NIX STORE:
every suite but pylib's own had been asserting against the shared library AS
LAST BUILT. A canary planted on such a file LIVES — the suite imports the
other copy and never notices — and the abort that followed said "the suite
neither executes that file nor reads its source", which was the wrong sentence
about the right observation. The two cases are indistinguishable from inside a
suite run, so the harness now asks OUTSIDE it: when every control has lived on
a Python file, it asks the suite's own interpreter, through the same script,
which file it imports that module from, and the abort carries the answer.
Three outcomes and three sentences — another copy (SHADOWED, and the mutations
would have meant nothing), this copy (the original abort, now measured), or no
answer at all, which says nothing.

`@ label` opens a block, the next bare line is the repo-relative file, and
the `-`/`+` lines are the hunk (joined in order, indentation kept verbatim).
`old` must appear EXACTLY once in the file: a hunk that matches twice is an
error, not a coin flip about which copy got mutated. A block with no `+`
lines is a deletion.

The file is restored after every run, and the suite is run once more at the
end with the tree clean — because "the tree is green again" is the claim
iteration 70 got wrong, and it is worth one more suite run to make it.
"""

from __future__ import annotations

import argparse
import dataclasses
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

CANARY_MARK = "jv-mutate canary: this file must be executed by the suite"

# How a suite can depend on a file, and therefore which canary proves it does
# (B55). These are not two grades of the same claim — they are two different
# claims, and the harness says which one it made.
#
#   EXECUTED  the suite loads and runs this file. Proved by making it
#             impossible to LOAD and watching the suite go red. A survivor
#             then means "no test asserts this line".
#   READ      the suite never loads it; it matches text in the source, which
#             is the ONLY way one service may make a claim about another
#             (invariant 1 forbids the import). Proved by making the file
#             unMATCHABLE — erasing it — and watching the suite go red. A
#             survivor then means "no test matches this text", which is a
#             different and weaker sentence, so the report carries it.
EXECUTED = "executed"
READ = "read"

# What a suite run leaves behind in its own scratch directory (B56). `WHAT` is
# written BEFORE the suite starts and `INDEX` (at the top of the run tree) is
# appended to after it finishes, so a runner that dies still leaves the run it
# died in named — and the run nobody can name is exactly the one being
# investigated. `SUITE_LOG` is `script_runner`'s, because only a runner knows
# whether it has output to keep.
SUITE_LOG = "suite.log"
WHAT = "WHAT"
INDEX = "INDEX"


class SpecError(Exception):
    """The spec could not be read as mutations."""


class HarnessError(Exception):
    """The harness cannot make an honest claim and is not going to make one."""


@dataclasses.dataclass(frozen=True)
class Mutation:
    label: str
    path: str
    old: str
    new: str


@dataclasses.dataclass(frozen=True)
class Outcome:
    label: str
    path: str
    status: str  # "caught" | "survived"
    logs: str = ""  # the scratch dir of the suite run that graded it (B56)


@dataclasses.dataclass(frozen=True)
class Report:
    outcomes: Sequence[Outcome]
    # The run tree, when it was KEPT — which is only when a survivor makes it
    # worth opening. `None` means the grading was clean and the tree is gone.
    logs: Path | None = None
    # Per FILE: how the suite turned out to depend on it, EXECUTED or READ
    # (B55). Measured, not declared — it is whichever canary killed the suite.
    # Empty only on a Report nobody graded (the CLI's own test doubles).
    relations: Mapping[str, str] = dataclasses.field(default_factory=dict)

    @property
    def caught(self) -> int:
        return sum(1 for o in self.outcomes if o.status == "caught")

    @property
    def survived(self) -> int:
        return sum(1 for o in self.outcomes if o.status == "survived")

    def summary(self) -> str:
        lines = [f"{self.caught}/{len(self.outcomes)} caught"]
        for o in self.outcomes:
            if o.status == "survived":
                lines.append(f"  survived: {o.label}  ({o.path})")
                if self.relations.get(o.path) == READ:
                    lines.append(
                        "            no test matches that text — this is not "
                        "a file the suite runs"
                    )
                if o.logs:
                    lines.append(f"            {o.logs}")
        # Said whether or not anything survived, because it qualifies the
        # COUNT and not just the misses: "11 of 11 caught" against a file the
        # suite only greps is a claim about regexes, and only the harness
        # knows which kind of claim it just made (B55).
        for rel in sorted(p for p, kind in self.relations.items() if kind == READ):
            lines.append(f"  the suite reads {rel} — it never runs it")
        return "\n".join(lines)


# ---------------------------------------------------------------- languages


def _appended(text: str, line: str) -> str:
    """`text` with `line` added at column zero, after a newline the file may
    not have had. Column zero matters: the canary has to run/parse from
    outside any trailing indented block."""
    tail = "" if text.endswith("\n") or not text else "\n"
    return f"{text}{tail}{line}\n"


def python_canary(text: str) -> str:
    """A module that cannot be imported. Whatever else the suite does, the
    import of this module raises, so every test that touches it fails."""
    return _appended(text, f'raise ImportError("{CANARY_MARK}")')


def qml_canary(text: str) -> str:
    """A QML file that cannot be parsed. `*** ... ***` is a syntax error
    wherever it lands, so the component becomes `Type X unavailable` and
    every test that instantiates it fails to compile.

    It means two different things to the two QML runners, and the weaker
    one is measured rather than assumed. Under `--runner qml` it is the
    strong claim: `qmltest.sh` only ever fails on a file it INSTANTIATES,
    so a canary that dies there means the suite really ran this component.
    Under `--runner shots` it is the Rust claim: `hudshots.sh` runs
    `qmllint` over the whole staged shell before either driver starts, and
    a syntax error is a lint failure, so the run goes red whether or not a
    driver ever builds the type. Verified by planting one on
    `StatePlate.qml`: exit 255 out of qmllint, no driver reached.

    That is still worth having — the stage DROPS `shell.qml` and `tests/`,
    so a canary in either lives and the harness refuses to grade them,
    which is exactly the file an A-track iteration is most likely to mutate
    by mistake. What it does not prove is that a driver instantiates the
    plate, and nothing here should be read as proving it. The gate that
    does prove it is `test_every_plate_in_the_shell_is_lit_in_some_shot`
    in tools/tests/test_hudshots.py, next to the one that pins Corner.qml's
    membership and order to shell.qml's.
    """
    return _appended(text, f"*** {CANARY_MARK} ***")


def rust_canary(text: str) -> str:
    """A crate that cannot be compiled.

    Honest limit, and it is why this is the weakest of the three: this proves
    the file is part of the compiled crate, not that any test exercises it.
    A `mod` that nobody calls still fails to build. It catches the one thing
    worth catching anyway — a file not in the module tree at all, or a suite
    run against a different crate than the one being mutated — and no more.
    Read a Rust survivor as "no test asserts this line", never as "the tests
    never load this file".
    """
    return _appended(text, f'compile_error!("{CANARY_MARK}");')


def erased(text: str) -> str:
    """The same file, made impossible for ANY suite to match a line in.

    The load canaries above each speak one language, because making a file
    impossible to load means something different in each. Erasure does not:
    a suite that greps another file's source is insensitive to whether that
    source would parse, and the relations this control exists for cross the
    language line in the only direction they can — `tools`' pytest suite
    matches a line in `shell/jv-hud/Bus.qml`, because invariant 1 forbids the
    HUD importing the bridge's constants or the other way round.

    Empty, and not a marker: anything left in the file is something a regex
    somewhere might still find, and a canary that can be matched is not a
    canary. `text` is taken and ignored so this reads like the others at the
    call site.

    The honest limit, and it is the mirror of the Rust canary's: a suite whose
    claim about this file is NEGATIVE — "this source contains nothing that
    looks like X" — is green on an empty file too, so the harness will refuse
    to grade it. That is the refusing direction, which is the safe one: it
    declines to claim rather than claiming wrongly.
    """
    return ""


# "Where does the suite import this module from?", already bound to the repo
# and the target, because the only caller has both and neither is its business.
Origin = Callable[[str], "str | None"]


def module_of(root: Path, rel: str) -> str | None:
    """The dotted name the suite would import a repo-relative `.py` path
    under, or `None` for a file that is not a module at all.

    Walking up while there is an `__init__.py` is exactly how the import
    system decides where a package starts, so this is the name the suite uses
    — `services/pylib/jarvis_bus/client.py` is `jarvis_bus.client`, and
    `.../jarvis_bus/__init__.py` is `jarvis_bus` and never
    `jarvis_bus.__init__`, because the second is not a name any importer says.
    """
    path = Path(rel)
    if path.suffix != ".py":
        return None
    parts: list[str] = []
    here = (root / path).parent
    while here != root and (here / "__init__.py").is_file():
        parts.append(here.name)
        here = here.parent
    parts.reverse()
    if path.stem != "__init__":
        parts.append(path.stem)
    return ".".join(parts) or None


def python_origin(root: Path, target: str, module: str) -> str | None:
    """The file `target`'s suite would import `module` from — asked of the
    SUITE'S OWN interpreter, through the same script that runs it.

    This exists because of what `runtests.sh` was doing until d55348b: it ran
    pytest from the service's own directory, so `jv_guard` came from the
    worktree and `jarvis_bus` came from the NIX STORE, and every suite but
    pylib's own had been asserting against the shared library as last BUILT.
    A canary planted on such a file lives — the suite imports the other copy
    and never notices — and the abort that followed said "no test touches
    this file", which was the wrong sentence and had no way of knowing.

    So the question is put to the only thing that can answer it. Not this
    interpreter's `find_spec`: the venv, the cwd and the PYTHONPATH belong to
    the script, and an answer from anywhere else would be about a different
    program. `None` means the question could not be asked (no env for that
    service, no such module, a script that failed) and is deliberately not
    the same as an answer — see `_modified` for the same discipline.
    """
    try:
        proc = subprocess.run(
            ["bash", str(root / "ops" / "ralph" / "runtests.sh"), "--origin", module, target],
            cwd=root,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    found = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    return found[-1] if found else None


def shadow_note(path: Path, rel: str, module: str | None, origin: Origin | None) -> str:
    """What the probe adds to a canary that lived, and nothing when it has
    nothing to add.

    Three answers, and they are three different sentences. Another copy: the
    canary lived for a reason that says nothing about the tests, and the file
    that has to change is the one the suite imports. This copy: the abort's
    own sentence was right all along and is now measured rather than assumed.
    No answer: silence, because a hint that guessed would be worse than none.
    """
    if module is None or origin is None:
        return ""
    try:
        found = origin(module)
    except OSError:
        return ""
    if not found:
        return ""
    here, there = os.path.realpath(path), os.path.realpath(found)
    if here == there:
        return (
            f"The suite's own interpreter imports {module} from this very "
            f"file, so it is grading the right copy and the sentence above is "
            f"the whole story."
        )
    return (
        f"SHADOWED (B58): the suite imports {module} from {there}, which is "
        f"NOT the file that was mutated ({rel}). A canary on a copy nothing "
        f"imports lives for a reason that says nothing about the tests, and "
        f"every mutation graded against that copy would have meant nothing "
        f"either. Fix what the suite imports before reading anything into "
        f"this run."
    )


def python_env(cache_dir: Path) -> dict[str, str]:
    """A private, empty bytecode cache (so nothing compiled by another run
    can be read) and no writing beside the source (so a harness run leaves
    the tree as it found it)."""
    return {
        "PYTHONPYCACHEPREFIX": str(cache_dir),
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def qml_env(cache_dir: Path) -> dict[str, str]:
    """The same two guarantees for Qt. `XDG_CACHE_HOME` moves
    `qmltestrunner/qmlcache/*.qmlc` somewhere empty; `QML_DISABLE_DISK_CACHE`
    means the guarantee does not depend on Qt honouring `XDG_CACHE_HOME`."""
    return {
        "XDG_CACHE_HOME": str(cache_dir),
        "QML_DISABLE_DISK_CACHE": "1",
    }


def cargo_env(cache_dir: Path) -> dict[str, str]:
    """Deliberately nothing. A private `CARGO_TARGET_DIR` would recompile the
    crate and its dependencies once per suite run — minutes each — so Rust's
    only staleness control is the always-newer mtime every write gets."""
    return {}


def shots_env(cache_dir: Path) -> dict[str, str]:
    """`hudshots.sh` already gives itself a fresh `XDG_CACHE_HOME` inside its
    own `mktemp` stage and exports it over whatever it was handed, so the
    empty-cache half is free here and setting it would be theatre. What is
    NOT free is the second half: nothing in that script disables the disk
    cache, so this is a real control and not a copy of `qml_env`'s — it
    survives the script's own export."""
    return {"QML_DISABLE_DISK_CACHE": "1"}


# --------------------------------------------------- what a RED baseline means


def _modified(root: Path, path: str) -> list[str] | None:
    """The paths under `path` that differ from HEAD, tracked or not — `None`
    when git could not answer at all, which includes a `root` that is not a
    repository (every unit test in this file works in one that is not).

    `None` and `[]` are deliberately different. "Nothing is modified" is a
    finding; "I could not look" is not, and the caller must not print the first
    sentence when it only has the second. A hint must also never be the reason
    a refusal turns into a traceback."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "--", path],
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    out = []
    for line in proc.stdout.splitlines():
        name = line[3:].strip()
        if name:
            out.append(name.split(" -> ")[-1].strip('"'))
    return sorted(out)


def shots_baseline_hint(root: Path) -> str:
    """Why `--runner shots` alone can go red with a healthy suite (B53).

    It is the only runner that reads a COMMITTED artifact back: `hudshots.sh`
    renders the plates and then compares every PNG against `HEAD:docs/hud`
    (tools/hudsheet.py), so an uncommitted change to a plate that draws
    anything new makes the baseline run red, the harness abort, and the abort
    say "fix the suite first" about a suite that is fine. Measured while
    closing B52, on an uncommitted edit to `StatePlate.qml`.

    Which is why this is a measurement and not a fixed sentence. With the tree
    at HEAD there is nothing for the read-back to disagree with, the red is
    real, and a harness that sent the reader off to re-render a contact sheet
    would be pointing at the wrong thing. And when git cannot answer, this says
    NOTHING — the abort it decorates is a refusal to make a claim, and a hint
    that guessed at the reason would be the one thing this harness never does.
    """
    moved = _modified(root, "shell/jv-hud")
    if moved is None:
        return ""
    if not moved:
        return (
            "Not the stale-sheet case (B53): shell/jv-hud matches HEAD, so the "
            "sheet read-back has nothing to disagree with and the suite itself "
            "is red."
        )
    named = ", ".join(moved[:3]) + (f", +{len(moved) - 3} more" if len(moved) > 3 else "")
    stale = (
        f"The SHEET may be stale rather than the suite (B53): "
        f"{len(moved)} file(s) under shell/jv-hud differ from HEAD ({named}), and "
        f"hudshots.sh compares every PNG it renders against HEAD:docs/hud, so a "
        f"plate that now draws something new makes the BASELINE red. Run "
        f"`bash ops/ralph/hudshots.sh`, LOOK at the new PNGs, commit them, then grade."
    )
    if _modified(root, "docs/hud"):
        stale += (
            " docs/hud is itself modified and not committed, which does not help "
            "yet: the comparison is against HEAD."
        )
    return stale


@dataclasses.dataclass(frozen=True)
class Language:
    """A suite this harness knows how to run, and what a canary means in it."""

    runner: str                       # the --runner value
    script: str                       # ops/ralph/<script>
    suffixes: tuple[str, ...]         # which files it may grade
    canary: Callable[[str], str]
    env: Callable[[Path], Mapping[str, str]]
    targets: tuple[str, ...] | None    # None = the script validates the name
    pass_target: bool                  # does the script take the target as argv?
    # A suite that WRITES something the repo keeps needs telling where to put
    # it instead. hudshots.sh defaults to docs/hud/ — the committed contact
    # sheet — and a grading run rewrites it a dozen times, half of those from
    # a mutant. So it is handed a directory inside this run's own scratch,
    # which is thrown away with the rest of it.
    scratch_out: bool = False
    # Appended to the canary-lived abort: the runner that WOULD execute this
    # file, when there is one. A generic "check the runner" is no help to a
    # loop that has just been told its plate numbers mean nothing.
    canary_hint: str = ""
    # Appended to the RED-baseline abort, called with the repo root. Only one
    # runner reads a committed artifact back, so only one has a red baseline
    # that is not the suite's fault — and the useful version of that sentence
    # is a measurement of the tree, not a slogan (B53).
    baseline_hint: Callable[[Path], str] | None = None
    # (root, target, module) -> the file this runner's suite imports that
    # module from. Asked only when every canary has LIVED, to tell a file no
    # test touches from a file the tests import from ANOTHER COPY (B58).
    # `None` on three of the four runners on purpose: "where did this come
    # from" has an answer for an interpreter, and inventing one for a
    # qmltestrunner import path or a cargo module tree would be the overclaim
    # this harness exists to prevent.
    origin: Callable[[Path, str, str], str | None] | None = None

    def command(self, root: Path, target: str, scratch: Path) -> list[str]:
        cmd = ["bash", str(root / "ops" / "ralph" / self.script)]
        if self.pass_target:
            cmd.append(target)
        if self.scratch_out:
            cmd.append(str(scratch / "shots"))
        return cmd


PYTHON = Language(
    runner="tests",
    script="runtests.sh",
    suffixes=(".py",),
    canary=python_canary,
    env=python_env,
    targets=None,
    pass_target=True,
    origin=python_origin,
)

QML = Language(
    runner="qml",
    script="qmltest.sh",
    suffixes=(".qml",),
    canary=qml_canary,
    env=qml_env,
    # qmltest.sh grades the whole of shell/jv-hud/tests and takes no target,
    # so the name exists only to be typed and checked.
    targets=("hud",),
    pass_target=False,
    canary_hint=(
        "qmltest.sh imports \"../core\" and never a plate, so a canary on a "
        "top-level plate always lives (B49). Regrade it with --runner shots, "
        "which stages the whole shell and drives the real plates."
    ),
)

CARGO = Language(
    runner="cargo",
    script="cargotest.sh",
    suffixes=(".rs",),
    canary=rust_canary,
    env=cargo_env,
    targets=None,
    pass_target=True,
)

SHOTS = Language(
    runner="shots",
    script="hudshots.sh",
    suffixes=(".qml",),
    canary=qml_canary,
    env=shots_env,
    # hudshots.sh stages the whole shell and runs both drivers over it; the
    # only argument it takes is where to write the PNGs, which `scratch_out`
    # supplies. There is nothing else to name.
    targets=("hud",),
    pass_target=False,
    scratch_out=True,
    baseline_hint=shots_baseline_hint,
    canary_hint=(
        "hudshots.sh stages the shell but DROPS shell.qml and tests/, so a "
        "canary in either lives. shell.qml is the Quickshell half no other "
        "engine can load, and no runner here can grade it: what it claims is "
        "gated by tools/tests/test_hudshots.py, which READS it."
    ),
)

LANGUAGES: dict[str, Language] = {
    lang.runner: lang for lang in (PYTHON, QML, CARGO, SHOTS)
}


# --------------------------------------------------------------------- spec


def parse_spec(text: str) -> list[Mutation]:
    """Parse the block format above. Comments (`#`) and blank lines are
    ignored outside hunks; inside one they would start with `-` or `+`."""
    muts: list[Mutation] = []
    label: str | None = None
    path: str | None = None
    old: list[str] = []
    new: list[str] = []

    def close(at: str) -> None:
        nonlocal label, path, old, new
        if label is None:
            return
        if path is None:
            raise SpecError(f"block `{label}` names no file (line {at})")
        if not old:
            raise SpecError(f"block `{label}` has no `-` lines; there is nothing to find")
        muts.append(Mutation(label, path, "\n".join(old), "\n".join(new)))
        label, path, old, new = None, None, [], []

    for n, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip("\n")
        if line.startswith("@"):
            close(str(n))
            label = line[1:].strip()
            if not label:
                raise SpecError(f"line {n}: a block needs a label after `@`")
            continue
        if line[:1] in ("-", "+"):
            if label is None:
                raise SpecError(f"line {n}: a hunk line before any `@ label`")
            if path is None:
                raise SpecError(f"line {n}: block `{label}` names no file before its hunk")
            body = line[2:] if line[1:2] == " " else line[1:]
            (old if line[0] == "-" else new).append(body)
            continue
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if label is None:
            raise SpecError(f"line {n}: `{line.strip()}` before any `@ label`")
        if old or new:
            raise SpecError(f"line {n}: a file line after the hunk of `{label}`")
        if path is not None:
            raise SpecError(f"line {n}: block `{label}` names two files")
        path = line.strip()
    close("end")
    return muts


def resolve(mut: Mutation, *, root: Path) -> Path:
    """The absolute path of a mutation's target, refused if it leaves the
    repo. The spec is written by the loop, not by a stranger — but a harness
    that rewrites files in place gets the cheap check anyway."""
    root = root.resolve()
    target = (root / mut.path).resolve()
    if Path(mut.path).is_absolute() or not target.is_relative_to(root) or target == root:
        raise HarnessError(f"{mut.path} is outside the repository ({root})")
    return target


def controls_for(mut: Mutation, lang: Language) -> tuple[str, ...]:
    """Which relations this runner could possibly have with this file, in the
    order the harness will try to prove them — strongest first.

    The suffix used to be a refusal (`--runner tests` on a `.qml` file was an
    error). It is a CHOICE OF CONTROL now, because the refusal was wrong about
    a real case: `tools`' Python suite does match lines in `Bus.qml`, and the
    relation the old rule called impossible is the one B55 exists to grade.

    What the suffix still decides is which canaries can mean anything. A
    Python `raise` appended to QML parses as nothing, so on an off-language
    file the load canary would live for a reason that says nothing about the
    suite — noise, and a whole suite run spent on it. So an off-language file
    is offered the one control it could ever fail.
    """
    if Path(mut.path).suffix in lang.suffixes:
        return (EXECUTED, READ)
    return (READ,)


# ------------------------------------------------------------------- edits


def apply_once(text: str, old: str, new: str) -> str:
    """Replace `old` with `new`, insisting it appears exactly once."""
    if old == new:
        raise HarnessError("the mutation is identical to the original; it tests nothing")
    found = text.count(old)
    if found == 0:
        raise HarnessError(f"does not appear in the file: {old!r}")
    if found != 1:
        raise HarnessError(f"appears {found} times in the file, so the edit is ambiguous: {old!r}")
    return text.replace(old, new)


def with_canary(text: str, lang: Language = PYTHON) -> str:
    """The same file, made impossible for `lang`'s suite to load."""
    return lang.canary(text)


def canary_for(relation: str, text: str, lang: Language) -> str:
    """The file as the control for `relation` needs it: unloadable, or
    unmatchable."""
    return with_canary(text, lang) if relation == EXECUTED else erased(text)


class Stamps:
    """Whole-second mtimes, strictly increasing, and always in the future.

    Every build tool this harness drives decides "do I need to recompile
    this?" from the source's mtime, and at least two of them (CPython's
    `.pyc`, Qt's `.qmlc`) compare it in whole seconds. So the harness never
    lets two of its own writes share a second, and never writes a file that
    looks OLDER than the artifact built from its predecessor — including the
    restore, which is why the tree comes back byte-identical but not
    mtime-identical. Going BACKWARDS is the dangerous direction: cargo asks
    "is any source newer than what I built", so a source that looks old is a
    source it will not recompile.

    The `now` re-read on every stamp is not decoration — it is the fix for a
    bug this class shipped with and the first real Rust run caught. A counter
    that starts at "now" and adds a second per write falls behind a slow
    suite: the cargo grading below took ~40 s of wall clock, so the fifth
    stamp said start+5 s while the artifacts cargo had just written said
    start+35 s. The restored file looked THIRTY SECONDS OLD, cargo skipped
    the rebuild, and `proto::tests::matching` failed with the tree byte-for-
    byte clean — iteration 70's bug again, in a third language. B48's
    run-the-suite-once-more-at-the-end check is what caught it.
    """

    def __init__(self, floor: float, now: Callable[[], float] = time.time) -> None:
        self._now = now
        self._next = float(math.floor(floor) + 1)

    def stamp(self, path: Path) -> float:
        at = max(self._next, float(math.floor(self._now()) + 1))
        os.utime(path, (at, at))
        self._next = at + 1.0
        return at


# --------------------------------------------------------------------- run

Runner = Callable[[Mapping[str, str], Path], bool]


def canary_abort(
    rel: str, tried: Sequence[tuple[str, Path]], lang: Language, note: str = ""
) -> str:
    """What to say when a file survived every control it was offered.

    Two different sentences, because two different things went wrong. A file
    in this runner's own language was offered both controls and failed both,
    so the suite has no relation with it at all. An off-language file was only
    ever offered one, and naming the other would send the reader looking for
    an execution that was never on the table.

    `note` is the third thing it can be, and the only one this harness cannot
    work out from its own runs: the suite has a relation with a DIFFERENT COPY
    of the file (B58). It goes first among the appendices because it is the
    one that changes what the reader should do next.

    Every run that went wrong is named, not just the last one (B56's rule):
    two live canaries are two suite logs, and which of them the reader opens
    depends on which relation they thought they had.
    """
    if EXECUTED in [relation for relation, _ in tried]:
        why = (
            f"both canaries lived: the suite stayed GREEN with {rel} made "
            f"impossible to load AND with {rel} erased, so it neither executes "
            f"that file nor reads its source. Nothing this harness could report "
            f"about it would mean anything — check the runner, the target, and "
            f"that the tests read the worktree and not an installed copy."
        )
    else:
        why = (
            f"the erasure canary lived: {rel} is not a "
            f"{'/'.join(lang.suffixes)} file, so the only relation --runner "
            f"{lang.runner} could have with it is reading its source — and the "
            f"suite stayed GREEN with {rel} erased, so it does not read it "
            f"either."
        )
    kept = ", ".join(f"{cache} ({relation})" for relation, cache in tried)
    return (
        why
        + (f" {note}" if note else "")
        + (f" {lang.canary_hint}" if lang.canary_hint else "")
        + f" Those runs were kept in {kept}."
    )


def run(
    mutations: Iterable[Mutation],
    runner: Runner,
    *,
    root: Path,
    lang: Language = PYTHON,
    origin: Origin | None = None,
) -> Report:
    """Grade `mutations`. `runner(env, scratch)` runs the suite and returns
    True if it passed; `env` carries this run's private cache settings and
    `scratch` is a private empty directory the suite may write into (which is
    how `hudshots.sh` is kept off the committed contact sheet).

    `origin(module)` answers where the suite imports a module from, and is
    asked ONLY on the way out of a file that survived every canary — that is
    the one place where "no test touches this" and "the tests read another
    copy of this" are the same observation (B58).

    Order: baseline (must be green) -> one canary per file (each must be red)
    -> the mutations -> baseline again (must be green).

    The run tree is KEPT whenever this returns a survivor or raises, and swept
    when every mutation was caught (B56). A clean grading has nothing in it
    anyone will ever open, and under `--runner shots` it is a dozen runs of
    thirteen PNGs; a survivor or an abort is precisely the case where the
    alternative was re-running a 53 s suite by hand to see what happened.
    Every abort below names the one run that went wrong rather than the tree.
    """
    mutations = list(mutations)
    if not mutations:
        raise HarnessError("no mutations in the spec; a perfect score of zero is not a claim")

    targets: dict[str, Path] = {}
    controls: dict[str, tuple[str, ...]] = {}
    for m in mutations:
        controls[m.path] = controls_for(m, lang)
        targets[m.path] = resolve(m, root=root)
    for rel, path in targets.items():
        if not path.is_file():
            raise HarnessError(f"no such file to mutate: {rel}")
    originals = {rel: path.read_text(encoding="utf-8") for rel, path in targets.items()}

    base = Path(tempfile.mkdtemp(prefix="jv-mutate-"))
    state = {"n": 0}
    stamps = Stamps(max([time.time()] + [p.stat().st_mtime for p in targets.values()]))

    def write(path: Path, text: str) -> None:
        path.write_text(text, encoding="utf-8")
        stamps.stamp(path)

    def suite(what: str) -> tuple[bool, Path]:
        """Run the suite once and return (passed, that run's scratch dir)."""
        state["n"] += 1
        cache = base / f"run{state['n']:03d}"
        cache.mkdir()
        (cache / WHAT).write_text(f"{what}\n", encoding="utf-8")
        passed = bool(runner(lang.env(cache), cache))
        with (base / INDEX).open("a", encoding="utf-8") as fh:
            fh.write(f"{cache.name}  {'pass' if passed else 'fail'}  {what}\n")
        return passed, cache

    def swapped(rel: str, text: str, what: str) -> tuple[bool, Path]:
        """Run the suite with `rel` holding `text`, then put it back."""
        path = targets[rel]
        try:
            write(path, text)
            return suite(what)
        finally:
            write(path, originals[rel])

    keep = True
    try:
        ok, cache = suite("baseline")
        if not ok:
            hint = lang.baseline_hint(root) if lang.baseline_hint else ""
            raise HarnessError(
                "the baseline suite is RED before any mutation. Every mutation "
                "would be reported as caught for free; fix the suite first."
                + (f" {hint}" if hint else "")
                + f" That run was kept in {cache}."
            )

        relations: dict[str, str] = {}
        for rel in targets:
            # Strongest control first. Each one that LIVES rules out a
            # relation; the first that dies is the relation, and it is the
            # sentence the report will carry. A file that survives every
            # control it was offered is one this harness cannot say anything
            # about (B55).
            tried: list[tuple[str, Path]] = []
            for relation in controls[rel]:
                lived, cache = swapped(
                    rel,
                    canary_for(relation, originals[rel], lang),
                    f"canary {rel} ({relation})",
                )
                if not lived:
                    relations[rel] = relation
                    break
                tried.append((relation, cache))
            else:
                note = shadow_note(targets[rel], rel, module_of(root, rel), origin)
                raise HarnessError(canary_abort(rel, tried, lang, note))

        outcomes: list[Outcome] = []
        for mut in mutations:
            mutant = apply_once(originals[mut.path], mut.old, mut.new)
            passed, cache = swapped(mut.path, mutant, f"mutation: {mut.label}")
            outcomes.append(
                Outcome(mut.label, mut.path, "survived" if passed else "caught", str(cache))
            )

        for rel, path in targets.items():
            if path.read_text(encoding="utf-8") != originals[rel]:
                raise HarnessError(f"{rel} was not restored; put it back by hand before committing")
        ok, cache = suite("closing baseline")
        if not ok:
            raise HarnessError(
                "the suite is RED after the last restore, with every file back "
                "as it was. Something outside these mutations is broken — do "
                f"not commit until it is green. That run was kept in {cache}."
            )
        report = Report(
            outcomes,
            logs=base if any(o.status == "survived" for o in outcomes) else None,
            relations=relations,
        )
        keep = report.logs is not None
        return report
    finally:
        if not keep:
            shutil.rmtree(base, ignore_errors=True)


# --------------------------------------------------------------------- cli


def suite_runs(mutations: Sequence[Mutation]) -> int:
    """The FLOOR: the opening baseline, one canary per distinct FILE, one per
    mutation, and the closing baseline.

    A floor and not a count since B55, and only ever by one run per file: a
    file the suite READS rather than imports costs a second canary, because
    the first one — the unloadable file — is the control that has to be seen
    to live before erasure is the honest thing to try."""
    return 2 + len({m.path for m in mutations}) + len(mutations)


def script_runner(root: Path, lang: Language, target: str, *, quiet: bool = False) -> Runner:
    """The real runner: one of the loop's own `ops/ralph/*.sh` suites.

    The whole of each run's output goes to `scratch/suite.log`; ONE line of it
    is printed, and that line names the run it came from (B56). The two are
    deliberately not the same thing. Choosing one line out of a suite's output
    is a guess about which line matters, and B53 is the record of that guess
    being wrong at the worst moment: the line printed for a red `--runner
    shots` baseline was the tail of the comparator's closing paragraph, which
    is the sentence for the case that was NOT what happened. The printed line
    is a progress indicator. The log is the evidence.
    """

    def go(env: Mapping[str, str], scratch: Path) -> bool:
        cmd = lang.command(root, target, scratch)
        proc = subprocess.run(
            cmd,
            cwd=root,
            env={**os.environ, **env},
            capture_output=True,
            text=True,
        )
        (scratch / SUITE_LOG).write_text(
            f"$ {' '.join(cmd)}\n[exit {proc.returncode}]\n"
            f"\n--- stdout ---\n{proc.stdout}"
            f"\n--- stderr ---\n{proc.stderr}",
            encoding="utf-8",
        )
        if not quiet:
            tail = (proc.stdout or proc.stderr).strip().splitlines()[-1:] or [""]
            print(f"    {scratch.name}  {tail[0][:100]}", flush=True)
        return proc.returncode == 0

    return go


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mutate", description=__doc__.split("\n")[0])
    ap.add_argument(
        "--runner",
        choices=sorted(LANGUAGES),
        default="tests",
        help="tests = a Python service (runtests.sh), qml = the HUD's core "
        "(qmltest.sh), cargo = a Rust crate (cargotest.sh), shots = the HUD's "
        "PLATES through the staged shell (hudshots.sh, ~53 s a run)",
    )
    ap.add_argument("target", help="the service, `hud`, or the crate to grade")
    ap.add_argument("spec", nargs="?", default="-", help="spec file, or - for stdin")
    args = ap.parse_args(argv)

    lang = LANGUAGES[args.runner]
    if lang.targets is not None and args.target not in lang.targets:
        print(
            f"--runner {lang.runner} grades {' or '.join(lang.targets)}, not {args.target!r}",
            file=sys.stderr,
        )
        return 2

    root = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )
    text = sys.stdin.read() if args.spec == "-" else Path(args.spec).read_text(encoding="utf-8")

    try:
        muts = parse_spec(text)
    except SpecError as exc:
        print(f"spec: {exc}", file=sys.stderr)
        return 2

    print(f"{len(muts)} mutation(s) against {args.target} ({lang.runner})", flush=True)
    for m in muts:
        print(f"  @ {m.label}  ({m.path})", flush=True)
    # Said out loud because one of the four runners costs ~53 s a run: the
    # grading is a baseline, a canary per file, the mutations, and a baseline
    # again, and a loop that knows the count before it starts can decide to
    # send fewer mutations rather than abandon a run half way through.
    print(f"  at least {suite_runs(muts)} suite runs", flush=True)
    probe: Origin | None = None
    if lang.origin is not None:
        probe = lambda module: lang.origin(root, args.target, module)  # noqa: E731
    try:
        report = run(
            muts,
            script_runner(root, lang, args.target),
            root=root,
            lang=lang,
            origin=probe,
        )
    except HarnessError as exc:
        print(f"\nHARNESS: {exc}", file=sys.stderr)
        return 2
    print("\n" + report.summary())
    if report.logs is not None:
        print(
            f"\nkept: {report.logs} — {INDEX} names every run, each run dir "
            f"holds its {WHAT} and the suite's whole {SUITE_LOG}. Delete it "
            f"when you are done with it.",
            flush=True,
        )
    return 0 if report.survived == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
