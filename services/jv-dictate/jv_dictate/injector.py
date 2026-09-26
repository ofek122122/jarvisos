"""Where a transcribed sentence goes. Invariant 3 is explicit: only jv-act
injects input, and no injector exists there yet (docs/optimization-backlog.md
R11 proposes `input.type_text`, human-review-only, PLAN F5 — still `[B]`).

So everything upstream of the keystrokes (services/jv-dictate/jv_dictate/
main.py) is built and tested against a `Sink`, and today's default is
`LogSink` — it types nothing, anywhere, ever. Swapping in the real jv-act
tool once R11 is reviewed is a one-call change: replace the sink main.py
constructs, nothing else in this service moves.
"""

from __future__ import annotations

from typing import Protocol


class Sink(Protocol):
    def type_text(self, text: str) -> None: ...


class FakeSink:
    """What the tests use: a Sink that remembers what it was asked to type
    instead of typing it anywhere."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def type_text(self, text: str) -> None:
        self.calls.append(text)


class LogSink:
    """The production default until PLAN F5's jv-act tool exists. Prints
    rather than types — a human reading the journal can see dictation is
    working end to end without this service ever touching a keyboard."""

    def type_text(self, text: str) -> None:
        print(f"[jv-dictate] would type: {text!r}", flush=True)
