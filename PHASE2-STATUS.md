# Phase 2 status — It acts

Tracking per [`BRIEF-phase2.md`](BRIEF-phase2.md). Overnight autonomous
stretch, 2026-08-22.

> ## ⚠ REVIEW-REQUIRED: jv-act
> The entire `services/jv-act` commit series (registry TOML included) is
> built and tested but **must not run anywhere before Ofek has read
> every line** (CLAUDE.md invariant 3, BRIEF-phase2 exit item 8). It is
> deliberately NOT wired into `modules/jarvis-services.nix` until that
> review happens.

| # | Item | Status |
|---|---|---|
| 0 | Additive schemas (7 new topics) | in progress |
| 1 | `services/jv-context` (Python) | not started |
| 2 | `services/jv-act` (Rust) — **REVIEW-REQUIRED** | not started |
| 3 | jv-brain v1 tool calling | not started |
| 4 | `services/jv-compat` + `services/jv-guard` + windows-compat.nix | not started |
| 5 | Greeting v0 | not started |

## Waiting for the machine

- (accumulates as built)
