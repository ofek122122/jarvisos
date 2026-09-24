"""jv-ears end-to-end on the committed fixtures — real openWakeWord,
real Silero VAD, real faster-whisper, no microphone (BRIEF-phase1 §7).

Requires models: ./models/fetch.sh --only ears (CI caches them).
Skips (loudly) if models are absent rather than faking a pass.
"""

import sys
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


def run_fixture(name: str):
    events = []
    pipe = EarsPipeline(CFG, lambda t, c, v, b: events.append((t, c, b)))
    pipe.run(WavSource([FIXTURES / name], CFG.chunk_samples))
    return events


def topics(events):
    return [t for t, _, _ in events]


def final_of(events) -> str:
    finals = [b for t, _, b in events if t == "audio.transcript" and b["kind"] == "final"]
    assert len(finals) == 1, f"expected exactly one final, got {len(finals)}"
    return finals[0]["text"].lower()


def test_clean_wake_partials_final():
    events = run_fixture("hey-jarvis-clean.wav")
    assert "audio.wake" in topics(events)
    partials = [b for t, _, b in events if t == "audio.transcript" and b["kind"] == "partial"]
    assert partials, "streaming partials expected before the final"
    text = final_of(events)
    assert "what time" in text
    # every transcript threads the same input utterance
    ids = {b["utterance_id"] for t, _, b in events if t == "audio.transcript"}
    assert len(ids) == 1


def test_music_bed_does_not_break_asr():
    """Requirement: speech with music/noise behind it must still wake and
    transcribe."""
    events = run_fixture("hey-jarvis-music.wav")
    assert "audio.wake" in topics(events)
    assert "volume" in final_of(events)


def test_mid_sentence_pause_stays_one_utterance():
    """Requirement: a 1.2 s pause mid-sentence must NOT split the
    utterance — one speech_start, one speech_end, one final containing
    both halves."""
    events = run_fixture("hey-jarvis-pause.wav")
    vad = [b["event"] for t, _, b in events if t == "audio.vad"]
    assert vad == ["speech_start", "speech_end"]
    text = final_of(events)
    assert "remind me" in text
    assert "sister" in text and "tomorrow" in text


def test_no_wake_means_no_transcription():
    """Speech without the wake word: VAD publishes (continuous presence
    signal), but nothing is transcribed. Also: no wake event."""
    events = run_fixture("speech-no-wake.wav")
    assert "audio.wake" not in topics(events)
    assert "audio.transcript" not in topics(events)
    vad = [b["event"] for t, _, b in events if t == "audio.vad"]
    assert vad == ["speech_start", "speech_end"]


def test_wake_scores_are_confident():
    events = run_fixture("hey-jarvis-clean.wav")
    wakes = [b for t, _, b in events if t == "audio.wake"]
    assert len(wakes) == 1
    assert wakes[0]["score"] >= 0.8
    assert wakes[0]["threshold"] == CFG.wake_threshold


def test_the_pipeline_reports_the_wake_window_it_actually_enforces():
    """The HUD stops calling itself "listening" when ears has disarmed.

    It used to mirror `wake_timeout_s` in QML with a "keep this at or
    below what ears is tuned to" comment (PLAN A14). Now ears says it,
    on sys.health.metrics — and says what it ENFORCES, which is the
    sample-clock count the code compares against, not the number in the
    config file. Today they agree to within one sample; the day anything
    here rounds differently, the published value follows the code.
    """
    pipe = EarsPipeline(CFG, lambda t, c, v, b: None)
    reported = pipe.budgets()["wake_timeout_s"]
    assert reported == pipe._wake_timeout / CFG.sample_rate
    assert reported == pytest.approx(CFG.wake_timeout_s, abs=1.0 / CFG.sample_rate)
    assert reported > 0


# ------------------------------------------------ the committed sessions

# What the live pipeline does here is also committed, frame by frame, in
# harness/fixtures/sessions — so that everything downstream of ears can be
# tested on a machine with no model weights (PLAN B3). The recording is
# only worth having while something re-derives it, and this is that thing:
# without it a retuned VAD would leave four stale files asserting the old
# behaviour, and every test built on them would keep passing.
sys.path.insert(0, str(REPO / "harness"))
sys.path.insert(0, str(REPO / "harness" / "fixtures" / "sessions"))

import generate_sessions  # noqa: E402
import session as session_file  # noqa: E402


def shape(frames):
    """What must not change: which frames, when, and in what state.

    Deliberately not `conf` and not the partial texts — a model score is
    the last digits of a float on the machine that ran it, and a fixture
    that fails because CI has a different CPU teaches people to regenerate
    without reading. Segmentation, gating and timing are what these files
    are for, and all three are here.
    """
    out = []
    for f in frames:
        b = f["body"]
        out.append((f["topic"], f["ts"], b.get("event") or b.get("kind")))
    return out


def normalized_final(frames) -> list:
    """Final transcripts, case- and punctuation-insensitive.

    Only the finals: a partial is whisper's opinion of half a sentence and
    a word of it moving is not a regression. The final is the sentence
    jv-brain is handed, so a word of THAT moving is.
    """
    out = []
    for f in frames:
        if f["topic"] == "audio.transcript" and f["body"]["kind"] == "final":
            text = f["body"]["text"].lower()
            keep = "".join(c for c in text if c.isalnum() or c.isspace())
            out.append(" ".join(keep.split()))
    return out


@pytest.mark.parametrize("wav", generate_sessions.SOURCES)
def test_the_committed_session_is_what_the_pipeline_still_does(wav):
    committed = session_file.load(
        REPO / "harness" / "fixtures" / "sessions" / f"{Path(wav).stem}.jsonl")
    live = generate_sessions.frames_for(FIXTURES / wav)
    assert shape(live) == shape(committed.frames), (
        f"{wav}: perception changed. If that was the point, regenerate with "
        f"python harness/fixtures/sessions/generate_sessions.py and read the diff."
    )
    assert normalized_final(live) == normalized_final(committed.frames)
