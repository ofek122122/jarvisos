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
      from `personality/`. Everything else consumes it. — 6c0eafb
      (`personality/theme.toml` is the source of truth; `tools/gen_theme_qml.py`
      compiles it to `shell/jv-hud/Theme.qml` + `qmldir`; `--check` runs inside
      the jv-hud build, so a drifted theme cannot be built. Tests:
      `bash ops/ralph/runtests.sh tools`.)
- [ ] A3. "Jarvis state" HUD element driven by REAL `speech.state` + `audio.wake`
      from the bus: idle / listening / speaking / interrupted. Ember accent only
      when genuinely active. This is the first real, data-backed UI.
- [ ] A4. Live mic indicator from `audio.vad`/`audio.wake` — truthful, not fakeable;
      off when no signal. (Camera indicator waits for a vision-phase signal.)
- [x] A5. A tiny bus client for QML so HUD elements subscribe to the Unix-socket
      bus without violating invariant 1 (consumer only). — bae8e03
      (`services/jv-hud-bridge` writes one JSON line per envelope; `Bus.qml`
      reads it with `Process` + `SplitParser`. Consumer-only is structural: the
      pump holds a `ReadOnlyBus` with no publish method. `Bus.frames` is cleared
      whenever the link drops. The singleton is lazy, so an idle HUD runs no
      bridge. Tests: `bash ops/ralph/runtests.sh jv-hud-bridge` — 25, three of
      them against a real jarvisd; smoked against the live bus on ares.)
- [ ] A7. Motion primitives on top of A2: a `Ease` Behavior (Theme.easeMs) and a
      `prefers-reduced-motion` switch every animated element honours, so "motion
      off" is one place and not a rule each element remembers. Blocked on nothing;
      worth doing next to A3 so the first moving pixel already obeys it.
- [ ] A8. Font packaging: theme.toml names Archivo + JetBrains Mono, but nothing
      declares them in the system yet — a missing font silently becomes a
      different look. Add both to `fonts.packages` (its own small commit).
- [ ] A9. Headless QML tests for the HUD (`qmltestrunner` / `qml -platform
      offscreen`) wired into jv-hud's checkPhase. Nothing on the QML side is
      tested today: `Bus.ingest` — JSON parsing, clearing the frame cache on
      link down, the monotonic-clock pinning — is verified only by reading it,
      and qmllint does not catch a typo'd self-assignment inside a file. This
      makes every element from A3 onward cheap to test. Discovered building A5.

- [ ] A6. `sys.health` glance: a quiet, edge-docked readout of service health +
      llm rung, 0 fps when nothing changes.

## Track B — Features / hardening (when UI is blocked, or for variety)
- [~] B1. Pull the next safe item from `docs/optimization-backlog.md` that is NOT
      marked human-review, and implement it under the verify gate. **Checked
      2026-09-24: there is no such item — all 27 are human-review-gated.** Leave
      this here in case a future pass adds auto-safe findings; do not re-check it
      every iteration.
- [x] B2. `jv tap`/CLI ergonomics: small, tested improvements to the debug CLI.
      — 62c440f
      (Every stream is bounded: `-n/--count`, `--for SECS`, Ctrl-C; an unmet
      `--count` exits 1 so `jv` is scriptable. `jv tap --latency` prints a
      per-topic p50/p95/max summary; end-to-end is reported once per utterance
      as time-to-FIRST-word, and the utterance map is a bounded ring. Logic
      moved to `jarvisd::cli`; 30 tests green, 8 of them running the real `jv`
      binary against a real broker. Tests: `bash ops/ralph/cargotest.sh jarvisd`,
      gate `nix build .#jarvisd`.)
- [ ] B4. `jv act-log` / `jv confirm` are still untested: reading+tailing the
      audit file has no coverage, and nothing asserts the `action.confirm` frame
      `jv confirm` publishes is the shape jv-act's `resolve_voice` expects.
      Small, and it guards the one path where the CLI can cause a real action.
      Discovered building B2.
- [ ] B3. More replay-harness fixtures for perception (recorded-session tests).

## Track C — Creative (within blueprint + invariants)
- [ ] C1. Propose and add genuinely new, on-brand capabilities here before building
      them — one line each, so a human can veto in the next `updates` read.

## Done
- A1 — jv-hud Quickshell layer-shell skeleton (49046db, 2026-09-23)
- A2 — theme tokens in personality/theme.toml -> generated Theme singleton
  (6c0eafb, 2026-09-24)
- A5 — read-only bus link for QML: jv-hud-bridge + Bus.qml (bae8e03, 2026-09-24)
