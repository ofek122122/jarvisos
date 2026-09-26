"""The push-to-talk state machine: raw (keycode, pressed) events in,
"start"/"stop" transitions out. Deliberately dumb, the same way
dialog.ListenWindow (services/jv-ears/jv_ears/dialog.py) is dumb — it does
not know what a sentence is, it does not decide the user is done, and the
only things that end a recording are the key coming back up or the hard
safety cap. That is what makes it testable without a microphone: feed it
keycodes on a fake clock and read off exactly two words.

Threading model mirrors EarsPipeline: `feed()` runs on the evdev listener's
thread (or the event loop, for the async listener in main.py); `expired()`
is polled from wherever owns the clock. There is exactly one PushToTalk per
process, so there is no hand-off to reason about the way dialog.py's
deque is for a multi-writer race.
"""

from __future__ import annotations

import time
from typing import Optional


class PushToTalk:
    # Mirrors dialog.listen's own `window_s <= 60` (schemas/dialog.listen.json):
    # a key that never reports its own release must not become an open mic.
    MAX_RECORDING_S = 60.0

    def __init__(self, trigger_keycode: int, *, clock=time.monotonic) -> None:
        self.trigger_keycode = trigger_keycode
        self._clock = clock
        self._active = False
        self._started_at: Optional[float] = None

    @property
    def active(self) -> bool:
        return self._active

    def feed(self, keycode: int, pressed: bool) -> Optional[str]:
        """One raw key event. Returns "start", "stop", or None.

        Only the trigger key is looked at — everything else on the keyboard
        passes through untouched, because this never owns the keyboard the
        way keyd does; it only watches one code. Autorepeat (a held key
        re-delivering `pressed=True` every ~30ms) must not restart a
        recording that is already running, and a release of a key that was
        never seen going down (this process started mid-press, or a second
        listener raced it) must not stop one that never started.
        """
        if keycode != self.trigger_keycode:
            return None
        if pressed:
            if self._active:
                return None
            self._active = True
            self._started_at = self._clock()
            return "start"
        if not self._active:
            return None
        self._active = False
        self._started_at = None
        return "stop"

    def expired(self) -> bool:
        """Has the hard safety cap been reached? Checked by the caller on
        its own cadence — this class runs no timer of its own, the same
        choice ListenWindow makes for the same reason (a class with no
        writer of its own age has nothing wrong to keep quiet about)."""
        if not self._active or self._started_at is None:
            return False
        return self._clock() - self._started_at >= self.MAX_RECORDING_S

    def force_stop(self) -> None:
        """Called when `expired()` is true, or when the process is shutting
        down with the key still held — either way, this is the caller
        deciding the recording is over, not a "stop" this class detected."""
        self._active = False
        self._started_at = None
