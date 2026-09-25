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

WHAT THIS IS NOT. It is not the whole verify gate. `nixos-rebuild build
--flake .#ares` is, and so is `nix build .#jarvisd`, and `ops/ralph/nixtest.sh`
reads `modules/` in a way nothing here can derive (see PLAN B72). Those are
named in PROMPT.md and run beside this.

AND IT IS ABOUT THE TREE. `git status`, not the index: the failure in 5a3f1e9
was a green working tree whose commit took 31 of its 33 files, and no verdict
computed before a commit can see what that commit will contain. So the verdict
prints the paths it covers, and `--since <ref>` exists to ask the question
again about what a commit actually took.
"""

from __future__ import annotations

import argparse
import dataclasses
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Iterable, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dependents  # noqa: E402

CARGOTEST = "bash ops/ralph/cargotest.sh"


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

    @property
    def ok(self) -> bool:
        return self.status == 0


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
    """
    out: dict[str, list[str]] = {}
    for crate in crates(root):
        under = f"services/{crate}"
        hit = [
            p
            for p in sorted({rel for g in paths for rel in _rels(root, g)})
            if p == under or p.startswith(under + "/")
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


def _spawn(root: Path, command: str) -> int:
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
    """
    try:
        return subprocess.run(
            ["bash", "-c", command],
            cwd=str(root),
            env={**os.environ, "RALPH_GATE": "1"},
        ).returncode
    except OSError as exc:  # no bash, no cwd, nothing left to run with
        print(f"verify: could not start `{command}`: {exc}", flush=True)
        return 127


def run(
    root: Path,
    steps: Sequence[Step],
    *,
    spawn: Callable[[Path, str], int] = _spawn,
    clock: Callable[[], float] = time.monotonic,
) -> list[Result]:
    """Every step, in order, all of them, whatever the earlier ones did.

    Fail-fast is the wrong trade for a gate whose entire subject is the OTHER
    red suite you did not know about: stopping at the first failure hands back
    the partial picture this exists to replace, and costs a second full run —
    minutes — to learn the rest.
    """
    results: list[Result] = []
    for i, step in enumerate(steps, 1):
        print(f"\n── [{i}/{len(steps)}] {step.command}", flush=True)
        start = clock()
        status = spawn(root, step.command)
        took = clock() - start
        word = "ok" if status == 0 else f"FAILED (exit {status})"
        print(f"── [{i}/{len(steps)}] {word}  {took:.1f} s", flush=True)
        results.append(Result(step=step, status=status, seconds=took))
    return results


# ----------------------------------------------------------------- the report


def report(results: Sequence[Result], paths: Sequence[str]) -> list[str]:
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
        if bad:
            lines += ["verify: RED. Do not commit.", ""]
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
    if args.list_only:
        print(f"verify: {_n(steps, 'gate')} would run over {_n(paths, 'path')}:")
        for step in steps:
            print(f"  {step.command}")
        return 0

    results = run(root, steps)
    for line in report(results, paths):
        print(line)
    return 1 if any(not r.ok for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
