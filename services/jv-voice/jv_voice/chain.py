"""The signature effects chain (blueprint §06): an excellent natural
voice with subtle processing — not a robotic TTS.

Stages: high-pass ~120 Hz → octave-up harmonic "shimmer" (full-wave
rectifier trick: |x| doubles the fundamental, then band-passed) → short
plate reverb (synthetic exponential-decay IR, seeded → deterministic) →
soft tanh limiter. `intensity` scales shimmer + reverb wet, and above
0.5 fades in a faint ring modulator for the overtly synthetic register.

At 0.2 the chain should read as "good speakers in a treated room"; at
0.4 people ask what voice that is; at 0.7 it is unmistakably a machine.
Ofek auditions all three from harness/fixtures/voice-samples/.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

from .config import ChainParams


def _highpass(audio: np.ndarray, rate: int, hz: float) -> np.ndarray:
    sos = butter(2, hz, btype="highpass", fs=rate, output="sos")
    return sosfilt(sos, audio)


def _octave_shimmer(audio: np.ndarray, rate: int) -> np.ndarray:
    """Octave-up layer via full-wave rectification (doubles the
    fundamental), band-passed to keep only the airy top."""
    rect = np.abs(audio) - float(np.mean(np.abs(audio)))
    sos = butter(2, [900.0, 5000.0], btype="bandpass", fs=rate, output="sos")
    return sosfilt(sos, rect)


def _plate_ir(rate: int, seconds: float, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)  # fixed seed: the room never changes
    n = max(1, int(seconds * rate))
    t = np.arange(n) / rate
    ir = rng.normal(0, 1, n) * np.exp(-t / (seconds / 3.0))
    sos = butter(1, 300.0, btype="highpass", fs=rate, output="sos")
    ir = sosfilt(sos, ir)
    return (ir / (np.max(np.abs(ir)) + 1e-9)).astype(np.float64)


def apply_chain(audio_f32: np.ndarray, rate: int, p: ChainParams) -> np.ndarray:
    """float32/float64 mono in [-1, 1] -> processed float32."""
    x = audio_f32.astype(np.float64)
    i = float(np.clip(p.intensity, 0.0, 1.0))

    x = _highpass(x, rate, p.highpass_hz)

    if i > 0:
        x = x + _octave_shimmer(x, rate) * (p.shimmer_base * i)

        wet = fftconvolve(x, _plate_ir(rate, p.reverb_seconds), mode="full")[: len(x)]
        wet /= max(1.0, np.max(np.abs(wet)) / (np.max(np.abs(x)) + 1e-9))
        x = x * (1.0 - 0.5 * p.reverb_wet_base * i) + wet * (p.reverb_wet_base * i)

        ring_amt = max(0.0, i - 0.5) * 0.6  # silent below 0.5, subtle above
        if ring_amt > 0:
            t = np.arange(len(x)) / rate
            x = x * (1.0 - ring_amt) + (x * np.sin(2 * np.pi * p.ringmod_hz * t)) * ring_amt

    # Soft limiter: drive into tanh, normalize to a healthy peak.
    x = np.tanh(x * p.limiter_drive) / np.tanh(p.limiter_drive)
    peak = np.max(np.abs(x)) + 1e-9
    if peak > 0.95:
        x = x / peak * 0.95
    return x.astype(np.float32)
