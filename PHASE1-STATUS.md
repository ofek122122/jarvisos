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
