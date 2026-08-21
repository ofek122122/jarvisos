"""jv-ears end-to-end on the committed fixtures — real openWakeWord,
real Silero VAD, real faster-whisper, no microphone (BRIEF-phase1 §7).

Requires models: ./models/fetch.sh --only ears (CI caches them).
Skips (loudly) if models are absent rather than faking a pass.
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
