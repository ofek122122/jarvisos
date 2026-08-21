#!/usr/bin/env python3
"""Generate the fixture WAVs used by CI to test jv-ears end-to-end
without a microphone (BRIEF-phase1 §7). TTS = piper en_US-ryan-high (the
project voice), 16 kHz mono s16 output.

Fixtures (see REVIEW-ears.md for what each one tests):
  hey-jarvis-clean.wav   wake + question, quiet room
  hey-jarvis-music.wav   same shape with a synthetic music bed behind it
  hey-jarvis-pause.wav   speech pauses 1.2 s MID-SENTENCE and continues
  speech-no-wake.wav     speech without the wake word (negative control)

Run: python harness/fixtures/generate_fixtures.py
Requires models/fetch.sh --only voice to have run (JARVIS_MODELS_DIR
honored, default ./models-cache on dev machines).
"""

from __future__ import annotations

import io
import os
import sys
import wave
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RATE = 16_000


def models_dir() -> Path:
    if env := os.environ.get("JARVIS_MODELS_DIR"):
        return Path(env)
    if sys.platform != "win32":
        return Path("/var/lib/jarvis/models")
    return REPO / "models-cache"


def tts(voice, text: str) -> np.ndarray:
    """Piper -> float32 mono at 16 kHz."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        voice.synthesize_wav(text, w)
    buf.seek(0)
    with wave.open(buf, "rb") as w:
        rate = w.getframerate()
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    f32 = pcm.astype(np.float32) / 32768.0
    if rate != RATE:
        from math import gcd

        g = gcd(RATE, rate)
        f32 = resample_poly(f32, RATE // g, rate // g)
    return f32.astype(np.float32)


def silence(seconds: float) -> np.ndarray:
    return np.zeros(int(seconds * RATE), dtype=np.float32)


def music_bed(n: int, seed: int = 7) -> np.ndarray:
    """Synthetic 'music': slow chord pad + percussive noise bursts.
    Copyright-free by construction."""
    rng = np.random.default_rng(seed)
    t = np.arange(n) / RATE
    pad = sum(
        np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)) * a
        for f, a in [(196.0, 0.5), (247.0, 0.35), (294.0, 0.3), (392.0, 0.2)]
    )
    pad *= 0.6 + 0.4 * np.sin(2 * np.pi * 0.25 * t)  # slow swell
    perc = np.zeros(n, dtype=np.float64)
    step = int(0.5 * RATE)
    for i in range(0, n - step, step):
        burst = rng.normal(0, 1, int(0.05 * RATE)) * np.linspace(1, 0, int(0.05 * RATE))
        perc[i : i + len(burst)] += burst * 0.8
    bed = pad * 0.5 + perc
    return (bed / (np.max(np.abs(bed)) + 1e-9)).astype(np.float32)


def mix(speech: np.ndarray, bed: np.ndarray, snr_db: float = 12.0) -> np.ndarray:
    """Speech over bed at the given speech-to-bed ratio."""
    s_rms = np.sqrt(np.mean(speech**2) + 1e-12)
    b_rms = np.sqrt(np.mean(bed**2) + 1e-12)
    bed_gain = s_rms / (b_rms * (10 ** (snr_db / 20)))
    out = speech + bed[: len(speech)] * bed_gain
    return out / max(1.0, np.max(np.abs(out)) + 1e-9)


def write(name: str, audio: np.ndarray) -> None:
    import soundfile as sf

    peak = np.max(np.abs(audio)) + 1e-9
    if peak > 0.99:
        audio = audio / peak * 0.95
    sf.write(HERE / name, (audio * 32767).astype(np.int16), RATE, subtype="PCM_16")
    print(f"wrote {name}  {len(audio) / RATE:.2f}s")


def main() -> None:
    from piper import PiperVoice

    mdir = models_dir() / "piper"
    voice = PiperVoice.load(
        str(mdir / "en_US-ryan-high.onnx"),
        str(mdir / "en_US-ryan-high.onnx.json"),
    )

    lead, tail = silence(0.6), silence(0.6)

    clean = np.concatenate([lead, tts(voice, "Hey Jarvis. What time is it?"), tail])
    write("hey-jarvis-clean.wav", clean)

    speech = np.concatenate(
        [lead, tts(voice, "Hey Jarvis. Turn the volume down."), tail]
    )
    write("hey-jarvis-music.wav", mix(speech, music_bed(len(speech))))

    pause = np.concatenate(
        [
            lead,
            tts(voice, "Hey Jarvis, remind me to"),
            silence(1.2),  # mid-sentence pause — must NOT split the utterance
            tts(voice, "call my sister tomorrow morning."),
            tail,
        ]
    )
    write("hey-jarvis-pause.wav", pause)

    nowake = np.concatenate(
        [lead, tts(voice, "The quick brown fox jumps over the lazy dog."), tail]
    )
    write("speech-no-wake.wav", nowake)


if __name__ == "__main__":
    main()
