#!/usr/bin/env python3
"""Refuse a run whose BROKER said something, however the corner read (PLAN D51).

`ops/ralph/shellload.sh` starts two `jarvisd` — one for the frames run and one
for the blind HUD's relink (PLAN D49) — and until this file existed the only
thing that ever opened either log was the failure message D49 quotes it into.
So a broker that came up, accepted the bridge and then went wrong was invisible
here: the run reads as a HUD that ignored its frames, which is the wrong repair
by a whole process. Everything downstream — ten plates, an empty corner, ten
plates again — is a reading of what that broker did, and nothing read the
broker.

`tools/qmlerrors.py` cannot be pointed at it. That file knows three QML
engines' prefixes, and a Rust tracing line is not one of them, so over a
broker's log it reports "nothing threw" whatever the log says — the exact
silence it was itself written to remove.

THE RULE, and it is stricter than "no ERROR lines" on purpose. A broker that is
well writes tracing lines and nothing else, so:

    every line is a tracing line the broker wrote at INFO or below,
    and one of them says it is listening on the socket it was told to bind.

Both halves earn their keep, and the second is the floor under the first: a log
nobody wrote has no ERROR lines in it either, which is how the three staged
harnesses graded themselves clean in D38. `--listening` is what makes this a
census rather than an absence — the broker has to name the path this run gave
it, so a `--bus` that silently did not apply, or a log belonging to some other
run's broker, is a fault here rather than a HUD that would not light.

And REFUSING A LINE IT CANNOT PARSE is what makes the first half cover more
than the two `tracing::error!` sites in `services/jarvisd/src/broker.rs`. What
a Rust process writes when it is NOT well is mostly not tracing at all:

    Error: Permission denied (os error 13)

is what `main` returning `Err` prints (recorded from the flake's own jarvisd,
given a `--bus` under a directory it may not write), and a panic in a spawned
task — which does not end the process, and so would leave the accept loop dead
under a run that goes on waiting — prints a `thread '…' panicked at …` block
that is not a tracing line either. Neither has a level to filter on. So the
rule is about the whole file: anything that is not one of the broker's own
lines is quoted back, and the reader does not have to have predicted its shape.

THE FORMAT is tracing-subscriber's default, recorded from the binary this flake
builds rather than read off its source, because what this has to match is what
it prints:

    2026-09-26T02:20:57.087052Z  INFO jarvisd: jarvisd listening on /…/bus.sock

— an RFC-3339 timestamp, the level right-aligned in five columns, the target
(`jarvisd`, or `jarvisd::broker` for everything the broker itself logs), then
`: ` and the message.

ONE THING THE HARNESS MUST DO, and it is the same line `tools/qmlerrors.py`
needs for the same reason: `NO_COLOR=1`. tracing-subscriber colours its output
whether or not anything is watching, and with colour on the level arrives as
`\x1b[32m INFO\x1b[0m`. The failure direction is the safe one here — a coloured
log parses as no lines at all, so the census fails and the run goes red rather
than green — but it goes red for the wrong reason, and the reason is worth
knowing.
"""

from __future__ import annotations

import argparse
import dataclasses
import re
import sys
from pathlib import Path

# The five levels tracing has, in the order it orders them. Anything at or
# below INFO is a broker narrating itself; WARN and ERROR are it reporting
# that something went wrong, and there is no third category.
LEVELS = ("TRACE", "DEBUG", "INFO", "WARN", "ERROR")
QUIET = ("TRACE", "DEBUG", "INFO")

# `2026-09-26T02:20:57.087052Z  INFO jarvisd: jarvisd listening on /…` — the
# default `tracing_subscriber::fmt()` layout. The level is right-aligned in
# five columns, so `INFO` and `WARN` arrive with a leading space; the target is
# a Rust module path, and the message is everything after the first `: ` that
# follows it.
LINE = re.compile(
    r"^(?P<ts>\d{4}-\d\d-\d\dT[\d:.]+Z)\s+"
    r"(?P<level>" + "|".join(LEVELS) + r")\s+"
    r"(?P<target>[A-Za-z_][\w:]*?): "
    r"(?P<message>.*)$"
)

# What the broker says when it has bound. `services/jarvisd/src/bin/jarvisd.rs`
# logs it once, immediately after `Listener::bind`, with the address it really
# got rather than the one it was asked for — which is what makes it worth
# checking against the path this run handed over.
LISTENING = re.compile(r"^jarvisd listening on (?P<addr>.+)$")


@dataclasses.dataclass(frozen=True)
class Said:
    """One line the broker wrote, as tracing laid it out."""

    level: str
    target: str
    message: str

    def __str__(self) -> str:
        return f"{self.level} {self.target}: {self.message}"


def scan(text: str) -> tuple[list[Said], list[str]]:
    """Every line the broker wrote, split into the ones tracing formatted and
    the ones it did not.

    Blank lines are neither: a process that wrote a trailing newline has not
    said anything, and refusing it would make this gate about whitespace.
    """
    said: list[Said] = []
    other: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        found = LINE.match(line)
        if found is None:
            other.append(line)
            continue
        said.append(
            Said(
                level=found.group("level"),
                target=found.group("target"),
                message=found.group("message"),
            )
        )
    return said, other


def complaints(said: list[Said]) -> list[Said]:
    """The lines the broker wrote to report that something went wrong.

    Spelled as "not one of the quiet levels" rather than as a list of the two
    loud ones, so a level tracing gains is a fault here until somebody decides
    otherwise — which is the direction a gate should fail in.
    """
    return [line for line in said if line.level not in QUIET]


def bound(said: list[Said]) -> list[str]:
    """Every address this broker announced it was listening on.

    A list rather than one value, because a log with two of them is a file two
    brokers wrote into, and that is a different fault from a log with none.
    """
    out = []
    for line in said:
        found = LISTENING.match(line.message)
        if found:
            out.append(found.group("addr"))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # ONE log, unlike `tools/qmlerrors.py`, and the reason is `--listening`:
    # the two brokers in a shellload run bind two different sockets, so a
    # scanner that took both logs would have to be told which address belonged
    # to which — or check neither. The caller loops instead.
    ap.add_argument("log", type=Path, help="the broker's captured output")
    ap.add_argument(
        "--listening",
        required=True,
        help="the socket this broker was told to bind, which it has to say it "
        "got — the census that keeps an empty log from reading clean",
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
        # Not a pass, for `qmlerrors.py`'s reason and one more of its own: this
        # runs after the driver, so a broker log that is not there means the
        # run ended before the act that starts it — and a reader that saw no
        # file and said "clean" would put a green line under that.
        print(
            f"brokerlog: cannot read {args.log}: {exc}\n"
            "  Nothing wrote it, so the run did not reach the act that starts "
            "this broker.\n  Whatever failed above is the reason.",
            file=sys.stderr,
        )
        return 2

    said, other = scan(text)
    loud = complaints(said)
    addrs = bound(said)
    wrong = args.listening not in addrs

    if not loud and not other and not wrong:
        print(
            f"brokerlog: {args.log.name} — the broker bound "
            f"{args.listening} and said nothing else of note "
            f"({len(said)} lines)"
        )
        return 0

    print(f"brokerlog: {args.log.name} is not the log of a broker that was well:")
    if wrong:
        print()
        print(
            f"  it never said it was listening on {args.listening}"
            + (f" — it named {addrs}" if addrs else ", and named nothing")
        )
    if loud:
        print()
        print(f"  {len(loud)} line(s) at a level above INFO:")
        for line in loud:
            print(f"    {line}")
    if other:
        print()
        print(f"  {len(other)} line(s) tracing did not write:")
        for line in other:
            print(f"    {line}")
    print()
    print(
        "The HUD's whole view of this run came through this broker. A corner "
        "that\nlit nothing, or went dark and stayed dark, reads as a shell "
        "that ignored\nits frames — and if the broker was refusing them, that "
        "is the wrong repair\nby a whole process. Read the lines above first, "
        f"then re-run `{args.rerun}`."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
