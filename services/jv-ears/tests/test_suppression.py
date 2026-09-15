"""Half-duplex gate: while jv-voice is speaking, the ears must not open
utterances — Jarvis must not hear Jarvis.

Field evidence (2026-09-16, ares): with nobody in the room, a spoken
speech.say produced audio.vad speech_start + a 12.16 s utterance in
jv-ears. In real conversations that polluted every utterance boundary and
inflated end-to-end latency to 10-60 s. Wake stays ACTIVE while
suppressed — that is what barge-in runs on.
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


def run_pipe(pipe: EarsPipeline, name: str, events: list) -> None:
    pipe.run(WavSource([FIXTURES / name], CFG.chunk_samples))


def collect(events: list):
    return lambda t, c, v, b: events.append((t, b))


def starts(events) -> list:
    return [b for t, b in events if t == "audio.vad" and b["event"] == "speech_start"]


def test_suppressed_ears_open_no_utterances():
    events: list = []
    pipe = EarsPipeline(CFG, collect(events))
    pipe.set_suppressed(True)
    run_pipe(pipe, "hey-jarvis-clean.wav", events)
    assert starts(events) == []
    assert [t for t, _ in events if t == "audio.transcript"] == []


def test_unsuppressed_pipeline_still_works():
    """The gate must default open and fully reopen after suppression."""
    events: list = []
    pipe = EarsPipeline(CFG, collect(events))
    pipe.set_suppressed(True)
    pipe.set_suppressed(False)
    run_pipe(pipe, "hey-jarvis-clean.wav", events)
    assert starts(events), "utterance expected once unsuppressed"
    assert "audio.transcript" in [t for t, _ in events]


def test_no_vad_evidence_accumulates_while_gated():
    """Speech heard while the gate is closed must not count: without a
    reset, the moment the gate reopens the accumulated speech-run fires
    an instant utterance from Jarvis's own tail audio (field-observed:
    a 20 ms blip 350 ms after speech.state idle)."""
    chunks = list(
        WavSource([FIXTURES / "hey-jarvis-clean.wav"], CFG.chunk_samples).chunks()
    )
    # find a cut point where an UNGATED pipeline holds live speech evidence
    probe = EarsPipeline(CFG, lambda *a: None)
    cut = None
    for i, chunk in enumerate(chunks):
        probe.feed(chunk)
        if probe._speech_run >= probe._min_speech:
            cut = i
            break
    assert cut is not None, "fixture must contain speech"

    events: list = []
    pipe = EarsPipeline(CFG, collect(events))
    pipe.set_suppressed(True)
    for chunk in chunks[: cut + 1]:
        pipe.feed(chunk)
    assert pipe._speech_run == 0
    assert starts(events) == []


def test_suppression_tail_blocks_immediate_reopen():
    """Right after unsuppression the room still carries the tail of
    Jarvis's audio — the gate stays closed for suppress_tail_ms of
    SAMPLES, then reopens. The fixture front-loads speech, so with a huge
    tail nothing may start."""
    events: list = []
    cfg = EarsConfig()
    cfg.suppress_tail_ms = 10 * 60 * 1000  # longer than any fixture
    pipe = EarsPipeline(cfg, collect(events))
    pipe.set_suppressed(True)
    pipe.set_suppressed(False)
    run_pipe(pipe, "hey-jarvis-clean.wav", events)
    assert starts(events) == []
