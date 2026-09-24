"""The bounded no-wake window, as a decision and as a wire.

`dialog.listen` is the ONE approved exception to "the wake word, every
time" (DECISIONS-approved, taken 2026-08-22): jv-act asks for it when it
needs the answer to a confirmation, jv-brain when it is asking an
onboarding or follow-up question. Two services have been publishing it
since Phase 2 and nothing has ever opened the window.

This file is the half that needs no microphone and no models: what the
window accepts, what it refuses, and that the frame reaches the pipeline
at all. The audio half — the same WAV transcribed or not depending on one
bus frame — is tests/test_no_wake_window.py.

Every refusal here matters more than the acceptances. A frame this code
cannot read confidently must leave the microphone exactly as wake-gated
as it was: the failure this validation exists to prevent is an
unparsable, mis-versioned or hedged frame opening a no-wake window on a
machine whose user never said anything to it.
"""

from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path

import pytest

import jv_ears.main as main_mod
from jv_ears.dialog import MAX_WINDOW_S, REASONS, ListenWindow

REPO = Path(__file__).resolve().parents[3]
SCHEMA = json.loads((REPO / "schemas" / "dialog.listen.json").read_text())

RATE = 16_000
GOOD = {"listen_id": "4b1d", "window_s": 15.0, "reason": "confirm"}


def opened(window_s=15.0, **over) -> ListenWindow:
    """A window with an accepted request, advanced to sample 0."""
    w = ListenWindow(RATE)
    assert w.request({**GOOD, "window_s": window_s, **over})
    assert w.advance(0)
    return w


# --------------------------------------------------------------- the law

def test_the_cap_is_the_frozen_schemas_own_maximum():
    """60 s is not this file's number to choose (invariant 2)."""
    assert MAX_WINDOW_S == SCHEMA["properties"]["window_s"]["maximum"]


def test_the_reasons_are_the_frozen_schemas_own_enum():
    assert REASONS == frozenset(SCHEMA["properties"]["reason"]["enum"])


@pytest.mark.parametrize("field", sorted(SCHEMA["required"]))
def test_a_frame_missing_a_required_field_opens_nothing(field):
    """Tied to the schema, not to a list here: the day `dialog.listen`
    requires a fourth field, this fails until ears validates it."""
    body = {k: v for k, v in GOOD.items() if k != field}
    w = ListenWindow(RATE)
    assert not w.request(body)
    assert not w.advance(0)


# ------------------------------------------------------------- acceptance

def test_a_fresh_window_is_closed():
    """Nothing about arriving at a machine opens a microphone."""
    w = ListenWindow(RATE)
    assert not w.advance(0)
    assert not w.open
    assert w.reason is None


def test_an_accepted_request_opens_at_the_next_advance():
    w = ListenWindow(RATE)
    assert w.request(GOOD)
    assert not w.open, "the bus thread arms; the pipeline thread opens"
    assert w.advance(0)
    assert w.open
    assert w.reason == "confirm"


def test_the_window_lasts_exactly_the_seconds_it_was_asked_for():
    w = opened(window_s=15.0)
    assert w.advance(15 * RATE - 1)
    assert not w.advance(15 * RATE)
    assert w.reason is None


@pytest.mark.parametrize("reason", sorted(REASONS))
def test_every_approved_reason_opens_and_is_readable(reason):
    """The reason is the audited field — the schema says the HUD will
    show it, so it survives the trip rather than being validated away."""
    assert opened(reason=reason).reason == reason


def test_a_window_can_be_opened_again_after_it_expires():
    w = opened(window_s=1.0)
    assert not w.advance(RATE)
    assert w.request(GOOD)
    assert w.advance(2 * RATE)


# ------------------------------------------------------------- refusals

@pytest.mark.parametrize(
    "window_s",
    [0, 0.0, -1.0, MAX_WINDOW_S + 0.001, 1e9, float("nan"), float("inf"),
     "15", None, True],
)
def test_a_window_length_that_is_not_a_bounded_positive_number_is_refused(window_s):
    """Fail closed. `True` is in here on purpose: it is an `int` in
    Python, and `True * 16000` is a perfectly good-looking window."""
    w = ListenWindow(RATE)
    assert not w.request({**GOOD, "window_s": window_s})
    assert not w.advance(0)


def test_the_longest_window_the_schema_allows_is_still_accepted():
    """The cap is a boundary, not a fence one short of it."""
    assert opened(window_s=MAX_WINDOW_S).open


@pytest.mark.parametrize("reason", ["", "dictation", "CONFIRM", None, 3])
def test_an_unaudited_reason_is_refused(reason):
    """A reason this ears cannot name is a purpose it cannot audit, and
    an unauditable purpose does not get a microphone."""
    w = ListenWindow(RATE)
    assert not w.request({**GOOD, "reason": reason})
    assert not w.advance(0)


@pytest.mark.parametrize("listen_id", ["", None, 17, b"4b1d"])
def test_a_request_with_no_usable_listen_id_is_refused(listen_id):
    w = ListenWindow(RATE)
    assert not w.request({**GOOD, "listen_id": listen_id})
    assert not w.advance(0)


@pytest.mark.parametrize("body", [None, "confirm", 3, [], ("window_s", 5)])
def test_a_body_that_is_not_an_object_is_refused(body):
    w = ListenWindow(RATE)
    assert not w.request(body)
    assert not w.advance(0)


@pytest.mark.parametrize("conf", [0.99, 0.5, 0.0, -1.0, None, "1.0", True])
def test_a_hedged_command_is_refused(conf):
    """`dialog.listen` is a command topic: the schema says conf = 1.0.
    A producer that is not sure it wants the microphone open does not
    get it opened (invariant 4, pointed the safe way)."""
    w = ListenWindow(RATE)
    assert not w.request(GOOD, conf=conf)
    assert not w.advance(0)


@pytest.mark.parametrize("v", [0, 2, 99, None, "1", True])
def test_a_body_version_this_ears_does_not_know_is_refused(v):
    """A v2 body means whatever v2 says it means. Refusing is the only
    reading that cannot be wrong about a microphone."""
    w = ListenWindow(RATE)
    assert not w.request(GOOD, v=v)
    assert not w.advance(0)


# ------------------------------------------------------------ overlapping

def test_a_second_request_extends_the_window_and_never_shortens_it():
    """jv-brain asking for 5 s must not cut short the 15 s jv-act is
    waiting on — the mic closing early loses an answer the user gave."""
    w = opened(window_s=15.0)
    assert w.request({**GOOD, "window_s": 5.0, "reason": "followup"})
    assert w.advance(RATE)
    assert w.reason == "confirm", "the furthest deadline owns the window"
    assert w.advance(15 * RATE - 1)
    assert not w.advance(15 * RATE)


def test_a_longer_second_request_moves_the_deadline_out():
    w = opened(window_s=5.0)
    assert w.request({**GOOD, "window_s": 20.0, "reason": "onboarding"})
    assert w.advance(RATE)
    assert w.reason == "onboarding"
    assert w.advance(20 * RATE)  # the second request started at sample RATE
    assert not w.advance(21 * RATE)


def test_two_requests_between_two_chunks_both_count():
    """The bus thread can arm twice inside one 80 ms chunk. Neither may
    be dropped: a queue, not a slot that the pipeline thread clears."""
    w = ListenWindow(RATE)
    assert w.request({**GOOD, "window_s": 1.0})
    assert w.request({**GOOD, "window_s": 30.0, "reason": "onboarding"})
    assert w.advance(0)
    assert w.reason == "onboarding"
    assert w.advance(29 * RATE)


# --------------------------------------------------------------- the wire


class FakeBus:
    """A bus that hands over a fixed list of frames and then goes quiet.

    `drained` is what makes this test deterministic rather than a race:
    the fake pipeline's worker thread holds the process open until the
    frame loop has consumed every frame, so amain cannot reach its
    `finally` and cancel the bus task before it has run.
    """

    def __init__(self, frames):
        self.frames = list(frames)
        self.subscribed: list = []
        self.drained = threading.Event()

    async def publish(self, *args, **kwargs):
        pass

    async def subscribe(self, topics):
        self.subscribed.append(list(topics))

    async def next_frame(self):
        if self.frames:
            await asyncio.sleep(0)
            return self.frames.pop(0)
        self.drained.set()
        await asyncio.Event().wait()  # cancelled when amain returns

    async def close(self):
        pass


def run_main(monkeypatch, frames):
    """Run the real amain over a fake bus; return the bus and pipeline."""
    bus = FakeBus(frames)
    seen: dict = {}

    class FakeBusClient:
        @staticmethod
        async def connect(*a, **k):
            return bus

    class Pipeline:
        """The half of EarsPipeline main.py touches."""

        def __init__(self, cfg, publish):
            self.listens: list = []
            self.suppressions: list = []
            seen["pipe"] = self

        def budgets(self):
            return {"wake_timeout_s": 8.0}

        def request_listen(self, body, conf=1.0, v=1):
            self.listens.append((body, conf, v))
            return True

        def set_suppressed(self, value):
            self.suppressions.append(value)

        def run(self, source):
            assert bus.drained.wait(timeout=10), "frame loop never drained"

    monkeypatch.setattr(main_mod, "BusClient", FakeBusClient)
    monkeypatch.setattr(main_mod, "MicSource", lambda *a, **k: object())
    monkeypatch.setattr(main_mod, "EarsPipeline", Pipeline)

    assert asyncio.run(main_mod.amain([])) == 0
    return bus, seen["pipe"]


def frame(topic, body, conf=1.0, v=1):
    return {"topic": topic, "ts": 0.0, "seq": 1, "src": "jv-act",
            "conf": conf, "v": v, "body": body}


def test_ears_subscribes_to_the_window_it_now_honours(monkeypatch):
    bus, _ = run_main(monkeypatch, [])
    assert bus.subscribed == [["speech.state", "dialog.listen"]]


def test_a_listen_frame_reaches_the_pipeline_whole(monkeypatch):
    """Envelope and body both: the window refuses on `conf` and `v`, so a
    wire that forwarded only the body would make those refusals
    unreachable from the bus."""
    _, pipe = run_main(monkeypatch, [frame("dialog.listen", GOOD)])
    assert pipe.listens == [(GOOD, 1.0, 1)]


def test_a_hedged_listen_frame_is_forwarded_and_refused_there(monkeypatch):
    """main.py does not do the deciding — one place decides, and it is
    the one with the tests."""
    _, pipe = run_main(monkeypatch, [frame("dialog.listen", GOOD, conf=0.4)])
    assert pipe.listens == [(GOOD, 0.4, 1)]


def test_the_half_duplex_gate_still_works_alongside_it(monkeypatch):
    _, pipe = run_main(monkeypatch, [
        frame("speech.state", {"state": "speaking"}),
        frame("dialog.listen", GOOD),
        frame("speech.state", {"state": "idle"}),
    ])
    assert pipe.suppressions == [True, False]
    assert len(pipe.listens) == 1


def test_a_topic_ears_did_not_ask_for_is_ignored(monkeypatch):
    _, pipe = run_main(monkeypatch, [frame("audio.transcript", {"text": "hi"})])
    assert pipe.listens == []
    assert pipe.suppressions == []
