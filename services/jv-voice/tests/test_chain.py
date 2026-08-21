"""Unit tests for the signature chain — pure DSP, no models needed."""

import dataclasses

import numpy as np

from jv_voice.chain import apply_chain
from jv_voice.config import ChainParams


def speechish(seconds: float = 1.0, rate: int = 22050) -> np.ndarray:
    """Deterministic speech-like test signal: pitched buzz + noise."""
    rng = np.random.default_rng(1)
    t = np.arange(int(seconds * rate)) / rate
    x = (
        0.5 * np.sin(2 * np.pi * 120 * t)
        + 0.25 * np.sin(2 * np.pi * 240 * t)
        + 0.05 * rng.normal(0, 1, len(t))
    )
    return (x / np.max(np.abs(x)) * 0.8).astype(np.float32)


def test_output_sane_at_all_intensities():
    x = speechish()
    for i in (0.0, 0.2, 0.4, 0.7, 1.0):
        y = apply_chain(x, 22050, ChainParams(intensity=i))
        assert y.shape == x.shape
        assert np.all(np.isfinite(y))
        assert np.max(np.abs(y)) <= 0.951


def test_intensity_is_monotonic_in_effect_strength():
    """More intensity -> more deviation from the intensity-0 baseline."""
    x = speechish()
    base = apply_chain(x, 22050, ChainParams(intensity=0.0))
    deltas = []
    for i in (0.2, 0.4, 0.7):
        y = apply_chain(x, 22050, ChainParams(intensity=i))
        deltas.append(float(np.sqrt(np.mean((y - base) ** 2))))
    assert deltas[0] < deltas[1] < deltas[2], deltas


def test_ringmod_only_above_half():
    """Below 0.5 the ring modulator must be silent: 0.2 vs 0.4 differ only
    in shimmer/reverb scale, both without the 55 Hz tremor."""
    x = speechish()
    p = ChainParams(intensity=0.49)
    y_lo = apply_chain(x, 22050, p)
    p2 = dataclasses.replace(p, ringmod_hz=7.0)  # would be very audible
    y_lo2 = apply_chain(x, 22050, p2)
    assert np.allclose(y_lo, y_lo2), "ring mod leaked below intensity 0.5"
