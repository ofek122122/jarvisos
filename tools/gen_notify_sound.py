#!/usr/bin/env python3
"""Generate jv-notify's one arrival chime (PLAN G8, blueprint §06 "Sound as UI":
"three or four short, quiet, distinct cues — armed, confirmed, dismissed").

This is the first of those cues — "a notification arrived" — and it is
generated at build time from pure arithmetic, the same discipline
`pkgs/jarvis-wallpaper` uses for the desktop art: no binary blob checked in,
so the sound can be reviewed as the numbers that make it (two frequencies, two
durations, one peak level) rather than as an opaque .wav nobody can diff.

THE MOTIF. Two short sine tones, a rising fourth (330 Hz -> 440 Hz, E4 -> A4),
one just after the other. Rising reads as "received", not "alert" — falling or
buzzing intervals are what most desktops already spend on errors, and this is
neither an error nor an interruption worth demanding attention for. Each tone
ramps up and back down to exactly zero (a triangular envelope) so there is
never a sample-to-zero jump at either end — a chime that clicks on every
notification is worse than none.

QUIET ON PURPOSE. `PEAK` is 0.22 of full scale: audible in a quiet room,
never a jump-scare in a loud one, and jv-notify additionally plays it at
reduced volume (see pkgs/jv-notify's wrapper) so the two quiet decisions
compose rather than one silently overriding the other.

Usage:
  python tools/gen_notify_sound.py --out arrived.wav
"""

from __future__ import annotations

import argparse
import math
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 44100

# (frequency Hz, start second, duration seconds). Deliberately not overlapping
# in time — the mixer below still clamps for safety, but nothing here relies
# on that clamp to stay under 1.0.
NOTES = (
    (330.0, 0.0, 0.075),
    (440.0, 0.085, 0.11),
)

PEAK = 0.22
# The attack/release each note ramps over. Short enough that the note still
# has an audible sustain at these durations, long enough that neither edge is
# an audible click.
FADE_S = 0.012


def _note_samples(freq: float, dur_s: float, peak: float, sample_rate: int) -> list[float]:
    """One tone, as floats in [-1, 1], zero at both ends."""
    n = max(2, round(dur_s * sample_rate))
    fade_n = max(1, min((n - 1) // 2, round(FADE_S * sample_rate)))
    out = []
    for i in range(n):
        # A triangular envelope: 0 at i=0, 1 once fade_n samples in, back to 0
        # at i=n-1. Using the SAME expression for both edges is what makes the
        # boundary samples exactly 0.0 rather than "close to it".
        env = min(1.0, i / fade_n, (n - 1 - i) / fade_n)
        t = i / sample_rate
        out.append(peak * env * math.sin(2 * math.pi * freq * t))
    return out


def samples(sample_rate: int = SAMPLE_RATE) -> list[float]:
    """The whole chime, mono, floats in [-1, 1]. Deterministic: same input,
    same output, every time — nothing here reads a clock or a random source."""
    tones = []
    total_n = 0
    for freq, start, dur in NOTES:
        offset = round(start * sample_rate)
        tone = _note_samples(freq, dur, PEAK, sample_rate)
        tones.append((offset, tone))
        total_n = max(total_n, offset + len(tone))

    mix = [0.0] * total_n
    for offset, tone in tones:
        for i, v in enumerate(tone):
            mix[offset + i] += v
    # A safety clamp, not a mixer: NOTES do not overlap, so nothing here
    # should ever actually reach +-1.0.
    return [max(-1.0, min(1.0, v)) for v in mix]


def write_wav(path: Path, sample_rate: int = SAMPLE_RATE) -> None:
    frames = samples(sample_rate)
    path.parent.mkdir(parents=True, exist_ok=True)
    packed = struct.pack(f"<{len(frames)}h", *(round(v * 32767) for v in frames))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(packed)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="where to write the .wav")
    parser.add_argument("--sample-rate", type=int, default=SAMPLE_RATE)
    args = parser.parse_args()
    write_wav(args.out, args.sample_rate)


if __name__ == "__main__":
    main()
