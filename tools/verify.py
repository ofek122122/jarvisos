#!/usr/bin/env python3
"""Run every gate that reads what you changed, and AND their verdicts (B70).

`tools/dependents.py` (B68, B69) answers "which suites read this?" and
`runtests.sh` prints the answer at the end of every run. That is advice: the
exit status stays pytest's, so an iteration can read the line and not run what
it names. The rule it replaced — "run the relevant test suite(s)" — was also
advice, and it was wrong three times in ninety iterations, each time leaving a
red suite committed for days.

This is the same information with a verdict on it. It asks git what changed,
asks `dependents` who reads it, adds the Rust that `dependents` can only
apologise for, runs every one of them, and exits non-zero if ANY of them
failed. Nothing about which suite is "relevant" is left to the author.

THE COST, since B70 called this a cost question and nobody had measured it.
One suite at a time, warm venvs, on ares' hardware:

    pylib          1.6 s      jv-guard       3.9 s      jv-voice      23.0 s
    jv-hud-bridge  1.6 s      jv-context    11.4 s      jv-brain      36.3 s
    jv-compat      2.7 s      tools         12.2 s      jv-ears      145.8 s
    harness        3.4 s                               ----------------------
                                                        all ten      241.7 s

Four minutes, once, for the worst change in the repo (`services/pylib/`, which
every service imports), and 60% of that is jv-ears alone. A service change is
that service plus `tools`; a HUD change is `tools` plus the two QML gates,
about 80 s. B70 floated binding only when the named set is small — that is not
a cheaper version of this, it is this with the `services/pylib/` case removed,
and that case is the only one where the author could not possibly have guessed
the readers. Every step prints its own seconds so the table above can be
re-measured by anyone who thinks it has drifted.

AND THE THREE GATES THAT ARE A NIX EVALUATION (B72, D41).
`ops/ralph/nixtest.sh` reads `.#nixosConfigurations.ares`,
`ops/ralph/hudscreens.sh` photographs `.#jv-hud`, and `ops/ralph/shellload.sh`
loads all three shells under a real quickshell; a flake attribute is not a path
anything can walk, so all three are DECLARED in `dependents.DECLARED_GATES`
against their own `# reads:` headers. Two of them are steps like any other:
`nixtest.sh` at 22 s is the only thing in this repo that asserts what a module
OPTION does to the unit text ares is handed, and `shellload.sh` at 25 s is the
only thing that ever opens the bar's or the notifier's `shell.qml` at all.
`hudscreens.sh` is not: 3m00s, a compositor, and a sheet of photographs
somebody has to look at and commit — and they are not reproducible, so a
bound run would dirty the tree this verdict was computed from every single
time. It is NAMED instead, beside the paths that asked for it, on every
verdict — green or red — because the failure being prevented here is a gate
that is quietly not in the list. D41 is the answer to the obvious next
question, and it is a qualified no: the CHEAP half of `hudscreens.sh` — did
the shell load, did it say anything that throws — really is a verdict a gate
can collect, and it is now this second gate. What stayed behind is the
pictures and the 97.7 s idle probe, which is most of the price.

AND THE RUNNERS (B73). `runtests.sh` and `cargotest.sh` are not suites and are
read by none: they are HOW a suite runs — the venv and the PYTHONPATH for one,
the nix dev shell and the vendored registry for the other. Nothing derived
could reach either, so a change to `runtests.sh` used to plan `tools` alone
(which reads it as text) and a change to `cargotest.sh` planned exactly that
too. Each is now every suite it can run: ten Python suites, both crates. That
is the 241.7 s case above, and it is the same argument — nobody can guess
which of the ten a change to the runner moved.

WHAT THIS IS NOT. It is not the whole verify gate. `nixos-rebuild build
--flake .#ares` is, and so is `nix build .#jarvisd`. Those are named in
PROMPT.md and run beside this.

AND IT IS ABOUT A SHARED BRANCH, WHICH IS WHOSE FAILURE (D80). This branch is
driven by the loop and by hand at the same time, so a red gate is not
necessarily yours: 490d1ad opened on one item, built it, and found three gates
red from three commits that had landed while it worked. That is not a small
inconvenience, because `tools` is the third suite to everything (Invariant 1)
and is named for any Python, QML, nix or `pkgs/` change AND — measured — for a
change to `JOURNAL.md` or `PLAN.md`. A red `tools` is therefore a repo where
NOTHING is committable, including the journal entry STEP 3 asks for when a gate
is red and the work has to be reverted. There is no way out of such an
iteration except by fixing somebody else's red.

`--baseline` is the way out. It re-runs the gates that FAILED, at HEAD, in a
`git worktree add --detach` under `$TMPDIR` — so the working tree is never
touched and the shared stash stack is never used — and labels each one:

    INHERITED  red at HEAD too, with the same failure lines. Not yours.
    NEW        green at HEAD. Yours. Always fatal.
    CHANGED    red at HEAD, but your run fails in a way HEAD's does not.
               Fatal: an inherited red is not a place to hide a new one.
    UNKNOWN    no baseline could be established — the worktree would not
               build, or the gate does not EXIST at HEAD because you just
               wrote it. Fatal, because a gate with no baseline is not a
               gate with a clean one.

All-INHERITED exits 3, which is a different sentence to the loop than exit 1:
"RED, and every failure predates you." Everything else that is red still exits
1. Three things this gets right on purpose. It re-runs only the gates that
FAILED, not the whole plan — a green gate cannot have inherited anything, so
the doubling D80 expected is only the worst case where every gate is red. It
compares WITHIN a gate as well as across gates, over the failure lines it can
recognise (`FAILED`, `FAIL`, `ERROR`, `error:`), which is what stops a new
failing test from riding into a suite that was already red; a gate whose
failure text it cannot parse falls back to the exit status, and that fallback
is stated in the report rather than implied. And a gate that is missing at HEAD
is never INHERITED, which is the hole a naive exit-status comparison leaves
wide open: a brand-new gate script that is red exits 127 at HEAD, and 127 is
not evidence of anything.

AND IT IS ABOUT THE TREE. `git status`, not the index: the failure in 5a3f1e9
was a green working tree whose commit took 31 of its 33 files, and no verdict
computed before a commit can see what that commit will contain. So the verdict
prints the paths it covers, and `--since <ref>` exists to ask the question
again about what a commit actually took.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable, Iterable, Iterator, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dependents  # noqa: E402

# The script every crate's tests are RUN by, and the command that runs one.
# Split apart the way `dependents.RUNTESTS_SH` is: the path is a read in its
# own right (PLAN B73).
CARGOTEST_SH = "ops/ralph/cargotest.sh"
CARGOTEST = f"bash {CARGOTEST_SH}"


@dataclasses.dataclass(frozen=True)
class Step:
    """One command the gate will run, and the changed paths that asked for it."""

    command: str
    why: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class Result:
    step: Step
    status: int
    seconds: float
    log: Path | None = None

    @property
    def ok(self) -> bool:
        return self.status == 0

    def output(self) -> str:
        """Everything the gate said, if anybody asked for it to be kept.

        Only `--baseline` asks: the default run streams straight to the
        terminal and keeps nothing, which is the behaviour every other verdict
        in this file was measured against.
        """
        if self.log is None or not self.log.is_file():
            return ""
        return self.log.read_text("utf-8", errors="replace")


# --------------------------------------------------------------- the Rust half


def crates(root: Path) -> list[str]:
    """Every crate under `services/`, by having a `Cargo.toml`.

    `dependents` prints a standing caveat here instead of an answer, because a
    Rust crate keeps its tests inside the source they test and there is no
    third file naming a path to derive anything from. But the caveat's own
    sentence — "a change under services/jarvisd or services/jv-act is
    cargotest.sh <crate>, always" — is a rule, and a rule can be a step. This
    reads the directory rather than the two names, so a third crate needs no
    edit here.
    """
    services = root / "services"
    if not services.is_dir():
        return []
    return sorted(
        d.name for d in services.iterdir() if (d / "Cargo.toml").is_file()
    )


def rust_commands(root: Path, paths: Iterable[str]) -> dict[str, list[str]]:
    """`cargotest.sh <crate>` -> the changed paths inside that crate.

    The prefix test is per segment: `services/crate-xyz/f` is not inside
    `services/crate-x`, and a string `startswith` would say it was.

    Plus the runner, which is inside no crate and read by no suite (PLAN B73).
    `cargotest.sh` is HOW a crate's tests run at all — it borrows the
    derivation's dev shell for cargo, rustc and the vendored registry, and
    points the build at a cache outside the repo — so a change to it is every
    crate, for the same reason `dependents` makes a change to `runtests.sh`
    every Python suite. Guarded on the file being there: a deleted runner is a
    changed path, and a command that cannot run is worse advice than none.
    """
    want = sorted({rel for g in paths for rel in _rels(root, g)})
    runner = CARGOTEST_SH in want and (root / CARGOTEST_SH).is_file()
    out: dict[str, list[str]] = {}
    for crate in crates(root):
        under = f"services/{crate}"
        hit = [
            p
            for p in want
            if p == under or p.startswith(under + "/") or (runner and p == CARGOTEST_SH)
        ]
        if hit:
            out[f"{CARGOTEST} {crate}"] = hit
    return out


def _rels(root: Path, given: str) -> list[str]:
    """`given` as repo-relative paths, the way `dependents` expands it — a
    directory stands for its files, because `git status` reports an untracked
    directory as one entry."""
    return dependents._expand(root, given)


# ------------------------------------------------------------------- the plan


def plan(
    root: Path,
    paths: Iterable[str],
    *,
    warn: Callable[[str], None] | None = None,
) -> list[Step]:
    """Every gate that reads `paths`, each exactly once, in a fixed order.

    Fixed because the per-step seconds this prints are the only measurement
    anyone has of what the gate costs, and an order that depended on which
    path was listed first would make two runs incomparable. `dependents`
    already returns its suites sorted and its QML gates in declaration order;
    Rust follows, because a crate's tests are the slowest thing here and are
    the least likely to be what the author just broke.
    """
    paths = list(paths)
    found = dict(dependents.commands(root, paths, warn=warn))
    found.update(rust_commands(root, paths))
    return [Step(command=cmd, why=tuple(why)) for cmd, why in found.items()]


# ---------------------------------------------------------------- the running


def _spawn(root: Path, command: str, log: Path | None = None) -> int:
    """Run one gate with its output going straight to the terminal.

    Not captured: a 145-second suite behind a pipe is indistinguishable from a
    hang, and the line naming the failing test is the only thing the author
    needs. A gate that cannot be STARTED at all — script deleted, nix missing
    — is a red step and not a traceback, because a traceback out of the gate
    is a verdict nobody gets.

    `RALPH_GATE=1` tells `runtests.sh` to keep its dependents notice to itself.
    That notice is advice for whoever picked a suite by hand; printed once per
    step it would have this gate urging the reader, nine times over, to run the
    suites it is in the middle of running.

    `log` is the one departure, and it is opt-in for a reason: comparing a
    failure against HEAD's needs the TEXT of the failure, so a `--baseline` run
    reads each line and writes it to both the terminal and a file. That costs
    the child its tty — pytest loses its colour — and the default path must not
    pay for a flag nobody passed, so with no `log` this is the plain inherited
    stdio it has always been.
    """
    env = {**os.environ, "RALPH_GATE": "1"}
    try:
        if log is None:
            return subprocess.run(
                ["bash", "-c", command], cwd=str(root), env=env
            ).returncode
        with subprocess.Popen(
            ["bash", "-c", command],
            cwd=str(root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            bufsize=1,
        ) as proc, log.open("w", encoding="utf-8") as fh:
            for line in proc.stdout:  # type: ignore[union-attr]
                sys.stdout.write(line)
                sys.stdout.flush()
                fh.write(line)
            return proc.wait()
    except OSError as exc:  # no bash, no cwd, nothing left to run with
        print(f"verify: could not start `{command}`: {exc}", flush=True)
        return 127


def run(
    root: Path,
    steps: Sequence[Step],
    *,
    spawn: Callable[..., int] = _spawn,
    clock: Callable[[], float] = time.monotonic,
    logs: Path | None = None,
    label: str = "",
) -> list[Result]:
    """Every step, in order, all of them, whatever the earlier ones did.

    Fail-fast is the wrong trade for a gate whose entire subject is the OTHER
    red suite you did not know about: stopping at the first failure hands back
    the partial picture this exists to replace, and costs a second full run —
    minutes — to learn the rest.
    """
    results: list[Result] = []
    for i, step in enumerate(steps, 1):
        tag = f"{label}[{i}/{len(steps)}]"
        print(f"\n── {tag} {step.command}", flush=True)
        log = None if logs is None else logs / f"{label}{i}.log"
        start = clock()
        status = spawn(root, step.command, log)
        took = clock() - start
        word = "ok" if status == 0 else f"FAILED (exit {status})"
        print(f"── {tag} {word}  {took:.1f} s", flush=True)
        results.append(Result(step=step, status=status, seconds=took, log=log))
    return results


# --------------------------------------------------------------- the baseline

# What `--baseline` can conclude about one red gate. INHERITED is the only one
# that is not fatal, and it is the entire reason the flag exists (PLAN D80);
# every other label, including the two that mean "could not tell", keeps the
# exit status at 1.
INHERITED = "INHERITED"
NEW = "NEW"
CHANGED = "CHANGED"
UNKNOWN = "UNKNOWN"
FATAL = (NEW, CHANGED, UNKNOWN)

# The exit status for "red, and every failure predates you". Not 0 — the repo
# IS red and no report here may say GREEN — and not 1, because 1 is the status
# STEP 3 reads as "revert what you did", which is the wrong instruction for a
# failure somebody else committed.
EXIT_INHERITED = 3

# A line that is a gate reporting a failure, across the four shapes this repo
# has: pytest's `FAILED tests/x.py::test_y`, qmltestrunner's `FAIL!  : tst_X`,
# nixtest.sh's `  FAIL <name>`, and a nix evaluation's `error:`. Deliberately
# not a parser — it is a fingerprint, and the only question asked of it is
# whether your run says something HEAD's did not.
_FAILURE_LINE = re.compile(r"^\s*(FAILED|FAIL!|FAIL|ERRORS?|error:|not ok)\b")

# The two things in a failure line that differ between two runs of the same
# failure: a store path rebuilt under a different hash, and the root the gate
# ran in (which is a temp worktree for the baseline and this repo for you).
_STORE = re.compile(r"/nix/store/[0-9a-df-np-sv-z]{32}-")


def failure_lines(text: str, roots: Sequence[Path] = ()) -> frozenset[str]:
    """The failure lines in `text`, with what cannot match normalised away.

    Counts and timings are not in here, because they are not failure lines —
    `792 passed in 66.41s` is a summary, and comparing summaries would make
    every run differ from every other. What is in here is the name of each
    thing that went wrong, which is exactly what a human compares by eye when
    they read two runs in a transcript and decide whose red it is.
    """
    out: set[str] = set()
    for raw in text.splitlines():
        if not _FAILURE_LINE.match(raw):
            continue
        line = _STORE.sub("/nix/store/H-", raw.strip())
        for root in roots:
            line = line.replace(str(root), "<root>")
        out.add(line)
    return frozenset(out)


@dataclasses.dataclass(frozen=True)
class Verdict:
    """One red gate, and whether HEAD was red the same way."""

    command: str
    label: str
    seconds: float
    note: str = ""
    extra: tuple[str, ...] = ()

    @property
    def fatal(self) -> bool:
        return self.label in FATAL


@dataclasses.dataclass(frozen=True)
class Baseline:
    """Every red gate asked again at `sha`, plus why it could not be asked."""

    sha: str
    error: str
    verdicts: tuple[Verdict, ...]

    @property
    def fatal(self) -> tuple[Verdict, ...]:
        return tuple(v for v in self.verdicts if v.fatal)


def _gate_script(command: str) -> str | None:
    """The `.sh` in `bash ops/ralph/runtests.sh tools`, if there is one.

    Asked so that a gate which does not exist at HEAD is never called
    INHERITED. A gate script you have only just written exits 127 at HEAD, and
    127 out of `bash` is indistinguishable from a suite that was already red —
    which would hand a brand-new broken gate the one label that is not fatal.
    """
    try:
        parts = shlex.split(command)
    except ValueError:
        return None
    return next((p for p in parts if p.endswith(".sh")), None)


@contextlib.contextmanager
def head_worktree(root: Path) -> Iterator[tuple[Path | None, str]]:
    """A throwaway checkout of HEAD, outside the repo, removed on the way out.

    `git worktree add --detach`, under `$TMPDIR`, for three reasons that are
    each a rule somewhere else. It is not a `git stash`: this branch is shared
    with the main checkout and other sessions, and popping somebody else's
    entry is the accident the worktree rules in this repo exist to prevent. It
    is not in the repo: a checkout under `root` would be an untracked
    directory, which is a changed path, which is an input to the very plan this
    is a baseline for. And it is detached: HEAD is already checked out here, and
    a second worktree on the same branch is refused.
    """
    tmp = Path(tempfile.mkdtemp(prefix="verify-baseline-"))
    where = tmp / "head"
    done = subprocess.run(
        ["git", "-C", str(root), "worktree", "add", "--detach", "-q",
         str(where), "HEAD"],
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        yield None, (done.stderr.strip() or done.stdout.strip() or
                     f"git worktree add exited {done.returncode}")
        return
    try:
        yield where, ""
    finally:
        subprocess.run(
            ["git", "-C", str(root), "worktree", "remove", "--force", str(where)],
            capture_output=True,
            text=True,
        )
        shutil.rmtree(tmp, ignore_errors=True)
        subprocess.run(
            ["git", "-C", str(root), "worktree", "prune"],
            capture_output=True, text=True,
        )


def _head_sha(root: Path) -> str:
    done = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True,
    )
    return done.stdout.strip() if done.returncode == 0 else "HEAD"


def baseline(
    root: Path,
    results: Sequence[Result],
    *,
    spawn: Callable[..., int] = _spawn,
    clock: Callable[[], float] = time.monotonic,
    logs: Path | None = None,
) -> Baseline:
    """Ask HEAD about every gate that just failed, and label each answer.

    Only the failures. A gate that passed in your tree cannot have inherited
    anything, so re-running it would buy nothing and D80's "it doubles the
    wall clock" is the worst case — every gate red — rather than the price of
    the flag.
    """
    red = [r for r in results if not r.ok]
    if not red:
        return Baseline(sha=_head_sha(root), error="", verdicts=())

    sha = _head_sha(root)
    with head_worktree(root) as (where, error):
        if where is None:
            return Baseline(
                sha=sha,
                error=error,
                verdicts=tuple(
                    Verdict(command=r.step.command, label=UNKNOWN, seconds=0.0,
                            note="no baseline worktree")
                    for r in red
                ),
            )
        print(
            f"\nverify: baseline — re-running the {_n(red, 'red gate')} at "
            f"{sha} in {where}",
            flush=True,
        )
        verdicts: list[Verdict] = []
        for i, r in enumerate(red, 1):
            script = _gate_script(r.step.command)
            if script is not None and not (where / script).is_file():
                verdicts.append(
                    Verdict(
                        command=r.step.command,
                        label=UNKNOWN,
                        seconds=0.0,
                        note=f"{script} does not exist at {sha}",
                    )
                )
                print(
                    f"\n── base[{i}/{len(red)}] {r.step.command}\n"
                    f"── base[{i}/{len(red)}] {UNKNOWN}  {script} is not at {sha}",
                    flush=True,
                )
                continue
            log = None if logs is None else logs / f"base{i}.log"
            print(f"\n── base[{i}/{len(red)}] {r.step.command}", flush=True)
            start = clock()
            status = spawn(where, r.step.command, log)
            took = clock() - start
            if status == 0:
                verdict = Verdict(
                    command=r.step.command, label=NEW, seconds=took,
                    note=f"green at {sha}",
                )
            else:
                mine = failure_lines(r.output(), (root, where))
                theirs = failure_lines(
                    log.read_text("utf-8", errors="replace")
                    if log is not None and log.is_file()
                    else "",
                    (root, where),
                )
                extra = tuple(sorted(mine - theirs))
                verdict = Verdict(
                    command=r.step.command,
                    label=CHANGED if extra else INHERITED,
                    seconds=took,
                    note=(
                        f"red at {sha} too, and failing differently here"
                        if extra
                        else f"red at {sha} too (exit {status})"
                        if mine or theirs
                        else f"red at {sha} too (exit {status}); no failure "
                             f"line either run could be compared"
                    ),
                    extra=extra,
                )
            verdicts.append(verdict)
            print(
                f"── base[{i}/{len(red)}] {verdict.label}  {took:.1f} s",
                flush=True,
            )
    return Baseline(sha=sha, error="", verdicts=tuple(verdicts))


# ----------------------------------------------------------------- the report


def skipped(root: Path, paths: Iterable[str]) -> list[tuple[str, list[str], str]]:
    """The gates that read what changed and that this deliberately does not run.

    One today: `hudscreens.sh`, and not for being hard — it runs here fine,
    measured at 3m00s, of which 2m25s is the probes (B75: the run books its
    own phases now, and a version of it that kept no pictures would save 19%
    — the screens are not what it costs). It is out because what it produces is not a verdict to
    collect: a sheet of photographs a human looks at. B72 gave a second reason — it
    rewrites the tree the plan was computed from, every run, because two runs
    of an unchanged HUD do not agree to the byte — and B74 measured that noise
    and put a floor under it, so a run that changed nothing now restores what
    it compared against and leaves the tree clean. What is left of that reason
    is the run that DID change the HUD: new PNGs to look at, which is
    the right outcome at a keyboard and the wrong one inside a gate. So it is
    reported instead — on EVERY verdict, because the whole point of this file
    is that nothing which reads your change goes unmentioned.
    """
    return [
        (gate.script, why, gate.note)
        for gate, why in dependents.unrun(root, list(paths))
    ]


def report(
    results: Sequence[Result],
    paths: Sequence[str],
    skips: Sequence[tuple[str, list[str], str]] = (),
    base: Baseline | None = None,
) -> list[str]:
    """The table at the end, which is the part that is actually read.

    A real run of this is minutes of somebody else's test runner scrolling
    past, so the summary has to hold the whole answer on its own: every gate,
    its verdict, its exit status when it failed, and its price.
    """
    lines: list[str] = [""]
    if not results:
        lines += [
            f"verify: no gate reads any of the {_n(paths, 'path')} that changed.",
            "",
        ]
    else:
        bad = [r for r in results if not r.ok]
        width = max(len(r.step.command) for r in results)
        lines += [
            f"verify: {_n(results, 'gate')}, "
            f"{len(results) - len(bad)} ok, {len(bad)} FAILED — "
            f"{sum(r.seconds for r in results):.1f} s",
            "",
        ]
        for r in results:
            note = "" if r.ok else f"   (exit {r.status})"
            lines.append(
                f"  {'ok' if r.ok else 'FAILED':<7}{r.seconds:7.1f} s  "
                f"{r.step.command.ljust(width)}{note}"
            )
        lines.append("")
    lines += _skips(skips)
    red = [r for r in results if not r.ok]
    if red:
        lines += _baseline(red, base)
        return lines

    lines += [
        f"verify: GREEN over {_n(paths, 'path')}:",
        "",
    ]
    lines += [f"    {p}" for p in paths]
    lines += [
        "",
        "This verdict is about the WORKING TREE. Nothing here can see the index,",
        "so a commit that takes fewer files than these was never verified (5a3f1e9);",
        "`verify.sh --since HEAD~1` asks the question again about what it took.",
        "",
    ]
    return lines


def _baseline(red: Sequence[Result], base: Baseline | None) -> list[str]:
    """The last word on a red run: yours, or one you walked into (PLAN D80).

    Three sentences, and only one of them lets the iteration continue. With no
    `--baseline` it is the sentence this file has always ended on, because a
    red gate whose history nobody asked about is a red gate you must assume is
    yours.
    """
    if base is None:
        return [
            "verify: RED. Do not commit.",
            "",
            "If this branch is shared and you suspect the reds predate you, ask:",
            "`bash ops/ralph/verify.sh --baseline` re-runs just these gates at HEAD",
            "in a throwaway worktree and says which failures are yours.",
            "",
        ]

    lines = [f"verify: baseline against {base.sha} —"]
    if base.error:
        lines += ["", f"  the baseline worktree could not be made: {base.error}"]
    lines += [""]
    width = max([len(v.command) for v in base.verdicts] or [1])
    for v in base.verdicts:
        lines.append(f"  {v.label:<11}{v.command.ljust(width)}   # {v.note}")
        for extra in v.extra:
            lines.append(f"      only here: {extra}")
    lines += [""]

    covered = {v.command for v in base.verdicts}
    missing = [r.step.command for r in red if r.step.command not in covered]
    if missing or base.fatal or not base.verdicts:
        # Anything this could not account for counts against you. The label
        # that means "I could not tell" must never be the label that lets a
        # failure through, or the flag becomes a way to commit past your own
        # breakage by making the baseline fail.
        for cmd in missing:
            lines.append(f"  {UNKNOWN:<11}{cmd}   # never asked about")
        if missing:
            lines.append("")
        if base.verdicts:
            claim = (
                f"{_n(base.fatal, 'failure')} "
                f"{'is' if len(base.fatal) == 1 else 'are'} yours"
                + (f" (plus {len(missing)} this could not ask about)"
                   if missing else "")
            )
        else:
            claim = "the baseline established nothing about it"
        lines += [f"verify: RED, and {claim}. Do not commit.", ""]
        return lines

    return [
        *lines,
        f"verify: RED, and every one of these {_n(red, 'failure')} was ALREADY",
        f"red at {base.sha}, failing the same way. Nothing you changed turned a",
        "gate red.",
        "",
        "What that licenses: committing YOUR work and the journal entry for it,",
        "on a branch somebody else has left red. What it does not: committing a",
        "change to a gate that is red, or leaving the inherited failures unsaid —",
        "name them in the journal so the next iteration does not re-discover them.",
        "",
        "And what it cannot see: a gate whose failure text this could not read is",
        "compared by exit status alone, and says so in its note above.",
        "",
    ]


def _skips(skips: Sequence[tuple[str, list[str], str]]) -> list[str]:
    """The named-not-run block. Loud, and above the verdict rather than under
    it, so it cannot be read as a footnote to a GREEN."""
    if not skips:
        return []
    lines = [f"verify: NOT RUN here, and reading what you changed — "
             f"{_n(skips, 'gate')}:", ""]
    for script, why, note in skips:
        shown = ", ".join(why[:3]) + (f", +{len(why) - 3} more" if len(why) > 3 else "")
        lines += [f"  bash {script}   # {shown}", f"      {note}", ""]
    return lines


def _n(items: Sequence[object], noun: str) -> str:
    return f"{len(items)} {noun}{'' if len(items) == 1 else 's'}"


# --------------------------------------------------------------- the worktree


def _since(root: Path, ref: str) -> list[str]:
    """What `ref` and the tree disagree about — committed changes included.

    Plain `git diff <ref>` compares the WORKING TREE against the ref, so this
    covers a commit that has already happened and anything still lying around
    on top of it, which is exactly the pair 5a3f1e9 got wrong.
    """
    done = subprocess.run(
        ["git", "-C", str(root), "diff", "--name-only", "-z", ref],
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        print(done.stderr.strip(), file=sys.stderr)
        return []
    return sorted({p for p in done.stdout.split("\0") if p})


# ----------------------------------------------------------------------- CLI


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="verify", description=__doc__.split("\n")[0]
    )
    ap.add_argument("--root", default=None, help="the repo (default: this file's)")
    ap.add_argument(
        "--since",
        metavar="REF",
        default=None,
        help="plan from `git diff REF` instead of the uncommitted tree",
    )
    ap.add_argument(
        "--list",
        action="store_true",
        dest="list_only",
        help="print the plan and run nothing",
    )
    ap.add_argument(
        "--baseline",
        action="store_true",
        help="on a red run, re-run the failed gates at HEAD in a throwaway "
             "worktree and say which failures are INHERITED (exit 3) rather "
             "than yours (exit 1)",
    )
    ap.add_argument("paths", nargs="*", help="extra paths to treat as changed")
    args = ap.parse_args(argv)

    root = (
        Path(args.root).resolve()
        if args.root
        else Path(__file__).resolve().parents[1]
    )
    if not (root / "services").is_dir():
        print(f"verify: {root} does not look like this repo", file=sys.stderr)
        return 2

    paths = sorted(
        {
            *args.paths,
            *(_since(root, args.since) if args.since else dependents.changed(root)),
        }
    )
    if not paths:
        # An empty plan is not a pass. The gate runs BEFORE the commit, so
        # being asked about a clean tree means it was asked after — which is
        # 5a3f1e9 exactly, and exiting 0 here would hand that iteration the
        # word it wanted.
        print(
            "verify: nothing has changed, so there is nothing to verify — and a\n"
            "clean tree is not a green verdict. If you have already committed, ask\n"
            "about the commit: `bash ops/ralph/verify.sh --since HEAD~1`."
        )
        return 2

    steps = plan(root, paths)
    skips = skipped(root, paths)
    if args.list_only:
        print(f"verify: {_n(steps, 'gate')} would run over {_n(paths, 'path')}:")
        for step in steps:
            print(f"  {step.command}")
        for line in ([""] + _skips(skips) if skips else []):
            print(line)
        if args.baseline:
            print(
                f"\nverify: --baseline would then re-run whichever of those "
                f"{_n(steps, 'gate')} went red, at {_head_sha(root)}, in a "
                f"throwaway worktree."
            )
        return 0

    # The logs exist only for `--baseline`, which needs the TEXT of a failure
    # to tell it from HEAD's. Kept in `$TMPDIR` and dropped on the way out: a
    # gate's output under `root` would be a changed path in the next run's plan.
    with contextlib.ExitStack() as stack:
        logs = (
            Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="verify-log-")))
            if args.baseline
            else None
        )
        results = run(root, steps, logs=logs)
        base = baseline(root, results, logs=logs) if args.baseline else None
        for line in report(results, paths, skips, base):
            print(line)

    if all(r.ok for r in results):
        return 0
    if base is not None and base.verdicts and not base.fatal and len(
        base.verdicts
    ) == len([r for r in results if not r.ok]):
        return EXIT_INHERITED
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
