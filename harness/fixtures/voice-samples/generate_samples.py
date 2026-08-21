#!/usr/bin/env python3
"""Generate the robotic-intensity audition samples Ofek listens to
before locking personality/voice.toml's `intensity`.

Output: robotic-0.2.wav / robotic-0.4.wav / robotic-0.7.wav (+ dry.wav
for reference), all piper en_US-ryan-high through the §06 chain.

Run: python harness/fixtures/voice-samples/generate_samples.py
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import soundfile as sf

from jv_voice.config import VoiceConfig
from jv_voice.tts import Synthesizer

HERE = Path(__file__).resolve().parent

SENTENCE = (
    "Good evening, Ofek. All systems are online. "
    "The build finished while you were away, and the E S P soak is holding steady."
)


def main() -> None:
    cfg = VoiceConfig.load()
    synth = Synthesizer(cfg)

    for intensity in (0.0, 0.2, 0.4, 0.7):
        synth.cfg = dataclasses.replace(
            cfg, chain=dataclasses.replace(cfg.chain, intensity=intensity)
        )
        audio, rate = synth.synth(SENTENCE)
        name = "dry.wav" if intensity == 0.0 else f"robotic-{intensity}.wav"
        sf.write(HERE / name, (audio * 32767).astype(np.int16), rate, subtype="PCM_16")
        print(f"wrote {name}  ({len(audio) / rate:.2f}s @ {rate} Hz)")


if __name__ == "__main__":
    main()
