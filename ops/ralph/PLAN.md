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
- [x] A8. Font packaging: theme.toml named Archivo + JetBrains Mono and
      nothing installed either. — 5e5ef8d
      (`modules/fonts.nix` reads the family names out of
      `personality/theme.toml` with `builtins.fromTOML` — the same source
      `tools/gen_theme_qml.py` compiles for the HUD, so the two cannot
      disagree about which faces are wanted. What the module owns is the
      binding from a NAME to something that provides it, and every step
      throws rather than guesses: an unbound family is an eval throw, a
      provider theme.toml does not name fails an assertion, a `family_<role>`
      with no fontconfig generic throws (theme.toml calls the generics the
      fallbacks; a role without one falls back to nothing). The system
      installs the face it CHECKED — each goes through a derivation that asks
      `fc-scan`, the thing that resolves the name at runtime, and fails if the
      family is not in there. "Provides the family", not "every file is that
      family": jetbrains-mono legitimately ships JetBrains Mono NL alongside.
      **The check caught a real one immediately**: as a plain symlinkJoin,
      `fc-match monospace` answered `JetBrainsMono-Regular.woff2`, because
      nixpkgs ships every face three times and fontconfig indexes web fonts
      too — whether a WOFF2 renders depends on how the reading FreeType was
      built. Outline formats only now; 0 woff2 in the built font path.
      `pkgs/archivo` is option (b) from the research: upstream pinned at a
      commit (no tags exist), 66 MiB of source for 3.4 MiB of face, BASE WIDTH
      only, with an install check that all 18 faces report family `Archivo`
      and that the upright Regular is there. Plus `enableDefaultPackages`, so
      the generic fallbacks resolve to something. Two tools gates: no QML file
      may name a family of its own, and theme.toml's faces must equal
      providerOf's keys (the module checks that at eval; tools/tests is where
      it can run without nix, i.e. CI's bare checkout). `Theme.familySans`
      still has no reader — every HUD element is mono, as A8 always said;
      Archivo is packaged because the toml declares it. 11 mutations, 11
      caught. Tests: `bash ops/ralph/runtests.sh tools`.)
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

- [x] B5. `jv act-log` can be asked a question. — da134b9
      (`--since` — a duration back from now, 10m/2h/90s/3d, or a UTC
      timestamp — plus `--failed` and a repeatable `--outcome WORD`, the two
      of them mutually exclusive since `--failed` IS `--outcome` negated.
      ONE rule governs it: **a filter narrows what is shown and never hides
      what it could not evaluate** — an unreadable line has no ts and no
      outcome, a missing/nonsense `ts` cannot be proven older than the
      cutoff, a non-string `outcome` has not been shown to be `ok`; all
      three survive every filter and print `?` in the column the filter was
      about. A `--failed` view quietly missing the damaged entries is the
      same lie `act_log_render` already refuses about a torn line. Filters
      run BEFORE `--tail`, so `--failed --tail 1` is the newest FAILURE.
      Exit follows grep: a question nothing answers exits 1 and prints
      nothing (on a healthy machine "nothing failed" is the good answer),
      which is also the only thing between a typo'd `--outcome denyed` and a
      reassuring empty listing — so the words are deliberately NOT validated
      against jv-act's enum (a second hand-copy of a human-review-only file,
      and an old `jv` would refuse to display a record it did not
      recognise). `--tail` is a window, not a question, so `--tail 0` still
      exits 0. Wall clock, not `ts_mono`: `ts_mono` restarts at every boot
      and no human can type one. `iso_to_epoch` is the hand-written inverse
      of jv-act's `now_iso` (no chrono for one date function) and refuses an
      offset rather than ignoring it. 57 tests green (was 36), 27 mutations,
      27 caught. Tests: `bash ops/ralph/cargotest.sh jarvisd`.)

- [~] B8. WITHDRAWN — the premise is false, found while picking work in
      iteration 45. B8 assumed "jv-guard and jv-compat write their own
      records"; they do not. Nothing under `services/jv-guard/` or
      `services/jv-compat/` opens a file for writing, and neither has a
      state dir (`JARVIS_STATE_DIR` is set for one unit only) — both
      services publish their lifecycle on the bus and are read from there
      (`guard.verdict` by the HUD since A51, `compat.install` by nobody
      yet, which is A52). So there is no second caller for a shared record
      reader because there is no second record. If one is ever written,
      the shared-reader idea is still the right one; it is not a task
      today. Discovered in B5, withdrawn in B19's iteration.
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
- [x] B3. More replay-harness fixtures for perception (recorded-session
      tests). — d2f9634
      (The harness had existed since Phase 3 with nothing recorded in it.
      `harness/fixtures/sessions/` now holds four: what the REAL pipeline
      — real openWakeWord, real Silero VAD, real faster-whisper —
      published while listening to each committed fixture WAV, so the
      requirements REVIEW-ears.md states are asserted twice: against the
      live models when installed, and against the recording ALWAYS, on a
      machine with no weights. `ts` is `EarsPipeline.clock()` (the sample
      clock, formerly a private `_t()` with no callers), so a session
      reproduces to the sample and a diff means perception changed rather
      than the machine being busy — and the header's `boot_id` is the
      `sample-clock` SENTINEL, because borrowing a real one would claim,
      in the field that exists to check the claim, that these ts line up
      against a live recording. `harness/session.py` is now the only
      reader of the format and can be asked `problems()`: envelope keys,
      closed bodies, required fields, `v`, and per-`(src, topic)` ts/seq
      ordering — all off the GENERATED bindings, never a hand-copy of
      schemas/. An unknown topic and a seq gap are deliberately NOT
      problems (the B5 rule: never refuse to show what you merely do not
      recognise). Nothing rots quietly: with models installed jv-ears
      re-records every WAV through the generator's own `frames_for()` and
      compares which frames arrived, when, and in what state, plus the
      normalized finals — not model scores, not partial texts, which are
      float noise from the machine that ran it. 78 harness tests green
      (was 3), 36 jv-ears (was 32). Tests:
      `bash ops/ralph/runtests.sh harness`, `... jv-ears`.)

- [x] B9. The HUD's QML tests hand-type the JSON lines the bridge writes;
      B3 means there are now REAL recordings to hand them instead. — 36a486d
      (`tests/tst_sessionreplay.qml`, a new file rather than an addition to
      `tst_speechstate.qml`: it shares no helper with it — a replay sends
      recorded lines, not composed ones. Each session goes through
      `core/BusModel` + `core/SpeechState` and the trajectory is asserted in
      the recording's own seconds — clean `unknown -> listening@1.44 ->
      thinking@3.76`, pause `1.36 -> 6.64` across 1.2 s of real mid-sentence
      silence with NO flicker (the trajectory is every change, so a flicker
      is two extra transitions), no-wake `unknown` start to finish. Two
      assertions are about the coupling and need real data: the recorded
      wakes clear SpeechState's self-consistency bar with openWakeWord's own
      score/conf (a 0.995 bar fails on BOTH the music bed's 0.963 and the
      quiet room's 0.990), and the longest recorded utterance (5.28 s) fits
      inside ears' 8 s `wake_timeout_s` — tune that below what a person says
      and a test fails instead of the plate blanking mid-sentence. QML cannot
      read a repo file, so `tools/gen_sessions_qml.py` compiles the
      recordings verbatim into `tests/Sessions.qml` — A2's theme pattern,
      with `--check` in the jv-hud build (VERIFIED: moving a wake 0.2 s fails
      the build). The generator knows nothing about schemas and is
      stdlib-only on purpose, so it runs under the build's plain python3 and
      CI's bare checkout. 250 QML tests (was 238), 52 tools tests (was 30).
      Tests: `bash ops/ralph/qmltest.sh`, `bash ops/ralph/runtests.sh tools`.)

- [ ] B10. Every trajectory in the replay test ends in "thinking" and then
      times out, because the committed sessions are jv-ears ALONE — nothing
      in the repo records a whole turn. Record one session off the LIVE bus
      on ares during a single real spoken turn (`harness/record.py` has
      always been able to; `live_header()` exists for exactly this), commit
      it, and the HUD replay gets the other half: `speaking`, the gaps
      between streamed sentences, the return to idle. It would also be the
      first committed session containing `sys.health`, which is why
      `MicState` and `HealthState` cannot be replayed at all today. Needs a
      human at the machine for one utterance — the SAME ask as the standing
      "nobody has looked at the HUD" item, so ask for both together.
      Discovered in B9.

- [x] B11. `jv health` can be asked a question. — c8b2967
      (`jv health --check` listens for one window — `--for SECS`, default 6,
      a nominal heartbeat period plus a margin — then prints one line per
      service HEARD FROM, worst first, the llm rung when jv-brain reports
      it, and a footer; exit 0 only when every service heard from is `ok`.
      Built on the same three rules as `core/HealthState.qml`, because they
      belong to `sys.health` and not to either reader: the roster is who has
      spoken, a heartbeat speaks for two of its own periods, and unreadable
      is `unknown` and ranks above `degraded`. Silence is NOT an all-clear —
      a bus nobody heartbeats on exits 1 — and `--check` conflicts with
      `--count` so a usage error (exit 2) is never read as "not well". 51
      unit + 27 integration tests, 22 mutations, 22 caught after two real
      survivors were fixed. Tests: `bash ops/ralph/cargotest.sh jarvisd`.)

- [ ] B12. `jv health --check` can say a service is not well and can never
      say one is MISSING: on a machine where jv-ears died at boot it prints
      a short, clean, exit-0 report. That is exactly R5's gap, now arriving
      in a SECOND reader — which is what R5 said it was waiting for, so the
      proposal is worth a human's attention with two callers behind it
      rather than one. Nothing to build until `sys.roster` exists; when it
      does this is one more section in the report and one more reason to
      exit 1. Discovered in B11.

- [x] B13. The one number the Phase 1 budget is judged on stops containing
      the user's own voice. — ee96c43
      (`jv tap --latency` printed "VAD start -> first speech.say" and
      nothing else, so the 5.4 s measured on ares on 2026-09-15 could not
      be held against the 2.5 s budget at all: 2-3 s of it was the user
      speaking. A turn is now split at the boundaries jv-ears itself
      publishes — `spoke` (you, talking), `hold` (its `vad_min_silence_ms`,
      the silence it deliberately sits through to bridge a mid-sentence
      pause), `respond` (ASR + brain + bus) — with a p50/p95/max per span
      and a stated rule: the machine's share is `hold + respond`. It does
      NOT re-state the budget; which span the 2.5 s applies to is a human's
      call, and the point is that the call can now be made against data.
      The hold is read off jv-ears' `sys.health` `metrics`
      (`vad_min_silence_s`, added for this reader — the free-form section
      `wake_timeout_s` already uses, so no schema change; B7's rule is
      "publish when something reads it", and this is the reader). There is
      deliberately NO fallback to ears' default, unlike the HUD, which has
      to draw something: an instrument that substitutes a constant for a
      reading is how a number stops meaning its label, so an unheard
      budget prints `?` and the table says which gauge was missing. Two
      real bugs fell out: an `audio.transcript` partial — emitted PART-WAY
      through an utterance — was allowed to define its start, silently
      measuring those turns short, and the one integration test covering
      any of this published `{"kind": "speech_start"}` on `audio.vad`,
      where the schema says `event`, which nothing noticed because the old
      reader never looked at the field. Anchored on the frames' own `ts`
      now rather than on when the tap got round to them. 63 unit + 31
      integration tests (was 57 + 27); seven mutations, one real survivor
      fixed. Tests: `bash ops/ralph/cargotest.sh jarvisd`,
      `bash ops/ralph/runtests.sh jv-ears`.)

- [x] B14. `respond` stops being one number over two services. — f7f1572
      (`jv tap --latency` splits `respond` at the `audio.transcript` final
      into `hear` — jv-ears' ASR — and `think` — jv-brain to its first word,
      plus a bus hop each way. No new publisher, no schema change: jv-ears
      runs whisper AFTER publishing `speech_end` and publishes the final
      when it is done, so that frame IS the seam. The final is an anchor
      INSIDE a turn and not a boundary, and is treated as one: it annotates
      an utterance `audio.vad` already bounded and never conjures one, only
      `kind: final` counts, and a seam that does not sit inside the span it
      would divide refuses BOTH halves rather than publishing a negative.
      An utterance with no final — jv-ears publishes none for one its ASR
      read as empty — prints `?` for both and keeps `respond` whole.
      Fixed on the way: `silent_broker()` in the tests was not silent. A
      tokio interval's first tick fires IMMEDIATELY, so jarvisd published a
      heartbeat at t=0, before its accept loop had taken a connection —
      reaching nobody on an idle machine and whoever was already accepted
      on a busy one. The new tests' load made that deterministic; the first
      beat is now due one whole period in. 71 unit + 8 bus + 32 integration
      (was 63 + 7 + 31), green five consecutive times; 11 mutations, 11
      caught after two real survivors were fixed. Tests:
      `bash ops/ralph/cargotest.sh jarvisd`.)

- [x] B16. `think` stops being one number over the model and the queue.
      — ceca526
      (jv-brain states the one moment nothing on the bus marks — when the
      completion request went out — as `llm_first_say_ms` plus a turn
      counter `llm_first_says` in its `sys.health` `metrics` (free-form by
      schema, so no schema change). `jv tap --latency` divides `think`
      into `model` (request -> first `speech.say`) and `wait` (the two bus
      hops, the input queue, and jv-brain's own pre-LLM work), as two
      table rows and one short second line per turn — the `>>> turn` line
      itself is deliberately no wider while B17 is open. Three refusals do
      most of the work: a turn that ran TOOLS publishes no gauge at all
      (tool time, confirm window included, is inside `think` and is not
      the model's, so the table prints `think unsplit` and names the gauge
      it wanted); the gauge is bound to its turn by frame ORDER, because
      jv-brain heartbeats immediately after the word it measures on the
      same connection, with the counter telling a fresh gauge from the
      same number re-stated on the next periodic beat; and the FIRST count
      a tap sees is recorded and not consumed, because it may describe a
      turn from before the tap connected. jv-brain 57 tests (was 53),
      jarvisd 82+8+34 (was 71+8+32); 18 mutations, 3 real survivors, all
      pinned. Tests: `bash ops/ralph/runtests.sh jv-brain`,
      `bash ops/ralph/cargotest.sh jarvisd`.)

- [x] B18. `jv health --check` answers "is generation slow right now?"
      without starting a tap and speaking to the machine. — 4bd95fd
      (The `llm` line gained `first_say=<ms> turn_age=<s>`, the gauge's
      second reader, which is what B7 says a gauge needs. The wording
      care this item asked for became the feature: jv-brain re-states the
      same number on every periodic beat forever, so the AGE is
      load-bearing, and it comes off `llm_first_says`. The count rose
      inside the window -> the turn is the frame that raised it and the
      age is a measurement (`turn_age=1.5s`); it never moved -> the turn
      predates the first heartbeat we read and the only honest statement
      is a lower bound (`turn_age>=6.0s`). Three more refusals, each with
      a test: the FIRST count is never fresh (it may predate the
      connection — the tap loop's rule), a count going BACKWARDS is a
      restart and not a newer turn, and a readable beat that dropped the
      gauge takes the number with it. `turn_age` and not "idle" because a
      tool turn publishes no gauge. jarvisd 89+8+36 (was 84+8+34); five
      mutations, all caught. Tests:
      `bash ops/ralph/cargotest.sh jarvisd`.)

- [ ] B20. Nothing has read the new `llm ... first_say= turn_age=` line
      on a real turn — the same complaint B17 makes about `>>> turn`, and
      now from the same missing two minutes of a human at a terminal. The
      two questions worth answering together: does `turn_age>=` read as
      "we could not date this" or as noise, and is the line still one
      terminal width once a rung, a backend, a number and an age are on
      it. Cheap to change afterwards — it is one `format!` and its
      tests — and not worth guessing at beforehand. Discovered in B18.

- [x] B19. A tool turn's `think` was the only span in the table with no
      decomposition at all, and the longest one a user can hit. — e8df1a2
      (`tool` is the UNION of the `intent.action` -> `action.result` round
      trips inside a turn's `think` — not their sum, since two outstanding
      requests are one moment of jv-act's time, and not the bracket from
      first request to last result, since jv-brain runs a completion
      between serial calls. It is jv-act's execution AND, for a confirming
      tool, the whole 15 s window it waited in, which is never spoken and
      today reads as a slow LLM. Five refusals, each tested: an unanswered
      request, a round trip outside the `think` it divides, a turn with no
      ASR seam, a turn past `ACTS_PER_TURN = 32` (the runaway tool loop is
      real — backlog #5 — and past the cap the COUNT survives and the
      measurement does not), and a frame that named nobody. `tool_calls`
      rides beside `tool_ms` because "no tool" and "a tool nobody could
      time" both print `?`. B17's width worry is respected: it prints its
      own line, like jv-brain's `wait`/`model` split, and `>>> turn` keeps
      its six numbers. No new publisher, no schema change. 106+8+38 tests
      (was 89+8+36), 13 mutations, 13 caught. Tests:
      `bash ops/ralph/cargotest.sh jarvisd`.)

- [x] B21. `tool` is one number over a window that is mostly the human
      deciding, and the half a faster machine could never shorten is
      exactly the half it cannot name. — cd47fde
      (`you` is the UNION of the `action.confirm` request -> answer
      windows inside a turn, and `ran` is `tool - you`. The seam that
      worked was NOT the one this item guessed at: `action.result`'s
      `duration_ms` is measured from jv-act's `t0`, BEFORE the
      confirmation, so it is the whole request including the wait — the
      same number, not its complement. The two `action.confirm` frames
      are, and they carry the `request_id` `intent.action` already named,
      so the join is `action.result`'s. Five refusals, each tested: no
      question asked (not a 0 ms window), a question still open when the
      reply landed, a window not NESTED inside its own call's round trip
      — which is also what makes `ran` a subtraction that cannot go
      negative — a `tool` nobody could measure, and a question for a
      request this tap never saw. jv-act ECHOES the answer it acted on
      onto the topic `jv confirm` publishes on, so one decision is two
      frames and the earliest is when the user stopped deciding. Its own
      line under the `tool` line; `>>> turn` keeps its six numbers. Also
      closed a hole in B19's width check, which filtered out 4-space
      indented lines and would have exempted these two rows from it.
      119+8+39 tests (was 106+8+38), seven mutations, seven caught.
      Tests: `bash ops/ralph/cargotest.sh jarvisd`.)

- [x] B22. B17's complaint now has a machine-checked half and an
      unchecked one. — dd0857b
      (The assertion was written first and failed at 133 columns — and not
      because of the id. The line was already 96 with the five-character
      id every test used: six numbers plus a label each do not fit a
      terminal at all, so B22 could not be closed by adding a test. A
      turn's report is now a LADDER, each rung dividing a span the rung
      above it valued — `total spoke hold`, `respond is hear + think`,
      `think includes tool`, `tool is you + ran` — in one grammar (`X is
      A + B` for a partition, `X includes Y` for a share) that
      `brain_split` already spoke. `Turn::lines` owns which rungs exist
      and in what order, so no rung can name a span no printed line
      valued; `confirm_line` gained a `think` guard so that holds of the
      TYPE and not only of its one caller. `short_id` caps the id at
      `ID_COLUMNS` = 11 — eight characters and `...`; an id that fits is
      never touched, and two ids that start alike print alike, which is a
      test and not a silence. The width test runs at the widest input
      that can reach these lines and names each bound: the id is capped
      by construction, both counts are two digits via `ACTS_PER_TURN`,
      and six-digit spans (16.7 minutes) are the one bound assumed rather
      than enforced. It carries A34's kind of control — a line far UNDER
      budget fails too. Tables held to the same 80. Also fixed a
      PRE-EXISTING flake: the confirm test compared three independently
      rounded numbers with `< 1.0` where the rounding error is exactly 1.
      124+8+39 tests (was 119+8+39), twelve mutations, twelve caught.
      Tests: `bash ops/ralph/cargotest.sh jarvisd`.)

- [ ] B23. The per-frame `jv tap --latency` hop line
      (`{topic:<20} {src:<12} seq={seq:<8} hop={ms:8.2}ms`) is formatted
      in `jv.rs` and is the one line the tap writes as a REPORT that B22's
      width test cannot reach — the test lives in `cli.rs` and walks what
      `cli.rs` renders. It is 61 columns for a 20-character topic and
      widens with the topic, which `{:<20}` pads and does not truncate;
      `context.window.changed` is already 22. Either move the `format!`
      into `cli.rs` beside the tables it belongs with (where the existing
      test picks it up for free) or give it its own assertion. Small, and
      it closes the last hole in "every report line fits". Discovered in
      B22.

- [ ] B17. Every `>>> turn` line is now six numbers wide and a summary
      table six rows deep, and `jv tap --latency` prints a hop table above
      both. Nothing has ever looked at that output on a real turn — the
      only eyes on it are tests with 20 ms holds. Worth one read-through
      by a human the first time B10's live recording is made, together
      with A13/A27: if the live line wraps in a terminal it is worse than
      the one number it replaced. Discovered in B14.
      **HALF CLOSED by B22** (dd0857b): "does it wrap" is a test now, at
      the widest input that can reach those lines, and the line that
      prompted this worry turned out to be 133 columns on a live id. What
      is left is the half that genuinely needs eyes, and it is a NEW
      question because the output changed: four lines per tool turn is
      more output than one, and does the ladder read as a decomposition or
      as noise? Same two minutes at a terminal, same trigger (B10/A28),
      now shared with B20.

- [ ] B15. Nothing measures the last hop. `jv tap` stops at `speech.say`,
      which is jv-brain handing words to jv-voice — the user hears nothing
      until Piper has synthesised and the device has started playing.
      **CORRECTION (found while building A37): `speech.state` `speaking`
      is NOT that moment.** `_speak_one` in jv-voice publishes `speaking`
      BEFORE it hands the text to Piper (service.py: `await
      self._state("speaking", say_id)` and only then the synth executor),
      so the frame means "jv-voice accepted this utterance", and the whole
      CPU synthesis of the first sentence sits between it and the first
      audible sample. Measuring to it and calling the result "until you
      hear it" is exactly the "a number stops meaning its label" failure
      B13 was written against. So this needs a decision first and the
      options are not equal: moving the publish to after synth would make
      the HUD go dark for the length of a synth (StatePlate reads the same
      frame) and would leave an utterance interrupted mid-synth with an
      `interrupted` it never said `speaking` for; publishing time-to-first
      -audio as a jv-voice `sys.health` gauge is B16's shape and is
      per-turn data on a heartbeat topic. Not a schema question either way
      — `speech.state`'s enum is frozen and neither option adds a state. Adding it would
      make `total` the thing the budget actually names ("hey jarvis" →
      spoken reply) instead of a proxy for it. Worth doing WITH the human
      decision B13 leaves open, because moving the end of the measurement
      and choosing which span the budget covers are one conversation.
      Discovered in B13.

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

- [x] A19. The hand-check from iteration 21 is a build gate. — be1b264
      (`jv-fonts-resolve` in `system.checks`: a check, not a dependency, so
      `nixos-rebuild build` runs it and nothing of it enters the closure. It
      resolves against `config.fonts.fontconfig.confPackages` — the conf
      packages the fontconfig module really links into /etc — reading the
      real `fonts.conf` with one edit, its absolute `<include>` of conf.d,
      because there is no /etc inside a build. Two rules, both stated as
      PROPERTIES rather than as a copy of the mechanism that implements them:
      every installed file is an sfnt by its own first four bytes (NOT by
      extension, which is what the find filter goes by; NOT by fc-scan's
      `%{fontformat}`, which calls a WOFF2 "TrueType" whenever the reading
      FreeType has woff2 support — which is exactly the property at issue),
      and asking for each family by name AND for the generic behind it
      answers that family in a file this module linked (the only check that
      covers `defaultFonts` at all). A generic is only a question if
      fontconfig has heard of it: `49-sansserif.conf` answers any
      unrecognised family with the sans-serif default, so a misspelled alias
      resolved to Archivo and passed — the vocabulary gate greps fontconfig's
      OWN `conf.avail`, never the conf.d this module helped generate.
      `genericOf` now carries both spellings per role (the NixOS option and
      fontconfig's word). Two tools gates because CI instantiates the system
      but never builds it: the check must stay wired into `system.checks`
      (unwiring it is invisible to everything else), and genericOf's roles
      must equal theme.toml's. Worth recording: with the filter widened,
      `fc-match` still answered the .otf — the resolve half alone would NOT
      have caught the regression this item was about. 12 mutations, 12
      caught. Tests: `bash ops/ralph/runtests.sh tools`.)

- [x] A20. The confirmation you can only HEAR gets a readable copy. — 6779708
      (`core/ConfirmState.qml` decides — 34 QML tests, 15 mutations run
      through them — and `ConfirmPlate.qml` draws jv-act's question, its
      words verbatim, with the tool id underneath. jv-act stops in front of
      every destructive tool (invariant 3), speaks the question and opens a
      15 s window in which silence is a no; until now nothing about that
      handshake was visible, so a question you did not hear was answered by
      a timeout you never knew was running. The plate cannot ANSWER, and
      that is structural rather than a decision: the surface has an empty
      input region and takes no keyboard (invariant 10, pinned by a tools
      test), so there is no path from these pixels to an authorization —
      answering stays where invariant 3 put it, your voice or `jv confirm`.
      The request has to be LATCHED, and the bus forces it: `bus.latest()`
      keeps one frame per topic and the ANSWER lands on the SAME topic as
      the request, so a derived "something is pending" would see the
      question only in the instant it arrived. Three ways to let go — an
      answer naming THIS `request_id` (not any answer: jv-act keeps a
      single outstanding slot, but the HUD is not what enforces that), the
      link dropping, and the window jv-act DECLARED in the frame running
      out (A14's rule; `windowFallbackS` is for a request that declares
      none and mirrors no service's constant). Refusing to read a frame is
      never the same as being answered: an unreadable frame leaves a
      pending question exactly where it was. A mutation found a real one —
      the words are gated on the question still being OPEN, not on the
      latch still being held, or an expired question stays readable and
      answerable-looking. New build gate: every topic a `core/` element
      reads must be one jv-hud-bridge subscribes to — an element reading an
      unsubscribed topic builds, lints, passes its own tests and draws
      nothing forever on a surface that is unmapped by design. Tests:
      `bash ops/ralph/qmltest.sh`, `bash ops/ralph/runtests.sh tools`,
      `... jv-hud-bridge`.)

- [ ] A21. `ConfirmPlate` shows that a window is open and never how much of
      it is left. The window closing is a real signal and §06 would let it
      move a pixel — a hairline that shortens, say — but it would be the
      only thing in this HUD that animates continuously, and it has to go
      through `Motion`, which means the one user who asked for no motion
      would get the one indicator with no sense of time. Whether that reads
      as urgency or as a nag is a question for a human eye on ares, so it
      was deliberately not built blind. Discovered in A20.

- [ ] A22. The plate simply vanishes when the question is answered — the
      same exit for granted, denied and timed out. Those are three
      different facts and the user saw none of them; "it went away" is
      indistinguishable from "it expired while I was reading it". A brief,
      quiet outcome (the word, then gone) is the obvious answer and is also
      the first thing in this HUD that would be on screen for a fixed time
      rather than for as long as its signal is true — a new rule, worth
      deciding deliberately rather than as a side effect. Discovered in A20.

- [x] A23. The HUD says when it has stopped being able to see the machine.
      — 34f9af8
      (Every element in this HUD refuses rather than guesses — MicState will
      not call a mic it cannot see "off", SpeechState will not call an
      invisible bus "idle", BusModel empties its cache on `up:false` — and
      every one of those refusals draws the SAME NOTHING that a calm, well
      machine draws. So the corner meant two opposite things with the same
      pixels, and the more dangerous one was silent: a dark recording light
      over a microphone the HUD simply could not see. `core/LinkState.qml`
      decides — 22 QML tests, 18 mutations run through them — and
      `LinkPlate.qml` says NO BUS / SENSOR STATE UNKNOWN plus the bridge's
      own explanation ("connect: ...", "bus closed the connection"),
      clipped to a glance and stripped of line breaks it would otherwise
      break the plate with. No dot and no accent: this is the panel talking
      about its own pipe, never a sensor row — the rule the self-test
      marker already stated for "bus up / bus down", now where a user can
      see it. First in the stack, because it qualifies everything under it.
      The judgement is the WAIT: a down link is ordinary (jv-hud-bridge
      retries 0.5 s after jarvisd restarts, Bus.qml respawns the bridge
      2 s after it dies), and a plate that blinked through every rebuild
      would be ignored on the day it was true — so nothing is said for 5 s,
      and a new tools gate fails the build if EITHER of those cadences,
      in two files that have no reason to think about the HUD, ever grows
      past the grace (VERIFIED it bites from both sides). The wait belongs
      to the OUTAGE, not to the last line about it: the bridge re-announces
      "down" on every failed retry with a backoff climbing to 8 s, so an
      element that re-armed on each one would push the report past its own
      grace forever. Three mutation survivors were all real and all fixed:
      a reported outage handing its verdict to the next brief blip, the
      outage the HUD BOOTS into (a machine where nothing is running —
      `linked` is false from the first instant, so no change signal ever
      fires for it) never being timed at all, and an `onBusChanged` no
      path could reach, deleted. Tests: `bash ops/ralph/qmltest.sh`,
      `bash ops/ralph/runtests.sh tools`.)

- [x] A24. `LinkPlate` reports the pipe; nothing reports the PROCESSES.
      **Written up as proposal R5** in `docs/optimization-backlog.md`; the
      build stays blocked on a human. No code: the deliverable IS R5.
      (A bus that is up says only that jarvisd is up, and the HUD's roster
      (A6) is "who has spoken": a service that DIED is caught — HealthState
      expires a heartbeat at `period_s * 2` — but one that never started is
      absent, and absent is indistinguishable from not installed and from a
      well machine. R5 proposes one new frozen topic, `sys.roster`,
      published by jarvisd: the services this generation expects (written
      into jarvisd's config by the module that declares the units, so the
      list is a property of the running generation) and the ones holding a
      bus connection right now. jarvisd because it is the only process that
      already knows the second list and gains no privilege by saying so.
      Two shapes were considered and rejected in writing: baking the roster
      into the HUD at build time, which answers only the half that never
      changes and puts a fact about the system inside a view; and jv-context
      polling systemd, which answers "the unit is active" when the question
      is "can it speak on the bus".)

- [x] A26. The HUD stops being unable to say what it heard. — d7ac325
      (`core/HeardState.qml` decides — 34 QML tests, 25 mutations run
      through them — and `HeardPlate.qml` draws jv-ears' transcript
      verbatim, teal-dotted, under the state plate. Until now the commonest
      failure of a voice assistant was the one thing this screen had no
      word for: "it misheard me", "it never heard me" and "it is just slow"
      were the same dark corner, and the user found out only when a wrong
      answer came back. FINALS ONLY, which is the schema's own line —
      partials are provisional and only finals are acted on — and it is why
      the line must be LATCHED: partials ride the same topic, so a derived
      reading would blank itself the instant the user started speaking
      again. The exit is a REAL SIGNAL and deliberately not a timer: the
      line leaves when Jarvis starts answering, because from then on the
      answer is the better report on whether you were heard. That is what
      keeps this out of the "on screen for a fixed duration" territory A22
      flagged as needing a human decision. `holdS` is only the backstop for
      a turn nobody ever answers, and a new tools gate fails the build if it
      ever drifts from SpeechState's `thinkWindowS` — the two are the same
      claim about the same turn. NO CONFIDENCE BAR, and the recordings are
      why: the three real finals in `harness/fixtures/sessions/` carry
      0.886, 0.863 and 0.739 and all three transcribe their sentence
      correctly, so any bar inside that spread flags a word-perfect
      transcript and any bar below it never fires — exp(avg_logprob) is
      measuring the room. `tst_sessionreplay` pins that against the real
      numbers, so changing the decision costs an argument with data. The
      privacy line held because jv-ears transcribes ONLY wake-gated
      utterances: everything on this topic was said TO Jarvis, and
      `speech-no-wake` — a real room, real speech, no wake word, no
      transcript at all — is replayed through the element to say so. Two
      mutation survivors were real: an `idle` jv-voice read as an answer
      (the words would vanish while the user was still waiting), and a
      final with no `ts` DISPLACING a good line instead of being refused at
      the door. Two more survive as equivalences and are recorded in the
      journal. Tests: `bash ops/ralph/qmltest.sh`,
      `bash ops/ralph/runtests.sh tools`, `... jv-hud-bridge`.)

- [ ] A27. The heard line is drawn on EVERY monitor, and it is the user's
      own words — which makes A13's question ("three copies of LISTENING
      across three screens: right, or noise?") sharper rather than new.
      There is also no way to turn it off. Both are the same human call and
      should be answered together with A13 — and as of A30 by looking at
      `docs/hud/screens/02-heard-desk.png`, which is your own sentence
      repeated across three real-sized monitors, rather than at ares.
      Nothing was built toward either answer: the plate is
      one `HeardPlate {}` in the stack and a `personality/` switch would be
      the obvious shape if the answer is "sometimes". Discovered in A26.

- [ ] A28. B10 would now buy more than it did. A live-bus recording of one
      real turn is the only way to replay the heard line LEAVING: the exit
      is a `speech.state` `speaking` frame, and nothing committed has ever
      contained one. Today `tst_sessionreplay` can prove the words arrive
      and can only prove the departure with hand-written frames — which is
      exactly the gap B9 set out to close. Same ask, more to gain.
      Discovered in A26.

- [ ] A25. The blind plate cannot say how long the HUD has been blind, for
      the same reason A21's window cannot shorten: a duration on screen is
      the first thing in this HUD that would animate continuously. "NO BUS
      FOR 4 MIN" as a still, coarse line (recomputed on a slow timer, not
      per frame) may be the version that fits §06 — a minute-resolution
      label is not motion. Worth one human opinion alongside A21/A22 rather
      than three separate answers to the same question. Discovered in A23.

- [ ] A13. `StatePlate` is drawn on EVERY monitor, because every surface
      builds one. Three copies of "LISTENING" across three screens may be
      right (you see it wherever you look) or noise. **No longer needs a
      seat at ares**: `docs/hud/screens/02-heard-desk.png` is that exact
      picture, at ares' real monitor sizes (A30). It is a two-minute human
      opinion now, and it should be answered together with A27.
      Discovered in A3.

- [x] A29. The HUD can be looked at without sitting at ares. — fea019c
      (`docs/hud/*.png`: seven shots of one real surface at its real size,
      written by `ops/ralph/hudshots.sh`. The plates are the real files,
      the theme is generated from `personality/theme.toml`, the faces are
      JetBrains Mono and Archivo pinned from the flake, and every frame
      goes in through the same `core/BusModel.qml` the running HUD uses —
      three shots replay `harness/fixtures/sessions` verbatim (B3) and the
      rest are composed, which `docs/hud/README.md` states per shot,
      because a composed picture is a picture of an intention and only a
      recorded one is evidence about the machine. The harness STAGES a
      copy of `shell/jv-hud` with exactly two files replaced — `Bus.qml`
      and `Motion.qml`, the only two that import Quickshell, whose QML
      plugin is linked into the quickshell binary — so `pkgs/jv-hud` is
      untouched and the shipped shell has no idea this exists. Three
      duplications are gated in `tools/tests/test_hudshots.py` (the scene's
      plate stack against shell.qml's, the stubs' members against the real
      singletons', the shots taken against the shots committed); all four
      gates were mutation-checked. The PNGs are not byte-compared — a pixel
      assertion breaks when a font ships a new version. Tests:
      `bash ops/ralph/runtests.sh tools`.)

- [x] A30. The surface stops being verified by reading the source.
      — d56b12e
      (`ops/ralph/hudscreens.sh` runs the SHIPPED `.#jv-hud` — quickshell,
      layer-shell, its own bridge — against a real jarvisd on a headless
      wlroots compositor carrying ares' three monitors, and photographs
      every screen with grim into `docs/hud/screens/`. Nothing is staged,
      which is the one claim A29's sheet cannot make and the first thing a
      future run would give up, so a tools gate reads the driver and fails
      on any `cp`/`ln -s`/`shell/jv-hud` outside a comment. The pictures
      are the smaller half: no PNG is written unless the HUD drew on EVERY
      monitor and only inside the 300x560 box shell.qml anchors to the
      top-right corner at `inset_px`; unless the seat's keyboard is the
      same node it was before the HUD existed; unless the quiet shot comes
      back pixel-identical to the bare desktop on all three screens; and
      unless every workspace still has its whole monitor. Five mutations
      built and photographed, three caught by three different checks
      (anchored left, `WlrKeyboardFocus.Exclusive`, a health plate that
      reports a well machine); a sixth, one surface instead of one per
      screen, caught by the corner check. ONE EQUIVALENCE RECORDED: on a
      CORNER-anchored surface the layer-shell protocol ignores an
      exclusive zone entirely, so `ExclusionMode.Normal` and `.Auto` both
      change nothing — the anchor is what keeps the HUD out of the way and
      `Ignore` is the belt to its braces. That check is kept for the day
      the anchors change and VERIFIED to bite then (left+right+top with
      `Auto` → usable 2560x880). Not ares: sway is not Niri and the
      outputs are headless, so this answers "on all three, in the right
      corner, costing nothing" and never "does it look right". 10 tools
      mutations, 10 caught. Tests: `bash ops/ralph/runtests.sh tools`.)

- [ ] A31. A29 cannot photograph time. A21 (the confirm window shortening),
      A22 (granted / denied / timed out leaving differently) and A25 (how
      long the HUD has been blind) are all questions about what a plate
      does over seconds, and a still frame answers none of them — the sheet
      makes those three EASIER to reason about and no closer to decided.
      The honest still-image version is a strip: the same shot at fade
      start, mid and settled, side by side, which is a picture of a
      transition without pretending to be motion. Cheap once A29 exists
      (one more loop in the driver); worth building only if the human
      answering A21/A22/A25 says the stills were not enough. Discovered in
      A29.

- [x] A32. The empty input mask stops being a claim nobody tested.
      — 48d9c74
      (`probe_click_through` in tools/hudscreens/shoot.py runs after the
      photographs, puts an ordinary Wayland toplevel under the HUD on the
      primary monitor and a second one on a side monitor to hold the
      keyboard, and clicks three points: a CONTROL clear of the surface
      — without it a harness whose clicks went nowhere would report a
      perfect pass-through — a pixel the HUD actually PAINTED, read out
      of the capture rather than guessed, and a point inside the 300x560
      box it painted NOTHING on, because an input region that tracks the
      content is the likelier mistake and looks reasonable in a diff. All
      three must end with the keyboard on the window underneath. It starts
      NO jarvisd: the probe needs a lit state that does not expire, every
      other one is a frame ageing out, and a bus the HUD cannot see is the
      one thing it says indefinitely. The witness is sway's own ROUTING,
      read back over IPC — `node_at_coords` consults each layer surface's
      input region before it looks at a window — and NOT the client's
      wl_pointer, which never fires because a headless seat advertises no
      pointer capability; the README says so. Three mutations, three
      caught by two different points: no mask at all (the painted pixel),
      a mask over only the lower unpainted half of the box (the third
      point, which is how that point earned its place), and a LinkState
      grace so long the plate never arrives (the guard against the whole
      stage going vacuous). The compositor config moved into
      `sheet.sway_config()` and gained `focus_follows_mouse no`, because
      `cursor set` is a warp and a compositor that follows the mouse would
      move focus before any button existed. 83 tools tests (was 77), eight
      mutations through six new gates. Tests:
      `bash ops/ralph/runtests.sh tools`.)

- [ ] A33. The probe answers CLICK and says nothing about scroll or
      hover, which ride the same input region and are the two a user
      would notice next — a scroll eaten over a plate is a page that
      stops moving for no reason. `swaymsg seat - cursor` has no scroll
      verb, so this needs the axis event to come from somewhere else
      (a virtual pointer held open for the length of the probe, which
      would also give the client a real wl_pointer and turn the whole
      measurement from sway's routing into the client's own log). Worth
      it the day the mask is ever edited; not before. Discovered in A32.

- [x] A34. "0 fps when idle" stops being an argument about how Qt works.
      — d420e24
      (`probe_idle_frames` in tools/hudscreens/shoot.py counts the HUD's
      own Wayland commits — libwayland's `WAYLAND_DEBUG` log, client side,
      which is what actually costs a composite and needs no cooperation
      from Qt — over two six-second windows: a live bus with nothing on it
      (surface unmapped) and a plate on screen with no further input. Both
      read ZERO. The instrument moved into `sheet.py` so a test with no
      compositor can execute it over real log lines. The point of the
      whole thing is the two CONTROLS, because every way of breaking a
      probe that passes on zero also returns zero: each window is paired
      with a stretch that MUST contain commits — a real jv-ears heartbeat
      waking the HUD (44), the blind plate arriving (42) — counted by the
      same code through the same log. Both controls bit for real: the
      first version's pattern expected `wl_surface@41` where this
      libwayland writes `wl_surface#41`, and deleting `WAYLAND_DEBUG` from
      the lit stage fails there rather than reporting a perfect zero. The
      headline mutation — a 4 px ember square on `loops:
      Animation.Infinite` inside LinkPlate, which qmllint, 347 QML tests
      and every photograph accept without complaint — reads 1110 commits
      in 6 s. 89 tools tests (was 83). Tests:
      `bash ops/ralph/runtests.sh tools`, `bash ops/ralph/hudscreens.sh`.)

- [ ] A35. The QUIET window is very nearly tautological, and the pulsing
      mutation proved it: with a HUD animating at ~62 fps on three
      surfaces, the quiet window still read 0, because an unmapped surface
      cannot commit whatever the scene graph is doing. All the work is
      done by the LIT window — and there is exactly ONE lit state that can
      be held still long enough to measure: LinkPlate with no bus. Every
      other plate is a frame ageing out (a heartbeat speaks for two of its
      own periods, a confirmation for jv-act's window), so ConfirmPlate,
      HeardPlate, StatePlate, MicPlate and HealthPlate have never been
      watched standing still. A heartbeat with a long `period_s` would buy
      the mic and health plates; the other three need a frame clock the
      harness can hold. Worth building the day a second element is allowed
      to move, which is exactly what A21/A25 are asking for. Discovered in
      A34. **A42 DID the cheaper half (4c63122): the lit-and-still
      measurement now exists on a live bus, with `OutputPlate` as the
      plate. What is left of A35 is the other four plates — tracked as
      A43, which inherits A42's `feed_snapshots`.**

- [ ] A36. The probe counts frames and never milliseconds. §06 budgets the
      ambient scene at "< 2 ms of GPU per frame AND 0 fps when idle", and
      only the second half is measurable here: sway renders with pixman,
      in software, on a headless backend, so no frame in this harness took
      any time on a 1660 SUPER. The first half is also not yet a question
      — there IS no ambient scene; the whole HUD is static glass, and the
      parallax/reticle layers §06 budgets are Phase 5 wgpu work that no
      sensor feeds yet. Re-read this the day the first moving layer lands,
      and measure it on ares rather than here. Discovered in A34.

- [x] A37. The HUD says what Jarvis did to your machine when it did not
      work. — 7bc1eb5
      (`core/ActionState.qml` decides — 35 QML tests, 8 mutations run
      through them — and `ActionPlate.qml` draws ACTION FAILED, the
      registry tool name verbatim, and the schema's own error word, in
      `risk` rather than ember. Invariant 3 gives one process the right to
      change this computer and the HUD could show the QUESTION jv-act asks
      before a destructive tool (A20) and never the outcome of any tool at
      all. Three decisions: FAILURES ONLY (a success draws nothing — the
      machine visibly doing the thing is the report that it was done,
      HealthPlate's argument applied to actions); NEVER A TOOL IT CANNOT
      PROVE (`action.result` has a request_id and no tool name, the name
      is in the `intent.action` that asked, `bus.latest()` holds one frame
      per topic — so the ids must match or the failure is reported
      nameless, and the pair is latched TOGETHER at the moment the failure
      is accepted because both sources keep moving); and NOT `denied` /
      `confirm_timeout`, which are how a CONFIRMATION ended and therefore
      A22's question for a human — passed over here, and passed over as NO
      NEWS so a denial cannot silently clear a real failure. The exit is a
      real signal and not a timer, the same three HeardState uses: Jarvis
      starting to explain, a newer outcome (including a SUCCESS — holding
      a failure under a retry that worked describes a machine that is not
      the one in front of you), and the link dropping, with `holdS` as the
      backstop. `intent.action` + `action.result` joined the bridge's
      topic list, and a new tools gate fails the build if any element
      under `core/` so much as names `args` or `detail` — the 08-action
      shot composes frames carrying both, so the sheet is the
      demonstration. Tests: `bash ops/ralph/qmltest.sh` (384, was 347),
      `bash ops/ralph/runtests.sh tools` (90), `... jv-hud-bridge`.)

- [ ] A38. `ActionPlate` is drawn on EVERY monitor, like every other
      plate, so the A13/A27 question ("three copies across three screens:
      right, or noise?") now has a third instance — and this one is the
      least ignorable of the three, because it is the one that says
      something went wrong. Nothing was built toward an answer: it is one
      `ActionPlate {}` in the stack, and a `personality/` switch is the
      obvious shape if the answer is "sometimes". Answer it with A13/A27,
      not separately. Discovered in A37. **A40 added a fourth instance
      (`OutputPlate`), which does not change the question.** **A52 added a
      fifth (`InstallPlate`) — three copies of "the app did not install",
      one per monitor — and does not change it either.**

- [ ] A39. A22 now has a ready-made shape if the human answering it wants
      one. `ActionState` deliberately passes over `denied` and
      `confirm_timeout` because they are how a confirmation ENDED, but it
      already reads the topic, already latches, and already leaves on a
      real signal — so "the word, then gone" would be one line in
      `apply()` and one more `reportableReasons` entry, with no timer and
      no new rule. Do NOT build it until A22 is answered; this note exists
      so that answering it is cheap. Discovered in A37.

- [x] A40. The HUD stops saying SPEAKING while the room is silent.
      — b643c22
      (`core/OutputState.qml` decides — 36 QML tests, 17 mutations run
      through them — and `OutputPlate.qml` draws ONE line, OUTPUT MUTED or
      OUTPUT AT ZERO, directly under the word it qualifies. SPEAKING is a
      claim about jv-voice and not about the room: with the default sink
      muted, jv-voice accepts the utterance, Piper synthesises it,
      PortAudio plays it, every service heartbeats `ok`, and you hear
      nothing — no error anywhere in the sequence, which makes it the
      failure with the least evidence attached. Four decisions: ONLY WHILE
      SPEAKING (a muted machine is a choice, not news — §06's earned
      emptiness); SILENCE, NOT QUIETNESS (muted or zero, with no threshold
      on "too quiet", which would be a guess about your room — and two
      words because they are two different controls, a toggle and a
      slider); THE RAW jv-voice WORD rather than `SpeechState`'s, which
      lets the microphone claim outrank the speaking one; and A LIVE
      READING, NOT A LATCH — both inputs describe the present, so there is
      nothing to forget, and the one timer in the file exists to stop
      BELIEVING a frame, armed on the earlier of two deadlines (three 1 Hz
      periods for the snapshot, the rate stated by the schema itself; 30 s
      under a `speaking` frame a dead jv-voice would never retract).
      `context.system` joined the bridge's topic list — the first
      NON-EVENT topic the HUD subscribes to, a frame every second forever
      — so the idle probe's QUIET window stopped being a bus with nothing
      on it and became a bus TALKING: six ordinary snapshots over six
      seconds, 0 Wayland commits, both controls still biting at 45 and 41.
      Tests: `bash ops/ralph/qmltest.sh` (423, was 384),
      `bash ops/ralph/runtests.sh tools` (90), `... jv-hud-bridge` (25),
      `bash ops/ralph/hudshots.sh`, `bash ops/ralph/hudscreens.sh`.)

- [x] A41. **The one place `OutputPlate` could be confidently wrong**, and
      it no longer is. — d504ba4
      (jv-voice publishes `output_device_pinned` in `sys.health.metrics`
      on every heartbeat including the degraded ones — 1 if it opened a
      device it was configured to open, 0 if it took PortAudio's default
      — and `core/OutputState.qml` says OUTPUT MUTED only on the 0. No
      schema change: `metrics` is free-form numbers, which is also why
      this is a 1/0 and not a device name. **Unknown is not 0**: silence
      from jv-voice, a v2 body, a hedged beat, a missing `metrics`, a
      non-numeric gauge, a 2, and another service's gauge on the topic
      all leave the plate dark — it never speaks about a sink nobody
      said Jarvis uses. The gauge is deliberately NOT aged, unlike the
      two frames either side of it: it is jv-voice's configuration
      rather than a reading of the world, and `sayWindowS` is already
      the backstop for a dead jv-voice. The knob is real —
      `JARVIS_VOICE_OUTPUT_DEVICE`, empty reads as unset, and
      `SoundDevicePlayer` passes it to `sd.play`. Both screenshot
      harnesses learned the fact and one taught back: publishing the
      beat ONCE made `HealthPlate` arrive mid-window saying *jv-voice
      lost*, so the live-lit feed now carries the heartbeat with the
      snapshot. Seven mutations, seven caught — the link guard only
      after `test_a_bus_still_handing_out_frames_on_a_dead_link` gained
      an `ownSink` assertion, because a third reader's guard is
      unobservable through `unheard`. Tests:
      `bash ops/ralph/qmltest.sh` (435, was 423),
      `bash ops/ralph/runtests.sh jv-voice` (27, was 17), `... tools`
      (96), `bash ops/ralph/hudshots.sh`, `bash ops/ralph/hudscreens.sh`.
      The other half — PipeWire muting jv-voice's STREAM while the sink
      is open — is proposal **R6** in `docs/optimization-backlog.md`.)

- [x] A42. "0 fps when idle" stops being measured only on a HUD with no
      bus. — 4c63122
      (A third window in `probe_idle_frames`: a real broker, jv-voice
      `speaking`, and a MUTED `context.system` snapshot re-published at
      1 Hz, so SPEAKING + OUTPUT MUTED sit on screen for the whole six
      seconds while the `seq` moves, OutputState's expiry timer re-arms
      and every binding downstream of the snapshot re-evaluates to the
      same value. 0 commits under 6 snapshots. Lit in TWO steps — audible
      sink first, then the mute — and the region must grow DOWNWARDS with
      its top and right edges unmoved, so the thing held still provably
      includes A40's plate and not just StatePlate; the first check of
      A40's decision through a compositor. The box is re-measured BEFORE
      the count is judged, because a plate that expired mid-window commits
      the traffic of leaving. Three mutations: the feed replaced by a
      sleep is caught on the box (shrunk back to SPEAKING alone, 28
      commits of OutputPlate leaving); an infinite animation is caught by
      A34's window too, so it proves nothing here; and a "freshness" fade
      bound to `ageOf(snapshot)` — no animation, no timer, invisible to
      every photograph — reads 0 / 0 / **18**, which is the whole
      justification for the window. Two premises were wrong first time:
      the top-LEFT corner does move (OUTPUT MUTED is a longer line than
      SPEAKING), and `feed_snapshots` has to run inside the WAIT loops too
      or a slow capture outlasts `snapshotS`. Tests:
      `bash ops/ralph/runtests.sh tools` (96), `bash ops/ralph/qmltest.sh`
      (423), `bash ops/ralph/hudscreens.sh`.)

- [x] A43. The mic and health plates get watched standing still.
      — fed202f
      (The idle probe's fourth window. ONE jv-ears heartbeat describing a
      device that is open and delivering nothing says both `MIC NO AUDIO`
      — `core/MicState.qml` against jv-ears' own `capture_stall_s` — and
      `jv-ears DEGRADED`, so re-publishing that single frame at 1 Hz
      holds two plates. No long `period_s` was needed: jv-ears' real 5 is
      long enough, and faking one would be a picture of a machine that
      does not exist. Lit in two steps like A42's, growing 41 px
      downwards through `sheet.grew_downwards`. Carries one guard the
      other three do not, and it is window 3's inverted: those plates
      OUTLIVE a six-second silence, so the feed is the subject rather
      than life support and a dead feed would pass every other check — so
      the heartbeats inside the window are counted and fewer than two
      fails. Read 0; verified it bites with A42's "freshness" fade moved
      to the mic dot, which windows 1-3 all read 0 for and this one read
      18. The failure message's first guess was wrong and was kept:
      HealthPlate's `Repeater` model IS rebuilt on every heartbeat and it
      costs no commit. Also tightened the probe's own gates, which were
      greps of the form "somewhere after LIVE AND LIT" that this window
      was about to satisfy on window 3's behalf. Tests:
      `bash ops/ralph/runtests.sh tools` (110),
      `bash ops/ralph/hudscreens.sh`.)

- [x] A48. The two plates whose words come off a latch get watched
      standing still. — 9e322a1
      (The cheap first step answered the question and the answer was the
      good one: a re-published frame RE-TAKES the latch — the envelope
      replaced, `requestKey`/`transcriptKey` moved, `armExpiry`/`armHold`
      run, a one-shot timer restarted — and does NOT re-run the fade,
      because both elements clear `expired` before anything downstream
      reads it and `pending`/`heard` never go false in between. So the
      fifth idle window holds HEARD and CONFIRM on a live bus at 1 Hz and
      reads 0. It is the only one of the five with a latch in it: every
      plate the other four hold is a reading. The mutation is A21's own
      temptation in its most considerate form — the CONFIRM dot's opacity
      bound to the age of jv-act's question, no animation, no timer —
      windows 1-4 read 0 and the fifth read 15, three surfaces times five
      re-publishes, box unmoved. The other refusal is written down: the
      declared window is jv-act's 15 s and not the 600 that would have
      made the feed unnecessary, which means the latches outlive a
      six-second silence and A43's `< 2` guard is needed here too. A test
      pins the declared window against the schema's own description.
      `03-confirm` and the window now read one `CONFIRM_REQUEST`. Tests:
      `bash ops/ralph/runtests.sh tools` (117), `bash ops/ralph/qmltest.sh`
      (435, unchanged — no QML edited), `bash ops/ralph/hudscreens.sh`.)

- [x] A49. `ActionPlate` was the only plate in the stack that had never
      been watched standing still. — 4b62514
      (The decision the item asked for was made and it was NO SIXTH PAIR
      OF PROCESSES: the same broker, the same shell and the same TURN as
      A48's window, carried to its end — the user answers, jv-act runs
      `fs.trash`, it fails. The probe still starts exactly five shells
      and the WAYLAND_DEBUG count pins that. Running the story forward
      earned a step nothing in this harness had ever taken: an outcome
      landing while `ConfirmPlate` still stood would be jv-act reporting
      a tool it was still asking permission for, so the answer goes on
      the bus first and the region has to SHRINK — `grew_downwards` read
      with its arguments swapped — back to (2284, 16, 2543, 84), the box
      the heard line held before it was asked, to the pixel. The failure
      then arrives 78 px taller for 36 commits. Window: 0 commits in 6 s
      under 5 re-publishes, and the re-publish does more here than in
      A48 — re-taking `ActionState.failure` also re-runs `toolFor()`,
      which re-reads `intent.action` and re-resolves the tool name from
      scratch, a binding that reads a SECOND topic every time the first
      arrives. Mutation: the ACTION FAILED dot's opacity bound to the age
      of the failure — qmllint-clean, builds, windows 1-5 read 0, the
      sixth read 18, box unmoved. Also paid A20's honesty debt: `fs.trash`
      is not in jv-act's registry and the sheet now says so, pinned by a
      test. Tests: `bash ops/ralph/runtests.sh tools` (125),
      `bash ops/ralph/qmltest.sh` (435, unchanged),
      `bash ops/ralph/hudscreens.sh`.)

- [ ] A50. **Human review.** The entire confirmation path has never once
      been driven by the registry this machine deploys.
      `services/jv-act/tools.toml` is v0 — "observe + benign only" — and
      the confirmation rule is structural: ONLY destructive and
      privileged tools are ever confirmed. So there is no tool on ares
      today that can produce an `action.confirm` at all, and everything
      downstream of one — `ConfirmPlate`, `ConfirmState`, jv-act's 15 s
      window, its yes/no classifier, the `03-confirm` shot and two idle
      windows — is exercised by composed frames only. The machinery is
      built and reviewed and the composition is fair (registry v0 says
      the destructive tools "arrive in later phases with their own
      review"); what is missing is the first real one. Adding it is a
      `services/jv-act/**` change, which GUARDRAILS forbids this loop
      from touching, so it goes to `docs/optimization-backlog.md` as a
      proposal for a human. Discovered in A49.

- [x] A44. The live-lit window held a state nobody had photographed.
      — 3052b8f
      (`docs/hud/screens/04-unheard-primary.png`: SPEAKING with OUTPUT
      MUTED under it, on the 1440p primary, through the real shell. Two
      mechanisms had to exist first. `hold` — a frame list the settle
      republishes at jv-context's 1 Hz, because `OutputState` is a
      reading of the present and not an event — and `grows_from`, a
      thrown-away first exposure with an AUDIBLE sink that the real shot
      must have grown DOWNWARDS from, because StatePlate says SPEAKING on
      jv-voice's frame alone and "the HUD drew something" would be true
      of a picture where A40's plate never appeared. Measured
      (2444,16,2543,48) → (2412,16,2543,89), 41 px taller; verified it
      bites by making the two exposures identical (exit 1, and no PNG
      written, because the check runs before `write_png`). The growth
      rule moved out of A42's window into `sheet.grew_downwards()` with
      eight unit tests that need no compositor. Honest footnote: the
      `hold` is margin, not necessity — publishing once writes the same
      PNG byte for byte, because one exposure beats the 3 s expiry by
      under a second. Every comment claiming otherwise was corrected.
      Tests: `bash ops/ralph/runtests.sh tools` (104),
      `bash ops/ralph/hudscreens.sh` (7 screens).)

- [x] A51. The HUD says when this machine refused to run a program.
      — ecc89c5
      (Invariant 8 makes jv-guard's screening the only moment JarvisOS
      says NO to something its user asked for, and it was the one moment
      with no pixels. `core/GuardState.qml` decides — 41 QML tests, 10
      mutations run through them — and `GuardPlate.qml` draws BINARY
      BLOCKED in `risk` or BINARY SUSPICIOUS in `warn`, over the file's
      own name. REFUSALS ONLY; NOT the scanner's `reasons`, which the
      schema says are spoken on request and which are the only text on
      this topic a schema does not fix; the NAME IS SANITISED, because it
      is the one string this HUD draws that an attacker chose — whitespace
      collapsed first, then C0/C1, zero-width marks and bidi overrides
      stripped, then capped, and a name with nothing left falls back to
      the first 12 hex of the sha256 labelled as a hash; and NO SPOKEN
      EXIT, because a verdict is not part of a voice turn, which makes the
      30 s hold the ordinary exit rather than a backstop. `guard.verdict`
      joined the bridge's topics; the surface box grew 560 → 624 and three
      other files carry that number. Tests: `bash ops/ralph/qmltest.sh`
      (476), `... runtests.sh tools` (125), `... jv-hud-bridge` (25),
      `bash ops/ralph/hudshots.sh` (10 shots, `10-guard.png` new),
      `bash ops/ralph/hudscreens.sh` (7 screens, green against the real
      `.#jv-hud`).)

- [x] A52. The HUD reads jv-compat now, and says which app did not get
      installed. — caa7c75
      (`core/InstallState.qml` decides — 36 QML tests, 14 mutations run
      through them — and `InstallPlate.qml` draws INSTALL FAILED over the
      app's slug, in `risk`, under GuardPlate: the two halves of invariant
      8 said by the two processes that enforce it. Four decisions.
      FAILURES ONLY, which is also how the progress question was left
      alone rather than answered — see A60. NOT `blocked`, because that is
      how the SCREENING ended and GuardPlate already draws it from
      jv-guard's own frame; passed over as NO NEWS, so a refusal cannot
      clear a real failure. NOT the `error` text, which on a failed frame
      is the last 500 bytes of a confined Windows installer's stdout — the
      element does not expose the field, so no plate can draw it. And THE
      SLUG MUST LOOK LIKE ONE: `app` is an identifier, so it is drawn only
      if it still has the shape of a prefix directory name and REFUSED
      rather than repaired otherwise (a scrubbed identifier is another
      app's name), falling back to the sha256 prefix — which is the one
      place this element parts company with GuardState, where a file NAME
      is sanitised and drawn. `compat.install` joined the bridge's topics;
      the surface box grew 624 -> 688 and four other files carry that
      number. Tests: `bash ops/ralph/qmltest.sh` (536, was 498),
      `... runtests.sh tools` (131), `... jv-hud-bridge` (25),
      `bash ops/ralph/hudshots.sh` (11 shots, `11-install.png` new),
      `bash ops/ralph/hudscreens.sh` (7 screens, green against the real
      `.#jv-hud`).)

- [ ] A60. **Human decision, and the half of A52 deliberately left
      undone.** An install is the only thing on this bus that takes
      MINUTES, and the HUD now draws exactly one of its six events. So
      "what is jv-compat doing right now" is still unanswerable from the
      screen: `fingerprinted`, `screened` and `prefix_created` go by
      invisibly, and a user who ran `jv-compat install` and walked away
      cannot tell a running install from one that never started. The
      shape is the problem, not the data — every plate in this stack is
      about a MOMENT, and a progress indicator is a thing §06 does not
      have: it would be the first element on screen for minutes at a
      time, the first whose whole point is that it changes, and the first
      that competes with the voice turn for the corner. Three ways out
      for whoever answers: (a) leave it — the terminal that started the
      install is the progress indicator, and the HUD is for what you
      would otherwise miss; (b) a one-line plate that says the app and
      the stage and nothing else, holding the rhythm of the rest of the
      stack; (c) a genuinely new §06 shape, which is a design decision
      and not an implementation one. Discovered in A52.

- [x] A61. `10-guard.png` and `11-install.png` are the two halves of one
      story and no picture has ever shown them together, though the box
      was grown for precisely that case. — 542797a
      (`12-guard-install.png`, caption `guard install mic`. The
      refusal-then-retry this item described CANNOT produce it: jv-guard
      screens the retried build too, and a `clean` verdict is newer news
      from the same screener, so `GuardState` lets the refusal go before
      the retry can fail. The refusal has to be the NEWER screening about
      a DIFFERENT binary — which is just two overlapping installs, and an
      install takes minutes: a long installer gets its prefix, the user
      installs something else while waiting and jv-guard refuses it, and
      the first install dies fourteen seconds later. Every frame is one
      `install.py`/`jv-guard` really publish, in order, at real
      timestamps, including the `blocked` on `compat.install` that lands
      mid-lifecycle and that `InstallState` reads as no news — the shape
      that makes A52's rule matter, on a screen for the first time. The
      sheet also stopped taking the FIT on faith: every shot now asserts
      `insetPx + stack.height <= surface height`, mutation-checked with a
      170 px box. Tests: `bash ops/ralph/hudshots.sh` (12 shots, the
      other eleven byte-identical), `... runtests.sh tools` (131),
      `... qmltest.sh` (536, untouched).)

- [ ] A62. The corner can show two plates about two unrelated things and
      has no way to say so. `12-guard-install.png` is the first picture of
      it: `codec_pack_setup.exe` was refused, `fl-studio` failed, the two
      have nothing to do with each other, and they are stacked 8 px apart
      in the same severity colour. A reader who assumes one story reads
      "the thing that was blocked then failed", which is the one sentence
      those frames do not support. Every plate in this HUD is true alone
      and the stack has no grammar for relating two of them — and the pair
      that reads MOST like one story (guard + install, joined in the
      schemas by a sha256) is the pair that most often is not. This is a
      design question and a human's: (a) leave it — a HUD is a list of
      facts and the voice is where relationships live; (b) join what can
      be joined (the sha256 IS in both frames, so "same binary" is
      knowable and "different binary" therefore assertable); (c) a §06
      shape for grouping, which is new design. Do not build (b) before
      answering (a). Discovered in A61.

- [ ] A63. The new fit check passes with over 500 px to spare, because no
      shot lights more than three plates. The box is 300x688 and the
      tallest committed shot is now A61's own, at 165 px of corner inside
      it — so the case the box is actually SIZED for, six or eight plates
      up at once, is neither
      photographed nor asserted, and the four co-occurrence arguments in
      `shell.qml`'s height binding are still arguments. A composed shot
      that lights six or eight plates would close it and is cheap, but it
      is a picture of exactly the confusion A62 names, so it wants A62
      answered first. Discovered in A61.

- [x] A64. `GuardPlate`'s entire `warn` branch was unreachable on this
      machine: `decide()` returned `clean` or `blocked` and nothing else,
      so the approved policy's middle rung lived in the schema's policy
      note, jv-compat's override message and the HUD's second colour —
      and in no code path. — eca239e
      (Took the first of the two ways out: jv-guard grew a local,
      hash-free SHAPE engine. `jv_guard/pe.py` reads the section table
      and refuses to guess at anything it cannot parse confidently;
      `jv_guard/heuristics.py` raises a concern for an EXECUTABLE section
      at entropy >= 7.2, one that is also writable (W+X), or one with no
      bytes in the file but virtual space to unpack into. "Executable" is
      the whole difference between a rung and a nuisance: every
      Inno/NSIS/7z installer carries a ~8-entropy compressed payload in a
      DATA section, and a test says so. Engines now declare a KIND —
      SIGNATURE is authoritative, HEURISTIC is advisory — because without
      it the new engine would have silently deleted fail-closed: ClamAV
      down + shape engine ordinary would have become `clean`. `decide()`
      returns None unless an authoritative engine ran, even when the
      advisory one is shouting (the outage clause forbids inviting an
      override too). Missing Authenticode was rejected with reasons in the
      docstring: it fires on nearly every binary this machine will screen,
      and signature PRESENCE is not trust. Tests:
      `bash ops/ralph/runtests.sh jv-guard` (33, was 6; five mutations),
      jv-compat 9 and pylib 4 unchanged.)

- [ ] A65. **Human decision, and it just stopped being theoretical.** The
      `suspicious` override path is now the only exit from a verdict this
      machine can actually produce. A UPX-packed freeware tool and a
      Themida/VMProtect-wrapped game installer both read as packed —
      because they are — and v0 refuses them with a message describing a
      confirmation nobody can give. That is invariant 8 behaving exactly
      as written, and it is also a class of install that used to succeed
      and now stops. Three things a human could decide: (a) wire the
      override through the confirm surface that already exists
      (`ConfirmPlate` + jv-act owns confirmations — this is the designed
      answer and the biggest); (b) leave it refusing and accept that
      packed installers need a human at a terminal; (c) tune which
      concerns reach `suspicious` (W+X alone is rarer than packing; the
      thresholds are two named constants with a calibration test).
      Discovered in A64.

- [ ] A66. The thirteenth contact-sheet shot A61 refused to take is now
      honest. `GuardPlate`'s `warn` colour has a producer, so a composed
      frame of a `suspicious` verdict is a picture of something jv-guard
      really publishes rather than of an intention — and the reasons it
      carries ("executable section '.text' looks packed or encrypted:
      entropy 7.96 of a possible 8.00") are longer than any blocked
      reason yet photographed, which makes it a real test of the plate's
      wrapping and of the fit check A61 added. Cheap, and unlike A63 it
      lights one plate, so it does not want A62 answered first.
      Discovered in A64.


- [x] A53. `10-guard.png` is a picture only a human can tell apart from a
      picture of `ActionPlate`. — 754a49b
      (Answered with the QML-side probe, which turned out to be cheap where
      it counts: every plate declares `plateName`, pinned to its own file
      name by a tools gate so it cannot drift into a confident lie, and
      `core/PlateStack.qml` collects `litNames` — the plates on screen, in
      reading order, as the plates themselves report it. `anyLit` is
      untouched: it maps the surface, it is the only safety-critical answer
      here, and a test holds the two to agreeing in every case. The contact
      sheet now asserts its CAPTION per shot instead of one bit that nine
      of ten shots answered identically; `07-no-bus.png` is checked for
      A23's actual argument (`link` ALONE, every plate under it gone rather
      than stale); a plate the sheet renders but never LIGHTS fails a test;
      and `docs/hud/README.md` carries a machine-checked `**On screen:**`
      line per shot. Mutation-checked with the exact confusion this item
      names: 10-guard.png expecting `action` FAILS now and passed before.
      Tests: `bash ops/ralph/qmltest.sh` (487), `... runtests.sh tools`
      (130), `bash ops/ralph/hudshots.sh` (10 shots, byte-identical).)

- [x] A54. The corner is only ever checked at one settled instant, and a
      plate that arrives one frame late or leaves one frame early is a
      SEQUENCE bug no still picture can catch. — 8b2fa24
      (Answered where the real plates can actually be built: the shot
      harness's stage. `tools/hudshots/scene/tst_sequence.qml` replays the
      committed recordings through the real nine-plate corner and asserts
      the whole trajectory — every `litNames` change with the `ts` of the
      frame that caused it — plus four claims only a sequence can make: no
      recording lights a plate no service in it reported, the words are
      never up without the state plate above them, an unanswered turn
      empties the corner by itself, and losing the bus takes every plate
      down BEFORE the link plate arrives (the 5 s of grace `07-no-bus.png`
      settles past). Motion is suppressed through the real reduced-motion
      path so a plate's arrival is a frame and not a fade; one test holds
      that. Both drivers now build ONE corner —
      `tools/hudshots/scene/Corner.qml`, pinned to `shell.qml` for
      membership and ORDER, with a second gate against a driver keeping its
      own copy. Tests: `bash ops/ralph/hudshots.sh` (15, and the 10 shots
      byte-identical), `... runtests.sh tools` (131). Eight mutations
      caught; one honest miss reported in the journal.)

- [ ] A56. The sequence suite runs in `ops/ralph/hudshots.sh` and NOT in
      `nix build .#jv-hud`, so the strongest assertion about what the HUD
      shows is not in the build gate. The obstacle is real: the plates need
      the stage (two Quickshell singletons substituted), the stage is
      assembled by a shell script that shells out to nix, and a derivation
      cannot run that — so gating it means a SECOND implementation of the
      staging, which is a thing that drifts, and the drift would mean the
      sheet and the gate photograph and assert different HUDs. Options, for
      a human: (a) accept it — the loop runs `hudshots.sh` on every HUD
      iteration; (b) move the staging into a small generator both the script
      and the derivation call; (c) put the stubs in the shell as build-only
      files so no staging is needed at all (invites a stub reaching a real
      screen, and is probably wrong). Discovered in A54.

- [x] A57. The two windows that hold up the pair of plates a turn puts on
      screen were pinned equal at 30 s and kept time DIFFERENTLY. — 3f6c144
      (`HeardState.anchor`: the hold is timed from the `audio.vad
      speech_end` of the utterance those words belong to — the same frame
      SpeechState times "thinking" from — matched by `utterance_id`, with
      the transcript's own `ts` as the fallback when that boundary was not
      seen. The fallback is the old behaviour and errs the old way, too
      long rather than too short; nothing here decides whether the line is
      SHOWN. `audio.vad` was already subscribed and is never rendered.
      Eight new cases in `tst_heardstate.qml` (495, was 487), one of them
      pairing the two real elements on one bus with real timers; nine
      mutations, all caught; one redundant guard removed rather than
      shipped untested. `tst_sequence.qml` could NOT show it and says so:
      the fixture generator stamps the final at the same `ts` as the
      speech_end, so every replay has an instantaneous ASR — see A58.)

- [x] A58. Every committed recording had an INSTANTANEOUS ASR, and that is
      why A57 lived through five suites. — 746166e
      (`generate_sessions.asr_delay()` adds `ASR_LATENCY_S` = 2.2 s to a
      final transcript's `ts` — the figure measured on ares,
      PHASE1-STATUS.md's "ASR is ~2.2 s fixed", the same span `jv tap
      --latency` calls `hear`. A declared constant and not a measurement
      taken while generating: the recordings stay reproducible to the
      sample. Partials are deliberately NOT delayed — see A59. The three
      finals were restamped in place, one number per recording, because
      the loop's machine has no weights; the weights-gated staleness
      check is what proves a regeneration agrees. `tst_sessionreplay`
      now reads A57's anchor off a real recording and pairs the two real
      elements on one bus (498, was 495); `tst_sequence`'s three
      trajectories moved to the second the words arrive and its
      shortened window grew from 200 ms to 3 s, which a budget under the
      ASR could not be. The 10 shots came out byte-identical. Four
      mutations caught. Tests: `runtests.sh harness` 88 (was 78),
      `qmltest.sh` 498, `hudshots.sh` 15, `runtests.sh tools` 131.)

- [ ] A59. The recordings model the FINAL's ASR and not the partials',
      and the asymmetry is stated rather than resolved. Every partial
      also costs a `transcribe()` and also reaches the bus after it
      returns, so a live partial is late too — but nothing has measured
      by how much, and modelling it honestly means modelling the sample
      clock falling BEHIND the room and catching up, because the
      transcribe runs inline on the one thread that feeds wake and VAD
      (docs/optimization-backlog.md §6: a live mic backs its queue up and
      drops). That would move every other frame in these recordings
      instead of one, so it is a different and larger claim than A58 was.
      Two honest ways out: measure it on ares alongside the 2.2 s (a
      human at the machine, and it pairs with A28), or decide the
      partials are close enough to free to leave alone and say so in one
      place instead of two. What must NOT happen is a second invented
      constant. `test_a_provisional_sentence_is_stamped_while_the_
      utterance_is_still_open` is the guard that holds until then.
      Discovered in A58.

- [ ] A55. "What is the HUD showing right now" is answerable only by
      looking at the screen. `litNames` is the string a `jv hud` subcommand
      would print, and the B track has wanted a terminal view of the HUD's
      state since B15 asked which span the 2.5 s budget names — a `jv tap`
      that can say the corner went from `state heard mic` to `state mic` is
      a latency measurement of the LAST hop, not just of the bus. The
      obstacle is real and worth stating: the HUD is the only bus consumer
      that is a separate process with no way to be asked anything, so this
      is the same seam A47 wants for hudscreens and it should be decided
      ONCE, for both. Do not build it before A47 is answered. Discovered
      in A53.

- [ ] A47. The growth check proves a plate ARRIVED, never WHICH plate.
      `grows_from` (A44) and A42's live-lit window both measure the same
      thing: the drawn region got taller from the same top-right corner.
      A `HealthPlate` saying `jv-voice lost` would do that too, in the
      same direction, by a similar number of pixels — which is not
      hypothetical, since it is exactly what A42 hit when a heartbeat
      lapsed mid-window. Today the only thing that distinguishes them is
      the picture, read by a human, which is fine for a sheet whose whole
      purpose is to be looked at and not fine for a check that claims to
      prove the caption. No cheap answer: reading the words needs OCR or
      a QML-side probe, and both are new machinery in a harness whose
      value is that it stages nothing. Worth writing down so nobody reads
      more into the measurement than it says. Discovered in A44.
      A48 makes it three: `grew_downwards` is now asked by three idle
      windows and the shot loop, and all four of them prove only that
      SOMETHING arrived under the thing above it.
      A49 makes it four, and adds a mirror image: its shrink check proves
      something LEFT the screen and is equally unable to say what. The
      answer is the same for both, and so is the cost of getting one.
      **A53 closed the fifth instance and NARROWED this one** (754a49b):
      the QML-side probe exists now — `plateName` on every plate,
      `litNames` on the stack — and it answers completely inside
      `tools/hudshots`, where the scene is built by a QML test that can
      read a property. What remains is `tools/hudscreens` ONLY, and it is
      the harder half by construction: it photographs the real `.#jv-hud`
      binary under a real compositor with `grim`, so there is no QML engine
      to ask. Two honest options and neither is cheap — OCR (the captions
      are 11 px mono; tesseract is unreliable there), or an IPC seam in the
      SHIPPED shell that reports `litNames`, which stages something in
      production code for a test's benefit and this harness's whole value
      is that it stages nothing. **One human decision: OCR, an IPC seam, or
      leave those four checks saying exactly what they say.** Until then the
      four measurements are correct about growth and silent about identity,
      and `tools/hudscreens/shoot.py` says so.

- [x] A45. `docs/hud/screens/*.png` are not byte-reproducible, and the
      README now says so with numbers. — 3052b8f
      (Half of this was already true: that README has carried a
      "two runs are not byte-identical" paragraph since A30, which is
      why nobody noticed a journal entry leaning on the opposite. It now
      states what was measured over three runs of an untouched HUD —
      `01-quiet` (draws nothing) and `04-unheard` (two short monospace
      labels) identical every time, `02-heard` and `03-confirm` moving by
      2-5 px per monitor, one channel, one value, on glyph edges inside
      the plate — and a test pins the disclaimer so it cannot quietly
      leave. NOT made reproducible: the cause is below this harness, the
      shots that carry a long wrapped sentence are the only ones that
      drift, and a picture nobody byte-compares does not need to be a
      fixture. Done as part of A44, which rewrites the directory anyway.)

- [x] A46. `JARVIS_VOICE_OUTPUT_DEVICE` (A41) is honoured by the process
      and declared nowhere. — 61f26a4
      (`jarvis.voice.outputDevice`, a `types.nullOr types.str` defaulting
      to null, threaded into jv-voice's unit environment and NO other
      unit's. The repo's first NixOS option, so the module grew an
      `options`/`config` split to hold it. The empty string is refused by
      an assertion, because jv-voice reads an empty variable as "no
      device" and `outputDevice = ""` would be a configuration claiming a
      device is pinned while the service it configures reports none.
      Tests: `bash ops/ralph/nixtest.sh` — NEW machinery, 7 cases, each a
      `nix eval` of an `extendModules`-overridden ares asserting the
      GENERATED UNIT TEXT rather than the attrset, with four mutations run
      through it. The toplevel derivation path is identical to its
      parent's: a knob on ares, and not a byte of what ares would boot.
      Committed in iteration 43 and journalled in iteration 44 — the
      iteration that built it never wrote it down.) `modules/jarvis-services.nix` builds
      `systemd.user.services.jv-voice` with `environment = commonEnv`
      and no way to name a device, so pinning one today means editing a
      unit by hand — the imperative mutation the NixOS discipline
      forbids ("if it isn't declared, it doesn't exist"). The fix is one
      option (`jarvis.voice.outputDevice`, a `types.nullOr types.str`
      defaulting to null) threaded into that unit's `environment`, which
      also makes the HUD's new quiet-when-pinned path reachable on ares
      without touching a running system. Nothing is blocked on it — the
      default IS unpinned and that is the honest state of this machine —
      so it is small, tidy, and worth doing before anyone actually
      plugs in a dedicated speaker. Discovered in A41.

## Done
- A51 — the HUD says when this machine refused to run a program: jv-guard's
  verdict on a plate, the reasons deliberately left for the voice, and the
  one string in this HUD an attacker chose made safe to draw (ecc89c5,
  2026-09-24)
- A46 — the speaker Jarvis talks into becomes something the machine
  declares: `jarvis.voice.outputDevice`, the repo's first NixOS option, and
  `ops/ralph/nixtest.sh` to assert what options do to units (61f26a4,
  2026-09-24)
- A49 — the last plate in the stack gets watched standing still, and the
  turn gets an ending: a sixth measured window on the fifth's own broker
  and shell, the first check of a plate LEAVING, 0 commits, and a
  mutation the other five windows are blind to (4b62514, 2026-09-24)
- A48 — the two plates whose words come off a latch get watched standing
  still: a fifth idle window, a re-published frame re-taking a latch once
  a second, 0 commits, and a mutation the other four windows are blind to
  (9e322a1, 2026-09-24)
- A43 — the mic and health plates get watched standing still: a fourth
  idle window, two plates off one re-published heartbeat, 0 commits, and
  a mutation the other three windows are blind to (fed202f, 2026-09-24)
- B18 — `jv health --check` answers "is generation slow right now?": the
  brain's own gauge beside the rung, dated off its turn counter so a
  re-stated number can never pass as a current condition (4bd95fd,
  2026-09-24)
- A44/A45 — the screen sheet photographs the state where two plates
  disagree about whether Jarvis is working, and stops being mistaken for
  a fixture (3052b8f, 2026-09-24)
- A41 — the HUD stops assuming the sink it can see is the one Jarvis
  speaks into: jv-voice publishes `output_device_pinned`, OutputPlate
  goes quiet rather than confidently wrong (d504ba4, 2026-09-24)
- A42 — "0 fps when idle" stops being measured only on a HUD with no bus:
  a plate held lit on a LIVE bus, 0 commits under 6 snapshots, and a
  mutation the other two windows cannot see (4c63122, 2026-09-24)
- B16 — `think` stops being one number over the model and the queue: the
  model's share of it, stated by the only service that can see it
  (ceca526, 2026-09-24)
- A40 — the HUD stops saying SPEAKING while the room is silent
  (b643c22, 2026-09-24)
- A37 — the HUD says what Jarvis did to your machine when it did not work
  (7bc1eb5, 2026-09-24)
- A34 — the HUD renders nothing while nothing changes, counted off its own
  Wayland socket instead of argued from how Qt Quick works
  (d420e24, 2026-09-24)
- B14 — `respond` stops being one number over two services: split at the
  final transcript into `hear` (ASR) and `think` (the brain), and the
  broker's first heartbeat stops being a scheduling race
- B13 — `jv tap --latency` stops reporting one number: a turn split into
  spoke / hold / respond, and the gauge jv-ears had to publish for it
  (ee96c43, 2026-09-24)
- A32 — a click over the HUD reaches the window underneath, measured
  rather than read (48d9c74, 2026-09-24)
- A30 — the HUD on three monitors, and the four invariant-10 claims that
  stopped being verified by construction (d56b12e, 2026-09-24)
- A29 — the HUD, photographed: docs/hud contact sheet rendered from the
  real plates (fea019c, 2026-09-24)
- B11 — `jv health --check`: the machine can be asked whether it is well,
  and answers with its exit code (c8b2967, 2026-09-24)
- A26 — the HUD says what it heard: HeardState/HeardPlate, and the
  recordings that refused it a confidence bar (d7ac325, 2026-09-24)
- A24 — "which services are supposed to be running" written up as proposal
  R5 rather than built (2026-09-24)
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
- B3 — perception's real output becomes a fixture anyone can test on: four
  recorded sessions + one reader that can be asked `problems()` (d2f9634,
  2026-09-24)
- B9 — the HUD's tests stop typing their own frames: real sessions compiled
  into QML and replayed, trajectories asserted in real seconds (36a486d,
  2026-09-24)
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
- A8 — the faces theme.toml names finally exist on the machine, and the one
  that was silently a web font does not (5e5ef8d, 2026-09-24)
- B5 — `jv act-log` can be asked a question: --since/--failed/--outcome, and
  a filter that never hides what it could not evaluate (da134b9, 2026-09-24)
- A20 — the confirmation stops being only audible: ConfirmState/ConfirmPlate,
  jv-act's question on screen for exactly as long as it can be answered
  (6779708, 2026-09-24)
- A19 — the font module stops promising and starts proving: fc-match run
  against the system's own fontconfig config, every build (be1b264,
  2026-09-24)
