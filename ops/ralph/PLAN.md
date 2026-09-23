# Ralph loop — PLAN (the prioritized backlog; the loop edits this)

Priority ladder: **UI/UX first** (blueprint §06), then features/backlog, then
creative additions. Mark items `[x]` done with the commit hash. Add follow-ups
you discover. Keep items small enough to finish in one iteration.

## Track A — UI/UX (Quickshell/QML HUD + workspace) — PRIMARY
The HUD is a bus CONSUMER: it subscribes to real topics and reflects them
truthfully. Never fake a sensor/state indicator (invariant 10).

- [x] A1. Quickshell skeleton: a minimal shell that launches under Niri as a
      non-focus-stealing overlay layer (layer-shell, `exclusive_zone` 0, no
      keyboard focus). Prove it loads; qmllint clean. — 49046db
      (pkg `.#jv-hud`, qmllint `-W 0` in checkPhase, user unit installed but
      not auto-started; `JV_HUD_SELFTEST=1 jv-hud` proves the surface maps.
      Still needs a human to eyeball it once on ares — the sandbox has no
      compositor, so "it maps" is verified by construction, not by sight.)
- [x] A2. Theme singleton: a QML `Theme` object holding the blueprint §06 tokens
      (ground #090D12/#0C1116, ember #F0714A, teal #4FB8BF, text tiers) sourced
      from `personality/`. Everything else consumes it. — <HASH>
      (`personality/theme.toml` is the source of truth; `tools/gen_theme_qml.py`
      compiles it to `shell/jv-hud/Theme.qml` + `qmldir`; `--check` runs inside
      the jv-hud build, so a drifted theme cannot be built. Tests:
      `bash ops/ralph/runtests.sh tools`.)
- [ ] A3. "Jarvis state" HUD element driven by REAL `speech.state` + `audio.wake`
      from the bus: idle / listening / speaking / interrupted. Ember accent only
      when genuinely active. This is the first real, data-backed UI.
- [ ] A4. Live mic indicator from `audio.vad`/`audio.wake` — truthful, not fakeable;
      off when no signal. (Camera indicator waits for a vision-phase signal.)
- [ ] A5. A tiny bus client for QML (do this BEFORE A3 — A3 has no real frames
      to show until it exists) (or a thin bridge) so HUD elements subscribe to
      the Unix-socket bus without violating invariant 1 (consumer only, no direct
      imports into other services).
- [ ] A7. Motion primitives on top of A2: a `Ease` Behavior (Theme.easeMs) and a
      `prefers-reduced-motion` switch every animated element honours, so "motion
      off" is one place and not a rule each element remembers. Blocked on nothing;
      worth doing next to A3 so the first moving pixel already obeys it.
- [ ] A8. Font packaging: theme.toml names Archivo + JetBrains Mono, but nothing
      declares them in the system yet — a missing font silently becomes a
      different look. Add both to `fonts.packages` (its own small commit).
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
- A1 — jv-hud Quickshell layer-shell skeleton (49046db, 2026-09-23)
- A2 — theme tokens in personality/theme.toml -> generated Theme singleton
  (<HASH>, 2026-09-24)
