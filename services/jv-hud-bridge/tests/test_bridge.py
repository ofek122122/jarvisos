"""jv-hud-bridge — the HUD's one-way window onto the bus.

The HUD is a CONSUMER (invariant 1): it subscribes over the bus socket and
never imports, calls or writes to another service. This bridge is the only
process that touches the socket on the HUD's behalf, so these tests are
mostly about what it *cannot* do — publish, emit a line QML cannot parse,
lie about the link, or keep claiming a state after the bus went away.
"""

from __future__ import annotations

import asyncio
import io
import json
import math
from pathlib import Path

import pytest

from jv_hud_bridge import bridge as br

SRC = Path(br.__file__).resolve().parent


def env(topic="speech.state", body=None, **over):
    frame = {
        "topic": topic,
        "ts": 12.5,
        "seq": 3,
        "src": "jv-voice",
        "conf": 1.0,
        "v": 1,
        "body": {"state": "speaking"} if body is None else body,
    }
    frame.update(over)
    return frame


class FakeBus:
    """Stands in for a connected BusClient. Publishing is a test failure,
    not a code path: the HUD has no business writing to the bus."""

    def __init__(self, frames):
        self.frames = list(frames)
        self.subscribed = []
        self.closed = False

    async def subscribe(self, topics):
        self.subscribed.append(list(topics))

    async def next_frame(self):
        await asyncio.sleep(0)
        return self.frames.pop(0) if self.frames else None

    async def close(self):
        self.closed = True

    async def publish(self, *a, **k):  # pragma: no cover - must never run
        raise AssertionError("the HUD bridge published to the bus")

    async def publish_env(self, *a, **k):  # pragma: no cover
        raise AssertionError("the HUD bridge published to the bus")


def lines(out):
    return [json.loads(line) for line in out.getvalue().splitlines()]


async def run_once(frames, **kw):
    """One connect -> pump -> disconnect cycle, with no retry sleep."""
    out = io.StringIO()
    slept = []

    async def sleep(d):
        slept.append(d)

    bus = FakeBus(frames)
    await br.run(lambda: _ready(bus), out, attempts=1, sleep=sleep, **kw)
    return bus, lines(out), slept


async def _ready(bus):
    return bus


# --- the line protocol -----------------------------------------------------


def test_a_frame_becomes_one_json_line_carrying_the_whole_envelope():
    line = br.encode_frame(env())
    assert "\n" not in line
    msg = json.loads(line)
    assert msg["t"] == "frame"
    # Every envelope field reaches QML: conf and ts are how a consumer
    # handles late / low-confidence input (invariant 4).
    assert msg["frame"] == {
        "topic": "speech.state",
        "ts": 12.5,
        "seq": 3,
        "src": "jv-voice",
        "conf": 1.0,
        "v": 1,
        "body": {"state": "speaking"},
    }


def test_frame_line_never_contains_a_raw_newline_or_control_character():
    line = br.encode_frame(env(body={"text": "two\nlines\r\tand a tab — dash"}))
    assert "\n" not in line and "\r" not in line and "\t" not in line
    assert json.loads(line)["frame"]["body"]["text"].startswith("two\nlines")


def test_extra_keys_outside_the_envelope_are_not_forwarded():
    line = br.encode_frame(env(**{"surprise": "x"}))
    assert "surprise" not in json.loads(line)["frame"]


@pytest.mark.parametrize(
    "bad",
    [
        "not a frame",
        {"topic": "speech.state"},  # no body
        {"body": {}},  # no topic
        {"topic": 7, "body": {}},  # topic is not a string
        {"topic": "speech.state", "body": "not a map"},
        {"topic": "speech.state", "body": {"blob": b"\xff"}},  # unencodable
        {"topic": "speech.state", "body": {"conf": math.nan}},  # NaN is not JSON
    ],
)
def test_a_frame_qml_could_not_parse_is_dropped_not_emitted(bad):
    assert br.encode_frame(bad) is None


def test_link_lines_say_up_or_down_and_carry_the_reason():
    assert json.loads(br.encode_link(True)) == {"t": "link", "up": True}
    down = json.loads(br.encode_link(False, "bus closed the connection"))
    assert down == {"t": "link", "up": False, "err": "bus closed the connection"}


# --- consumer-only, structurally -------------------------------------------


def test_the_bus_handed_to_the_pump_has_no_way_to_publish():
    view = br.ReadOnlyBus(FakeBus([]))
    assert not hasattr(view, "publish")
    assert not hasattr(view, "publish_env")
    assert sorted(n for n in dir(view) if not n.startswith("_")) == [
        "close",
        "next_frame",
        "subscribe",
    ]


def test_the_bridge_source_contains_no_publish_call():
    """A grep-level fence to go with the type-level one: if a future edit
    reaches for publish, this fails before a human has to notice."""
    for py in sorted(SRC.glob("*.py")):
        for n, line in enumerate(py.read_text("utf-8").splitlines(), 1):
            assert ".publish" not in line, f"{py.name}:{n} calls publish: {line.strip()}"


async def test_a_full_cycle_subscribes_forwards_and_never_publishes():
    bus, msgs = (await run_once([env(), env(topic="audio.wake", body={"model": "hey_jarvis", "score": 0.8, "threshold": 0.5}, conf=0.8)]))[:2]
    assert bus.subscribed == [list(br.DEFAULT_TOPICS)]
    assert bus.closed
    assert [m["t"] for m in msgs] == ["link", "link", "frame", "frame", "link"]
    assert msgs[0] == {"t": "link", "up": False, "err": "connecting"}
    assert msgs[1] == {"t": "link", "up": True}
    assert msgs[2]["frame"]["topic"] == "speech.state"
    assert msgs[3]["frame"]["conf"] == 0.8
    assert msgs[-1]["up"] is False


async def test_the_default_topic_set_is_only_topics_the_hud_can_show_truthfully():
    for topic in br.DEFAULT_TOPICS:
        assert (
            Path(__file__).resolve().parents[3] / "schemas" / f"{topic}.json"
        ).exists(), f"{topic} has no schema"


async def test_topics_are_configurable_and_subscribed_exactly_once():
    out = io.StringIO()

    async def sleep(_):
        pass

    bus = FakeBus([env()])
    await br.run(lambda: _ready(bus), out, topics=["sys.health"], attempts=1, sleep=sleep)
    assert bus.subscribed == [["sys.health"]]


# --- the link is never claimed when it is not there ------------------------


async def test_eof_on_the_bus_reports_the_link_down_before_retrying():
    _, msgs, slept = await run_once([])
    assert msgs[-1] == {"t": "link", "up": False, "err": "bus closed the connection"}
    assert slept == [br.FIRST_BACKOFF_S]


async def test_a_refused_connection_reports_down_and_backs_off_exponentially():
    out = io.StringIO()
    slept = []

    async def sleep(d):
        slept.append(d)

    async def refuse():
        raise ConnectionRefusedError("no such socket")

    await br.run(refuse, out, attempts=6, sleep=sleep)
    msgs = lines(out)
    assert all(m["up"] is False for m in msgs)
    assert "no such socket" in msgs[-1]["err"]
    # Doubling, capped: a HUD that lost the bus must not spin on connect().
    assert slept[0] == br.FIRST_BACKOFF_S
    assert slept == sorted(slept)
    assert max(slept) <= br.MAX_BACKOFF_S


async def test_a_link_that_worked_resets_the_backoff():
    out = io.StringIO()
    slept = []

    async def sleep(d):
        slept.append(d)

    buses = [FakeBus([]), FakeBus([]), FakeBus([env()])]

    async def connect():
        if not buses:
            raise ConnectionRefusedError("gone")
        return buses.pop(0)

    await br.run(connect, out, attempts=3, sleep=sleep)
    assert slept == [br.FIRST_BACKOFF_S] * 3


async def test_a_broker_error_is_reported_as_down_not_swallowed():
    class Angry(FakeBus):
        async def next_frame(self):
            raise br.BusError("bad envelope")

    out = io.StringIO()

    async def sleep(_):
        pass

    bus = Angry([])
    await br.run(lambda: _ready(bus), out, attempts=1, sleep=sleep)
    msgs = lines(out)
    assert msgs[-1]["up"] is False and "bad envelope" in msgs[-1]["err"]
    assert bus.closed, "the socket is closed even when the pump raised"


# --- the HUD going away is not an error ------------------------------------


async def test_the_bridge_exits_quietly_when_the_hud_closes_the_pipe():
    class ClosedPipe(io.StringIO):
        def write(self, s):
            raise BrokenPipeError(32, "Broken pipe")

    async def sleep(_):  # pragma: no cover - never reached
        raise AssertionError("should not retry once the HUD is gone")

    # attempts=None would loop forever if the broken pipe were ignored.
    await br.run(lambda: _ready(FakeBus([env()])), ClosedPipe(), attempts=None, sleep=sleep)


async def test_output_is_flushed_per_line_so_the_hud_sees_state_immediately():
    flushes = []

    class Watched(io.StringIO):
        def flush(self):
            flushes.append(self.getvalue().count("\n"))

    await br.run(lambda: _ready(FakeBus([env()])), Watched(), attempts=1, sleep=_noop)
    # one flush per emitted line, each after its newline landed
    assert flushes == [1, 2, 3, 4]


async def _noop(_):
    pass


# --- B50: the cadence itself, and not only the shape of it -----------------


async def test_the_reconnect_cadence_stays_inside_what_it_promises_the_hud():
    """Every other claim about the backoff in this file is spelled WITH it.

    `slept == [br.FIRST_BACKOFF_S]` and `max(slept) <= br.MAX_BACKOFF_S`
    check the SHAPE — the first sleep is the first backoff, the sequence
    rises and then stops rising — and a retune moves the code and those
    assertions together, so they go green for any pair of numbers at all,
    including a pair that leaves the HUD blind for a minute after jarvisd
    has come back. Measured, not argued: both constants were mutated (0.5 ->
    2.0, 8.0 -> 30.0) against this suite and both survived (PLAN B50).

    These are the properties the two numbers exist to satisfy, in absolute
    seconds so that a retune past them fails HERE:

    - the first retry is well under a second, because it has to land inside
      the grace `core/LinkState.qml` waits out before it puts NO BUS on
      screen. That relation is pinned across the two files in
      tools/tests/test_gen_theme_qml.py (RECONNECT_CADENCES); this end of it
      is the claim that keeps the comparison worth making.
    - and it is not zero, because spinning on connect() is the thing a
      backoff exists to prevent.
    - the ceiling is under ten seconds, because it is the worst-case age of
      everything on the HUD after the bus returns, and a HUD that is stale
      for longer than a glance is one that lies for that long (invariant 10).
    """
    assert 0.1 <= br.FIRST_BACKOFF_S < 1.0
    assert br.FIRST_BACKOFF_S < br.MAX_BACKOFF_S <= 10.0
