"""The HUD's one-way window onto the bus.

QML cannot open a Unix socket or unpack MessagePack, and the HUD must not
import another service (invariant 1). So this process — and only this
process — holds the socket on the HUD's behalf, subscribes to a small set
of topics, and writes each frame to stdout as one line of JSON. Quickshell
reads those lines with a `SplitParser`. Nothing flows the other way: the
pump is handed a `ReadOnlyBus`, which has no publish method to reach for.

The line protocol is two tagged shapes, one per line, never anything else:

    {"t":"frame","frame":{topic,ts,seq,src,conf,v,body}}
    {"t":"link","up":true}                        subscribed to a live bus
    {"t":"link","up":false,"err":"..."}           not subscribed, and why

`link` is deliberately NOT a bus topic: it describes this pipe, not the
machine, and inventing a topic for it would be writing schema without a
reviewed schema commit (invariant 2). The HUD needs it because invariant
10 forbids showing a sensor state it cannot currently observe — on
`up:false` the HUD drops everything it cached rather than keep drawing the
last thing it heard.

Backpressure: if the HUD stops reading, this process blocks on write and
becomes a slow consumer, so jarvisd drops ITS frames and leaves everyone
else alone (invariant 5 — the HUD can never stall the bus). The gaps show
up as jumps in `seq`, which is exactly what `seq` is for.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Awaitable, Callable, Dict, Iterable, Optional, Sequence, TextIO

from jarvis_bus import BusError

# The topics the HUD can render truthfully today or in the next elements:
# Jarvis's speech state, the wake word firing, voice-activity boundaries,
# service health, and the two ends of a brain turn — which are how the HUD
# knows Jarvis is working rather than idle (PLAN A12). Each one has a frozen
# schema in schemas/ — a test asserts that, so this list cannot drift into
# inventing topics.
#
# brain.request/brain.response are the first topics here whose bodies carry
# conversation TEXT. That stays on this machine like everything else
# (invariant 7): this pipe is one process writing to another on the same
# box, and no element reads those bodies — the HUD uses only the fact that
# a frame exists and when. A future element that wants the words is free to,
# but it should be a deliberate choice rather than a thing that happened.
DEFAULT_TOPICS: Sequence[str] = (
    "speech.state",
    "audio.wake",
    "audio.vad",
    "sys.health",
    "brain.request",
    "brain.response",
)

# Exactly the envelope (schemas/envelope.json). Forwarding the whole thing
# is the point: `conf` and `ts` are how the HUD handles low-confidence and
# late input (invariant 4), and `seq` is how it notices dropped frames.
ENVELOPE_KEYS = ("topic", "ts", "seq", "src", "conf", "v", "body")

FIRST_BACKOFF_S = 0.5
MAX_BACKOFF_S = 8.0


class HudGone(Exception):
    """The HUD closed the pipe. Not an error — our reader went home."""


class ReadOnlyBus:
    """A one-way view of a connected bus client: subscribe, receive, close.

    There is no publish method here, so the pump cannot grow one by
    accident. The HUD observes the machine; it does not act on it — acting
    is `jv-act`'s job alone (invariant 3).
    """

    __slots__ = ("_client",)

    def __init__(self, client: Any) -> None:
        self._client = client

    async def subscribe(self, topics: Iterable[str]) -> None:
        await self._client.subscribe(list(topics))

    async def next_frame(self) -> Optional[Dict[str, Any]]:
        return await self._client.next_frame()

    async def close(self) -> None:
        await self._client.close()


def _dumps(obj: Any) -> str:
    # ensure_ascii escapes every control character and non-ASCII byte, so a
    # transcript containing a newline can never split one message into two
    # lines. allow_nan=False turns a NaN conf into a dropped frame instead
    # of `NaN`, which is not JSON and would throw inside QML's JSON.parse.
    return json.dumps(obj, ensure_ascii=True, allow_nan=False, separators=(",", ":"))


def encode_frame(frame: Any) -> Optional[str]:
    """One envelope -> one line, or None if QML could not parse it.

    A malformed frame is dropped silently rather than crashing the bridge:
    the HUD showing nothing is correct, the HUD dying is not.
    """
    if not isinstance(frame, dict):
        return None
    if not isinstance(frame.get("topic"), str) or not isinstance(frame.get("body"), dict):
        return None
    envelope = {k: frame.get(k) for k in ENVELOPE_KEYS}
    try:
        return _dumps({"t": "frame", "frame": envelope})
    except (TypeError, ValueError):
        return None


def encode_link(up: bool, err: Optional[str] = None) -> str:
    msg: Dict[str, Any] = {"t": "link", "up": bool(up)}
    if not up and err:
        msg["err"] = err
    return _dumps(msg)


def emit(out: TextIO, line: str) -> None:
    """Write one line and flush it. The HUD's state is only as fresh as the
    last flush, and a HUD lagging behind the room is a HUD that lies."""
    try:
        out.write(line + "\n")
        out.flush()
    except (BrokenPipeError, ValueError) as e:  # ValueError: closed file
        raise HudGone(str(e)) from e


async def pump(bus: ReadOnlyBus, topics: Iterable[str], out: TextIO) -> None:
    """Subscribe, then forward frames until the bus goes quiet (EOF)."""
    await bus.subscribe(topics)
    emit(out, encode_link(True))
    while True:
        frame = await bus.next_frame()
        if frame is None:
            return
        line = encode_frame(frame)
        if line is not None:
            emit(out, line)


async def run(
    connect: Callable[[], Awaitable[Any]],
    out: TextIO,
    topics: Iterable[str] = DEFAULT_TOPICS,
    *,
    attempts: Optional[int] = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    """Connect, pump, report the link honestly, retry forever.

    `attempts` bounds the retry loop for tests; in production it is None
    and the bridge outlives every restart of jarvisd.
    """
    topics = list(topics)
    delay = FIRST_BACKOFF_S
    tries = 0
    try:
        # Say "down" before the first connect: until we are subscribed, the
        # honest answer about every topic is "I don't know".
        emit(out, encode_link(False, "connecting"))
        while attempts is None or tries < attempts:
            tries += 1
            try:
                client = await connect()
            except OSError as e:
                emit(out, encode_link(False, f"connect: {e}"))
            else:
                bus = ReadOnlyBus(client)
                try:
                    await pump(bus, topics, out)
                    why = "bus closed the connection"
                except BusError as e:
                    why = f"bus rejected us: {e}"
                except OSError as e:
                    why = f"link: {e}"
                finally:
                    await bus.close()
                emit(out, encode_link(False, why))
                delay = FIRST_BACKOFF_S  # a link that worked earns a fast retry
            await sleep(delay)
            delay = min(delay * 2, MAX_BACKOFF_S)
    except HudGone:
        return
