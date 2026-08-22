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
| 0 | Additive schemas (8 new topics incl. dialog.listen) | **DONE** — CI green |
| 1 | `services/jv-context` (Python) | **DONE** — niri event-stream backend (TODO(machine) field-verify) + mock for CI; pre-seeded privacy blocklist tested (keepass/bitwarden/1password/private/incognito); 1 Hz snapshots; 13 tests |
| 2 | `services/jv-act` (Rust) — **REVIEW-REQUIRED** | **BUILT + TESTED, NOT WIRED** — registry TOML (11 tools, observe/benign only), validation gauntlet, confirm flow (yes/no/timeout all tested), append-only audit + `jv act-log`, `jv confirm`; 11 tests + clippy clean; **deliberately absent from jarvis-services.nix until Ofek reads every line** |
| 3 | jv-brain v1 tool calling | **DONE** — registry-driven OpenAI tool defs, tool loop off the frame reader (no deadlock), 5-call cap, hallucinated tools never reach act (counted in health metrics), results fed back for spoken summaries; 15 tests |
| 4 | jv-compat + jv-guard + windows-compat.nix | **DONE** — fingerprint (nsis/inno/msi/arch from headers), recipes (default-deny grants), bwrap confinement argv, fail-closed pipeline; guard verdict logic + EICAR + no-engine=no-verdict; windows-compat.nix completed (binfmt, wine/umu/bottles, clamav); 15 tests |
| 5 | Greeting v0 | not started |

## Waiting for the machine

- (accumulates as built)
