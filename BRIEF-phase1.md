# BRIEF — Phase 1: It speaks

Goal: the nervous system (bus) and the first full sensory loop (voice).
End state: you say "hey jarvis" across the room and it answers out loud,
fully offline. Everything in this phase is code + CI-testable with mocked
audio; only the exit checklist needs the real machine, so this entire phase
can be built BEFORE install day and validated the same way Phase 0 was.

Blocked on nothing. Runs in parallel with the ESP soak.

## Order is law: schemas → broker → services

### 1. Schemas (frozen before any service code)

`schemas/` gets JSON Schema files, each versioned, with the standard
envelope (topic, ts monotonic, seq, src, conf, body) from the blueprint:

- `envelope.json` — the frame every message uses
- `audio.wake.json` — wake detection events (model, score)
- `audio.vad.json` — speech start/stop
- `audio.transcript.json` — partial + final transcripts, lang, conf
- `speech.say.json` — TTS requests (text, priority, interruptible)
- `speech.state.json` — speaking/idle/interrupted
- `brain.request.json` / `brain.response.json`
- `sys.health.json` — every service heartbeats on this

Generate typed bindings for both Rust and Python from these files (codegen
checked into CI, drift = build failure). A schema change after freeze is its
own reviewed commit with a version bump. Invariant 2 applies.

### 2. `services/jarvisd` — the broker (Rust)

- Unix socket `/run/jarvis/bus.sock`, MessagePack frames, topic pub/sub
  with prefix subscriptions (`vision.*`).
- Slow-consumer policy: drop-oldest per subscriber for stream topics,
  never block a publisher (Invariant 5). Log drops to `sys.health`.
- Ships with a debug CLI `jv`: `jv sub <topic>`, `jv pub`, `jv tap
  --latency` (prints per-hop latency from envelope timestamps), `jv health`.
  This CLI is how we debug everything forever — make it good.
- Unit + integration tests (multiple pubs/subs, disconnects, drop policy)
  run in CI.

### 3. `services/jv-ears` (Python)

Pipeline: openWakeWord (pretrained `hey_jarvis`) → Silero VAD →
whisper.cpp streaming (distil-small.en, **CPU** — the GPU belongs to the
brain). Publishes `audio.wake`, `audio.vad`, `audio.transcript` (partials +
final). Mic via PipeWire. Audio input abstracted behind a source interface
so tests and the replay harness can feed WAV files instead of a mic.

### 4. `services/jv-voice` (Python)

Consumes `speech.say`, speaks via Piper (CPU, pick a good en voice, make
the voice a `personality/` setting). Publishes `speech.state`.
Interruption: a new wake event while speaking stops playback mid-sentence
(ducking now, barge-in polish later).

### 5. `services/jv-brain` v0 (Python)

- llama.cpp server, 8B-class Q4 instruct model, OpenAI-compatible endpoint,
  managed as its own systemd unit. VRAM guard: refuses to load if the GPU
  reports insufficient free memory, logs to `sys.health` and falls back to
  CPU inference (slow but alive).
- v0 scope: conversation only. Consumes final transcripts, replies via
  `speech.say`. Short rolling context. NO tools, NO memory writes — that is
  Phases 2 and 4. Do not gold-plate.
- System prompt loaded from `personality/system.md` (v0: name Jarvis,
  English, concise spoken-style replies — write a first draft for review).

### 6. Wiring

- `modules/jarvis-services.nix`: systemd units for all four, sandboxed
  (DynamicUser where possible, device access only where needed), restart
  on-failure, socket dir via tmpfiles. Killing any one service must leave
  the others running (Invariant 1) — test this.
- Models (whisper, piper voice, LLM GGUF, openwakeword) fetched via Nix
  fixed-output derivations or a documented `models/fetch.sh` with hashes —
  no "download it manually from somewhere".

### 7. Harness seed

`harness/record.py` (dump bus topics to a session file) and
`harness/replay.py` (replay a session onto the bus with original timing).
Plus 3–4 fixture WAVs (scripted phrases, TTS-generated is fine) used by CI
to test ears end-to-end without a microphone.

## CI additions

Schema validation + codegen drift, jarvisd tests, ears-on-fixtures test,
flake check as before. No GPU in CI — GPU paths behind a flag.

## Exit checklist (needs the real machine, post-install)

- [ ] "hey jarvis" → spoken reply, end-to-end < 2.5 s, measured by `jv tap
      --latency`, machine offline (network unplugged for the demo)
- [ ] Partial transcripts visible in `jv sub audio.transcript` while speaking
- [ ] Speaking while it talks interrupts it
- [ ] `systemctl kill` any one jv-* service: others unaffected, it restarts,
      chain recovers without reboot
- [ ] Whisper runs on CPU; brain on GPU; `nvidia-smi` confirms during a chat
- [ ] A recorded session replays through `harness/replay.py` and produces a
      brain response with no mic involved

Then request BRIEF-phase2 (jv-act, jv-context, jv-compat — it acts).
