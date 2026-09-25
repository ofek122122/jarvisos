"""The bounded no-wake listening window (schemas/dialog.listen.json).

Jarvis wants the wake word every time. `dialog.listen` is the one
approved exception (DECISIONS-approved, taken 2026-08-22): jv-act asks
for it when it has stopped in front of something destructive and needs
your answer, jv-brain when it is asking an onboarding or follow-up
question. For the seconds they ask for, jv-ears gates utterances without
a wake — and for every other second of the day it does not.

Ears stays DUMB, and that is the shape of this whole file. It does not
learn what "yes" means, it does not decide that the answer has arrived,
and it does not close the window early because an utterance went past.
The requester interprets transcripts (that is the approved split, and it
is why intent interpretation stays out of a perception service); a window
that shut itself after the user's first "um" would be ears making exactly
that interpretation, badly, at the moment it costs an answer. **The only
thing that closes this window is time.**

Which puts the entire safety argument on time, so time is enforced here
rather than trusted:

  · every request is bounded by the frozen schema's own `maximum`, and a
    test reads the schema so this file cannot drift from it;
  · anything this code cannot read confidently is REFUSED rather than
    guessed at. An unparsable, mis-versioned or hedged frame must leave
    the microphone exactly as wake-gated as it found it — every default
    in here points at "closed", because the failure that matters is a
    machine that listens to a room nobody addressed;
  · the clock is the SAMPLE clock, like every other decision in this
    service: the same audio and the same frames produce the same events,
    which is what makes a replayed fixture evidence.

Threading. `request()` is called on the bus thread and `advance()` on the
pipeline thread, once per chunk. The hand-off is a deque because
`append`/`popleft` are atomic under the GIL and a read-then-clear
attribute is not — a request lost in that race is a microphone that
stayed shut while a service was waiting on it.
"""

from __future__ import annotations

import collections
import math
from typing import Optional

# Mirrored from schemas/dialog.listen.json. tests/test_dialog_listen.py
# reads the schema and fails if either drifts — the schema is the law
# (invariant 2) and these are a copy of it, not a second opinion.
MAX_WINDOW_S = 60.0
REASONS = frozenset({"confirm", "onboarding", "followup"})
BODY_V = 1


def _is_number(x: object) -> bool:
    """A real number, and not a bool — `True` is an `int` in Python, and
    `True * 16_000` is a perfectly good-looking window length."""
    return isinstance(x, (int, float)) and not isinstance(x, bool)


class ListenWindow:
    """One no-wake window: closed unless a service asked, and for how long."""

    def __init__(self, sample_rate: int) -> None:
        self._rate = sample_rate
        self._requests: collections.deque = collections.deque()
        self._until: Optional[int] = None
        self._reason: Optional[str] = None

    # ----------------------------------------------------------- bus thread

    def request(self, body: object, conf: object = 1.0, v: object = BODY_V) -> bool:
        """Take a `dialog.listen` frame. True if it will open a window.

        Envelope AND body: `conf` and `v` are refusal grounds, so the
        caller forwards the whole frame rather than just its body.
        """
        if not _is_number(v) or v != BODY_V:
            # A v2 body means whatever v2 says it means. Refusing is the
            # only reading of an unknown version that cannot be wrong
            # about a microphone.
            return False
        if not _is_number(conf) or conf < 1.0:
            # `dialog.listen` is a command topic: the schema says conf is
            # 1.0. A producer that is not certain it wants the microphone
            # open does not get it opened — invariant 4, pointed the one
            # way it can be pointed here.
            return False
        if not isinstance(body, dict):
            return False
        listen_id = body.get("listen_id")
        if not isinstance(listen_id, str) or not listen_id:
            return False
        reason = body.get("reason")
        if reason not in REASONS:
            # The audited field. A purpose this ears cannot name is one it
            # cannot audit, and the schema says the HUD will show it.
            return False
        window_s = body.get("window_s")
        if not _is_number(window_s) or not math.isfinite(window_s):
            return False
        if window_s <= 0 or window_s > MAX_WINDOW_S:
            return False
        self._requests.append((float(window_s), reason))
        return True

    # ------------------------------------------------------ pipeline thread

    def advance(self, pos: int) -> bool:
        """Move to sample `pos` and answer: is the window open there?

        Called once per chunk, before anything reads `open` — a window
        whose deadline passed two chunks ago is not a window.
        """
        while self._requests:
            window_s, reason = self._requests.popleft()
            until = pos + int(round(window_s * self._rate))
            # Overlapping requests EXTEND and never shorten: a 5 s
            # follow-up must not cut short the 15 s jv-act is waiting on,
            # because the mic closing early loses an answer the user gave
            # in time. The reason on show is the furthest window's.
            if self._until is None or until > self._until:
                self._until = until
                self._reason = reason
        if self._until is not None and pos >= self._until:
            self._until = None
            self._reason = None
        return self._until is not None

    @property
    def open(self) -> bool:
        """As of the last `advance`. Never a wall-clock answer."""
        return self._until is not None

    @property
    def reason(self) -> Optional[str]:
        """Why the open window was asked for, or None while it is shut."""
        return self._reason
