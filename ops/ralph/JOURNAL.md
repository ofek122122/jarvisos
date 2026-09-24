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

## 2026-09-24 — iteration 14 — A10: the surface properties get a witness

**what**: the last corner of invariant 10 that nothing was watching. `shell.qml`
declares six things that make the HUD safe — `WlrLayershell.keyboardFocus:
WlrKeyboardFocus.None`, `focusable: false`, `exclusionMode:
ExclusionMode.Ignore`, `WlrLayershell.layer: WlrLayer.Top`, `color:
"transparent"` and `mask: Region {}` — and until this commit every one of them
was asserted by nobody. Three new gates in `tools/tests/test_gen_theme_qml.py`,
and a CI job so they run somewhere other than Ralph's good intentions.

**why this and not something else**: the journal named it as next, and it is the
sibling of A15 — same file, same class of rot. The difference between qmllint
and a gate is the whole point: qmllint proves `WlrKeyboardFocus.None` RESOLVES,
and it would be exactly as happy with `.Exclusive`. Every one of these is a
property whose wrong value is invisible on a surface that is unmapped most of
the time. Nothing in the build would fail; you would find out by having a click
eaten, or your keyboard taken mid-sentence, on a machine where the HUD is
supposed to be the thing that is never in the way.

**the decision that shaped it — a gate, not a refactor.** The obvious move was
to lift the safety properties into a `HudSurface.qml` component so a second
surface could not be written unsafely, exactly as A15 lifted the visible-OR into
`PlateStack`. I did not, and the reason is the same reason A10 was hard in the
first place: there is no way to run Quickshell here. A new component in the
window-creation path would have been verified by qmllint and by nothing else,
on the one surface nobody has ever LOOKED at. A gate is pure source analysis —
it cannot break a runtime that no test can reach. And per-window rather than
per-file, it covers the future surface just as well as the component would
have: the check is keyed on `PanelWindow`/`FloatingWindow`/`PopupWindow`, so a
second window is checked the day it is written, in whatever file it lands.

**what is actually asserted**:
- each of the five properties bound exactly once, to exactly one permitted
  value. Not "the word appears in the file" — `assigned()` returns the list, and
  the assert compares it to `[value]`, so a duplicate binding or a missing one
  reads the same as a wrong one.
- `mask` matches `Region\s*\{\s*\}` — EMPTY. `mask: Region { Rectangle {} }`
  passes any grep for "mask: Region" and is the opposite of what §06 wants.
- `exclusiveZone`, if present at all, is 0.
- at least one window was found. A gate that silently stops seeing its subject
  is worse than no gate; if the regex rots, it fails loudly.
- nothing in the HUD reaches for the keyboard: `forceActiveFocus`, `focus:
  true`, `activeFocusOnTab: true`, `Keys.`/`Keys {`, `TextInput`/`TextEdit`/
  `TextField`/`TextArea`/`FocusScope`, `WlrKeyboardFocus.Exclusive|OnDemand`.
  These are INERT today — the compositor is already told not to offer the
  keyboard — which is precisely why one would get committed without a thought,
  and then be found sitting there the day someone loosens `keyboardFocus`.
  Taking the keyboard is a human's decision about invariant 10 and it starts at
  that property, not at a widget that quietly assumes it.
- nothing waits on a pointer: `MouseArea`, `HoverHandler`, `TapHandler`,
  `DragHandler`, `PinchHandler`, `WheelHandler`, `PointHandler`. With an empty
  input region these can never fire — dead code that reads like a feature, and
  the kind of thing someone later "fixes" by opening the mask.

**the parsing, and why it is not a grep**: `window_bodies()` collects each
window's OWN lines (brace depth tracked per line, nested blocks dropped) because
`shell.qml` already contains `color: Theme.ground` three levels down, inside the
self-test marker's Rectangle. A file-wide regex would have matched it and passed
forever while the surface's own colour went opaque. Proven, not assumed: a
`focusable: true` wedged into that same nested Rectangle leaves all 28 tests
green, and the real line still governs. `strip_qml_comments()` exists for the
same reason in reverse — the header comment of shell.qml quotes every one of
these properties, so a naive scan would have read the documentation instead of
the code.

**proving the gates bite**: 18 mutations of shell.qml, 18 caught — each of the
five values changed to a plausible wrong one (`focusable: true`,
`keyboardFocus: Exclusive`, `keyboardFocus: OnDemand`, `exclusionMode: Normal`,
`layer: Overlay`, an opaque surface colour), each of the six lines deleted
outright, a non-empty `Region`, an `exclusiveZone: 32` added, a `MouseArea`, a
`TextInput`, an `Item { focus: true }`, and the window type renamed away
entirely (caught by the "found no window" assert). Plus the negative proof
above, and a second unsafe `PanelWindow` in a new file, which the gate caught in
a file it had never been told about. Worth recording: the first mutation run
reported three MISSES, and all three were my harness replacing the first
occurrence of the string — which was in shell.qml's header comment. The gate was
right and the mutation never reached the code. That is a good argument for
anchoring mutations on the code line and not on the token.

**the other half — a gate nobody runs is not a gate.** `tools/tests` has never
been in CI. `.github/workflows/check.yml` checks the flake, jarvisd, jv-act and
seven Python services, but the theme-drift check (invariant 9), A7's
"nothing animates around Motion", A15's two plate-stack gates and now these
three ran only when the loop remembered to type `runtests.sh tools`. They are
pure source checks — no GPU, no disks, no models, 0.11 s — so there was never a
reason beyond nobody having done it. Added as a `tools` job; verified it runs
green from the repo root, which is where CI runs it, not from `tools/`.

**what this does NOT prove, and it matters**: that Quickshell APPLIES these
properties. This is source analysis, and A10's other half — a `quickshell`-run
smoke test — still needs a compositor, which the sandbox does not have and CI
does not either. The offscreen window `qmltestrunner` uses is never exposed, so
it has no polish cycle and cannot answer a surface question at all (established
in A15). So: the HUD's source now cannot silently stop being safe, and whether
the safe source produces a safe surface remains a thing a human confirms once
on ares.

- tests: `bash ops/ralph/runtests.sh tools` — 28 green, was 25 (3 new);
  `bash ops/ralph/qmltest.sh` — 202 green, unchanged (no runtime change).
- build: `nix build .#jv-hud` and `nixos-rebuild build --flake .#ares` both ok.
  Never test/switch. No schema change, no jv-act, no boot path, no pins.
  shell.qml's only diff is a comment; the QML the HUD runs is byte-identical
  apart from it.
- files: tools/tests/test_gen_theme_qml.py, .github/workflows/check.yml,
  shell/jv-hud/shell.qml (comment only), shell/jv-hud/README.md
- commit: fe43c88
- next: Track A's remaining items are all blocked on a human or on hardware —
  **A8** (fonts) needs an identity call (invariant 9), **A11** needs the frozen
  schemas of proposal R1, **A13** needs an eye on ares. **A14** is the one
  unblocked UI item and it is good: the HUD hand-mirrors two jv-ears constants
  (`wakeWindowS` 8 s, `stallS` 1 s) with "keep this at or below" comments that
  are waiting to rot, and ears already publishes free-form `metrics` on
  sys.health, so it can report its own budgets with no schema change. Otherwise
  **B5** (`jv act-log --since/--failed`, small and pure) or **B6** (jv-brain has
  no barge-in path — the real fix behind A16's downstream patch, and the largest
  honest bug left in the voice loop). The standing one, unchanged: nobody has
  ever LOOKED at this HUD on ares. `JV_HUD_SELFTEST=1 jv-hud`, then a real wake
  word.

## 2026-09-24 — iteration 15 — A14: the service states its own budgets

**what and why.** The HUD kept two jv-ears constants in QML by hand:
`wakeWindowS` (8 s, ears' `wake_timeout_s` — how long a wake word keeps
meaning `listening`) and `stallS` (1 s, `CaptureMeter.STALL_S` — how long an
open microphone may go quiet and still read as `live`). Each sat under a
comment asking whoever retuned the service to remember the HUD. That is not a
mechanism, it is a hope, and the failure is silent and one-directional: retune
ears down and the HUD goes on claiming an open microphone after ears has
disarmed. Invariant 10 says that indicator is not fakeable; a stale copy of
someone else's configuration is a slow way to fake it.

So jv-ears states what it enforces. `sys.health.metrics` is free-form and
service-local by schema, which is the same door A4's mic gauges went through —
no schema change, nothing frozen touched (invariant 2), and the HUD stays a
pure consumer.

**what ears publishes**: `EarsPipeline.budgets()` → `wake_timeout_s`, read off
`self._wake_timeout / sample_rate` — the sample-clock count the code actually
compares against, NOT `cfg.wake_timeout_s`. Same reasoning as CaptureMeter
counting what the device delivered: what runs is the truth, and today the two
differ by at most one sample. `CaptureMeter.metrics()` → `capture_stall_s`,
which rides from the very first heartbeat, before any audio has arrived —
unlike `capture_age_s`, which is absent until there is one. A budget is not a
measurement and must not wait for one; a mic that has NEVER delivered is
exactly when a consumer needs the budget. `health_body` takes `budgets` as a
REQUIRED argument (a caller that forgets is a TypeError here, not a consumer
guessing over there) and floats every value on the way out, so a non-numeric
budget raises in jv-ears instead of riding out as a string the HUD would
refuse in silence.

**what the HUD does with it**: `core/EarsBudgets.qml`, the one place that
reads them; StatePlate and MicPlate feed them into SpeechState/MicState, whose
own properties stay plain inputs (they each decide one thing and take their
inputs — the A9 rule holds). The shipped defaults remain in QML as fallbacks,
because the HUD has to say something before the first heartbeat lands and
because zero would close every window instantly. They are mirrors still — but
pinned mirrors: `tools/tests` now fails the build if a default drifts from the
Python that enforces it, if a mirror is renamed out of the gate's sight (the
"at least two of these exist" assert), if a ceiling drops to or below ears'
own tuning, or if a plate stops binding the reported value and quietly runs on
the fallback. That last one is the gate that matters most: it is invisible
otherwise, because the HUD would go on drawing a perfectly plausible
indicator.

**the deliberate asymmetry**: budgets do NOT expire with the heartbeat that
carried them, while MicState's gauges expire after the two periods the schema
grants them. A gauge describes a moment; a budget describes how a service is
CONFIGURED and stays true until it says otherwise. jv-ears beats immediately
on start, so a retuned restart lands within a frame, and a jv-ears too dead to
beat publishes no wakes for the window to bound anyway. Both directions are
pinned in tests, including a heartbeat with no numeric `ts` — which MicState
refuses outright and this accepts, because there is nothing here to age.

**refusing a number**: a reported budget must be a number (`typeof` first —
`"12" > 0` is true in JavaScript, and a string budget is a jv-ears we do not
understand), positive, and under a ceiling (60 s wake, 10 s stall). The
ceiling is not fussiness: the value ends up in a `Timer` interval, and an
infinite window never closes. Refused means fall back, never zero.

**proving it bites — 35 mutations, and the first round was the useful one.**
13 against the tools gates (ears retuned in either file, each QML default
drifted, a mirror renamed, a ceiling dropped below ears' tuning, the budget
renamed out of config.py, each plate's binding removed or replaced with a
literal, an EarsBudgets deleted) — all 13 caught. 6 against jv-ears (the
budget dropped from the meter, made to wait for the first chunk, the merge
removed, the float() coercion removed, main no longer asking the pipeline, the
pipeline reporting cfg instead of what it enforces) — all 6 caught. 16 against
EarsBudgets — 13 the first time, and **3 MISSED**, all three real:
  · `isFinite(v)` was unreachable. +Infinity already fails the ceiling, and
    -Infinity/NaN already fail `> 0`. Deleted, and the comment now says the
    ceiling does that work — dead defensiveness reads like protection.
  · a numeric STRING would have sailed through: no test used one. Now one does.
  · the `linkUp` guard could not be reached through BusModel at all, since
    BusModel drops every frame when the bridge dies. Pinned through a
    hand-built bus that reports the link down while still holding a frame —
    the exact case the guard exists for.
All three re-run and caught afterwards.

- tests: `bash ops/ralph/qmltest.sh` — 228 green (was 202; 26 new);
  `bash ops/ralph/runtests.sh tools` — 30 (was 28);
  `bash ops/ralph/runtests.sh jv-ears` — 32 (was 26);
  `bash ops/ralph/runtests.sh jv-hud-bridge` — 25, unchanged (sys.health was
  already in DEFAULT_TOPICS; the bridge needed no change at all).
- build: `nix build .#jv-hud` and `nixos-rebuild build --flake .#ares` both ok.
  Never test/switch. No schema change, no jv-act, no boot path, no pins.
- files: services/jv-ears/jv_ears/{audio,main,pipeline}.py,
  services/jv-ears/tests/{test_capture_meter,test_exit_code,
  test_pipeline_fixtures}.py, shell/jv-hud/core/EarsBudgets.qml (new),
  shell/jv-hud/tests/tst_earsbudgets.qml (new), shell/jv-hud/core/{qmldir,
  MicState,SpeechState}.qml, shell/jv-hud/{StatePlate,MicPlate}.qml,
  shell/jv-hud/README.md, tools/gen_theme_qml.py,
  tools/tests/test_gen_theme_qml.py
- commit: 042438a
- next: Track A is now entirely blocked on a human or on hardware — **A8**
  (fonts) is an identity call (invariant 9), **A11** needs proposal R1's
  schema fields, **A13** needs an eye on ares. So the next iterations are
  Track B: **B6** is the largest honest bug left in the voice loop (jv-brain
  has no barge-in path — it keeps streaming an answer nobody is listening to,
  holds the GPU, and records the abandoned reply as if it had been heard), and
  **B5** (`jv act-log --since/--failed`) is the small pure one. A quieter
  follow-up this iteration suggests: jv-ears now has a place to state its
  tuning, and `wake_refractory_s` / `suppress_tail_ms` are the next two
  constants another service might otherwise learn to mirror — publish them
  when something actually needs them, not before. The standing one, unchanged:
  nobody has ever LOOKED at this HUD on ares. `JV_HUD_SELFTEST=1 jv-hud`, then
  a real wake word.

---

## 2026-09-24 — iteration 16 — B6: jv-brain barge-in

Track A is human-blocked (A8 identity, A11 schemas, A13 an eye on ares), so
this is the Track B item the last three journals kept naming: **jv-brain did
not subscribe to `audio.wake`.** The barge-in path existed everywhere except
the one service that generates. jv-voice stopped playing, jv-ears reopened its
gate, the HUD went to listening — and the brain kept streaming: the GPU held
for an answer nobody was listening to, `speech.say` frames jv-voice had to
refuse one group at a time (that is what A16's `DROPPED_GROUPS` is for), and
the abandoned reply added to the conversation as if it had been heard.

**the shape of the fix.** A spoken turn now runs as a CHILD task of the input
worker (`_stream_reply`), so a wake cancels that answer without touching the
worker that must go on to handle the utterance the wake belongs to — the
worker is why this is not simply `task.cancel()` on whatever is running.
`_respond` catches its own `CancelledError` and returns `(what it said,
INTERRUPTED)`; the guard is `asyncio.current_task() is not self._barged`, so a
cancellation this service did not ask for (shutdown cancels the worker) still
propagates untouched instead of being swallowed as an interruption. The wake
is handled on the frame loop, not in the worker — the worker is busy with the
very turn being cancelled.

**what could not be said on the bus.** `brain.response.finish_reason` is
frozen at `stop|length|error`. "stop" claims the answer ran to its end;
"error" blames the LLM for obeying the user; an extra boolean field would be
two fields that can disagree about one fact. So an interrupted turn publishes
NO `brain.response`, the barge-in is counted in `sys.health`'s free-form
`metrics` as `barge_ins` (where `hallucinated_tool_calls` already lives, so no
schema change), and **proposal R3** asks a human for the word. Writing
`interrupted` into a frozen enum would also have broken every Rust consumer —
the binding is `deny_unknown_fields`.

**the turn is recorded, not lost.** `interrupted_record()` keeps the text with
an explicit marker. Dropping the turn would leave two user messages in a row
(some chat templates refuse that) and let the model believe its half-answer
was the whole one. It records what was SENT, not what was HEARD: jv-voice
drops the tail of the group it never played, so this is the upper bound of
what reached the user, and the comment says so rather than pretending the
brain knows.

**the bug inside the fix.** A turn cancelled while awaiting an `action.result`
leaves an assistant `tool_calls` message whose result never comes — which a
chat template refuses, so ONE interruption would poison that conversation for
the rest of the session. `Conversation.repair_open_tool_calls` answers the
open calls with `{"ok": false, "error": "interrupted"}`. It does NOT pretend
the action was recalled: jv-act already has it, and only its audit log knows
how it ended.

**two deliberate refusals.** A SILENT turn is not cancellable: a wake says the
user is talking to Jarvis, not that the CLI or HUD stopped wanting the answer
it asked for, and nothing is being spoken over. And a wake is acted on unless
the frame REFUTES ITSELF (a numeric score below the numeric threshold the same
frame reports) — narrow on purpose, because the frame's existence is jv-ears
asserting a detection and `score`/`threshold` are there so tuning is
auditable. Losing an answer to a spurious wake would be worse than the bug
being fixed; refusing an unreadable-but-real wake would restore it.

**proving it bites — 13 mutations, 2 missed, both real.** Caught: wake not
subscribed, acting on a contradicting wake, never cancelling, propagating the
cancellation, swallowing ANY cancellation, the turn not recorded, the turn
published as if normal, silent turns made cancellable, the metric dropped,
tool calls left open, the record forgetting it was cut. Missed:
  · `_is_number`'s bool guard was pinned only in the direction that cannot
    bite. `score: true` is 1.0 and never refuses; `score: false` is 0.0 and
    would — a field we cannot read at all turning into a refusal. Test and
    comment now name the case that matters (plus `threshold: true`, which
    would refuse nearly every wake).
  · a `task.done()` check in `_barge_in` that no test could distinguish,
    because cancelling a finished task is already a no-op and it is the
    INTERRUPTED return that counts a barge-in. Deleted — dead defensiveness
    reads like protection (the A14 lesson, again).

- tests: `bash ops/ralph/runtests.sh jv-brain` — 50 green (was 37: 11 new
  barge-in/predicate tests, 3 new Conversation tests);
  `bash ops/ralph/runtests.sh jv-voice` — 17, unchanged (comment-only edits).
  The new suite streams the stub LLM one token per 0.25 s so a wake can
  genuinely land mid-reply, and asserts the stub SAW the client hang up —
  the generation is dropped, not just the speaking of it.
- build: `nixos-rebuild build --flake .#ares` ok. Never test/switch. No
  schema change, no jv-act, no boot path, no pins.
- files: services/jv-brain/jv_brain/service.py,
  services/jv-brain/tests/test_barge_in.py (new),
  services/jv-brain/tests/test_conversation.py,
  services/jv-voice/jv_voice/service.py (comments),
  services/jv-voice/tests/test_voice_service.py (docstring),
  docs/optimization-backlog.md (R3)
- commit: 4d05900
- next: this fix created one small downstream untruth, logged as **A17**: the
  HUD's `thinking` used to end on `brain.response`, and an interrupted turn no
  longer publishes one, so after a barge-in followed by SILENCE the plate can
  read `thinking` until A12's 30 s floor. The honest rule is that a wake NEWER
  than the thinking latch ends it — a few tests in `core/SpeechState.qml`, and
  a HUD-side item while Track A's other items wait on a human. Otherwise
  **B5** (`jv act-log --since/--failed`) is the small pure one. The standing
  item, unchanged: nobody has ever LOOKED at this HUD on ares.
  `JV_HUD_SELFTEST=1 jv-hud`, then a real wake word.

---

## 2026-09-24 — iteration 17 — A17: the question you gave up on stops reading "thinking"

**what.** `core/SpeechState.qml` now ends its thinking window when a wake
arrives NEWER than the open prompt. B6 (last iteration) made a wake cancel the
answer in flight, and an interrupted turn publishes no `brain.response` at all
— the frozen `finish_reason` enum has no word for "the user stopped me"
(proposal R3). That quietly removed the one frame that could close a thinking
window for a prompt nobody will ever answer, so the plate could claim a
working brain for the whole 30 s floor.

**the item was wider than the bug, and the tests are what found that out.**
A17 was written expecting the VOICE path to be broken. It was not: `prompt`
for a spoken turn is the audio.vad speech_end frame, and `utteranceEnded`
requires `vad.ts >= wake.ts` — so a newer wake disqualifies the very frame
that was the prompt, and the window closes by arithmetic nobody planned. The
test written for that scenario passed before a line of the fix existed; it is
kept, as the pin for a property that is currently accidental.

The real hole was `brain.request` — the CLI, the replay harness, and later the
HUD itself. Its frame stays readable and stays the prompt, so nothing ended
the window. Three of the seven new tests failed before the fix, all of them on
that path.

**only a spoken turn is abandoned.** jv-brain refuses to cancel a silent turn
(`_stream_reply`: a wake says the user is talking to Jarvis, not that the CLI
stopped wanting the answer it asked for). So a `brain.request` with
`speak: false` is still genuinely being worked on, and calling it abandoned
would be the same lie pointing the other way. One field decides it for both
topics: `body.speak !== false` — the schema's own default, and audio.vad has
no such field.

**latched, not derived**, for the reason `heardAnswer` is: `bus.latest()` holds
one frame per topic, so the wake that ended the window is gone the moment the
next detection lands, and a detection we refuse to believe leaves nothing to
compare against — derived, the abandoned question would come back to life.
Checked on the WAKE edge only, unlike `heardAnswer` which is also re-checked
when the prompt changes: a prompt arriving AFTER a wake is a NEW question, not
an abandoned one, because jv-brain saw that wake first and had nothing to
cancel. `onPromptKeyChanged` clears the latch for exactly that reason.

**proving it bites — 14 mutations, 14 caught.** Two survived the first round
and both were real:
  · a `topic !== "brain.request"` check in front of `speak !== false` that
    could not change an answer, since audio.vad's frozen body has no `speak`.
    Deleted — dead defensiveness reads like protection (the A14 and B6 lesson,
    a third time).
  · the null-wake guard, which no assertion could distinguish: a TypeError in
    a signal handler is a warning, not a test failure. There is now a test for
    the one path where the wake goes from a frame to NOTHING with a question
    still open and unabandoned, and it declares `failOnWarning(/TypeError/)`
    so the guard cannot be deleted quietly. First use of `failOnWarning` in
    this suite; worth reaching for wherever a guard only shows up as a log line.
  A third mutation (`>=` -> `>`) survived until a tie-break test was added: two
  frames stamped identically cannot be ordered, so the file's existing
  convention ("same instant" counts as "after", as in `answered`,
  `utteranceEnded`, `repliedOnBus`) is pinned rather than left to drift. Ending
  the window is also the under-claiming direction — "thinking" is the
  assertion, so dropping it says less.

- tests: `bash ops/ralph/qmltest.sh` — 237 green (was 228: 9 new);
  `bash ops/ralph/runtests.sh tools` — 30 green.
- build: `nix build .#jv-hud` ok (qmllint + the same tests in checkPhase);
  `nixos-rebuild build --flake .#ares` ok. Never test/switch. No schema
  change, no new topic, no jv-act, no boot path, no pins.
- files: shell/jv-hud/core/SpeechState.qml,
  shell/jv-hud/tests/tst_speechstate.qml
- commit: b0c8262
- next: Track A's remaining items are human-blocked (A8 wants a font decision
  that is identity, A11 wants two frozen-schema fields, A13 wants an eye on
  ares), so the next one is **B5** — `jv act-log --since/--failed`, small and
  pure, entirely inside `cli::act_log_render`. Discovered here and logged as
  **A18**: the voice path's immunity to this bug is accidental, a consequence
  of `utteranceEnded` rather than of anything that says so; if the prompt for
  a spoken turn ever stops being the vad frame it silently regains the bug.
  The standing item, unchanged and now seventeen iterations old: nobody has
  ever LOOKED at this HUD on ares. `JV_HUD_SELFTEST=1 jv-hud`, then a real
  wake word.

## 2026-09-24 — iteration 18 — B5: `jv act-log` can be asked a question

Track A is human-blocked in all four of its open items (A8 wants a font
decision that is identity and so a human's under invariant 9; A11 wants two
additive fields in frozen schemas; A13 wants an eye on ares; A18 is a warning
note, not work), so this is the B5 the last journal entry named.

`jv act-log` could print the whole file or `--tail N` of it. That is a
listing, not a reader. After something happens on this machine the human has
exactly two questions — **"what did jv-act do in the last ten minutes"** and
**"show me everything that was not ok"** — and neither could be asked of the
record of the one service allowed to change the machine. Both land entirely
in the already-parsed entries: `--since`, `--failed`, `--outcome WORD`
(repeatable), and `--failed`/`--outcome` made mutually exclusive, since
`--failed` IS `--outcome` negated and accepting both would have to invent a
meaning for their intersection.

**one rule, and it is the same rule the file already lived by.** `act_log_render`
has always refused to drop a line it cannot parse, because a reader that
silently skips a hole reports a torn audit trail as a clean one. A filter is
the second chance to tell that lie, and a better-hidden one: a `--failed`
view that quietly omits the entries something went wrong with is worse than
no filter at all. So: **a filter narrows what is shown, and never hides what
it could not evaluate.** Stated once, reached three ways —

  · an unreadable LINE has no ts and no outcome, so no filter can exclude it;
  · a readable entry with a missing or nonsense `ts` cannot be proven older
    than the cutoff;
  · one whose `outcome` is not a string has not been shown to have succeeded.

Each of those prints `?` in the column the filter was about, so the admission
is on screen rather than only in a doc comment. An unreadable line is SHOWN
but is not counted as an ANSWER (`matched`), which is the distinction that
keeps the exit code honest.

**filters run before `--tail`**, so `--failed --tail 1` is "the newest
failure" and not "the last line of the file, if it happens to be a failure".
The second reading makes `--tail` silently answer a different question than
the one asked. `matched` is likewise counted before the window narrows it:
"did anything match" is about the filter, not about how many of the matches
were asked for.

**grep's exit rule.** A question nothing answers exits 1 and prints NOTHING
for it. Two reasons it has to be silent: on a healthy machine `--failed`
matching nothing is the GOOD answer, and a warning printed every time would
train a human to ignore this command. And that exit is the only thing
standing between a typo'd `--outcome denyed` and a reassuring empty listing —
which is precisely why `--outcome` words are NOT validated against jv-act's
outcome enum. Validating would be a second hand-copy of a human-review-only
file (`act_audit_path` is already one, proposal R2), and an old `jv` would
then refuse to show a record whose outcome word a newer jv-act had learnt to
write; refusing to display a record because you do not recognise it is the
wrong failure for an audit reader. `--tail` is a WINDOW and not a question
(`ActLogFilter::is_query`), so `--tail 0` and a plain empty log still exit 0
exactly as before.

**wall clock, not `ts_mono`.** Entries carry both, and `ts_mono` is the better
clock in every way except the one that matters here: "the last ten minutes"
is a question about the clock on the wall, `ts_mono` restarts at every boot,
and no human can type one. So `iso_to_epoch` had to exist — the exact inverse
of jv-act's `now_iso` civil-from-days, hand-written rather than by adding
chrono (a new dependency is a vendored-registry change for one date
function). Deliberately strict: an offset like `+03:00` is REFUSED rather
than ignored, because ignoring one shifts an entry by hours and then answers
the wrong question with complete confidence — and jv-act writes UTC and only
UTC, so a stamp with an offset did not come from jv-act. An unreadable
`--since` is an error raised BEFORE the file is opened; a filter that
silently widens prints the whole log and reads as a great deal of recent
activity, and printing the log first would bury the message.

Deleted while here: the `0 <=` halves of the hour/minute/second range checks.
`small_int` and `plain_number` both refuse a sign, so no input could reach
them. Dead defensiveness reads like protection — the A14/B6/A17 lesson, a
fourth time. (A mutation pass is how it was found: the branch could not be
made to fail.)

**27 mutations, 27 caught**, across the filter predicate, the tail/filter
ordering, both exit-code clauses, the duration and ISO parsers, and the clap
wiring (`--failed` reaching the filter, the `conflicts_with`, `--since` being
judged before the file is read). No survivors this round — the first time in
several iterations, and worth noting that the three edge tests that made it
so (the inclusive `--since` boundary, three-digit seconds, one past the leap
second) were all written because a mutation was aimed at them first.

- tests: `bash ops/ralph/cargotest.sh jarvisd` — 57 green (was 36: 14 new
  unit tests, 7 new integration tests running the real `jv` binary).
- build: `nix build .#jarvisd` ok; `nixos-rebuild build --flake .#ares` ok.
  Never test/switch. No schema change, no new topic, no jv-act change, no
  boot path, no pins.
- files: services/jarvisd/src/cli.rs, services/jarvisd/src/bin/jv.rs,
  services/jarvisd/tests/cli.rs
- commit: da134b9
- next: Track A stays human-blocked, so Track B again. The candidate found
  here and logged as **B8**: `jv act-log` is now the only reader of the audit
  trail that can answer a question, and jv-guard/jv-compat have no equivalent
  — but before adding more flags, the honest next item is **B3** (replay
  harness fixtures), which is the oldest unstarted item in the plan and the
  one thing Phase 3 says is used forever. **A18** remains a note rather than
  work. The standing item, unchanged and now EIGHTEEN iterations old: nobody
  has ever LOOKED at this HUD on ares. `JV_HUD_SELFTEST=1 jv-hud`, then a
  real wake word.

---

## 2026-09-24 — iteration 19 — **B3: the harness finally has something recorded in it**

Track A is still human-blocked (nobody has looked at the HUD on ares), so
Track B, and the honest pick was the one the last entry named: **B3**, the
oldest unstarted item in the plan. The blueprint says the replay harness is
built in Phase 3 and used forever — *recorded sensor sessions are the test
fixtures for all perception work*. It has existed since Phase 3 with
**nothing recorded in it**. `record.py` could write a session, `replay.py`
could play one back, and the only session either had ever seen was the
three synthetic frames the roundtrip test makes and deletes.

The cost of that is not abstract. `services/jv-ears/tests/test_pipeline_fixtures.py`
is the only place jv-ears' end-to-end behaviour is asserted, and it needs
~1 GB of ONNX and `pytest.skip`s loudly without it. So on any machine
without the weights, the whole of perception has zero coverage, and
everything DOWNSTREAM of ears — the HUD's state machine, jv-brain's turn
taking — has no example of what perception actually looks like to be
tested against. Every such test to date has hand-written the frames it
wished it had.

**`harness/fixtures/sessions/` now holds four recordings**: what the real
pipeline — real openWakeWord, real Silero VAD, real faster-whisper —
published while listening to each committed fixture WAV. 7, 7, 11 and 2
frames; 8 KB in total. The requirements `REVIEW-ears.md` states are now
asserted twice: there against the live models when they are installed, and
in `harness/tests/test_sessions.py` against the recording, always.

**The sample clock is the whole trick.** `EarsPipeline` already decided
everything on samples-consumed rather than the wall clock ("the same
fixture always produces the same events, which is what makes CI
meaningful") — but that clock was a private `_t()` with zero callers.
Publishing it as `EarsPipeline.clock()` is what makes a session reproduce
to the sample: regenerating twice produced byte-identical frames modulo
the UUIDs. A diff on these files therefore means the pipeline changed, not
that the machine was busy.

It is also why the header's `boot_id` is the **`sample-clock` sentinel**
rather than a real one. `boot_id` exists to prove a session's monotonic
`ts` came from this boot and can be lined up against another session's.
These `ts` cannot. Borrowing a real boot_id would be a claim, in the exact
field that exists to check the claim, that they can — the same class of
lie as a faked sensor indicator, at a much smaller scale.

**`harness/session.py` is now the only thing that knows the format** —
`load`, `dump`, both header makers, and `problems()`. A committed fixture
is worth having only while it is still LEGAL: the moment a schema moves
under it, every test built on it keeps passing while asserting yesterday's
law. So `problems()` checks envelope keys, closed bodies, required fields,
`v` against the schema's current version, and per-`(src, topic)` `ts` and
`seq` ordering — all read off the **generated** bindings
(`jarvis_bus.schema`, which CI already gates against drift), never a
hand-copy of `schemas/*.json` here. A hand-copy is the thing that rots;
with one, a v2 envelope would leave two truths in the repo and no way to
tell which one a fixture was recorded against. The one regex I would have
had to copy (the topic pattern) is simply not checked — what is checked is
what the README states in prose and the bindings cannot: no wildcard in a
published topic.

Two things are deliberately NOT problems, and it is the B5 rule again:
**never refuse to show what you merely do not recognise.** An unknown
topic is accepted as-is (adding a topic is an ordinary reviewed commit; an
old harness rejecting a recording of a newer one is the `--outcome denyed`
mistake), and a `seq` gap is accepted (a gap is the slow-consumer policy
working — that is what `seq` is FOR). Ordering is per `(src, topic)` and
not global, because two publishers are two clocks read at two moments and
can legitimately land out of order; one publisher's own frames on one
topic cannot.

**Nothing lets the recordings rot quietly.** A fixture nothing re-derives
has already rotted and not told anyone, so when the models ARE installed
jv-ears re-records every WAV through the same `frames_for()` the generator
uses and compares. What it compares is chosen: which frames arrived, at
what `ts`, in what state (`event`/`kind`), plus the finals normalized for
case and punctuation. NOT model scores and NOT partial texts — those are
the last digits of a float on the machine that ran it, and a fixture that
fails because CI has a different CPU teaches people to regenerate without
reading the diff. Segmentation, gating and timing are what these files are
for, and all three are in the comparison.

Also here, because the format now has one home: `record.py` no longer
writes its own header (`session.live_header()`), `replay.py` no longer has
its own loader, and the `jarvisd`-spawning fixture moved to a
`conftest.py` both bus tests share.

- tests: `bash ops/ralph/runtests.sh harness` — 78 green (was 3: 30 on the
  format, 45 on the committed sessions, including one that replays a real
  recording onto a real jarvisd and gets every frame back). `bash
  ops/ralph/runtests.sh jv-ears` — 36 green (was 32).
- build: `nixos-rebuild build --flake .#ares` ok. Never test/switch. No
  schema change, no new topic, no jv-act change, no boot path, no pins.
- files: harness/session.py (new), harness/tests/conftest.py (new),
  harness/tests/test_session_format.py (new), harness/tests/test_sessions.py
  (new), harness/fixtures/sessions/{README.md,generate_sessions.py,4×.jsonl}
  (new), harness/record.py, harness/replay.py,
  harness/tests/test_record_replay.py, services/jv-ears/jv_ears/pipeline.py,
  services/jv-ears/tests/test_pipeline_fixtures.py
- commit: d2f9634
- next: the fixtures exist so something downstream can be tested on them —
  and the obvious first consumer is the HUD, whose QML tests hand-type the
  JSON lines the bridge writes. **B9** (new): feed a committed session
  through `core/BusModel` + `SpeechState` in `tst_speechstate.qml` and
  assert the state trajectory against a real recording. That needs the
  session files reachable from the jv-hud build (`src` is `shell/jv-hud`
  only today — the theme toml is already wired in as an extra input, so
  there is a pattern). **B8** (one shared audit reader) still waits for a
  second real caller. **A18** remains a note. The standing item, unchanged
  and now NINETEEN iterations old: nobody has ever LOOKED at this HUD on
  ares. `JV_HUD_SELFTEST=1 jv-hud`, then a real wake word.

## 2026-09-24 — iteration 20 — **B9: the HUD's tests stop typing their own frames**

The last entry ended with the obvious next move and this is it. B3 gave the
repo four recordings of what jv-ears REALLY publishes; the HUD's QML tests,
meanwhile, hand-typed every bridge line they asserted on. That is the flaw
worth naming: **the input and the expectation had the same author.** Every
one of those 238 tests is a claim about what the HUD does with a frame *I*
wrote, and a misunderstanding about what perception actually emits would
have been written into both halves, where it would agree with itself
forever. No amount of care inside the test file can find that; only a
recording from outside it can.

So `shell/jv-hud/tests/tst_sessionreplay.qml` replays each committed
session through `core/BusModel` + `core/SpeechState` and asserts the state
trajectory in the recording's own seconds:

```
hey-jarvis-clean   unknown -> listening@1.44 -> thinking@3.76
hey-jarvis-music   unknown -> listening@1.44 -> thinking@4.16
hey-jarvis-pause   unknown -> listening@1.36 -> thinking@6.64
speech-no-wake     unknown
```

Those numbers are facts about a room, not numbers chosen to make a test
pass, and the shape of the assertion matters as much as the values: the
trajectory is *every change*, so a flicker cannot hide in it — it is two
extra transitions. That is what makes `hey-jarvis-pause` worth having. It
holds 1.2 s of real silence inside one sentence (the fixture exists because
that pause must not split the utterance), and nothing hand-written would
have caught a HUD that blinked there, because nobody types a 1.2 s hole into
a test they are writing to pass. `speech-no-wake` is the other direction: a
real room, real speech, nobody addressing Jarvis. The HUD must stay dark
through all of it, and now a recording says so rather than an argument —
claiming that microphone is open *for us* is precisely the invariant-10 lie.

Two assertions are about the COUPLING rather than about the HUD, and both
are only possible with real data:

- The recorded wake frames have to clear SpeechState's "a frame that
  disagrees with itself is not a detection" bar using openWakeWord's own
  `score` and `conf`. A stricter bar (conf ≥ 0.995) fails on the music bed's
  0.963 **and** on the quiet room's 0.990 — so the bar is now checked
  against numbers a detector produced, not numbers a test author picked.
- The longest recorded utterance has to fit inside `wakeWindowS`, which is
  ears' own `wake_timeout_s` (A14). 5.28 s of real speech against an 8 s
  window today. If anyone ever tunes that below what a person actually says,
  the HUD would drop "listening" mid-sentence while ears was still
  recording — and the recordings are the only evidence in the repo about how
  long "what a person actually says" is. The failure message states the
  margin.

**Getting the files to QML is the real design question here.** A QML engine
cannot read a file out of the repository, and the alternatives were worse
than they look: an XHR on a relative path resolves differently in the
worktree and in the build; a committed symlink into `harness/` is dangling
inside `src` and has to be repaired by the build; an env var is unreadable
from QML. So `tools/gen_sessions_qml.py` compiles the recordings into
`tests/Sessions.qml`, which is the pattern A2 already established for the
theme — one source of truth, a generated committed artefact, and a `--check`
in the jv-hud build. Moving a wake 0.2 s in a `.jsonl` now fails
`nix build .#jv-hud` (VERIFIED), so a re-recorded session and a stale
fixture cannot pass a build together.

The generator knows **nothing** about schemas, deliberately. Its entire
knowledge of the format is "line 1 is the header, the rest are frames";
`harness/session.py` is the format's only reader and already holds these
files to the generated bindings, so a second validator here would be a
second truth to keep and the wrong one would be believed by whoever read it
last. It copies bytes and refuses anything it cannot copy honestly (a
non-object line, a non-ASCII line, a recording with no frames, an empty
directory — that last one because a generator that happily emits nothing
leaves every test built on it passing while asserting nothing). Being
stdlib-only is what lets that check run under the plain `python3` of the
jv-hud build AND under CI's bare checkout, where `jarvis_bus` does not
exist.

Two differences from a live HUD, both stated rather than left to be noticed.
The bridge forwards a whitelist, so the real HUD never sees the
`audio.transcript` frames in these recordings; we replay the whole thing, so
a test asserts the transcripts change nothing — which is the claim that
makes a superset safe (and the privacy line holding: the words are on the
bus and no element reads them). And `ts` is the sample clock, so the
injected monotonic clock is driven to each frame's own `ts`: every frame
lands zero seconds old, as on a machine keeping up, and winding past the end
is what closes the thinking window on a brain that never answered.

One mutation survived and it was real: the "frames are verbatim" test passed
against a line `json.dumps` happened to have formatted, so a generator that
parsed and re-dumped every line looked correct. The fixture is now a line
`json.dumps` would never write.

- tests: `bash ops/ralph/qmltest.sh` — 250 green (was 238), 12 new; 7
  mutations run through them, 7 caught. `bash ops/ralph/runtests.sh tools` —
  52 green (was 30), 22 new; 4 mutations, 3 caught and the survivor fixed.
  `bash ops/ralph/runtests.sh harness` — 78 green, unchanged.
- build: `nix build .#jv-hud` ok (the new `--check` runs before qmllint) and
  `nixos-rebuild build --flake .#ares` ok. Never test/switch. No schema
  change, no new topic, no jv-act change, no boot path, no pins.
- files: tools/gen_sessions_qml.py (new), tools/tests/test_gen_sessions_qml.py
  (new), shell/jv-hud/tests/Sessions.qml (new, GENERATED),
  shell/jv-hud/tests/tst_sessionreplay.qml (new), pkgs/jv-hud/default.nix,
  shell/jv-hud/README.md, harness/fixtures/sessions/README.md,
  .github/workflows/check.yml
- commit: 36a486d
- next: the recordings are jv-ears alone, so every trajectory here ends in
  "thinking" and times out — nothing in the repo records a WHOLE turn.
  **B10** (new): record a session off the live bus on ares during one real
  spoken turn (`harness/record.py` has always been able to; `live_header()`
  is for exactly this), commit it, and the HUD replay gets the other half —
  speaking, the gaps between streamed sentences, back to idle. That needs a
  human at the machine for one utterance, which makes it the SAME ask as the
  standing item, so ask for both at once. Also worth noting: `MicState` and
  `HealthState` cannot be replayed at all yet, because no committed session
  contains a `sys.health` frame — a live recording would fix that too.
  **A18** remains a note; **B8** still waits for a second real caller. The
  standing item, now TWENTY iterations old: nobody has ever LOOKED at this
  HUD on ares. `JV_HUD_SELFTEST=1 jv-hud`, then a real wake word.

## 2026-09-24 — iteration 21 — A8: the machine finally has the faces the theme names

`personality/theme.toml` has named Archivo and JetBrains Mono since A2 and
nothing installed either of them. Every pixel of type the HUD has drawn since
A3 — every plate, every label — was rendering in whatever fontconfig picked
that day. That is the worst shape a missing dependency can take: it does not
fail, it does not warn, it just looks like something else. For a versioned
identity (invariant 9) it is the only failure mode that matters.

`modules/fonts.nix` does not repeat the family names. It reads them out of
theme.toml with `builtins.fromTOML`, which is the same thing
`tools/gen_theme_qml.py` does for the HUD — one source of truth, two
compilers, so renaming a face moves the system with it. What the module owns
is the binding from a family NAME to something that provides it, and every
step **throws rather than guesses**, because every guess here is invisible:
a face theme.toml names with nothing bound to it is an eval-time throw, a
provider theme.toml does not name fails an assertion (a face installed for no
declared reason is one more family fontconfig can substitute), and a
`family_<role>` with no fontconfig generic behind it throws too — theme.toml
calls the generic families "the fallbacks", and a role with no generic has no
fallback at all.

The system installs the face it **checked**. A font package is only worth
having if it really reports the family asked for; that name lives inside the
font binary and nothing about a package's name or its file names guarantees
it. So each declared face goes through a derivation that asks `fc-scan` —
the same thing that will resolve the name at runtime — and fails the build if
the family is not in there. "Provides the family" and not "every file is that
family", deliberately: jetbrains-mono ships `JetBrains Mono NL` next to
`JetBrains Mono`, and refusing that is refusing the packaging, not catching a
drift.

**That check found a real one on its first run.** The first version of the
module was a plain `symlinkJoin`, and `fc-match monospace` against the built
system answered `JetBrainsMono-Regular.woff2` — nixpkgs ships every face
three times (opentype, truetype, WOFF2) and fontconfig indexes the web font
like any other. Whether a WOFF2 renders at all depends on how the FreeType
doing the rendering was built, so shipping one is the same silent
substitution this module exists to stop, one layer further in. The join now
links outline formats only, and `fc-list | grep -c woff2` over the built
closure is 0.

`pkgs/archivo` is the pin A8's research recommended. nixpkgs has no
`archivo`; the only packaged source is `google-fonts`, whose src is 1.1 GiB
to fetch and 2.7 GiB unpacked even overridden to one family, on a machine
that builds its own system and never garbage-collects during development.
Upstream is 66 MiB of source for 3.4 MiB of installed face — one rev, one
hash, no tags or releases exist so the pin is a commit. Base width only:
theme.toml names no Condensed/Expanded/SemiExpanded/AAA cut, and a family
installed but never asked for is one more thing fontconfig can reach for when
the real one is missing. Its install check asserts all 18 faces report family
`Archivo` (widening the glob to `Archivo*.ttf` lets ArchivoCondensed in and
fails the build — VERIFIED) and that the upright Regular is among them, since
a package carrying only Thin and Black would pass the first check and render
nothing anyone asked for.

Two Python gates, because two things the nix side cannot see: no QML file may
name a font family of its own (the same rule as colour — a literal
`font.family: "monospace"` would put the drift back one binding at a time with
nothing failing), and theme.toml's faces must equal `providerOf`'s keys. That
second one IS checked at eval by the module; it is repeated in `tools/tests`
because that is the one place it can run without nix — the `tools` CI job on
a bare checkout, in half a second, with a diff instead of a stack trace.

One thing this does NOT do: `Theme.familySans` still has no reader. Every HUD
element is mono, exactly as A8 said. Archivo is packaged because theme.toml
declares it and a declared face must exist, not because anything draws in it
yet.

- tests: `bash ops/ralph/runtests.sh tools` — 54 green (was 52), 2 new. 11
  mutations across the whole change, 11 caught: wrong package bound to a
  family, provider deleted, provider nothing asks for, a `family_serif` with
  no generic, `providerOf` renamed out of the gate's sight, the archivo glob
  widened, archivo installing no Regular, a face dir with no outline files, a
  hardcoded `font.family` string, the grouped `font { family: }` form, and a
  provider key typo.
- build: `nixos-rebuild build --flake .#ares` ok, `nix flake check --no-build`
  ok, `nix eval ...toplevel.drvPath` ok (CI parity), `nix build .#archivo` ok,
  `nix build .#jv-hud` ok. Never test/switch. No schema change, no jv-act
  change, no boot path, no NVIDIA/kernel/flake pin touched.
- verified end to end, as far as a sandbox can: `fc-match` for `Archivo`,
  `JetBrains Mono`, `sans-serif` and `monospace` against the BUILT system
  closure's own `conf.d` all resolve to the declared outline faces. Not
  verified: what it looks like. That needs a human on ares.
- files: modules/fonts.nix (new), pkgs/archivo/default.nix (new), flake.nix,
  hosts/ares/default.nix, tools/tests/test_gen_theme_qml.py,
  shell/jv-hud/README.md
- commit: 5e5ef8d
- next: **A19** (new): nothing pins the outline-only rule. If a later hand
  widens the `-iname` filter in `checkedFace`, the WOFF2 comes back and every
  check still passes — the face check only asks whether the family is present.
  The honest gate is the one this iteration ran by hand: build a fontconfig
  config from `fonts.packages` and assert `fc-match "<family>"` returns a file
  this module linked. Small, and it would make the verification above
  automatic instead of a paragraph in a journal. **A13** and **A18** are
  unchanged notes; **B8** still waits for a second real caller; **B10** needs
  a human at the machine. The standing item is now TWENTY-ONE iterations old
  and has just grown a second half: nobody has ever LOOKED at this HUD on
  ares, and now nobody has looked at its type either. `JV_HUD_SELFTEST=1
  jv-hud`, then a real wake word — and tell me whether the labels are
  JetBrains Mono.

## 2026-09-24 — iteration 22 — A19: the hand-check becomes a build gate

Iteration 21 ended by verifying, by hand, the thing the whole font module
exists to promise: build the system, point fontconfig at the closure's own
`conf.d`, and ask `fc-match` for each declared family. It resolved to the
declared outline faces. Then that became a paragraph in a journal, which is
exactly as durable as nothing — and the specific hole was already written
down: widen the `-iname` filter in `checkedFace` and the WOFF2 comes back
with every existing check still green, because the face check only asks
whether the family is PRESENT in the package, never which file fontconfig
hands back when something asks for the name.

`jv-fonts-resolve` asks that question every build. It is in `system.checks`,
so `nixos-rebuild build` builds it and nothing of it lands in the system
closure — a check, not a dependency.

**It resolves against the configuration this machine will really have.** The
conf packages come from `config.fonts.fontconfig.confPackages`, the same list
the fontconfig module links into `/etc/fonts`, and the config file is the real
`fonts.conf` with one edit: its `<include>` of conf.d is an absolute `/etc`
path and there is no `/etc` inside a build. A check that assembles its own
fontconfig setup proves something about that setup and nothing about ares.

Two rules, and both are stated as PROPERTIES rather than as a copy of the
mechanism that implements them. A gate that restates its implementation passes
the moment the implementation changes, which is the whole failure A19 was
written about:

1. **Every file in an installed face is an sfnt**, decided by the file's own
   first four bytes. Not by the extension — that is what the find filter goes
   by, so it cannot also be the witness. And not by `fc-scan`'s
   `%{fontformat}`, which was the obvious thing to reach for and is wrong:
   asked about `JetBrainsMono-Regular.woff2` it answers `TrueType`, because
   the FreeType it was built against decompresses woff2. That is *precisely*
   the property at issue — whether a face renders depends on the library that
   opens it, so "some FreeType could read this" is not the question. `wOF2`
   in the first four bytes is.

2. **Asking for each family by name, and for the generic behind it, answers
   that family in a file this module linked.** One sentence, the module's
   whole promise, and the only check here that covers `defaultFonts` —
   nothing else notices if `monospace` quietly lands on DejaVu Sans Mono.

A generic is only a question if fontconfig has heard of it. This is the one
thing the first version of the check got wrong, and the mutation found it:
with the alias misspelled `sansSerif`, `fc-match sansSerif` still answered
Archivo and the check passed. fontconfig's `49-sansserif.conf` answers ANY
unrecognised family with the sans-serif default, so a typo'd generic looks
exactly like a correct one. The vocabulary gate greps fontconfig's OWN shipped
`conf.avail` for `<family>…</family>` — never the `conf.d` this module helped
generate, or the answer would come from the same place as the question.

`genericOf` now carries two names per role: the NixOS option that sets the
alias (`sansSerif`) and the word fontconfig itself answers to (`sans-serif`).
They are not always spelled the same and the check has to ask in fontconfig's
spelling. Plus an assertion that `fonts.fontconfig.enable` is true — the check
reads `confPackages`, which is only populated while it is, and with fontconfig
off this module installs faces into a system that can resolve no name at all.

Two tools gates, because **CI instantiates the ares system but never builds
it** — `nix eval …toplevel.drvPath` proves the check exists as a derivation
and never runs it. So: the check must still be wired into `system.checks`
(unwiring it is the one mutation nothing else in the repo notices — the faces
still install, the module still evaluates, every other gate stays green, and
the proof simply never happens again), and `genericOf`'s roles must equal
theme.toml's `family_*` roles in both directions.

One thing worth recording from the mutations: with the find filter widened to
admit WOFF2, `fc-match` still answered the `.otf`. The resolve half alone
would NOT have caught the regression A19 was written about — the content rule
did. The two halves are not redundant.

- tests: `bash ops/ralph/runtests.sh tools` — 56 green (was 54), 2 new. 12
  mutations, 12 caught: the find filter widened to admit WOFF2; `defaultFonts`
  dropped (monospace → DejaVu Sans Mono); a generic spelled the NixOS way; the
  upstream packages installed directly instead of the checked faces (fc-match
  answers out of `archivo-0-unstable-…` and the check names the file); the
  check resolving against an empty fontconfig config; the check unwired from
  `system.checks` (toplevel references: 1 → 0); a role with no generic; a
  generic for a role nobody names; the check renamed out of the tools gate's
  sight.
- build: `nixos-rebuild build --flake .#ares` ok, `nix flake check --no-build`
  ok, `nix build` of the check itself ok — it prints what each name resolved
  to, so a passing build says so in four lines. Never test/switch. No schema
  change, no jv-act change, no boot path, no NVIDIA/kernel/flake pin touched.
- files: modules/fonts.nix, tools/tests/test_gen_theme_qml.py
- commit: be1b264
- next: Track A is now down to items that need a human. **A13** and **A18**
  are unchanged notes; **A11** is schema-blocked (proposal R1); **B8** waits
  for a second real caller; **B7** waits for a consumer. The standing ask is
  TWENTY-TWO iterations old and has three parts now, all answerable in one
  sitting at ares: (1) look at the HUD — `JV_HUD_SELFTEST=1 jv-hud`, then a
  real wake word — and say whether it is right; (2) say whether the labels are
  JetBrains Mono, which the machine can now prove it installed but not that
  anyone can read it; (3) **B10** — record one real spoken turn off the live
  bus (`harness/record.py`), because every replayed trajectory in the HUD's
  tests still ends in "thinking" and times out, and nothing in the repo has
  ever contained a `speaking` frame or a `sys.health` one. Without (3) the
  next UI iteration is testing against half a conversation.

## 2026-09-24 — iteration 23 — A20: the question you could only hear

jv-act stops in front of every destructive tool and asks (invariant 3). It
publishes `action.confirm{kind=request}` with the question, opens a window it
declares in the frame — 15 s — and jv-voice speaks it. Inside that window
silence is a no. Everything about that handshake was audible and nothing
about it was visible, which makes it fragile in the most ordinary way there
is: music playing, headphones off, one sentence half heard, and a question
you did not know was asked gets answered by a timeout you did not know was
running. The one moment invariant 3 hands the user a veto was the one moment
the HUD had nothing to say.

`ConfirmPlate` is the readable copy. jv-act's words verbatim, the tool id
underneath, on screen for exactly as long as the question can still be
answered.

**It cannot answer, and that is structural rather than a decision made in
this file.** The HUD surface has an empty input region and takes no keyboard
(invariant 10, and tools/tests pins both on every Quickshell window in the
directory), so there is no path from these pixels to an authorization at all.
A clickable YES would make the HUD a second actuator, which invariant 3 has
no word for. Answering stays where it was: your voice, or `jv confirm`.

**The request has to be latched, and the bus is what forces it.** `latest()`
keeps exactly one frame per topic, and the ANSWER lands on the same topic as
the request — so the instant anything answers, the question is gone from the
bus. Derived, "is something pending" would see the question only in the
moment it arrived and be blind to it for the rest of its life. This is the
third latch in the HUD for the same reason (`heardAnswer`, `abandoned`), and
the rule they share is worth stating once: latch an observation the bus no
longer carries, never one it still does.

A latch has to be let go of, and each of the three ways is a rule about
somebody else's authority:

1. **An answer naming THIS `request_id`** — not any answer. jv-act reserves a
   single outstanding confirm slot today, so in practice there is only ever
   one; but the HUD is not the thing that enforces that, and closing on
   somebody else's answer would blank a live question. The answer also does
   not always come from the service that asked: `jv confirm` publishes it
   itself, which is exactly why this reads the topic and not a publisher on
   it.
2. **The link dropping.** A question latched from a bus we can no longer see
   describes a machine we can no longer see — and the window has very likely
   closed while we were not looking. A link that comes back does not bring it
   back with it, which is its own test.
3. **The window running out**, as the backstop for a jv-act that died
   mid-question and will never publish the answer that normally ends this.
   The window is the one jv-act DECLARED in the request (A14's rule: the
   service that enforces a budget states it and the HUD reads it rather than
   keeping a copy that drifts). `windowFallbackS` is only for a request that
   declares none, and mirrors no service's constant on purpose.

And the rule that is not about letting go: **refusing to read a frame is
never the same as being answered.** A malformed `action.confirm` — a body
from a schema version we were not written against, a hedged `conf`, no
`request_id` — leaves a pending question exactly where it was. Every other
element in the HUD can treat "unreadable" as "nothing known" because nothing
known is drawn as nothing; here, nothing known would blank the one plate the
user has to act on.

The mutation pass found a real one. The words — `summary`, `tool`,
`requestId` — were gated on the latch still being HELD, not on the question
still being OPEN, and the latch deliberately outlives the window (it has to,
or a second request could not tell whether it replaced one). So an expired
question stayed readable and answerable-looking through the element's own
API. The plate's visibility hid it completely, which is what made it worth a
test of its own: this element will get a second reader.

**A new build gate, and it is not about this element.** The HUD only ever
sees what jv-hud-bridge subscribed to. An element that reads a topic missing
from `DEFAULT_TOPICS` is not broken in any way anything notices: it builds,
it lints, its own tests pass — they hand it frames directly — and on the
machine it draws nothing, forever, on a surface that is unmapped by design.
That is the A15 failure mode arriving through the other end of the pipe, so
tools/tests now reads every `latest(...)`/`latestFrom(...)`/`publishersOf(...)`
in `core/` and fails if the bridge does not subscribe to it. One direction
only: the bridge may subscribe ahead of the element that will read a topic,
it may not fall behind one that already does. VERIFIED it bites — dropping
`action.confirm` from the list fails the gate.

`action.confirm` is also the first topic whose BODY the HUD renders. The
bridge already carried `brain.request`/`brain.response`, whose bodies hold
conversation text, under a comment saying no element reads those words and
that an element which wants them should be a deliberate choice rather than a
thing that happened. This is that choice, and it is the narrow one: a
confirmation you cannot read is one you answer by guessing. Nothing leaves
the machine; this is one local process writing to another (invariant 7).

What the question does NOT say is which file. `summary` is jv-act's static
per-tool description plus " — yes or no?", so it reads "empty the trash —
yes or no?" whether the trash holds one file or four hundred. That is a
jv-act change and jv-act is human-review-only, so it is written up as
proposal **R4** rather than worked around: the plate shows the summary
verbatim and the tool id, and the day the summary gets better the plate gets
better with no HUD change at all.

- tests: `bash ops/ralph/qmltest.sh` — 284 green (was 250), 34 new. 15
  mutations, 15 caught (one only after the test the survivor earned): the
  window forgotten; any answer closing any question; an unreadable frame
  closing one; the link dropping without forgetting; jv-act's declared
  window ignored; a late frame given a whole window; any schema version
  readable; a hedged confirmation believed; a question with no id held; any
  `kind` treated as a request; the words outliving the question; a negative
  window believed; the first question winning over the newest; an unarmable
  window never expiring. `bash ops/ralph/runtests.sh tools` — 57 (was 56);
  `... jv-hud-bridge` — 25 green.
- build: `nix build .#jv-hud` ok (qmllint -W 0 clean, 284 QML tests in the
  checkPhase), `nixos-rebuild build --flake .#ares` ok, `nix flake check
  --no-build` ok. Never test/switch. No schema change, no jv-act change, no
  boot path, no NVIDIA/kernel/flake pin touched.
- files: shell/jv-hud/core/ConfirmState.qml (new),
  shell/jv-hud/ConfirmPlate.qml (new),
  shell/jv-hud/tests/tst_confirmstate.qml (new), shell/jv-hud/shell.qml,
  shell/jv-hud/qmldir + core/qmldir (generated), tools/gen_theme_qml.py,
  tools/tests/test_gen_theme_qml.py,
  services/jv-hud-bridge/jv_hud_bridge/bridge.py,
  docs/optimization-backlog.md (R4), ops/ralph/PLAN.md
- commit: 6779708
- next: **A21** (how much of the window is left — the only thing in this HUD
  that would animate continuously, so it wants a human eye before it is
  built) and **A22** (granted, denied and timed out all exit the same way,
  and "it went away" reads the same as "it expired while I was reading it").
  Both are judgement calls about a plate nobody has seen yet, which is the
  standing ask, now TWENTY-THREE iterations old and unchanged in shape: one
  sitting at ares to (1) look at the HUD — `JV_HUD_SELFTEST=1 jv-hud`, a
  real wake word, and now `jv act-log`-worthy: ask Jarvis to do something
  destructive and watch the corner; (2) say whether the labels are JetBrains
  Mono; (3) **B10** — record one real spoken turn off the live bus
  (`harness/record.py`). Every replayed trajectory still ends in "thinking"
  and times out, and nothing in the repo has ever contained a `speaking`
  frame, a `sys.health` one, or — as of today — an `action.confirm` one, so
  three of the HUD's four plates cannot be replayed at all.

## 2026-09-24 — iteration 24 — A23: the HUD stops letting its own blindness look like calm

Track A's remaining items (A11, A13, A21, A22) are all waiting on a human —
two on a schema proposal, two on an eye that has never seen this HUD — so
the ladder said "a feature from PLAN.md". What I found instead was a hole
in the UI itself, which is where the ladder wanted me anyway.

Every element in this HUD is built to REFUSE. MicState will not call a
microphone it cannot see "off" (that refusal is the whole of A4 and the
lesson of the 2026-09-15 mic outage). SpeechState will not call an
invisible bus "idle". ConfirmState lets go of a latched question the moment
the link drops. BusModel empties its entire cache on `up:false`, because a
stale indicator is worse than no indicator. Every one of those refusals is
correct, and every one of them reaches the screen the same way: the plate
draws nothing.

An empty corner is also the ordinary state of a well machine — §06's earned
emptiness, and the reason `visible` is false most of the time. So the same
absent pixels carried two opposite meanings, and the user had no way to
tell "Jarvis is idle" from "this screen has been blind for a minute and the
microphone could be open". Invariant 10 asks the HUD to show sensor state
truthfully; a silence indistinguishable from a reading is a coin flip. The
one thing the HUD can observe without a bus is whether it HAS one, and
until today the only place that fact appeared was the developer self-test
marker, behind an env var.

`core/LinkState.qml` decides; `LinkPlate.qml` draws NO BUS / SENSOR STATE
UNKNOWN and, underneath, the bridge's own explanation — "connect: [Errno 2]
..." when jarvisd is not running, "bus closed the connection" when it went
away. That second line is passed through rather than summarised: the
distinction between those two is the entire diagnostic value, and this file
has no better information than the process holding the socket. It is
clipped to a glance and its whitespace collapsed, because a newline from
the bridge would not wrap the sentence, it would break the plate. No dot
and no accent colour: ember means Jarvis is doing something and teal means
you are, and this is neither — it is the panel talking about its own pipe.
shell.qml's self-test marker has said exactly that about "bus up / bus
down" since A1; this is the same rule somewhere a user will see it. First
in the stack, because it qualifies everything underneath.

The real work was the WAIT. A down link is ordinary and usually brief:
jv-hud-bridge retries 0.5 s after a link that worked drops (FIRST_BACKOFF_S)
and Quickshell respawns the bridge 2 s after it dies (Bus.qml). A plate that
appeared during either would blink on every `nixos-rebuild switch` of
jarvisd, and a warning that blinks is one nobody reads on the day it is
true. So nothing is said for 5 s — and because that number is only correct
RELATIVE to two constants in two files that have no reason to think about
the HUD, a tools gate now fails the build if either cadence grows past the
grace. VERIFIED it bites from both sides (grace down to 1 s; backoff up to
9 s).

Writing the tests turned up the failure I would not have predicted: the
bridge does not say "down" once. It says it again on EVERY failed retry,
with a fresh explanation and a backoff climbing to 8 s. An element that
restarted its wait whenever it heard "down" would push the report past the
outage that caused it, and for the first several seconds past its own grace
forever. The wait belongs to the outage, not to the last line about it, so
it is armed by a CHANGE of link state and never by a repetition of one.

Three mutation survivors, all real, all fixed:
  · a reported outage handing its verdict to the next brief blip — the
    cry-wolf failure arriving one outage later, which is when nobody is
    looking for it. `waited` is now cleared when a new outage starts being
    timed, and deliberately not when the link returns (`blind` already
    knows there is no outage then). One fact per line.
  · the outage the HUD BOOTS into never being timed at all. `linked` is
    false from the first instant and stays false while a bridge fails to
    connect, so no change signal ever fires for the machine where nothing
    is running — the most important outage there is. Every test assigned a
    property after construction and so armed the wait by accident; the new
    test builds what production builds (`LinkState { bus: Bus }`) and
    nothing else.
  · an `onBusChanged` no path could reach, deleted. The production binding
    is in place before `Component.onCompleted` runs, and every later change
    of link state arrives through `linked`.
The one survivor left standing is `restart()` → `start()`, which no
reachable flow can distinguish (the timer is never running when the element
re-arms it, and QML restarts a running Timer on an interval change anyway).
Kept `restart()` for what it says, and recording the equivalence here
rather than contorting a test around it.

What this does NOT do, and should not: it says nothing about the machine.
A live bus means jarvisd is up and nothing more — jv-ears can be dead
behind a perfectly healthy link, and A6's roster still cannot tell a
service that died from one that never started, because nothing on the bus
announces who is supposed to be running. That is **A24**, and the only
honest source for it (the systemd units the flake declares) would need a
new producer and a schema, so it is a proposal before it is a build.

- tests: `bash ops/ralph/qmltest.sh` — 306 green (was 284), 22 new. 18
  mutations, 17 caught: no grace at all; blindness that never lifts; a bus
  that never answered `linkUp` taken as up; a null bus read as an
  exception rather than as blindness; the verdict inherited by the next
  outage; a live link that keeps timing; a negative grace waited out; the
  grace read as milliseconds; a young link explaining itself; the reason
  refused by truthiness instead of by type (caught only by a
  `failOnWarning(/TypeError/)`); a clipped reason that reads as whole;
  surviving whitespace; newlines collapsed but not tabs; the boot outage
  never timed; a dropped link never timed. `bash ops/ralph/runtests.sh
  tools` — 58 (was 57); `... jv-hud-bridge` — 25 green (untouched, run
  because the new gate reads bridge.py).
- build: `nix build .#jv-hud` ok (qmllint -W 0 clean, 306 QML tests in the
  checkPhase), `nixos-rebuild build --flake .#ares` ok, `nix flake check
  --no-build` ok. Never test/switch. No schema change, no jv-act change,
  no boot path, no NVIDIA/kernel/flake pin touched.
- files: shell/jv-hud/core/LinkState.qml (new),
  shell/jv-hud/LinkPlate.qml (new),
  shell/jv-hud/tests/tst_linkstate.qml (new), shell/jv-hud/shell.qml,
  shell/jv-hud/qmldir + core/qmldir (generated), tools/gen_theme_qml.py,
  tools/tests/test_gen_theme_qml.py, ops/ralph/PLAN.md
- commit: 34f9af8
- next: **A24** (nothing reports which SERVICES are supposed to be running;
  write the proposal first — it needs a producer and a schema) and **A25**
  (how long the HUD has been blind, which is the same question A21 asks
  about the confirm window: may a still, coarse, minute-resolution label
  count as "not motion"?). The standing ask is now TWENTY-FOUR iterations
  old and unchanged in shape: one sitting at ares to (1) look at the HUD —
  `JV_HUD_SELFTEST=1 jv-hud`, a real wake word, a destructive action to
  watch the confirm plate, and now the easiest one of all, since stopping
  jarvisd for five seconds is enough to see today's work; (2) say whether
  the labels are JetBrains Mono; (3) **B10** — record one real spoken turn
  off the live bus (`harness/record.py`). Every replayed trajectory still
  ends in "thinking" and times out, and nothing in the repo has ever
  contained a `speaking` frame, a `sys.health` one, an `action.confirm`
  one, or a link that dropped, so four of the HUD's five plates cannot be
  replayed at all.

## 2026-09-24 — iteration 25 — A26: the HUD says what it heard (+ A24 as a proposal)

Track A opened this iteration with every remaining item blocked: A11 on a
schema review, A13/A21/A22/A25 on a human eye that has now been asked for
twenty-four times, A18 on a topic that does not exist yet, and A24 on
being a proposal rather than a build. So the iteration did A24's actual
deliverable — **proposal R5**, written up in the backlog — and then took
the ladder's "brainstorm a new UI item and pick one" branch rather than
inventing work in a track that is genuinely done.

The gap it picked is the one the HUD had never had a word for. It could
say the microphone was open (A4), that a wake word fired and that Jarvis
was working (A3/A12), and it could say it had gone blind (A23). It could
not say **what it heard** — so the commonest failure of a voice assistant
was invisible until it came back as a wrong answer, and "it misheard me",
"it never heard me" and "it is just slow" were the same dark corner.

`core/HeardState.qml` decides; `HeardPlate.qml` draws jv-ears' transcript
verbatim, teal-dotted (theme.toml reserves the cooler voice for YOUR state
— the open mic is yours, and so are these words), directly under the state
plate. For the stretch `StatePlate` says THINKING, the sentence it is
thinking about is beside it.

Four decisions are the whole of this element, and three of them were made
by something other than taste.

**Finals only** is the schema's own line: "Partials are provisional and may
be rewritten; only finals are acted on." A partial that got rewritten a
breath later would have shown the user a sentence Jarvis never acted on,
which is a more expensive wrong than showing nothing. It is also what
forces a LATCH — partials ride the same topic, so `bus.latest()` replaces
the final with the next utterance's first partial, and a derived reading
would blank itself the instant the user started speaking again, which is to
say at the busiest moment of a conversation. `hey-jarvis-pause` rewrites
itself seven times before it settles, and the replay test walks every one
of those rewrites past the element to prove none of them reaches a screen.

**The exit is a real signal, not a timer.** The line leaves when Jarvis
starts answering, because from that moment the answer is the better report
on whether you were heard. This matters beyond this plate: A22 flagged "on
screen for a fixed duration" as a NEW rule for this HUD, worth deciding
deliberately rather than as a side effect, and nothing here enters that
territory. `holdS` is only the backstop for a turn nobody ever answers —
and a new tools gate fails the build if it drifts from SpeechState's
`thinkWindowS`, because the two are the same claim about the same turn.
The harmful direction is named in the test: words outliving the THINKING
that says they are still live. VERIFIED the gate bites.

**No confidence bar**, and this is the one I expected to decide the other
way. Invariant 4 says handle low-confidence input, and the obvious handling
is a doubt marker — until you look at what the ASR actually produces. The
three real finals in `harness/fixtures/sessions/` carry 0.886 (quiet room),
0.863 (a mid-sentence pause) and 0.739 (a music bed), and **all three
transcribe their sentence correctly**. So every bar inside that spread
flags a word-perfect transcript, and every bar below it never fires:
exp(avg_logprob) is measuring the room, not whether the words are right.
A doubt marker that fires on correct transcripts is one the user learns to
ignore — LinkPlate's cry-wolf failure with better manners. The handling is
therefore to require a numeric `conf` and show the words, and
`tst_sessionreplay` pins the numbers so that changing the decision costs an
argument with real data rather than an edit. The one qualifier that stayed
is `lang`, and only because there is a known gap behind it: the pinned ASR
is English-only, so a frame claiming Hebrew is a frame disagreeing with the
model that produced it (backlog item 12).

**The privacy line.** The bridge's own comment has said since A12 that the
words crossing this pipe are a deliberate choice and not a thing that
happens, and A20 set the precedent by rendering jv-act's question. What
makes this one defensible is upstream: jv-ears transcribes ONLY wake-gated
utterances, so everything on `audio.transcript` was said TO Jarvis after a
wake word. The room's ordinary conversation is seen by the VAD and never
reaches an ASR, let alone a screen. `speech-no-wake` — a real room, real
speech, no wake word, no transcript at all — is replayed through the
element to assert exactly that, and is the test that fires first if ears
ever starts transcribing ungated speech. It is not an argument; it is a
recording.

Writing the tests turned up the thing I would not have predicted: the
FIRST frame a HUD ever sees necessarily lands at age zero. BusModel pins
its clock offset from the frames themselves and keeps the largest estimate,
so there is no such thing as a stale first frame — which quietly made two
of my backstop tests assert nothing at all. They now pin the clock with an
unrelated frame first.

Four mutation survivors out of 25, two real and two equivalences:
  · an `idle` jv-voice read as an answer. Only `speaking` and
    `interrupted` mean the reply began; jv-voice publishes on every
    transition, and an `idle` landing between the transcript and the first
    word — an errored say, a cancelled turn — is the answer NOT starting.
    Reading any state as an answer takes the words away at precisely the
    moment the user is still waiting for one.
  · a final with no `ts` DISPLACING a good line. Without a `ts` there is
    no age and so no backstop, and the envelope check refuses it — but
    nothing said what that refusal COSTS. Refusing to read a frame is
    never the same as being answered, and it must not blank the sentence
    already on screen either.
  · `root.linked &&` in the `heard` binding, which no reachable path can
    distinguish: `onLinkedChanged` nulls the latch first. Kept, because
    ConfirmState is built the same way for the same reason — the gate
    states the rule where the rule is read, and the latch-clear enforces
    it. One of the two would be the thing deleted in a file that had only
    one of them; the sibling element having both is what makes this
    consistency rather than redundancy.
  · `stringOf` reading by type instead of by truthiness. `frame` already
    guarantees all three fields are strings, so nothing reachable reaches
    it with a number. Kept: it is what stops `flatten` throwing inside a
    binding — where the only symptom is a warning nobody reads — the day
    that guard is relaxed.

**A24 is done as a proposal, which was its whole deliverable.** R5 asks for
one new frozen topic, `sys.roster`, published by **jarvisd**: the services
this generation expects and the ones holding a bus connection right now.
Worth recording what the writing turned up — the item's premise was half
wrong. A service that DIED is already caught: `HealthState` expires a
heartbeat at `period_s * 2` and says so. What is invisible is a service
that NEVER STARTED, which is absent from a roster built out of "who has
spoken" and therefore indistinguishable from a well machine. jarvisd is
proposed as the publisher because it is the only process that already knows
who is connected and gains no privilege by saying so; two other shapes were
considered and rejected in writing (baking the list into the HUD at build
time answers only the half that never changes; jv-context polling systemd
answers "the unit is active" when the question is "can it speak on the
bus").

- tests: `bash ops/ralph/qmltest.sh` — 347 green (was 306), 41 new. 25
  mutations on HeardState, 21 caught first pass, 23 after the two real
  survivors were fixed, 2 recorded as equivalences above.
  `bash ops/ralph/runtests.sh tools` — 59 (was 58), the new gate VERIFIED
  to bite from the drift side; `... jv-hud-bridge` — 25 green (the topic
  list grew, its tests read it rather than copying it).
- build: `nix build .#jv-hud` ok (qmllint -W 0 clean, 347 QML tests in the
  checkPhase), `nixos-rebuild build --flake .#ares` ok, `nix flake check
  --no-build` ok. Never test/switch. No schema change, no jv-act change,
  no boot path, no NVIDIA/kernel/flake pin touched.
- files: shell/jv-hud/core/HeardState.qml (new),
  shell/jv-hud/HeardPlate.qml (new),
  shell/jv-hud/tests/tst_heardstate.qml (new),
  shell/jv-hud/tests/tst_sessionreplay.qml, shell/jv-hud/shell.qml,
  shell/jv-hud/qmldir + core/qmldir (generated), tools/gen_theme_qml.py,
  tools/tests/test_gen_theme_qml.py,
  services/jv-hud-bridge/jv_hud_bridge/bridge.py,
  docs/optimization-backlog.md (R5), ops/ralph/PLAN.md
- commit: d7ac325
- next: **A27** and **A28**, both discovered here and both pointing at the
  same human. A27 is the sharper version of A13 — the heard line is drawn
  on every monitor and it is the user's OWN words, with no way to turn it
  off; that is one decision with A13, not two. A28 is why **B10** is now
  worth more than it was: the heard line's EXIT is a `speech.state`
  `speaking` frame, and nothing committed has ever contained one, so the
  departure is the half of this element that only hand-written frames can
  test. The standing ask is TWENTY-FIVE iterations old and has grown by
  one item: one sitting at ares to (1) look at the HUD — `JV_HUD_SELFTEST=1
  jv-hud`, a real wake word (which now puts your own sentence on screen —
  say whether that is wanted at all), a destructive action for the confirm
  plate, and five seconds with jarvisd stopped for the blind plate;
  (2) say whether the labels are JetBrains Mono; (3) **B10** — record one
  real spoken turn off the live bus (`harness/record.py`).

## 2026-09-24 — iteration 26 — B11: the machine can be asked whether it is well

Track A is where it was: A11 waits on a schema review, A13/A21/A22/A25/A27
on a human eye that has now been asked for twenty-five times, A28 and B10
on one recorded utterance off the live bus, A18 on a topic that does not
exist yet. The last three iterations were all UI, which is the ladder's own
signal to take a feature instead — and `docs/optimization-backlog.md` has
nothing to offer (B1 settled that: all 27 findings are human-review-gated).
So this one went to the debug CLI, which is where the standing human ask
actually gets easier: the person who finally sits at ares needs a way to
ask this machine a question and get an answer, not a stream to read.

`jv health` could only FOLLOW. One line per heartbeat, forever, until
Ctrl-C — fine to watch, impossible to ask and impossible to script. There
was no command anywhere in this repo that answers "is Jarvis well right
now", and the only thing that knew was a QML element on a surface nobody
has ever seen.

`jv health --check` listens for one window and answers once: a line per
service heard from, worst first, then the footer, then an exit code that
IS the answer. That last part is the point — `jv health --check || notify`
is a thing a human can put in a shell.

Three rules hold it to the truth, and they are deliberately the SAME three
as the HUD's `core/HealthState.qml`, because they are properties of
`sys.health` rather than of either reader:

- **The roster is who has spoken.** Nothing on the bus says which services
  are supposed to be running (that is proposal R5, still unreviewed), so a
  service that never started is ABSENT from the report, not failed. The
  footer therefore always states the window — "heard from 4 services in
  6.0s" — because the count means nothing without the listening time, and
  because absence is the half of the answer this command may not give.
- **A heartbeat expires.** The schema grants a frame two of its own
  periods; past that it is `lost`, and its `notes` are dropped, because
  they described a moment that has passed.
- **Unreadable is not fine.** A wrong `v`, a hedged `conf`, a body naming
  a service other than the one the broker saw publish it, a missing or
  non-positive `period_s`, a state word outside the frozen enum: all
  `unknown`, all printed, all non-zero exit. `lost` and `unknown` rank
  ABOVE `degraded` — a service that told us it is impaired is in better
  shape than one we cannot hear or cannot read.

Two decisions beyond the port:

**Silence is not an all-clear.** A bus nobody heartbeats on prints "heard
from no service in 6.0s" and exits 1. The tempting alternative — nothing
wrong was found, so exit 0 — is the exact failure this whole command
exists to prevent, and it is the one a script would believe.

**`--check` and `--count` cannot both be asked.** They are two different
exit policies for one status: `-n` means "non-zero if I did not get N
frames", `--check` means "non-zero if the machine is not well". Clap
refuses the combination, so a usage error stays exit 2 and can never be
read as "not well". `--for` is not a conflict — it IS the window, and the
default 6 s is one nominal heartbeat period plus a margin. Ctrl-C ends the
window early and still answers, for as long as it listened, which the
footer states.

The llm rung came along because it is the single number that explains why
Jarvis got slow: read off jv-brain's own heartbeat BY NAME (not from
whoever published `llm_rung` last), suppressed entirely when the brain is
unreadable or expired, and never rendered as "gpu" on a guess — a half-known
gauge prints `backend=?` rather than a reassuring word.

Verified against a real broker and the real binaries, not only the test
harness: a lone `jarvisd` reads `all well` / exit 0, and a pumped degraded
brain reads `jv-brain degraded ... fell back to CPU` first, `llm rung=4
backend=cpu`, `1 not well`, exit 1.

- tests: `bash ops/ralph/cargotest.sh jarvisd` — 51 unit (was 36) and 27
  integration (was 21), 22 mutations run through them. TWO survived the
  first pass and both were real: a `period_s` of 0 or less was believed,
  which made `lost()` fire instantly and report a perfectly talkative
  service as having gone quiet (it is an unreadable body — the schema says
  exclusiveMinimum 0 — and now reads `unknown`); and `starting`/`stopping`
  exited 0 when they were the only finding, which would tell a caller right
  after boot that a service still coming up is ready. Both now have their
  own test; 22/22 caught on the re-run.
- build: `nix build .#jarvisd` ok (its checkPhase runs the suite),
  `nixos-rebuild build --flake .#ares` ok, `nix flake check --no-build` ok.
  Never test/switch. No schema change, no jv-act change, no boot path, no
  NVIDIA/kernel/flake pin touched.
- files: services/jarvisd/src/cli.rs, services/jarvisd/src/bin/jv.rs,
  services/jarvisd/tests/cli.rs, ops/ralph/PLAN.md
- commit: c8b2967
- next: **B12**, discovered here and the sharper half of what this command
  cannot do. `--check` can say a service is not well and can never say one
  is MISSING, so on a machine where jv-ears died at boot it prints a short,
  clean, exit-0 report — which is R5's gap arriving in a second reader, and
  the second reader is what R5 said it was waiting for. Worth noting the
  proposal now has two callers, not one. Beyond that the standing ask is
  unchanged and TWENTY-SIX iterations old: one sitting at ares to (1) look
  at the HUD — `JV_HUD_SELFTEST=1 jv-hud`, a real wake word, a destructive
  action for the confirm plate, five seconds with jarvisd stopped for the
  blind plate; (2) say whether the labels are JetBrains Mono; (3) **B10** —
  record one real spoken turn off the live bus (`harness/record.py`). That
  sitting is now cheaper to prepare for: `jv health --check` tells the
  person whether the machine is ready before they start.

## 2026-09-24 — iteration 27 — A29: the HUD, photographed

Track A is almost entirely human-blocked and has been for three
iterations. A11 waits on schemas (R1), A18 waits on a topic that does not
exist yet, and A13/A21/A22/A25/A27 all wait on the same sentence, now
twenty-six iterations old: *somebody has to sit at ares and look at it.*
Track B is in the same shape — B7 says not yet, B8 says not until there is
a second caller, B10 needs a person at the microphone, B12 needs
`sys.roster` to exist. The backlog in docs/optimization-backlog.md is, by
its own title, human-review-required end to end.

So the highest-value thing available was not another element. It was to
attack the blocker itself.

**What was built.** `ops/ralph/hudshots.sh` renders the HUD to PNG and
`docs/hud/` holds the result: seven shots of one surface at its real size
(300x560, the box shell.qml asks the compositor for), with a README that
says, per shot, where its frames came from. The plates are the real files.
Theme is the generated one. The faces are JetBrains Mono and Archivo,
pinned out of the flake and checked with `fc-match` before anything
renders, because a sheet drawn in DejaVu would be a picture of a fallback.
Every frame goes in as a JSON line through `core/BusModel.qml` — the same
state machine the running HUD uses.

Three of the seven replay `harness/fixtures/sessions` verbatim (B3): the
LISTENING shot is the real wake at 1.44 s, and the HEARD shot carries the
words faster-whisper actually returned off a committed WAV. Four are
composed. **The README says which, per shot, and that line is the whole
value of the sheet** — a composed picture is a picture of an intention,
and only a recorded one is evidence about the machine. The composed frame
that matters is `speaking`: nothing in this repo has ever recorded
jv-voice answering, which is exactly what B10/A28 have been asking a human
for, and now there is a picture of the assumption.

**How it can exist at all.** The plates reach for two singletons that
import Quickshell — `Bus` (it runs the bridge child through Quickshell.Io)
and `Motion` (it reads one environment variable through Quickshell.env) —
and quickshell links its QML plugin into its own binary, so no other
engine can resolve either. QML resolves a singleton through the
directory's qmldir, so the only way to substitute one is to *be* that
directory: the script stages a copy of `shell/jv-hud` and replaces exactly
those two files. Everything else is verbatim, and the staged tree is
linted with the jv-hud build's own qmllint invocation — the only gate the
stubs and the driver have, since they live in `tools/hudshots/` on purpose
so that `pkgs/jv-hud` and the shipped shell are untouched by any of this.

**Three duplications, three gates, all four mutation-checked.** Every one
of these fails silently, which is why each is a test rather than a note:

- a plate added to shell.qml and not to the scene still renders six
  perfectly good pictures of a HUD that no longer exists;
- a member the stub `Bus` forgot reads as `undefined`, and a plate that
  gets `undefined` decides it has nothing to say — a correct plate,
  photographed blank;
- a shot taken and never committed is one nobody can look at without
  running the harness, and an orphaned PNG is a photograph of a HUD that
  has since changed.

Plus a fourth: the grey behind the plates must not be a `theme.toml`
colour. The real surface is transparent, the PNG has to put *something*
behind it or the 0.86 plate opacity is invisible, and if that something
were ever a palette entry a reader would have no way to tell the
photograph's paper from Jarvis's own colours.

Two decisions worth stating.

**The PNGs are not byte-compared against anything.** The obvious next move
is a golden-image test, and it is wrong here: a pixel assertion breaks when
a font ships a new version or Qt changes its rasterizer, and it would fail
in a way nobody can read. The point of this directory is a picture a person
can look at, not a comparison a machine can make. What IS asserted is
`stack.anyLit` per shot — a contact sheet of seven empty rectangles would
look exactly like a HUD with earned emptiness and would actually be a
broken harness, and that one line is what tells the two apart.

**The sheet is the CONTENT of one surface and says so loudly.** Layer-shell,
the empty input mask, the zero exclusive zone, focus behaviour and the
three real monitors are all `shell.qml`'s, and none of them are exercised
here. That means A13/A27 — three copies of one plate across three screens
— is precisely the question a single-surface photograph cannot answer.
Claiming otherwise would have made this worse than nothing, so the README
and the scene's own header both refuse the claim, and A30 records the way
to actually get it: a headless wlroots compositor (cage, or sway with
`WLR_BACKENDS=headless`) plus `grim`, photographing the REAL quickshell
surface on three outputs at ares' real resolutions. That was deliberately
not attempted today — a compositor inside this sandbox is a much larger
and flakier thing than a QML engine, and a flaky gate is worse than an
honest gap.

A31 records the other half of what a still cannot do: A21, A22 and A25 are
all questions about what a plate does over *seconds*, and the sheet makes
them easier to reason about without bringing any of them closer to decided.

- tests: `bash ops/ralph/runtests.sh tools` — 66 (was 60). Four mutations
  run through the new gates, four caught: a plate in shell.qml's stack and
  not the scene's, a function dropped from the stub Bus, a shot renamed so
  its PNG is not committed, and the backdrop set to a palette colour.
  `bash ops/ralph/qmltest.sh` — 347, untouched and green.
- build: `nix build .#jv-hud` ok (unchanged — nothing in `shell/jv-hud`
  was edited), `nixos-rebuild build --flake .#ares` ok. Never test/switch.
  No schema change, no jv-act change, no boot path, no NVIDIA/kernel/flake
  pin touched.
- files: ops/ralph/hudshots.sh, tools/hudshots/{stub/Bus.qml,
  stub/Motion.qml, scene/tst_shots.qml}, tools/tests/test_hudshots.py,
  docs/hud/{README.md, 01..07*.png}, ops/ralph/PLAN.md
- commit: fea019c
- next: **look at `docs/hud/`.** That is the ask, and it is now four
  minutes of scrolling rather than a seat at the machine. Specifically:
  is 01 (all quiet) the right amount of nothing; does 05 want a shortening
  hairline for its 15 s window (A21) and a word on the way out (A22); does
  07 want "NO BUS FOR 4 MIN" (A25). Those three are one human opinion, not
  three. Still genuinely needing the machine, and unchanged: (1) the
  layer-shell behaviour the sheet cannot show — no focus stolen, clicks
  passing through, the surface yielding to fullscreen — which is
  `JV_HUD_SELFTEST=1 jv-hud` and five seconds of looking; (2) whether
  three copies of one plate across three screens is right or noise
  (A13/A27), or **A30**, which would answer it without anyone being there;
  (3) **B10** — one real spoken turn recorded off the live bus
  (`harness/record.py`), which would turn shot 04 from an assumption into
  a recording. `jv health --check` (B11) will tell you whether the machine
  is ready before you start.

---

## 2026-09-24 — iteration 28 — A30: the surface stops being verified by reading the source

For thirty iterations every claim in `shell.qml`'s header was true because
somebody read the file. `WlrKeyboardFocus.None` was a line of QML that
qmllint proved RESOLVES; it would have been just as happy with
`.Exclusive`. `ExclusionMode.Ignore`, the empty input mask, one surface per
monitor, "visible is false whenever nothing is on screen" — all of it was
verified by construction, which is a polite way of saying nobody had
tried it. A29 closed the other gap (nobody had SEEN the plates) and was
explicit that it could not close this one: a QML engine rendering into a
300x560 rectangle knows nothing about compositors.

`ops/ralph/hudscreens.sh` runs the real thing. Headless wlroots (sway,
`WLR_BACKENDS=headless`, pixman) with ares' three monitors — 2560x1440 at
the origin and two 1920x1080 beside it — a real `jarvisd` on a private
socket, and the **shipped** `.#jv-hud`: quickshell, its layer-shell
surface, its own `jv-hud-bridge` child. Frames go onto that bus and the
HUD reads them the way it reads any frame. `grim` photographs each output
and the whole desk. The whole thing comes up in about ninety seconds from
a warm store.

Nothing is staged. That is the one claim this sheet makes that A29's
cannot, and it is also the first thing a future iteration would give up to
make a stubborn run go green, so `test_the_harness_photographs_the_shipped_binary_and_stages_nothing`
reads the driver and fails on any `cp`, `ln -s`, or mention of
`shell/jv-hud` outside a comment.

**The pictures are the smaller half.** Before any PNG is written the run
has to survive four measurements no QML engine can make:

- Everything drawn on each output falls inside the 300x560 box `shell.qml`
  anchors to the top-right, with the right-hand gap equal to
  `geometry.inset_px`. Measured per monitor, so "one surface per screen"
  is part of it.
- The seat's focused node, read with no HUD running and again while the
  HUD is drawing, is the same node.
- The quiet shot comes back pixel-identical to the bare desktop on all
  three monitors. Not "looks dark": an unmapped surface, measured.
- No workspace has lost usable area.

Five mutations were built and photographed. **Three caught**: anchoring
the surface `left` (drew at x46..283 on a monitor whose box starts at
2244), `WlrKeyboardFocus.Exclusive` + `focusable: true` (the seat moved
from node 6 to node 0), and a `HealthPlate` whose `shown` is hard-coded
true (the quiet shot drew a 20x20 square on a screen that should have been
bare). A sixth, `model: [Quickshell.screens[0]]`, was caught by the
per-monitor corner check — which is the A13 claim itself.

**Two equivalences, both recorded rather than papered over.** The first is
the interesting one and cost three builds to pin down. `ExclusionMode`
set to `Normal` — and then to `Auto` — changed not one pixel of any
workspace rect. The reason is the wlr-layer-shell protocol: an exclusive
zone is only honoured for a surface anchored to ONE edge, or to an edge
plus both perpendicular ones, and this surface is anchored to a CORNER
(top + right). So what actually keeps the HUD from pushing anyone's
windows around is the anchor, and `ExclusionMode.Ignore` is the belt to
its braces. The check is kept because the day those anchors change — a
status strip along the top edge is the obvious future — the zone becomes
real; VERIFIED it bites then, by anchoring left+right+top with `Auto`,
which took HEADLESS-1's usable area to 2560x880. The second equivalence:
the self-test `Loader` forced `active: true` shows nothing, because
`visible` still gates the whole surface on `anyLit`.

What the sheet **cannot** say, and says so on its own first page: sway is
not Niri, the outputs are headless (right sizes, no scanout, no panel, no
NVIDIA, named `HEADLESS-1..3`), and nothing here knows whether an 11 px
label is comfortable from where you actually sit. It answers "is it on all
three screens, in the right corner, costing nothing" — which is what
A13/A27 were blocked on — and not "does it look right".

Two smaller decisions. The desktop behind the HUD is the same flat
`#31353B` A29 paints its backdrop with, and a tools gate now requires the
two sheets to agree: without something behind them the plates' 0.86
opacity is invisible, and two different greys across two documents read as
two different HUDs. And the sheet is honest that reruns are not
byte-identical — consecutive runs of an unchanged HUD move about five
pixels by one value along an antialiased glyph edge, so a dirty
`git status` after a re-run is not evidence of anything.

`02-heard-desk.png` is the picture A13 and A27 have been blocked on: the
same THINKING, the same "Hey Jarvis, what time is it?", the same MIC,
three times, once per screen. Nothing was built toward an answer.

- tests: `bash ops/ralph/runtests.sh tools` — 77 (was 66). Ten mutations
  run through the new gates, ten caught: an orphan PNG, a backdrop that is
  a Jarvis colour, a driver that stages a copy of the shell, a driver that
  sets `JV_HUD_SELFTEST`, a shot with no README section, a surface box
  that drifts from shell.qml, an inset that drifts from theme.toml, a
  dropped monitor, the only dark shot going lit, and a sheet with no
  whole-desk photograph. `bash ops/ralph/qmltest.sh` — 347, untouched and
  green.
- build: `nix build .#jv-hud` ok, `nixos-rebuild build --flake .#ares` ok.
  Never test/switch. No schema change, no jv-act change, no boot path, no
  NVIDIA/kernel/flake pin touched. Nothing new enters any closure: sway,
  swaybg, grim, numpy and msgpack are realized by the harness at run time
  and are not inputs to anything the machine installs.
- files: ops/ralph/hudscreens.sh, tools/hudscreens/{sheet.py,shoot.py},
  tools/tests/test_hudscreens.py, docs/hud/screens/{README.md, 6 PNGs}
- commit: d56b12e
- next: **A13 and A27 are now one look at `docs/hud/screens/`**, and
  answering them is a two-minute human opinion rather than a seat at ares:
  three copies of your own sentence across three monitors — right, or
  noise, and should there be a `personality/` switch. The three timing
  questions (A21 the shortening window, A22 granted/denied/timed-out
  leaving differently, A25 "NO BUS FOR 4 MIN") are still one human call on
  `docs/hud/`, and A31 — the three-frame strip — is the build that follows
  IF the stills turn out not to be enough. Still genuinely needing the
  machine: **B10/A28**, one real spoken turn recorded off the live bus, is
  now worth more again, because this harness would replay it onto a real
  compositor and photograph the answer arriving. `jv health --check` (B11)
  says whether the machine is ready first. New: **A32** — the empty input
  mask is the one invariant-10 claim this harness still cannot test, for
  want of a second client to click through to.

## 2026-09-24 — iteration 29 — A32: the empty input mask stops being a
## claim nobody tested

A30 turned four of invariant 10's structural promises into
measurements and left one alone, for a reason it stated in its own
header: `mask: Region {}` is a claim about a window UNDERNEATH the
HUD, and the harness had no second client. A compositor with nothing
on it will let any click through, however greedy the layer surface —
so the check would have passed on a HUD that ate input, which is worse
than no check.

So the harness gets a second client. `probe_click_through` runs after
the photographs (it puts two windows on screen, and every shot above
needs a bare desktop behind the HUD): one ordinary Wayland toplevel
tiled to fill the primary monitor, underneath the HUD, and one on a
side monitor whose only job is to hold the keyboard between clicks, so
that "focus moved" is a fact about the click rather than about where
focus already was. Three points, all of which must end with the
keyboard on the window under the HUD:

  · a CONTROL clear of the surface. Without it a harness whose clicks
    went nowhere at all would report a perfect pass-through, which is
    the way this measurement fails silently.
  · a pixel the HUD actually PAINTED — read out of the capture rather
    than guessed at, so it is over a plate and not over transparency.
  · a point inside the 300x560 surface box that the HUD painted
    NOTHING on. The likelier future mistake is an input region that
    tracks the content, which looks perfectly reasonable in a diff.

**It starts no jarvisd, on purpose.** The probe needs a lit HUD that
does not expire, and every other lit state in this shell is a frame
ageing out — a heartbeat speaks for two of its own periods, a
confirmation for its window. A plate that blanked mid-probe would
report a pass-through that was really an unmapped surface. A bus the
HUD cannot see is the one thing it says indefinitely (LinkPlate, after
LinkState's 5 s grace), and the input region is a property of the
surface, never of what is drawn on it. The probe still brackets it:
the painted box is measured before the clicks and again after the
windows are gone, and the two must match.

**What the measurement is, exactly.** The window's own `wl_pointer`
never fires. A headless seat has no input device, so it advertises no
pointer capability and no client binds a pointer at all — I checked,
with `wev` under this compositor: `capabilities: none`, and not one
pointer event for a click that sway itself was routing. (A transient
virtual pointer via `wlrctl` does give the seat a pointer, but the
device dies with the process, so the client is still binding when the
button arrives — a race, not a test.) The button is synthesised through
sway's IPC and the witness is sway's own ROUTING, read back over IPC.
That routing IS the hit test — `node_at_coords` consults each layer
surface's input region before it ever looks at a window — so the
direction of the claim is right, and the mutations prove the direction
rather than assuming it. The README says all of this on its own page;
a reader who took it for "the client logged a button" would over-trust
it.

Three mutations, built and photographed, three caught by two different
points:
  · delete `mask: Region {}` → the painted pixel fails ("the keyboard
    stayed on 10").
  · `mask: Region { y: 200; width: 300; height: 360 }`, i.e. a region
    over only the lower, unpainted half of the box → the painted pixel
    PASSES and the third point fails. That is the one that shows the
    third point is not decoration.
  · `LinkState.graceS: 600` → the plate never arrives and the probe
    fails with "the HUD never drew anything ... in 25s" rather than
    sailing through. This is the guard against the whole stage going
    vacuous, and it is the one I most wanted to see bite.

Two smaller things. The compositor config moved out of the driver's
heredoc into `sheet.sway_config()`, so the checks read the same text
the compositor was given rather than a second copy of it; and it gained
`focus_follows_mouse no`, because `cursor set` is a warp and a
compositor that follows the mouse could move focus before any button
existed — the probe would then report a pass-through that no click
caused. Both are gated.

The PNGs are unchanged and deliberately not re-committed: the HUD did
not change, and a re-run moves about five pixels along an antialiased
glyph edge, which the sheet already says is not evidence of anything.

- tests: `bash ops/ralph/runtests.sh tools` — 83 (was 77). Eight
  mutations run through the six new gates, eight caught: a compositor
  that follows the mouse, a config that drifts from the sheet's monitor
  positions, a driver that writes its own config, a driver with no
  second client, a shoot.py that never starts one, a `main()` that
  defines the probe and never calls it, a README that drops the
  wl_pointer caveat, and a README that stops naming the mask.
  `bash ops/ralph/qmltest.sh` — 347, untouched and green.
- build: `nix build .#jv-hud` ok, `nixos-rebuild build --flake .#ares`
  ok. Never test/switch. No schema change, no jv-act change, no boot
  path, no NVIDIA/kernel/flake pin touched. `wev` is realized by the
  harness at run time and is not an input to anything the machine
  installs.
- files: ops/ralph/hudscreens.sh, tools/hudscreens/{sheet.py,shoot.py},
  tools/tests/test_hudscreens.py, docs/hud/screens/README.md
- commit: 48d9c74
- next: the header of `docs/hud/screens/README.md` now has no
  structural claim left that rests on a reading — which means the
  remaining Track A items are all questions for a person, and they have
  not moved: **A13/A27** (three copies of your own sentence across
  three monitors — right, or noise, and should there be a
  `personality/` switch) are two minutes on `02-heard-desk.png`, and
  **A21/A22/A25** are one opinion about what a plate does over seconds,
  with **A31** — the three-frame strip — as the build that follows only
  if the stills turn out not to be enough. Still genuinely needing the
  machine: **B10/A28**, one real spoken turn recorded off the live bus;
  this harness would now replay it onto a real compositor AND click
  through it. New: **A33** — the probe proves a click passes through and
  says nothing about scroll or hover, which share the same input region
  and are the two a user would notice next.

## 2026-09-24 — iteration 30 — B13: the latency number stops containing
## the user's own voice

Track A is where the ladder points first and every open item on it is a
question for a person: A13/A27 want two minutes of opinion on
`docs/hud/screens/02-heard-desk.png`, A21/A22/A25 want one opinion about
what a plate does over seconds, A31 and A33 are builds that follow those
answers, and A11 is blocked on proposal R1. Three iterations of UI in a
row besides. So: the backlog.

PHASE1-STATUS has carried the same open line since the first on-hardware
measurements — *"decide the measurement anchor (VAD end vs start) and
re-state the budget accordingly"*. The exit criterion for this phase is
`"hey jarvis" → spoken reply, end-to-end < 2.5 s, measured by jv tap`,
and the FAIL recorded against it is 5353 ms best, typical 5-7 s. What
`jv tap --latency` measured was the earliest ts of any frame carrying an
utterance_id, to the first `speech.say`. Two or three seconds of that is
the user speaking. The number could not be compared to the budget it was
being compared to, and nothing in the output said so.

**A turn is now four spans, and each one has exactly one owner.**

```
  speech_start        last speech      speech_end      first speech.say
       |---- spoke ------|---- hold ----|---- respond ----|
       |-------------------- total ----------------------|
```

`spoke` is the user talking, and no faster machine shortens it. `hold`
is jv-ears' `vad_min_silence_ms` — the silence it deliberately sits
through so a 1.2 s mid-sentence pause does not end the utterance;
machine time, and tunable. `respond` is ASR, the brain, and the bus hops
between them. So the machine's share of a turn is `hold + respond`, and
that is printed as a rule under the table rather than left to be worked
out. Per-span p50/p95/max, and one line per turn as it completes.

It does NOT re-state the budget. Which span the 2.5 s applies to is a
human's call — a good case exists for `hold+respond` (what Jarvis costs)
and for `total` (what the user experiences), and they differ by seconds.
The point is that the call can now be made against data instead of
against one figure that mixes both.

**The boundary had to come from somewhere.** Only jv-ears knows its
endpoint hold, so it publishes it: `vad_min_silence_s` on its
`sys.health` `metrics`, the same free-form section `wake_timeout_s` has
used since A14, so nothing frozen moved (invariant 2). B7's rule was
"publish a gauge WHEN something reads it, not before" — this is the
reader, and it is the second reader of that section, which is what B7
was waiting for.

**No fallback, on purpose.** The HUD's `EarsBudgets` falls back to ears'
shipped defaults, because the HUD has to draw something. This is a
measuring instrument, and an instrument that substitutes a constant for
a reading is exactly how a number stops meaning what its label says. A
tap that has not heard a jv-ears heartbeat prints `?` for the two spans
that need one, drops both rows from the table, and says which gauge was
missing and that `total` therefore still has the user's voice in it.
`spoke` and `hold` are recorded together or not at all — they are two
halves of one subtraction, and a hold that does not FIT inside the
segment it is supposed to be part of (ears restarted mid-tap with
different tuning) produces no third number rather than a negative one.

**Two real bugs fell out of writing it down.**

1. `audio.transcript` was allowed to define an utterance's start. A
   partial transcript carries the same `utterance_id` and is emitted
   PART-WAY through the utterance, so any turn whose partial was routed
   ahead of its vad frame was silently measured short — by however much
   of the sentence had already been said. The old code's comment
   defended taking the earliest ts of any such frame; the earliest ts of
   the WRONG frame is still the wrong answer. Boundaries now come from
   `audio.vad` alone, by `event`.
2. The one integration test covering any of this published
   `{"kind": "speech_start"}` on `audio.vad`. The schema's field is
   `event`. Nothing caught it because the old reader never looked at the
   field at all — it took any frame with an `utterance_id`. A fixture
   that does not match the schema it claims to imitate is a test proving
   something about a bus that does not exist.

Also: the report is anchored on the frames' own `ts` now, not on
`mono_now()` when this process got round to them. Every other boundary
in the calculation is a frame ts, and a tap doing other work must not
inflate the number it exists to report. That change is NOT pinned by a
test — a test would have to starve the reader deliberately — and it is
recorded here rather than claimed.

**Seven mutations, six caught, one real survivor fixed, one equivalence
recorded.**

  · `speech_end` also sets the start → the mid-utterance test fails
    (`total=?` becomes a number measured from the wrong end).
  · a transcript defines the start again → the transcript test fails
    (a turn gets reported that nothing on the bus bounded).
  · the hold falls back to jv-ears' shipped 1.5 → the no-budget test
    fails; a constant had been printed as a reading.
  · the hold is read off anyone's heartbeat → refused-unless-jv-ears
    fails.
  · a hold that does not fit is subtracted anyway → the fit test fails.
  · `?` prints as `0ms` → unknown-not-zero fails.
  · SURVIVED, then fixed: `spoke` and `hold` recorded independently.
    A hold that did not fit left its own row in the table with n=1
    beside a `spoke` row with n=0 — two rows averaging over different
    sets of turns, under a footer saying the spans were unmeasured.
    `a_hold_that_did_not_fit_takes_its_own_row_down_with_it` now pins it.
  · EQUIVALENCE, recorded not fixed: publishing the hold as
    `cfg.vad_min_silence_ms / 1000` instead of
    `_min_silence / sample_rate` passes. At 16 kHz the two are
    identical for every integer millisecond (`ms * 16000 // 1000` never
    truncates), so the docstring's "the day this rounds differently,
    what is published follows the code" is true and untestable at the
    rate this runs at. Distinguishing it would mean building the
    pipeline at a sample rate openWakeWord and Silero do not accept,
    which is a worse test than none. The pre-existing `wake_timeout_s`
    test has exactly the same property.

One flake, seen once and chased: `health_check_prints_the_rung_the_brain_reports`
(`--for 0.6`, pre-existing) failed on the first run with the new
integration tests holding three `jv` children and six bus clients open
for 2 s each. The new tests were cut to 1.2 s windows and 30 ms cycles;
five consecutive full runs since are clean. Recorded rather than
declared fixed — the window is tight and the next test added here may
find it again.

- tests: `bash ops/ralph/cargotest.sh jarvisd` — 63 unit + 31
  integration + 7 bus (was 57 + 27 + 7), all green, run five times for
  the flake. `bash ops/ralph/runtests.sh jv-ears` — 37 (was 36).
  `bash ops/ralph/runtests.sh tools` — 83, untouched and green.
- build: `nix build .#jarvisd` ok (it runs the same tests in its
  checkPhase), `nixos-rebuild build --flake .#ares` ok. Never
  test/switch. No schema change — `metrics` is free-form by
  `schemas/sys.health.json`. No jv-act change, no boot path, no
  NVIDIA/kernel/flake pin touched.
- files: services/jarvisd/src/cli.rs, services/jarvisd/src/bin/jv.rs,
  services/jarvisd/tests/cli.rs, services/jv-ears/jv_ears/pipeline.py,
  services/jv-ears/tests/test_pipeline_fixtures.py, PHASE1-STATUS.md
- commit: ee96c43
- next: **the question this hands to a human is small and concrete** —
  which span the 2.5 s exit budget names. `hold+respond` is what Jarvis
  costs and what an optimisation would move; `total` is what the user
  waits through. Answering it also decides **B15**, which would push the
  end of the measurement from `speech.say` (brain hands words to voice)
  to `speech.state` `speaking` (the user actually hears something) —
  the same conversation, so ask them together. **B14** splits `respond`
  into ASR and brain with one more anchor already on the bus, and is
  worth doing the day someone is optimising either. Everything on Track
  A is still waiting on the same two human opinions: **A13/A27** (two
  minutes on `docs/hud/screens/02-heard-desk.png`) and **A21/A22/A25**
  (what a plate does over seconds). **B10/A28** still need one real
  spoken turn recorded at ares — and it is worth more now than it was
  this morning, because a recording with `sys.health` in it would be the
  first thing that could replay this whole measurement.

## 2026-09-24 — iteration 31 — B14: `respond` stops being one number
## over two services

Track A was picked over first, as the ladder says, and every open item
on it is gated on something this loop cannot supply: A11 waits on
proposal R1, A13/A27 and A21/A22/A25 on two minutes of a human's
opinion, A28/B10 on one spoken turn recorded at ares, A31 on whether
the A29 stills were enough, A33 on the input mask ever being edited,
A18 on a topic that does not exist yet. So: B14, which PHASE1-STATUS
has been asking for since the 2026-09-15 latency FAIL.

**The measurement had two services in one span.** B13 split a turn into
`spoke` (the user), `hold` (ears' endpoint wait) and `respond`, and
`respond` is jv-ears' ASR *and* jv-brain. PHASE1-STATUS carries those
two as SEPARATE open latency items — "ASR is ~2.2 s fixed" and "prefill
is fixed but generation is not" — and one number over both cannot say
which of them a change moved. The figures it quotes for each came from
llama-server's own timings and a stopwatch, not from the bus.

**The frame that divides them was already there.** `jv-ears`'
`_on_speech_end` publishes `audio.vad` speech_end, THEN runs whisper,
THEN publishes the `audio.transcript` final. So the final is the seam,
on the bus, in the right order, for free. `respond` now splits into
`hear` (speech_end -> final: jv-ears' ASR) and `think` (final -> first
`speech.say`: jv-brain to its first word, plus a bus hop each way),
which partition it exactly. No new publisher, no schema change — B7's
rule ("publish a gauge when something reads it") did not even need
invoking, because nothing new is published.

What the seam is NOT:

  · **not a boundary.** B13's whole bug was a partial transcript being
    allowed to say where an utterance began. A final says where ASR
    ENDED, which is a moment inside a turn, not a turn. So `heard()`
    annotates an utterance `audio.vad` already bounded and never
    creates one — otherwise a bus with finals and no vad would print
    `>>> turn` lines for things no service ever called a turn.
  · **not any transcript.** Only `kind: final`. A partial is
    provisional output that may be rewritten.
  · **not an anchor that lands outside the span it divides.** A final
    before its own speech_end, or after the first word answering it,
    means two frames disagree about the order the pipeline ran in.
    Both halves are refused, not one of them published as a negative —
    and not just the half that would go negative, because an anchor
    that is not trusted for one side is not trusted for the other.
  · **not mandatory.** jv-ears publishes NO final for an utterance its
    ASR read as empty (`_emit_transcript` returns early on empty text),
    and a tap can simply have missed the frame. Then both print `?`,
    `respond` stays whole, and the table says which frame was missing.

`hear` and `think` are pushed to the stats on their own terms, unlike
`spoke`/`hold`: they are two subtractions sharing a middle anchor, not
two halves of one, and `hear` needs a speech_end where `think` does
not. A tap that joined mid-utterance can therefore time the brain and
not the ASR, and the `n` column is what says so.

**The flake from iteration 30 was not a flake.** Adding one more
integration test made `health_check_puts_the_worst_finding_first_and_fails`
fail 5 runs out of 5 — and on the pre-change tree it passed 3 out of 3,
so this was load, not chance. The cause: `silent_broker()` sets
`health_period: 3600s` and a tokio interval's FIRST tick fires
immediately, so jarvisd published a heartbeat at t=0 regardless. At
that moment its accept loop has taken no connection, so the beat
reaches nobody — unless the machine is busy enough that a client got
accepted and subscribed before the health task was first polled, and
then it reaches them. Which clients see a heartbeat was being decided
by the scheduler. Both readers of `sys.health` are built on "a
heartbeat speaks for two of its own periods"; a beat with an
unpredictable audience is the one thing that rule cannot absorb. The
broker's first beat is now due one whole period in, which is what
`period_s` claims it is. Nothing in production loses a beat it could
have read: `jv health --check` defaults to a period plus a margin, and
the t=0 beat was unreachable by construction anyway.

Mutations — 11 run, 11 caught, TWO REAL SURVIVORS fixed:

  · SURVIVED, then fixed: dropping the `kind == "final"` check entirely
    changed nothing. Every jv-ears partial is published BEFORE its
    speech_end, so the out-of-order guard refused them anyway and the
    `kind` check was doing no work the test could see — accidental
    immunity, exactly the shape A18 warns about. The test now puts a
    partial where a seam belongs, between speech_end and the first
    word, where nothing but its `kind` can disqualify it.
  · SURVIVED, then fixed: the earliest-ts test fed `14.0` then `13.5`,
    and "keep whichever came last" gives the same answer as "keep the
    earliest" for that order. It now runs both orders.
  · Caught: a final conjuring an utterance; no ordering filter; a bad
    seam killing `hear` but not `think`; keeping the latest ts; the
    missing-seam footer removed; hear/think printed after respond;
    `think` measured from speech_end (so it would equal `respond` and
    double-count `hear`); `?` printed as `0ms`; the broker's immediate
    tick restored; the broker's first beat at a quarter period.

- tests: `bash ops/ralph/cargotest.sh jarvisd` — 71 unit + 8 bus + 32
  integration (was 63 + 7 + 31), green five consecutive times.
  `bash ops/ralph/runtests.sh pylib` — 4, including
  `test_health_heartbeat_arrives` against the REAL broker with the new
  timing. `bash ops/ralph/runtests.sh jv-hud-bridge` — 25, three
  against a real jarvisd.
- build: `nix build .#jarvisd` ok (it runs the same tests in its
  checkPhase), `nixos-rebuild build --flake .#ares` ok. Never
  test/switch. No schema change, no jv-act change, no boot path, no
  NVIDIA/kernel/flake pin touched.
- files: services/jarvisd/src/cli.rs, services/jarvisd/src/bin/jv.rs,
  services/jarvisd/src/broker.rs, services/jarvisd/tests/cli.rs,
  services/jarvisd/tests/bus.rs, PHASE1-STATUS.md
- commit: f7f1572
- next: **B15 plus B13's open question are still one conversation** —
  which span the 2.5 s budget names, and whether the measurement should
  end at `speech.say` (brain hands words to voice) or at
  `speech.state` `speaking` (the user hears something). Ask them
  together. **B16** (jv-brain publishing its own `first_token_ms`, so
  `think` can say how much was the model) is the same move this made
  for `hear`, and is worth doing the day someone optimises generation.
  **B17** is new and cheap to ask for: nobody has ever LOOKED at
  `jv tap --latency` output on a real turn, and the live line is now
  six numbers wide — fold it into the same visit as B10/A28's recording
  and A13/A27's two minutes at the screen. Track A unblocks the moment
  a human spends ten minutes at ares; until then this loop has Track B.

## 2026-09-24 — iteration 32 — A34: the HUD's idle cost stops being an argument

PLAN.md had no doable item left. Track A is six items deep in questions
that need a human at ares or an opinion on a still picture (A13, A21,
A22, A25, A27, A31); Track B's four open items are all "when a second
caller exists" or "when the human decides which span the budget names";
`docs/optimization-backlog.md` is human-review-required from top to
bottom. So this took the one §06 claim that was still resting on an
argument rather than a number.

Invariant 10 and §06 both say the ambient scene costs "< 2 ms of GPU per
frame, 0 fps when idle". A30 and A32 turned three of invariant 10's
promises into measurements — no space reserved, the keyboard never
moves, a click passes through — and left this one, because the argument
for it is genuinely good: Qt Quick renders on change, `shell.qml` unmaps
the surface when the stack has nothing to say, therefore zero. Both
halves are true. Neither is a measurement, and what would break them is
not a bad argument but one ordinary edit: a plate that pulses, a
duration that counts up, a `NumberAnimation` left on
`loops: Animation.Infinite`. Each of those looks correct in a diff, is
invisible in a photograph, and costs a composite of three monitors
forever.

`probe_idle_frames` counts the HUD's own Wayland commits — libwayland's
`WAYLAND_DEBUG` log, read off the client side of the socket. A commit is
the thing that actually costs a composite, and counting the protocol
needs no cooperation from Qt and no compositor feature. Two windows, six
seconds each, because §06 claims this of two different states: QUIET (a
live bus with nothing on it, surface unmapped) and LIT (a plate on
screen, nothing new to say). Measured: 0 and 0.

**The controls are the whole design, not a garnish.** A probe that
passes on zero fails open: an unset env var, a libwayland that renames
its objects, a log that turns out not to be the HUD's — every one of
those reads exactly like a perfectly still HUD. So each window is paired
with a stretch that MUST contain commits, counted by the same code
through the same log: a real jv-ears heartbeat waking the quiet HUD
(44 commits), and the blind plate arriving before the lit window
(42 commits). Both of them bit for real during this iteration:

  · the first version's pattern was `wl_surface@\d+\.commit\(\)`, which
    is how libwayland has always printed object ids and is NOT how the
    build under this harness prints them — it writes `wl_surface#41`.
    The quiet window reported a flawless 0 and the control killed the
    run on the next line. Without it this would have been committed as
    a green measurement of nothing. The pattern now takes both, and the
    comment says why the controls exist.
  · deleting `WAYLAND_DEBUG` from the lit stage fails at the second
    control rather than reporting zero.

The headline mutation is the bug this exists to catch: a 4 px ember
square inside `LinkPlate` on `loops: Animation.Infinite`. It passes
qmllint, passes all 347 QML tests, passes `nix build .#jv-hud`, and is
invisible in every photograph the sheet takes. The lit window reads
**1110 commits (1113 frame callbacks) in 6 s** — ~62 fps on each of
three surfaces, on a desktop where nothing is happening.

That mutation also proved the quiet window is nearly tautological: with
the HUD animating at 62 fps, QUIET still read 0, because an unmapped
surface cannot commit whatever the scene graph is doing. All the work is
done by the lit window (A35 follows from that).

The instrument itself — `COMMIT_RE`, `FRAME_RE`, `surface_traffic()` —
moved into `tools/hudscreens/sheet.py`, for the same reason
`sway_config()` lives there: shoot.py needs numpy and a compositor, and
an instrument nothing can execute is one nobody can check. Two of the
new tools tests run the counter over verbatim log lines from a real run
(both `@` and `#` forms) and over the traffic it must NOT count —
`xdg_surface.commit`, `wl_surface.destroy`, `wl_callback.done`.

Also here, since it is the same paragraph of §06: the README and the
driver header now state which half was measured. Only "0 fps when idle".
This compositor renders with pixman, in software, on a headless backend;
no frame here took any time on a 1660 SUPER, and calling this a GPU
budget measurement would be the exact over-trust every other page of
that sheet is written against (A36).

Three small things came out of it: `Proc.mark()`/`Proc.since()` (a
measurement over a stretch of a log still being written),
`wait_for_blind_plate()` extracted from the click probe, which now has
two callers, and `check_desk_is_bare()` extracted from `main()`, which
now says which of its two claims it is asking. No PNG changed: nothing
in `shell/jv-hud` was touched, so the pictures are of the same HUD and
re-rendering them would have been a diff of antialiasing noise.

- tests: `bash ops/ralph/runtests.sh tools` — 89 (was 83).
  `bash ops/ralph/qmltest.sh` — 347, untouched but run because the
  mutation lived in a plate. `bash ops/ralph/hudscreens.sh` — the whole
  sheet green end to end, three times: once for the fix, once after the
  instrument moved, once final. Two mutations, two caught, plus the
  regex defect the control caught on its own.
- build: `nix build .#jv-hud` ok (qmllint + 347 QML tests in its
  checkPhase), `nixos-rebuild build --flake .#ares` ok. Never
  test/switch. No schema change, no jv-act change, no boot path, no
  NVIDIA/kernel/flake pin touched.
- files: tools/hudscreens/shoot.py, tools/hudscreens/sheet.py,
  tools/tests/test_hudscreens.py, ops/ralph/hudscreens.sh,
  docs/hud/screens/README.md
- next: **A35** is the real successor — only ONE lit state can be held
  still long enough to measure (LinkPlate with no bus), because every
  other plate is a frame ageing out, so confirm / heard / state / mic /
  health have never been watched standing still. It becomes urgent the
  day A21 or A25 is answered "yes, let it move", since that is the day
  a plate is deliberately given an animation and someone has to say how
  much it costs. **A36** is the other half of the §06 sentence and is
  not yet a question: there is no ambient scene to price. And the human
  asks are unchanged and now number five (A13/A27 together, A21/A22/A25
  together, B10+A28+B17 together, B13/B15) — this loop has built every
  measurement it can build without them.

## 2026-09-24 — iteration 33 — A37: the HUD says what Jarvis did to your
## machine when it did not work

Track A's open items are still questions for a human (A13/A27, A21/A22/
A25, A31) or gated on a signal that does not exist yet (A35, A36);
`docs/optimization-backlog.md` is human-review-required from top to
bottom, so it is not the "non-human-review backlog item" the ladder
points at. The ladder's own fallback is to find the highest-value thing
the HUD does not yet say, and there was one left that nothing in PLAN.md
had ever named.

**Invariant 3 gives exactly one process the right to change this
computer, and the HUD had no word for the outcome of any of it.** A20
put the QUESTION jv-act asks before a destructive tool on screen; what
came of it — of that tool or of any other — was never shown. So "it did
it", "it broke", "it was refused" and "nothing was ever asked" were the
same empty corner, and the only report on any of them was a sentence
jv-brain composed afterwards out of `action.result.output`. That
sentence is a paraphrase by a language model of an error it did not
witness; this plate is the tool's registry name and the schema's own
error word, which is to say the two strings you can go and grep for in
`jv act-log`.

`core/ActionState.qml` decides and `ActionPlate.qml` draws. Three
decisions are the element:

  · **FAILURES ONLY.** An action that worked draws nothing. The machine
    visibly doing the thing is the report that it was done, and a corner
    that lights up for every volume change is one nobody reads on the
    day it matters — HealthPlate's argument (A6) applied to actions
    instead of services, and the thing that keeps §06's earned emptiness
    real rather than decorative. A success is not merely ignored, it
    CLEARS a held failure: the brain retrying with another tool and
    getting it right is newer news about the same machine, and a failure
    left standing under it would describe a machine that is not the one
    in front of you.
  · **NEVER A TOOL IT CANNOT PROVE.** This is the one that took the
    thinking. `action.result` carries a `request_id` and no tool name —
    the name is in the `intent.action` that asked — and `bus.latest()`
    holds exactly ONE frame per topic, which may well belong to a
    different request by the time an outcome lands. A HUD that took the
    name on faith would eventually name the wrong tool, and a lie about
    what touched your machine is strictly worse than the empty line it
    replaced. So the ids must match or the failure is reported without a
    name, and the pair is latched TOGETHER at the instant the failure is
    accepted, because both of its sources keep moving afterwards. The
    mutation that binds the displayed name to `toolFor()` at render time
    instead reads beautifully and relabels a failure that has not
    changed the moment the brain tries the next thing.
  · **NOT `denied` / `confirm_timeout`.** Those two are how a
    CONFIRMATION ended, and A22 — granted, denied and timed out all
    leaving the screen identically — is deliberately an open question
    for a human. Answering it as a side effect of a different element is
    exactly what A22 asked not to happen. They are passed over, and
    passed over as NO NEWS rather than as an outcome, so a denial
    landing after a real failure cannot silently take it off the screen.

The exit is a real signal and not a timer, which is the rule A26 set and
this keeps: Jarvis starting to explain (jv-brain is handed every
action.result and phrases it, so from then on the explanation is the
better report), a newer outcome, or the link dropping — with `holdS` as
the backstop for a failure nobody ever explains (a `jv` run with nothing
to speak, a brain that died between the tool and the sentence). The
comparison is against the failure's own `ts` and not against a
`speaking` frame merely existing, because a tool call in the middle of a
streamed reply leaves one on the topic that is about the sentence
BEFORE the attempt; deleting that comparison passes qmllint and silences
the plate on every turn where Jarvis narrated first.

`intent.action` and `action.result` joined the bridge's topic list, and
`intent.action.args` is the most sensitive body on it — whatever the
tool was asked to operate on, a path or a search string or a window
title. The bridge forwards whole envelopes on purpose (`conf`, `ts` and
`seq` are why), so the rule has to live at the other end: a new tools
gate fails the build if any element under `shell/jv-hud/core` so much as
NAMES `args` or `detail`, scoped to core/ because that is the only half
where those words can mean the bus field (HealthPlate has a row field
called `detail` built out of the health schema's own state words, and
it is innocent). The `08-action` shot composes frames carrying both
fields, so the contact sheet is the demonstration rather than the
claim.

Also found, and recorded against B15 rather than acted on: **`speech.state`
`speaking` is not the moment the user can hear anything.** jv-voice
publishes it BEFORE handing the text to Piper, so the whole CPU
synthesis of the first sentence sits between that frame and the first
audible sample. B15 was written on the premise that it is "exactly that
moment" and would have measured a number labelled "until you hear it"
that excludes synthesis — the same failure B13 was written against. The
options are not equal and both are now written down in PLAN.md; neither
is a schema change.

- tests: `bash ops/ralph/qmltest.sh` — 384 (was 347), 35 of them new.
  `bash ops/ralph/runtests.sh tools` — 90 (was 89).
  `bash ops/ralph/runtests.sh jv-hud-bridge` — 25.
  `bash ops/ralph/hudshots.sh` — the sheet regenerated, 8 shots, and the
  seven committed PNGs came back byte-identical, which is the evidence
  that a plate nobody fed changed nothing.
  `bash ops/ralph/hudscreens.sh` — the whole three-monitor sheet green
  end to end, because shell.qml changed: three outputs, the idle probe
  (0 commits quiet, 0 lit and still, 45 and 42 on its two controls) and
  the click probe all pass with the new plate in the stack. Its five
  PNGs were reverted: the diff was 3 to 12 pixels at a maximum channel
  difference of 1 — antialiasing noise, not content.
  Eight mutations, eight caught: the id match in `toolFor`, the
  confirm-outcome guard, the success branch, latch-time vs render-time
  tool resolution, the `ts` comparison in `noteExplained`, the `ok`
  boolean floor, the unhedged-`conf` floor, and the new privacy gate
  (an element reaching for `args`). A ninth bit for real without being
  planted: adding the plate to `shell.qml` failed
  `test_the_sheet_stacks_the_same_plates_the_shell_does` until the
  contact-sheet scene was updated too.
- build: `nix build .#jv-hud` ok (qmllint `-W 0` + 384 QML tests in its
  checkPhase), `nixos-rebuild build --flake .#ares` ok. Never
  test/switch. No schema change, no jv-act change, no boot path, no
  NVIDIA/kernel/flake pin touched.
- files: shell/jv-hud/core/ActionState.qml (new),
  shell/jv-hud/ActionPlate.qml (new),
  shell/jv-hud/tests/tst_actionstate.qml (new),
  shell/jv-hud/shell.qml, shell/jv-hud/README.md, shell/jv-hud/qmldir,
  shell/jv-hud/core/qmldir, tools/gen_theme_qml.py,
  tools/tests/test_gen_theme_qml.py, tools/hudshots/scene/tst_shots.qml,
  services/jv-hud-bridge/jv_hud_bridge/bridge.py, docs/hud/README.md,
  docs/hud/08-action.png (new)
- next: the HUD now draws seven plates and the questions about ALL of
  them are the same four a human has to answer by looking, which A38
  makes sharper rather than new — the failure line is the least
  ignorable thing to repeat across three screens. **A39** is the only
  new buildable item and it is deliberately gated: A22 answered "yes,
  say the word" is now one line in `apply()` and one entry in
  `reportableReasons`, with no timer and no new rule, which is the
  cheapest that question has ever been to answer. The B15 correction is
  the one thing in this entry a human should read before the next
  latency iteration. Human asks unchanged in number and now worth more:
  A13/A27/A38 together, A21/A22/A25 together, B10+A28+B17 together,
  B13/B15.

## 2026-09-24 — iteration 34 — A40: the HUD stops saying SPEAKING while
## the room is silent

Same ladder walk as iteration 33 and the same answer. Track A's open
items are still questions for a human (A13/A27/A38, A21/A22/A25, A31) or
gated on a signal that does not exist yet (A33, A35, A36, A39);
`docs/optimization-backlog.md` is human-review-required from top to
bottom, so it is still not the "non-human-review backlog item" the
ladder points at. So: the highest-value thing the HUD does not yet say.

The way to find it was to ask which frozen, actually-published topic the
HUD still does not read. There was exactly one that mattered —
`context.system`, jv-context's 1 Hz snapshot — and it carries the one
field pair that answers a question no other topic on this bus can:
**when the HUD says SPEAKING, is anything reaching the room?**

Because SPEAKING is a claim about jv-voice, not about the room. With the
default sink muted, jv-voice accepts the utterance, Piper synthesises
it, PortAudio plays it, `action.result` is clean, every service
heartbeats `ok`, and you hear nothing. There is no error anywhere in
that sequence. Of all the ways a voice assistant fails, this is the one
with the least evidence attached — and the HUD was showing a true frame
that added up to a false impression, which is the same failure shape
A26 (the HUD could not say what it heard) and A37 (it could not say
what it broke) were each written against.

`core/OutputState.qml` decides; `OutputPlate.qml` draws one line and
nothing else, directly under the word it qualifies. Four decisions are
the element:

  · **ONLY WHILE SPEAKING.** A muted machine is not news — it is a
    choice you made, probably on purpose — and a plate that nags about
    it all day is the opposite of §06's earned emptiness. It becomes
    news at exactly one moment. That is also why it sits under
    `StatePlate` rather than anywhere else in the stack: the two are one
    reading, the way HeardPlate is one reading with THINKING above it,
    and the contact sheet is the argument (`09-muted.png` — SPEAKING in
    ember, OUTPUT MUTED in warn, MIC underneath, one story top to
    bottom).
  · **SILENCE, NOT QUIETNESS.** `audio_muted` is silence by definition
    and so is `audio_volume` at zero. There is no threshold on "too
    quiet to hear", because that would be a guess about your speakers
    and your room, and it would put a plate on screen for a machine you
    deliberately turned down. The failure that leaves — a reply at 3% in
    a loud room — is at least one the user can reason about. And the two
    silences are two WORDS, OUTPUT MUTED and OUTPUT AT ZERO, because
    they are two different controls: one is a toggle and one is a
    slider, and a single "no sound" would send you to the wrong one half
    the time.
  · **THE RAW jv-voice WORD, NOT `SpeechState`'s.** SpeechState answers
    "what is Jarvis doing" and lets the microphone claim outrank the
    speaking one, so a barge-in reads as `listening` while jv-voice is
    still finishing its sentence. Right answer to its question, wrong
    input to this one: what matters here is whether an utterance is
    being played, which is `speech.state` verbatim.
  · **A LIVE READING, NOT A LATCH.** Every element built since A20 has
    been a memory of something the bus stopped carrying, with rules for
    letting go of it. Both inputs here describe the present, so there is
    nothing to forget: the line leaves the instant jv-voice stops
    speaking or the sink comes back. The only clock in the file exists
    to stop BELIEVING a frame, never to hide one — ONE timer on the
    earlier of two deadlines, because believing the pair is believing
    both. Three 1 Hz periods for the snapshot (the rate is stated by the
    schema itself, so it is not the hand-copied constant B7 warns
    about; three rather than two because jv-context is a Python process
    competing with CPU Whisper and an 8B prefill, and the moment it is
    late is exactly the moment this machine is busy). Thirty seconds
    under the `speaking` frame, as the backstop for a jv-voice that died
    mid-sentence and will never publish the `idle` that ordinarily ends
    this — without it, a muted machine would carry this plate until the
    next reboot, which is the one thing §06 will not have.

**The one assumption, written down where it will be found.** jv-voice
plays through `sd.play(audio, rate)` with no device argument, which is
PortAudio's default output — the same default sink jv-context reads with
`wpctl get-volume @DEFAULT_AUDIO_SINK@`. That is a routing assumption
and it is the only one in the file. The other direction is safe and
stays unreported: PipeWire can mute jv-voice's STREAM while the sink is
open, and that is a silence this element cannot see, so it under-claims
— the direction everything in `core/` errs in. Both halves are now A41.

**The new cost, measured rather than argued.** `context.system` is the
first NON-EVENT topic the bridge subscribes to: a frame every second,
forever, on a HUD whose entire design is to cost nothing while nothing
happens. A34 proved "0 fps when idle" off the HUD's own Wayland socket
six days' work ago, and the honest thing was to re-ask that question
with the new subscription live rather than to assert that an unmapped
surface cannot commit. So the idle probe's QUIET window stopped being a
bus with nothing on it and became a bus TALKING: six ordinary unmuted
snapshots over six seconds, every one of them reaching the HUD, not one
of them anything to draw. It read 0 commits, and both its controls still
bit (waking the HUD cost 45, the blind plate arriving cost 41). That
also makes the window less tautological than A35 found it — though only
a little, because the surface is still unmapped. The real prize A35 is
after is now closer for a different reason: see A42.

- tests: `bash ops/ralph/qmltest.sh` — 423 (was 384), 36 of them new.
  `bash ops/ralph/runtests.sh tools` — 90. `... jv-hud-bridge` — 25.
  17 mutations, 15 caught first time and BOTH survivors were real:
  (1) a `root.linked &&` term in `unheard` that no test could ever
  reach, because both readers already refuse a frame off a dead link —
  a third guard on top of two is a guard whose deletion is invisible, so
  it was removed and the gate now lives where the frame is read, once,
  with the pair pinned by a hand-made bus that hands out frames while
  `linkUp` is false; (2) the `typeof audio_muted !== "boolean"` check,
  which the strict `=== true` downstream makes behaviourally dead — what
  it really buys is that the frame is refused OUTRIGHT, so there is
  nothing to TIME either, and that is what the test now asserts.
  Worth recording as a limit: deleting the link gate from ONE reader is
  unobservable (the other one nulls the pair, and BusModel throws its
  frames away on link-down anyway), so only the pair is pinned.
  `bash ops/ralph/hudshots.sh` — 9 shots, and the eight committed PNGs
  came back byte-identical, which is the evidence that a plate nobody
  fed changed nothing. `bash ops/ralph/hudscreens.sh` — green end to end
  with the new plate in the stack and the new 1 Hz feed in the idle
  probe: three outputs, quiet (0 commits under 6 snapshots), lit and
  still (0), and all three click-through points. Its five PNGs were
  reverted — 6 to 33 differing bytes at a maximum channel delta of 1,
  which is antialiasing, not content.
- build: `nix build .#jv-hud` ok (qmllint `-W 0` + 423 QML tests in its
  checkPhase), `nixos-rebuild build --flake .#ares` ok. Never
  test/switch. No schema change, no jv-act change, no boot path, no
  NVIDIA/kernel/flake pin touched.
- files: shell/jv-hud/core/OutputState.qml (new),
  shell/jv-hud/OutputPlate.qml (new),
  shell/jv-hud/tests/tst_outputstate.qml (new),
  shell/jv-hud/shell.qml, shell/jv-hud/README.md, shell/jv-hud/qmldir,
  shell/jv-hud/core/qmldir, tools/gen_theme_qml.py,
  tools/hudshots/scene/tst_shots.qml, tools/hudscreens/sheet.py,
  tools/hudscreens/shoot.py,
  services/jv-hud-bridge/jv_hud_bridge/bridge.py, docs/hud/README.md,
  docs/hud/09-muted.png (new)
- next: the HUD now draws eight plates and every frozen topic anything
  actually publishes is read by one of them, so the "what does the HUD
  not say yet" seam this iteration and the last two mined is closed
  until a new producer exists. What is left on Track A is four questions
  a human answers by LOOKING (A13/A27/A38 now with a fourth instance,
  A21/A22/A25, A31, B17) and two new items this iteration created:
  **A41** (jv-voice's output path is assumed, not published — and the
  per-stream mute is a silence nothing on this bus can see) and **A42**
  (A40 hands A35 the first lit plate a harness can hold still on a LIVE
  bus, which is the measurement A35 said was worth building the day a
  second element could be held). A41 is the one a human should read
  first: it is the only place this plate could be confidently wrong.

## 2026-09-24 — iteration 35 — B16: `think` stops being one number over
## the model and the queue

Track A's ladder walk came out the same way it has for three iterations
running: every open UI item is either a question only a human at the
machine can answer (A13/A27/A38, A21/A22/A25, A31, B17) or gated on a
signal nobody publishes yet (A33, A36, A39) — and A42, the one genuinely
buildable Track A item this iteration inherited, is a measurement of the
HUD rather than a thing the HUD says. But the ladder itself settles it:
the last three iterations were all UI, so step 2 applies and this one
takes a feature. Of the open features, B16 is the only one whose
precondition ("publish the gauge when something reads it") is actually
met — the memory's standing NEXT TASK is the latency FAIL (5.4 s against
a 2.5 s budget), and PHASE1-STATUS names the model's generation as one
of the two spans still open. Today is the day someone reads it.

**What `think` actually was.** B14 split `respond` at the final
transcript into `hear` (jv-ears' ASR) and `think` (the brain), which was
enough to stop one number covering two services. It was not enough to
optimise either: `think` is the LLM's prefill and generation AND a bus
hop each way AND however long the transcript sat in jv-brain's input
queue behind whatever the worker was doing. A change to generation and a
change to queueing move the same number, and the table could not tell
them apart.

**Why this seam needed a publisher and hear/think did not.** B14's seam
was free: jv-ears runs whisper AFTER publishing `speech_end`, so the
final transcript already marked the handover. There is no equivalent
frame for "jv-brain issued the completion request" — nothing but
jv-brain can see that moment. So jv-brain states it, in the one place
that costs no schema change: `sys.health` `metrics`, free-form and
service-local by schema (invariant 2 intact), as `llm_first_say_ms` plus
a turn counter `llm_first_says`. The tap divides `think` into **model**
(request -> first `speech.say`: prefill and generation up to the first
sentence closing) and **wait** (the remainder: two bus hops, the queue,
and jv-brain's own pre-LLM work), and they partition it exactly the way
`hear` + `think` partition `respond`.

**Three refusals, which are most of the work.**

1. *A tool turn states nothing.* `TurnTiming` counts the completions a
   turn issued and hands back a number only for a turn that issued
   exactly ONE. A turn that called a tool spends real time in jv-act
   between its first completion and the words the user hears — a
   15-second confirm window, potentially — and that time is inside
   `think` and is not the model's. A `model` gauge with a confirm window
   in it is precisely the "a number stops meaning its label" failure B13
   was written against, so the gauge is simply absent and the table
   prints `think unsplit`, names the gauge it wanted, and says why.
2. *The gauge is bound by frame ORDER, not by a guess.* `sys.health`
   carries no `utterance_id` and adding one is a frozen-schema change.
   What makes the binding sound is that the gauge frame and the
   `speech.say` frame it measures leave jv-brain on the SAME connection,
   in that order — jv-brain heartbeats immediately after the first word
   — so a subscriber cannot see them out of order. The counter then
   distinguishes that fresh gauge from the identical number re-stated on
   every later periodic heartbeat, which a reader watching only the
   value would apply to the NEXT turn.
3. *The first count a tap sees is recorded and not consumed.* It may be
   restating a turn from before the tap connected. That costs the first
   turn of every tap its split, and the `n` column is what says so.

The `>>> turn` line itself is deliberately no wider. B17 is open on
nobody having read that line on a real turn — it is already six numbers
across — so the split prints as its own short second line when the gauge
lands, and the table (rows, not columns) carries the distributions.

- tests: `bash ops/ralph/runtests.sh jv-brain` — 57 (was 53), four of
  them new: `TurnTiming` in isolation, the gauge landing after a
  multi-sentence reply with the count NOT rising per sentence, three
  consecutive turns counting 1/2/3, a silent `brain.request` turn
  stating nothing, and a tool turn stating nothing. (The silent-turn test
  found its own premise wrong first time: `brain.request` defaults
  `speak` to TRUE, so the "silent" turn had been speaking.)
  `bash ops/ralph/cargotest.sh jarvisd` — 82 unit + 8 bus + 34
  integration (was 71 + 8 + 32). 18 mutations, 15 caught first time and
  all three survivors were real:
  (1) `model_ms >= 0.0` in `brain_split` was dead against the wire —
  `brain_first_say` already refuses a negative — but `brain_split` is a
  public entry point with a rule of its own, so it is pinned by a direct
  call rather than deleted (the opposite call to A40's, where both
  readers already refused and the third guard went);
  (2) when a new turn arrives with no measurable `think`, the previous
  turn must STOP waiting — otherwise the new turn's gauge divides the old
  turn, which is the same error the counter prevents one layer out;
  (3) a turn counter that never rose survived everything, because no test
  ran two turns through one jv-brain. That one mattered most: it would
  have left the split working on turn 1 and silently dead forever after.
  The integration test pumps whole turns through a real broker with a
  *stale* restatement deliberately valued differently from the fresh
  gauge, so a missing counter check is visible from outside the process.
- build: `nix build .#jarvisd` ok (its checkPhase runs the Rust tests),
  `nixos-rebuild build --flake .#ares` ok. Never test/switch. No schema
  change, no jv-act change, no boot path, no NVIDIA/kernel/flake pin.
- files: services/jv-brain/jv_brain/service.py,
  services/jv-brain/tests/test_turn_timing.py (new),
  services/jv-brain/tests/test_brain_service.py,
  services/jv-brain/tests/test_brain_tools.py,
  services/jarvisd/src/cli.rs, services/jarvisd/src/bin/jv.rs,
  services/jarvisd/tests/cli.rs, PHASE1-STATUS.md
- next: the turn table now names five spans a human can argue a budget
  about and every one of them is read off the bus. What it has never done
  is print on a REAL turn — B17 asked for one read-through and this
  iteration widened the output again (a second line per turn, two more
  rows), so B17 is now worth more, not less. The two new items this
  iteration created are **B18** (the same gauge would let `jv health`
  answer "is generation slow right now?", which is a second reader and
  the thing B7 says a gauge needs before it is published — jv-ears'
  `wake_refractory_s` and `suppress_tail_ms` are still waiting for
  theirs) and **B19** (a tool turn's `think` is now the one span with no
  decomposition at all, and `intent.action`/`action.result` already
  bracket the part of it that was jv-act's). A41 is still the item a
  human should read first: it is the only place the HUD could be
  confidently wrong, and the schema-legal half of its fix is the same
  shape as this one — except that a device NAME cannot ride `metrics`,
  which is numbers-only, so that half is smaller than it looks.

## 2026-09-24 — iteration 36 — A42: the idle probe gets a window on a live bus

**What.** A third window in `probe_idle_frames` (tools/hudscreens/shoot.py):
a plate on screen, a real broker, and a `context.system` snapshot arriving
every second for the whole six seconds. It reads **0 commits under 6
snapshots**.

**Why it was worth a whole iteration.** A34 measured invariant 10's one
cost claim — "0 fps when idle" — over two windows, and stated its own
limit in the plan the same day (A35): the only lit state a harness could
hold still was `LinkPlate` with **no bus at all**, because every other
thing this HUD says is a frame ageing out (a heartbeat speaks for two of
its own periods, a confirmation for the window jv-act declared). A HUD
that can see nothing has nothing arriving to make it re-render, so half
of that zero was a fact about the silence rather than about the shell.
The quiet window has the traffic and no plate; A34's lit window has the
plate and no traffic. Neither is the state the HUD is in on a running
machine.

A40's `OutputState` is the first element that can be both: a LIVE READING
of two topics rather than a latch, so it stays true for exactly as long as
the frames keep coming. One `speaking` from jv-voice (which does not
expire on its own) plus a muted snapshot at jv-context's own 1 Hz, and
SPEAKING + OUTPUT MUTED sit on screen indefinitely while the `seq` moves,
the expiry timer re-arms, and every binding downstream of the snapshot
re-evaluates — to the same values. A commit there is a re-render on
**bookkeeping**, and that is a way of spending §06's budget that neither
window above can see.

**Three decisions.**

1. *Lit in TWO steps.* "Something is drawn" was not the claim.
   `StatePlate` has said SPEAKING since A3 and lights on the jv-voice
   frame alone — so a window that only checked for pixels could be holding
   StatePlate still with OutputPlate never having appeared, and it would
   report the identical zero. So: an AUDIBLE sink first, then the mute, and
   the drawn region has to grow downwards. That is also the first time
   A40's decision (this line exists only while the sink is silent) has been
   checked through a compositor rather than in a QML test.
2. *The box before the count.* A plate that expired mid-window would have
   committed the traffic of LEAVING, and reporting that as "something in
   the shell is animating" would send the next reader hunting an animation
   that does not exist. So the region is re-measured first and the commit
   count is quoted inside that failure.
3. *Both boxes read after a settle.* §06's fade is a real animation and a
   region measured half way through one is smaller than the plate.
   Comparing two mid-fade boxes would make the growth check a coin flip.

**Two premises found wrong by running it.**

- The growth check first insisted the **top-left** corner stay put. It
  fails: the stack is docked to the top-right and `OUTPUT MUTED` is a
  longer line than `SPEAKING`, so the region widens leftwards by 32 px.
  The real invariant is top edge + RIGHT edge unmoved, bottom grown, left
  edge free to travel outwards.
- `feed_snapshots` was written as politeness and is load-bearing. A capture
  of a 2560x1440 screen plus a numpy compare is slow enough to outlast
  `OutputState.snapshotS` (3 s), so the *wait* loops have to keep feeding
  too or they watch the plate they are waiting for expire and then blame
  the element.

**Mutations — three, all three informative.**

- *Feed replaced with a plain `sleep`* → caught, on the BOX: it had shrunk
  back to `(2444,16,2543,48)`, SPEAKING alone. 28 commits, every one of
  them OutputPlate leaving. This is decision 2 earning itself.
- *Infinite `SequentialAnimation` on the dot's opacity inside OutputPlate*
  → caught, but by **A34's** lit window (143 commits arriving, 1113 in the
  window), not by the new one. An animation runs whether or not anyone can
  see it, so this is the failure the first two windows were already built
  for. Recorded because it is the obvious mutation to reach for and it
  proves nothing about A42.
- *A "freshness" fade* — the dot's opacity bound to `ageOf(snapshot)`.
  No animation, no timer, no loop: the binding re-runs only when a frame
  lands, which is once a second, forever, on any running machine. The
  drawn box never moves and every photograph is identical. **Quiet read 0.
  A34's lit window read 0. This one read 18** (three surfaces x six
  seconds). That is the whole justification for the window, and it is the
  kind of edit a reviewer would call considerate.

- tests: `bash ops/ralph/runtests.sh tools` — 96 (was 91); five new, and
  two of them are about the frames rather than the probe (both hand-written
  bodies are validated against `schemas/speech.state.json` and
  `schemas/context.system.json` for required/unknown keys and the state
  enum — a harness publishing an illegal body measures a machine that
  cannot exist). `bash ops/ralph/qmltest.sh` — 423, unchanged; no QML was
  edited, only mutated and reverted (md5 verified both ways).
  `bash ops/ralph/hudscreens.sh` — all three idle windows 0, the click
  probe and every photograph unchanged.
- build: `nixos-rebuild build --flake .#ares` ok. Never test/switch. No
  schema change, no jv-act change, no boot path, no NVIDIA/kernel/flake
  pin. `shell/` is untouched in the commit.
- files: tools/hudscreens/sheet.py (SINK_MUTED, VOICE_SPEAKING),
  tools/hudscreens/shoot.py (feed_snapshots, wait_for_drawing, the third
  window; the quiet window now uses the shared feeder),
  tools/tests/test_hudscreens.py, ops/ralph/hudscreens.sh,
  docs/hud/screens/README.md
- next: A35 asked for a lit-and-still measurement on a live bus and now has
  one, so what is left of it is the *other* plates — ConfirmPlate,
  HeardPlate, MicPlate and HealthPlate have still never been watched
  standing still, and `feed_snapshots` is most of the machinery for the two
  that a long `period_s` heartbeat would buy (**A43**). The second thing
  this iteration created is smaller and sharper: the live-lit window now
  holds a state nobody has photographed, and a 300x560 crop of SPEAKING
  with OUTPUT MUTED under it would be the one shot the screen sheet is
  missing for A40 (**A44**). A13/A27/A38 remain the oldest open question
  and are still one two-minute human opinion, answerable from
  `docs/hud/screens/02-heard-desk.png` without sitting at ares.

## 2026-09-24 — iteration 37 — A41: the plate stops assuming the sink it can see is Jarvis'

A40 put `OUTPUT MUTED` under `SPEAKING` and it reads the DEFAULT SINK.
That the default sink is what jv-voice plays into was true, and it was
true because I had read `player.py` — `sd.play(audio, rate)`, no device
argument, PortAudio's default, which under PipeWire is the sink
`wpctl get-volume @DEFAULT_AUDIO_SINK@` reports. That is knowledge a bus
consumer is not allowed to have (invariant 1), and the day anyone pins a
device the plate is a true statement about the wrong sink. A HUD that is
confidently wrong about why you cannot hear Jarvis is worse than the
empty corner it replaced.

**The fix is the shape A41 was corrected into while building B16** —
`sys.health.metrics` is `additionalProperties: {"type": "number"}`, so a
device NAME cannot ride it, but a 1/0 can, and whether the visible sink
is the relevant one is the whole of what the plate depends on. jv-voice
publishes `output_device_pinned` on every heartbeat including the
degraded ones; `OutputState` speaks only on the 0.

**The decision that took the most thought: unknown is not 0.** The
alternative — absence means "probably the default", which is what the
element assumed yesterday — keeps the plate working on a jv-voice too
old to publish, and that jv-voice ceases to exist with this commit. What
it costs is the whole point of the change: a plate that speaks about a
sink nobody said Jarvis uses. So silence from jv-voice, a v2 body, a
hedged beat, a missing `metrics`, a non-numeric gauge, a 2, and another
service's gauge on the same topic all leave the plate dark. The price is
a few seconds of quiet after a link is made, because a heartbeat is 5 s
away and nothing retains frames.

**The one asymmetry, stated in the file:** this gauge is NOT aged, and
the two frames either side of it are. It is jv-voice's *configuration*,
not a reading of the world; configuration does not rot sitting still,
and a restarting jv-voice heartbeats on its first loop pass. Expiring it
would hang a second, shorter clock on the plate (10 s, two `period_s`)
and hand the dead-jv-voice case to it — when `sayWindowS` (30 s) is the
backstop written for exactly that, and is tested. The link is the one
thing that does forget it.

**The harness taught me something back.** Adding jv-voice's beat ONCE to
A42's live-lit window passed the two-step box check — SPEAKING, then 41
px taller with OUTPUT MUTED under it — and then failed the measurement
it exists for: the box had grown again, to 130 px, with 37 commits under
it. `period_s` is 5, `HealthState` calls a service lost after two of its
own periods, and eleven seconds into the window `HealthPlate` arrived
under the plate being held still, saying *jv-voice lost*. Obvious
afterwards and I did not see it coming: A41 gave `OutputPlate` a second
publisher to satisfy, and a publisher the HUD is being told is SPEAKING
has to keep saying it is alive. The feed now carries the heartbeat with
the snapshot (1 Hz, faster than its own nominal period, which is what a
real service does under a state change) and the window reads 0 commits
in 6 s under 5 snapshots on TWO topics, at exactly the box it read
before A41.

**Verified end to end, not by construction.** Removing the beat from the
contact sheet's `09-muted` scene changes that PNG — the plate is gone —
and putting it back makes all nine shots byte-identical to the committed
ones. That is the gate proving itself through a QML engine; the
hudscreens window proves it through a compositor.

**Mutations — seven, all seven caught, one of them only after a new
assertion.** `unheard` dropping the `ownSink` term (9 fail); `ownSink`
reading unknown as "took the default" (6); the gauge read with
`latest("sys.health")` instead of `latestFrom(..., "jv-voice")` (1); the
degraded heartbeat dropping `metrics` (1); the player reporting pinned
and calling `sd.play` without the device (1); the empty env var read as
a pinned device (2). The seventh — deleting the `linked` guard from
`devicePinned` — **survived**, because `unheard` was already false: the
other two readers null the pair on a dead link, so the third guard is
unobservable from outside. The existing dead-link test says exactly that
about the first two and calls it fine. It is not fine once there are
three, so that test now also asserts `ownSink` directly, which is where
it *is* observable, and the mutation dies.

**Not done and why:** the other half of this failure is PipeWire muting
jv-voice's own STREAM while the sink is wide open — the same silence one
level down, one per-app slider away, invisible to a jv-context that
reads sinks. Seeing it needs two new optional `context.system` fields,
which is `schemas/**` and therefore human review. Written up as **R6**
in `docs/optimization-backlog.md`, including the shape I rejected
(jv-voice noticing its own stream: PortAudio hands it no node id, so it
would be jv-context's job done twice, badly, inside the synthesiser).
`OutputState`'s header states the gap in its own words.

- tests: `bash ops/ralph/qmltest.sh` — 435 (was 423; 12 new).
  `bash ops/ralph/runtests.sh jv-voice` — 27 (was 17; new `test_config.py`,
  two player tests, three service tests). `... tools` — 96, with three new
  assertions guarding the harness frames. `... jv-hud-bridge` — 25,
  unchanged (`sys.health` was already in `DEFAULT_TOPICS`).
  `bash ops/ralph/hudshots.sh` — 9 shots, byte-identical.
  `bash ops/ralph/hudscreens.sh` — all four idle windows pass, click probe
  unchanged.
- note: `docs/hud/screens/*.png` are NOT byte-reproducible. Three runs
  gave three different files, all differing from the committed ones by
  **2 pixels** inside the plate (antialiasing jitter), in `02-heard` and
  `03-confirm` — shots taken before anything A41 touched. Left as
  committed. A42's journal recorded them as unchanged, so this is either
  new nondeterminism or a coincidence that run matched; worth knowing
  before anyone treats that directory as a fixture (**A45**).
- build: `nixos-rebuild build --flake .#ares` ok, and `nix build .#jv-hud`
  (qmllint `-W 0` + the QML suite) ok. Never test/switch. No schema
  change, no jv-act change, no boot path, no NVIDIA/kernel/flake pin.
- files: services/jv-voice/jv_voice/{config,player,service,main}.py,
  services/jv-voice/tests/{test_config,test_player,test_voice_service}.py,
  shell/jv-hud/core/OutputState.qml, shell/jv-hud/tests/tst_outputstate.qml,
  shell/jv-hud/README.md, tools/hudscreens/{sheet,shoot}.py,
  tools/hudshots/scene/tst_shots.qml, tools/tests/test_hudscreens.py,
  docs/hud/README.md, docs/optimization-backlog.md
- next: the knob exists and nothing declares it — `JARVIS_VOICE_OUTPUT_DEVICE`
  is honoured by the process and absent from `modules/jarvis-services.nix`,
  so pinning a device today means editing a unit by hand, which is exactly
  the imperative mutation the NixOS discipline forbids (**A46**, small).
  A43 and A44 are both untouched and both still cheap, and A44 got cheaper:
  the live-lit window now composes SPEAKING + OUTPUT MUTED *and* holds it
  with a heartbeat, which is the entire frame list a `04-unheard` screen
  needs. A13/A27/A38 remain the oldest open question and are still one
  two-minute human opinion.

## 2026-09-24 — iteration 38 — A44: the screen sheet photographs the state
## where two plates disagree

A40 put `OUTPUT MUTED` under `SPEAKING` and A41 taught it which sink it
is allowed to say that about, and in neither iteration did anyone look
at the result on a monitor. It had a tile on the contact sheet — 300x560
of plain QML engine — and no SCREEN, which meant the one HUD state where
**two plates disagree about whether Jarvis is working** existed only as
a rendering of its own content. `docs/hud/screens/04-unheard-primary.png`
is that state on ares' 1440p panel, through quickshell, layer-shell, a
real bridge and a real jarvisd: SPEAKING in ember, OUTPUT MUTED under it
in warn, and 2560x1440 of untouched desktop around them.

**The shot needed a mechanism the sheet did not have.** Every other
picture here is of an EVENT — a wake word happened, jv-act asked — and
the plate it lights stands up on its own for longer than a camera takes.
`OutputState` is a reading of the PRESENT: it believes a
`context.system` snapshot for three of jv-context's periods, and the
jv-voice heartbeat that tells it the visible sink is Jarvis' lapses
after two of its own. So a shot may now declare `hold`, and the settle
becomes a feed at the 1 Hz jv-context publishes at all day.

**And then the hold turned out to be worth less than the argument for
it, which is the thing worth writing down.** Publishing the pair ONCE
and sleeping writes the same PNG, byte for byte: one exposure reaches
grim about two seconds after the publish and the snapshot expires at
three, so publish-once is inside the window — by under a second, on this
machine, with this shot's single capture. The feed is not what makes the
picture right today; it is what stops a sub-second margin from being the
thing that makes it right, and it is what survives a second monitor (a
33 Mpx grim and a PNG encode each), a slower run, a longer settle. Every
comment and paragraph that said "would photograph a plate that had
already left" was rewritten to say what was measured instead.

**The check that does bite: `grows_from`.** StatePlate has said SPEAKING
off jv-voice's frame alone since A3, so "the HUD drew something" is true
of a picture where A40's plate never appeared — and it would be a
perfectly sharp photograph under a caption describing a line that is not
in it. So the shot is exposed twice, the first one thrown away: the same
frames with an AUDIBLE sink, then the mute, and the drawn region must
have grown DOWNWARDS with its top and right edges unmoved. Measured:
(2444, 16, 2543, 48) → (2412, 16, 2543, 89), 41 px taller, the left edge
travelling outwards because OUTPUT MUTED is a longer line than SPEAKING.
**Verified it bites**: making the shorter exposure identical to the lit
one fails the run (exit 1) and — because the check was moved to before
`write_png` — leaves no PNG behind for the next reader to find looking
as finished as the others.

**The geometry rule is now stated once.** A42's live-lit window had it
inline as four index comparisons, and the shot needs exactly the same
one, so it is `sheet.grew_downwards()` — next to the frame counter, in
the stdlib-only file, where eight unit tests run it with no compositor
(taller, shorter, unchanged, top moved, right moved, left outwards, left
inwards, and None). The two tests that used to grep shoot.py for
`box[3] <= speaking_box[3]` now assert the window ASKS, and the rule
itself is tested rather than pattern-matched.

**A45, closed with numbers.** The claim it complained about — that
`docs/hud/screens/*.png` are a fixture — was already contradicted in
that README since A30, which is why nobody noticed it was load-bearing.
Now it is measured across three runs of an untouched HUD: `01-quiet`
(draws nothing) and `04-unheard` (two short monospace labels) come back
byte for byte every time; `02-heard` and `03-confirm`, the two shots
carrying a long wrapped sentence, move by 2-5 pixels per monitor, one
channel, one value, on glyph edges. A test now pins the disclaimer so it
cannot quietly leave. The five PNGs that drifted were restored to their
committed bytes: nothing about those shots changed this iteration, and a
diff of 2 px in each is noise in the history.

- tests: `bash ops/ralph/runtests.sh tools` — 104 (was 96; 8 new).
  `bash ops/ralph/hudscreens.sh` — 7 screens (was 6), run twice green
  plus two mutation runs into a temp directory.
- build: `nixos-rebuild build --flake .#ares` ok, and `nix build .#jv-hud`
  (qmllint + the QML suite) three times as part of the harness. Never
  test/switch. No schema change, no jv-act change, no boot path, no
  NVIDIA/kernel/flake pin. `shell/jv-hud` was not touched at all — this
  iteration photographs it, it does not change it.
- files: tools/hudscreens/sheet.py, tools/hudscreens/shoot.py,
  tools/tests/test_hudscreens.py, docs/hud/screens/README.md,
  docs/hud/screens/04-unheard-primary.png
- next: the growth check proves a plate ARRIVED and not WHICH plate
  (**A47**) — a HealthPlate saying `jv-voice lost` would grow the region
  in exactly the same direction, and only the picture distinguishes them,
  read by a human. A43 is still the other four plates standing still, and
  `hold` is now the mechanism for two of them. A46 (declaring
  `JARVIS_VOICE_OUTPUT_DEVICE` in `modules/jarvis-services.nix`) is
  untouched and still small. A13/A27/A38 remain the oldest open question
  and are still one two-minute human opinion — and `04-unheard` gives
  that human a fourth plate to have the opinion about.

## 2026-09-24 — iteration 39 — B18: `jv health --check` answers "is
## generation slow right now?"

Three iterations of HUD work in a row (A42, A41, A44), so this one is a
feature off PLAN.md instead — and the cheapest one on the board, because
the data was already on the wire and already in front of a reader that
was ignoring it.

B16 gave jv-brain a gauge, `llm_first_say_ms`, that says how much of a
turn's `think` was the model. It had exactly ONE reader: `jv tap
--latency`, which means the only way to ask how fast generation is right
now was to start a tap and then speak to the machine. `jv health
--check` already subscribes to `sys.health`, already reads jv-brain's
heartbeat by name, and already prints the rung off it. The gauge is on
that same frame. B7's rule — a gauge is worth publishing once a SECOND
reader wants it — is satisfied here for free.

**The number alone would have been a lie waiting to happen.** jv-brain
sets `_first_say_ms` once and never clears it, so every periodic beat
for the rest of the process's life re-states the same number. A reader
that printed it would answer "is generation slow right now?" with a
measurement that may be an hour old — a brain nobody has spoken to since
breakfast reading as one that just took 412 ms. That is a number quietly
stopping meaning what its label says, which is the failure this whole
CLI is written against, and it is why B18 was written as a wording
problem rather than a plumbing one.

**The age is the load-bearing half, and it comes off the count.**
`llm_first_says` rises once per measured turn, so a window of heartbeats
can say one of two things and must say which: the count ROSE while we
listened, so the turn is the frame that raised it and its age is a
measurement (`turn_age=1.5s`); or it never moved, so the turn predates
the first brain heartbeat we read and the only honest statement is a
LOWER BOUND (`turn_age>=6.0s`). The `>=` is the whole feature. A reader
deciding whether the number describes right now needs to see, in the
line itself, whether it is a reading or a bound.

**Three more refusals, each with a test that fails without it.** The
FIRST count a window sees is recorded and never treated as fresh — it
may describe a turn from before `--check` connected, which is the same
rule the tap loop already follows for the same reason. A count going
BACKWARDS is jv-brain restarted (the counter starts at 1 again), not a
newer turn, so the window starts over on it rather than reading a
smaller number as progress. And a readable heartbeat that stopped
carrying the gauge takes the number with it, because "the newest thing a
service said wins" is already the rule the report follows when the
newest frame is unreadable, and keeping a superseded reading alive would
be this instrument inventing a measurement that is no longer on the
wire. Two more shapes are pinned: the gauge is worth a line on its own
(`llm rung=? backend=? first_say=412ms turn_age>=1.0s` — a brain that
has not said which rung it picked has still said how long its last turn
took), and it never outlives its heartbeat, because a `lost` brain
prints no llm line at all.

**`turn_age`, not "idle".** A turn that ran TOOLS publishes no gauge —
tool time, confirm window included, is inside `think` and is not the
model's — so the last MEASURED turn can be older than the last turn. The
field name is the only place that distinction fits on one line; the doc
comment carries the rest.

**The integration test taught me its own premise.** First version
started the brain pump and the reader at the same moment and asserted an
exact age; it printed `turn_age>=0.6s` and failed, correctly — the
reader had never seen the count before the rise, so the rise was its
first reading. The pump now holds a steady count for 0.6 s of a 1.2 s
window and rises inside it, and the helper's doc comment says why,
because the obvious way to write that test proves the opposite of what
it claims.

- tests: `bash ops/ralph/cargotest.sh jarvisd` — 89 lib + 8 bus + 36 cli
  (was 84+8+34; 7 new). Five mutations run through them, all caught:
  first-count-is-fresh, a backwards count counted as a new turn, a
  gauge-less beat keeping the old number, the exact age measured off the
  wrong frame, and the bound printed as a reading.
- build: `nix build .#jarvisd` ok, `nixos-rebuild build --flake .#ares`
  ok. Never test/switch. No schema change (`metrics` is free-form and
  service-local, same as B16), no jv-act change, no boot path, no
  NVIDIA/kernel/flake pin, no HUD change.
- files: services/jarvisd/src/cli.rs, services/jarvisd/tests/cli.rs,
  PHASE1-STATUS.md
- next: **B20** — nothing has read this line on a real turn either, which
  is the same complaint B17 makes about `>>> turn`, and both are now
  waiting on the same two minutes of a human's attention at a terminal.
  B19 (dividing a tool turn's `think`) is unblocked by none of this and
  still wants B17 answered first. A46 (declaring
  `JARVIS_VOICE_OUTPUT_DEVICE` in `modules/jarvis-services.nix`) is
  still the smallest untouched item on the board. A43 is still the four
  plates nobody has watched stand still, and A47 still says the growth
  check proves a plate arrived and not which one.

## 2026-09-24 — iteration 40 — A43: the mic and health plates get watched
## standing still

A42 was the first time "0 fps with a plate on screen" was measured on a
HUD that could see a live bus, and it could only be done with one pair of
plates. Every lit state in this HUD is a frame ageing out — a heartbeat
speaks for two of its own periods, a confirmation for the window jv-act
declared — and `core/OutputState.qml` is the one element that is a
READING of the present rather than a latch, so it stays true for exactly
as long as the harness keeps feeding it. That left four plates nobody had
ever watched stand still, which is what A43 was opened for.

**A35 had already named the cheap half and it is cheaper than it looks.**
One `jv-ears` heartbeat describing a device that is OPEN and delivering
NOTHING says two things at once: `MIC NO AUDIO`, because
`core/MicState.qml` compares `capture_age_s` against jv-ears' own
`capture_stall_s` budget, and `jv-ears DEGRADED`, because that is the
word the service uses about itself when its capture stalls. Two plates,
one frame, one publisher. Re-publish it at 1 Hz and both sit there. A35
thought this needed a heartbeat with a long `period_s`; it does not —
jv-ears' real 5 is long enough, and faking a period would have been a
picture of a machine that does not exist.

**Lit in two steps, for A42's reason.** `MicPlate` lights off the first
heartbeat alone, so "the HUD drew something" would be true of a window
holding MicPlate while HealthPlate never appeared — and it would report
exactly the same zero. So: a healthy jv-ears with the device open
(MicPlate alone), then the device goes silent, and the drawn region has
to grow DOWNWARDS through `sheet.grew_downwards`. 41 px, the same number
A44 measured for OutputPlate, which is what one more plate costs in this
stack. A47's complaint applies here unchanged and is not answered: the
measurement proves a plate ARRIVED and not WHICH one.

**One guard the other three do not have, and it is window 3's inverted.**
OutputState stops believing a snapshot after three of jv-context's
periods, so window 3's feed is life support — stop it and the plate
leaves and the box check fails loudly. A heartbeat speaks for two of its
own `period_s`, so these two plates outlive a six-second silence on their
own. The feed here is the SUBJECT, not the life support, which means a
feed that stopped would leave the photograph intact, pass every other
check, and quietly turn this back into A34's lit window. So the
heartbeats published inside the window are counted and fewer than two is
a failure. Worth being plain about the limit: what this really rules out
is a deliberate edit, because the run-up alone (two settles and two
waits) is past ten seconds, so a feed that never ran at all already fails
on the box.

**A prediction that was wrong, kept rather than deleted.** The window was
built expecting it to FAIL. `HealthPlate` renders a list;
`core/HealthState.qml` rebuilds its roster into a fresh JS array on every
heartbeat; a `Repeater` told its model changed rebuilds its delegates —
and that would be a frame on three surfaces, once a second, forever, to
draw exactly what was already there. It reads 0. That churn is real and
happens on any machine with a degraded service, and it costs no commit.
Nothing had to be fixed. The hypothesis stays in the failure message,
where it is the first thing a future reader should check, and the README
says it was measured and disproved.

**So the window was made to prove it bites.** The mutation is A42's
"freshness" fade moved to the one plate only this window can hold: the
mic dot's opacity bound to the age of jv-ears' heartbeat. No animation,
no timer, re-running once a second forever — the considerate edit nobody
looks at twice. Windows 1, 2 and 3 read 0 (MicPlate is dark in all three:
window 2 has no bus, window 3 is holding SPEAKING and OUTPUT MUTED) and
this one read 18, three surfaces times six seconds, with the drawn box
unmoved and the photographs identical.

**The gates needed tightening before they could be trusted.** They are
greps over `probe_idle_frames`, and several were written as "somewhere
after the words LIVE AND LIT" — `feed_snapshots(` is there, a broker is
started, a growth check exists. A fourth window that also starts a broker
and also feeds would have started satisfying those on window 3's behalf,
silently. `idle_window_text()` now slices one window out by its own
`# --- TITLE:` banner and raises if the banner is gone.

- tests: `bash ops/ralph/runtests.sh tools` — 110 (was 104; six new),
  `bash ops/ralph/qmltest.sh` — 435 (unchanged; no QML was edited),
  `bash ops/ralph/hudscreens.sh` — all four idle windows 0, seven screens
  written. Run three times end to end: baseline before the change, with
  the change, with the mutation.
- build: `nixos-rebuild build --flake .#ares` ok. Never test/switch. No
  schema change, no jv-act change, no boot path, no NVIDIA/kernel/flake
  pin, and no change to `shell/jv-hud` at all — this iteration only adds
  an instrument. `docs/hud/screens/*.png` are deliberately NOT
  regenerated: the HUD did not change, and A45 measured that re-running
  the harness moves a handful of pixels for no reason a reader could use.
- files: tools/hudscreens/sheet.py, tools/hudscreens/shoot.py,
  tools/tests/test_hudscreens.py, docs/hud/screens/README.md,
  ops/ralph/hudscreens.sh
- next: **A48** — `ConfirmPlate` and `HeardPlate` are the two plates left,
  and both are latches with a clock, so holding one still means either a
  frame carrying an implausibly long window or a re-publish that may
  simply re-latch. Neither is known; A43 did not try. A46 (declaring
  `JARVIS_VOICE_OUTPUT_DEVICE` in `modules/jarvis-services.nix`) is still
  the smallest untouched item on the board. A47 is unchanged and now has
  a second instance: two growth checks prove a plate arrived and neither
  can say which. B20 and B17 are still both waiting on the same two
  minutes of a human's attention at a terminal.

## 2026-09-24 — iteration 41 — A48: the two plates whose words come off a latch get watched standing still

**The cheap first step was the whole risk, so it went first.** A48 was
written as an open question rather than a task: `ConfirmState` and
`HeardState` are latches with a clock, and the two obvious ways to hold
one still were both unknown. Publishing an implausibly long window would
have worked and would also have been a frame no jv-act sends.
Re-publishing at 1 Hz might simply re-latch and re-run the fade, in which
case the window would be measuring a plate arriving over and over and
would be right to fail. The item said: read the two elements and write
down what a repeated frame does, before building anything.

It does re-take the latch. `publish_shot` stamps a fresh `ts` on every
frame — which is what a live publisher does — so `requestKey` and
`transcriptKey` move on every re-publish, `armExpiry`/`armHold` run,
`expired` is cleared again and a one-shot timer restarts. What it does
NOT do is re-run the fade, and the reason is worth keeping: both arming
functions clear `expired` before anything downstream reads it, and
`pending`/`heard` are conjunctions that never go false in between. The
strings the plates draw re-evaluate to the same strings, and QML does not
signal a string property that did not change. So the plate can be held
still, and the re-taking of the latch IS the subject of the window.

**Which is a failure the other four windows cannot see.** They hold five
plates and every one of them is a READING: `OutputState` believes a
snapshot while the snapshots keep coming, `MicState` and `HealthState`
read the heartbeat in front of them. Nothing above this window has a
latch in it at all. A plate that did anything visible when its latch was
re-taken would cost a composite of three monitors for as long as the
question stood, and windows 1-4 would all report a flawless zero.

**The mutation is not an invented temptation.** A21 is an open item
asking this exact plate to show how much of the answer window is left, so
the mutation is that edit in its most considerate form: the CONFIRM dot's
opacity bound to the age of jv-act's question. No animation, no timer;
the binding re-runs only when a frame lands, which is once a second for
as long as a question stands. `ConfirmPlate` is dark in every other
window — nothing above publishes an `action.confirm` at all — so windows
1, 2, 3 and 4 read 0 and the fifth read 15, three surfaces times five
re-publishes, with the drawn box unmoved at (2284, 16, 2543, 178) and the
photographs identical.

**The refusal is written into the frame.** `ConfirmState` arms its expiry
off the window the FRAME declares (A14's rule), so publishing
`window_s: 600` would have held the plate up for ten minutes, made the
feed decorative and the measurement easy. It would also be a picture of a
machine that does not exist — the same thing A43 refused to do to a
heartbeat's `period_s`. The harness publishes jv-act's own 15 s, and a
test pins that number against `schemas/action.confirm.json`'s own
description so the two cannot drift. The cost of the refusal is that both
latches outlive a six-second silence on their own (15 s and 30 s against
a window of 6), so this needs A43's guard rather than A42's: the
re-publishes inside the measured window are counted and fewer than two is
a failure, because a dead feed would otherwise leave both plates exactly
where they are and report a perfect zero about an idle bus.

**The transcript is composed, and says so.** The committed recording's
final asks what time it is, and nothing destructive follows from that, so
replaying it under an `fs.trash` confirmation would have put two true
frames on the bus that add up to a machine which had confused itself.
These two are one turn — the words, and the question they earned. The
envelope `conf` is borrowed rather than invented: 0.88583 is that
recording's own final from a quiet room, because invariant 4 wants a
number there and a composed 1.0 is a certainty no ASR reports.

**One thing got tidier on the way.** `03-confirm` carried its own inline
copy of the confirmation frame and the new window needed the same one;
two copies drift, and the side that drifts is the one nobody is looking
at. Both now read `sheet.CONFIRM_REQUEST`, pinned by a test that counts
the copies.

- tests: `bash ops/ralph/runtests.sh tools` — 117 (was 113; nine new, and
  four existing counts updated for the fifth window),
  `bash ops/ralph/qmltest.sh` — 435 (unchanged; no QML was edited),
  `bash ops/ralph/hudscreens.sh` — all five idle windows 0, seven screens
  written. Run four times end to end: baseline before the change, twice
  with the change, once with the mutation (exit 1 on the fifth window),
  and once more after reverting it.
- build: `nixos-rebuild build --flake .#ares` ok. Never test/switch. No
  schema change, no jv-act change, no boot path, no NVIDIA/kernel/flake
  pin. `shell/jv-hud` is byte-identical to its parent commit — the
  mutation was applied to `ConfirmPlate.qml`, measured, and restored from
  a copy. `docs/hud/screens/*.png` are deliberately NOT regenerated: the
  HUD did not change, and A45 measured that re-running the harness moves
  a handful of pixels for no reason a reader could use.
- files: tools/hudscreens/sheet.py, tools/hudscreens/shoot.py,
  tools/tests/test_hudscreens.py, docs/hud/screens/README.md,
  ops/ralph/hudscreens.sh
- next: **A49** — `ActionPlate` is now the only plate in the stack that
  has never been watched standing still, and it is a latch with a 30 s
  hold exactly like `HeardState`, so A48 has already proved the mechanism.
  The open question is whether it earns a sixth window or belongs inside
  the fifth, where the story already runs the right way (jv-act asked, the
  answer was no, the tool failed) and the growth check has a third step to
  make. A47 is now three instances rather than two: three windows and the
  shot loop all prove a plate ARRIVED and none can say which. A46
  (declaring `JARVIS_VOICE_OUTPUT_DEVICE` in `modules/jarvis-services.nix`)
  is still the smallest untouched item on the board. B20 and B17 are still
  both waiting on the same two minutes of a human's attention at a
  terminal.
