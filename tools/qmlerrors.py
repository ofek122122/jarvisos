#!/usr/bin/env python3
"""Refuse a shot run whose QML threw, however green the totals are (PLAN D36).

D34's second fault — a workspaces row composed from the PREVIOUS desk's plan
over THIS desk's array — announced itself exactly once, as

    QWARN  : qmltestrunner::BarSettle::test_the_desk_can_empty_and_come_back()
             file:///tmp/tmp.XXXX/Workspaces.qml:113: TypeError: Value is
             undefined and could not be converted to an object

in the middle of a run that ended `8 passed, 0 failed` and wrote eleven
correct PNGs. That is the shape of the failure this file exists for: a QML
handler that throws keeps whatever the property already had and recovers on
the next evaluation, so the surface stays plausible, the contact sheet stays
byte-identical, every assertion still holds — and the single warning line is
the only evidence there ever was. All three harnesses piped the runner's
output straight through to a terminal nobody reads unless something else has
already gone wrong.

WHY IT IS NOT "FAIL ON ANY WARNING", which is the cheap version. `console.warn`
is a legitimate voice in this repo: `NiriModel` uses it for a line of `niri msg
--json event-stream` it REFUSES to parse, which is a service being honest, and
three drivers narrate their measurements through `console.log`. A gate that
refused those would be a gate that rewards silence.

So the rule is about a THROW, and the discriminator is the shape the engine
prints rather than the words in the message. QtTest writes console output as

    QDEBUG : qmltestrunner::Suite::test_x() qml: the arrival, sampled: 0.86/0

— the `qml:` prefix, no source location — and an error the engine caught as

    QWARN  : qmltestrunner::Suite::test_x() file:///s/T.qml:7: TypeError: …

— a location, and one of ECMAScript's seven error names. A warning whose text
merely mentions `TypeError` is a voice; a line the engine attributed to a file
and a line number is a fault.

WHAT IT CANNOT SEE, measured rather than assumed. qmltestrunner prints nothing
that is logged while no test function is running: a `console.warn` in
`Component.onCompleted` and every error thrown by a binding evaluated as the
scene is built are both dropped by QtTest's own message handler, before any
scan of the output could reach them. (Probed against Qt 6.11.1: a handler that
reads a property of `undefined` prints the line above; the identical fault in a
declarative binding prints nothing at all, and the property silently keeps its
default.) What lands in the output is what the engine reports while a test body
runs — which is where the drivers do all of their work, and where D34's
TypeError was. The other half is PLAN D38.
"""

from __future__ import annotations

import argparse
import dataclasses
import re
import sys
from pathlib import Path

# ECMAScript's error constructors, which are every name the engine can put in
# front of the colon. Listed rather than pattern-matched on `…Error:` so that
# the rule is a rule and not a guess about what a message might contain.
ERROR_NAMES = (
    "Error",
    "EvalError",
    "RangeError",
    "ReferenceError",
    "SyntaxError",
    "TypeError",
    "URIError",
)

# `QWARN  : qmltestrunner::Suite::test_x() ` — QtTest's own prefix, and the
# test body that was running when the message was logged. The type name is
# optional because a message logged by the runner itself carries no test.
PREFIX = re.compile(
    r"^Q(?:DEBUG|INFO|WARN|CRITICAL|FATAL|SYSTEM)\s*:\s*"
    r"(?:\w+::(?P<test>[\w:]+?)\(\)\s*)?"
)

# `file:///stage/core/NotifyModel.qml:113: TypeError: Cannot read …` — a
# location the engine attributed the throw to, then the name, then the text.
# The column is optional: the engine prints it for some errors and not others.
THROW = re.compile(
    r"^(?P<where>\S+:\d+(?::\d+)?): "
    r"(?P<error>" + "|".join(ERROR_NAMES) + r"): "
    r"(?P<message>.*)$"
)

# What `console.log`/`warn`/`error` output looks like once the prefix is off.
# Everything after it is a string this repo's own QML chose to say.
CONSOLE = "qml: "

TOTALS = re.compile(
    r"^Totals: (?P<totals>\d+ passed, \d+ failed, \d+ skipped, \d+ blacklisted)"
)


@dataclasses.dataclass(frozen=True)
class Throw:
    """One error the engine caught, as the runner reported it."""

    where: str
    error: str
    message: str
    test: str

    def __str__(self) -> str:
        where = f"{self.where}: {self.error}: {self.message}"
        return f"{where}\n    in {self.test}()" if self.test else where


def scan(text: str, *, stage: str | None = None) -> list[Throw]:
    """Every thrown error in a runner's output, in the order it threw.

    `stage` is the temporary directory the harness assembled, if it says: the
    paths the engine prints are `file:///tmp/tmp.XXXX/…`, a prefix that is
    different every run and names nothing a reader can open. Relative to the
    stage they are `core/NotifyModel.qml`, which is a path in this repository.
    """
    out: list[Throw] = []
    for line in text.splitlines():
        prefix = PREFIX.match(line)
        if not prefix:
            continue
        rest = line[prefix.end() :]
        if rest.startswith(CONSOLE):
            continue
        throw = THROW.match(rest)
        if not throw:
            continue
        out.append(
            Throw(
                where=_relative(throw.group("where"), stage),
                error=throw.group("error"),
                message=throw.group("message"),
                test=prefix.group("test") or "",
            )
        )
    return out


def _relative(where: str, stage: str | None) -> str:
    """`where` as the stage's own path, when it is inside the stage."""
    if not stage:
        return where
    for prefix in (f"file://{stage}/", f"{stage}/"):
        if where.startswith(prefix):
            return where[len(prefix) :]
    return where


def collapse(throws: list[Throw]) -> list[tuple[Throw, int]]:
    """The same throw, once, with how many times it threw.

    One handler in one delegate throws once per plate the scene builds, and
    the first real run of this gate printed fourteen identical lines for one
    fault. The COUNT is worth keeping — a throw per delegate and a throw once
    are different bugs — but fourteen copies of one sentence is a report that
    buries the second fault under the first. First appearance wins the order.
    """
    out: list[tuple[Throw, int]] = []
    seen: dict[Throw, int] = {}
    for throw in throws:
        if throw in seen:
            out[seen[throw]] = (throw, out[seen[throw]][1] + 1)
            continue
        seen[throw] = len(out)
        out.append((throw, 1))
    return out


def totals(text: str) -> str | None:
    """The runner's own verdict, so the refusal can carry the contradiction."""
    for line in text.splitlines():
        found = TOTALS.match(line)
        if found:
            return found.group("totals")
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("log", type=Path, help="the runner's captured output")
    ap.add_argument(
        "--stage",
        default=None,
        help="the temporary directory the harness rendered from, so the "
        "report names files the way this repository does",
    )
    ap.add_argument(
        "--rerun",
        default="the harness",
        help="the command that would run this gate again, named in the report",
    )
    args = ap.parse_args(argv)

    try:
        text = args.log.read_text("utf-8", errors="replace")
    except OSError as exc:
        # Not a pass. This runs after the runner, inside a script under
        # `set -e`, so a log that is not there means something went wrong
        # ahead of it — and a scanner that read nothing and said "clean" is
        # the exact silence it was written to remove.
        print(f"qmlerrors: cannot read {args.log}: {exc}", file=sys.stderr)
        return 2

    threw = scan(text, stage=args.stage)
    lines = len(text.splitlines())
    if not threw:
        print(f"qmlerrors: nothing threw in {lines} lines of runner output")
        return 0

    verdict = totals(text)
    said = f" — the runner said {verdict}" if verdict else ""
    faults = len(collapse(threw))
    print(
        f"qmlerrors: {faults} thrown error(s) in this run{said}"
        + (f" ({len(threw)} lines)" if len(threw) != faults else "")
        + ":"
    )
    print()
    for throw, times in collapse(threw):
        print(f"  {throw}" + (f"\n    {times} times" if times > 1 else ""))
    print()
    print(
        "A QML binding or handler that throws keeps the value it already had "
        "and\nrecovers on the next evaluation — so the surface stays "
        "plausible, the shots\nstay identical and every assertion still "
        "holds. These lines are the only\nevidence. Fix them and re-run "
        f"`{args.rerun}`.\n\nWhatever this run rendered was drawn by a scene "
        "that threw: do not commit it."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
