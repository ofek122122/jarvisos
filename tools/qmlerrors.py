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

WHAT THE RUNNER CANNOT SAY, measured rather than assumed. qmltestrunner prints
nothing that is logged while no test function is running: a `console.warn` in
`Component.onCompleted` and every error thrown by a binding evaluated as the
scene is built are both dropped by QtTest's own message handler, before any
scan of the output could reach them. (Probed against Qt 6.11.1: a handler that
reads a property of `undefined` prints the line above; the identical fault in a
declarative binding prints nothing at all, and the property silently keeps its
default.) What lands in the output is what the engine reports while a test body
runs — which is where the drivers do all of their work, and where D34's
TypeError was.

It is narrower still than that, and the narrowing is alphabetical: a driver
whose scene is built BEFORE the run begins is silent, and every later one is
not. Two identical files in one directory, and only the second is heard —

    PASS   : qmltestrunner::Probea::cleanupTestCase()
    QWARN  : qmltestrunner::UnknownTestFunc() qml: warn from b onCompleted
    QWARN  : qmltestrunner::UnknownTestFunc() …/tst_b.qml:7: TypeError: …

— so which surface of a harness this rule covers was decided by a filename.

SO THIS FILE READS TWO ENGINES (PLAN D38). The other one is plain `qml`, which
installs no handler of its own and writes the engine's own line bare, with no
`QWARN :` in front of it; `tools/qmlprobe/Probe.qml` loads the same staged
scene under it, and every harness hands what it printed to this. Both outputs
come here, because a throw is a throw and the discriminator was never the
prefix.

AND NOW A THIRD (PLAN D39), which is the one that draws the real HUD.
`ops/ralph/hudscreens.sh` runs the REAL `.#jv-hud` — quickshell — through a
real compositor, and until now nothing had ever read a line of what it said.
D38 predicted the obstacle would be `QT_FORCE_STDERR_LOGGING`, because this Qt
is built with the journald backend and a Qt program whose stderr is not a
terminal prints nothing. MEASURED, and that is not what happens: quickshell
installs a message handler of its OWN, so its output reaches a redirected file
whatever Qt would have done with it. What it writes there is a third shape,
and both halves of the D36 rule are different in it:

     WARN scene: @core/BusModel.qml[113:-1]: TypeError: Value is undefined
    DEBUG qml: the arrival, sampled

— a level and a CATEGORY instead of `QWARN :`, a location written
`@path[line:column]` relative to the shell's own root rather than
`file:///…:line:`, and a column of -1 when the engine did not have one. The
category is the cleaner half of the discriminator this file already had:
quickshell logs `console.log`/`warn`/`error` under `qml` and the engine's own
errors under `scene`, so the voice and the fault are separated at the source.
The location and the error name are still required, because the rule is about
the shape the engine prints, and a category is a claim someone else makes
about it.

ONE THING THE HARNESS MUST DO, and it is not optional: quickshell colours its
output with ANSI escapes whether or not anything is watching, so a log written
to a file carries `\x1b[33m` in front of every level. `NO_COLOR=1` turns it
off, and without it every line here reads as unprefixed noise.
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
#
# THE WHOLE PREFIX IS OPTIONAL, because there are two engines (PLAN D38).
# QtTest writes it; plain `qml`, which the probe next door runs the same
# staged scene under, installs no handler and writes what the engine wrote:
#
#     file:///tmp/tmp.XXXX/Workspaces.qml:113: TypeError: Value is undefined
#
# with nothing in front of it. Same fault, same shape, one rule.
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

# `  WARN scene: ` — quickshell's own handler (PLAN D39), which is the third
# engine and the only one that ever draws the real HUD. A level padded to six
# columns, then an optional CATEGORY, then the colon. Quickshell logs its own
# internal messages with no category at all (`  INFO: Configuration Loaded`),
# every `console.*` under `qml`, and the QML engine's own errors under `scene`.
#
# The levels are quickshell's four and not Qt's six: DEBUG, INFO, WARN, ERROR.
# Recorded from quickshell 0.3.0 rather than read off its source, because what
# this has to match is what it prints.
QS_PREFIX = re.compile(
    r"^\s*(?:DEBUG|INFO|WARN|ERROR)\s*(?P<category>[\w.]+)?:\s*"
)

# The category quickshell puts every `console.log`/`warn`/`error` under. It is
# the same word the other two engines use as a line prefix, for the same
# reason, and it is skipped here for the same reason: a voice is not a fault.
QS_CONSOLE = "qml"

# `@core/BusModel.qml[113:-1]: TypeError: Value is undefined` — the same fault
# in quickshell's notation. The path is relative to the shell's own root (the
# directory holding `shell.qml`), and the column is -1 when the engine did not
# have one, which is most of the time.
QS_THROW = re.compile(
    r"^@(?P<where>\S+?)\[(?P<line>\d+):(?P<column>-?\d+)\]: "
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


def scan(
    text: str, *, stage: str | None = None, prefix: str | None = None
) -> list[Throw]:
    """Every thrown error in a runner's output, in the order it threw.

    `stage` is the temporary directory the harness assembled, if it says: the
    paths the engine prints are `file:///tmp/tmp.XXXX/…`, a prefix that is
    different every run and names nothing a reader can open. Relative to the
    stage they are `core/NotifyModel.qml`, which is a path in this repository.

    `prefix` is the other half of the same courtesy, for the third engine
    (PLAN D39): quickshell prints `@core/BusModel.qml`, already relative — but
    relative to the shell's own root, which is a store path. Told that root's
    place in this repository, the report names `shell/jv-hud/core/BusModel.qml`
    and a reader can open it.
    """
    out: list[Throw] = []
    for line in text.splitlines():
        found = _uncover(line)
        if found is None:
            continue
        rest, test = found
        throw = THROW.match(rest)
        where = _relative(throw.group("where"), stage) if throw else None
        if throw is None:
            throw = QS_THROW.match(rest)
            if throw is None:
                continue
            where = _rooted(throw, prefix)
        out.append(
            Throw(
                where=where,
                error=throw.group("error"),
                message=throw.group("message"),
                test=test,
            )
        )
    return out


def _uncover(line: str) -> tuple[str, str] | None:
    """One logged line without whichever engine's prefix it carries, and the
    test that was running, or None when the line is a VOICE rather than a
    report the engine made.

    Three engines, three prefixes, and one of them is the empty string: plain
    `qml` installs no handler and writes the engine's line bare, which is why
    a line nothing matches is still handed on rather than dropped.
    """
    runner = PREFIX.match(line)
    if runner:
        rest = line[runner.end() :]
        return None if rest.startswith(CONSOLE) else (rest, runner.group("test") or "")
    shell = QS_PREFIX.match(line)
    if shell:
        # Quickshell says which channel a line came from, so the voice is
        # separated from the fault before any of it is parsed.
        if shell.group("category") == QS_CONSOLE:
            return None
        return (line[shell.end() :], "")
    return None if line.startswith(CONSOLE) else (line, "")


def _relative(where: str, stage: str | None) -> str:
    """`where` as the stage's own path, when it is inside the stage."""
    if not stage:
        return where
    for prefix in (f"file://{stage}/", f"{stage}/"):
        if where.startswith(prefix):
            return where[len(prefix) :]
    return where


def _rooted(throw: "re.Match[str]", prefix: str | None) -> str:
    """Quickshell's `@path[line:column]` as the `path:line` everything else
    here speaks, under the repository directory it is relative to.

    The column is dropped when the engine did not have one (-1), rather than
    printed as a position no file has. An ABSOLUTE path is left alone: it is
    already not relative to the shell's root, so prefixing it would invent a
    place.
    """
    where = throw.group("where")
    column = int(throw.group("column"))
    at = f"{where}:{throw.group('line')}" + (f":{column}" if column >= 0 else "")
    if prefix and not where.startswith("/"):
        return f"{prefix.rstrip('/')}/{at}"
    return at


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
    # MORE THAN ONE, because the third engine does not run once (PLAN D39).
    # `hudscreens.sh` starts a fresh jv-hud per shot and per idle window —
    # twelve of them in a run — and each writes its own log. A scanner that
    # took one would have made the harness choose which surface to believe.
    ap.add_argument(
        "log", type=Path, nargs="+", help="the runner's captured output"
    )
    ap.add_argument(
        "--stage",
        default=None,
        help="the temporary directory the harness rendered from, so the "
        "report names files the way this repository does",
    )
    ap.add_argument(
        "--prefix",
        default=None,
        help="the repository directory quickshell's own relative paths are "
        "under, so the report names files this repository has",
    )
    ap.add_argument(
        "--rerun",
        default="the harness",
        help="the command that would run this gate again, named in the report",
    )
    args = ap.parse_args(argv)

    lines = 0
    faulty: list[tuple[Path, list[Throw], str | None]] = []
    for path in args.log:
        try:
            text = path.read_text("utf-8", errors="replace")
        except OSError as exc:
            # Not a pass. This runs after the runner, inside a script under
            # `set -e`, so a log that is not there means something went wrong
            # ahead of it — and a scanner that read nothing and said "clean"
            # is the exact silence it was written to remove. A glob that
            # matched no file arrives here as its own unexpanded pattern,
            # which is the same answer for the same reason.
            print(f"qmlerrors: cannot read {path}: {exc}", file=sys.stderr)
            return 2
        lines += len(text.splitlines())
        threw = scan(text, stage=args.stage, prefix=args.prefix)
        if threw:
            faulty.append((path, threw, totals(text)))

    across = f" across {len(args.log)} logs" if len(args.log) > 1 else ""
    if not faulty:
        print(f"qmlerrors: nothing threw in {lines} lines of runner output{across}")
        return 0

    total = sum(len(collapse(threw)) for _, threw, _ in faulty)
    print(f"qmlerrors: {total} thrown error(s) in this run{across}:")
    for path, threw, verdict in faulty:
        print()
        said = f" — the runner said {verdict}" if verdict else ""
        faults = len(collapse(threw))
        # The log's own name, only when there is more than one of them: with
        # a single log it is the thing the caller just named on the command
        # line, and repeating it back is noise.
        where = f"{path.name}: " if len(args.log) > 1 else ""
        print(
            f"  {where}{faults} fault(s){said}"
            + (f" ({len(threw)} lines)" if len(threw) != faults else "")
            + ":"
        )
        for throw, times in collapse(threw):
            print(f"    {throw}" + (f"\n      {times} times" if times > 1 else ""))
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
