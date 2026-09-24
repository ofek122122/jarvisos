#!/usr/bin/env python3
"""The Ralph loop's mutation harness — PLAN B48, extended to three languages
by B49.

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


@dataclasses.dataclass(frozen=True)
class Report:
    outcomes: Sequence[Outcome]

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
    every test that instantiates it fails to compile."""
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

    def command(self, root: Path, target: str) -> list[str]:
        cmd = ["bash", str(root / "ops" / "ralph" / self.script)]
        if self.pass_target:
            cmd.append(target)
        return cmd


PYTHON = Language(
    runner="tests",
    script="runtests.sh",
    suffixes=(".py",),
    canary=python_canary,
    env=python_env,
    targets=None,
    pass_target=True,
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

LANGUAGES: dict[str, Language] = {lang.runner: lang for lang in (PYTHON, QML, CARGO)}


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


def check_language(mut: Mutation, lang: Language) -> None:
    """Refuse a file this runner's suite could not be grading.

    Not pedantry: `--runner tests` on a `.qml` file would append a Python
    `raise` to QML, which parses as nothing, so the canary would LIVE and the
    harness would abort with a confusing message about the wrong thing."""
    if Path(mut.path).suffix not in lang.suffixes:
        raise HarnessError(
            f"{mut.path} is not a {'/'.join(lang.suffixes)} file, so --runner "
            f"{lang.runner} is the wrong grader for it"
        )


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

Runner = Callable[[Mapping[str, str]], bool]


def run(
    mutations: Iterable[Mutation],
    runner: Runner,
    *,
    root: Path,
    lang: Language = PYTHON,
) -> Report:
    """Grade `mutations`. `runner(env)` runs the suite and returns True if it
    passed; `env` carries this run's private cache directory.

    Order: baseline (must be green) -> one canary per file (each must be red)
    -> the mutations -> baseline again (must be green).
    """
    mutations = list(mutations)
    if not mutations:
        raise HarnessError("no mutations in the spec; a perfect score of zero is not a claim")

    targets: dict[str, Path] = {}
    for m in mutations:
        check_language(m, lang)
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

    def suite() -> bool:
        state["n"] += 1
        cache = base / f"run{state['n']:03d}"
        cache.mkdir()
        return bool(runner(lang.env(cache)))

    def swapped(rel: str, text: str) -> bool:
        """Run the suite with `rel` holding `text`, then put it back."""
        path = targets[rel]
        try:
            write(path, text)
            return suite()
        finally:
            write(path, originals[rel])

    try:
        if not suite():
            raise HarnessError(
                "the baseline suite is RED before any mutation. Every mutation "
                "would be reported as caught for free; fix the suite first."
            )

        for rel in targets:
            if swapped(rel, with_canary(originals[rel], lang)):
                raise HarnessError(
                    f"the canary lived: the suite stayed GREEN with {rel} made "
                    f"impossible to load, so the suite does not execute that "
                    f"file. Nothing this harness could report about it would "
                    f"mean anything — check the runner, the target, and that "
                    f"the tests read the worktree and not an installed copy."
                )

        outcomes: list[Outcome] = []
        for mut in mutations:
            mutant = apply_once(originals[mut.path], mut.old, mut.new)
            passed = swapped(mut.path, mutant)
            outcomes.append(
                Outcome(mut.label, mut.path, "survived" if passed else "caught")
            )

        for rel, path in targets.items():
            if path.read_text(encoding="utf-8") != originals[rel]:
                raise HarnessError(f"{rel} was not restored; put it back by hand before committing")
        if not suite():
            raise HarnessError(
                "the suite is RED after the last restore, with every file back "
                "as it was. Something outside these mutations is broken — do "
                "not commit until it is green."
            )
        return Report(outcomes)
    finally:
        shutil.rmtree(base, ignore_errors=True)


# --------------------------------------------------------------------- cli


def script_runner(root: Path, lang: Language, target: str, *, quiet: bool = False) -> Runner:
    """The real runner: one of the loop's own `ops/ralph/*.sh` suites."""
    cmd = lang.command(root, target)

    def go(env: Mapping[str, str]) -> bool:
        proc = subprocess.run(
            cmd,
            cwd=root,
            env={**os.environ, **env},
            capture_output=True,
            text=True,
        )
        if not quiet:
            tail = (proc.stdout or proc.stderr).strip().splitlines()[-1:] or [""]
            print(f"    {tail[0][:100]}", flush=True)
        return proc.returncode == 0

    return go


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mutate", description=__doc__.split("\n")[0])
    ap.add_argument(
        "--runner",
        choices=sorted(LANGUAGES),
        default="tests",
        help="tests = a Python service (runtests.sh), qml = the HUD "
        "(qmltest.sh), cargo = a Rust crate (cargotest.sh)",
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
    try:
        report = run(muts, script_runner(root, lang, args.target), root=root, lang=lang)
    except HarnessError as exc:
        print(f"\nHARNESS: {exc}", file=sys.stderr)
        return 2
    print("\n" + report.summary())
    return 0 if report.survived == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
