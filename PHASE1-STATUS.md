# Phase 1 status — It speaks

Tracking per [`BRIEF-phase1.md`](BRIEF-phase1.md). Built on Windows ahead of
install day; anything needing real hardware is mocked and tagged
`TODO(machine)` tied to the exit checklist.

| # | Item | Status |
|---|---|---|
| 1 | Schemas (`schemas/`) | **FROZEN v1** (76f3c84) + codegen w/ CI drift gate |
| 2 | `services/jarvisd` broker + `jv` CLI (Rust) | **DONE** — 7 tests green (routing, fanout, disconnect, drop-oldest + health report, envelope rejection); `jv sub/pub/tap --latency/health`; Nix package in flake |
| 3 | `services/jv-ears` (Python) | **DONE** — wake(oww)+VAD(silero)+ASR(faster-whisper) verified on 4 fixtures incl. music-bed and mid-sentence-pause requirements; see REVIEW-ears.md; pylib bus client + models/fetch.sh landed with it |
| 4 | `services/jv-voice` (Python) | **DONE** — piper ryan-high + §06 chain (intensity knob in personality/voice.toml, default 0.4 PROVISIONAL); wake barge-in, urgent-preempts, low-drops all tested vs real bus; **audition samples in harness/fixtures/voice-samples/ (dry / 0.2 / 0.4 / 0.7) — listen and lock intensity** |
| 5 | `services/jv-brain` v0 (Python) | **DONE** — conversation-only vs llama-server API; jv-llm-launch implements the VRAM ladder (headroom-based, KV-in-budget, rung → rung-file → sys.health metrics); personality/system.md DRAFT awaiting review; 12 tests (7 ladder, 5 service vs stub LLM) |
| 6 | `modules/jarvis-services.nix` + model fetching | **DONE (eval-verified)** — hybrid units, hardened, personality in /etc; models/fetch.sh SHA256-pinned; ⚠ nix python packaging is BUILD-untested until first `nixos-rebuild build` (flagged in nix/jarvis-python.nix) |
| 7 | Harness seed (`record.py` / `replay.py` + fixtures) | **DONE** — JSONL sessions w/ boot-anchor header, timing-preserving replay (--speed/--instant), 4 fixtures; roundtrip tested vs real jarvisd |
| CI | schema validation, codegen drift, jarvisd tests, ears-on-fixtures | **DONE** — 4 jobs: flake eval, bindings drift, jarvisd (tests+clippy), python (pylib/ears/voice/brain/harness suites, cached models) |

## Decisions (locked by Ofek, 2026-08-21)

- **Brain model: Qwen3-8B** (thinking mode OFF for voice latency). The VRAM
  guard must budget **total headroom, not model size**: measure free VRAM
  with the desktop already running on all three monitors, and include the
  KV cache in the budget. Fallback ladder, explicit in config, in order:
  1. KV cache quantized to q8
  2. context 4k → 2k
  3. Q4_K_S weights
  4. CPU inference
  The active rung is logged in `sys.health` (visible via `jv health`).
- **Piper voice: en_US-ryan-high** — permanent (consistency is identity);
  §06 effects chain applies on top later.

## Your review queue (in order)

1. `DECISIONS-pending.md` — every call taken while you were out
2. `REVIEW-ears.md` — mock wiring + fixture table
3. **Listen**: `harness/fixtures/voice-samples/` (dry / 0.2 / 0.4 / 0.7),
   then lock `intensity` in `personality/voice.toml` (currently 0.4
   PROVISIONAL)
4. `personality/system.md` — v0 draft, edit to taste

## First on-hardware exit measurements (2026-09-15/16)

- **Offline demo: PASS.** ~5.5 h with connectivity `none` (logged every
  2 s); 15 complete voice exchanges during the window. Nothing left the
  machine — there was no network to leave on.
- **Kill-one-service: PASS.** jv-context SIGKILLed; restarted in 2 s;
  all other services unaffected. (Bonus find, fixed same day: jv-ears
  died 0 on a PipeWire race and stayed down — see e3be821.)
- **Latency < 2.5 s: FAIL.** `jv tap --latency` over 15 exchanges:
  best 5353 ms, typical 5–7 s, degrading to ~18 s late in the evening,
  worst 44.7 s. llama-server timings put the blame precisely:
  - generation is fine (~43 tok/s, replies 0.5–1.5 s)
  - **prompt prefill on cache miss is the killer**: 1400-token history
    re-prefilled from scratch = 10.0 s (140 tok/s prefill on the 1660).
    When the slot cache hits (task following task), prefill is ~0.5 s.
  - the degradation curve = conversation history growing all evening
    with no trimming, re-prefilled per exchange.
  - measurement definition: `jv tap` anchors at **VAD start**, so the
    number includes the user's own speaking time + endpoint silence
    (~2–3 s). Even the "true" system latency (speech end → speech.say)
    is ~2–4 s best case today — still over budget on cache misses.

  Fix directions for the latency task (own session): pin llama slot +
  `cache_prompt` so history never re-prefills; trim/summarize history
  in jv-brain; cap spoken-reply length; stream first sentence to
  jv-voice while the rest generates; decide the measurement anchor
  (VAD end vs start) and re-state the budget accordingly.

  **UPDATE 2026-09-24 (ee96c43): the measurement stops mixing your voice
  with the machine's time.** `jv tap --latency` no longer prints one
  number. Each turn is split at the boundaries jv-ears itself publishes —
  `spoke` (you talking), `hold` (ears' `vad_min_silence_ms`, the silence
  it deliberately sits through to bridge a mid-sentence pause), `respond`
  (ASR + brain + bus) — and the summary carries a p50/p95/max per span.
  The machine's share of a turn is `hold + respond`; `spoke` is yours and
  no faster machine shortens it. The hold is read off jv-ears'
  `sys.health` `metrics` (`vad_min_silence_s`, added for this reader, the
  same free-form section `wake_timeout_s` uses — no schema change); there
  is NO fallback to its default, so a tap that has not heard a jv-ears
  heartbeat prints `?` for the spans that need it rather than a number
  that would look like a reading.

  This does not re-state the budget — **which span the 2.5 s applies to is
  still an open human decision**, and it is now a decision that can be
  made against data. Also fixed here: the old anchor took the earliest ts
  of ANY frame carrying the utterance_id, including an `audio.transcript`
  partial, which is emitted part-way through the utterance — so a turn
  whose partial arrived before the vad frame was silently measured short.
  Boundaries now come only from `audio.vad`, by `event`.

  **UPDATE 2026-09-24: `respond` stops being one number over two
  services.** The two STILL-OPEN latency chunks below are ASR and the
  brain, and until now the measurement had them in a single span — so
  neither could be optimised against it. The frame that divides them was
  already on the bus: jv-ears runs whisper AFTER publishing `speech_end`
  and publishes the `audio.transcript` **final** when it is done, so that
  frame is the seam. `jv tap --latency` now reports `hear` (speech_end ->
  final transcript: jv-ears' ASR) and `think` (final transcript -> first
  `speech.say`: jv-brain to its first word, plus a bus hop each way),
  which partition `respond` exactly. No new publisher, no schema change.
  A turn with no final (jv-ears publishes none for an utterance its ASR
  read as empty, and a tap can simply have missed it) prints `?` for both
  and keeps `respond` whole; a final landing outside the span it would
  divide refuses both halves rather than publishing a negative. The
  2.2 s ASR figure and the prefill/generation figures below came from
  llama-server's own timings and a stopwatch; they are now readable off
  the bus in the same table as everything else.

  **UPDATE 2026-09-24: `think` stops being one number over the model and
  everything around it.** `think` was the LLM AND a bus hop each way AND
  however long the transcript sat in jv-brain's input queue, and the span
  this file wants to optimise ("prefill fixed, generation not") is the
  model's alone. Unlike the hear/think seam, no frame on the bus marks the
  moment the completion request went out — only jv-brain can see it — so
  jv-brain now states it: `llm_first_say_ms` plus a turn counter
  `llm_first_says` in its `sys.health` `metrics`, which is free-form and
  service-local by schema (no schema change). `jv tap --latency` divides
  `think` into `model` (the completion request -> the first `speech.say`:
  prefill + generation to the first sentence) and `wait` (the rest: bus
  hops, the input queue, jv-brain's own work), as two more rows in the
  table and a second line per turn.

  **What a turn prints is a LADDER of lines, and every one of them fits 80
  columns.** One line carrying six numbers and a live utterance id came to
  133 columns and wrapped, which is worse than the one number it replaced;
  each rung now divides a span the rung above it gave a value for (the turn,
  then `respond`, then jv-act's share of `think`, then your share of
  jv-act's), and the utterance id — a `uuid4` from jv-ears, 36 characters —
  prints as an 8-character prefix and `...`. The width is a test at the
  widest input that can reach those lines, not a hope.

  Two honesty rules, both enforced by tests. (1) A turn that ran TOOLS
  publishes no gauge at all: tool round-trips — including a confirm window —
  sit inside its `think`, and calling that time "the model" is how a number
  stops meaning its label. The table then says `think unsplit` and names the
  gauge it wanted rather than printing a guess. (2) `sys.health` carries no
  `utterance_id`, so the gauge is bound to its turn by frame ORDER: jv-brain
  publishes it immediately after the `speech.say` it measures, on the same
  connection, and the counter is what tells a fresh gauge from the same
  number re-stated on the next periodic heartbeat. The first count a tap
  sees is recorded and not consumed — it may describe a turn from before the
  tap connected, and a measurement may not guess.

  `jv health --check` is now the gauge's SECOND reader: its `llm` line adds
  `first_say=<ms> turn_age=<s>` beside the rung, so "is generation slow right
  now?" can be asked without starting a tap and speaking to the machine. The
  age is the load-bearing half. jv-brain re-states the same number on every
  periodic heartbeat for the rest of the process's life, so a brain nobody has
  spoken to since breakfast would otherwise read as one that just took 412 ms.
  The counter decides: it rose inside the window and the age is a measurement
  (`turn_age=1.5s`), or it did not and the only honest statement is a lower
  bound (`turn_age>=6.0s`). A count going BACKWARDS is jv-brain restarted, not
  a newer turn, and starts the window over. Note the age dates the last
  DIVISIBLE turn — a turn that ran tools published no gauge — which is why the
  field is `turn_age` and not "idle".

  **UPDATE 2026-09-23 (308e12b): streaming reply — the perceived-latency
  fix.** jv-brain now streams the llama completion and speaks each sentence
  as it closes (SentenceChunker → one speech.say per sentence, shared
  reply_group; schema f461a09); jv-voice drops a reply_group's queued tail
  on barge-in. Measured live: request → first sentence **580 ms** vs
  request → full reply 1457 ms (877 ms head start on 4 sentences, grows
  with length). Also fixed same evening: clipped speech tails (voice
  player waited on a wall-clock guess, not the device) and Jarvis hearing
  itself (half-duplex gate in jv-ears) — see 7f39196.

  STILL OPEN — the two remaining latency chunks are in the EARS, both
  bigger changes for their own session:
  1. **ASR is ~2.2 s fixed** (faster-whisper distil-small, CPU, runs after
     speech_end). Real fix = streaming ASR. Strong candidate found:
     NVIDIA Nemotron streaming ASR 0.6B (June 2026, ~24 ms to final,
     40-locale, configurable chunk) — evaluate as a whisper replacement.
  2. **Endpoint wait 1.5 s** — deliberately tuned to bridge a 1.2 s
     mid-sentence pause; needs semantic/smarter endpointing to cut safely,
     not a flat reduction.

  **UPDATE 2026-09-16 (d94807a): the re-prefill cliff is fixed** —
  pinned slot + cache_prompt, --parallel 1 + --cache-reuse 256, batched
  prefix-stable trims, and a startup warmup. Measured: first exchange
  after boot 10 532 ms → 653 ms total LLM time; warm turns ~190 ms
  prefill + generation. Voice re-measurement (`jv tap --latency`)
  pending; sentence-streaming to TTS and the measurement-anchor decision
  remain on the table if voice numbers are still over budget.

## Mocked / waiting for the machine (all tagged TODO(machine))

- `MicSource` + `SoundDevicePlayer` — real mic array + speakers
- `jv-llm-launch` against the real 1660 SUPER (ladder constants verified
  live); llama-server + Qwen3 weights (`./models/fetch.sh --only brain`,
  ~9.8 GB)
- `nix/jarvis-python.nix` builds (openwakeword/piper wheels) — first
  `nixos-rebuild build`
- Real-voice wake tuning + Hebrew transcript fixture (needs your voice)
- Entire BRIEF-phase1 exit checklist (latency <2.5s, kill-one-service,
  offline demo, replay-to-brain with no mic)

## Phase 0 remainder (on Ofek, in parallel)

- Pre-flight (BitLocker+key, recovery USB, Secure Boot decision, NixOS USB);
  install day. (ESP migration cancelled 2026-08-23; 2 TB disk off-limits.)
