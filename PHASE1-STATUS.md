# Phase 1 status — It speaks

Tracking per [`BRIEF-phase1.md`](BRIEF-phase1.md). Built on Windows ahead of
install day; anything needing real hardware is mocked and tagged
`TODO(machine)` tied to the exit checklist.

| # | Item | Status |
|---|---|---|
| 1 | Schemas (`schemas/`) | **DRAFTED — awaiting Ofek's review before freeze** |
| 2 | `services/jarvisd` broker + `jv` CLI (Rust) | not started (blocked on schema freeze) |
| 3 | `services/jv-ears` (Python) | not started |
| 4 | `services/jv-voice` (Python) | not started |
| 5 | `services/jv-brain` v0 (Python) | not started — LLM model choice goes to Ofek |
| 6 | `modules/jarvis-services.nix` + model fetching | not started |
| 7 | Harness seed (`record.py` / `replay.py` + fixtures) | not started |
| CI | schema validation, codegen drift, jarvisd tests, ears-on-fixtures | not started |

## Open decisions (Ofek decides, options to be presented)

- LLM model (8B-class Q4 instruct) — options with sizes/tradeoffs pending
- Piper voice — options pending

## Mocked / waiting for the machine

- (none yet — will list every mock and its `TODO(machine)` tag here)
- Exit checklist (BRIEF-phase1) runs only post-install on ares.

## Phase 0 remainder (on Ofek, in parallel)

- Pre-flight 3 & 4 tonight; ESP migration + 3-boot soak after; install day.
