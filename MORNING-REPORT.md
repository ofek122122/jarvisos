# Morning report — Phase 2 overnight (2026-08-22)

Good morning. Phase 2 ("It acts") is built end-to-end on the Windows
side, CI green on every step. I stopped here — did **not** start Phase 3,
per your instruction.

## The three things to check first

1. **`services/jv-act/` — read every line, then decide wiring.** This is
   the invariant-3 gate. It's built, 11 tests pass, but it is
   deliberately **not** in `modules/jarvis-services.nix` and runs
   nowhere. Start with `tools.toml` (the capability registry — the
   security surface) and `src/service.rs` (the validation gauntlet +
   confirm flow). Nothing acts on the machine until you've done this.
2. **`DECISIONS-pending.md` — ~14 calls I made while you slept.** The
   ones most worth your eye: `suspicious`-verdict = refuse-in-v0 (I did
   NOT wire the compat→confirm override — flagged as couples-two-services-
   early); `dialog.listen` as a shared no-wake primitive; the follow-up
   trickle heuristic. Overrule anything and I'll change it.
3. **First-boot onboarding — is the *meeting* right?** Read
   `personality/system.md` (now a template — no user baked in) and
   `services/jv-brain/jv_brain/onboarding.py` (the spoken scripts). This
   is the "meet whoever installs it" flow you asked for; the words are
   mine and yours to rewrite. `jv-onboard --reset` re-runs it.

## What's done (7 commits, all CI-green)

| Item | State |
|---|---|
| 8 additive schemas | frozen-v1 untouched; codegen extended for scalar arrays |
| jv-context | window events + 1 Hz system; **pre-seeded** title blocklist |
| **jv-act** | **built + 11 tests, NOT WIRED — REVIEW-REQUIRED** |
| jv-brain v1 | registry tool calling; 5-call cap; hallucinations rejected |
| jv-compat + jv-guard | fingerprint→screen→confine→install; **fail-closed** |
| windows-compat.nix | binfmt + wine/umu/bottles/clamav/bwrap |
| Greeting v0 + onboarding | de-hardcoded; profile store; meeting; corrections |

Test totals now: Rust — jarvisd (8) + jv-act (11); Python — pylib,
jv-ears, jv-voice, jv-context (13), jv-brain (23), jv-guard (6),
jv-compat (15), harness. CI jobs: flake eval, bindings drift, jarvisd
(+jv-act) tests+clippy, python suite. All green at HEAD (`c54eb6a`).

## Decisions that carved against earlier grain (want your nod)

- **`dialog.listen`** — a bounded (≤60s, reason-audited) no-wake window.
  It's the one sanctioned exception to wake-every-time, used by both
  confirmations and onboarding. Ears stays dumb; the requester interprets.
- **close-window = benign**, so **no v0 tool triggers the confirm flow in
  real use** — the flow is fully built and tested, just waiting for a
  genuinely destructive tool (Phase 3+). You approved this in the Q&A;
  restating because it means "a destructive tool asks first" (exit item
  4) is proven by test, not yet by a live tool.
- **suspicious verdict refuses in v0** rather than half-wiring the
  compat→act override before the HUD exists.

## Mocked / waits for ares (all tagged `TODO(machine)`)

- jv-act **not wired** pending your review (then it needs the machine too).
- Real executors: gtk-launch / niri msg / wpctl / playerctl / fd / rg /
  xdg-open (jv-act), ClamAV real scan (guard), wine-in-bwrap install
  (compat), niri event-stream field-verification (context), mic/speakers.
- `nix/jarvis-python.nix` builds (openwakeword/piper/psutil envs) — first
  `nixos-rebuild build`; evaluation is CI-checked, builds are not.
- Brain GGUFs (~9.8 GB) not fetched locally.
- Voice `intensity` still **0.4 provisional** — the four samples in
  `harness/fixtures/voice-samples/` are still waiting for your ears.

## Exit checklist (all need ares; none run yet)

Items 1–3 (open/volume/close), 4 (destructive asks), 5 (.exe→prefix),
6 (EICAR blocked aloud), 7 (`jv act-log`), 8 (you've read jv-act). The
logic behind each is tested behind mocks; the machine is the proving
ground.

## Not done / explicitly deferred

- The compat→confirm override for `suspicious` (needs the confirm surface).
- jv-guard drift-watch (systemd/boot-entry/listener auditing) — the brief
  scoped guard v0 to screening; drift is a later pass.
- Recipe DB ships empty (`recipes/` has only the README) — real recipes
  come as you install real apps.

Nothing was blocked. No frozen schema was changed; no Phase 0 boot config
was touched.
