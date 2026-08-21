# Phase 1 status — It speaks

Tracking per [`BRIEF-phase1.md`](BRIEF-phase1.md). Built on Windows ahead of
install day; anything needing real hardware is mocked and tagged
`TODO(machine)` tied to the exit checklist.

| # | Item | Status |
|---|---|---|
| 1 | Schemas (`schemas/`) | **FROZEN v1** (76f3c84) + codegen w/ CI drift gate |
| 2 | `services/jarvisd` broker + `jv` CLI (Rust) | **DONE** — 7 tests green (routing, fanout, disconnect, drop-oldest + health report, envelope rejection); `jv sub/pub/tap --latency/health`; Nix package in flake |
| 3 | `services/jv-ears` (Python) | not started |
| 4 | `services/jv-voice` (Python) | not started |
| 5 | `services/jv-brain` v0 (Python) | not started — LLM model choice goes to Ofek |
| 6 | `modules/jarvis-services.nix` + model fetching | not started |
| 7 | Harness seed (`record.py` / `replay.py` + fixtures) | not started |
| CI | schema validation, codegen drift, jarvisd tests, ears-on-fixtures | not started |

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

## Mocked / waiting for the machine

- (none yet — will list every mock and its `TODO(machine)` tag here)
- Exit checklist (BRIEF-phase1) runs only post-install on ares.

## Phase 0 remainder (on Ofek, in parallel)

- Pre-flight 3 & 4 tonight; ESP migration + 3-boot soak after; install day.
