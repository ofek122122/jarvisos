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

- [x] A6. `sys.health` glance: a quiet, edge-docked readout of service health +
      llm rung, 0 fps when nothing changes. — 7406009
      (`core/HealthState.qml` decides — 35 new QML tests, 22 mutations run
      through them — and `HealthPlate.qml` draws the SHORT list: what is not
      well, worst first, and NOTHING when every service heard from says `ok`.
      The roster is who has SPOKEN: nothing on the bus announces which
      services are supposed to be running, so a service that never started is
      absent rather than dead. A heartbeat expires after the two periods the
      schema grants it, on ONE timer armed for the soonest deadline in the
      roster — a HUD with nothing on the bus runs no timer at all. Anything
      unreadable (wrong `v`, hedged `conf`, a body naming another service, no
      `period_s`, a state word outside the enum) is `unknown` and reported,
      and `unknown`/`lost` rank ABOVE `degraded`. The llm rung shows only
      when the brain is on the CPU floor, and never off a stale heartbeat.
      Also landed: `BusModel.publishersOf(topic)`, forwarded by `Bus`.
      Tests: `bash ops/ralph/qmltest.sh`, `bash ops/ralph/runtests.sh tools`.)
- [x] A10. The surface properties that make the HUD safe are asserted, not
      assumed. — fe43c88
      (Three gates in `tools/tests/test_gen_theme_qml.py`: every Quickshell
      window in shell/jv-hud binds `keyboardFocus: None`, `focusable: false`,
      `exclusionMode: Ignore`, `layer: Top`, `color: "transparent"` exactly
      once to exactly that value, `mask` is an EMPTY `Region {}`, and any
      `exclusiveZone` is 0 — qmllint only proved those names RESOLVE, and
      would have been as happy with `.Exclusive`. Per WINDOW, not per file, so
      a second surface is covered the day it is written; it parses each
      window's own lines, so the self-test marker's nested `color:
      Theme.ground` is not mistaken for the surface's. Plus: nothing in the
      HUD may reach for the keyboard, and nothing may wait on a pointer the
      empty mask can never deliver. A gate, deliberately NOT a `HudSurface`
      component — no way to run Quickshell here, so a change to the
      window-creation path would be verified by qmllint and nothing else.
      18 mutations, 18 caught. Also landed: `tools/tests` is a CI job, so the
      theme-drift check and the A7/A15/A10 gates stop depending on the loop
      remembering to run them. Still NOT proven: that Quickshell applies the
      properties — that needs a compositor, i.e. a human on ares. Tests:
      `bash ops/ralph/runtests.sh tools`.)

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
- [x] B4. `jv act-log` / `jv confirm` are tested, and act-log stopped lying.
      — 3a3e8ec
      (Reading/tailing moved into `jarvisd::cli` — `act_log_render`,
      `act_audit_path_from`, `act_log_exit_code` — and an unreadable line is
      now RENDERED, warned about, and exits 1 instead of being skipped in
      silence: the line most likely to be torn is the last one written, i.e.
      the action that was running when something went wrong. `jv confirm`'s
      frame is pinned against the frozen `action.confirm` v1 binding, since
      jv-act acts only on kind=answer + answered_by=cli. Fallout:
      `broker::from_value_named` (the bus spells enums as snake_case strings,
      which `rmpv::ext::from_value` refuses — no Rust consumer could read a
      generated body back) and `common::subscribe_live` (the broker does not
      ack a Sub, so subscribing then spawning a one-shot publisher was a
      latent flake). 46 tests green, 14 mutations caught. Tests:
      `bash ops/ralph/cargotest.sh jarvisd`, gate `nix build .#jarvisd`.)

- [ ] B5. `jv act-log` has no way to ask a question: it prints the whole file
      (or `--tail N`) and nothing else. The two questions a human actually has
      after something happened are "what did jv-act do in the last 10 minutes"
      and "show me everything that was not `ok`" — a `--since` and a
      `--failed`/`--outcome` filter over the already-parsed entries, plus
      exit-1 when a filter matches nothing so it is scriptable. `ts_mono` and
      the ISO `ts` are both already in every entry. Small, pure, and it lands
      entirely in `cli::act_log_render`. Discovered building B4.
- [x] B6. jv-brain subscribes to `audio.wake`: a barge-in stops the answer,
      not just the speaking of it. — 4d05900
      (A spoken turn runs as a CHILD task of the input worker, so the wake
      cancels THAT answer and not the worker that must handle the utterance
      the wake belongs to; `_respond` catches its own cancellation and
      returns what it said, while a cancellation this service did not ask
      for — shutdown — still propagates. An interrupted turn publishes NO
      `brain.response`: `finish_reason` is frozen at stop|length|error, and
      "stop" would claim the answer finished while "error" would blame the
      LLM for obeying the user (proposal **R3** asks a human for the word;
      until then the count rides in sys.health's free-form `metrics` as
      `barge_ins`). The turn is still RECORDED, with a marker, and it
      records what was SENT — jv-voice drops the tail it never played.
      `Conversation.repair_open_tool_calls` answers the tool calls a turn
      cancelled mid-tool left open, which a chat template refuses: one
      interruption would otherwise poison the conversation for the whole
      session. A SILENT turn is not cancellable (a wake does not say the
      CLI stopped wanting its answer), and a wake is acted on unless the
      frame refutes itself. 50 tests green (was 37), 13 mutations, 2 missed
      and both real. Tests: `bash ops/ralph/runtests.sh jv-brain`,
      `bash ops/ralph/runtests.sh jv-voice`.)
- [ ] B7. jv-ears now has a place to state its tuning (sys.health `metrics`,
      A14), and two more constants could one day be mirrored by another
      service the way `wake_timeout_s` was: `wake_refractory_s` and
      `suppress_tail_ms` (the half-duplex tail, which jv-voice's turn
      timing is implicitly tuned against). Publish them WHEN something
      actually reads them, not before — a gauge nobody consumes is noise
      on the bus and a second thing to keep true. Noted so the next
      hand-copied constant is recognised as one. Discovered in A14.
- [ ] B3. More replay-harness fixtures for perception (recorded-session tests).

## Track C — Creative (within blueprint + invariants)
- [ ] C1. Propose and add genuinely new, on-brand capabilities here before building
      them — one line each, so a human can veto in the next `updates` read.

- [x] A12. A "thinking" state for the gap between Jarvis hearing you and you
      hearing anything back. — 7eca614
      (It used to read `idle`, which draws NOTHING, so the HUD went dark at
      the one moment the user was waiting on it. Nothing on the bus says
      "the brain accepted this", so the prompt is RECOGNISED: a wake-gated
      utterance ending (ears disarms and transcribes there; jv-brain answers
      every transcript final) or a `brain.request` from the non-voice
      frontends. Ungated speech in the room is not a prompt — ears' VAD runs
      continuously. It ends on `brain.response` (the only thing that can for
      a silent or errored reply), on the first `speaking` frame after it, or
      on a 30 s floor that mirrors no service's constant on purpose.
      `listening` still outranks everything, and what jv-voice says is
      AUDIBLE outranks thinking — observations beat inferences. The "we
      already heard this answer start" fact is a LATCH, not a binding:
      `bus.latest()` keeps only the newest frame per topic, so the
      `speaking` frame is gone once the idle after it lands, and jv-brain
      speaks one sentence per speech.say — derived, it flipped the word back
      to `thinking` once per sentence. No schema change; the bridge just
      subscribes to two already-frozen topics. 31 new QML tests, 18
      mutations run through them. Tests: `bash ops/ralph/qmltest.sh`,
      `bash ops/ralph/runtests.sh jv-hud-bridge`.)

- [x] A16. jv-voice speaks TURNS, not sentences: one answer is one
      `speaking`→`idle` pair. — 8944abe
      (jv-brain publishes one speech.say per sentence, so an answer used to
      blink once per sentence. Not only cosmetic: **jv-ears releases its
      half-duplex gate on `idle`**, so every inter-sentence idle reopened
      the microphone gate for the length of the next Piper synth while
      Jarvis was still talking. `_speak_turn` now speaks a reply_group as
      one thing — a `speaking` per sentence (each with its own say_id) and
      ONE idle when the turn drains. Two real bugs fell out: `_speaking`
      used to be cleared between sentences, so a wake in the gap was
      IGNORED and the next sentence played over the user; and `_drop_group`
      only purged what was queued, while jv-brain (which has no barge-in
      path) keeps publishing the rest of an interrupted reply — a dropped
      group is remembered now, bounded at 8. `TURN_GAP_S` (0.5 s) bridges
      the bus, not the brain, and the gap is reactive: two timing
      assertions pin that a turn resumes when the sentence LANDS and ends
      the instant a wake does. No schema change. 17 tests green (was 10),
      11 mutations caught 11. Tests: `bash ops/ralph/runtests.sh jv-voice`.)
- [x] A14. jv-ears states the budgets it enforces; the HUD reads them
      instead of mirroring them by hand. — 042438a
      (`EarsPipeline.budgets()` publishes `wake_timeout_s` off the
      SAMPLE-CLOCK count the code compares against — not off cfg, same
      reason CaptureMeter counts what the device delivered — and
      `CaptureMeter.metrics()` adds `capture_stall_s`, which rides from
      the first heartbeat because a budget is not a measurement and must
      not wait for one. Free-form `metrics`, so no schema change.
      `health_body` takes them as a REQUIRED argument, so a caller that
      forgets is a TypeError rather than a consumer guessing.
      `core/EarsBudgets.qml` is the one place that reads them; the plates
      feed them to SpeechState/MicState. The shipped defaults stay as
      fallbacks — the HUD must say something before the first heartbeat —
      but they are PINNED: tools/tests fails the build if a default drifts
      from the Python, if a mirror is renamed out of the gate's sight, if
      a ceiling drops to or below ears' tuning, or if a plate stops
      binding the reported value and quietly runs on the fallback.
      A reported budget must be a number (`"12"` is not twelve), positive
      and under a ceiling; refused means fall back, never zero. Budgets
      deliberately do NOT expire with their heartbeat the way MicState's
      gauges do — a gauge describes a moment, a budget describes how a
      service is configured. 35 mutations; the first round missed three,
      all real: an `isFinite` no input could reach (deleted — the ceiling
      does that work), a numeric string nothing tested, and a `linkUp`
      guard BusModel can never exercise. Tests:
      `bash ops/ralph/qmltest.sh`, `bash ops/ralph/runtests.sh tools`,
      `bash ops/ralph/runtests.sh jv-ears`.)
- [x] A15. `shell.qml`'s `visible` is no longer a hand-maintained OR of every
      plate's `shown`/`lit`. — 0dbe844
      (`core/PlateStack.qml` is a Column that asks its own children — `shown`
      (something true to say now) or `lit` (still on screen, fade included) —
      and the surface is mapped while `stack.anyLit`. Nothing upstream keeps a
      list. Both properties are load-bearing: `shown` MAPS the surface, and
      waiting for `lit` would deadlock, because an unmapped window has no
      animation driver to run the fade that would light it. A JS block, not a
      chain of ORs, because QML tracks what a binding READS — so a plate added
      later counts, and the early return is safe. A child that answers NEITHER
      question is counted as drawing: idle frames are cheaper than a plate that
      never appears. Two tools gates keep that branch unreachable — every direct
      child of the stack must be a `*Plate` declaring `shown`, `lit` and its own
      `visible: shown || lit`, and the surface's `visible` may not name a plate
      again. 11 new QML tests, 9 mutations run through them, 5 more through the
      gates. Tests: `bash ops/ralph/qmltest.sh`,
      `bash ops/ralph/runtests.sh tools`.)
- [x] A17. A wake newer than the open prompt ends the thinking window:
      the user abandoned that question. — b0c8262
      (Narrower than this item was written, and the tests narrowed it. The
      VOICE path was never broken: `utteranceEnded` requires
      `vad.ts >= wake.ts`, so a newer wake disqualifies the speech_end that
      WAS the prompt and the window closes by arithmetic nobody planned —
      that test passed before the fix existed and is kept as its pin. The
      real hole was `brain.request`, whose frame stays readable and stays
      the prompt: the CLI, the harness, later the HUD. Only a SPOKEN turn
      is abandoned, because only a spoken turn is what jv-brain cancels —
      `body.speak !== false`, the schema's own default. Latched, not
      derived (`bus.latest()` keeps one frame per topic, so the wake that
      ended the window is gone the moment the next detection lands), and
      checked on the WAKE edge only: a prompt arriving AFTER a wake is a
      new question, not an abandoned one. 9 new QML tests, 14 mutations,
      14 caught; two first-round survivors were real — a topic check that
      could not change an answer (deleted), and the null-wake guard, which
      only shows up as a log line and now has a `failOnWarning(/TypeError/)`
      test. Tests: `bash ops/ralph/qmltest.sh`,
      `bash ops/ralph/runtests.sh tools`.)

- [ ] A18. The voice path's immunity to A17's bug is ACCIDENTAL. Nothing
      in `core/SpeechState.qml` says "a newer wake ends a spoken prompt";
      it falls out of `prompt` being the audio.vad frame and
      `utteranceEnded` comparing that frame against the wake. It is
      pinned by a test, so it cannot break silently — but if the spoken
      prompt ever stops being the vad frame (say jv-brain one day
      publishes something that means "I accepted this", which is the
      thing A12 wanted and could not have), the bug returns and the
      abandon latch would then be the only thing standing. Either make
      the rule explicit there or leave this note as the warning. Small,
      and worth doing the day that topic appears. Discovered in A17.

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
- B4 — `jv act-log`/`jv confirm` tested; a torn audit log now reads as torn
  (3a3e8ec, 2026-09-24)
- A6 — the sys.health glance: HealthState/HealthPlate, a corner that stays
  empty until something is actually wrong (7406009, 2026-09-24)
- A12 — "thinking": the HUD stops going dark while Jarvis is working
  (7eca614, 2026-09-24)
- A16 — jv-voice speaks turns, not sentences: one answer, one speaking/idle
  pair, and the half-duplex gate stays shut across it (8944abe, 2026-09-24)
- A15 — PlateStack: the surface asks the stack whether anything is on screen,
  so the list that could rot is gone (0dbe844, 2026-09-24)
- A10 — invariant 10 gets a witness: every HUD surface's safety properties
  pinned, and tools/tests finally run in CI (fe43c88, 2026-09-24)
- A14 — jv-ears states its own budgets and the HUD stops mirroring them
  (042438a, 2026-09-24)
- B6 — the brain stops generating when the user barges in, and the turn it
  lost is recorded as interrupted (4d05900, 2026-09-24)
- A17 — the question you gave up on stops reading "thinking" (b0c8262,
  2026-09-24)
