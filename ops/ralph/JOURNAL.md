# Ralph loop — JOURNAL (append-only; newest at the bottom)

The loop appends ONE entry per successful iteration. `ops/ralph/updates.sh` reports
everything here (and every commit) since the last time you asked. Format per entry:

```
## <YYYY-MM-DD HH:MM> — <short title>
- built: <what, and why it matters>
- tests: <suites run> -> <pass/fail>
- build: nixos-rebuild build -> <ok/fail>
- files: <paths>
- commit: <hash>
- next: <suggested follow-up>
```

---

## 2026-09-23 — loop scaffolding seeded (by the setup session, not the loop)
- built: ops/ralph/ guardrails, prompt, plan, journal, updates reporter — the
  harness the autonomous loop runs inside.
- next: install the ralph plugin, launch the loop on branch ralph/auto.

## 2026-09-23 18:40 — A1: jv-hud Quickshell skeleton
- built: `shell/jv-hud/shell.qml` — the first piece of the face (blueprint §06).
  One Wayland layer-shell surface per connected monitor, and it renders nothing:
  no bus subscription exists yet, so there is nothing truthful to display, and
  §06's default state is your work and nothing else. Invariant 10 is enforced by
  construction, not by comment: `WlrKeyboardFocus.None` + `focusable:false` (the
  surface cannot take the keyboard), `ExclusionMode.Ignore` (zero exclusive zone —
  no window is resized around it), `mask: Region {}` (empty input region, clicks
  pass through), `WlrLayer.Top` (over windows, yields to fullscreen/lock), and
  `visible:false` until something real arrives — an unmapped surface is 0 fps.
  `JV_HUD_SELFTEST=1 jv-hud` maps a small marker that reports only that the SHELL
  loaded; it never stands in for a sensor. Packaged as `.#jv-hud` (QML copied to
  the store + wrapped quickshell 0.3.0) and installed system-wide, with a user
  unit that is intentionally NOT in `default.target.wants` — a resident, empty
  overlay is exactly the set dressing §06 forbids.
- tests: no Python/Rust touched, so `runtests.sh` was not applicable. The gate for
  QML is qmllint inside the package's checkPhase, run with `-W 0` (any warning
  fails; `uncreatable-type` disabled because every quickshell window type is
  registered non-creatable upstream). Verified the gate is real by appending a
  syntax error to shell.qml: `nix build .#jv-hud` FAILED as it should, then passed
  again once reverted.
- build: `nix build .#jv-hud` -> ok · `nixos-rebuild build --flake .#ares` -> ok
  (checked the result: `etc/systemd/user/jv-hud.service` exists and is absent from
  `default.target.wants`, as intended).
- files: shell/jv-hud/shell.qml, shell/jv-hud/README.md, pkgs/jv-hud/default.nix,
  flake.nix, modules/jarvis-services.nix
- commit: 49046db
- next: A2 — a `Theme` QML singleton holding the §06 tokens (ground #090D12/#0C1116,
  ember #F0714A, teal #4FB8BF, text tiers), sourced from `personality/theme.toml`
  so the look is versioned with the voice and the wake word. Then A5 (the
  consumer-only bus bridge) before A3, since A3 needs real frames to exist.
  Note for A2/A3: quickshell's `margins` grouped property has no resolvable type
  in its qmltypes — use inner-item anchors margins, or the lint gate trips.

## 2026-09-24 — A2: theme tokens live in personality/, the HUD only consumes them
- built: `personality/theme.toml` — the blueprint §06 palette, type, motion and
  geometry tokens, versioned beside `voice.toml` and `system.md` because a theme
  is identity (invariant 9), and `tools/gen_theme_qml.py`, which compiles it into
  `shell/jv-hud/Theme.qml` (a `pragma Singleton`) plus the `qmldir` that makes
  `import "."` resolve. `shell.qml` now carries no colour of its own: ground,
  ember, radius, inset, font and tracking all come from `Theme`. The point is
  that "why is it that colour?" is answered by one diffable file, and that
  jv-dream can propose a look the way it proposes a voice — as a patch a human
  reads. Four gates keep it honest, and each one was checked by breaking it:
  (1) `--check` runs in jv-hud's checkPhase before qmllint, so a Theme.qml that
  has drifted from the toml cannot be built — verified by flipping ember to
  #FF00FF, watching `nix build .#jv-hud` fail with "stale generated files", and
  restoring; (2) qmllint type-checks token access through the singleton —
  `Theme.doesNotExist` is `missing-property`, a build failure, not a silently
  transparent rectangle at runtime; (3) a test forbids a literal `"#RRGGBB"` in
  any QML file but the generated one — it caught shell.qml's three hardcoded
  colours, which is what drove this change into shell.qml rather than leaving the
  singleton unused; (4) a test parses `docs/blueprint.html`'s dark `:root` block
  and asserts all 15 tokens still equal it, so the theme cannot wander off from
  the design it came from. theme.toml is also /etc-deployed with the rest of
  personality/ — nothing reads it at runtime (the HUD's copy is compiled in), but
  the whole of what Jarvis is should be readable in one directory on the machine.
- tests: `bash ops/ralph/runtests.sh tools` -> 16 passed (new suite:
  tools/tests/test_gen_theme_qml.py). Written first and run red — the generator
  did not exist, then the colour-literal test failed alone until shell.qml
  consumed the singleton.
- build: `nix build .#jv-hud` -> ok (Theme.qml + qmldir land in the store beside
  shell.qml) · `nixos-rebuild build --flake .#ares` -> ok, and
  `result/etc/jarvis/personality/theme.toml` is present. Never test/switch.
- files: personality/theme.toml, tools/gen_theme_qml.py,
  tools/tests/test_gen_theme_qml.py, shell/jv-hud/Theme.qml, shell/jv-hud/qmldir,
  shell/jv-hud/shell.qml, shell/jv-hud/README.md, pkgs/jv-hud/default.nix,
  modules/jarvis-services.nix, ops/ralph/PLAN.md
- commit: 6c0eafb
- next: A5 — the consumer-only bus bridge for QML (a small client that subscribes
  to the Unix socket and exposes frames as QML properties, never importing another
  service), because A3 has nothing truthful to display until real frames exist.
  Two follow-ups fell out of this one and are in PLAN.md: A7 (a single
  `prefers-reduced-motion` switch + `Theme.easeMs` Behavior, so the first moving
  pixel already obeys §06) and A8 (Archivo + JetBrains Mono are named in
  theme.toml but not declared in `fonts.packages` — a missing font is a silent
  change of look).

## 2026-09-24 — A5: a read-only bus link for QML (frames in, nothing out)
- built: `services/jv-hud-bridge` + `shell/jv-hud/Bus.qml`. The HUD cannot
  speak the bus itself — QML has no Unix socket and no MessagePack, and
  invariant 1 forbids importing another service — so it gets exactly one
  child process. The bridge subscribes to `speech.state`, `audio.wake`,
  `audio.vad`, `sys.health` and writes each envelope as one line of JSON;
  `Bus.qml` runs it via `Process` + `SplitParser`. The whole envelope is
  forwarded, not just the body: `conf` and `ts` are how a consumer handles
  low-confidence and late input (invariant 4), and `seq` is how it notices
  the frames jarvisd dropped for it. Three design calls worth recording:
  (1) **consumer-only is structural.** The pump is handed a `ReadOnlyBus`
  whose whole public surface is subscribe/next_frame/close — there is no
  publish method to reach for — and a test greps the package for `.publish`
  on top of that. The HUD observes; only `jv-act` acts.
  (2) **link state is not a bus topic.** `{"t":"link","up":false,"err":...}`
  describes this pipe, not the machine; minting `hud.link` would be writing
  schema without a reviewed schema commit (invariant 2). The HUD needs the
  signal because `Bus.frames` is **emptied whenever the link drops** — an
  indicator still showing what it heard before jarvisd died is worse than
  no indicator, and that is invariant 10 in one line of code.
  (3) **the link costs nothing when unused.** Quickshell builds a singleton
  lazily, so as long as no element references `Bus`, no bridge runs and no
  socket is held. That only holds if no binding touches it, so the
  self-test plate moved inside a `Loader { active: selfTest }` rather than
  relying on `visible: false`. Under `JV_HUD_SELFTEST=1` the plate now also
  prints `bus up` / `bus down` — the state of the pipe, in plain words, in
  text2/text3, deliberately not dressed as a sensor indicator.
  `ageOf(env)` pins CLOCK_MONOTONIC against Qt's ElapsedTimer by keeping
  the largest `ts - elapsed()` seen (in-flight delay only biases it low, so
  the max converges from below) and returns Infinity until a first frame
  makes the offset knowable — no age is better than a wrong one.
  `tools/gen_theme_qml.py` now renders the qmldir from a `SINGLETONS` list,
  because it owns that file and an unregistered singleton resolves to
  nothing; a test asserts the list and the directory agree exactly.
- tests: `bash ops/ralph/runtests.sh jv-hud-bridge` -> 25 passed (22 unit +
  3 against a REAL jarvisd: a published frame arrives as one parseable
  line, an unsubscribed topic never does, and killing the broker under a
  running bridge reports the link down then recovers it). Tests were
  written first; since I wrote both before running, I proved they bite by
  mutation instead — dropping `allow_nan=False`, never resetting the
  backoff, and swallowing the broken pipe each failed exactly one test and
  only that one. `runtests.sh tools` -> 17 passed.
- build: `nix build .#jv-hud` -> ok · `nixos-rebuild build --flake .#ares`
  -> ok, jv-hud still absent from `default.target.wants`. Never test/switch.
  Then the real proof: ran the PACKAGED `jv-hud-bridge` against the live
  `/run/jarvis/bus.sock` on ares for 3 s — link up, then real `sys.health`
  frames from jv-ears, jv-context, jv-guard and jarvisd, each one line of
  parseable JSON. Also re-broke both gates on purpose: an unregistered
  singleton fails the build as "stale generated files: qmldir", and
  `Bus.linkUpp` read from shell.qml fails qmllint as `missing-property`.
- known gap, honestly: qmllint type-checks CROSS-FILE singleton access but
  does NOT catch a typo in a self-assignment inside `Bus.qml` itself
  (`root.linkUpp = up` builds clean). Verified, noted in the HUD README,
  and the reason A9 below is worth doing.
- files: services/jv-hud-bridge/{pyproject.toml,jv_hud_bridge/*,tests/*},
  shell/jv-hud/{Bus.qml,shell.qml,qmldir,README.md}, pkgs/jv-hud/default.nix,
  nix/jarvis-python.nix, flake.nix, modules/jarvis-services.nix,
  tools/gen_theme_qml.py, tools/tests/test_gen_theme_qml.py,
  ops/ralph/runtests.sh
- commit: bae8e03
- next: A3 — the first data-backed element, now that `Bus` can deliver
  frames: Jarvis's state from real `speech.state` + `audio.wake`, ember only
  when genuinely active, nothing at all when `Bus.linkUp` is false. Do A7
  (the one `prefers-reduced-motion` switch + `Theme.easeMs` Behavior) in the
  same breath or just before, so the first moving pixel already obeys §06.
  A9 fell out of this one: there is no headless test of the QML side at all,
  so `Bus.ingest` — the JSON parsing, the frame-cache clearing on link down,
  the clock pinning — is verified only by reading it. A `qmltestrunner`
  (or `qml -platform offscreen`) suite in the jv-hud checkPhase would close
  the largest untested gap in the HUD and make every later element cheap to
  test.

## 2026-09-24 — iteration 4 — B2: `jv` streams are bounded, scriptable, tested

- why this and not UI: the ladder says take a feature when the last three
  iterations were UI, and A1/A2/A5 were all Track A. B1 was checked first
  and is empty — all 27 items in `docs/optimization-backlog.md` are
  human-review-gated, so there is no auto-applyable one to pull. B2 it is.
- what: `jv sub`/`tap`/`health` ran until killed. That is fine to watch and
  impossible to script or assert on, and it is why the CLI that is
  supposed to be "how we debug everything forever" had zero tests. Now
  every stream stops on `-n/--count N`, `--for SECS`, or Ctrl-C, and an
  unmet `--count` exits 1 — a script can finally tell "here is the frame"
  from "the bus went away" from "nothing was published", which all looked
  like a clean exit before.
- two behaviour fixes that only showed up once the tap was testable:
  (1) the end-to-end line fired for EVERY `speech.say` answering an
  utterance. jv-brain streams a reply sentence by sentence (reply_group),
  so one utterance printed 340ms, then 1200ms, then 2600ms — which reads
  as latency degrading and is only a long reply. It reports once per
  utterance now and says what it actually measures: VAD start -> FIRST
  speech.say, i.e. time to first word, which is the budget that exists.
  (2) `utt_start` was an unbounded HashMap in a tool meant to be left
  running for hours; it is a 256-entry ring now. Utterance start is also
  the EARLIEST ts seen rather than the first frame delivered, because
  vad / partial / final transcript frames need not arrive in ts order.
- `jv tap --latency` prints a per-topic p50/p95/max summary when it stops.
  A scrolling column of per-frame numbers is not a measurement, and
  invariant 5 says measure, don't assume. Nearest-rank percentiles, so
  every number printed is a latency that was really observed. Ctrl-C is
  wired precisely so an interactive tap can ask for that summary: the
  SIGINT future is registered ONCE and polled across iterations, because
  a fresh `ctrl_c()` per loop pass can drop a signal that lands while
  we are printing.
- the reasoning moved into a new `jarvisd::cli` module (latency
  accounting, utterance tracking, line formats, exit policy) so it can be
  tested without a process; `bin/jv.rs` is argument parsing plus one
  `select!` loop. Nothing here touches broker.rs, proto.rs or jv-act —
  the bus hot path is byte-identical.
- tooling: added `ops/ralph/cargotest.sh`, the Rust sibling of
  `runtests.sh`. `nix build .#jarvisd` does run cargo test, but it copies
  into the store and rebuilds the world per edit, which is far too slow
  for red/green. This borrows the derivation's own build env (cargo,
  rustc, the vendored registry — no network) and a cached target dir
  outside the repo. It is the INNER loop, not the gate.
- tests: 30 green — 16 unit + 6 broker + 8 new end-to-end that run the
  REAL `jv` binary as a child process against a real broker on a real
  socket. `tests/common/mod.rs` now holds the broker fixture that
  `bus.rs` had inline, so both suites share it.
  On flakiness, deliberately: whether a child has finished subscribing is
  not observable from the test, and sleeping a guessed amount then
  publishing once is exactly the flake that makes an unattended gate
  worthless. So each test re-publishes its frames on a tick for the whole
  window and asserts only things that are TRUE UNDER REPEATS — `-n 1`
  prints one line however many frames arrive, and an end-to-end report
  fires once per utterance by construction. `wait_out` panics rather than
  hangs if the CLI overruns its bound, since "it stops when told" is the
  thing under test.
  I wrote tests and implementation together, so rather than claim
  test-first I proved they bite by mutation: dropped eviction, forgotten
  "already reported", inverted earliest-ts, always-zero exit code,
  ignored `--count`, ignored `--for`, ignored Ctrl-C, and an invented
  zero uptime each failed exactly the tests that should have caught them
  and no others.
- build: `nix build .#jarvisd` -> ok, and its checkPhase ran all 30 tests
  green INSIDE the sandbox (the child-process tests included).
  `nixos-rebuild build --flake .#ares` -> ok; jv-act rebuilt clean
  against the changed jarvisd lib (it takes it as a path dep). Never
  test/switch. Then the real proof: ran the PACKAGED `jv` against the
  live `/run/jarvis/bus.sock` on ares — `jv health -n 3` returned real
  heartbeats from jv-guard/jv-act/jv-voice and exited 0; `jv tap
  --latency --for 6` saw real sys.health from all seven producers and
  summarised **p50 0.24ms / p95 0.27ms / max 0.27ms per hop** (10 frames);
  `jv sub 'sys.*' -n 1` returned exactly one parseable envelope; and
  `jv sub jv.nothing -n 1 --for 1` exited 1 as designed.
- one thing checked before changing anything: `modules/jarvis-services.nix`
  uses only `jv pub` (the greeting unit), and that path is untouched.
- files: services/jarvisd/src/cli.rs (new), services/jarvisd/src/lib.rs,
  services/jarvisd/src/bin/jv.rs, services/jarvisd/tests/cli.rs (new),
  services/jarvisd/tests/common/mod.rs (new),
  services/jarvisd/tests/bus.rs, ops/ralph/cargotest.sh (new)
- commit: 62c440f
- next: back to Track A with the variety debt paid. Do **A7 then A3** in
  that order: the `Ease`/`prefers-reduced-motion` switch first so the
  first moving pixel in the HUD already obeys §06, then A3 — Jarvis's
  state from real `speech.state` + `audio.wake`, ember only when
  genuinely active, nothing at all when `Bus.linkUp` is false. **A9 is
  now cheaper and more clearly worth it:** this iteration showed what a
  real test harness buys (three behaviour bugs surfaced in an hour), and
  the QML side still has zero tests, so `Bus.ingest` is verified only by
  reading it. Consider A9 immediately before A3 so the new element is
  born tested. A8 (fonts) stays a good 10-minute filler commit.
  Newly discovered, small: `jv act-log` and `jv confirm` are still
  untested — act-log now has a testable `cli::act_log_line`, but reading
  and tailing the file is not covered, and `jv confirm` has no test that
  the frame it publishes is the shape jv-act's resolve_voice expects.

## 2026-09-24 — iteration 5 — A9: the QML side gets a test harness

- picked: A9 (headless QML tests), exactly as iteration 4 suggested. Track A
  was due, and A9 comes before A3 on purpose: the HUD's first data-backed
  element should be born tested rather than retrofitted.
- the obstacle, and the design that came out of it: quickshell links its QML
  plugin INTO its own binary (there is no `quickshell-coreplugin.so` in the
  package to point an engine at), so `import Quickshell` can never resolve in
  `qmltestrunner`. Worse, importing a directory resolves every type its qmldir
  lists — my first attempt put `BusModel.qml` next to `Bus.qml` and the whole
  directory became unimportable because ONE listed singleton needed Quickshell.
  So the HUD is now split by what can be loaded, not by taste:
    shell/jv-hud/core/   QtQuick only   -> any QML engine, so: tests
    shell/jv-hud/        Quickshell     -> the quickshell binary, only
  `core/BusModel.qml` is the bus state machine (parse, cache, link, age);
  `Bus.qml` keeps only what cannot be tested — the bridge child process, the
  respawn timer, the ElapsedTimer — and forwards the whole API, so shell.qml
  and every future element still see one `Bus` and did not change.
  The one shape change: the monotonic clock is injected (`monotonic`, a
  callable returning seconds). Bus.qml passes ElapsedTimer; tests pass one
  they drive by hand, which is what makes the age arithmetic reproducible.
- the tests found a real bug on their first green-ish run, which is the whole
  argument for writing them: with no clock, `elapsed()` is NaN, so the offset
  pinned to NaN and `ageOf()` returned NaN. NaN compares false against every
  threshold — an unknown-age frame would have read as FRESH to any element
  asking "is this stale?". That is precisely the quiet lie invariant 10 exists
  to prevent. Fixed by refusing to pin a non-numeric reading; unknown age is
  Infinity, which reads as stale everywhere.
- on proving the tests bite, since I wrote them alongside the split rather
  than strictly red-first for every case: 9 mutations, each run through the
  suite. Stale cache on link down, `frames` mutated in place instead of
  replaced (the one that kills bindings silently), `latest()` returning
  undefined, NaN clock pinning, keeping the WORST offset estimate, uncounted
  frames, topics that need not be strings — all 7 failed exactly the tests
  that should have caught them. The 8th (`linkError = err` instead of
  `up ? "" : err`) SURVIVED: it is equivalent on the wire, because a link-up
  line never carries an err. That gap was real — the contract "up means no
  error" was untested — so a test went in for it, and the 9th mutation
  (linkError never cleared on reconnect) is caught too.
- guardrails so the arrangement cannot rot, because a split that depends on
  discipline is a split that dies:
    · `nix build .#jv-hud` runs qmltestrunner (-platform offscreen) right
      after qmllint. VERIFIED it bites: a deliberately broken BusModel failed
      the build, not just the inner loop.
    · a tools test fails if any file under core/ imports anything but QtQuick
      (VERIFIED by adding a Quickshell.Io import — it failed).
    · core/qmldir is generated from `CORE` in tools/gen_theme_qml.py, drift-
      checked inside the build, and cross-checked against the files on disk —
      the same treatment SINGLETONS already got.
    · installPhase drops tests/: a build gate, not shipped QML.
- tooling: `ops/ralph/qmltest.sh`, sibling of runtests.sh and cargotest.sh.
  Resolves qtdeclarative from the flake's own nixpkgs and runs the suite
  offscreen in ~5ms; extra args pass through to qmltestrunner for filtering.
- tests: 27 QML green (also green INSIDE the nix sandbox), 20 tools green
  (3 new), 25 jv-hud-bridge green (untouched, run as a counterpart check).
- build: `nix build .#jv-hud` ok; `nixos-rebuild build --flake .#ares` ok.
  Never test/switch. Nothing outside shell/, tools/, pkgs/jv-hud and ops/
  was touched — no schema, no jv-act, no boot path.
- files: shell/jv-hud/core/BusModel.qml (new), shell/jv-hud/core/qmldir (new,
  generated), shell/jv-hud/tests/tst_busmodel.qml (new), shell/jv-hud/Bus.qml,
  shell/jv-hud/README.md, pkgs/jv-hud/default.nix, tools/gen_theme_qml.py,
  tools/tests/test_gen_theme_qml.py, ops/ralph/qmltest.sh (new)
- commit: 4c7c048
- next: **A7 then A3**, unchanged from last iteration's advice and now
  cheaper. A7 (an `Ease` Behavior + one `prefers-reduced-motion` switch) is
  small; note that the reduced-motion decision is pure logic and therefore
  belongs in `core/` with a test, while the Behavior itself is wiring. Then
  A3 — Jarvis's state from real `speech.state` + `audio.wake`, ember only
  when genuinely active, nothing at all when `Bus.linkUp` is false: put the
  frames-to-state mapping in `core/` and test every transition, including
  "link down" and "frame too old", before drawing a single pixel.
  Newly discovered: **A10** — shell.qml's safety properties (keyboardFocus
  None, exclusionMode Ignore, empty input mask) are asserted by nobody, and
  they cannot move into core/ because they ARE Quickshell types. That corner
  of invariant 10 needs a different kind of gate.
  A8 (fonts) is still a good 10-minute filler commit.

## 2026-09-24 — A7: one switch turns the HUD's motion off
- built: the HUD's motion policy, and the single component every moving value
  goes through. §06 gives motion four rules and three are about NOT moving —
  "off with prefers-reduced-motion · off on battery · full stop when a window
  is fullscreen" — plus "ease toward target over ~200ms, never raw pose". Left
  to each element, one eventually forgets, and the forgetting is invisible: a
  HUD that keeps breathing after a human asked it to stop. So:
    · `core/MotionPolicy.qml` — the decision, pure QtQuick and therefore
      tested: `animate`, `suppressedBy` (a reason, not a bare bool — "why did
      it go still?" is a question someone will ask), and `ms(base)` which
      returns 0 whenever motion is suppressed.
    · `Motion.qml` — the wiring: binds the policy to real sources and
      republishes the §06 durations already gated (`Motion.easeMs` etc.), so
      an animation that forgot to check `animate` still cannot move anything.
    · `Ease.qml` — `Ease on color {}`. A PropertyAnimation, not a Number one,
      so the same component eases colours, which is most of what a HUD
      settles. `base` picks how LONG a move takes; it can never pick whether
      one happens, because the duration reaching the animation is always
      `Motion.ms(base)`. Verified a QML-file-defined Behavior really does work
      as a property interceptor before building on it.
  Followed A9's rule exactly: logic in `core/`, Quickshell files stay wiring.
- sources, and the honest state of each: the declared preference is
  `personality/theme.toml [motion] reduced_motion` (versioned identity,
  invariant 9), and `JV_HUD_REDUCED_MOTION=1`/`=0` overrides it for a session
  — ONLY those two exact strings, because a machine that reads "true" as true
  and "yes" as false is a machine nobody can predict. `onBattery` and
  `fullscreen` have NO source: `context.system.battery_pct` says nothing about
  discharging (and is absent on ares, so its absence cannot mean "on AC"
  either), and `context.window` has no fullscreen field. They are real
  properties rather than TODO comments — wiring one later is a single binding
  — and they sit at false, which is the truth on ares, a desktop on AC.
- guardrails hit: making those two real needs two additive fields in frozen
  schemas. Did NOT touch `schemas/**`; wrote proposal **R1** into
  `docs/optimization-backlog.md` under a new "Proposals from the Ralph loop"
  section (kept separate so the 2026-09-23 pass's accounting stays intact).
- first use: the self-test plate's `bus up`/`bus down` label eases its colour
  — the one moving pixel in the HUD so far, and it moves only because the link
  state actually changed.
- proving the tests bite: 8 mutations through the suite, 7 caught — animate
  frozen true, battery outranking the user's own wish in `suppressedBy`, the
  env "0" branch dropped, `ms` ungated, loose truthiness for the env override,
  fullscreen ignored, `animate` as a non-notifying property. The survivor is
  `base >= 0` where the code says `base > 0`: they differ only at base 0,
  where both return 0, so it is equivalent, not a gap.
- the second gate, which is the point of the whole commit: a `tools/` test
  fails the build if any QML file in the HUD declares an animation type
  (`Behavior`, `*Animation`, `*Animator`, …) without mentioning `Motion.`.
  VERIFIED it bites twice — a raw `NumberAnimation on opacity` in shell.qml
  failed it, and so did an `OpacityAnimator`. `Ease` needs no exemption: it
  consults Motion itself, so a file that only uses Ease is already gated.
  Files in `core/` cannot reference Motion (a Quickshell singleton), which is
  exactly right — core/ is logic, and logic does not animate.
- also: `tools/gen_theme_qml.py` grew a `COMPONENTS` registry beside
  `SINGLETONS`/`CORE`, since our qmldir replaces the one Quickshell would
  synthesize and a qmldir exposes only what it lists — an unregistered `Ease`
  is not a type at all, and the error lands in the USING file, miles away.
  A test asserts the registry and the directory agree (verified: dropping Ease
  from it fails).
- footgun worth remembering: new QML files must be `git add`ed before
  `nix build` sees them — the flake source is the git tree, so the first build
  failed with "Motion.qml is listed in qmldir but does not exist".
- tests: 52 QML green (25 new, also green INSIDE the nix sandbox), 22 tools
  green (2 new). jv-hud-bridge untouched.
- build: `nix build .#jv-hud` ok; `nixos-rebuild build --flake .#ares` ok.
  Never test/switch. No schema, no jv-act, no boot path.
- files: shell/jv-hud/core/MotionPolicy.qml (new), shell/jv-hud/Motion.qml
  (new), shell/jv-hud/Ease.qml (new), shell/jv-hud/tests/tst_motionpolicy.qml
  (new), shell/jv-hud/shell.qml, shell/jv-hud/README.md, shell/jv-hud/qmldir +
  core/qmldir + Theme.qml (generated), personality/theme.toml,
  tools/gen_theme_qml.py, tools/tests/test_gen_theme_qml.py,
  docs/optimization-backlog.md
- commit: 245926e
- next: **A3**, and everything it needs now exists — `Bus` delivers frames and
  is tested, `Motion`/`Ease` mean the first animated element obeys the switch
  for free. Put the frames-to-state mapping in `core/` (call it
  `SpeechState.qml`) and test every transition before drawing a pixel:
  idle / listening / speaking / interrupted, plus the two that matter more —
  `Bus.linkUp` false shows NOTHING, and a frame older than a threshold is
  stale, not current (`Bus.ageOf` is there for exactly this and its Infinity
  case is already tested). Ember only while genuinely active.
  A8 (fonts: Archivo + JetBrains Mono in `fonts.packages`) is still a good
  10-minute filler commit, and is now the only thing standing between the HUD
  and the look it declares. A10 (shell.qml's unguarded safety properties) is
  unchanged and still worth a grep-shaped gate — note that this iteration's
  animation-gate test is exactly that shape, so the pattern now has a
  precedent to copy.

## 2026-09-24 — iteration 7 — A3: Jarvis's state, on screen, from real frames

- picked A3 off the top of the ladder: UI/UX, and the journal's own `next:`.
  Everything it needed had landed — `Bus` delivers frames (A5), `Motion`/`Ease`
  mean the first animated element obeys the reduced-motion switch for free (A7),
  and A9's `core/` split is where the logic had to go.
- built two files. `core/SpeechState.qml` is the decision (pure QtQuick, so it
  is tested); `StatePlate.qml` is a dot and one word. The plate draws NOTHING
  for `idle` and nothing for `unknown`, so the layer-shell surface is unmapped
  unless a frame earned it. A badge permanently reading "idle" is chrome that
  never earned its place, and one reading it while the bus is down is a lie.
- the hard part, and the only interesting design decision: **`listening` has no
  closing signal.** jv-ears publishes `audio.wake` when a window opens and
  publishes nothing at all when it disarms (read `services/jv-ears/jv_ears/
  pipeline.py`: `_armed_at` is cleared silently on both the timeout path and at
  a gated `speech_end`). So the close has to be inferred, and since this is a
  claim about the MICROPHONE, every rule is chosen to stop claiming it early
  rather than late:
    · Jarvis answering (`speech.state` -> speaking, newer than the wake) means
      it already heard you. A `speaking` frame OLDER than the wake is barge-in,
      not an answer — wake detection stays live while jv-voice talks — so that
      still reads as listening, which is the responsive AND the true thing.
    · `audio.vad` `speech_end` newer than the wake closes it. If that segment
      was not actually wake-gated, ears stays armed and we stop saying
      "listening" a little early. Early is the safe direction.
    · `interrupted` deliberately does NOT close it: jv-voice publishes that
      BECAUSE of the wake, so treating it as an end would blank the plate at
      the exact moment the user is mid-sentence.
    · the fallback is `wakeWindowS` = 8 s, mirroring ears' `wake_timeout_s`
      default. This is the one number in the element that is a HUD-side
      constant, because **nothing on the bus publishes ears' configuration.**
      Written down in the file and the README: keep it AT OR BELOW whatever
      ears is tuned to, or the HUD over-claims. A candidate for a future
      `sys.health`-shaped signal, not worth a schema change today.
- the timer is armed with whatever is LEFT of the window (`wakeWindowS` minus
  `Bus.ageOf(wake)`), not the whole of it: a frame that spent 0.45 s queued
  behind a slow consumer is already 0.45 s into its own window. Armed only
  while a window is open, so an idle HUD runs no timer at all.
- frames are refused rather than guessed at — wrong schema `v` (invariant 2: a
  v2 body is not a v1 body), a wake scoring below the threshold it declares or
  whose envelope `conf` contradicts that score (invariant 4: a frame that
  disagrees with itself), a state topic hedging its `conf`, and any frame with
  no numeric `ts`. That last one is not pedantry: ordering a wake against a
  speech transition IS the listening rule, and an unorderable frame would have
  to be guessed at. With no clock pinned, `ageOf` is Infinity and there is
  therefore no `listening` at all — the A9 NaN fix pays for itself here.
- colour: teal for listening, ember for speaking. theme.toml already said why —
  ember means Jarvis is doing something, teal is "your own state, not Jarvis's"
  — and an open microphone is yours. `interrupted` is quiet: a fact worth
  reading, not an alarm worth colouring. The dot carries the accent and the
  word carries the meaning; ember never touches the text.
- proving the tests bite: 17 mutations, 17 caught. Among them — no-frame
  reading as `idle`, an unrecognised state word falling back to `idle`,
  `wakeFresh` ignoring the timer, ignoring the age, `answered`/`utteranceEnded`
  dropping their ts comparison, `answered` counting `interrupted`,
  `utteranceEnded` accepting any VAD boundary, the wake ignoring its own
  threshold or its conf, `wellFormed` dropping the `v` or the `ts` check,
  `frameOn` ignoring `linkUp`, and the expiry arming a whole window instead of
  the remainder. Two tests were written specifically because the first sweep
  showed the remainder-arming and the window-change re-arm would have survived.
- qmllint footgun, new one: `Component.createObject()` is typed `QObject`, so
  every member READ on the result is `missing-property` and `-W 0` fails the
  build. (Writes are not flagged, which is why tst_busmodel never hit it.)
  Fix is the same shape as that file's: route instantiation through an untyped
  helper, and the linter stops guessing. Worth knowing before the next test file.
- consequence worth naming: the HUD is a live bus consumer now, so `Bus` is
  built at load and its bridge child runs for as long as the shell does. The
  A5 claim "an idle HUD runs no bridge process" is no longer true and the
  README and PLAN now say so. What stays lazy is the screen.
- tests: 86 QML green (34 new), also green INSIDE the nix sandbox; 22 tools
  green. jv-hud-bridge and jarvisd untouched.
- build: `nix build .#jv-hud` ok (qmllint clean at `-W 0`, tests ran in the
  checkPhase); `nixos-rebuild build --flake .#ares` ok. Never test/switch.
  No schema, no jv-act, no boot path.
- files: shell/jv-hud/core/SpeechState.qml (new), shell/jv-hud/StatePlate.qml
  (new), shell/jv-hud/tests/tst_speechstate.qml (new), shell/jv-hud/shell.qml,
  shell/jv-hud/README.md, shell/jv-hud/qmldir + core/qmldir (generated),
  tools/gen_theme_qml.py
- commit: 769dcdd
- next: **A8** is now the highest-value small thing — theme.toml names Archivo
  and JetBrains Mono, nothing declares them, and A3 just put mono type on
  screen for the first time, so the missing font is no longer theoretical.
  Ten-minute commit, `fonts.packages` in its own change.
  Then **A4** (the live mic indicator). Note the trap found while building A3:
  it is a DIFFERENT claim from `listening` and must not be derived from it —
  jv-ears runs VAD continuously whether or not a wake window is open, so the
  mic indicator answers "is audio being captured?" while `listening` answers
  "is Jarvis attending to me?". Two signals, two elements.
  New follow-ups filed: **A12** (a `thinking` state — between `speech_end` and
  jv-voice's `speaking` frame the HUD says `idle`, which under-claims; the real
  signal is `brain.request`/`brain.response`, frozen schemas the bridge simply
  does not subscribe to — one line in `DEFAULT_TOPICS`, no schema change) and
  **A13** (StatePlate is drawn on every monitor; needs a human eye on ares to
  say whether that is right). A10 is unchanged and still wants a grep-shaped
  gate. And the HUD has now earned a human eyeball on ares: A1's "it maps" is
  still verified by construction, and A3 is the first thing worth looking at.

## 2026-09-24 — iteration 8 — A4: the recording light

- built **A4**, the live microphone indicator: `MicPlate.qml` (pixels) +
  `core/MicState.qml` (the decision, tested) + the signal underneath it in
  jv-ears. Invariant 10 calls the mic indicator "not optional and not
  fakeable"; those are two different jobs and this iteration did both.
- the trap A3 left a note about held: the mic is NOT `listening`. jv-ears
  runs VAD continuously, so `listening` answers "is Jarvis attending to me"
  and the recording light answers "is audio being captured at all". Two
  signals, two elements, and neither derived from the other. The plate is
  lit whenever the device is open, including while nobody is talking.
- what I could NOT do truthfully with today's bus, and what I did instead:
  nothing on the bus said whether the microphone was open. `sys.health`
  from jv-ears proves the PROCESS is alive, which is exactly what stayed
  cheerful through the 2026-09-15 field bug (PortAudio opened nothing, the
  stream delivered silence forever, everything downstream looked fine). An
  indicator fed by that would have been lit through the whole outage.
  So jv-ears now counts what the DEVICE hands it — `CaptureMeter` wraps the
  audio source, stamps a clock per chunk, and reports on its own heartbeat.
  The gauges ride in `metrics`, which schemas/sys.health.json declares
  free-form and service-local: **no schema change, nothing frozen touched**
  (checked against the guardrail before writing a line of it).
- `capture_age_s` is ABSENT until the device has ever delivered, never
  infinity. The bridge serializes with `json.dumps`, which writes a bare
  `Infinity`; that line would fail `JSON.parse` in BusModel and be dropped
  whole, so one un-delivered chunk would blind the HUD to the frame that
  says so. Worth knowing for every future gauge.
- the asymmetry the tests are written around: claiming a microphone that is
  closed is noise; going dark over an open one is the failure that costs
  trust. So "I cannot tell" never collapses into "off" — dropped link,
  heartbeat older than two of its own `period_s` (the schema's own
  presumed-dead rule), body `service` disagreeing with envelope `src`,
  hedged `conf`, wrong `v`, or a jv-ears too old to report gauges all read
  `unknown`. `off` and `unknown` both draw nothing, for different reasons.
- `stalled` earns its own state: the device is open (privacy-relevant, so
  the plate stays lit) and delivering nothing (Jarvis is deaf, so it says
  `MIC NO AUDIO` in `warn`, not teal). jv-ears calls the same condition
  `degraded` on the heartbeat, so `jv tap sys.health` tells the same story.
- two things fell out of building it:
  · `BusModel.latestFrom(topic, src)`. `sys.health` has one publisher per
    service, so `latest("sys.health")` answers "whoever spoke last" — a
    jv-brain heartbeat would have been read as evidence about the mic.
  · jv-ears published NO heartbeat at all when the pipeline ended
    immediately: the health task was cancelled before the event loop ever
    ran it. It now says hello before the frame loop. Found by the test that
    checks main() is actually wired to the unit-tested body — the unit
    tests were all green while the service published nothing.
- the bug this iteration nearly shipped: `Bus.qml` did not forward
  `latestFrom`, and MicState's defensive `typeof bus.latestFrom ===
  "function"` guard turned that into a HUD that shows nothing, forever,
  silently. qmllint cannot see it (the call is on an injected `var`) and
  the headless tests cannot (they drive a BusModel directly). Caught while
  writing the README table. There is now a tools test that fails the build
  if BusModel offers a function Bus.qml does not forward — verified it
  bites by deleting the forwarder.
- proving the tests bite: 17 mutations, 17 caught. QML — `unknown`
  collapsing to `off`, reading a stale heartbeat, ignoring the stall
  budget, accepting a body/src disagreement, accepting a hedged `conf` or a
  wrong `v`, arming a whole life instead of the remainder, `healthStale`
  ignoring the timer, `latestFrom` ignoring the publisher, a link drop
  keeping the source cache. Python — publishing the age as infinity, a
  stalled mic staying `ok`, stamping the clock once, not counting samples,
  a `--wav` run reporting a microphone, the heartbeat dropping `metrics`,
  and removing the pre-loop hello.
- **A8 was the plan's "ten-minute commit" and it is not one — descoped with
  the research written down.** theme.toml names Archivo, and nixpkgs has no
  `archivo`: the only packaged source is `google-fonts`, whose src is
  **1.1 GiB to download and 2.7 GiB unpacked** for one family, on a machine
  that never garbage-collects. The alternatives are a small pinned
  derivation from upstream (Omnibus-Type/Archivo, a few MB) or changing the
  face in theme.toml, which is identity and a human's call (invariant 9).
  JetBrains Mono is already in nixpkgs and is the face actually on screen
  today — every HUD element is mono. Written into PLAN A8 so the next
  iteration decides in one minute instead of researching it again.
- tests: 117 QML green (26 new), also green INSIDE the nix sandbox; 26
  jv-ears (15 new); 23 tools (1 new); 25 jv-hud-bridge unchanged and green.
- build: `nix build .#jv-hud` ok (qmllint clean at -W 0, tests ran in the
  checkPhase); `nixos-rebuild build --flake .#ares` ok. Never test/switch.
  No schema, no jv-act, no boot path, no pins.
- files: services/jv-ears/jv_ears/audio.py, services/jv-ears/jv_ears/main.py,
  services/jv-ears/tests/test_capture_meter.py (new),
  shell/jv-hud/MicPlate.qml (new), shell/jv-hud/core/MicState.qml (new),
  shell/jv-hud/tests/tst_micstate.qml (new), shell/jv-hud/core/BusModel.qml,
  shell/jv-hud/tests/tst_busmodel.qml, shell/jv-hud/Bus.qml,
  shell/jv-hud/shell.qml, shell/jv-hud/README.md, tools/gen_theme_qml.py,
  tools/tests/test_gen_theme_qml.py, qmldirs (generated)
- commit: 6796579
- next: **A6** (the `sys.health` glance) is now the cheapest real element —
  `latestFrom` is exactly what it needed, and jv-ears' `degraded` gives it
  something true to show on day one. **A12** (a `thinking` state) is still
  one line in the bridge's topic list plus one branch in SpeechState.
  New follow-up **A14**: the HUD now mirrors TWO jv-ears constants by hand
  (`wakeWindowS` 8 s, `stallS` 1 s) because nothing publishes ears'
  configuration; ears could report both in the same free-form `metrics` it
  now uses, and the HUD could stop guessing. And the HUD has earned a human
  eyeball on ares more than ever: there are two stacked plates now, on three
  monitors (A13), and nobody has ever seen one.

## 2026-09-24 — iteration 9 — B4: the two CLI paths that touch the actuator

- ladder: the last FOUR iterations were UI (A9, A7, A3, A4), so this one took
  a feature. B4 was also the smallest thing guarding the most dangerous
  surface: `jv act-log` reads back everything jv-act — the only service
  allowed to change the machine — actually did, and `jv confirm` can cause a
  destructive action to happen. Neither had a single test.
- **act-log was silently lying, and that is the real find.** It did
  `let Ok(e) = serde_json::from_str(line) else { continue };` — every line it
  could not parse simply vanished from the report. The line most likely to be
  torn is the LAST one written, i.e. the action that was running when
  something went wrong, so the failure mode was "the audit trail looks
  complete precisely when it isn't". Now: an unreadable line is rendered in
  place (`!! unreadable audit line N: <raw>`, bounded to 100 chars and
  char-boundary-safe, because a torn write can cut mid-UTF-8 and slicing
  bytes would panic and take the reader with it), a stderr warning says how
  many, and the command exits 1 so `jv act-log --tail 1 && ...` cannot
  proceed on the strength of a line nobody could parse.
- also refused: valid JSON that is not an object. Fed a bare string,
  `act_log_line` renders a plausible row of `?` that reads like a real action
  with missing fields — an invented row is worse than an admission.
- also: a blank `JARVIS_ACT_AUDIT` is now an UNSET one. An empty shell
  expansion used to become the file `""`, whose error message ("no audit log
  at ") reads as "jv-act has never acted" — the most misleading thing this
  command could say.
- logic moved to `jarvisd::cli` (`act_log_render`, `act_audit_path_from`,
  `act_log_exit_code`) so it is unit-testable; `bin/jv.rs` keeps printing and
  the exit code, per the B2 split.
- `jv confirm`: the frame is now pinned against the FROZEN `action.confirm` v1
  binding — kind=answer, request_id, granted, answered_by=cli, conf 1.0, and
  the request-only fields absent — because jv-act acts only on exactly that
  (`services/jv-act/src/service.rs` ignores an answer whose `answered_by` is
  not `cli`, since it echoes its own voice/timeout answers on the same topic).
  An answer that is neither yes nor no must not reach the bus at all, in
  EITHER direction: "maybe" becoming a denial would be as wrong as it
  becoming a grant.
- two things fell out of building it:
  · `broker::from_value_named`, the missing inverse of `to_value_named`. The
    bus convention spells an enum as its snake_case STRING, and
    `rmpv::ext::from_value` only accepts serde's tagged forms — so it rejects
    every generated body with a `kind`/`state`/`answered_by` in it, and no
    Rust consumer could read a schema binding back off the wire. Found by the
    confirm test failing with "invalid type: string \"answer\"".
  · `common::subscribe_live`, which PROVES a subscription is live (by probing
    with frames of its own until one returns) before a one-shot publisher
    runs. The broker does not ack a `Sub`, so "subscribe, then spawn
    `jv confirm`" would have been a race — exactly the flake that makes an
    unattended gate useless.
- proving the tests bite: 14 mutations, 14 caught — skipping an unreadable
  line, renumbering lines under `--tail`, accepting non-object JSON, byte-
  slicing the raw echo (this one SURVIVED at first: my UTF-8 test used
  `"é"*300` and the 100-byte cut landed exactly on a char boundary, so the
  test was tightened to an odd leading byte before it bit), an unbounded
  echo, always exiting 0, dropping the stderr warning, an empty env var as a
  path, confirm claiming `answered_by=voice`, confirm sending kind=request,
  confirm hedging its `conf`, a bad answer becoming a denial, and both halves
  of the wire convention.
- jv-act itself untouched (human-review-only). Its duplicate copy of the
  audit path default is now proposal **R2** in the backlog: one import and
  one deleted function, and the failure mode if someone moves the file and
  misses the reader is `jv act-log` printing an older complete-looking
  history, or claiming jv-act never acted.
- tests: 46 green, was 30 (25 lib, 7 bus, 14 cli); also green INSIDE the nix
  sandbox.
- build: `nix build .#jarvisd` ok; `nixos-rebuild build --flake .#ares` ok.
  Never test/switch. No schema, no jv-act, no boot path, no pins.
- files: services/jarvisd/src/cli.rs, services/jarvisd/src/bin/jv.rs,
  services/jarvisd/src/broker.rs, services/jarvisd/tests/cli.rs,
  services/jarvisd/tests/bus.rs, services/jarvisd/tests/common/mod.rs,
  docs/optimization-backlog.md
- commit: 3a3e8ec
- next: back to UI — **A6** (the `sys.health` glance) is the cheapest real
  element and `latestFrom` + jv-ears' `degraded` already give it something
  true to show; **A12** (a `thinking` state) is still one line in the
  bridge's topic list plus one branch in `core/SpeechState.qml`. New
  follow-up **B5**: `jv act-log` can print but cannot be asked a question —
  `--since` and an outcome filter over the entries it already parses are pure
  additions to `act_log_render`. And the standing one: nobody has ever LOOKED
  at this HUD on ares (A13), which no amount of green tests fixes.

## 2026-09-24 — iteration 10 — A6: the sys.health glance

- built **A6**, the HUD's third real element: `core/HealthState.qml` (logic,
  tested) + `HealthPlate.qml` (pixels), wired into the corner stack under
  StatePlate and MicPlate. Every service already heartbeats on `sys.health`
  with a state word, an uptime and the period it promises to speak again on,
  and jv-brain adds `llm_rung`/`llm_gpu` to the free-form `metrics` — nothing
  turned any of it into something a human could see. A degraded brain, or a
  service that fell over three minutes ago, looked exactly like a working
  machine.
- what it shows is the SHORT list: what is not well, worst first, and
  NOTHING when every service heard from says `ok`. §06's earned emptiness
  taken literally — a readout that is on screen all day is a readout nobody
  reads, and this one only has to be right the day it appears. Which makes
  the silence ambiguous (nothing wrong / cannot see the bus) and that is
  deliberate: both are the same amount of information, and the alternative
  is a plate reading "all services ok" from a bus that died, which is the
  exact failure invariant 10 exists to prevent.
- the three rules it is built on, each of which is where the tests are:
  · **the roster is who has SPOKEN.** Nothing anywhere on the bus announces
    which services are SUPPOSED to be running. Hardcoding that list in the
    HUD would be it reporting on a machine it has not heard — and would rot
    the first time a service is added. So a service that never started is
    absent, and absence claims nothing in either direction.
  · **a heartbeat expires.** schemas/sys.health.json: two missed periods =
    presumed dead, so a frame speaks for two of its own periods and no
    longer. Nothing publishes "jv-brain died", so a timer is the only way
    the HUD ever learns it. ONE timer for the whole roster, armed for the
    soonest deadline among the services still believed — not one per
    service: the roster is discovered at runtime, and a HUD with nothing on
    the bus must run no timer at all (§06: 0 fps when nothing happens). On
    a healthy machine each heartbeat pushes the deadline out, so it is
    restarted forever and never actually fires.
  · **unreadable is not fine.** Wrong schema `v`, a hedged `conf`, a body
    naming a different service than the envelope said published it, no
    usable `period_s`, a state word outside the frozen enum: all `unknown`,
    all reported, none rendered raw. `unknown` and `lost` rank ABOVE
    `degraded` on purpose — a service that told us it is impaired is in
    better shape than one we cannot hear at all.
- the llm rung rides the same expiry and appears only when the brain is on
  the CPU floor. No service calls that a fault, so it is not coloured as
  one, but it is the only thing on this machine that explains a Jarvis that
  takes thirty seconds to answer (invariant 6). A rung read off a stale
  heartbeat describes a process that may not be running, so that is not
  shown either.
- one real design bug, found by the tests and worth recording: the expiry
  timer first RECOMPUTED every age when it fired. Correct-looking, and in
  the tests (whose monotonic clock is frozen by hand) it meant a claim
  un-expired itself and re-armed at the 1 ms floor — a spin, not a HUD. The
  fix splits the two reasons to re-arm: a frame arriving reassesses
  everything from the frames, and the timer firing expires exactly what it
  was counting down for, because the wall clock waiting those milliseconds
  IS the evidence. A frozen clock can no longer produce a busy loop.
- also landed: `BusModel.publishersOf(topic)` — the roster the model could
  always answer and had no way to be asked — forwarded by `Bus.qml`, which
  the existing tools test enforces.
- proving the tests bite: 22 mutations, 21 caught. Rejecting the version /
  conf / service-name / period gates, rendering an undefined state word
  raw, never losing anyone, only the timer being allowed to expire a
  heartbeat, the timer expiring nobody, a new frame failing to revive,
  arming for the LAST deadline instead of the first, a stale rung still
  counting, whoever-spoke-first owning the rung, an unknown backend reading
  as `gpu`, a dead link still reporting, the roster in arrival order, and
  both halves of `publishersOf`.
  The ONE survivor: deleting the name tiebreak from the `findings` sort.
  It is equivalent under the current code — the roster is already
  name-sorted when `findings` filters it, so a stable sort gives the same
  answer. It is kept anyway, because "the engine's sort happens to be
  stable" is not a guarantee a rendered order should rest on.
  Two other mutations survived at first for a related reason and were then
  caught by a change to the TESTS: driving HealthState through a real
  BusModel can never prove HealthState sorts its own roster or refuses a
  dead link, because BusModel already sorts its publishers and empties
  itself on a drop. A stub bus with the same API and none of the good
  manners now proves both — the guarantee was doubly held and singly
  tested, which is how a refactor deletes one silently.
- tests: `bash ops/ralph/qmltest.sh` — 158 green, was 123 (35 new: 32 for
  HealthState, 6 for publishersOf, minus overlap). `bash
  ops/ralph/runtests.sh tools` — 23 green. Both also green INSIDE the nix
  sandbox via jv-hud's checkPhase (qmllint then qmltestrunner).
- build: `nix build .#jv-hud` ok; `nixos-rebuild build --flake .#ares` ok.
  Never test/switch. No schema change, no jv-act, no boot path, no pins.
- files: shell/jv-hud/core/HealthState.qml (new),
  shell/jv-hud/HealthPlate.qml (new), shell/jv-hud/tests/tst_healthstate.qml
  (new), shell/jv-hud/core/BusModel.qml, shell/jv-hud/Bus.qml,
  shell/jv-hud/shell.qml, shell/jv-hud/tests/tst_busmodel.qml,
  tools/gen_theme_qml.py, the two generated qmldirs
- commit: 7406009
- next: **A12** is now the cheapest thing left on Track A — one line in the
  bridge's `DEFAULT_TOPICS` plus one branch in `core/SpeechState.qml`, and
  it closes the gap where Jarvis is thinking and the HUD says `idle`.
  **A14** (jv-ears publishing its own budgets on sys.health) is more
  valuable and now cheaper than it was, since HealthState already reads
  free-form `metrics` off a heartbeat the same way. New follow-up **A15**:
  three plates now decide independently when to fade, and shell.qml's
  `visible` is a growing hand-maintained OR of every one of them — the next
  element that forgets to add itself will be invisible and nothing will
  notice. And the standing one, unchanged and unfixable by tests: nobody
  has ever LOOKED at this HUD on ares (A13).

## 2026-09-24 — iteration 11 — A12: "thinking", the state the HUD was missing

Picked A12 off the ladder (UI first; last three iterations were A6/B4/A4, so
UI was still the first choice, and the previous entry's `next:` pointed here).

- the hole: between Jarvis having your words and you hearing anything back,
  `SpeechState` answered `idle` — and `StatePlate` draws NOTHING for idle.
  So the one moment the user is actually waiting on the HUD was the one
  moment it went dark. It now says `thinking`, and only ever while it can
  point at a frame.
- nothing on the bus announces "the brain accepted this", so the prompt has
  to be RECOGNISED. Exactly two things are recognisable as one:
  a wake-gated utterance ENDING — jv-ears disarms and transcribes at that
  boundary, and jv-brain answers every transcript final, so it is a question
  in flight — and a `brain.request`, which is how the non-voice frontends
  (jv CLI, the replay harness) ask. A `speech_end` with no wake behind it is
  just speech in the room (ears' VAD runs continuously, per A4) and means
  nothing here; a test pins that, because it is the difference between a HUD
  that reports Jarvis working and one that reports anyone talking.
- three things end it: `brain.response` — the ONLY thing that can for a
  `speak:false` CLI query or a reply that errored and was never spoken; the
  first `speaking` frame after it; and `thinkWindowS` (30 s) under a brain
  that died mid-turn. That constant deliberately mirrors NO service's
  configuration, so it does not join A14's pile of hand-copied budgets: it
  is a policy about how long the HUD is willing to assert work it cannot
  see, and past it we fall back to jv-voice, which under-claims. The CPU
  rung that explains a genuinely slow answer is already on screen (A6).
- precedence, written down because it is the whole design: `listening`
  first (the microphone is the costly claim, so re-asking mid-answer reads
  as listening), then whatever jv-voice says is audible RIGHT NOW, then
  thinking. `speaking`/`interrupted` are observations and thinking is an
  inference; the inference must not talk over the observation.
- one real design bug, found by the tests: "the user has heard this answer
  START" cannot be derived. `bus.latest()` holds only the newest frame per
  topic, so the `speaking` frame is GONE the moment jv-voice publishes the
  idle after it — and since jv-brain publishes one speech.say per SENTENCE,
  a derived version forgot between every pair of sentences and flipped the
  word back to `thinking` once per sentence. It is a latch now, and it is
  set on both edges that can make it true: a speech frame arriving, and the
  prompt changing under an already-speaking Jarvis. The second edge is not
  hypothetical — frames queue behind a slow consumer, so the answer can
  arrive before the boundary that opened the window it closes, and a
  `repliedAloud` binding would never have fired for it at all.
- a known under-claim, recorded rather than fixed: two prompts in quick
  succession can have the first one's reply close the second one's window,
  because matching is by `ts` and not by id. `brain.response.in_reply_to`
  names the audio.transcript final for the voice path, and the HUD does not
  subscribe to transcripts (partials would flood the pipe for nothing). It
  errs toward showing less, which is the direction this file always errs in.
- no schema change. `brain.request`/`brain.response` were already frozen;
  the bridge just subscribes. They are the first topics it carries whose
  bodies hold conversation TEXT — that stays on this machine like everything
  else (invariant 7), and no element reads those bodies: the HUD uses only
  the fact that a frame exists and when. Said so in the bridge, so a future
  element that wants the words makes that choice deliberately.
- `StatePlate` needed no code at all — `thinking` falls into the quiet
  branch of `dotColor`, so it is a word and not a third accent. §06 spends
  the ember on Jarvis speaking and the teal on your open microphone;
  working is neither.
- proving the tests bite: 18 mutations, 17 caught. Both latch edges, the
  latch failing to reset for a new prompt, any speech_end opening a window,
  brain.response unable to close one, a reply answering a prompt it
  predates, the older of two prompts owning the window, thinking outranking
  what is audible, the window never timing out, a late prompt getting a
  whole fresh window, an unaged prompt counting as fresh, an empty or
  sourceless or hedged request being believed, an unreadable reply counting
  as a reply, an unknown state word falling back to idle, and thinking
  earning an accent.
  The ONE survivor: dropping topic+src from `promptKey`, leaving seq@ts.
  Equivalent in practice — the key exists only to detect a CHANGE, and a
  cross-publisher `seq` collision (jv-ears and jv-cli both start at 0) would
  also need an identical monotonic `ts`, which the clock does not hand out
  twice. Kept anyway, because it costs one string concat and the reasoning
  above is the kind that stops being true quietly.
- tests: `bash ops/ralph/qmltest.sh` — 189 green, was 158 (31 new).
  `bash ops/ralph/runtests.sh jv-hud-bridge` — 25. `bash
  ops/ralph/runtests.sh tools` — 23. All also green INSIDE the nix sandbox
  via jv-hud's checkPhase (qmllint then qmltestrunner).
- build: `nix build .#jv-hud` ok; `nixos-rebuild build --flake .#ares` ok.
  Never test/switch. No schema change, no jv-act, no boot path, no pins.
- files: shell/jv-hud/core/SpeechState.qml,
  shell/jv-hud/tests/tst_speechstate.qml, shell/jv-hud/StatePlate.qml,
  services/jv-hud-bridge/jv_hud_bridge/bridge.py
- commit: 7eca614
- next: **A16**, discovered while building this and the most valuable thing
  on the board now — jv-voice publishes a speaking/idle PAIR per sentence,
  so one answer makes StatePlate blink off and on once per sentence. A12
  stops that gap from lying, not from flickering, and §06 calls flicker
  churn. jv-voice already tracks `reply_group` for barge-in, so it can know
  a streamed reply is ONE utterance; that is a jv-voice change (permitted —
  not jv-act, not a schema) and it wants care around barge-in and the
  urgent-preempt path. Otherwise **A14** (ears publishing its own budgets
  on sys.health, deleting two hand-mirrored constants) is still the best
  non-UI slice. And the standing one, unchanged and unfixable by tests:
  nobody has ever LOOKED at this HUD on ares (A13, A10).

## 2026-09-24 — iteration 12 — A16: one answer is one utterance

Picked A16, which the previous entry's `next:` called the most valuable thing
on the board. It is a HUD problem fixed in jv-voice (permitted — not jv-act,
not a schema), and while proving it I found it was never only a HUD problem.

- the flicker: jv-brain streams the completion and publishes one speech.say
  per SENTENCE (all sharing a `reply_group`), and jv-voice answered each one
  with its own `speaking` -> `idle`. So one answer read as four answers.
  A12 stopped the gap between hearing you and answering from LYING; it did
  not stop the answer itself from blinking, and §06 calls blinking churn.
- the part that was not cosmetic, and is why this was worth an iteration:
  **jv-ears releases its half-duplex gate on `idle`** (main.py
  `follow_speech_state`). jv-voice synthesizes sentence N+1 only after N
  finishes playing (backlog entry on prefetch), so every inter-sentence
  `idle` reopened the utterance gate for the length of a Piper synth while
  Jarvis was still mid-answer — and the sink+mic chain delivers his last
  samples ~350 ms late (ears' `suppress_tail_ms` exists for exactly that).
  "Jarvis hearing Jarvis" was fixed in 7f39196; streaming quietly reopened
  a slice of it. The gate now stays closed for the whole turn.
- so the unit is the TURN. `_speak_turn` speaks an item and then the rest of
  its reply_group as the sentences arrive, publishing one `speaking` per
  sentence (each carries its own say_id — the schema says speech.state
  reports progress against a say_id, and `jv tap --latency` keys off
  speech.say, so nothing loses resolution) and ONE `idle` when the turn
  drains. `interrupted`/`error` are unchanged: they end the turn where they
  happen. No schema change was needed, and the contract already anticipated
  this — speech.state's description says `interrupted` is followed by `idle`
  OR the next `speaking`.
- two real bugs fell out of thinking in turns, both about the gaps INSIDE
  one:
  1. `self._speaking` used to be cleared after every sentence, so a wake
     landing between two sentences hit `if self._speaking` and did nothing
     — no interrupt, no group drop, and sentence N+1 then played over the
     user who had just barged in. It now stays set across the turn.
  2. `_drop_group` only purged what was ALREADY QUEUED. jv-brain does not
     subscribe to audio.wake (checked — it has no barge-in path at all), so
     it keeps publishing the remaining sentences of an interrupted reply,
     and those arrived after the purge and were spoken. A dropped group is
     remembered now and `_enqueue` refuses it. Bounded at 8: this service
     runs for weeks, and uuid4 groups older than the last handful are over.
     That bound is the same instinct as `jv tap`'s utterance ring.
- `TURN_GAP_S` = 0.5 s, and what it is allowed to mean matters. It bridges
  the BUS, not the brain: sentence N+1 is normally already queued (the LLM
  generates faster than Piper speaks), so the only gap worth covering is a
  frame published as the previous sentence ended and still in flight. Past
  it we stop asserting a turn we can no longer see — which is what a brain
  that died mid-answer looks like, and the CPU rung that explains a
  genuinely slow answer is already on screen (A6). Deliberately NOT a
  mirror of any other service's constant, so it does not join A14's pile.
- the gap is reactive, not polled: `_enqueue` and `_interrupt` set a
  `_nudge` event, cleared before the queue is re-scanned so no wakeup can
  be lost. That is not tidiness — polling or waiting the budget out would
  add up to half a second of silence before the next sentence's synthesis
  starts, and half a second before jv-ears learns a barge-in ended the
  turn. Both are pinned by timing assertions (`< TURN_GAP_S / 2`), which
  is what finally killed the two mutations that survived the first pass:
  without them, an interruption-blind gap still ended the turn with the
  same STATES, just late, and tests that only read states cannot tell the
  difference.
- one judgement call, written down: a wake in the gap reports
  `idle(say_id, completed)`, not `interrupted`. `reason` is "why the
  previous utterance ended" and that utterance did finish playing — it is
  the TURN that was cut. The wake itself is on the bus for anyone who
  wants it, and both consumers only need the level.
- second judgement call: a turn's sentences are taken out of FIFO order if
  something unrelated is queued behind them. FIFO is between turns; an
  announcement from elsewhere belongs after the answer, not wedged between
  two of its sentences. Urgent still preempts, exactly as before.
- proving the tests bite: 11 mutations, 11 caught — a zero gap, a dropped
  group that is not remembered, `_drop_group` forgetting to record, no
  merging at all, a gap blind to interruption, an unbounded gap, an idle
  after every sentence, the speaker forgotten between sentences, only the
  queue HEAD able to continue a turn, and each of the two nudges removed.
- tests: `bash ops/ralph/runtests.sh jv-voice` — 17 green, was 10 (7 new).
  The 10 old ones passed untouched, which is the claim that matters: the
  single-utterance, wake, preempt and low-priority contracts did not move.
- build: `nixos-rebuild build --flake .#ares` ok. Never test/switch. No
  schema change, no jv-act, no boot path, no pins.
- files: services/jv-voice/jv_voice/service.py,
  services/jv-voice/jv_voice/player.py (FakePlayer grew a `finished` event
  so a test can act in the gap deterministically),
  services/jv-voice/tests/test_voice_service.py
- commit: 8944abe
- next: **A14** is the best non-UI slice and it is now cheap to justify —
  the HUD hand-mirrors two jv-ears constants, and this iteration just added
  a third hand-tuned budget to the system's timing story. Otherwise **A15**
  (the HUD's `visible` OR grows a term per plate and nothing notices when
  one is missing) is small and closes a real quiet-failure hole. And the
  standing one, unchanged and unfixable by tests: nobody has ever LOOKED at
  this HUD on ares (A13, A10) — and nobody has heard a streamed reply since
  this change, so the first live answer on ares is worth listening to for a
  seam between sentences.

## 2026-09-24 — iteration 13 — A15: the surface asks the stack, not a list

Picked A15, the smaller of the two the last entry offered, because the hole it
closes is the kind nothing else in the build can see. UI again, and the first
pure-HUD iteration since A12.

- the bug that had not happened yet: the HUD's surface is unmapped by design,
  so ONE expression decides whether it reaches the screen at all, and that
  expression was a hand-written OR in `shell.qml` — `statePlate.shown ||
  statePlate.lit || micPlate.shown || ...`, two terms per element, six by the
  third plate. Every element I have added this week had to remember to add
  itself to it. The one that forgets would draw nothing, on a surface that is
  invisible on purpose: no test fails, no warning fires, and the symptom is
  "the HUD never appeared", three iterations after the cause.
- the fix is to stop keeping the list. `core/PlateStack.qml` is a Column that
  asks its own children the two questions a plate can answer — `shown` (it has
  something true to say right now) and `lit` (it is still on screen, INCLUDING
  its fade out) — and `shell.qml` maps the surface while `stack.anyLit`.
  Nothing upstream knows how many plates there are.
- both properties are load-bearing, and the reason is not symmetry.
  `shown` is what MAPS the surface: at the instant a frame lands no opacity
  has moved yet, so `lit` is still false — and an unmapped window has no
  animation driver, so if the surface waited for `lit` the fade that would
  have lit it would never run. That is a deadlock, not a flicker. `lit` is
  what keeps the surface mapped while the last plate evaporates, so the exit
  is an element fading and not a window vanishing out from under it.
- a JS block rather than a chain of ORs, because QML tracks what a binding
  READS: every `shown`/`lit` touched becomes a dependency, and `children`
  itself is one, so a plate created later counts too. The early `return true`
  is safe for the same reason — if the child that said yes goes quiet, the
  re-run reads the ones after it (that one has a test, because a cache would
  pass every other test in the file).
- the judgement call, written down: a child that answers NEITHER question is
  counted as drawing. Of the two ways to be wrong about an unaskable plate,
  "the surface stays mapped with nothing on it" costs idle frames and "the
  plate that was trying to warn you never appeared" is exactly the bug A15
  exists to kill. Fail toward the truth being visible.
- and then keep that branch unreachable, since a fail-safe nobody checks is
  just a slow leak: a tools test requires every direct child of the stack to
  be a `*Plate` declaring `shown`, `lit` and its own `visible: shown || lit`,
  and a second one forbids the surface's `visible` from naming a plate again.
  The per-plate `visible` moved OUT of shell.qml and into the plates — it is
  each plate's own business whether it takes room in the stack, and it is
  what makes the survivors close up over a silenced one rather than leaving
  a hole where a signal used to be.
- what is deliberately NOT asserted, and why it is in a comment in the test
  file: that the plates below a silenced one actually close up. A Column
  repositions on polish, and the offscreen window these tests run in is never
  exposed, so it has no polish cycle — `tryCompare` waits out its two seconds
  and reads the old layout. That is Qt's behaviour rather than ours; what
  makes it fire is the per-plate `visible`, which is checked where it can be.
  The tests do pin that a PlateStack is a positioner at all, so the plates
  cannot land on top of each other.
- proving the tests bite: 9 mutations on PlateStack, 9 caught — never lit,
  always lit, only the first child consulted, forgetting `shown`, forgetting
  `lit`, the fail-safe inverted, the fail-safe fired for a child that answers
  one of the two, the base type demoted to Item, and `anyLit` computed once at
  startup instead of bound. Plus 5 on the two tools gates (the OR grown back,
  a `Text` child wedged into the stack, a plate with no `visible`, a `visible`
  that forgot `shown`, a plate that renamed `shown`) — all 5 bit.
- tests: `bash ops/ralph/qmltest.sh` — 202 green, was 191 (11 new);
  `bash ops/ralph/runtests.sh tools` — 25 green, was 23.
- build: `nix build .#jv-hud` (qmllint + the same tests in checkPhase) and
  `nixos-rebuild build --flake .#ares` both ok. Never test/switch. No schema
  change, no jv-act, no boot path, no pins.
- files: shell/jv-hud/core/PlateStack.qml (new),
  shell/jv-hud/tests/tst_platestack.qml (new), shell/jv-hud/shell.qml,
  shell/jv-hud/{State,Mic,Health}Plate.qml, shell/jv-hud/core/qmldir,
  tools/gen_theme_qml.py, tools/tests/test_gen_theme_qml.py
- commit: 0dbe844
- next: **A10** is now the last unguarded corner of invariant 10 and it is the
  sibling of what just landed — the surface properties that make the HUD safe
  (keyboardFocus None, exclusionMode Ignore, the empty input mask) are still
  asserted by nobody, and `surface_visible_expr`/`plate_stack_children` in
  tools/tests are the parsing this iteration built for exactly that kind of
  gate. Otherwise **A14** (the HUD hand-mirrors two jv-ears constants) or
  **B5** (`jv act-log --since/--failed`), both small and self-contained. The
  standing one, unchanged: nobody has ever LOOKED at this HUD on ares — and
  this iteration moved the expression that decides whether it appears at all,
  so the next human on that machine should run `JV_HUD_SELFTEST=1 jv-hud`
  once and then watch a real wake word light the corner.
