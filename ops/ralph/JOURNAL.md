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
