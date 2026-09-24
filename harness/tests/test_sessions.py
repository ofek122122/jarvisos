"""The committed perception sessions (harness/fixtures/sessions).

These files are what jv-ears really published while listening to the
fixture WAVs. They exist so that perception behaviour can be asserted on a
machine with no model weights: `services/jv-ears/tests/test_pipeline_fixtures.py`
needs ~1 GB of ONNX and skips loudly without it, which leaves everything
downstream of ears with no example of what perception looks like.

So the requirements REVIEW-ears.md states are checked twice: there, against
the live models when they are installed, and here, against the recording,
always. The two only stay in agreement because the jv-ears suite also
re-records and compares — a fixture nothing re-derives is a fixture that
has already rotted and not told anyone.
"""

import asyncio
import sys
from pathlib import Path

import pytest

HARNESS = Path(__file__).resolve().parents[1]
REPO = HARNESS.parent
sys.path.insert(0, str(HARNESS))
sys.path.insert(0, str(HARNESS / "fixtures" / "sessions"))
sys.path.insert(0, str(REPO / "services" / "pylib"))

import replay  # noqa: E402
import session  # noqa: E402
from jarvis_bus import BusClient  # noqa: E402

SESSIONS = HARNESS / "fixtures" / "sessions"
NAMES = sorted(p.stem for p in SESSIONS.glob("*.jsonl"))


def load(name: str) -> session.Session:
    return session.load(SESSIONS / f"{name}.jsonl")


def bodies(sess: session.Session, topic: str) -> list[dict]:
    return [f["body"] for f in sess.frames if f["topic"] == topic]


def final(sess: session.Session) -> dict:
    finals = [b for b in bodies(sess, "audio.transcript") if b["kind"] == "final"]
    assert len(finals) == 1, f"expected exactly one final, got {len(finals)}"
    return finals[0]


def said(sess: session.Session) -> str:
    return final(sess)["text"].lower()


# ------------------------------------------------- the files are still law

def test_there_are_sessions_to_test():
    assert NAMES, "no committed sessions — run generate_sessions.py"


@pytest.mark.parametrize("name", NAMES)
def test_every_committed_session_is_legal(name):
    """Envelope keys, bodies, versions, ordering — against the generated
    bindings, so a schema that moves fails here instead of silently
    invalidating every test below."""
    session.check(load(name))


@pytest.mark.parametrize("name", NAMES)
def test_every_committed_session_is_anchored_to_the_sample_clock(name):
    """`ts` here is the WAV's sample clock, not this boot's monotonic one,
    and the header has to say so rather than borrow a real boot_id."""
    sess = load(name)
    assert sess.header["boot_id"] == session.SAMPLE_CLOCK
    assert sess.header["monotonic_now"] == 0.0
    assert all(f["ts"] >= 0.0 for f in sess.frames)


def test_every_source_wav_has_a_session_and_the_reverse():
    """A WAV added without re-recording, or a session left behind after its
    WAV went away, is a hole in the coverage nobody would notice."""
    import generate_sessions

    assert NAMES == sorted(Path(s).stem for s in generate_sessions.SOURCES)
    for name in generate_sessions.SOURCES:
        assert (HARNESS / "fixtures" / name).exists()


@pytest.mark.parametrize("name", NAMES)
def test_only_jv_ears_speaks_in_a_perception_session(name):
    assert {f["src"] for f in load(name).frames} <= {"jv-ears"}


# --------------------------------------------- what perception must do

def test_a_clean_wake_produces_partials_then_one_final():
    sess = load("hey-jarvis-clean")
    (wake,) = bodies(sess, "audio.wake")
    assert wake["score"] >= wake["threshold"]
    kinds = [b["kind"] for b in bodies(sess, "audio.transcript")]
    assert kinds[-1] == "final"
    assert kinds[:-1] and set(kinds[:-1]) == {"partial"}, kinds
    assert "what time" in said(sess)


def test_music_behind_the_speech_breaks_neither_wake_nor_asr():
    sess = load("hey-jarvis-music")
    assert bodies(sess, "audio.wake")
    assert "volume" in said(sess)


def test_a_mid_sentence_pause_stays_one_utterance():
    """1.2 s of silence in the middle of a sentence must not close the
    utterance: one speech_start, one speech_end, one final with both
    halves of the sentence in it."""
    sess = load("hey-jarvis-pause")
    assert [b["event"] for b in bodies(sess, "audio.vad")] == [
        "speech_start", "speech_end"]
    text = said(sess)
    assert "remind me" in text
    assert "sister" in text and "tomorrow" in text


def test_speech_without_the_wake_word_is_heard_but_never_transcribed():
    """VAD publishes continuously — presence is a free signal and not a
    privacy decision. ASR is wake-gated, so nothing said here is written
    down anywhere."""
    sess = load("speech-no-wake")
    assert bodies(sess, "audio.vad"), "the VAD should still see the speech"
    assert bodies(sess, "audio.wake") == []
    assert bodies(sess, "audio.transcript") == []


@pytest.mark.parametrize("name", NAMES)
def test_nothing_is_transcribed_before_a_wake(name):
    """Across every session: the first transcript, if there is one, comes
    after a wake. This is the gate that keeps a room out of the record."""
    sess = load(name)
    waked = False
    for frame in sess.frames:
        if frame["topic"] == "audio.wake":
            waked = True
        if frame["topic"] == "audio.transcript":
            assert waked, f"{name}: transcript with no wake before it"


@pytest.mark.parametrize("name", NAMES)
def test_every_transcript_threads_an_utterance_the_vad_opened(name):
    """The input `utterance_id` is minted at speech_start and has to flow
    through every transcript (schemas/README.md) — that thread is what
    jv-brain answers and what jv-memory will archive."""
    sess = load(name)
    opened = {b["utterance_id"] for b in bodies(sess, "audio.vad")
              if b["event"] == "speech_start"}
    spoken = {b["utterance_id"] for b in bodies(sess, "audio.transcript")}
    assert spoken <= opened
    assert len(spoken) <= 1, "one wake, one utterance (v0)"


# --------------------------------------------------- they still replay

async def test_a_committed_session_replays_onto_a_real_bus(bus_addr):
    """The point of recording them: a consumer under test can be handed a
    real perception session without a microphone anywhere in the room."""
    sess = load("hey-jarvis-clean")
    sub = await BusClient.connect(bus_addr, src="t-sub")
    await sub.subscribe(["audio.*"])
    await asyncio.sleep(0.3)

    assert await replay.replay(SESSIONS / "hey-jarvis-clean.jsonl",
                               bus_addr, instant=True) == len(sess.frames)

    got = []
    while len(got) < len(sess.frames):
        got.append(await asyncio.wait_for(sub.next_frame(), timeout=5))
    assert [f["topic"] for f in got] == [f["topic"] for f in sess.frames]
    assert [f["body"] for f in got] == [f["body"] for f in sess.frames]
    assert all(f["src"] == "jv-ears" for f in got)
    await sub.close()
