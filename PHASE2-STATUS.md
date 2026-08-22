# Phase 2 status — It acts

Tracking per [`BRIEF-phase2.md`](BRIEF-phase2.md). Overnight autonomous
stretch, 2026-08-22.

> ## ✅ REVIEW-PASSED: jv-act (2026-08-22)
> Ofek + advisor read `services/jv-act` line by line. Architecture
> approved; four required fixes applied and tested (see below). jv-act is
> now **wired** into `modules/jarvis-services.nix` as a user-session unit
> with the authoritative registry at `/etc/jarvis/tools.toml`.
>
> Review fixes, each with a regression test:
> 1. **Confirm/transcript correlation tightened** — at most one confirm
>    outstanding (a second destructive intent is `denied`); voice answers
>    accepted only when the transcript's envelope ts is inside the open
>    window. Tests: `stray_yes_no_with_no_window_open_is_ignored`,
>    `voice_answer_outside_the_window_is_ignored`,
>    `second_destructive_denied_while_one_pends`. (Airtight fix — a
>    `listen_id` on `audio.transcript` — logged for the next schema bump.)
> 2. **`window.move_workspace` keeps its window_id** — focus-then-move,
>    tested in `move_workspace_keeps_the_window_id`.
> 3. **Flag injection closed** — `--` terminator before every user
>    positional; `open.item` rejects leading-dash targets. Tests:
>    `user_positionals_are_flag_guarded`, `open_item_rejects_flag_targets`.
> 4. **Audit-before-execute** — an intent line is written before any
>    execution and a failed write refuses the action; outcome line after.
>    Test: `benign_tool_executes_and_audits` asserts the intent→outcome
>    ordering.

| # | Item | Status |
|---|---|---|
| 0 | Additive schemas (8 new topics incl. dialog.listen) | **DONE** — CI green |
| 1 | `services/jv-context` (Python) | **DONE** — niri event-stream backend (TODO(machine) field-verify) + mock for CI; pre-seeded privacy blocklist tested (keepass/bitwarden/1password/private/incognito); 1 Hz snapshots; 13 tests |
| 2 | `services/jv-act` (Rust) — **REVIEW-PASSED + WIRED** | registry TOML (11 tools, observe/benign only), validation gauntlet, confirm flow, audit + `jv act-log`/`jv confirm`; **4 review fixes applied**; 18 tests (6 unit + 12 integration) + clippy clean; wired as a user-session unit |
| 3 | jv-brain v1 tool calling | **DONE** — registry-driven OpenAI tool defs, tool loop off the frame reader (no deadlock), 5-call cap, hallucinated tools never reach act (counted in health metrics), results fed back for spoken summaries; 15 tests |
| 4 | jv-compat + jv-guard + windows-compat.nix | **DONE** — fingerprint (nsis/inno/msi/arch from headers), recipes (default-deny grants), bwrap confinement argv, fail-closed pipeline; guard verdict logic + EICAR + no-engine=no-verdict; windows-compat.nix completed (binfmt, wine/umu/bottles, clamav); 15 tests |
| 5 | Greeting v0 | **DONE** — time-of-day + name-if-known, session-start via jv-greeting oneshot unit |
| 6 | First-boot onboarding (added mid-stretch) | **DONE** — de-hardcoded system.md (profile injected at prompt time), profile.json semantic-seed store, spoken meeting via dialog.listen (name + pronunciation confirm), name corrections as facts, follow-up trickle, `jv-onboard --reset`; 23 brain tests |

## Install-day dry run (2026-08-22) — see `docs/dry-run.md`

Rehearsed Runbook C in WSL2 (real Linux kernel, not a GUI VM — a headless
agent can't drive an interactive installer console). Outcome:

- ✅ **disko end-to-end** against a virtual disk: ESP + LUKS2 + btrfs
  (`@root`/`@home`/`@nix`/`@log`); the by-id device swap verified + documented.
- ✅ **The complete system builds and closes** — first real `nix build`
  (evaluated before, never built): `nixos-system-ares` with grub-2.12 +
  os-prober + our theme, CUDA llama-cpp, NVIDIA driver, wine, and all six
  jv-* services + jarvisd + jv-act; `switch-to-configuration` uses grub.
  **It found two genuine build bugs CI could not** (eval-only): `jv-act`
  cargoRoot/subdir and `piper-tts` missing `pathvalidate` — both fixed
  and re-built green. (CUDA/NVIDIA blob downloads are flaky from this
  connection; first attempt failed on them, a retry completed — runbook C
  notes to re-run `nixos-install` on a transient fetch drop.)
- ✅ **GRUB boot change** is in the built system (theme + os-prober in the
  closure, bootloader uses grub).

**Pens-down on code until ares boots.** First-run-on-ares items: GRUB
menu rendering + Windows chainload, `nixos-install` + bootloader, and
`jarvis-doctor` (expected-fail table in README).

## Waiting for the machine

- GRUB actually booting + the themed OS chooser + generations submenu.
- Windows chainload via os-prober (+ manual `extraEntries` fallback).
- Every Phase 1/2 exit-checklist item (all hardware- or boot-dependent).
- `jarvis-doctor` all-PASS on real hardware.
