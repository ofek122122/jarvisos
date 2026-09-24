#!/usr/bin/env python3
"""The Ralph loop's mutation harness — PLAN B48.

Every iteration of this loop writes a sentence like "six mutations, six
caught". The sentence is the loop's only evidence that the tests it just
wrote have teeth, and until now it was produced by hand: edit the source,
re-run pytest, read the colour, put the file back. Iteration 70 found the
hole in that practice. CPython validates a cached `.pyc` against the source's
(mtime **in whole seconds**, size), so an equal-length edit written inside
the same second as the write before it reuses stale bytecode: pytest reports
a PASS for a mutant that never executed, the loop writes "survived", and the
only tell arrives later — a full-suite failure on a file that has already
been RESTORED and is still running the mutant out of the cache.

So this harness is not an automation of the old practice. It is the old
practice plus the two controls it never had:

**The canary.** Before a single mutation is graded, the target file is made
impossible to import and the suite MUST go red. If it stays green, the tests
do not execute that file at all — every mutation would be a silent survivor
— and the harness refuses to report anything rather than print a perfect
score. This is the direct test of the assumption the old practice made
implicitly, and it is stronger than reasoning about bytecode: it asks the
suite itself whether this file is the file it runs.

**A cache that cannot be stale.** Every suite run gets its OWN empty
`PYTHONPYCACHEPREFIX`, so no run can read bytecode compiled by another and
the in-tree `__pycache__` directories are unreachable rather than deleted.
Note for whoever reads B48: `python -B` alone does nothing about this. It
stops bytecode being WRITTEN, not read — the half that worked in iteration
70 was clearing `__pycache__`. `-B` is still set here, so a harness run
leaves no new caches beside the source, but the prefix is the guarantee.

Usage (spec on stdin is the ergonomic path — no scratch file to clean up):

    bash ops/ralph/mutate.sh jv-voice <<'EOF'
    # one block per mutation
    @ the inter-sentence gap widened
    services/jv-voice/jv_voice/service.py
    - TURN_GAP_S = 0.5
    + TURN_GAP_S = 0.9
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
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

CANARY_MARK = "jv-mutate canary: this file must be executed by the suite"
CANARY_LINE = f'raise ImportError("{CANARY_MARK}")'


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


def with_canary(text: str) -> str:
    """The same file, made impossible to import. Appended at column zero so
    it runs on import from outside any trailing indented block, and after a
    newline the file may not have had."""
    tail = "" if text.endswith("\n") or not text else "\n"
    return f"{text}{tail}{CANARY_LINE}\n"


def run_env(cache_dir: Path) -> dict[str, str]:
    """The environment every suite run gets: a private, empty bytecode cache
    (so nothing compiled by another run can be read) and no writing beside
    the source (so a harness run leaves the tree as it found it)."""
    return {
        "PYTHONPYCACHEPREFIX": str(cache_dir),
        "PYTHONDONTWRITEBYTECODE": "1",
    }


# --------------------------------------------------------------------- run

Runner = Callable[[Mapping[str, str]], bool]


def run(mutations: Iterable[Mutation], runner: Runner, *, root: Path) -> Report:
    """Grade `mutations`. `runner(env)` runs the suite and returns True if it
    passed; `env` carries this run's private cache directory.

    Order: baseline (must be green) -> one canary per file (each must be red)
    -> the mutations -> baseline again (must be green).
    """
    mutations = list(mutations)
    if not mutations:
        raise HarnessError("no mutations in the spec; a perfect score of zero is not a claim")

    targets = {m.path: resolve(m, root=root) for m in mutations}
    for rel, path in targets.items():
        if not path.is_file():
            raise HarnessError(f"no such file to mutate: {rel}")
    originals = {rel: path.read_text(encoding="utf-8") for rel, path in targets.items()}

    base = Path(tempfile.mkdtemp(prefix="jv-mutate-"))
    state = {"n": 0}

    def suite() -> bool:
        state["n"] += 1
        cache = base / f"run{state['n']:03d}"
        cache.mkdir()
        return bool(runner(run_env(cache)))

    def swapped(rel: str, text: str) -> bool:
        """Run the suite with `rel` holding `text`, then put it back."""
        path = targets[rel]
        try:
            path.write_text(text, encoding="utf-8")
            return suite()
        finally:
            path.write_text(originals[rel], encoding="utf-8")

    try:
        if not suite():
            raise HarnessError(
                "the baseline suite is RED before any mutation. Every mutation "
                "would be reported as caught for free; fix the suite first."
            )

        for rel in targets:
            if swapped(rel, with_canary(originals[rel])):
                raise HarnessError(
                    f"the canary lived: the suite stayed GREEN with {rel} made "
                    f"impossible to import, so the suite does not execute that "
                    f"file. Nothing this harness could report about it would "
                    f"mean anything — check the runner, the service, and that "
                    f"the tests import the worktree and not an installed copy."
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


def pytest_runner(root: Path, service: str, *, quiet: bool = False) -> Runner:
    """The real runner: the loop's own `ops/ralph/runtests.sh <service>`."""

    def go(env: Mapping[str, str]) -> bool:
        proc = subprocess.run(
            ["bash", str(root / "ops" / "ralph" / "runtests.sh"), service],
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
    ap.add_argument("service", help="a service name ops/ralph/runtests.sh knows")
    ap.add_argument("spec", nargs="?", default="-", help="spec file, or - for stdin")
    args = ap.parse_args(argv)

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

    print(f"{len(muts)} mutation(s) against {args.service}", flush=True)
    for m in muts:
        print(f"  @ {m.label}  ({m.path})", flush=True)
    try:
        report = run(muts, pytest_runner(root, args.service), root=root)
    except HarnessError as exc:
        print(f"\nHARNESS: {exc}", file=sys.stderr)
        return 2
    print("\n" + report.summary())
    return 0 if report.survived == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
