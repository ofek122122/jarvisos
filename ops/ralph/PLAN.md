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
- [x] A3. "Jarvis state" HUD element driven by REAL `speech.state` + `audio.wake`
      from the bus: idle / listening / speaking / interrupted. Ember accent only
      when genuinely active. This is the first real, data-backed UI. — 769dcdd
      (`core/SpeechState.qml` decides — 34 tests, 17 mutations run through them;
      `StatePlate.qml` draws a dot and one word and nothing else. `idle` and
      `unknown` both draw NOTHING, so the surface is unmapped unless a frame
      earned it. `listening` is inferred, since jv-ears publishes a window
      opening and never its close: Jarvis answering or an `audio.vad`
      speech_end closes it, `interrupted` does not, and `wakeWindowS` (8 s,
      mirroring ears' `wake_timeout_s`) is only the fallback. Frames are
      refused rather than guessed at — wrong schema `v`, a wake under its own
      threshold, a hedged `conf`, no numeric `ts`. Teal for listening (the open
      mic is yours), ember for speaking. Tests: `bash ops/ralph/qmltest.sh`.)
- [x] A4. Live mic indicator — truthful, not fakeable; nothing on screen when
      no microphone is open. (Camera indicator waits for a vision-phase
      signal.) — 6796579
      (NOT from `audio.vad`/`audio.wake` as this line used to say: those are
      a claim about attention, and jv-ears' VAD runs continuously whether or
      not a wake window is open. The mic is its own claim and needed its own
      signal, so jv-ears now counts what the DEVICE delivers —
      `CaptureMeter` — and reports `mic_open` / `capture_age_s` /
      `captured_s` in sys.health's FREE-FORM `metrics`; no schema change.
      A process being alive is not evidence about a device: that is exactly
      what stayed cheerful through the 2026-09-15 mic outage.
      `core/MicState.qml` decides — 26 new QML tests, 17 mutations caught —
      and refuses rather than guesses: "I cannot tell" never collapses into
      "off". `MicPlate.qml` draws a teal dot and `MIC`, or `warn` and
      `MIC NO AUDIO` when the device is open but silent. Nothing pulses.
      Also landed: `Bus.latestFrom(topic, src)` (sys.health has one
      publisher per service) and a tools test that fails the build if
      Bus.qml forgets to forward a BusModel function. Tests:
      `bash ops/ralph/qmltest.sh`, `bash ops/ralph/runtests.sh jv-ears`.)
- [x] A5. A tiny bus client for QML so HUD elements subscribe to the Unix-socket
      bus without violating invariant 1 (consumer only). — bae8e03
      (`services/jv-hud-bridge` writes one JSON line per envelope; `Bus.qml`
      reads it with `Process` + `SplitParser`. Consumer-only is structural: the
      pump holds a `ReadOnlyBus` with no publish method. `Bus.frames` is cleared
      whenever the link drops. (The singleton was lazy; since A3 an element
      watches the bus at load, so a running HUD always runs its bridge.) Tests: `bash ops/ralph/runtests.sh jv-hud-bridge` — 25, three of
      them against a real jarvisd; smoked against the live bus on ares.)
- [x] A7. Motion primitives on top of A2: an `Ease` Behavior and one
      reduced-motion switch every animated element honours. — 245926e
      (`core/MotionPolicy.qml` decides — tested, 25 new QML tests, 8 mutations
      run through them; `Motion.qml` binds it to real sources and republishes
      the §06 durations already gated; `Ease on color {}` is the one Behavior
      every moving value uses, and its `base` picks how long a move takes,
      never whether it happens. Sources: `personality/theme.toml [motion]
      reduced_motion` + `JV_HUD_REDUCED_MOTION=1/0`. A tools test fails the
      build if any HUD QML file animates without consulting `Motion`, so the
      off switch cannot be bypassed — VERIFIED it bites. Tests:
      `bash ops/ralph/qmltest.sh`, `bash ops/ralph/runtests.sh tools`.)
- [ ] A8. Font packaging: theme.toml names Archivo + JetBrains Mono, but nothing
      declares them in the system yet — a missing font silently becomes a
      different look. Add them to `fonts.packages` (its own small commit),
      plus `fontconfig.defaultFonts` so the generic families resolve to
      them, plus a tools test asserting every `[type] family_*` in
      theme.toml is declared (or the gate does not bite).
      **Researched 2026-09-24, and it is NOT the ten-minute commit it looks
      like — decide this before writing code:** nixpkgs has no `archivo`.
      The only packaged source is `google-fonts`, and even overridden to one
      family its src is **1.1 GiB to download / 2.7 GiB unpacked**, on a
      machine that never garbage-collects (the runtime closure is small; the
      source is not, and ares builds its own system). Options: (a) pay it,
      (b) a small pinned derivation from upstream Omnibus-Type/Archivo — a
      few MB, network works, needs a rev + hash, (c) change `family_sans` to
      a face nixpkgs already carries, which is IDENTITY and a human's call
      (invariant 9), not Ralph's. Recommendation: (b).
      JetBrains Mono is already in nixpkgs (grub-theme uses it) and is the
      only face on screen today — every HUD element is mono, so the mono
      half is pure win and can land whatever is decided about the sans.
- [x] A9. Headless QML tests for the HUD, wired into jv-hud's checkPhase.
      — 4c7c048
      (Quickshell links its QML plugin into its own binary, so its types can
      never load under `qmltestrunner`. The HUD is therefore split:
      `shell/jv-hud/core/` imports QtQuick ONLY and holds the logic —
      `core/BusModel.qml`, the bus state machine, with an injected clock;
      `Bus.qml` keeps the untestable half (bridge process, respawn timer,
      ElapsedTimer) and forwards the API. 27 tests, mutation-checked 9 ways;
      they found a real bug — a NaN clock offset made unknown-age frames read
      as fresh. `nix build .#jv-hud` runs them after qmllint, and a tools test
      fails if anything in core/ imports more than QtQuick.
      **The rule for every element from here: logic goes in `core/`, and
      Quickshell files stay wiring.** Tests: `bash ops/ralph/qmltest.sh`.)

- [ ] A11. Give `Motion.onBattery` and `Motion.fullscreen` real sources. Both
      are live inputs in `core/MotionPolicy.qml` with nothing feeding them, so
      two of §06's three "stop moving" rules cannot be honoured. Needs two
      additive fields in FROZEN schemas (`context.system.on_battery`,
      `context.window.fullscreen`) — proposal **R1** in
      `docs/optimization-backlog.md`. **Blocked on human review; do not build
      this autonomously.** When the schemas land it is one binding each in
      `Motion.qml` plus the jv-context publisher work. Discovered in A7.

- [ ] A6. `sys.health` glance: a quiet, edge-docked readout of service health +
      llm rung, 0 fps when nothing changes.
- [ ] A10. `shell.qml` is still untestable by construction: the surface
      properties that make the HUD safe (keyboardFocus None, exclusionMode
      Ignore, the empty input mask) are asserted by nobody — qmllint only
      checks they resolve. A `core/` component cannot hold them, since they
      ARE Quickshell types. Probably wants a different gate: grep the file for
      the five properties, or a quickshell-run smoke test on ares. Small, and
      it closes the last unguarded corner of invariant 10. Discovered in A9.

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

- [ ] A12. A "thinking" state: between `audio.vad` speech_end and jv-voice's
      `speaking` frame, Jarvis is working and the HUD says `idle`. That
      under-claims (the safe direction), but the real signal exists —
      `brain.request`/`brain.response` are frozen schemas the bridge does not
      subscribe to. One line in `DEFAULT_TOPICS` plus one branch in
      `core/SpeechState.qml`. No schema change needed. Discovered in A3.
- [ ] A14. The HUD mirrors TWO jv-ears constants by hand — `wakeWindowS`
      (8 s, ears' `wake_timeout_s`) and `stallS` (1 s, ears'
      `CaptureMeter.STALL_S`) — because nothing publishes ears'
      configuration. Both are "keep this at or below what ears is tuned
      to" comments waiting to rot. ears already publishes free-form
      `metrics` on sys.health; reporting its own budgets there would let
      the HUD read them instead of guessing, with no schema change. Small,
      and it deletes two footguns. Discovered in A4.
- [ ] A13. `StatePlate` is drawn on EVERY monitor, because every surface
      builds one. Three copies of "LISTENING" across three screens may be
      right (you see it wherever you look) or noise. Needs a human eye on
      ares before it is worth changing. Discovered in A3.

## Done
- A1 — jv-hud Quickshell layer-shell skeleton (49046db, 2026-09-23)
- A2 — theme tokens in personality/theme.toml -> generated Theme singleton
  (6c0eafb, 2026-09-24)
- A5 — read-only bus link for QML: jv-hud-bridge + Bus.qml (bae8e03, 2026-09-24)
- B2 — jv CLI: bounded, scriptable streams + --latency (62c440f, 2026-09-24)
- A9 — headless QML tests + the core/ split that makes them possible
  (4c7c048, 2026-09-24)
- A7 — one motion switch: MotionPolicy/Motion/Ease, and a build gate that
  stops an element from animating around it (245926e, 2026-09-24)
- A3 — the first data-backed element: SpeechState + StatePlate, the HUD's
  first pixels that mean something (769dcdd, 2026-09-24)
- A4 — the recording light: CaptureMeter in jv-ears + MicState/MicPlate,
  and the counters that make it honest (6796579, 2026-09-24)
