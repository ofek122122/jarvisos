"""The same three and a half seconds of speech, transcribed or not
depending on one bus frame — real openWakeWord, real Silero VAD, real
faster-whisper, no microphone.

`speech-no-wake.wav` is a real utterance nobody addressed to Jarvis, and
it has always been the fixture that proves the wake gate holds: the VAD
sees it, and the ASR never does. That makes it the only honest way to
show that `dialog.listen` works, because the difference between the two
outcomes is a single frame from jv-act or jv-brain and nothing else —
not a different WAV, not a threshold, not a flag.

Requires models: ./models/fetch.sh --only ears. Skips loudly if absent
rather than faking a pass.
"""

from pathlib import Path

import pytest

from jv_ears.audio import WavSource
from jv_ears.config import EarsConfig
from jv_ears.pipeline import EarsPipeline

REPO = Path(__file__).resolve().parents[3]
FIXTURES = REPO / "harness" / "fixtures"

CFG = EarsConfig()
if not CFG.wake_model.exists() or not (CFG.whisper_dir / "model.bin").exists():
    pytest.skip(
        "ears models missing — run ./models/fetch.sh --only ears",
        allow_module_level=True,
    )

# The fixture, on the sample clock this pipeline decides on: VAD confirms
# speech at 0.8 s and calls it over at 4.4 s. Every window length below is
# chosen against those two numbers.
SPEECH_START_S = 0.8
SPEECH_END_S = 4.4


def listen(window_s: float, reason: str = "confirm") -> dict:
    return {"listen_id": "b0a7", "window_s": window_s, "reason": reason}


def play(pipe: EarsPipeline, name: str, at=None) -> list:
    """Run a fixture through `pipe`; `at` is `(seconds, fn)`, called once
    the pipeline's own clock has passed that point."""
    for chunk in WavSource([FIXTURES / name], CFG.chunk_samples).chunks():
        if at is not None and pipe.clock() >= at[0]:
            at[1](pipe)
            at = None
        pipe.feed(chunk)
    assert at is None, "the fixture ended before the scheduled moment"


def collected():
    events: list = []
    return events, EarsPipeline(CFG, lambda t, c, v, b: events.append((t, c, b)))


def topics(events) -> list:
    return [t for t, _, _ in events]


def finals(events) -> list:
    return [b for t, _, b in events if t == "audio.transcript" and b["kind"] == "final"]


def test_without_a_window_the_wake_gate_still_holds():
    """The control, and the whole point of the fixture: speech in the
    room that nobody addressed to Jarvis is heard and never transcribed."""
    events, pipe = collected()
    play(pipe, "speech-no-wake.wav")
    assert "audio.vad" in topics(events)
    assert "audio.transcript" not in topics(events)


def test_inside_a_window_the_same_audio_is_transcribed():
    """jv-act asked for the next 15 seconds. This is the approved
    exception working, and it is the first time it ever has."""
    events, pipe = collected()
    assert pipe.request_listen(listen(15.0))
    play(pipe, "speech-no-wake.wav")
    assert len(finals(events)) == 1
    assert finals(events)[0]["text"].strip()


def test_a_no_wake_window_never_forges_a_wake():
    """`audio.wake` means openWakeWord scored the phrase. The HUD reads
    that frame (SpeechState) and so does `jv tap`; a window that
    published one to gate itself would be lying to both about what the
    user said."""
    events, pipe = collected()
    assert pipe.request_listen(listen(15.0))
    play(pipe, "speech-no-wake.wav")
    assert "audio.wake" not in topics(events)


def test_a_window_that_expired_before_you_spoke_transcribes_nothing():
    """0.5 s of no-wake listening, and the speech arrives at 0.8 s. The
    window is a deadline, not a mood."""
    events, pipe = collected()
    assert pipe.request_listen(listen(0.5))
    play(pipe, "speech-no-wake.wav")
    assert "audio.transcript" not in topics(events)
    assert finals(events) == []


def test_a_window_that_expires_mid_sentence_still_takes_the_sentence():
    """The window governs where you may START speaking without a wake
    word. Cutting an utterance off at the deadline would mean an answer
    the user gave in time arrives half-transcribed or not at all — and
    the recording is already bounded by the VAD."""
    events, pipe = collected()
    assert pipe.request_listen(listen(1.0))  # speech runs 0.8 s -> 4.4 s
    play(pipe, "speech-no-wake.wav")
    assert len(finals(events)) == 1


def test_a_window_opened_after_you_started_talking_does_not_reach_back():
    """The wake path gates retroactively, because "hey jarvis" is INSIDE
    the utterance it belongs to. A no-wake window has no such excuse: the
    words already in flight were spoken before any service asked for
    them, and transcribing them would be this machine listening to a
    sentence that was not addressed to it."""
    events, pipe = collected()
    play(
        pipe,
        "speech-no-wake.wav",
        at=(SPEECH_START_S + 0.5, lambda p: p.request_listen(listen(30.0))),
    )
    assert "audio.transcript" not in topics(events)


def test_jarvis_still_does_not_hear_jarvis():
    """Half-duplex outranks the window. jv-act publishes `dialog.listen`
    while jv-voice is still asking the question, so this is the ORDINARY
    case, not an edge one: the window is open for seconds during which
    the only voice in the room is Jarvis's own."""
    events, pipe = collected()
    pipe.set_suppressed(True)
    assert pipe.request_listen(listen(30.0))
    play(pipe, "speech-no-wake.wav")
    assert "audio.transcript" not in topics(events)


def test_a_refused_request_leaves_the_machine_wake_gated():
    """The refusals are unit-tested next door; this is the one that
    matters — a frame ears could not read confidently changes nothing
    about what the microphone does."""
    events, pipe = collected()
    assert not pipe.request_listen(listen(600.0))  # past the schema's cap
    play(pipe, "speech-no-wake.wav")
    assert "audio.transcript" not in topics(events)


def test_the_wake_path_is_untouched_by_all_of_this():
    """A window nobody asked for must leave the ordinary turn alone."""
    events, pipe = collected()
    play(pipe, "hey-jarvis-clean.wav")
    assert "audio.wake" in topics(events)
    assert len(finals(events)) == 1
