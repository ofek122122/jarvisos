"""harness/session.py — the recorded-session file format, in one place.

A session file is JSONL: line 1 is the session header required by
schemas/README.md, every line after it is one envelope frame, verbatim.
`record.py` writes them from a live bus, `replay.py` plays them back, and
`harness/fixtures/sessions/` commits a few so perception behaviour can be
tested on a machine with no model weights and no microphone.

That last use is why this module exists. A committed fixture is only worth
having while it is still LEGAL: the moment a schema moves under it, every
test built on it keeps passing while asserting yesterday's law. So the
format has one reader, and the reader can be asked `problems()`.

What it checks a session against is the GENERATED bindings
(`jarvis_bus.schema`, compiled from `schemas/*.json` by tools/gen_bindings.py
with a CI drift gate) — never a hand-copy of the schema files here. The
copy is the thing that rots; if this module had its own list of envelope
keys, a `v2` envelope would leave two truths in the repo and no way to tell
which one a fixture was recorded against.

Two rules about what is NOT a problem, both the same rule as `jv act-log`:

  · a topic these bindings do not know is accepted as-is. Adding a topic is
    an ordinary reviewed commit (schemas/README.md), and an old harness
    refusing to read a recording of a newer topic would be refusing to show
    what it merely does not recognise.
  · a `seq` gap is accepted. Gaps are jarvisd's slow-consumer policy
    working as designed — that is what `seq` is for.
"""

from __future__ import annotations

import dataclasses
import datetime
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "pylib"))
from jarvis_bus import mono_now, schema  # noqa: E402

# schemas/README.md, "Harness session header". Three keys, no more: the
# header exists to date monotonic `ts` values across a reboot, and a key
# nobody agreed on is a key no reader can rely on.
HEADER_KEYS = ("boot_id", "wall_time_utc", "monotonic_now")

# From the generated Envelope dataclass, so this tracks schemas/envelope.json.
ENVELOPE_KEYS = tuple(f.name for f in dataclasses.fields(schema.Envelope))

# `boot_id` for a session whose `ts` is an audio SAMPLE clock rather than
# this machine's CLOCK_MONOTONIC — see harness/fixtures/sessions/README.md.
# A sentinel and not a UUID on purpose: such a session cannot be lined up
# against a live recording, and saying so in the field that exists to prove
# it can is better than borrowing a real boot_id that would.
SAMPLE_CLOCK = "sample-clock"


def boot_id() -> str:
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return "dev-no-boot-id"


def live_header() -> Dict[str, Any]:
    """The anchor for a session recorded off a live bus: this boot, the
    wall clock now, and the monotonic reading at the same instant. Wall
    time of any frame = wall_time_utc + (frame.ts - monotonic_now), which
    holds only because boot_id proves the same boot."""
    return {
        "boot_id": boot_id(),
        "wall_time_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "monotonic_now": mono_now(),
    }


def sample_clock_header() -> Dict[str, Any]:
    """The anchor for a session derived from a fixture WAV rather than a
    live bus: `ts` is the audio's own sample clock, zero at the first
    sample, so there is no boot to name and `wall_time_utc` dates the
    RECORDING rather than the room. Nothing computes with it."""
    return {
        "boot_id": SAMPLE_CLOCK,
        "wall_time_utc": datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "monotonic_now": 0.0,
    }


class SessionError(ValueError):
    """A session file that cannot be read, or is not legal.

    ValueError because replay.py's callers have caught that since the
    harness existed.
    """


@dataclasses.dataclass(frozen=True)
class Session:
    header: Dict[str, Any]
    frames: List[Dict[str, Any]]
    path: Optional[Path] = None


def _topic_types() -> Dict[str, type]:
    """topic -> generated dataclass, discovered rather than listed."""
    out: Dict[str, type] = {}
    for name in dir(schema):
        obj = getattr(schema, name)
        if dataclasses.is_dataclass(obj) and isinstance(getattr(obj, "TOPIC", None), str):
            out[obj.TOPIC] = obj
    return out


def load(path: Path) -> Session:
    path = Path(path)
    lines: List[Any] = []
    with path.open(encoding="utf-8") as fh:
        for n, raw in enumerate(fh, start=1):
            if not raw.strip():
                continue
            try:
                lines.append(json.loads(raw))
            except ValueError as e:
                raise SessionError(f"{path}: line {n}: {e}") from e
    if not lines or not isinstance(lines[0], dict) or "boot_id" not in lines[0]:
        raise SessionError(f"{path}: missing session header (schemas/README.md)")
    return Session(header=lines[0], frames=lines[1:], path=path)


def dump(header: Dict[str, Any], frames: Iterable[Dict[str, Any]], out: TextIO) -> int:
    """Header then frames, one JSON object per line. Returns frames written.

    allow_nan=False: a NaN `ts` is not JSON, and a file that only some
    parsers accept is not a fixture.
    """
    def line(obj: Any) -> str:
        return json.dumps(obj, allow_nan=False, sort_keys=False)

    out.write(line(header) + "\n")
    n = 0
    for frame in frames:
        out.write(line(frame) + "\n")
        n += 1
    out.flush()
    return n


def _number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _whole(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _header_problems(header: Dict[str, Any]) -> List[str]:
    if set(header) != set(HEADER_KEYS):
        missing = sorted(set(HEADER_KEYS) - set(header))
        extra = sorted(set(header) - set(HEADER_KEYS))
        return [f"header: keys {sorted(header)} (missing {missing}, extra {extra})"]
    out = []
    for k in ("boot_id", "wall_time_utc"):
        if not isinstance(header[k], str) or not header[k]:
            out.append(f"header: {k} must be a non-empty string")
    if not _number(header["monotonic_now"]):
        out.append("header: monotonic_now must be a finite number")
    return out


def _envelope_problems(where: str, frame: Dict[str, Any]) -> List[str]:
    out = []
    missing = sorted(set(ENVELOPE_KEYS) - set(frame))
    extra = sorted(set(frame) - set(ENVELOPE_KEYS))
    if missing:
        out.append(f"{where}: missing envelope keys {missing}")
    if extra:
        out.append(f"{where}: keys the envelope does not have: {extra}")
    if missing:
        return out  # the rest would only restate it

    topic = frame["topic"]
    if not isinstance(topic, str) or "." not in topic:
        out.append(f"{where}: topic {topic!r} is not a dotted topic")
    elif "*" in topic:
        out.append(f"{where}: topic {topic!r} is a subscription pattern, not a topic")
    if not isinstance(frame["src"], str) or not frame["src"]:
        out.append(f"{where}: src must be a non-empty string")
    if not _number(frame["ts"]):
        out.append(f"{where}: ts must be a finite number")
    if not _whole(frame["seq"]) or frame["seq"] < 0:
        out.append(f"{where}: seq must be a non-negative integer")
    if not _number(frame["conf"]) or not 0.0 <= frame["conf"] <= 1.0:
        out.append(f"{where}: conf must be a number in [0, 1]")
    if not _whole(frame["v"]) or frame["v"] < 1:
        out.append(f"{where}: v must be an integer >= 1")
    if not isinstance(frame["body"], dict):
        out.append(f"{where}: body must be an object")
    return out


def _body_problems(where: str, frame: Dict[str, Any], cls: type) -> List[str]:
    out = []
    if frame["v"] != cls.V:
        out.append(f"{where}: {frame['topic']} recorded at v={frame['v']}, "
                   f"schemas are at v={cls.V}")
    body = frame["body"]
    if not isinstance(body, dict):
        return out
    fields = {f.name for f in dataclasses.fields(cls)}
    required = fields - set(cls._optional)
    for name in sorted(required - set(body)):
        out.append(f"{where}: {frame['topic']} body is missing {name!r}")
    for name in sorted(set(body) - fields):
        out.append(f"{where}: {frame['topic']} body has {name!r}, "
                   f"which its schema does not")
    return out


def problems(sess: Session) -> List[str]:
    """Every way this session breaks the bus contract, one line each.

    Returns them all rather than raising on the first: a fixture is fixed
    by regenerating it, and you want to see everything that moved.
    """
    out = _header_problems(sess.header)
    types = _topic_types()
    last: Dict[tuple, Dict[str, Any]] = {}
    for i, frame in enumerate(sess.frames, start=1):
        where = f"frame {i}"
        if not isinstance(frame, dict):
            out.append(f"{where}: not an object")
            continue
        env = _envelope_problems(where, frame)
        out += env
        if env:
            continue
        cls = types.get(frame["topic"])
        if cls is not None:
            out += _body_problems(where, frame, cls)
        # A publisher's own frames on one topic ride one monotonic clock and
        # one counter. Two publishers CAN land out of order — they are two
        # clocks read at two moments — so this is deliberately per (src, topic).
        key = (frame["src"], frame["topic"])
        prev = last.get(key)
        if prev is not None:
            if frame["ts"] < prev["ts"]:
                out.append(f"{where}: ts {frame['ts']} is before {prev['ts']} "
                           f"from the same {key}")
            if frame["seq"] <= prev["seq"]:
                out.append(f"{where}: seq {frame['seq']} does not follow "
                           f"{prev['seq']} from the same {key}")
        last[key] = frame
    return out


def check(sess: Session) -> None:
    """Raise with every problem at once, or return quietly."""
    found = problems(sess)
    if found:
        where = f"{sess.path}: " if sess.path else ""
        raise SessionError(where + "; ".join(found))
