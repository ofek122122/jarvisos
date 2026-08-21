# Decisions taken while Ofek is out — review on return

Rules in effect (Ofek, 2026-08-21): take the reasonable option, record it
here, keep going. Hard stops (frozen schemas / Phase 0 boot config / hard
to reverse) get a BLOCKED proposal instead. Anything overruled gets
changed on review.

## Pre-approved in the departure Q&A (not pending — recorded for context)

- ASR: **faster-whisper** (CT2 int8, distil-small.en) — brief said
  whisper.cpp; deviation approved.
- Units: **hybrid** — jarvisd + jv-brain system; jv-ears + jv-voice user
  session (PipeWire); bus stays at /run/jarvis/bus.sock.
- Models: **fetch.sh + SHA256** to /var/lib/jarvis/models (until /tank).
- Wake UX v0: **wake word every time**, no follow-up window.
- Self-decided defaults announced before departure: continuous VAD,
  wake-gated transcription, 8s wake timeout, ~0.5s partials; sounddevice
  I/O; offline-DSP voice chain w/ intensity knob (default 0.4);
  brain = OpenAI client to llama-server, stub server in CI, ~16-turn
  rolling context, 10-min idle reset, Qwen3 thinking off; JSONL sessions;
  TTS-generated fixtures; CI model caching.

## Taken while out

(chronological; format: what came up → chosen → why → alternative)

- **Dev model cache location** → `./models-cache/` (gitignored), overridden
  by `JARVIS_MODELS_DIR`; production default stays /var/lib/jarvis/models.
  Why: keeps 300+ MB of weights out of the repo and the same fetch.sh
  works on Windows dev, CI, and ares. Alt: commit small models into the
  repo (rejected: repo bloat, no git-lfs).
- **Python packaging** → one `pyproject.toml` per service + shared
  `services/pylib` (jarvis-bus package), pytest, editable installs in a
  repo-local `.venv` (gitignored). Alt: monolithic requirements.txt
  (rejected: services must stay independent — invariant 1 in spirit).
- **Fixture WAVs committed to the repo** (4 files, ~1 MB total, 16 kHz
  mono) plus the deterministic generator script. Why: CI must not depend
  on TTS to test ears; the WAVs ARE the contract. Alt: generate in CI
  (rejected: nondeterministic piper versioning would move the test target).
- **Wake phrase stays in the transcript** ("Hey Jarvis, what time is
  it?"). Ears publishes what was said; stripping the address is jv-brain's
  job (it gets the system prompt context to handle it). Alt: strip in ears
  (rejected: ears would need language knowledge it shouldn't have).
- **Retroactive wake gating**: the wake phrase sits inside the VAD
  utterance (VAD confirms at ~200 ms, wake needs ~1 s), so a wake fired
  mid-speech gates the already-running utterance and keeps its pre-roll
  audio. Alt: only gate speech that starts after wake (rejected: would
  drop every normal "hey jarvis, <command>" said as one breath — i.e.
  the main use case).
- **Q4_K_S rung source**: Qwen's official GGUF repo ships no Q4_K_S, so
  ladder rung 3 pins bartowski/Qwen_Qwen3-8B-GGUF (hash-pinned like all
  models). Alt: skip rung 3 (rejected: your ladder spec named it).
- **Octave-up shimmer via full-wave rectification** (|x| doubles the
  fundamental, band-passed 900–5000 Hz) instead of a phase-vocoder pitch
  shifter. Why: zero extra deps, deterministic, plenty subtle at the
  -20 dB-ish levels the blueprint calls for. Alt: librosa pitch_shift
  (rejected: heavy dependency for one effect; revisit if your ears
  disagree with the samples).
- **Ring modulator (55 Hz) fades in only above intensity 0.5** — so your
  0.2/0.4 candidates are "processed natural" and 0.7 is overtly synthetic;
  a `dry.wav` reference sample was added alongside the three requested.
- **Preempted speech is dropped, not resumed** (v0). Why: resuming
  mid-sentence sounds broken; the brain can re-say if it matters. Alt:
  requeue the interrupted utterance (rejected for v0 complexity).
