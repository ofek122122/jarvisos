# REVIEW — jv-ears (checkpoint file, Ofek reviews on return)

## How the mock audio source is wired

The pipeline never knows where audio comes from. `jv_ears.audio` defines
the seam:

```
AudioSource (interface: chunks() -> iterator of 80ms int16@16k chunks)
├─ MicSource  — sounddevice/PortAudio -> PipeWire   [TODO(machine): only
│               used on ares; tied to exit items 1–3, never used in CI]
└─ WavSource  — WAV file(s) as one continuous stream + 3s silence tail
                so trailing speech flushes through VAD
```

`EarsPipeline(cfg, publish)` consumes chunks from either source and emits
events through the `publish(topic, conf, v, body)` callback — `main.py`
binds that to the real bus; tests bind it to a list. **All segmentation
timing runs on the sample clock** (samples consumed ÷ 16000), not the wall
clock, so a fixture produces identical events on every run — that's what
makes the CI test meaningful. `jv-ears --wav file.wav` runs the same path
against the live bus with no microphone involved.

Pipeline: openWakeWord (hey_jarvis, cont.) + Silero VAD v5 (cont.) →
faster-whisper distil-small.en int8 (wake-gated only). One subtlety worth
knowing: the wake phrase sits INSIDE the utterance (VAD confirms speech
~200 ms in; "hey jarvis" needs ~1 s to score), so a wake fired mid-speech
gates the in-flight utterance retroactively. Finals include the "Hey
Jarvis" prefix — stripping it is jv-brain's concern, not ears'.

## Fixtures (harness/fixtures/, TTS = piper ryan-high, committed)

| WAV | Content | Tests |
|---|---|---|
| `hey-jarvis-clean.wav` | "Hey Jarvis. What time is it?" quiet | wake fires (0.99), ≥1 partial before final, final contains "what time", one utterance_id threads all transcripts |
| `hey-jarvis-music.wav` | "Hey Jarvis. Turn the volume down." over a synthetic music bed (chord pad + percussion, ~12 dB SNR) | **your requirement: music/noise behind speech** — wake 0.96, final contains "volume" (conf drops 0.89→0.72, expected) |
| `hey-jarvis-pause.wav` | "Hey Jarvis, remind me to" +**1.2 s silence**+ "call my sister tomorrow morning." | **your requirement: mid-sentence pause** — exactly one speech_start/speech_end pair, final holds both halves (`vad_min_silence_ms=1500` bridges it) |
| `speech-no-wake.wav` | "The quick brown fox…" no wake word | negative control: VAD events only (continuous presence), zero wake, zero transcripts |

`generate_fixtures.py` regenerates all four deterministically (seeded
noise). Observed on this machine: clean final = "Hey Jarvis, what time is
it?" @ conf 0.89; music final = "Hey Jarvis, turn the volume down!" @
0.72; pause final = "Hey Jarvis remind me to Call my sister tomorrow
morning" @ 0.86.

## Tunables (services/jv-ears/jv_ears/config.py — engineering, not personality/)

wake_threshold 0.5 · refractory 2 s · wake_timeout 8 s · vad_threshold
0.5 · min_speech 200 ms · **min_silence 1500 ms** (the pause-bridging
knob; also sets end-of-utterance latency — lower it if replies feel slow
on the machine) · pre-roll 400 ms · partial cadence 0.7 s.

## Waits for the machine (tagged TODO(machine))

- MicSource against the real far-field array (exit items 1–3).
- Real-voice wake tuning: TTS triggers at 0.88–0.99; your voice across
  the room is the actual test. Threshold may need lowering.
- Hebrew: Whisper language detection is wired (`lang` on every
  transcript) but untested — needs a spoken Hebrew fixture recorded by
  you (TTS won't prove it).
