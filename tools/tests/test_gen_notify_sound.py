"""tools/gen_notify_sound.py — jv-notify's one arrival chime (PLAN G8).

There is no golden .wav to diff — the point of generating the sound from
arithmetic rather than checking in a binary blob is that the arithmetic is
what gets reviewed. So these tests hold the CONTRACT the header comment
states: quiet, short, click-free at both ends, deterministic, and a real
16-bit mono .wav comes out the far end of the CLI.
"""

from __future__ import annotations

import struct
import sys
import wave
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import gen_notify_sound as gen  # noqa: E402


def test_deterministic():
    """Same call, same output — no clock, no randomness, nothing time-of-day
    dependent. A generator that drifted between builds would make the sound
    part of the flake's own reproducibility story a lie."""
    assert gen.samples() == gen.samples()


def test_quiet():
    """PEAK is 0.22 of full scale, and nothing downstream should ever see a
    sample louder than that: a mixing bug (an overlap the header comment says
    should not happen) would show up here as amplitude, not as a sound anyone
    has to listen to."""
    peak = max(abs(v) for v in gen.samples())
    assert 0.0 < peak <= gen.PEAK + 1e-9


def test_short():
    """A chime, not a jingle: blueprint §06 asks for "short, quiet, distinct
    cues", and a notification corner that plays a half-second fanfare on every
    toast is not that."""
    duration_s = len(gen.samples()) / gen.SAMPLE_RATE
    assert 0.05 < duration_s < 0.5


def test_click_free_at_both_ends():
    """Every note ramps to exactly zero at its own edges (a triangular
    envelope), and NOTES' first note starts at t=0 / the last note is the one
    that ends last, so the chime as a whole starts and ends at zero too — the
    one property that keeps a notification sound from popping."""
    frames = gen.samples()
    assert frames[0] == 0.0
    assert frames[-1] == 0.0


def test_two_distinct_notes_reach_full_envelope():
    """Not a single tone, and not so short that neither note ever reaches its
    own sustain (env=1): a generator that shrank FADE_S past a note's own
    duration would silently turn the whole chime into two clicks."""
    sr = gen.SAMPLE_RATE
    for freq, start, dur in gen.NOTES:
        tone = gen._note_samples(freq, dur, gen.PEAK, sr)
        assert max(abs(v) for v in tone) > gen.PEAK * 0.9, (
            f"note at {freq}Hz never reaches its own peak envelope"
        )


def test_notes_do_not_overlap():
    """The mixer's clamp is documented as a safety net, never load-bearing —
    this is what proves NOTES actually keeps that promise."""
    spans = sorted((start, start + dur) for _, start, dur in gen.NOTES)
    for (a_start, a_end), (b_start, b_end) in zip(spans, spans[1:]):
        assert a_end <= b_start, "NOTES overlap in time; the mixer's clamp would be load-bearing"


def test_write_wav_round_trips(tmp_path):
    """The CLI's whole job: a real mono 16-bit .wav at the sample rate asked
    for, with exactly as many frames as `samples()` produced."""
    out = tmp_path / "arrived.wav"
    gen.write_wav(out, sample_rate=22050)

    with wave.open(str(out), "rb") as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == 22050
        expected = gen.samples(22050)
        assert w.getnframes() == len(expected)
        raw = w.readframes(w.getnframes())

    got = struct.unpack(f"<{len(expected)}h", raw)
    # Round-tripped through 16-bit PCM: off by at most one quantization step.
    for sample, want in zip(got, expected):
        assert abs(sample - round(want * 32767)) <= 1


def test_cli_writes_the_file(tmp_path, monkeypatch):
    out = tmp_path / "nested" / "arrived.wav"
    monkeypatch.setattr(sys, "argv", ["gen_notify_sound.py", "--out", str(out)])
    gen.main()
    assert out.is_file()
    with wave.open(str(out), "rb") as w:
        assert w.getframerate() == gen.SAMPLE_RATE
