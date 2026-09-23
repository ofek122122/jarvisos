# Ralph loop — PLAN (the prioritized backlog; the loop edits this)

Priority ladder: **UI/UX first** (blueprint §06), then features/backlog, then
creative additions. Mark items `[x]` done with the commit hash. Add follow-ups
you discover. Keep items small enough to finish in one iteration.

## Track A — UI/UX (Quickshell/QML HUD + workspace) — PRIMARY
The HUD is a bus CONSUMER: it subscribes to real topics and reflects them
truthfully. Never fake a sensor/state indicator (invariant 10).

- [ ] A1. Quickshell skeleton: a minimal shell that launches under Niri as a
      non-focus-stealing overlay layer (layer-shell, `exclusive_zone` 0, no
      keyboard focus). Prove it loads; qmllint clean.
- [ ] A2. Theme singleton: a QML `Theme` object holding the blueprint §06 tokens
      (ground #090D12/#0C1116, ember #F0714A, teal #4FB8BF, text tiers) sourced
      from `personality/` where possible. Everything else consumes it.
- [ ] A3. "Jarvis state" HUD element driven by REAL `speech.state` + `audio.wake`
      from the bus: idle / listening / speaking / interrupted. Ember accent only
      when genuinely active. This is the first real, data-backed UI.
- [ ] A4. Live mic indicator from `audio.vad`/`audio.wake` — truthful, not fakeable;
      off when no signal. (Camera indicator waits for a vision-phase signal.)
- [ ] A5. A tiny bus client for QML (or a thin bridge) so HUD elements subscribe to
      the Unix-socket bus without violating invariant 1 (consumer only, no direct
      imports into other services).
- [ ] A6. `sys.health` glance: a quiet, edge-docked readout of service health +
      llm rung, 0 fps when nothing changes.

## Track B — Features / hardening (when UI is blocked, or for variety)
- [ ] B1. Pull the next safe item from `docs/optimization-backlog.md` that is NOT
      marked human-review, and implement it under the verify gate.
- [ ] B2. `jv tap`/CLI ergonomics: small, tested improvements to the debug CLI.
- [ ] B3. More replay-harness fixtures for perception (recorded-session tests).

## Track C — Creative (within blueprint + invariants)
- [ ] C1. Propose and add genuinely new, on-brand capabilities here before building
      them — one line each, so a human can veto in the next `updates` read.

## Done
(empty — the loop appends completed items here with hashes)
