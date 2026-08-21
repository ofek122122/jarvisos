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
