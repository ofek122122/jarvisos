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

## 2026-09-24 — iteration 42 — A49: the last plate gets watched standing
still, and the turn gets an ending

`ActionPlate` was the only plate in this HUD that had never been held
still and measured. Five idle windows hold seven plates between them and
not one of them publishes an `action.result` at all, so the last one was
out of reach of the whole probe.

**The decision A49 was opened to make was about cost, and the answer was
no sixth pair of processes.** A window per plate is how a probe stops
being a measurement and starts being a fixture, and a sixth jarvisd plus
a sixth jv-hud would have bought nothing but a longer run. So this is the
same broker, the same shell and the same TURN as A48's window, carried to
its end: the user asked for the downloads folder to be emptied, jv-act
stopped in front of the tool, and now the user answers and the tool
fails. The probe still starts exactly five shells, and the test that
counts `WAYLAND_DEBUG` pins that — the two gates hold each other up.

**Running the story forward is what earned the new step.** An
`action.result` landing while `ConfirmPlate` still stood would be jv-act
reporting a tool it was still asking permission to run, and
`ConfirmState` would hold that question up perfectly happily — it lets go
for an answer naming its own `request_id`, or for its 15 s, and for
nothing else. So the answer goes on the bus first and the drawn region
has to SHRINK: `sheet.grew_downwards` read with its arguments swapped,
which says the stack with the question on it was taller at the same
top-right corner. Nothing in this harness had ever measured a plate
LEAVING. It lands on (2284, 16, 2543, 84) — the box the heard line held
before it was asked, to the pixel — and the failure then arrives 78 px
taller at (2284, 16, 2543, 162) for 36 commits.

**The re-publish does one thing more here than it does in A48's window.**
Re-taking `HeardState.transcript` replaces an envelope, moves a key and
re-arms a one-shot timer. Re-taking `ActionState.failure` does all of
that AND re-runs `toolFor()`, which reaches back to the `intent.action`
still on the bus, compares its `request_id` and re-resolves the tool name
from scratch — once a second, forever, arriving at the same string. No
window above has a binding that reads a SECOND topic every time the first
one arrives. Measured: 0 commits in 6 s under 5 re-publishes.

**Mutated, because a window that passes on zero is a window every broken
instrument also passes.** The considerate edit, moved to the one plate
only this window has ever held: the ACTION FAILED dot's opacity bound to
the age of the failure. No animation and no timer — the binding re-runs
only when the latch is re-taken — and it passes qmllint and builds
cleanly, which is the point of choosing it. Windows 1-5 all read 0 and
the sixth read 18, with the drawn box unmoved. The mutation was applied
to `ActionPlate.qml`, measured, and restored from a copy;
`shell/jv-hud` is byte-identical to its parent commit.

**An honesty debt got paid on the way, and it is the more interesting
half of this iteration.** `fs.trash` is not in jv-act's registry.
`services/jv-act/tools.toml` is v0 — "observe + benign only" — the
confirmation rule is structural (only destructive and privileged tools
are ever confirmed), and so there is no tool on this machine today that
could produce an `action.confirm` at all. Asked for `fs.trash`, the real
jv-act answers `unknown_tool` before it asks anybody anything. That has
been true since A20 composed the frame, and the sheet's own comment
claimed "every number in it is jv-act's own" without mentioning that the
tool is not. The composition is still worth making — the thing under test
is the confirmation MACHINERY, which is built, reviewed and structural,
and registry v0 says the destructive tools "arrive in later phases with
their own review" — but leaving it unsaid is what made it dishonest. It
is now written under `CONFIRM_REQUEST`, and a test fails if the
disclaimer leaves OR if the registry gains the tool and makes the
disclaimer wrong (its message tells the reader to delete the paragraph).

**Four frames of one turn, one id.** `TURN_REQUEST_ID` replaces four
copies of `req-4f21`, because `schemas/intent.action.json` says in as many
words what the id is for — it threads intent → confirm → result — and a
drifted one is a question that never closes and a failure with no name. A
test asserts the four carry it and that the intent's `utterance_id` is
the transcript's own, so the window cannot quietly photograph two
unrelated turns stacked on each other.

`intent.action.args` carries `{"path": "~/Downloads"}` deliberately. It
is the most sensitive body the bridge forwards, no element reads it, and a
tools gate fails the build if one starts to — a frame with a real-looking
path in it is the only way this harness exercises that claim at all. Same
for `detail` on the result.

- tests: `bash ops/ralph/runtests.sh tools` — 125 (was 117; nine new, and
  several existing counts updated for the sixth window),
  `bash ops/ralph/qmltest.sh` — 435 (unchanged; no QML was edited),
  `bash ops/ralph/hudscreens.sh` — all six idle windows 0, seven screens
  written. Run twice end to end: once with the change, once with the
  mutation (exit 1 on the sixth window), then the mutation reverted.
- build: `nixos-rebuild build --flake .#ares` ok. Never test/switch. No
  schema change, no jv-act change, no boot path, no NVIDIA/kernel/flake
  pin. `shell/jv-hud` is byte-identical to its parent commit.
  `docs/hud/screens/*.png` deliberately NOT regenerated: the HUD did not
  change, and A45 measured that re-running the harness moves a handful of
  pixels for no reason a reader could use.
- files: tools/hudscreens/sheet.py, tools/hudscreens/shoot.py,
  tools/tests/test_hudscreens.py, docs/hud/screens/README.md,
  ops/ralph/hudscreens.sh
- next: **A50** is the question A49 just exposed and could not answer
  inside its own scope: jv-act's registry has NO destructive tool, so the
  entire confirmation path — `ConfirmPlate`, `ConfirmState`, jv-act's
  window, the yes/no classifier, `03-confirm`, two idle windows — is
  exercised only by composed frames, and has never once been driven by
  the registry this machine actually deploys. That is a human-review item
  (adding a destructive tool is a `services/jv-act/**` change and
  GUARDRAILS forbids touching it), so it belongs in
  `docs/optimization-backlog.md` as a proposal rather than in Track A.
  A47 is now four instances rather than three: four windows and the shot
  loop all prove a plate ARRIVED and none can say which — and A49 adds
  the mirror, a check that proves something LEFT and cannot say what.
  A46 (declaring `JARVIS_VOICE_OUTPUT_DEVICE` in
  `modules/jarvis-services.nix`) is still the smallest untouched item on
  the board. B20 and B17 are still both waiting on the same two minutes
  of a human's attention at a terminal.

## 2026-09-24 — iteration 44 — A51: the machine gets a face for the one
## time it says no to you

Two things in this entry, and the second one is bookkeeping the previous
iteration owed and did not pay.

**A46 was built, verified and committed in iteration 43 (61f26a4) and
never journalled, never marked done in PLAN.md, and never pushed.** The
loop's own memory is this repository, so an undocumented commit is a
thing that happened to a machine nobody can ask about later. The work
itself is sound and its verification is recorded in the commit message:
`jarvis.voice.outputDevice` is the repo's first NixOS option, the module
grew an `options`/`config` split to hold it, the empty string is refused
by an assertion because jv-voice reads an empty variable as "no device",
and `ops/ralph/nixtest.sh` is new machinery — seven cases, each one a
`nix eval` of an `extendModules`-overridden ares that greps the GENERATED
UNIT TEXT, so no case can pass because of how an option happens to be
expressed. Four mutations were run through it. The toplevel derivation
path was unchanged from its parent commit, which is the strongest thing
that can be said about a knob with a null default: it adds an option to
ares and not a byte to what ares would boot. PLAN.md marks it done below;
nothing about it was re-litigated here beyond re-running the build.

**A51 is the iteration's own work: the HUD can now say that this machine
refused to run a program.** Invariant 8 — Windows binaries are untrusted
by default, jv-guard screens every one before jv-compat builds a prefix —
makes that screening the only moment in JarvisOS where the machine says
NO to something its user asked for. It was the one moment with no pixels:
a `guard.verdict` on the bus, jv-compat failing closed in a terminal, and
a HUD showing the same empty corner it shows for a machine nobody has
asked to install anything. jv-guard is a real system unit on ares
(`modules/jarvis-services.nix`), so this plate is reachable today by
running `jv-compat install` on something a scanner objects to — it is not
a picture of a future phase.

`core/GuardState.qml` decides and `GuardPlate.qml` draws BINARY BLOCKED
in `risk` — that verdict is final — or BINARY SUSPICIOUS in `warn`,
because the confirmation flow may still override that one, over the
file's own name. What is NOT on it took as much deciding as what is:

**No reasons.** "matched ClamAV signature Win.Trojan.Agent" is in every
frame this element reads and on none of its pixels, because
`schemas/guard.verdict.json` says in as many words that the reasons are
"spoken on request". They are also the only text on this topic written by
a scanner rather than fixed by a schema, which is exactly the line
ActionPlate draws when it renders `execution_failed` and never jv-act's
free-text `detail`. A glance says a file was refused and which one;
asking why is what your voice is for.

**The name is sanitised, and that is the part of this element that is not
a copy of ActionState.** Every other string this HUD draws was chosen by
a service (a tool name, a state word) or by the user's own mouth (the
transcript). A file name was chosen by whoever built the installer, which
invariant 8 says outright is untrusted — and a Linux file name may carry
newlines (a plate three lines tall on a surface that floats over every
window), a bidirectional override (`setup<U+202E>exe.bat` renders as
`setup.bat` and is not), or four kilobytes of nothing. `plainName()`
collapses whitespace FIRST — a newline is a word boundary as well as a
control character, and stripping first would join two words its author
separated — then removes C0/C1, the zero-width marks and the bidi
overrides, then caps the length. A name with nothing left of it is
reported as NO name, which falls back to the first 12 hex of the sha256,
labelled as a hash: the identity jv-guard's own log uses and the only
thing about a file that may ever leave this machine (invariant 7).

**No spoken exit, on purpose.** ActionState lets go of a failure when
Jarvis starts explaining it, and copying that here would have been wrong:
a verdict is not part of a voice turn — the trigger is `jv-compat
install` at a terminal — so a `speaking` frame landing after one is
almost certainly about something else, and an unrelated sentence would
take the refusal off the screen. The 30 s hold is therefore the ORDINARY
exit here rather than a backstop, which is the one place this element
leans on a timer where its siblings lean on a signal, and it is written
down as such. The other two exits are the family's: a newer verdict
(including a clean one — the element reports the LAST binary screened, so
holding a refusal under a later screening would describe a machine that
is not the one in front of you), and the link dropping.

That last one produced the only mutation that survived the first pass.
`refused` is gated on `linked`, so an element that merely stopped
REPORTING on a dropped link looks identical to one that FORGETS — until
the bridge reconnects, BusModel comes back with an empty cache, and a
latch nobody let go of puts a verdict back on screen that nothing on the
bus is saying any more. A test for the reconnect was written and the
mutation dies.

The surface box grew 560 → 624. Unlike LinkPlate's growth (which can
never share the surface with anything) this one is about genuine
co-occurrence: a refused install says nothing about whether a service is
unwell or the microphone is open, so all of it can be on screen at once.
Three other files carry that number — both shot harnesses and the
sheet's README — and `tools/tests/test_hudscreens.py` pins the measuring
one to shell.qml's binding. Also corrected while in there: shell.qml's
"what it shows today" list had been missing `ActionPlate` since A37.

- tests: `bash ops/ralph/qmltest.sh` — 476 (was 435; 41 new), with TEN
  mutations run through them: a clean verdict reported like any other
  (3 fail), the name drawn as its author typed it (6), the length cap
  gone (1), a word outside the enum read as a verdict (1), a dropped link
  that keeps the refusal (1, after the reconnect test was added — 0
  before it, which is why it was), the hash shortened whatever it is (2),
  the hash left in whatever case it arrived in (1), the backstop never
  firing (4), a late frame treated as fresh (1), the envelope floor
  dropping the schema version (3). All ten reverted.
  `bash ops/ralph/runtests.sh tools` — 125, `... jv-hud-bridge` — 25.
  `bash ops/ralph/hudshots.sh` — 10 shots (all rewritten at the new box
  height; `10-guard.png` is new). `bash ops/ralph/hudscreens.sh` — 7
  screens, every window and probe green against the REAL `.#jv-hud` that
  now carries this plate. The six screens that moved are A45's documented
  2-5 px glyph drift, committed because the shell genuinely changed.
  One process note worth keeping: the first hudscreens run reported
  nothing wrong while its `nix build .#jv-hud` had FAILED, because the
  new files were untracked and nix builds the git tree — the failure was
  hidden by piping the script into `tail`, which ate its exit status. Run
  the gates unpiped, or `git add -N` first.
- build: `nix build .#jv-hud` ok (qmllint `-W 0` and the QML suite both
  run in its checkPhase), `nixos-rebuild build --flake .#ares` ok — twice,
  once on the parent commit as a baseline and once on this work. Never
  test/switch. No schema change, no jv-act change, no boot path, no
  NVIDIA/kernel/flake pin.
- files: shell/jv-hud/core/GuardState.qml (new),
  shell/jv-hud/GuardPlate.qml (new),
  shell/jv-hud/tests/tst_guardstate.qml (new), shell/jv-hud/shell.qml,
  shell/jv-hud/qmldir, shell/jv-hud/core/qmldir, tools/gen_theme_qml.py,
  tools/hudshots/scene/tst_shots.qml, tools/hudscreens/sheet.py,
  tools/hudscreens/shoot.py, ops/ralph/hudscreens.sh,
  services/jv-hud-bridge/jv_hud_bridge/bridge.py, docs/hud/README.md,
  docs/hud/*.png (10), docs/hud/screens/*.png (6)
- next: **A52** is what this element could not answer inside its own
  scope: GuardPlate says a binary was refused and jv-compat's whole
  lifecycle (`compat.install`) is on the bus unread, so the HUD cannot
  say a prefix build FAILED, or that an install it showed a refusal for
  was abandoned — and `compat.install.app` is the slug a reader would
  recognise where the HUD currently shows a file name. One topic, one
  element, and the same join discipline ActionState uses (`sha256` threads
  the lifecycle to its verdict). **A53** is the mirror of A47 for this
  plate: nothing but a human eye can tell `10-guard.png` apart from a
  picture of `ActionPlate`, and the growth checks in the screens harness
  would say the same thing about both.
  A50 (a destructive tool in jv-act's registry, human review) and A47
  (four windows that prove a plate ARRIVED and cannot say which) are
  unchanged. B20 and B17 are still waiting on the same two minutes of a
  human's attention at a terminal.

## 2026-09-24 — iteration 45 — B19: `think` stops being one number

UI was the last three iterations (A51, A49, A48), so the ladder sent this
one to a feature. Track B is mostly drained by human-shaped blockers —
B20/B17/B15 all want the same two minutes of a person at a terminal, B12
wants `sys.roster`, B10 wants a live recording, B7 says explicitly not to
publish a gauge nobody reads — and B8's premise turned out to be FALSE
(see below). B19 was the one item whose data was already on the bus.

What it is. `jv tap --latency` splits a voice turn into spoke / hold /
hear / think, and `think` — the final transcript to the first spoken word
— was the only span with no decomposition at all. It is also the longest
one a user can actually hit, because a confirmation window is 15 s by
design and sits entirely inside it. Worth being precise about why that
matters: jv-act publishes the confirm question to `action.confirm`, which
goes to the HUD's ConfirmPlate and is NEVER SPOKEN, and jv-brain holds its
sentences back while a tool call is open. So the whole window lands before
the first `speech.say` and is today indistinguishable from a slow LLM.

The seam was free. jv-brain publishes `intent.action`, jv-act answers
`action.result`, `request_id` threads the two, and the request carries the
input `utterance_id` — no new publisher, no schema change, exactly the
shape `hear`/`think` already had. `Utterances` grew `acted()`/`act_done()`
and a `request_id -> utterance_id` map, which is the one structure here
not keyed by utterance and is therefore swept when a turn is evicted.

The measurement is the UNION of the round trips. Not the sum: two requests
outstanding at once are one moment of jv-act's time, and summing could
produce a `tool` larger than the `think` containing it. Not the bracket
from first request to last result either: jv-brain runs a completion
between serial calls and charging jv-act for it would be the "a number
stops meaning its label" failure B13 was written against.

Five refusals, each with a test. An unanswered request (ran for a length
nobody can state; reporting only the answered ones would look complete
while being short). A round trip that runs backwards, starts before the
ASR seam, or ends after the first word — the same "two numbers that
disagree produce no third number" rule as `spoke_ms` and `brain_split`. A
turn whose seam is unknown, because a share of an unmeasured whole is not
a share and the table indents `tool` under `think`. A turn past
`ACTS_PER_TURN = 32`, which exists because the runaway tool loop is a
filed, real failure mode (optimization backlog #5) and `jv tap` is meant
to be left running for hours — past the cap it keeps the COUNT and loses
the measurement, since a number we stopped taking is not a short number.
And a frame that named nobody: `utterance_id` is optional on the schema
(a CLI-driven action has no voice turn behind it), and an empty one is
refused inside `acted` rather than only in the caller that unwraps the
Option. `tool_calls` rides beside `tool_ms` throughout, because "no tool
ran" and "a tool ran and could not be timed" both print `tool=?` and are
not the same fact.

Two things deliberately NOT done. It does not go on the `>>> turn` line,
which is already six numbers wide and is B17's open complaint — it prints
its own line, the same shape jv-brain's `wait`/`model` split already
prints, so the existing line keeps its width. And there is no complementary
"everything else" row: the remainder of a tool turn's `think` is two
completions plus the queue plus four bus hops, and naming that one thing
would be a label a number does not mean. Worth recording that `wait`/`model`
and `tool` can never describe the same turn — jv-brain states the first-say
gauge only for a first word that came straight out of the first completion.

One thing found while building and fixed here: the first `tool` row label
was 38 characters in a 31-character column, which silently shoved that
row's three numbers out of line — a broken-looking number, not a long
label, and exactly B17's family of complaint. The label was shortened (the
confirm-window explanation moved to the footnote, where it has room) and
`every_summary_row_stays_inside_the_columns_it_is_printed_in` now asserts
every row is the header's width, which is a guard the table never had.

**B8 is closed as WRONG, not done.** Its premise is that "jv-guard and
jv-compat write their own records". They do not: nothing under
`services/jv-guard/` or `services/jv-compat/` opens a file for writing, and
neither has a state dir (`JARVIS_STATE_DIR` is set for one unit only).
Both services publish and are read off the bus. There is no second caller
for a shared record reader because there is no second record.

- tests: `bash ops/ralph/cargotest.sh jarvisd` — 106 unit + 8 bus + 38
  integration (was 89 + 8 + 36). THIRTEEN mutations run through them, all
  thirteen caught: the union becoming a sum, an unanswered request skipped
  instead of refusing, the fit check dropping its bounds, the cap no longer
  bounding the measurement, evicted turns keeping their requests (the
  unbounded-map one), an action conjuring an utterance, `tool` computed
  with no seam, a re-delivered request counted as a second call, the row
  label outgrowing its column, `tool=` added to the `>>> turn` line, a
  result joined to whatever turn is open, and the empty-id guard removed.
  A thirteenth candidate — defaulting jv.rs's `utterance_id` Option to `""`
  — survives and is EQUIVALENT by construction now that `acted` refuses an
  empty id itself; that is why the guard was moved down a layer rather than
  left in the caller.
- build: `nix build .#jarvisd` ok (its checkPhase runs the same suite),
  `nixos-rebuild build --flake .#ares` ok. Never test/switch. No schema
  change, no jv-act change, no boot path, no NVIDIA/kernel/flake pin — the
  two new topics are READ, and jv-act's own code is untouched.
- files: services/jarvisd/src/cli.rs, services/jarvisd/src/bin/jv.rs,
  services/jarvisd/tests/cli.rs
- next: **B21** is what this cannot do from outside jv-act: `tool` is one
  number over a window that is mostly the human deciding, and
  `action.confirm{kind=request}` names its own `window_s` while
  `action.result` carries `duration_ms` — so "how much of this was waiting
  for YOU" is another free seam, on frames already on the bus, and it is
  the half of `tool` a faster machine could never shorten. It is `spoke`
  one level down. **B22**: B17's complaint now has a machine-checked half.
  `every_summary_row_stays_inside_the_columns_it_is_printed_in` proves the
  TABLE is aligned; nothing proves the `>>> turn` line fits a terminal, and
  it is six numbers plus an id whose length nothing bounds. A width
  assertion against 80 columns is cheap and would turn one of B17's two
  questions into a test.
  B17/B20 are unchanged and still want a human at a terminal; B15 and B13
  still want the one conversation about which span the 2.5 s budget names.
  A52/A53/A47 and A50 are unchanged.

## 2026-09-24 — iteration 46 — the HUD stops being something only a human can check

Two commits, one theme: the corner of the screen had two claims about it
that nothing but a person's eye could verify.

**`GuardPlate.qml` was in the tree as a binary blob** (`88878de`). It landed
in ecc89c5 as `Bin 0 -> 8407 bytes` — 226 lines of a surface that floats
above every window, the one element whose job is to say this machine refused
to run something, committed with no diff for anybody to object to. Cause:
two bytes. The plate joins three fields into a change key and two of them
are attacker-influenced (a file name jv-guard was handed, a hash), so it
needs a joiner neither can contain; `\0` typed as the BYTE works perfectly
at runtime, and git decides text-or-binary by looking for a NUL in the first
8 kB. Written as the escape it is the same string and the file is text.
`test_no_qml_file_is_a_file_git_calls_binary` now holds that for every
`.qml` under shell/, tools/, pkgs/ and harness/ — the claim is that a source
file is REVIEWABLE, which is a property of a text file and not of QML, so
the harness stages are covered on the same terms as the shipped shell. That
commit is itself still `Binary files differ`, because git compares both
sides and one of them is the old blob; every diff after it is text, which
the second commit demonstrates.

Worth naming the general shape: a gate that reads a file's CONTENT (and
almost every gate in tools/tests does) cannot tell you the file is one a
human could have read. Nothing here was watching that, and the thing it
missed was not subtle.

**A53 — the sheet asserts its caption** (`754a49b`). `anyLit` answers the
only question the surface needs — is anything on screen — so every external
check could prove that SOMETHING was drawn and never what. The contact
sheet's one per-shot assertion was that bit, and nine of ten shots answer it
identically; three plates in this stack draw the same two lines in the same
severity colour in the same corner (`health` lost a service, `action` failed
a tool, `guard` refused a binary), so a harness that fed a plate something
it refused and photographed a different plate would have gone green with a
README that misnames its own pictures.

Each plate now declares `plateName`, pinned to its own file name by a tools
gate so it cannot drift into a confident lie, and `PlateStack` collects
`litNames`: the plates on screen, in reading order, as the plates themselves
report it. `anyLit` is untouched — it is what maps the surface and the only
safety-critical answer here — and a test holds the two to agreeing in every
case, because two implementations of one fact drift. An unaskable child
contributes `"?"` rather than being skipped, the same fail-safe direction
`anyLit` takes: the surface counts it as drawing, so the list must admit
something is there.

Three things that fell out of it and are worth more than the mechanism:

  · `07-no-bus.png` is now checked for the argument it exists to make. It
    expects `link` ALONE — every plate under it gates on the bus whose loss
    it reports, so the open microphone from a second ago is gone rather than
    left up as a stale claim about the room. That is A23's whole point and
    it had only ever been looked at.
  · a plate the sheet RENDERS but never LIGHTS now fails a test. The older
    gate proved each plate is in the scene's stack, which only says it was
    built — every plate draws nothing until a real frame gives it something,
    so one could sit in all ten shots and appear in none. That is exactly
    how an element gets added, rendered, committed and never looked at.
  · `docs/hud/README.md` carries a machine-checked `**On screen:**` line per
    shot. A reader believes the README, and prose can drift into naming the
    wrong element.

All ten expected plate lists were right on the first run, which is a weaker
result than it sounds — so each was mutation-checked rather than accepted:
10-guard.png expecting `action` instead of `guard` FAILS now, and passed
before with only the picture to tell them apart.

**A53 is done; A47 is narrowed, not closed.** This closes one of its five
instances. The other four are in tools/hudscreens, which photographs the
REAL `.#jv-hud` under a real compositor — nothing there can read a QML
property, so `grows_from`, A42's live-lit window, A48's three idle windows
and A49's shrink check still prove only that something arrived or left. The
honest options there remain OCR (at 11 px, unreliable) or an IPC seam in the
shipped shell (which stages something in production code for a test's
benefit, and this harness's whole value is that it stages nothing). Left
open deliberately.

- tests: `bash ops/ralph/qmltest.sh` — 487 (was 476); eleven new PlateStack
  tests, FIVE mutations run through them, all five caught: a quiet plate
  staying in the list, reading order reversed, the unaskable child skipped
  instead of admitted, an unnamed plate reported as `""`, a fading plate
  dropping out. `bash ops/ralph/runtests.sh tools` — 130 (was 125); SIX more
  mutations, all caught: the NUL byte put back, a name drifting from its
  file, a plate declaring none, the README naming the wrong plate, a shot
  falling back to the one-bit flag, a plate no shot lights.
  `bash ops/ralph/hudshots.sh` — 10 shots, byte-identical to the committed
  ones, so nothing about the look moved.
- build: `nix build .#jv-hud` ok (qmllint + the QML suite in its checkPhase),
  `nixos-rebuild build --flake .#ares` ok, run against BOTH commits
  separately. Never test/switch. No schema change, no jv-act change, no boot
  path, no NVIDIA/kernel/flake pin. The HUD is still a read-only consumer.
- files: shell/jv-hud/GuardPlate.qml and the other eight *Plate.qml,
  shell/jv-hud/core/PlateStack.qml, shell/jv-hud/tests/tst_platestack.qml,
  tools/hudshots/scene/tst_shots.qml, tools/tests/test_gen_theme_qml.py,
  tools/tests/test_hudshots.py, docs/hud/README.md
- next: **A54** is the cheap thing `litNames` just made possible and this
  iteration did not take: `tst_sessionreplay.qml` walks recorded sessions
  through the whole stack and can now assert WHICH plates the HUD puts up at
  each moment of a real turn, which is a stronger claim than any shot —
  a shot is one settled instant, a replay is the sequence, and the sequence
  is where a plate that arrives one frame too late or leaves one frame too
  early would show. **A55**: the same property is what a `jv hud` subcommand
  would print — "what is the HUD showing right now" is currently answerable
  only by looking at the screen, and B-track has wanted a terminal view of
  the HUD's state since B15 asked which span the 2.5 s budget names. Both
  are additive and neither needs a human.
  A47 is narrowed as above and still wants one decision from a human: OCR,
  an IPC seam, or leave the four hudscreens checks saying what they say.
  A52 is unchanged and still wants the progress-indicator decision first.
  A50/A13/A27/A21/A22/A25/A31/A38/A39 are unchanged and still want a human
  at ares. B21/B22/B17/B20/B15/B13 unchanged.

## 2026-09-24 — iteration 47 — A54: the corner gets watched through a whole turn

Everything that has ever checked the HUD's corner checked ONE SETTLED
INSTANT. The contact sheet takes ten of them and, since A53, asserts which
plates each picture is of; the headless suites in `shell/jv-hud/tests` drive
one state element at a time and assert what it decided. Between those two
sits exactly the class of bug the corner stack can actually have: a plate
that arrives one frame late, leaves one frame early, blinks in the middle of
an utterance, or comes up in the wrong ORDER relative to the plate it is
supposed to qualify. None of those is a state. Every one of them is a
sequence, and a still picture of the settled end of a turn cannot see any of
them.

`tools/hudshots/scene/tst_sequence.qml` replays the committed recordings (B3)
through the REAL plates and asserts the corner's whole trajectory — every
change to `litNames` with the `ts` of the frame that caused it, which is what
`trajectory()` in `tst_sessionreplay.qml` does for one state machine's word:

    hey-jarvis-clean  (dark) -> state@1.44 -> state heard@3.76
    hey-jarvis-music  (dark) -> state@1.44 -> state heard@4.16
    hey-jarvis-pause  (dark) -> state@1.36 -> state heard@6.64
    speech-no-wake    (dark)

Three things that were arguments in a comment until now are facts about a
recording in these four lines:

  · the VAD opening at 0.80 s puts NOTHING on screen. Speech in the room is
    not speech to Jarvis, and the corner is dark for the whole 0.64 s before
    the wake word lands.
  · `hey-jarvis-pause` holds 1.2 s of real silence inside one sentence and
    rewrites itself seven times across it. Every one of those provisional
    sentences was on the bus and causes ZERO extra entries. A flicker is two
    more entries, in both directions, and there is nowhere for it to hide in
    a string.
  · `speech-no-wake` is a real utterance nobody addressed to Jarvis. The
    corner is dark for every frame of it — invariant 10 as a sequence rather
    than as a photograph.

Past the strings, four claims that only a sequence can make: no recording
may light a plate that no service in it reported (a `MicPlate` that took
`audio.vad` for a capture counter would be a recording light lit by the room
rather than by the device); the words are never up without the state plate
above them, which is an ordering claim about meaning and not about layout;
an unanswered turn empties the corner on its own; and losing the bus mid-turn
takes every plate down BEFORE the link plate arrives — the five seconds of
grace `07-no-bus.png` can never hold, because it settles past them.

**Why motion is off in that file**, since it is the one thing that makes any
of this measurable. A plate's `lit` is `opacity > 0`, eased over 140 ms, so
with fades running "when did this plate arrive" is a question about how long
the test process happened to block. The file switches on the REAL
reduced-motion path (`Motion.policy.envOverride = "1"`, parsed in
`core/MotionPolicy.qml`, the same thing `JV_HUD_REDUCED_MOTION=1` does on
ares), under which `Ease` is disabled outright and every opacity is
ASSIGNED: a plate is on screen in the same frame the bus gave it something to
say. One test asserts that property directly, because if it ever stopped
holding every trajectory here would silently become a measurement of this
process's scheduling. The fades themselves are watched standing still by the
shots (A43/A48/A49), where a duration can be looked at rather than raced.
The restore in `cleanupTestCase` is proven by the ten shots coming out
byte-identical: `HudSequence` runs before `HudShots`, and a sheet rendered
with motion left off would not be the same file.

**One copy of the corner, not one per driver.** The sequence replay needs the
same nine plates in the same order the sheet does, and the sheet already held
a copy of `shell.qml`'s stack. Two copies would have been two things to keep
matching the shell, so the stack moved to
`tools/hudshots/scene/Corner.qml`; both drivers build it, and the tools gate
pins it to `shell.qml` — membership AND order, because the order IS the
reading order both drivers assert against. A second gate fails any driver
that declares a plate of its own again.

**What this iteration deliberately did not do.** The suite runs in
`ops/ralph/hudshots.sh` and not in `nix build .#jv-hud`. Making it a build
gate means a second implementation of the stage (the derivation cannot run a
script that shells out to nix), and a staging assembly that exists twice is
one that drifts — the sheet and the gate would eventually be photographing
and asserting different HUDs. Left as a stated choice rather than an
oversight; A56 records it for whoever disagrees.

Also found and NOT fixed here, because fixing it is a behaviour change to a
shipped element and belongs in its own reviewed commit (A57): the two windows
that hold this pair of plates up are pinned equal at 30 s, but they keep time
differently. `SpeechState` expires on a frame's AGE; `HeardState` arms a
one-shot Timer when the line arrives. The transcript arrives after the VAD
boundary it followed, by however long the ASR took, so on ares the state
plate lets go first and the words sit alone for that gap. Small, real, and
invisible to every test that existed before this one.

- tests: `bash ops/ralph/hudshots.sh` — 15 (was 3): twelve new sequence
  cases, plus the 10 shots byte-identical to the committed ones. EIGHT
  mutations run through the new suite, all caught: `HeardPlate` and
  `StatePlate` swapped in the stack, a plate dropped from the corner,
  `MicPlate` lit by `audio.vad`, `HeardState` accepting partials, the held
  line not forgotten when the link drops, the motion guard switched off, the
  state plate arriving only at `thinking`, and the thinking window never
  closing. One mutation was NOT caught, and it is worth stating rather than
  hiding: dropping `root.linked` from `HeardState.heard` changes nothing,
  because `onLinkedChanged` already clears the line — that term is
  belt-and-braces, not a second mechanism, and the suite proves the
  mechanism that does the work.
  `bash ops/ralph/runtests.sh tools` — 131 (was 130); TWO mutations, both
  caught: the corner drifting from `shell.qml`, and a driver keeping its own
  plate. `bash ops/ralph/qmltest.sh` — 487, unchanged, since nothing in
  `shell/jv-hud` was touched.
- build: `nix build .#jv-hud` ok (qmllint + the QML suite in its checkPhase;
  the new files are linted by `hudshots.sh` over the stage, as the stubs
  always have been), `nixos-rebuild build --flake .#ares` ok. Never
  test/switch. No schema change, no jv-act change, no boot path, no
  NVIDIA/kernel/flake pin, and not one line of `shell/jv-hud` changed — the
  HUD itself is untouched and still a read-only consumer.
- files: tools/hudshots/scene/tst_sequence.qml (new),
  tools/hudshots/scene/Corner.qml (new), tools/hudshots/scene/tst_shots.qml,
  tools/tests/test_hudshots.py, ops/ralph/hudshots.sh, docs/hud/README.md
- next: **A57** is the cheapest real finding above — make `HeardState` time
  its hold the way `SpeechState` does (a frame age, not a wall clock) so the
  two windows that describe one turn close together, or have a human decide
  the gap does not matter. It is a one-line change to a shipped element with
  an existing headless suite around it, and the sequence file above is where
  the result would show. **A28/B10** got more valuable again: every
  trajectory here stops at `thinking` because no recording has ever contained
  jv-voice, so the second half of a turn — the answer starting, the words
  leaving, the ember lighting — has no recorded sequence at all. One real
  utterance at the machine would give it one. **A55** is now half-built in
  the sense that matters (the corner's state is a string something can
  print), but it still wants A47's decision about an IPC seam first.
  A47/A52/A50/A13/A27/A21/A22/A25/A31/A38/A39 unchanged and still want a
  human at ares. B21/B22/B17/B20/B15/B13 unchanged.

## 2026-09-24 — iteration 48 — A57: the words and the word above them stop keeping different time

A turn puts two plates on screen. `StatePlate` says THINKING, `HeardPlate`
says what you said. They are the same claim about the same turn — a question
is in flight — and a tools gate has failed the build since A26 if their two
windows ever stopped being the same LENGTH. They were still not one window,
because nothing checked that they started at the same INSTANT, and they did
not: `SpeechState` times its window from the utterance's `audio.vad
speech_end` (the frame that says a question is in flight), while `HeardState`
armed its hold when the TRANSCRIPT reached it, which is however long
faster-whisper took after that boundary. Two 30 s windows, one starting later
than the other, so on ares the state plate lets go first and the transcript
sits there alone for the length of the ASR — words with nothing above them
saying why they are still up. Found in A54 and deliberately left for its own
commit, because it is a behaviour change to a shipped element.

`HeardState` now has an `anchor`: the `speech_end` of the utterance those
words belong to when it saw one, and the transcript itself otherwise. The two
frames are matchable because `utterance_id` is minted at speech_start and
threaded through both topics, which is the only reason this was cheap. Four
rules keep the new reading from ever costing the reader anything — it decides
WHEN the line goes, never WHETHER it is shown, so every refusal falls back to
exactly what shipped before: only `speech_end` (a speech_start is where the
utterance began, and timing from it would subtract the length of the sentence
as well as the ASR), only a frame whose `conf` agrees with its own state
topic, only an id that matches, and never a boundary stamped AFTER the final
it supposedly preceded — that pair cannot be ordered, and using the later of
the two would LENGTHEN the hold, which is the one direction this window may
not err in. The boundary is latched (ears' VAD runs continuously, so the next
sound in the room replaces it on `bus.latest`) and dropped with everything
else when the link goes down.

**What this iteration could not do, and it is the finding worth keeping.** No
recording can show this bug. `harness/fixtures/sessions/generate_sessions.py`
stamps each final at the SAME `ts` as the speech_end before it, so in all
four replays the ASR is instantaneous, both anchors are the same number, and
every suite built on those recordings — tst_sessionreplay, the shot sheet,
A54's sequence suite — is structurally blind to the one number this is about.
That is why it survived five suites, and it is why the proof here is a paired
headless test (two real elements, one BusModel, real timers) rather than a
picture: the 10 shots came out byte-identical, as expected. A58 records the
fix — an ASR delay in the generator — and why it is its own commit: it means
regenerating the four recordings that the contact sheet asserts byte-for-byte
and that tst_sessionreplay pins real numbers out of.

Also removed one guard rather than shipping it untested: an `utterance_id`
type/length check in the frame reader that no mutation could distinguish from
the id comparison next to it, because a boundary carrying no id already fails
that comparison. One rule, one mechanism. And corrected the plate table in
`shell/jv-hud/README.md`, which still said eight plates and had never listed
`GuardPlate` (A51).

- tests: `bash ops/ralph/qmltest.sh` — 495 (was 487): eight new cases, the
  last of which puts a real `SpeechState` and a real `HeardState` on one bus
  with 0.5 s windows and 400 ms of ASR, and fails if the words outlive the
  word above them. NINE mutations run through the suite, all caught: the hold
  timed from the transcript again (the bug itself, caught by three tests),
  any boundary accepted regardless of utterance, a speech_start read as an
  end, every vad event read as an end, a boundary newer than the words
  accepted, a boundary that doubts its own `conf` accepted, the boundary
  surviving a dropped link, and nothing re-arming when the anchor changes.
  `bash ops/ralph/runtests.sh tools` — 131, unchanged (the equality gate
  still holds; its docstring now says which half of the rule it checks and
  where the other half is proved). `bash ops/ralph/hudshots.sh` — 15, and the
  10 shots byte-identical.
- build: `nix build .#jv-hud` ok (qmllint + the QML suite in its checkPhase),
  `nixos-rebuild build --flake .#ares` ok. Never test/switch. No schema
  change, no jv-act change, no boot path, no NVIDIA/kernel/flake pin. The HUD
  is still a read-only consumer and the new topic is never rendered.
- files: shell/jv-hud/core/HeardState.qml, shell/jv-hud/tests/tst_heardstate.qml,
  shell/jv-hud/README.md, tools/tests/test_gen_theme_qml.py
- next: **A58** is the cheapest thing that makes the replay suites able to
  catch this whole class of bug — give the fixture generator a realistic ASR
  delay and regenerate, with the shot diff reviewed. It pairs naturally with
  **A28/B10** (a live recording of one real utterance at the machine), which
  would do the same job better and would finally give the second half of a
  turn — the answer starting, the ember lighting — a recorded sequence at
  all; every trajectory still stops at `thinking`. **A56** (the sequence
  suite is not in the build gate) is unchanged and wants a human's pick
  between its three options. **A55** still waits on **A47**'s decision about
  an IPC seam. A50/A52/A13/A21/A22/A25/A27/A31/A38/A39 unchanged and still
  want a human at ares. B21/B22/B17/B20/B15/B13 unchanged.

## 2026-09-24 — iteration 49 — A58: the recordings stop saying that hearing is free

Last iteration fixed a HUD bug (A57: the transcript and the "THINKING"
above it kept different time) and reported, as the finding worth keeping,
that no committed recording could have shown it. This closes that.

`harness/fixtures/sessions/generate_sessions.py` stamped every frame at
`EarsPipeline.clock()`, the sample clock — samples consumed over rate.
No samples are consumed while faster-whisper runs, and jv-ears publishes
the final transcript from inside `_on_speech_end`, immediately after
`asr.transcribe()` returns. So on a real bus jarvisd stamps that frame
however long the transcribe took AFTER the `speech_end` beside it, and in
the recordings the two were the same number. The ASR was instantaneous in
all four files; the gap between "the turn ended" and "the words arrived"
was exactly zero everywhere in this repo, which is why five suites built
on these recordings were structurally unable to see A57.

The generator now adds `ASR_LATENCY_S` to a final's `ts`. 2.2 s, and the
number is not invented: PHASE1-STATUS.md records "ASR is ~2.2 s fixed
(faster-whisper distil-small, CPU, runs after speech_end)" as a live
measurement on ares, and it is the same span `jv tap --latency` already
calls `hear`. It is a DECLARED constant rather than a measurement taken
while generating, on purpose — a recording whose numbers depended on how
busy the generating machine was would stop being reproducible to the
sample, which is the property everything else in that file protects.

Partials are deliberately left alone, and the README says so rather than
leaving the asymmetry to be discovered. Each partial costs a transcribe
too, but nothing has measured one, and modelling it honestly means
modelling the sample clock falling BEHIND the room and catching up — the
transcribe runs inline on the one thread that feeds wake and VAD
(optimization-backlog §6) — which would move every other frame in these
files instead of one, and would be inventing a timeline rather than
recording one. A59 records that.

**How the files were changed, stated plainly because it matters.** The
loop's machine has no model weights, so the pipeline could not be re-run.
The three finals were restamped in place by the same `asr_delay()` the
generator now applies — one number per recording, headers untouched, so
`wall_time_utc` still dates the real recording rather than the edit. The
diff is three lines. What proves a regeneration lands in the same place is
`test_the_committed_session_is_what_the_pipeline_still_does`, which
compares `ts` frame by frame and needs the weights: the first jv-ears run
on a machine that has them is the check, and it is in the build's path,
not in this loop's.

What the gap immediately bought. `tst_sessionreplay` now reads A57's
anchor off a real recording rather than off frames whose author also
wrote the expectation, and pairs a real `SpeechState` with a real
`HeardState` on one bus with real timers; the numbers there are
load-bearing and the comment does the arithmetic (both windows 3 s, both
starting at the boundary, the words 2.2 s in, so the anchored hold has
0.8 s left and a hold timed from the transcript would have 3 s — 1.6 s is
the budget that separates the two readings rather than racing them). The
sequence suite's three trajectories move to the second the words really
arrive (`state heard@5.96` for the clean recording, was `@3.76`), and its
unanswered-turn test had to grow its shortened window from 200 ms to 3 s:
a budget under the ASR expires the line before it is ever shown, so that
test would have gone green over a corner the reader never saw. 200 ms was
only ever legal while the recordings said hearing was free.

One unrelated brittleness fixed on the way, because it cost real
debugging time here: that test shortened two windows and restored them on
its last line, so the `compare` in the middle of it meant four later
tests ran against a HUD with a 200 ms memory and failed for a reason that
was not theirs. The restore is now a `cleanup()`.

- tests: `bash ops/ralph/runtests.sh harness` — 88 (was 78): three new
  cases, one per recording that contains a final, plus per-recording
  checks that every partial is stamped while its utterance is still open
  and that file order is time order (replay.py sleeps the delta between
  consecutive lines and clamps at zero, so a frame written out of order
  would replay with its gap silently lost). `bash ops/ralph/qmltest.sh` —
  498 (was 495). `bash ops/ralph/hudshots.sh` — 15, and the 10 shots
  byte-identical, which is the expected answer: no plate draws a `ts`.
  `bash ops/ralph/runtests.sh tools` — 131, unchanged. `bash
  ops/ralph/runtests.sh jv-ears` — 37, with the staleness check skipping
  for want of weights. FOUR mutations run through the suites, all caught:
  the hold anchored back on the transcript (caught by the new paired
  replay test with a message, not a race), the declared latency back to
  zero, the delay applied to partials as well as finals, and a frame
  written out of time order.
- build: `nix build .#jv-hud` ok (qmllint + the QML suite + the two
  generators with `--check` in its checkPhase), `nixos-rebuild build
  --flake .#ares` ok. Never test/switch. No schema change, no jv-act
  change, no boot path, no NVIDIA/kernel/flake pin. The HUD is still a
  read-only consumer.
- files: harness/fixtures/sessions/generate_sessions.py,
  harness/fixtures/sessions/{hey-jarvis-clean,hey-jarvis-music,hey-jarvis-pause}.jsonl,
  harness/fixtures/sessions/README.md, harness/tests/test_sessions.py,
  shell/jv-hud/core/HeardState.qml, shell/jv-hud/tests/Sessions.qml,
  shell/jv-hud/tests/tst_sessionreplay.qml, shell/jv-hud/README.md,
  tools/hudshots/scene/tst_sequence.qml
- next: **A28/B10** is now the clearly biggest thing a human can unlock —
  one real utterance recorded at the machine would give the second half of
  a turn (the answer starting, the ember lighting) a recording at all, and
  would carry a REAL ASR instead of a declared one; every trajectory in
  the repo still stops at `thinking`. **A59** is the honest follow-up to
  this commit: the partial latency, which wants either a measurement or a
  decision to leave it. **A56** (the sequence suite is not in the build
  gate) is unchanged and wants a human's pick between its three options.
  **A55** still waits on **A47**'s decision about an IPC seam.
  A50/A52/A13/A21/A22/A25/A27/A31/A38/A39 unchanged and still want a
  human at ares. B21/B22/B17/B20/B15/B13 unchanged.

## 2026-09-24 — iteration 50 — B21: `tool` stops charging the machine for your
## own hesitation

UI was the last three iterations (A54, A57, A58), so the ladder says take a
feature. B21 was the direct follow-up to B19, which shipped `tool` — the
`intent.action` -> `action.result` union inside a turn's `think` — and named
its own flaw in the footnote it printed: that span includes the whole 15 s
confirmation window jv-act holds open for a destructive tool, "never spoken,
and otherwise indistinguishable from a slow LLM." One number over a window
that is mostly a human deciding cannot be argued about against a budget, and
the half a faster machine could shorten is precisely the half it cannot name.

**What it buys.** `jv tap --latency` now prints, under the `tool` line, which
is under `>>> turn`:

    >>> turn utt-c: think=26000ms includes tool=16000ms over 1 call (jv-act)
    >>> turn utt-c: tool=16000ms is you=15000ms + ran=1000ms over 1 confirmation

and two summary rows indented one level under `  tool`:

        you    of tool: you, deciding             1   15000ms ...
        ran    of tool: jv-act's own work         1    1000ms ...

**The seam was free, like hear/think and like tool.** `action.confirm`
kind=request is jv-act asking; kind=answer is the question closing, by an
answer or by the window expiring. Both frames carry the `request_id` that
`intent.action` already named, so the join is the same one `action.result`
goes through (`act_mut`, now shared by all three). No new publisher, no gauge,
no schema change. jv-act's `duration_ms` was NOT usable for this and it is
worth writing down why: it is measured from `t0`, before the confirmation, so
it is the whole request including the wait — the same number, not its
complement.

**Five refusals, because a number that mixes two things is what this commit
exists to stop.** No question asked at all is not a 0 ms window. A question
still open when the reply landed was open for a length nobody can state.
A window that does not NEST inside its own call's round trip means two frames
disagree about the order the pipeline ran in — and that nesting is also the
thing that makes `ran = tool - you` a plain subtraction that cannot go
negative, so `ran_ms` needs no fit check of its own and does not pretend to
have one. A `tool` nobody could measure leaves its share unreported: a share
of an unmeasured whole is not a share. A question for a request this tap never
saw belongs to no turn it can name. `confirm_waits` rides beside `confirm_ms`
for the same reason `tool_calls` rides beside `tool_ms`: "you were never
asked" and "you were asked and it could not be timed" are different facts.

**One live-order detail the integration test pumps rather than assumes.**
jv-act ECHOES the answer it acted on (`kind=answer`, answered_by=voice/cli/
timeout) onto the same topic the `jv confirm` CLI publishes its answer on, so
one decision produces two frames. The user stopped deciding at the first.
`keep_earliest`, and a test that publishes both in the real order.

**An unrelated hole closed on the way, because these rows fall straight into
it.** B19's `every_summary_row_stays_inside_the_columns_it_is_printed_in`
filtered out every line starting with four spaces, to skip footnote
continuations — which would have exempted the two new rows, the deepest and
the most likely to overflow their column, from the check written for exactly
that failure. It now takes the header and the rows under it and stops at the
first footnote, and a deliberately over-wide `ran` label is one of the seven
mutations below.

- tests: `bash ops/ralph/cargotest.sh jarvisd` — 119 unit + 8 bus + 39
  integration (was 106+8+38). SEVEN mutations run through them, all seven
  caught: the nesting check dropped, an open question timed to its own
  result, `confirm` no longer gated on `tool`, the union turned into a sum
  (which needed a new overlapping-windows test to bite — the first union test
  used disjoint windows, where union and sum agree), jv-act's echo taken as
  the answer, an over-wide label in a deep row, and a join that fell back to
  whatever turn was open. An eighth — bypassing the `reqs` index and scanning
  every turn's acts — turned out to be an EQUIVALENT mutant, not a survivor:
  `reqs` and `u.acts` are written and evicted together, so the index is a
  shortcut and never a filter. Noted rather than papered over with a test that
  would pass either way.
- build: `nix build .#jarvisd` ok (its checkPhase runs the suite again),
  `nixos-rebuild build --flake .#ares` ok. Never test/switch. No schema
  change, no jv-act change (it was read, not touched), no boot path, no
  NVIDIA/kernel/flake pin.
- files: services/jarvisd/src/cli.rs, services/jarvisd/src/bin/jv.rs,
  services/jarvisd/tests/cli.rs
- next: **B22** is now slightly more urgent than it was and is still the
  cheapest B item: nothing bounds a `>>> turn` line's width, and this commit
  added a third such line whose id is the same unbounded utterance id. With a
  UUID in it the new line is ~107 columns. B22 asks for exactly that assertion
  and names the id length that breaks it. **B20/B17** still want two minutes
  of a human reading real output at a terminal, and **B10/A28** — one live
  recording of one spoken turn on ares — remains the single biggest thing a
  human can unlock; it would also be the first recording containing an
  `action.confirm` at all, which is to say the first real number this commit
  could ever print. **A59** wants either a measurement at ares or a decision
  to leave the partials' latency alone. **A56** and **A55/A47** unchanged and
  want a human's pick. A50/A52/A13/A21/A22/A25/A27/A31/A38/A39 unchanged and
  still want a human at ares. B7/B12/B15/B13 unchanged.

## 2026-09-24 — iteration 51 — B22: the turn report stops being wider than the
## terminal it prints to
- built: **`jv tap`'s per-turn report is a ladder of lines, and every one of
  them fits 80 columns.** B22 asked for a width assertion against 80 with "the
  id length that would break it" named. The assertion was written first and it
  failed at 133 columns — and not because of the id. The live utterance id is
  a `uuid.uuid4()` (`jv_ears/pipeline.py:148`), 36 characters, but the line was
  already 96 columns with the five-character id every test used. Six numbers
  plus a label each cannot fit a terminal at all, so B22 could not be closed by
  adding a test. The format had to move.

**What it is now.** Each rung divides a span the rung above it gave a value
for, and nothing else:

```
>>> turn 00000002...: total=262ms spoke=? hold=20ms
>>> turn 00000002...: respond=262ms is hear=0ms + think=262ms
>>> turn 00000002...: think=262ms includes tool=262ms (1 jv-act call)
>>> turn 00000002...: tool is you=202ms + ran=61ms (1 confirmation)
```

One grammar throughout — `X is A + B` for an exact partition, `X includes Y`
for a share — which is the grammar `brain_split` already spoke and which the
summary table's indentation already draws. `Turn::lines` owns which rungs
exist and in what order, which is what makes "the line above it" a fact
rather than a hope at the call site; `jv tap` prints what it hands back and
decides nothing. And because the bottom rung says `tool` without restating
its value, `confirm_line` gained a `think_ms?` guard it does not otherwise
need, so "no rung names a span no printed line valued" is true of the TYPE
and not merely of the one caller that builds these today.

**The id.** `short_id` caps it at `ID_COLUMNS` = 11: eight characters and
`...` to say out loud that it is a prefix. An id that already fits is never
touched, so abbreviating can never make one longer — `echo_raw`'s shape. Two
ids that start alike print alike; that is the price, and it is a test
(`two_ids_that_start_alike_print_alike_and_that_is_the_price`) rather than a
silence. It is also not hypothetical: the first version of the confirm pump
varied only the last two hex digits of its uuid, every turn printed the same
abbreviated id, and the new ladder-grouping helper collapsed four turns into
one — the harness found the collision before a human could.

**The bound, stated.** `every_line_a_turn_prints_fits_eighty_columns` runs at
the widest input that can reach these lines and names each bound as what it
is: the id is capped BY CONSTRUCTION, both counts are two digits because
`ACTS_PER_TURN` stops the recording at 32, and every span is six digits —
999999 ms is 16.7 minutes, longer than any turn that ends with somebody still
listening, and THAT is the one bound assumed rather than enforced. A seventh
digit adds a column to four of the five lines and this test is what would
notice. It carries a control, in A34's spirit: a line that comes out far
UNDER the budget fails too, because then the test stopped building a worst
case and stopped proving anything. The summary and hop tables are held to the
same 80 — a table that wraps loses the column alignment that is all of its
value.

**A pre-existing flake, found on the way and fixed.** The confirm test
asserted `tool - (you + ran) < 1.0`. `ran` IS `tool - you` to the float, but
all three are rounded to whole milliseconds INDEPENDENTLY for printing, so a
262.4 ms tool prints as 202 + 61 and the difference is exactly 1. It failed
about one full-suite run in three under load and had nothing to do with this
change; the tolerance is now `<=` with the arithmetic written down.

- tests: `bash ops/ralph/cargotest.sh jarvisd` — 124 unit + 8 bus + 39
  integration (was 119+8+39), and the integration suite run six times over
  for the flake. TWELVE mutations run through them, all twelve caught:
  `short_id` never truncating, its cap raised to 20, truncating without the
  `...`, counting bytes rather than columns, the `think` guard dropped from
  `confirm_line`, `lines()` losing the respond rung, the old six-number line
  coming back, an over-wide label on the tool rung, the rungs printed out of
  order, a summary row pushed past its column, `brain_split` printing the raw
  id, and `jv` printing only the first rung. The confirm pump now stamps the
  live id shape, so the richest ladder is proven on a uuid end to end rather
  than only on a constructed `Turn`.
- build: `nix build .#jarvisd` ok (its checkPhase runs the suite again),
  `nixos-rebuild build --flake .#ares` ok. Never test/switch. No schema
  change, no jv-act change, no boot path, no NVIDIA/kernel/flake pin.
- files: services/jarvisd/src/cli.rs, services/jarvisd/src/bin/jv.rs,
  services/jarvisd/tests/cli.rs, PHASE1-STATUS.md
- commit: dd0857b
- next: **B17 is now half-closed and the remaining half is sharper.** The
  width question is a test; what is left for a human is whether the ladder
  READS — four lines per tool turn is more output than one, and `turn_age>=`
  (B20) is still unjudged. Both want the same two minutes at a terminal, and
  both are unlocked by **B10/A28**, the one live recording of one spoken turn
  on ares, which remains the biggest thing a human can hand this loop. New
  item **B23**: the per-frame `jv tap --latency` hop line is formatted in
  `jv.rs` and is the one report line the new width test cannot reach — it is
  61 columns today and a topic longer than its `{:<20}` field widens it.
  **A59** still wants a measurement at ares or a decision to leave the
  partials alone. **A56** and **A55/A47** unchanged and want a human's pick.
  A50/A52/A13/A21/A22/A25/A27/A31/A38/A39 unchanged and still want a human at
  ares. B7/B12/B15 unchanged.

## 2026-09-24 — iteration 52 — A52: the install you walked away from gets to
## tell you it failed

- built: **`core/InstallState.qml` + `InstallPlate.qml` — the Windows app
  jv-compat could not finish installing.** A51 gave the HUD half of
  invariant 8: jv-guard's refusal, the one moment JarvisOS says NO to
  something its user asked for. This is the other half — what happens to the
  binaries it lets THROUGH. `jv-compat install ~/Downloads/thing.exe` builds
  a bubblewrapped prefix and runs the installer inside it silently, for
  minutes, and it is the only fire-and-forget command on this machine: by
  the time it fails the terminal that started it is behind three windows and
  the user is somewhere else. The report was an exit code nobody was looking
  at. The HUD, which is on top of every window, now says `INSTALL FAILED`
  and names the app.

**FAILURES ONLY, and that is how the open question stayed open.** The topic
carries the whole lifecycle — fingerprinted, screened, prefix_created,
installed, failed, blocked — and A52 said outright that the interesting
decision came first: an install takes MINUTES, every plate in this stack is
about a moment, and "what is jv-compat doing right now" would be a progress
indicator, which is a shape §06 does not have. So nothing here anticipates
one. The happy path draws NOTHING, the way an action that worked (A37) and a
service that is well (A6) draw nothing, and the question is written down as
**A60** for a human with three ways out rather than answered by a loop that
felt like building something. The sheet asserts that silence: `11-install.png`
publishes a `prefix_created` AND a `failed`, and its caption is `install mic`
— one plate out of two frames.

**NOT `blocked`.** That event is how the SCREENING ended, and GuardPlate
already draws that refusal from jv-guard's own `guard.verdict`, joined to
this lifecycle by the same sha256. Two plates for one refusal would be the
HUD saying the same thing twice in two vocabularies, and the witness that
reads the screener directly is the better one. Passed over as NO NEWS —
ActionState's rule for the confirmation outcomes it declines — so a refusal
landing after a real failure cannot silently take it off the screen.

**NOT the error text.** On a `failed` frame, `compat.install.error` is
`detail[-500:]` of the confined installer's own stdout: free text written by
the one thing invariant 8 calls untrusted outright, and likely carrying
paths out of this filesystem. Same call as the scanner's `reasons` (A51) and
jv-act's `detail` (A37), drawn harder — the element does not expose the
field at all, so no plate can render what it never received, and a test
asserts the absence rather than trusting the QML.

**THE SLUG MUST LOOK LIKE ONE, and this is where the element parts company
with GuardState.** `app` is the prefix DIRECTORY name, built by jv-compat
out of a file name its author chose. GuardState sanitises a file name and
draws it, which is right: a name is a thing to LOOK at, so stripping the
invisible characters out of one still leaves the name its author typed. A
slug is an IDENTIFIER — the directory, the thing you would type to try
again — and a repaired identifier is another app's name. So it is sieved,
not scrubbed: drawn only if it still has the shape of a directory name (one
line, no separators, no spaces, 40 characters), REFUSED outright otherwise,
and the sha256 prefix shown instead. A failure whose slug and whose hash are
both unusable is still reported, nameless, because an install that failed is
news whether or not the HUD can say which.

**A gate came out, and the mutation harness is why.** The first version had
the family's "is that a word I know" check on the frozen enum, copied from
GuardState. The mutation that deletes it changed NOTHING: `apply()` acts on
two allow-lists (the exact string `failed`, and four clearing events), so a
word jv-compat invents tomorrow already does nothing at all. GuardState
needs its check because its clearing branch is "everything that is not a
refusal"; this one does not, and a guard no test can tell the presence of is
a guard nothing is holding up. It was removed and the reasoning written
where the next reader will be — and the one remaining belt-and-braces check
(`event` is a string) is labelled as such IN the test that covers its
outcome, so nobody mistakes a passing test for proof of a line.

The HUD is ten plates and a 688 px box now (624 -> 688, four other files
carry the number and `test_the_surface_box_is_the_one_shell_qml_declares`
pins the measuring one). The growth is real co-occurrence, not margin: a
refused binary and a failed install are the pair jv-compat itself produces
when somebody fetches a second build of the thing that was blocked.

- tests: `bash ops/ralph/qmltest.sh` — 536 (was 498; 36 new), with FOURTEEN
  mutations run through them and thirteen caught: `blocked` added to the
  clearing list (1 fail), `blocked` latched like a failure (2), everything
  that is not a failure clearing the plate (2), the slug drawn as the
  publisher sent it (4), a long slug truncated instead of refused (1), a
  newer install not clearing the old failure (3), the envelope floor
  dropping the schema version (2), the hash shortened whatever it is (1),
  the hash left in whatever case it arrived in (1), the backstop never
  firing (4), a dropped link that keeps the failure (1 — and only a
  RECONNECT can show that one, since `failed` is already false while the
  link is down), and the installer's stdout exposed as a property (1). The
  fourteenth is the one that escaped and took the redundant gate with it.
  `bash ops/ralph/runtests.sh tools` — 131 (was 128 + the three that failed
  until the sheet and its README caught up). `... jv-hud-bridge` — 25.
  `bash ops/ralph/hudshots.sh` — 11 shots, all rewritten at the new box
  height, `11-install.png` new, and the sequence suite (A54) green at ten
  plates. `bash ops/ralph/hudscreens.sh` — 7 screens, every window and probe
  green against the REAL `.#jv-hud` that now carries this plate; the five
  screens that moved are A45's documented 2-5 px glyph drift.
- build: `nix build .#jv-hud` ok (qmllint -W 0 + the QML suite in its
  checkPhase), `nixos-rebuild build --flake .#ares` ok. Never test/switch.
  No schema change, no jv-act change, no boot path, no NVIDIA/kernel/flake
  pin.
- files: shell/jv-hud/core/InstallState.qml (new),
  shell/jv-hud/InstallPlate.qml (new),
  shell/jv-hud/tests/tst_installstate.qml (new), shell/jv-hud/shell.qml,
  shell/jv-hud/qmldir, shell/jv-hud/core/qmldir, tools/gen_theme_qml.py,
  tools/hudshots/scene/{Corner,tst_shots,tst_sequence}.qml,
  tools/hudscreens/{sheet,shoot}.py, ops/ralph/hudscreens.sh,
  services/jv-hud-bridge/jv_hud_bridge/bridge.py, docs/hud/README.md,
  docs/hud/*.png, docs/hud/screens/*.png
- commit: caa7c75
- next: **A60 is the interesting one and it is a human's**: the progress
  question this iteration deliberately did not answer, with three options
  written out. **A61** is cheap and concrete — no shot has ever shown
  GuardPlate and InstallPlate together, which is the pair the box grew for.
  The A13/A27 "every plate on every monitor" question now has a fifth
  instance and is no closer to an answer. A50/A55/A47/A56/A59 unchanged and
  still want a human's decision; A21/A22/A25/A27/A31/A38/A39 still want a
  human at ares. **B10/A28 — one live recording of one spoken turn on ares
  — remains the biggest thing a human can hand this loop.** B7/B12/B15/B17/
  B20/B23 unchanged.

## 2026-09-24 — iteration 53 — A61: the two halves of invariant 8 get
## photographed together

- built: **`12-guard-install.png` — a refused binary and a failed install in
  one corner, which is the picture the surface box was grown for and the one
  nothing had ever taken.** `shell.qml` went 624 -> 688 px twice, once for
  GuardPlate (A51) and once for InstallPlate (A52), and both times the
  justification written into the binding was co-occurrence: these two plates
  can genuinely be up together, so the box has to hold them. Eleven shots
  later, no picture showed it. An argument nobody can check is an argument,
  and the box is the one number in this HUD that gets cropped by a
  compositor rather than caught by a test.

**A61's own story turned out to be impossible, and that is most of what this
bought.** The item described a refusal and a RETRY: jv-guard blocks an
installer, the user fetches a different build, that one fails inside its
prefix. Writing the frames out is what showed it cannot happen — jv-guard
screens the second build too, `core/GuardState.qml` reports *the last binary
screened*, and a `clean` verdict is newer news from the same screener, so
the refusal is off the corner before the retry gets as far as failing. For
both plates to be lit the refusal has to be the NEWER screening and the
failure has to belong to a DIFFERENT binary.

Which is not a contrivance — it is the ordinary shape of two overlapping
installs, and an install is the one thing on this bus that takes minutes:
t=0 a long installer is fingerprinted, screened clean and given a prefix;
t=200 the user, still waiting, grabs something else off a download site and
jv-guard matches a signature in it; t=214 the first install, still going,
dies inside its prefix. Every frame is one `install.py` and `jv-guard`
really publish, in the order they publish them, with real timestamps — the
heartbeat goes in LAST so the open mic is as fresh as the failure above it
rather than 214 s stale.

The `blocked` on `compat.install` at t=200 is the frame worth having a
picture of. It lands in the middle of ANOTHER app's lifecycle, and
`InstallState` reads it as no news at all: a clearing event there would have
wiped the failure that arrives fourteen seconds later, and a failure there
would have put `codec-pack` on the plate instead of `fl-studio`. A52's tests
assert that rule; this is the first time the situation that makes it matter
has been on a screen.

**The sheet also stopped taking the fit on faith.** Every shot now asserts
that `insetPx + stack.height <= surface height` — the real constraint, not a
stricter one. A stack taller than the box is not a smaller sheet; it is a
plate the compositor cuts in half on a panel floating over every window, and
until now the only thing that had ever checked it was a person looking at a
PNG and seeing nothing obviously wrong. Mutation: a 170 px surface fails on
`03-heard.png` at 161 px tall and passed before.

**What the picture shows that nothing asked for (A62).** The corner is
describing two unrelated binaries and says so nowhere: `codec_pack_setup.exe`
was refused, `fl-studio` failed, and they are stacked 8 px apart in the same
severity colour. A reader who assumes one story reads "the thing that was
blocked then failed" — the one sentence these frames do not support. Every
plate here is true alone and the corner has no grammar for relating two of
them. That is now written down rather than argued about.

Two more things this iteration found and did not build. The fit check passes
with 507 px of slack: the new shot is now the tallest committed one at 165 px
of corner inside a 688 px box, and no shot lights more than three plates — so
the case the box is actually sized for is still unphotographed and
unasserted (A63). And `jv-guard`'s `decide()` returns only `clean` or
`blocked` — no heuristic engine exists — so the `suspicious` verdict the
policy sanctions, the override path `install.py` prints instructions for,
and `GuardPlate`'s entire `warn` branch are unreachable on this machine
today (A64). The `warn` colour was very nearly photographed this iteration
before that came to light; a composed frame no code path can produce is a
picture of an intention, which is the one thing this sheet must not quietly
become.

- tests: `bash ops/ralph/hudshots.sh` — 12 shots (was 11) and 15 cases, with
  the other ELEVEN PNGs byte-identical, which is the check that the new
  entry changed nothing else. One mutation run through the new fit check
  (a 170 px surface box: FAILS now, passed before).
  `bash ops/ralph/runtests.sh tools` — 131, and the two README gates failed
  exactly as designed until the twelfth section was written (`shows
  12-guard-install.png in 0 sections`).
  `bash ops/ralph/qmltest.sh` — 536, unchanged: no file under
  `shell/jv-hud` was touched.
- build: `nix build .#jv-hud` ok, `nixos-rebuild build --flake .#ares` ok.
  Never test/switch. No schema change, no jv-act change, no boot path, no
  NVIDIA/kernel/flake pin.
- files: tools/hudshots/scene/tst_shots.qml, docs/hud/README.md,
  docs/hud/12-guard-install.png (new)
- commit: 542797a
- next: **A64 is the sharpest of the new three** and it is small: either
  jv-guard grows the heuristic engine its own policy describes, or the HUD's
  `warn` branch and `install.py`'s override message are documented as
  waiting on one — right now three files describe a verdict nothing can
  publish. A62 is a design question (does the corner need a grammar for
  "these two are unrelated", or is that a thing §06 refuses?) and belongs to
  a human. A63 wants one composed shot of a crowded corner, which is cheap
  but wants A62 answered first or it is a picture of the exact confusion A62
  names. **A60 is still the interesting one and still a human's.** A50/A55/
  A47/A56/A59 unchanged and still want a decision; A21/A22/A25/A27/A31/A38/
  A39 still want a human at ares. **B10/A28 — one live recording of one
  spoken turn on ares — remains the biggest thing a human can hand this
  loop.** B7/B12/B15/B17/B20/B23 unchanged.

## 2026-09-24 — iteration 54 — A64: the verdict three files describe gets
## something that can actually say it

- built: **jv-guard's shape engine — the `suspicious` rung now has a
  producer.** `decide()` could return `clean` or `blocked` and nothing
  else, so the approved policy's middle rung lived in three files and no
  code path: the schema's policy note, jv-compat's "override requires
  explicit confirmation — not wired in v0" message, and `GuardPlate`'s
  `warn` colour. A61 came within one composed frame of photographing that
  colour, which is what made it worth fixing rather than noting: a picture
  of a verdict nothing can publish would have put an intention into the one
  sheet whose whole value is that it isn't one.

`jv_guard/pe.py` reads a Windows binary's section table and nothing else —
no imports resolved, no relocations walked, no network, ~90 lines of
`struct.unpack_from` with a bounds check before every read. Anything it
cannot parse confidently it refuses to parse at all, because a half-read
header is a worse input to a security decision than no input.
`jv_guard/heuristics.py` turns sections into concerns: an **executable**
section that measures ≥ 7.2 bits of entropy (packed or encrypted), one
that is also **writable** (W+X — it can rewrite the code it runs), one
with **no bytes in the file** but hundreds of KiB of virtual space (the
UPX0 shape, which entropy cannot see because there is nothing to measure).
It reads a 64 KiB header window and then only the executable sections'
bytes, capped at 8 MiB each — an installer is gigabytes and none of it
belongs in memory.

**The word "executable" is the entire difference between a rung and a
nuisance.** Every Inno/NSIS/7z installer on earth carries a compressed
payload at entropy ~8, and it lives in a data section or an overlay. Had
the check been "any high-entropy section", `suspicious` would have meant
"is an installer" by the end of the first week. A test states that case as
its own argument, and flipping the executable guard off makes it fail.

**The regression this nearly introduced is the part worth reading.** Before
today, "no engine ran" and "ClamAV is down" were the same sentence, and
that sentence is what fail-closed is made of: no verdict published, compat
times out, the install refuses. Add a second engine that always runs and
that equivalence silently dies — ClamAV goes down, the shape engine reports
an ordinary-looking binary, `decide()` sees an engine that ran and says
**clean**. Fail-closed deleted by a feature, with no test failing anywhere.
So engines now declare a KIND: `SIGNATURE` is authoritative (its silence is
what `clean` is made of) and `HEURISTIC` is advisory (may raise suspicion,
may never grant trust). `decide()` returns None unless an authoritative
engine ran — and does so even when the advisory engine is shouting, because
the approved policy's outage clause says an outage must neither grant trust
nor invite an override, and publishing `suspicious` during one invites
exactly that. The degraded health note stopped saying "no scan engine
available" when one demonstrably ran; it now names the outage precisely and
says which advisory engine looked anyway.

**Missing Authenticode was the other candidate in A64 and is deliberately
not here.** It fails twice. Nearly every binary this machine will ever
screen — indie games, mod tools, decade-old installers — is unsigned, so
the rung would fire on almost everything and come to mean "is a Windows
program". And the cheap half is worthless regardless: the PRESENCE of a
signature blob is not trust, only a verified chain is, and verifying one
needs a certificate store and a policy about who is trusted. That is a
different and much bigger piece of work, and it is written into the module
docstring so the next reader doesn't re-derive it.

**What this costs, deliberately.** A UPX-packed freeware tool and a
Themida/VMProtect-wrapped game installer both read as packed, because they
are — and in v0 `suspicious` refuses, with a message describing an override
that isn't wired. So a class of installs that used to succeed now stops and
asks for a confirmation nobody can give yet. That is invariant 8 behaving
as written (untrusted by default, fail closed), and it is also the moment
the confirm-surface override stopped being a nice-to-have: it is now the
only door out of a verdict this machine can produce (A65).

- tests: `bash ops/ralph/runtests.sh jv-guard` — 33 (was 6), written
  first and red before the modules existed. Five mutations run through
  them: authority rule removed (any engine counts) → the two fail-closed
  tests FAIL; entropy measured on all sections → the data-section test
  FAILS; no minimum measurable size → the 256-byte-section test FAILS;
  heuristic promoted over a signature hit → six FAIL; threshold dropped to
  5.0 → the calibration test FAILS. That last one is the one to keep: it
  measures /bin/sh (6.13 over 1.2 MB of real compiled code) and asserts it
  sits under the threshold, so the constant cannot quietly drift down into
  ordinary binaries. Two of the new tests are end-to-end against a real
  jarvisd: a packed PE publishes `suspicious` on the bus with both engines
  in `scanned_by`, and the same PE with ClamAV broken publishes nothing at
  all. `... runtests.sh jv-compat` — 9, `... runtests.sh pylib` — 4, both
  unchanged (nothing outside jv-guard imports these types).
- build: `nixos-rebuild build --flake .#ares` ok. Never test/switch. No
  schema change (`suspicious` was already in the frozen enum — this is the
  first thing that can put it there), no jv-act change, no boot path, no
  NVIDIA/kernel/flake pin.
- files: services/jv-guard/jv_guard/pe.py (new),
  services/jv-guard/jv_guard/heuristics.py (new),
  services/jv-guard/jv_guard/scan.py, services/jv-guard/jv_guard/service.py,
  services/jv-guard/jv_guard/main.py,
  services/jv-guard/tests/test_pe_heuristics.py (new),
  services/jv-guard/tests/test_guard.py
- next: **A66 is now honest and cheap** — `GuardPlate`'s `warn` branch has
  a real producer, so the thirteenth contact-sheet shot A61 stopped itself
  from taking can be taken from frames `jv-guard` really publishes. **A65
  is the one a human should see first**: the override path is no longer
  theoretical, it is the only exit from a verdict this machine now
  produces. A62 (does the corner need a grammar for "these two plates are
  unrelated") and A63 (a crowded-corner shot, which wants A62 answered)
  unchanged. A60/A50/A55/A47/A56/A59 still want a decision; A21/A22/A25/
  A27/A31/A38/A39 still want a human at ares. **B10/A28 — one live
  recording of one spoken turn on ares — remains the biggest thing a human
  can hand this loop.** B7/B12/B15/B17/B20/B23 unchanged.

## 2026-09-24 — iteration 55 — A66: the colour that had no producer gets
## its photograph

- built: **`docs/hud/13-suspicious.png` — the sheet's first picture of the
  approved policy's middle rung, plus the gate that keeps it a picture of
  something real.** A61 stopped itself from taking this shot for a good
  reason: `decide()` could return `clean` or `blocked` and nothing else,
  so `GuardPlate`'s `warn` branch was a colour no frame on this machine
  could light, and photographing it would have put an intention into the
  one sheet whose entire value is that it is not one. A64 gave it a
  producer. This is the picture.

It is the same element as `10-guard.png`, one word and one colour apart —
`SUSPICIOUS` in `warn` where that one says `BLOCKED` in `risk` — and the
file in it is deliberately not malware. A decade-old widescreen patch for
a game, which its author ran UPX over to make it one small download,
`nfs2se-widescreen-patch.exe`. ClamAV recognises nothing in it. It is also,
byte for byte, shaped exactly like something hiding: an executable section
with no bytes in the file and 512 KiB of virtual space to unpack into, a
second one that is both writable and executable, and that one's payload at
7.98 bits of entropy. `blocked` would be a lie about this file and `clean`
would be a promise nothing here can make, which is the whole argument for
a middle rung, on a screen for the first time.

**A66's premise was half wrong and the shot is better for it.** The item
said the long reasons would be "a real test of the plate's wrapping".
They are not tested by this picture at all, because they reach no pixel:
`core/GuardState.qml` never reads `reasons` — `schemas/guard.verdict.json`
says they are spoken on request, and they are the one string on this topic
written by a scanner rather than fixed by a schema. What the picture
actually tests is the thing A66 was really after: that the warn branch
renders, and that the name of a real-world file fits the plate (27
characters, ~211 px of a 240 px cap — not elided, and close enough to the
cap that the next shot of a long name will be the one that finds it).
The three sentences are quoted in `docs/hud/README.md` instead, where a
reader can see what the machine has to say when asked.

**The frame is composed and its words are not, and that is the part worth
keeping.** Every other composed frame in this sheet is a shape somebody
reasoned out; this one is a quotation from another service, which is a
kind of claim a hand-typed literal has no business making. So
`tools/tests/test_hudshots.py` builds a PE of exactly the UPX shape — with
jv-guard's own fixture builder, not a copy of it — runs the real
`PEHeuristicScanner` and the real `decide()` over it, and compares the
verdict, all three reasons and `scanned_by` to the literal in the scene.
The payload is a fixed sha256 chain rather than `os.urandom`, because the
reason string carries the entropy to two decimals and the gate needs the
same bytes every run; the 8 KiB zero tail is there because a real packed
section is payload plus unpacker stub plus alignment slack, and a fixture
measuring a flat 8.00 would have put a number in the sheet that no real
binary produces.

Note what `scanned_by` in that frame says: `clamav` **and** `pe-shape`,
always both. The shape engine is advisory — it may raise suspicion and may
never grant trust — so `decide()` returns nothing at all unless an
authoritative engine ran, and a `suspicious` verdict is by construction two
engines' work. A composed frame naming one engine would have been a frame
describing a policy this machine does not have.

- tests: `bash ops/ralph/runtests.sh tools` — 132 (was 129). Five mutations
  run through the new gate, in both directions: the entropy digits changed
  in the scene (7.98 → 7.96) FAIL; `scanned_by` reduced to the advisory
  engine alone FAIL; the verdict word changed to `blocked` FAIL; "at run
  time" → "at runtime" in the scene FAIL; and — the one that matters most —
  a comma added to the wording inside `jv_guard/heuristics.py` itself FAILS
  the tools suite, which is the proof that the gate points at the real
  producer and not at its own copy of it. `bash ops/ralph/hudshots.sh` — 13
  shots, the other twelve byte-identical, plus tst_sequence's 11 unchanged.
  `... runtests.sh jv-guard` — 33, untouched. `... qmltest.sh` — 536,
  untouched.
- build: `nixos-rebuild build --flake .#ares` ok. Never test/switch. No
  schema change, no jv-act change, no boot path, no NVIDIA/kernel/flake
  pin. jv-guard's source was not modified — the tools test imports it read
  only, the way the other sheet gates read `shell.qml`.
- files: docs/hud/13-suspicious.png (new), docs/hud/README.md,
  tools/hudshots/scene/tst_shots.qml, tools/tests/test_hudshots.py
- next: **A65 is now the item with a picture attached** — the sheet shows an
  install stopped in front of a door with no handle, and a human choosing
  (a) wire the override through `ConfirmPlate`, (b) leave it refusing, or
  (c) tune which concerns reach `suspicious` is the only thing that opens
  it. A62 (does the corner need a grammar for "these two plates are
  unrelated") still gates A63 (the six-or-eight-plate fit shot), and A63 is
  now slightly more interesting than it was: shot 13's plate is 230 px wide
  on a 300 px surface, so the crowded corner is a width question as well as
  a height one. A60/A50/A55/A47/A56/A59 still want a decision;
  A21/A22/A25/A27/A31/A38/A39 still want a human at ares. **B10/A28 — one
  live recording of one spoken turn on ares — remains the biggest thing a
  human can hand this loop.** B7/B12/B15/B17/B20/B23 unchanged.

## 2026-09-24 — iteration 56 — A67: the sheet stops quoting services that could not have said it

A66 closed the gap for one frame: a composed picture of a `suspicious`
verdict, held to what jv-guard really produces for a binary of that shape.
A67 was the observation that it is not the only frame in the sheet that
puts words in another service's mouth — `05-confirm.png` carries a question
jv-act asks, `08-action.png` a tool call and one of jv-act's error words,
`06-health.png` jv-brain's rung, `11-install.png` and `12-guard-install.png`
jv-compat's lifecycle — and that nothing checked any of them. The README
labels each shot `recorded` or `composed`, and that label is a claim about
PROVENANCE, not about plausibility: it says nobody recorded this, and says
nothing at all about whether the named service could ever have said it.

**Four gates, all reading producers rather than running them.**
`jv_brain.config.LADDER` and `jv_compat.fingerprint` are imported;
`jv_compat/install.py` is parsed for its event vocabulary and for the extra
fields each call site attaches; jv-act's registry is TOML and its Rust is
read for the tool names, argument names, capabilities, error words, the
confirmation window, the `kind` literal and the question's format string.
Nothing here is a service talking to a service (invariant 1) and nothing
was written into `services/jv-act` — it is read, the way the older gates in
this file read `shell.qml`.

**The refusal in shot 12 is the gate worth copying.** The first version
compared jv-compat's `blocked` error to `"; ".join(reasons)` computed in the
test, and a mutation that made `install.py` prefix the sentence with
`clamav: ` went straight through green — a copy of a rule is a rule that
drifts, which is the exact failure this file exists to catch. It now lifts
every `error=` expression out of the three `blocked` call sites with `ast`
and evaluates jv-compat's own code over the verdict jv-guard is shown
giving in the same picture. Both directions fail now.

**Three frames were wrong, and all three in `08-action.png`.** The intent
passed `args.name` where the registry declares `app` — the real jv-act
answers `invalid_args` and never reaches an executor. It omitted the
`needs_confirmation` jv-brain always derives from the capability. And the
detail quoted `exec: "obsidian": executable file not found in $PATH`, which
is a Go runtime's sentence about execing a binary directly; jv-act is Rust
and `app.launch` plans `gtk-launch -- <app>`, so it never execs the
application at all. Not one of the three reaches a pixel, which is exactly
why they survived thirteen shots and five iterations of looking at this
sheet: the picture was right and the machine behind it was fiction.

**The one that changed on screen is `05-confirm.png`, and it got worse,
which is the point.** It read *move 14 files in ~/Downloads to the trash*.
jv-act does not compose a sentence about the invocation — `service.rs`
sends `format!("{} — yes or no?", spec.description)`, which is the tool's
REGISTRY description plus a fixed tail: the same question for every
invocation of that tool, forever. The old frame was a picture of a machine
that tells you what it is about to touch, and this one does not have that
machine. A21's human is now judging the question that will really be on
screen. It also makes a genuinely new thing visible, which is logged as
A68: a confirmation that cannot name its object may be one a user cannot
answer, and whether that is jv-act's summary to widen (its own commit,
human-reviewed) or the HUD's `args` to draw (privacy: `args` is content,
not vocabulary, and no core element may name it today) is a decision.

The scene and the README now also say, for this sheet, what
`tools/hudscreens/sheet.py` has said since A49: `fs.trash` is not in
jv-act's registry. v0 is observe+benign only and the confirmation rule is
structural, so no tool on this machine could produce an `action.confirm` at
all; asked for `fs.trash` the real jv-act answers `unknown_tool`. The
machinery is built and reviewed and the tool it is holding is not granted.
A test fails if the disclaimer leaves, and fails with "good news, delete
this branch" if the registry ever gains the tool.

**What is deliberately still only plausible**, said per shot in the README
rather than pinned: free text. An installer's stderr (11), a service's
`notes` (06), the composed registry description (05) and gtk-launch's
not-found message (08). Those are shaped like the real thing and are not
the real thing, and no reviewed source in this repo fixes them.

- tests: `bash ops/ralph/runtests.sh tools` — 136 (was 132). Fifteen
  mutations run through the new gates, in both directions. From the scene:
  an event jv-compat does not publish, a `prefix_created` carrying an
  `error`, an arch the fingerprinter cannot report, a refusal reworded, a
  CPU rung claiming the GPU, a rung off the ladder, an arg the registry
  does not declare, a `needs_confirmation` the capability denies, a detail
  naming a program jv-act never runs, a window jv-act does not open, a
  question jv-act cannot compose, the disclaimer leaving — twelve, each
  failing exactly one test. From the producers: jv-compat renaming a
  lifecycle event, rewording a refusal, shortening its stderr tail, the
  fingerprinter renaming an arch, and the ladder's floor moving onto the
  GPU — five, each failing the tools suite, which is the proof these point
  at the real producers and not at copies of them. All producer files were
  restored from backups and `git diff -- services/` is empty. jv-act was
  mutation-tested by READING only (guardrails: never modify it); what the
  gate parses out of it was printed and checked by hand instead — registry
  11 tools, error words {capability_mismatch, confirm_timeout, denied,
  execution_failed, invalid_args, timeout, unknown_tool}, window 15.0,
  kind `request`, format `{} — yes or no?` from `spec.description`,
  `app.launch` → `gtk-launch`.
- `bash ops/ralph/hudshots.sh` — 13 shots + 11 sequence assertions; only
  `05-confirm.png` changed, the other twelve byte-identical.
  `bash ops/ralph/qmltest.sh` — 536, untouched.
- build: `nixos-rebuild build --flake .#ares` ok. Never test/switch. No
  schema change, no jv-act change, no boot path, no NVIDIA/kernel/flake
  pin.
- files: docs/hud/05-confirm.png, docs/hud/README.md,
  tools/hudshots/scene/tst_shots.qml, tools/tests/test_hudshots.py
- next: **A68 is the new one and it is a human's** — the confirmation
  question is generic by construction, and a picture of it now exists to
  argue over. A62 (does the corner need a grammar for "these two plates
  are unrelated") still gates A63. A65/A60/A50/A55/A47/A56/A59 still want a
  decision; A21/A22/A25/A27/A31/A38/A39 still want a human at ares.
  **B10/A28 — one live recording of one spoken turn on ares — remains the
  biggest thing a human can hand this loop**, and it would retire the
  composed half of four shots at once. B7/B12/B15/B17/B20/B23 unchanged.

## 2026-09-24 — iteration 57 — B23: the one report line whose width a publisher got to choose

B22 (iteration 51) made "every line `jv tap` writes as a REPORT fits 80
columns" a test, and B23 wrote down the line it could not reach: the
per-frame hop line, formatted in `bin/jv.rs` while the test walks what
`cli.rs` renders. Closed it, and the hole under it turned out to be real
rather than cosmetic. `{topic:<20} {src:<12}` PADS and does not truncate,
and `validate_envelope` bounds a topic's alphabet and a src's emptiness
and NEITHER one's length — so the width of that line was chosen by a
remote process. Not hypothetically either: `jv-hud-bridge` is 13
characters and was already one past its column.

The line is `cli::hop_line` now, beside the `HopStats` that accumulates
it, and both strings are CLIPPED at named columns rather than assumed.
The marker is `short_id`'s own `...`, which is why `short_id` collapsed
into the `clip(s, columns)` it always was — one tested behaviour instead
of two.

`TOPIC_COLUMNS` = 22 serves BOTH views of a topic, the per-frame stream
and the summary table under it, and that is the decision worth recording:
the value of either view is that its columns line up, and a label wider
than its column breaks the table's alignment in exactly the way it breaks
the stream's budget, so one cap answers both. The stream grew from 20 to
22 to meet the table, so the two agree for the first time. The cost is
`short_id`'s cost, stated in the same place: two topics sharing their
first 19 characters print alike, and the whole topic is one `jv sub '*'`
away — that view prints frames, which are raw data and are as wide as
they are. `SRC_COLUMNS` = 13 is `jv-hud-bridge`.

**What is assumed rather than enforced**, said out loud the way
`every_line_a_turn_prints_fits_eighty_columns` says its own: `seq` is
eight digits and the hop is eight columns, which leaves this line 16 of
the 80 spare. A ten-digit seq (4.2e9 frames) and a 99-second hop both
still fit. A hop wide enough to break it is a publisher stamping
wall-clock `ts` on a monotonic bus, and printing that number WHOLE is the
report — clamping it or hiding it behind a `?` would suppress the one
signal it carries.

- tests: `cargo test` — 125 lib (was 124) and 39 e2e, green. **Nine
  mutations, all caught, and deliberately split across the two files**,
  because the two halves of this claim are not provable in the same
  place. Against the new unit gate: dropping the topic clip, dropping the
  src clip, the table ROW keeping its own 20-wide column, the table
  HEADER keeping its own, `clip` taking `columns` characters without
  saying it cut anything, and `hop_line` reverting to 20/12 — six, each
  failing it. Against the e2e: `bin/jv.rs` keeping its own `format!`,
  deleting the streamed line entirely, and swapping topic and src into
  each other's columns — three, each failing
  `a_turn_is_reported_split_at_the_boundaries_jv_ears_published`.
  **The honest finding from doing it this way**: a width assertion ALONE
  does not catch the call-site revert, because every topic a real bus
  carries fits either column, so the old `format!` passes at 61 columns.
  That is why the e2e pins WHERE the columns fall and not just how many
  there are — and it is the same reason the first version of the
  alignment assertion survived M3: the table's next field is right
  aligned, so a narrower column and a wider pad are the same string, and
  only the character past them tells the two apart.
- verified on the BUILT binary against a real broker, not only in tests:
  `sys.health             jarvisd       seq=1        hop=    0.19ms` at
  64 columns, over a 61-column table, the topic flush in the same column
  in both.
- build: `nixos-rebuild build --flake .#ares` ok. Never test/switch. No
  schema change, no jv-act change, no boot path, no NVIDIA/kernel/flake
  pin.
- files: services/jarvisd/src/cli.rs, services/jarvisd/src/bin/jv.rs,
  services/jarvisd/tests/cli.rs
- next: "every report line fits" is now closed for every line the tap
  writes, so **B17/B20 are what is left of the B-track width work and
  both are a human at a terminal** — does four lines per tool turn read
  as a decomposition or as noise. They share their trigger with B10/A28,
  **one live recording of one spoken turn on ares, still the biggest
  thing a human can hand this loop**. B15 wants the decision B13 left
  open; B7/B12 wait on a consumer and on `sys.roster`. On the A track
  A62 still gates A63; A65/A60/A50/A55/A47/A56/A59 want a decision and
  A21/A22/A25/A27/A31/A38/A39/A68 want a human at ares.

## 2026-09-24 — iteration 58 — B24: the measurement table stops being able to print one name twice

B23 gave the topic ONE cap — `TOPIC_COLUMNS` = 22 — serving both views of
a topic, the per-frame stream and the summary table under it, because the
value of either is that its columns line up. B24 was written the same
iteration as the consequence of that: a clip is a promise that what it
hid is one `jv sub '*'` away, and two topics sharing their first 19
characters print alike.

That promise is good enough for the STREAM. Every line there is about one
frame that named itself, and the frame is one `jv sub '*'` away whole.
It is not good enough for the TABLE, where a row is about a topic and the
label is the only thing that says which — so two topics collapse into two
rows of numbers under one name, and there is nothing in the output that
says it happened. The plan item made the ranking the fix had to encode:
a measurement table whose rows cannot be told apart is worse than a wide
one. **Identity outranks alignment here, and only here.**

`table_topic_columns(&[&str])` is the whole change: the smallest width
from `TOPIC_COLUMNS` up at which every PRINTED label is distinct. Three
properties worth stating rather than reading out of the loop:

- **It grows by the smallest amount that works**, so the 80-column budget
  is spent only as far as identity needs. The pair in the test separates
  at 27 and not at 26, and 27+39 = 66 still fits.
- **The search always finds a width**, so the `expect` is not a hidden
  panic: the topics are the keys of a map, and at the longest one's own
  length nothing is clipped, so every label is its whole distinct topic.
- **Printed labels are compared, never the topics.** Comparing topics is
  tautological — map keys are distinct, so the column would never grow —
  which is mutation M6 and it was caught. The other half of that argument
  I had to correct mid-iteration: I first wrote that a clipped label can
  collide with a WHOLE one "since this bus's alphabet allows `...`". It
  does not. `validate_envelope` refuses an empty topic SEGMENT, so no
  topic the broker accepts ends in two dots and that collision cannot
  reach a live tap. The test for it is kept and now says so: nothing else
  in this width code assumes the topic alphabet, and this should not be
  the one place that does.

**The trade is pinned where it costs something.** Every other report line
this CLI writes fits `TAP_COLUMNS` at its worst input (B22/B23); this one
deliberately does not, when a distinguishing character sits past column
41. A test builds that case and asserts the rows are OVER the budget — so
the day someone tightens the width gate, they are told which rule they
are about to reverse instead of discovering it as a collapsed table.

- tests: `bash ops/ralph/cargotest.sh jarvisd` — 128 lib (was 125) and 39
  e2e, green. **Seven mutations, all caught**: rows reverting to the fixed
  cap while the header moves, the header keeping its own column while the
  rows move, the column never growing, it always growing by one (caught by
  the real-bus case, which must stay at exactly 22), it jumping straight
  to the widest topic instead of searching, it comparing topics instead of
  printed labels, and growth capped at the 80-column budget (which turns
  the `expect` into the panic that proves the cap is load-bearing).
- verified on the BUILT binary against a real broker, not only in tests:
  four frames on `context.window.changed.alpha` / `.beta`, published with
  `jv pub`, tapped with `jv tap --latency`. The table printed
  `context.window.changed.a...` over `context.window.changed.beta` at 27
  columns; before this commit both rows read `context.window.chan...`.
- **the honest finding from looking at that output**: the four STREAM
  lines above the table are still four identical labels, and the table's
  column no longer starts the run of columns the stream's does — the two
  views diverge in exactly the case where the table had to widen. That is
  the documented trade and it is also new information, because the stream
  cannot do what the table did: a line printed as a frame arrives cannot
  know which topics will show up later. Written up as B25.
- build: `nix build .#jarvisd` ok (it runs the tests too);
  `nixos-rebuild build --flake .#ares` ok. Never test/switch. No schema
  change, no jv-act change, no boot path, no NVIDIA/kernel/flake pin.
- files: services/jarvisd/src/cli.rs
- next: **B25 is the stream half of what B24 just closed for the table**,
  and unlike B24 it has no cheap answer, so it is written down rather than
  built. The B track's remaining items are otherwise unchanged: B17/B20
  are a human at a terminal and share their trigger with B10/A28 — **one
  live recording of one spoken turn on ares, still the biggest thing a
  human can hand this loop**. B15 wants the decision B13 left open; B7/B12
  wait on a consumer and on `sys.roster`. The A track is where the value
  is and it is almost entirely blocked on people: A62 gates A63;
  A65/A60/A50/A55/A47/A56/A59 want a decision and
  A21/A22/A25/A27/A31/A38/A39/A68 want a human at ares.

## 2026-09-24 21:05 — the approved no-wake window finally opens (B26)

**Nothing consumed `dialog.listen`.** jv-act publishes it on every
confirmation (`service.rs:332`, alongside the `action.confirm` request),
jv-brain publishes it for every onboarding and follow-up question
(`service.py:602`), the schema has been frozen since Phase 2 stretch 0,
`DECISIONS-approved.md` records the design decision that created it — and
`grep -rn dialog services/jv-ears/` returned nothing at all. jv-ears
subscribed to `speech.state` and to nothing else. So every answer to
"delete this file — yes or no?" has needed "hey jarvis" in front of it,
and the one approved exception to wake-every-time existed as a topic two
services shouted into an empty room.

It is the kind of gap that is invisible from either end: jv-act's tests
assert it PUBLISHES the frame and pass; jv-ears' tests assert the wake
gate HOLDS and pass; the feature is missing in the space between two
green suites. I went looking for it because `schemas/dialog.listen.json`
says of its `reason` field "the HUD will show it (sensor truthfulness,
invariant 10)" — a HUD obligation nothing had built — and found the
consumer underneath it missing too.

**What it does.** `jv_ears/dialog.py` holds the window on the sample
clock, like every other decision in this service, so a replayed fixture
produces the same events every time. The pipeline advances it once per
chunk and an utterance that STARTS inside the window is gated without a
wake.

Three rules, each of which had a plausible alternative I rejected:

- **Only time closes the window.** Not the first utterance in it. The
  approved decision is that the REQUESTER interprets transcripts and ears
  never learns what "yes" means; a window that shut itself after one
  utterance would be ears deciding the answer had arrived — the same
  interpretation, moved into the perception service, and wrong exactly
  when the user's first sound is "um". The cap is what keeps it safe, and
  the cap is the schema's own 60 s, read from the frozen file by a test.
- **It governs where you may START speaking.** A window expiring
  mid-sentence does not throw the sentence away (the VAD already bounds
  the recording), and a window opening mid-sentence does NOT reach back.
  The wake path gates retroactively because "hey jarvis" lives inside the
  utterance it belongs to; a no-wake window has no such excuse — those
  words were spoken before any service asked for them.
- **Half-duplex still outranks it.** Not an edge case: jv-act publishes
  the request while jv-voice is still speaking the question, so the
  window is open for seconds during which the only voice in the room is
  Jarvis's own.

**Every refusal points the same way** — an unreadable frame leaves the
microphone exactly as wake-gated as it found it. Unknown body version
(a v2 body means whatever v2 says), hedged `conf` on a command topic
(the schema says 1.0; a producer that is not sure does not get a mic),
unaudited `reason`, non-object body, empty `listen_id`, and a
`window_s` that is not a bounded positive number — `True` included,
because it is an `int` in Python and `True * 16_000` looks like a fine
window. The required-field test is parametrised over the SCHEMA's own
`required` list, so the day `dialog.listen` gains a fourth field this
fails until ears validates it.

The bus→pipeline hand-off is a deque, not a slot: `append`/`popleft` are
atomic under the GIL and a read-then-clear attribute is not, and a
request lost in that race is a microphone that stayed shut while a
service waited on it.

- tests: `bash ops/ralph/runtests.sh jv-ears` — **104 (was 37)**, green.
  58 of them need no models (the window's decisions, and the wire through
  `main.amain` over a fake bus); 9 are the same fixture WAV with and
  without the frame. **13 mutations, all 13 caught**: the window never
  gating, never expiring, reaching back into speech already in flight,
  its deadline cutting off a sentence under way, a later request
  shortening it, the schema cap unenforced, the hand-off as a slot, the
  four validation clauses deleted one at a time, ears dropping the topic,
  main forwarding only the body (which would make the `conf`/`v`
  refusals unreachable from the bus), and ears never subscribing.
  Also: `harness` 88, `tools` 136, `pylib` 4 — unchanged and green.
- **verified on the built closure against a real broker**, not only in
  tests. `speech-no-wake.wav` — a real utterance nobody addressed to
  Jarvis — through the SHIPPED `jv-ears` from
  `nixos-system-ares…/etc/systemd/user`, on a real `jarvisd`: with no
  frame, `jv sub audio.transcript` printed nothing, exactly as it always
  has. With `jv pub dialog.listen --src jv-act
  --body '{"listen_id":"ralph-e2e","window_s":30,"reason":"confirm"}'`,
  the same audio produced four partials and a final —
  "The quick brown fox jumps over the lazy dog." — at conf 0.90.
- **one process note worth keeping.** The first `nixos-rebuild build`
  passed while building the OLD jv-ears: `dialog.py` was untracked, and a
  flake's source is git's. The build gate is only a gate on files git can
  see — `git add` BEFORE the build, or it verifies the previous commit.
  Confirmed by listing `jv_ears/` inside the built env both times.
- build: `nixos-rebuild build --flake .#ares` ok. Never test/switch. No
  schema change, no jv-act change, no boot path, no NVIDIA/kernel/flake
  pin.
- files: services/jv-ears/jv_ears/dialog.py (new),
  services/jv-ears/jv_ears/pipeline.py, services/jv-ears/jv_ears/main.py,
  services/jv-ears/tests/test_dialog_listen.py (new),
  services/jv-ears/tests/test_no_wake_window.py (new)
- commit: 4c4d350
- next: **B27 is the HUD half and it is now the loop's own to take** —
  the schema says the HUD will show the reason, and the microphone is
  open without a wake word, which is precisely what invariant 10 exists
  for. The obstacle is real and is written into the plan: `dialog.listen`
  is a REQUEST, and a HUD that drew it would be showing what a service
  asked for rather than what the microphone is doing — the fakeable
  indicator invariant 10 forbids. Only jv-ears can say the window
  actually opened, and its heartbeat is 5 s against a 15 s window. B28
  is the smaller companion: the window is invisible to `jv health` and to
  the audit for the same reason. Everything else is where it was — the A
  track is still almost entirely blocked on people (A62 gates A63;
  A65/A60/A50/A55/A47/A56/A59 want a decision; A21/A22/A25/A27/A31/A38/
  A39/A68 want a human at ares), and B10/A28 — one live recording of one
  spoken turn — is still the biggest thing a human can hand this loop.

## 2026-09-24 — iteration 60 — B29: the window list niri sends first,
and nothing ever read

The A track is still almost entirely blocked on people, and so is most
of B: B27/B28 share one human decision (an `ears.listen` topic or not),
B7/B12/B25 are each explicitly "not until something reads it", and
B10/B17/B20/A28 want two minutes of a human at ares. So I went looking
in the code instead of the plan, and the first thing I read — the niri
backend, the one part of jv-context that only ever runs on the machine
— had **no tests at all** and handled three of the four window events
its own docstring listed.

The missing one is `WindowsChanged`, and it is not a corner case: it is
niri's complete window list, and **I verified on ares today that it is
the third line of a live event stream**, before any event at all. It
listed the 3 windows that were open, exactly one of them focused. The
old parser threw all of that away, so on any desktop where anything was
open before jv-context started:

  * the FIRST event about every pre-existing window said `opened`. You
    have Firefox up all day, you switch tabs, and jv-brain is told
    Firefox just opened.
  * a `WindowClosed` or `WindowFocusChanged` for one of them carried
    `app_id: ""`. `schemas/context.window.json` says focus_changed
    frames are what jv-act resolves "this"/"the active window" against
    — so "close this" resolved to a window with no name.
  * nothing said which window had focus until the user switched one.

**The rule, and it is the whole design: events are forwarded; a RESYNC
publishes only what it CHANGES.** A state dump has no timestamps in it,
so it may not emit `opened` for a window that predates this process (it
cannot date it) and may not emit `closed` for the difference between
two lists (it cannot say when they went, and niri sends `WindowClosed`
for the ones it saw go). What it may do is seed the cache — which is
what lets every later frame NAME a window that predates the service —
and, when it names a focused window nothing has reported yet, publish
the one `focus_changed` that makes "this window" resolvable at all.
Deduped against the last focus reported, so a second resync that agrees
is silent.

Two decisions worth writing down because both had a defensible
opposite. `WindowFocusChanged {id: null}` — niri's "nothing has focus
now" — publishes NOTHING: `window_id` is required and `minimum: 0` in
the frozen schema, and there is no way to say it without a schema
change I am not allowed to make. But it must still be FORGOTTEN
internally, or the next resync dedups against an answer that expired;
a mutation proves it. And the resync's `focus_changed` is the one frame
here that could be argued as invented — focus did not change at that
instant, jv-context merely learned it. I took it because the schema's
own description makes focus_changed the frame that DEFINES the active
window, and the alternative is jv-act having no answer to "this" until
the user happens to switch. It is cheap to revert and it is in the plan
as B30 for a human to veto.

Privacy: the resync is the first thing that ever put real window titles
in this process, so the cache holds them raw and `redact_title` runs at
publish exactly as before. Two tests say a password manager that was
already open is redacted the same as one opened later, and a private
browsing title learned from a resync never reaches a body — asserted
here because seeding the cache is what made that path reachable at all.

- tests: `bash ops/ralph/runtests.sh jv-context` — **41 (was 13)**. The
  niri parser had ZERO coverage before this. `events()` itself — the
  `"EventStream"` handshake, the JSON-lines framing, one parser state
  carried across lines, a malformed line skipped — is now driven over a
  real unix socket by a fake niri. **Eight mutations, all eight
  caught**: the resync not handled at all, the resync reporting every
  listed window as `opened`, merging instead of replacing the list,
  publishing focus unconditionally, `id: null` not forgotten, a closed
  focused window still remembered as focused, `is_focused` on
  `WindowOpenedOrChanged` not tracked, and a resync never clearing a
  stale focus.
- **field-verified against the live niri-26.04 on ares**, read-only
  (connect, request, read, disconnect — no `niri msg action`). The wire
  answered: the reply is `{"Ok": ...}`, then `WorkspacesChanged`, then
  `WindowsChanged`; `struct Window` carries `app_id, focus_timestamp,
  id, is_floating, is_focused, is_urgent, layout, pid, title,
  workspace_id`, `id` an int, `app_id`/`title` on every entry; and
  `Ok`, `WorkspacesChanged`, `KeyboardLayoutsChanged`,
  `OverviewOpenedOrClosed`, `ConfigLoaded`, `CastsChanged` all arrive
  within three seconds on a desktop nobody is touching — every one of
  them now a fixture in the passed-over list, because a parser that
  tripped on any of them would take jv-context down at startup. Only
  structure was read out of the live session; no window title was
  printed, kept or committed. The half a quiet capture cannot show —
  the per-window events, and whether niri ever resyncs mid-session —
  stays a TODO(machine) in the docstring, now stated precisely.
- **the live session also found a bug in my own test.** `NiriBackend("")`
  falls back to `$NIRI_SOCKET`, and this loop runs inside the user's
  niri session, so the "no socket is an error" test connected to the
  REAL compositor and blocked until it was killed. `monkeypatch.delenv`,
  and the reason is in the docstring: a test that reaches the machine it
  runs on is not a test. Worth remembering for every other service whose
  seam reads an env var.
- build: `nixos-rebuild build --flake .#ares` ok, with `git add` BEFORE
  it (iteration 59's lesson) — and the SHIPPED closure was then asked to
  translate a resync, so "the new parser is in the built system" is a
  reading and not an inference. Never test/switch. No schema change, no
  jv-act, no boot path, no NVIDIA/kernel/flake pin.
- files: services/jv-context/jv_context/compositor.py,
  services/jv-context/tests/test_niri_events.py (new)
- commit: f00273f
- next: **B30 is the one thing here a human should look at** — the
  resync's `focus_changed`, which is the only frame in this service that
  reports a state rather than a transition. B31 is the bigger find and
  it is not mine to take: `context.window` has a `workspace` field and a
  `monitor` field and the niri backend has never populated either, while
  niri's `Window` carries `workspace_id` (an id, not the name the schema
  wants) — resolving it needs `WorkspacesChanged`, which is the next
  event down this same socket. Everything else is where it was: A is
  blocked on A62/A65/A68/A47/A56/A50/A60 (decisions) and A13/A21/A22/
  A25/A27/A31/A38/A39 (a human at ares), B27/B28 share one decision, and
  B10/A28 — one live recording of one spoken turn — is still the biggest
  thing a human can hand this loop. Though today's session is a reminder
  that the loop IS on ares now: read-only field verification against the
  live machine is available and was worth more than any test I wrote.

## 2026-09-24 — iteration 61 — B31: the two fields that said where a
window is, empty since the schema was frozen

B29 (last iteration) ended by pointing at this and calling it the bigger
find. It is: `schemas/context.window.json` has carried a `workspace`
field and a `monitor` field since v1, frozen, documented — and **no
publisher has ever put a value in either**. Two things fall out of that
emptiness. jv-act's registry has a `window.move_workspace` tool whose
`workspace` argument is a REQUIRED string, and nothing on the bus could
supply one. And the A track has asked three times (A13/A27/A38) what a
HUD with three monitors should do, always concluding there is no bus
data behind the question — there wasn't.

Not a schema change: both fields are already frozen in, and the generated
binding already had them. The obstacle was a real mismatch. niri's
`struct Window` carries a `workspace_id` — an integer — and the schema
wants a NAME. The name lives in `Event::WorkspacesChanged`, which is
B29's shape one level out: a list, authoritative, unread.

**Field-verified on ares first, read-only** (connect, request, read,
disconnect — no `niri msg action`, nothing printed but structure). What
the live compositor answered decided the design:

  * `WorkspacesChanged` is line TWO — `Ok`, then it, then
    `WindowsChanged`. So the workspace table is populated BEFORE the
    first window is ever listed, and the very first frame jv-context
    publishes can already say where that window is. No deferral, no
    second pass, no frame that has to be corrected later.
  * `struct Workspace` carries `active_window_id, id, idx, is_active,
    is_focused, is_urgent, name, output`. Four workspaces were up.
  * **`output` was a connector string on every one** (`DP-1`, `DP-2`,
    `HDMI-A-1` twice — the three monitors in CLAUDE.md).
  * **`name` was null on every one.** Ofek has never named a workspace.
  * **`idx` is per-OUTPUT.** Three of the four were `idx: 1`.

That last pair is the whole design decision. The tempting move —
"unnamed? publish the index" — would name three different workspaces
"1" at the same instant, and that string is exactly what
`window.move_workspace` would act on. So: the name is published when
niri reports one and the field is ABSENT when it does not, and the
monitor is published either way. An unnamed workspace still says which
screen it is on, which is the half this machine can actually answer.
A test says the index is never used, and it says why.

The rest follows B29's rules deliberately. The workspace table is
authoritative and replaced wholesale (unplugging a monitor moves
workspaces between outputs and niri restates the list; a merge would
keep publishing a window on a screen that is no longer there). It
publishes NO frame of its own — no window did anything, and
`context.window` has no vocabulary for "a workspace moved". And every
frame is placed at PUBLISH time through one door (`_frame`), against the
table as it stands now, so a close and a focus — events that carry an id
and nothing else — say where the window was just as accurately as a
resync does. The window cache became a record with a `workspace_id` on
it, which is what makes that possible.

- tests: `bash ops/ralph/runtests.sh jv-context` — **59 (was 41)**.
  **Twelve mutations, all twelve caught**: `WorkspacesChanged` not
  handled at all, the table merged instead of replaced, `idx` used as a
  name, an absent name suppressing the monitor too, an unknown id
  resolving to empty strings instead of absence, a close built without
  its record, the window record dropping its workspace, a moved window
  keeping its old one, an empty name published as a name, the table
  keyed by `idx`, `monitor` never published, and `monitor` published
  under niri's own field name (`output`) instead of the schema's. One
  test reads the two field names off the GENERATED binding rather than
  spelling them, and asserts both are optional there — absence has to be
  legal for any of this to be honest.
- build: `nixos-rebuild build --flake .#ares` ok, `git add` first. Never
  test/switch. No schema change, no jv-act, no boot path, no
  NVIDIA/kernel/flake pin.
- **verified through the BUILT closure against the live compositor**:
  the shipped `jv_context` (from
  `/nix/store/...python3-3.14.7-env/.../jv_context/compositor.py`, not
  the worktree) was run against the real niri socket, and the workspace
  table came back `{2: (None,'DP-1'), 3: (None,'DP-2'),
  4: (None,'HDMI-A-1'), 1: (None,'HDMI-A-1')}` with the first published
  frame reading `focus_changed / monitor: HDMI-A-1` and **no
  `workspace`** — which is the truth about this desktop and not a
  shortcut. Only structure and connector names were read; no window
  title or app_id was printed, kept or committed.
- files: services/jv-context/jv_context/compositor.py,
  services/jv-context/jv_context/service.py,
  services/jv-context/tests/test_niri_events.py
- commit: 752a834
- next: **B32 is the one to read first and it is a human's**: `workspace`
  will be absent on every frame this machine produces until a workspace
  is NAMED, and `window.move_workspace` needs that string — one line in
  a niri config fixes it, or the schema grows an id (frozen, so review).
  B33 is small and shares B30's question exactly (a frame that reports a
  state rather than a transition — here, restating where the focused
  window is after a monitor is unplugged); decide the two together.
  B34 is the interesting one: A13/A27/A38 now have SOME data behind them,
  though "the screen the focused window is on" is not "the screen you are
  looking at" and the senses that could say the latter are unwired.
  Otherwise unchanged: A blocked on A62/A65/A68/A47/A56/A50/A60
  (decisions) and A13/A21/A22/A25/A27/A31/A38/A39 (a human at ares),
  B27/B28 share one decision, and B10/A28 — one live recording of one
  spoken turn — is still the biggest thing a human can hand this loop.

## 2026-09-24 — iteration 62 — B35: the mixer reading nobody took, and the pump that died saying `ok`

The A track is blocked end to end (A62/A65/A68/A47/A56/A50/A60 want
decisions, A13/A21/A22/A25/A27/A31/A38/A39 want a human at ares) and so
is the front of the B track (B27/B28/B30/B32/B33/B34 are all somebody
else's call), so I went looking in the one publisher the HUD depends on
that nothing had audited: jv-context's 1 Hz system snapshot. Two defects,
both reproduced before a line was written.

**It could invent a reading.** `WpctlProbe.volume()` ended in
`float(parts[1]) if len(parts) >= 2 else 0.0`, so an unreadable sink —
wpctl missing from the closure, wpctl exiting non-zero, wpctl printing
its own error text on stdout, which it does — published
`audio_volume: 0.0, audio_muted: false`. That is not a harmless
placeholder anywhere, and on this machine it is specifically a lie the
HUD repeats: `core/OutputState.qml` reads `audio_volume <= 0` during an
utterance as YOU CANNOT HEAR THIS and lights a plate. A40 built that
plate for the worst-evidenced failure this assistant has, and A41 went to
real trouble making sure it never speaks about a sink jv-voice does not
use — and underneath both, the number itself could be something nobody
measured. Invariant 10 forbids exactly that.

**And it could stop, silently, forever.** `"no such id 42"` is two tokens,
so it passed the length check and `float("such")` raised `ValueError`
straight out of `_pump_system`. That task was never awaited: it died, the
process lived on pumping window events, `Restart=on-failure` never fired,
and `_pump_health` kept publishing `state: "ok"` about a jv-context that
had not published `context.system` since. A service that has stopped
doing half its job and says it is well is the failure mode `jv health`
exists to end.

The three rules, each with a test that dies without it:

- **A probe raises, it does not substitute.** `ProbeUnavailable` for a
  missing binary, a timeout, a non-zero exit, output that is not
  `Volume: <n>`, and a number that is not one — `nan` and `inf` parse as
  floats and are not measurements, and a negative is below the schema's
  own minimum. A real 0.0 still reads as zero; that distinction is the
  whole point.
- **A failed tick publishes NOTHING.** Every field a probe feeds is
  required by `schemas/context.system.json`, so there is no legal partial
  frame — and the two ways of filling the gap both say more than was
  measured: a substituted number is a reading nobody took, and restating
  the last good snapshot dates it NOW. The bus's last word simply ages
  out, which consumers already handle (the HUD stops believing a snapshot
  after three periods, and that clock was written for exactly this).
- **The failure moves to the heartbeat.** `degraded` with a note naming
  the exception, and IMMEDIATELY on the transition — which
  `schemas/sys.health.json` asks every service for ("every fixed period,
  and immediately on state change") and which jv-context had never done;
  on a 5 s beat a service that had just gone blind was up to 5 s of
  silence about itself. Only on the transition, though: a probe failing
  the same way sixteen times running is not news, and a beat per failed
  tick would put jv-context's 1 Hz onto a topic that is meant to be quiet
  (invariant 5). A test pins that the 0.8 s blind window produces exactly
  two beats, `ok` then `degraded`.

The `except Exception` in the pump is deliberate and is the substance of
the fix rather than a shortcut: the property being bought is that no
probe, present or future, can end that loop. What makes a broad catch bad
is silence, and this one is the opposite — every failure ends up on the
bus named by its exception type.

One line of Nix went with it. The unit had no `path` at all, so `wpctl`
was reaching it only by inheritance from the session; it now names
`wireplumber` the way `jv-act` already names the things it shells out to.

- tests: `bash ops/ralph/runtests.sh jv-context` — **82 (was 59)**.
  **Thirteen mutations, all thirteen caught**: an unreadable mixer
  reading as `(0.0, False)`, the `Volume:` word check dropped, the
  nan/negative guard dropped, `OSError` and the timeout uncaught, the
  exit code ignored, `snapshot()` substituting, the pump re-raising (the
  old behaviour), the heartbeat always `ok`, `degraded` with no note, no
  immediate beat on change, a beat per failed tick, the fault never
  cleared when the probe recovers, and a fabricated frame published
  anyway.
- build: `nixos-rebuild build --flake .#ares` ok, `git add` first. Never
  test/switch. No schema change, no jv-act, no boot path, no
  NVIDIA/kernel/flake pin.
- **verified through the BUILT closure on ares**: the shipped
  `jv_context` (from `/nix/store/...python3-3.14.7-env/.../jv_context/
  system.py`, not the worktree) read the live sink through the built
  unit's own `PATH=`, and the same binary with wpctl gone answered
  `ProbeUnavailable: wpctl did not run` instead of zero. A run under
  `env -i` with the unit PATH also produced `wpctl exited 2` — an
  artifact of stripping `XDG_RUNTIME_DIR`, which a systemd *user* unit
  has, and an accidental live demonstration of the new failure path. Only
  a volume float and a mute bool were read; no device name, nothing kept.
- files: services/jv-context/jv_context/system.py,
  services/jv-context/jv_context/service.py,
  services/jv-context/tests/test_context.py,
  modules/jarvis-services.nix, docs/optimization-backlog.md
- commit: dc04e77
- next: **B37 is the one I would take next and it is the loop's own.**
  `gpu_vram_free_mb` has never once been on the bus on ares — measured
  under the built unit's own PATH, where the snapshot came back without
  the field, because `nvidia-smi` is not in the closure either. Nothing
  is lying (the schema makes it optional and the probe already degrades
  to absent), but invariant 6 — "6 GB VRAM is a scheduling problem" —
  has no number behind it, and the fix is the same one line I wrote for
  wireplumber, reading `config.hardware.nvidia.package.bin` from
  `modules/jarvis-services.nix` without touching `gpu-nvidia.nix` or its
  pin. Pair it with backlog item 14, because the day it starts working is
  the day that fork-per-second starts being paid. **B38** is the same
  shape spread over three services: jv-ears, jv-guard and jv-brain still
  beat on a timer alone, so jv-ears' `microphone open but no audio` is up
  to a full period late and `jv health --check`'s 6 s window can miss it;
  `_set_fault` + an Event is the shape to copy. **B36 is a human's** —
  `net_online` is documented as one measurement and published as a much
  weaker one, and fixing it starts by rewording a frozen schema
  (proposal **R8**). Otherwise unchanged: A is blocked on A62/A65/A68/
  A47/A56/A50/A60 (decisions) and A13/A21/A22/A25/A27/A31/A38/A39 (a
  human at ares), B27/B28 share one decision, B30/B33 share another, and
  B10/A28 — one live recording of one spoken turn — is still the biggest
  thing a human can hand this loop.

## 2026-09-24 — iteration 63 — B37: the number invariant 6 is named after

CLAUDE.md invariant 6 is titled "6 GB VRAM is a scheduling problem". The
schema field that carries the number, `context.system.gpu_vram_free_mb`,
describes itself as feeding "the brain's own situational awareness". It
has been absent from every frame ares has ever published.

Nothing was lying, which is why nobody caught it: the field is optional,
the probe degraded to absent, and every consumer that would have read it
was correct to see a machine with no reading. `nvidia-smi` ships in the
NVIDIA driver's `bin` output rather than in jv-context's closure, nothing
named it on the unit path, and so the 1 Hz snapshot raised
FileNotFoundError about 86,000 times a day to learn the same thing. B35
found this by measuring under the BUILT unit's own PATH, which is the
only place the difference between "inherited from my shell" and "what the
service actually gets" is visible — and it is the second time that exact
measurement has found a missing binary in three iterations.

One line of Nix, named the way `jv-llm` already names it: the unit path
gains `config.hardware.nvidia.package.bin`. That READS `hardware.nvidia`;
`modules/gpu-nvidia.nix` and the driver pin are untouched. I first wrote
it with an `lib.elem "nvidia" videoDrivers` guard, then dropped the guard
— jv-llm pulls the same package unconditionally two units down, so the
guard bought nothing and cost the file's coherence. The rebuilt closure
came out at the identical store path either way, which is the cheapest
possible proof that the simplification changed nothing.

The larger half was the probe. `gpu_vram_free_mb` is optional, and I
think the lesson here is that an optional field's ABSENCE is a claim like
any other: the schema says "free VRAM if a GPU is present", so absent has
to mean *there is no GPU*, not *the reading did not work out*. The old
probe returned `None` for both, which is the B35 pathology one level
down — a machine that has a card and lost sight of it looked exactly like
a machine that never had one, and invariant 6's ladder would be flying
blind with nothing anywhere saying so.

So `GpuProbe` answers three ways instead of two: `None` (no card, not a
fault), a float, or `ProbeUnavailable` (there IS a driver and it went
quiet). The third reaches `sys.health` as `degraded` with a note naming
the field — while `context.system` keeps flowing, because the mirror
image of B35 is the point: the mixer feeds a REQUIRED field, so its
failure costs the whole frame; the GPU feeds an optional one, so its
failure must cost exactly that field and never the other four. That
asymmetry is now two tests that would each fail if the other's rule were
applied.

`parse_nvidia_smi_vram` rejects what `float()` would have taken happily:
`[N/A]` and `[Not Supported]` (what nvidia-smi prints when a device
cannot answer), NVML init errors, which arrive on stdout the way wpctl's
do, `nan` and `inf`, negatives, and — the case my first test missed — a
real number printed alongside a NON-ZERO exit, which is what a multi-GPU
box does when one card answers and another does not. That mutation
survived the first round precisely because my fake had also returned
empty stdout; the check I thought I was testing was being made by the
parser. Fixed the fake, not the code.

A missing binary LATCHES the probe off. The PATH is a store path fixed
when the unit started, so "there is no driver here" cannot stop being
true while the process lives, and re-forking once a second to re-learn it
is the pure-waste half of backlog item 14 — gone without touching the
cadence question (how fast should the ladder see a game-launch spike?)
or the pynvml question (a flake dependency), both of which remain the
human's. Backlog 14 is updated to say so, and to say that its cost is no
longer theoretical: as of today the fork returns a number.

- tests: `bash ops/ralph/runtests.sh jv-context` — **105 (was 82)**.
  **Eleven mutations, all eleven caught**: the latch removed (forks
  again), a missing binary raised as a fault, the gpu note dropped, the
  gpu failure allowed to take the whole frame, the finite/negative guard
  dropped, the exit code ignored, empty output read as `0.0`, the service
  ignoring the note, a GPU-less machine reported as degraded, and
  OSError/timeout left uncaught. `pylib` (4) and `tools` (136) green too,
  since `snapshot()` changed shape.
- build: `nixos-rebuild build --flake .#ares` ok, `git add` first. Never
  test/switch. No schema change, no jv-act, no boot path, no
  NVIDIA/kernel/flake pin — `gpu-nvidia.nix` is read, not written.
- **verified through the BUILT closure on ares**: the shipped
  `jv_context` (from `/nix/store/...python3-3.14.7-env/.../jv_context/
  system.py`) read **943 MiB free of 6144** off the GTX 1660 SUPER under
  the built unit's own `PATH=`, cross-checked against nvidia-smi's own
  `name,memory.total,memory.free`. The same binary with nvidia-smi gone
  answered `None` and latched, publishing a whole frame with no note. The
  generated unit file now carries `nvidia-x11-595.91.07-bin/bin` on its
  PATH. Only a free-VRAM integer was read; no process list, no device
  serial, nothing kept.
- files: services/jv-context/jv_context/system.py,
  services/jv-context/jv_context/service.py,
  services/jv-context/jv_context/main.py,
  services/jv-context/tests/test_context.py,
  modules/jarvis-services.nix, docs/optimization-backlog.md
- commit: befd1da
- next: **B39, and it is the sharper half of what B37 uncovered.**
  `jv_brain/launcher.py:probe_free_vram_bytes` runs the same nvidia-smi
  query with none of these fixes and, unlike jv-context's, its answer
  DECIDES something: `None` on any failure — OSError, timeout, non-zero
  exit, `int()` choking on `[N/A]` — goes straight into `pick_rung`,
  which reads it as "no usable GPU" and drops Jarvis to the CPU rung for
  the life of that llama-server. A driver hiccup at launch is
  indistinguishable from a machine with no card, and the only trace is a
  journal line: nothing on the bus, no heartbeat note, and the rung file
  writes `free_vram_mb=-1` for both. Its unit already has the driver on
  its path, so this is not B37's bug — it is B37's second half, and the
  shape to copy now exists. **B40** is the consumer question: the field
  is finally on the bus and nothing reads it. 943 MiB free is itself the
  interesting case — the 8B Q4 brain would not fit right now — and a HUD
  plate showing it is the loop's to build, while a brain that REACTS to
  it is a scheduling change that pairs with backlog 14. **B38** is
  unchanged and still small: jv-ears, jv-guard and jv-brain beat on a
  timer alone, and `_set_fault` + an Event is the shape to copy. **B36
  is a human's** (proposal R8). Otherwise unchanged: A is blocked on
  A62/A65/A68/A47/A56/A50/A60 (decisions) and A13/A21/A22/A25/A27/A31/
  A38/A39 (a human at ares), B27/B28 share one decision, B30/B33 share
  another, and B10/A28 — one live recording of one spoken turn — is
  still the biggest thing a human can hand this loop.

## 2026-09-24 — iteration 64 — B39: the blind rung

**What.** `jv_brain/launcher.py:probe_free_vram_bytes` returned `None` on
every way it could fail: OSError, a timeout, a non-zero exit, and `int()`
choking on `[N/A]`. `None` goes straight into `pick_rung`, which reads it
as "no usable GPU" and pins Jarvis to the CPU rung for the life of that
llama-server. So a driver hiccup at launch was indistinguishable from a
machine that never had a card — and unlike B37's jv-context probe, this
one DECIDES something. The only trace was a line on stderr: nothing on
the bus, no heartbeat note, `free_vram_mb=-1` written for both.

Three answers now, the shape B37 built:

- **measured** — a number, strictly parsed. `[N/A]`, `[Not Supported]`,
  NVML init errors arriving on stdout, `nan`/`inf`, negatives, and a
  number printed alongside a non-zero exit are all rejected. `nan` was
  the nastiest: `float()` takes it, and it then walks the whole ladder
  comparing false to every rung budget — indistinguishable from a card
  with nothing free, which at least lands on the same floor, but by
  accident.
- **absent** — no nvidia-smi at all. A fact about the machine, not a
  fault, and the only silent `None` left.
- **unreadable** — there IS a driver and it would not answer.

The CPU floor holds for all three; you cannot allocate VRAM you could not
count, so which rung gets picked does not change. What changes is what
anyone is allowed to CONCLUDE. The launcher execs into llama-server and
can never reach the bus, so the rung file is the whole of what it gets to
say: it now carries `vram=` and, when unreadable, nvidia-smi's own words
in `vram_note=`. Writer and reader moved in together (`write_rung_file` /
`read_rung_file`, tested as one pair), jv-brain's `_rung()` became a thin
call on that, and a blind launch turns its heartbeat **degraded** with the
reason attached — without erasing a worse note it already carried. A
GPU-less machine stays `ok`: on a dev box "degraded forever" is noise, and
"there is no card here" is not an impairment. An old rung file with no
`vram=` line infers from `free_vram_mb` and can never invent a fault
nobody observed.

- tests: `bash ops/ralph/runtests.sh jv-brain` — **85 (was 57)**.
  **Seventeen mutations, all seventeen caught**: any OSError folded back
  into "no GPU" (the original bug), the exit code ignored, the
  finite/negative guard dropped, empty output read as `0.0`, a timeout
  left uncaught, unreadable collapsed into absent, the source word or the
  reason left out of the rung file, a missing field read as a fault, the
  note left unflattened, the heartbeat not escalating, the blind note
  overwriting a real one, the reason never reaching the bus, a GPU-less
  machine reported degraded, the rung file not written on the blind path,
  and unreadable allowed to keep a GPU rung.
- build: `nixos-rebuild build --flake .#ares` ok, `git add` first. Never
  test/switch. No schema change, no jv-act, no boot path, no
  NVIDIA/kernel/flake pin — `jarvis-services.nix` is read, not written
  (it already puts the driver on jv-llm's path, which is why this was
  B37's second half and not B37's bug).
- **verified through the BUILT closure on ares**, under the jv-llm unit's
  own `Environment="PATH="`: the shipped `jv-llm-launch` read **943 MiB
  free of 6144** off the GTX 1660 SUPER, cross-checked against
  nvidia-smi's own `name,memory.total,memory.free`, and wrote
  `vram=measured`, rung 4. **That is the case this commit exists for** —
  ares launches its brain onto the CPU rung right now with a perfectly
  healthy card, because the desktop and a browser own the VRAM, and until
  today that outcome was byte-for-byte identical to a probe that failed.
  The same binary with the driver off PATH wrote `vram=absent`; with a
  stub answering `[N/A]`, and another printing `5432` then exiting 9, it
  wrote `vram=unreadable` plus the reason. No exec of llama-server was
  performed — every run went through the `exec_fn` seam into a tmp dir.
- files: services/jv-brain/jv_brain/launcher.py,
  services/jv-brain/jv_brain/service.py,
  services/jv-brain/tests/test_vram_guard.py (new)
- commit: 05117db
- next: **B41 or B40 — and B39 just made them the same question.** The
  bus can now say the brain picked its rung blind, but it still cannot
  say in WORDS which rung it is on: `llm_rung=4.0` and `llm_gpu=0.0` need
  the ladder memorised to become "CPU fallback, replies will be slow",
  and the launcher's own `label=` — the one human-readable string it
  writes — is read by nobody, though `RungRecord` now has it in reach for
  free (**B41**, small). **B40** is the same consumer question one step
  out: `context.system.gpu_vram_free_mb` has been on the bus since B37
  and nothing reads it, and today's 943 MiB is the argument for a HUD
  plate — but a plate showing "943 MiB free" without saying the desktop
  owns the rest reads as a fault when it is the machine working as
  designed, so that plate needs a sentence, not just a number. **B42** is
  the small hygiene B39 turned up: the rung file is written
  non-atomically and jv-brain is only `after=` jv-llm, so the window is
  real — it fails safe today (a torn read is `index=None`, `vram=absent`,
  degrading nothing), which is why it is a nicety and not a bug. **B38**
  is unchanged and still small: jv-ears, jv-guard and jv-brain beat on a
  timer alone, and `_set_fault` + an Event is the shape to copy. **B36 is
  a human's** (proposal R8). Otherwise unchanged: A is blocked on
  A62/A65/A68/A47/A56/A50/A60 (decisions) and A13/A21/A22/A25/A27/A31/
  A38/A39 (a human at ares), B27/B28 share one decision, B30/B33 share
  another, and B10/A28 — one live recording of one spoken turn — is still
  the biggest thing a human can hand this loop.

---

## 2026-09-24 — iteration 65 — B41: the rung in words, and the fall called a fall

**What.** Since the VRAM guard was written, the only thing the bus has
ever said about which rung the brain launched on is `llm_rung=4.0` and
`llm_gpu=0.0` — two numbers in a free-form gauge map. Turning `4.0` into
"CPU fallback, replies will be slow" requires having Ofek's ladder
memorised, and `jv health` doesn't even print metrics, so in the readout
a human actually looks at, the rung said nothing at all. Meanwhile the
launcher writes `label=` to the rung file on every launch — the one
human-readable string in the whole mechanism — and nobody had ever read
it. B39 put it in `RungRecord`'s reach at zero cost.

`describe_rung` reads it: `rung 4 (CPU fallback)`. It falls back to the
backend word when the file carried no label (never guesses the label
back from the index — that would be quoting THIS process's ladder about
a choice a different process made), and it says nothing whatsoever about
a rung it never read. An empty string, not `rung ?`: a caller cannot
splice a placeholder into a sentence and have it read as a fact. `-1` is
one of those — it is the parser's sentinel for a file with no `rung=`
line, never a number the launcher wrote.

**The half that matters.** Words are only worth adding where somebody
should read them, and chasing that question turned up the real finding:
jv-brain published **`ok`** while running on the CPU rung with a
perfectly healthy card. `schemas/sys.health.json` names that exact case
as its worked example of `degraded` — *"'degraded' = alive but impaired
(e.g. brain fell back to CPU, ears lost the mic)"* — and it is not a
hypothetical: ares measured 943 MiB free of 6144 again today, because
the desktop and a browser own the card, so the 8B Q4 brain is on the CPU
right now and the heartbeat called that fine.

So `rung_finding` answers the whole health question in one place:

- **the CPU rung on a machine that HAS a card** (measured or unreadable)
  is a finding — invariant 6 exists to keep the 8B Q4 resident, and an
  8B on this i5 answers in the time a GPU rung takes to finish;
- **a rung chosen blind** is a finding, unchanged from B39;
- **everything else is quiet.** A machine with no card is still simply a
  machine with no card (B39's call, kept). Rungs 1-3 gave something up
  deliberately and are still on the GPU — a note every 5 s for a ladder
  working as designed teaches a reader to skip the field the real fault
  will one day appear in, which is why this does NOT narrate the happy
  path. A worse note keeps its place at the front of `notes` and keeps
  its state; the finding only ever appends.

**What a human will notice.** `jv health --check` exits 1 while the
brain is on CPU, so ares will read `1 not well` on an ordinary day until
VRAM is free when jv-llm starts. That is the truth and it is actionable
(free VRAM, restart jv-llm) and it clears itself — but it IS a verdict
change made by the loop, so **B43** is logged for a human who would
rather have `ok` back: disagreeing means disagreeing with the schema's
own example, not with a heuristic.

Hardening that came along: rung-file values are stripped on the way in,
because `backend` now decides a STATE and `backend = cpu` from a
hand-edited file equals neither `"cpu"` nor `"gpu"` and would quietly
answer "no" to both questions. (Line endings needed no such care —
`read_text()` translates CRLF. I wrote the opposite in a comment first;
the mutation battery is what caught it, by refusing to die.) The label
is flattened the way `vram_note` already is: `jv health` renders notes
as one line of a table.

- tests: `bash ops/ralph/runtests.sh jv-brain` — **98 (was 85)**.
  **Sixteen mutations, all sixteen caught**: a negative index read as a
  rung, the label never parsed, the label not flattened, values not
  stripped, the backend fallback dropped, the fall not counted as a
  finding (the bug itself), a card-less machine counted as one, blind no
  longer a finding, a GPU rung counted as a fall, the finding
  overwriting a worse note, the state not escalating, a worse state
  overwritten by degraded, the blind branch quoting `-1 MiB` as a
  reading, the reason left out, the consequence left out, and `rung ?`
  spliced in for an unread rung. (Fifteen on the first run — the escapee
  is the one that corrected the comment above, and its test now pins the
  real reason the strip is there.)
- build: `nixos-rebuild build --flake .#ares` ok, `git add` first. Never
  test/switch. No schema change — `notes` is already "human-readable
  detail for degraded/error states", and this is the first thing to fill
  it that a human can act on. No jv-act, no boot path, no pins.
- **verified through the BUILT closure**, under the jv-llm unit's own
  `Environment="PATH="`: the shipped launcher read **943 MiB free of
  6144** off the real GTX 1660 SUPER, wrote `rung=4 / label=CPU
  fallback / vram=measured`, and the shipped `rung_finding` turned that
  file into `llm on rung 4 (CPU fallback) — no GPU layers, replies will
  be slow; 943 MiB VRAM free at launch`. No llama-server was exec'd; the
  rung file went to a tmp dir.
- files: services/jv-brain/jv_brain/launcher.py,
  services/jv-brain/jv_brain/service.py,
  services/jv-brain/tests/test_vram_guard.py
- commit: 6f6119b
- next: **B43 first if a human is reading** — it is the only item this
  iteration created that somebody might want to reverse, and it is one
  sentence of judgement, not work. Otherwise **B40 is now much riper**:
  the note says "943 MiB VRAM free at launch" but `at launch` is the
  whole limit of it — nothing still reads the live
  `context.system.gpu_vram_free_mb`, so nothing can see the number move
  when a game starts, which is the moment invariant 6 exists for. The
  HUD plate B40 describes now has a sentence to borrow for why 943 MiB
  is not a fault. **B42** (atomic rung-file write) is one rename and
  matters slightly more than it did this morning: that file now decides
  a published STATE, not just a gauge — a torn read still fails safe
  (`index=None`, `vram=absent`, quiet) but "fails safe" now means
  "silently reports ok while the brain crawls". **B38** is unchanged and
  still small: jv-ears, jv-guard and jv-brain beat on a timer alone, and
  B35 wrote the `_set_fault` + `asyncio.Event` shape to copy — and this
  iteration sharpened it too, since jv-brain's new degraded state waits
  up to a full period to be heard. **B36 is a human's** (proposal R8).
  Otherwise unchanged: A is blocked on A62/A65/A68/A47/A56/A50/A60
  (decisions) and A13/A21/A22/A25/A27/A31/A38/A39 (a human at ares),
  B27/B28 share one decision, B30/B33 share another, and B10/A28 — one
  live recording of one spoken turn — is still the biggest thing a human
  can hand this loop.

## 2026-09-24 — iteration 66 — B40: the free-VRAM number, on a screen at last

**What.** `schemas/context.system.json` has carried `gpu_vram_free_mb`
since v1 and nothing has ever read it. B37 made jv-context measure it;
B39 and B41 spent two iterations on the consequence of the number
without ever being able to show it. What ares measures is the whole
argument: **943 MiB free of 6144**, twice in one week, on a GTX 1660
SUPER that works perfectly — the desktop, the compositor and a browser
own the rest — which is why jv-brain launches onto the CPU rung.

The HUD has been saying the first half of that sentence since A6:
`llm CPU RUNG 4`, off jv-brain's own heartbeat. It could never say the
second half, so the line read as a fault — a broken driver, a card that
fell out, a thing to go and fix. It is none of those; it is the ladder in
invariant 6 doing exactly its job on a card that is already spent. This
iteration is the missing line: `vram 943 MiB FREE`, dimmer, directly
under the one it explains.

**Why it is a line and not a readout.** Four decisions, each of which is
a test:

- **Not a gauge.** A VRAM figure on screen all day is one nobody reads on
  the day it matters (§06). It speaks only while something is being paid
  for the shortage — a brain on the CPU floor. The gate `brainOnCpu` is
  an INPUT, fed from `HealthState.llmOnCpu`: jv-brain's rung already has
  a reader that owns the heartbeat's trust rules and expiry, and two
  files deciding the same fact off the same topic is how they come to
  disagree. Unfed, it is silent — and since the wiring lives in a plate,
  and plates import the Quickshell singletons and so cannot be tested
  headless, a python test pins the binding and the guard around the row.
  A forgotten binding is the exact edit that would turn this into the
  all-day gauge, silently and while looking correct.
- **Absent is not zero.** The field is optional because a machine with no
  GPU has no such number — and that machine reports `llm_gpu = 0` too
  (B39). Defaulting the absence to 0 would draw "0 MiB FREE" under the
  rung line on a card-less machine and explain a CPU brain with a
  shortage that never existed. So `known` is a separate boolean and
  `freeMb` is -1 for unknown, which leaves a genuine 0 MiB — the reading
  that explains the most — able to reach the screen.
- **A live reading, never a memory.** The value of the number is that it
  MOVES: a game starts, a browser closes. Three 1 Hz periods and it is
  gone, on its own timer, because no binding re-evaluates just because a
  clock moved.
- **Quoted, never judged.** "Enough VRAM for the 8B Q4" is a fact about
  the ladder in jv-brain's launcher, and the ladder is not on the bus.
  A HUD that said "the card is free now, restart the brain" would be
  guessing at another service's configuration through the wall invariant
  1 put there. It says the number; the reader knows their own card.
  Publishing the rung's requirement so the HUD *could* say the rest is
  B45, and it is jv-brain's to publish.

**Two things the work itself found.** The row's width is bounded by
construction — whole MiB below five digits, then GiB, then GiB with no
decimal past 100 — so every branch is thirteen characters at its widest
and no card can push it past `jv-compat DEGRADED`, the line the 300 px
surface was measured against. And `detail` turned out not to be
available as a property name anywhere in `core/`: a test has held that
name to `action.result.detail` (free log text no element may render,
invariant 7) since A37, and it fired on the first run. The figure is
`line`.

- tests: `shell/jv-hud` headless suite **569, was 536** (31 new), plus
  one in tools (**137, was 136**). **Twenty mutations, twenty caught** —
  the gate deleted, the gate defaulting open, unknown leaking the last
  figure, unknown reading as an empty card, a negative figure, a
  non-finite one, a string, a v2 body, a hedged frame, a timeless frame,
  a frame off a dropped link, freshness ignored, the expiry never
  cleared, a timer armed with nothing to expire, the unit seam moved a
  decade, the decimal kept forever, a gibibyte turned into a gigabyte,
  fractions of a MiB on screen, and the wrong topic read. Three of those
  needed a test written for them first, and one needed the test
  rewritten: a frame cannot be "born stale" against `core/BusModel`,
  which pins its clock offset off the frames themselves, so the first
  frame a HUD ever sees is age 0 by construction. The honest version is
  a second frame that spent nine seconds in flight.
- **photographed**: `docs/hud/06-health.png` re-shot through the real
  plates, carrying the 943 MiB ares actually measured, so the sheet shows
  the rung line explained rather than accused.
- build: `nix build .#jv-hud` (qmllint -W 0 over every QML file + the
  headless suite) and `nixos-rebuild build --flake .#ares` both green.
  Never test/switch. No schema change — the field has been frozen in
  `context.system` v1 since before anything wrote it. No jv-act, no boot
  path, no pins.
- files: shell/jv-hud/core/VramState.qml (new),
  shell/jv-hud/tests/tst_vramstate.qml (new),
  shell/jv-hud/HealthPlate.qml, shell/jv-hud/shell.qml,
  shell/jv-hud/README.md, shell/jv-hud/core/qmldir,
  tools/gen_theme_qml.py, tools/tests/test_gen_theme_qml.py,
  tools/hudshots/scene/tst_shots.qml, docs/hud/README.md,
  docs/hud/06-health.png
- commit: 86cffcb
- next: **B43 is still a human's** and still one sentence of judgement —
  and it is now cheaper to answer, because the thing B41 made `jv health`
  go red about is the thing the HUD can now show you the reason for. The
  loop's own pick would be **B42** (one rename: the rung file decides a
  published state and is written non-atomically) or **B38** (jv-ears,
  jv-guard and jv-brain still beat on a timer alone, and B35 wrote the
  shape to copy). **B44** — the brain reacting to the live VRAM number,
  rather than the HUD reporting it — is explicitly NOT the loop's until a
  human answers it: an automatic unload at the wrong moment is worse than
  a slow brain. **B45** is the small, honest half of it and belongs to
  jv-brain: publish what the chosen rung needed, and `VramState` gains
  the one sentence it currently refuses to guess. A is unchanged: blocked
  on A62/A65/A68/A47/A56/A50/A60 (decisions) and A13/A21/A22/A25/A27/
  A31/A38/A39 (a human at ares), and B10/A28 — one live recording of one
  spoken turn — is still the biggest thing a human can hand this loop.

## 2026-09-24 — iteration 67 — B45: what the card would have to give back

**What.** jv-brain now publishes the VRAM its ladder would require to put
Jarvis back on the GPU — `sys.health.metrics.llm_gpu_floor_mb`, and the
same figure in words in `notes`. On ares that number is **5424 MiB of a
6144 MiB card**.

**Why it had to be jv-brain's to say.** B40 put the free-VRAM figure on
a screen — `vram 943 MiB FREE`, under the rung line it explains. What
the HUD could not do, and must not do, is judge it: the ladder's
requirements live in `jv_brain/config.py`, they are not on the bus, and
invariant 1 exists precisely so that a consumer does not reach through
the wall for another service's configuration. So `VramState` quotes the
number and refuses the sentence — and the refused sentence is the useful
one. Worse, the sentence a reader supplies unaided is usually wrong on
this machine: "5 GB free and STILL on the CPU?" sounds like a fault, and
on a ladder whose cheapest GPU rung wants 5424 MiB it is the ladder doing
exactly its job. The fix is not a smarter HUD. It is the service that
owns the ladder publishing the one number it alone knows.

**The floor is a threshold, so it is defined as one.** Four decisions,
each pinned by a test:

- **`min()` over the GPU rungs, not `LADDER[-2]`.** A test already pins
  the budgets as strictly decreasing, so today they are the same figure.
  But this number is one somebody will act on — restart jv-llm or don't
  — and a reordered ladder must not be able to publish a figure that is
  not the floor. The stronger test is the one that never mentions the
  ladder's order at all: at the floor `pick_rung` reaches a GPU rung, one
  byte below it the ladder falls to the CPU.
- **Whole MiB, rounded UP.** MiB because that is the unit of the reading
  it will be compared against (`context.system.gpu_vram_free_mb`, and
  nvidia-smi's own); a threshold in different units from its reading is a
  comparison nobody can make. Up rather than nearest, because a floor
  rounded down is a HUD saying "it fits now" about a launch that would
  land straight back on the CPU.
- **`None` for a ladder with no GPU rung, never 0.** There is no VRAM
  figure that would buy a GPU brain on such a ladder; 0 would read as
  "any card at all will do".
- **Published only while something is waiting on it.** Not while the
  brain is already on the card — a requirement already met, restated
  every 5 s, is the all-day gauge §06 refuses — and not on a machine with
  no card at all, where a floor would send a reader hunting VRAM this
  machine has never had (the same invented shortage `VramState` refuses
  to draw). A blind launch DOES get it: whatever nvidia-smi would not say
  at launch, a live reading can be compared with the floor now.

**And the same comparison in words**, because `jv health` prints notes
and not metrics: `llm on cpu — no GPU layers, replies will be slow; 943
MiB VRAM free at launch, 5424 needed`. Unit said once, both figures MiB.
Only next to a measured reading, though — beside a blind launch a
requirement is a number with nothing to compare it with, and a test holds
it out of that line.

**One process note, for honesty.** This iteration opened on a dirty
worktree: iteration 66's `next:` named B45, and the changes were sitting
there unstaged and uncommitted, from a run that was cut off before its
verify gate. The loop's rule is never to commit unverified code, not
never to finish it — so it was verified from scratch rather than trusted:
full suite, ten mutations written and run against it here, tools suite
(it reads jv-brain's metric names off this very file), and the build.
The first `nixos-rebuild build` of the iteration was run through a pipe
to `tail`, which reports the exit status of `tail`; that gate was
worthless and was re-run with `pipefail`. Worth remembering — a green
that cannot go red is not a gate.

- tests: `bash ops/ralph/runtests.sh jv-brain` **109, was 98** (11 new),
  plus tools **137** unchanged. **Ten mutations, ten caught**: the safety
  margin dropped from the floor, the floor taken off the most expensive
  GPU rung instead of the cheapest, MiB rounded down, MiB that were
  really MB, a card-less ladder publishing 0 instead of nothing, the
  gauge published while already on the GPU, published on a machine with
  no card, the requirement dropped from the note, and the requirement
  quoted beside a blind launch.
- build: `nixos-rebuild build --flake .#ares` green. Never test/switch.
  No schema change — `metrics` is free-form by schema and has been since
  v1. No jv-act, no boot path, no pins.
- files: services/jv-brain/jv_brain/launcher.py,
  services/jv-brain/jv_brain/service.py,
  services/jv-brain/tests/test_vram_guard.py
- commit: 532566f
- next: **B46** — the HUD half of this, and the loop's own pick. The
  floor is on the bus and nothing reads it, so the comparison still
  happens in the reader's head. The plumbing is the shape B40 already
  wrote (`HealthState` owns the heartbeat, `VramState` takes the floor as
  an INPUT and never guesses it); the real work is the ROW, which is
  thirteen characters wide by construction on a 300 px surface — so
  `943 / 5424 MiB FREE` has to earn its width or find a shorter true
  form, and the deficit (`4481 MiB SHORT`) may be both shorter and the
  number a reader would actually act on. Otherwise unchanged: **B43 and
  B44 are still a human's** (is a CPU brain a `degraded` health state,
  and may jv-brain ever unload or relaunch itself), and **B42** (the rung
  file decides a published state and is written non-atomically — one
  rename) and **B38** (jv-ears, jv-guard and jv-brain still beat on a
  timer alone) are the loop's next small ones. A remains blocked on
  decisions and on a human at ares, and B10/A28 — one live recording of
  one spoken turn — is still the biggest thing a human can hand this
  loop.

## 2026-09-24 — iteration 68 — B46: the other number, next to the first one

B40 put the card's free VRAM under the rung line. B45 got the ladder's
requirement onto the bus. Neither of them, on its own, tells you
anything: `943 MiB FREE` is a figure you have to know this machine to
judge, and a requirement with no reading beside it is a figure you
cannot check at all. This iteration is the twenty lines that put them on
the same plate, one under the other, and then stops.

    llm   CPU RUNG 4
    vram  943 MiB FREE
    llm   NEEDS 5424 MiB

**Two rows, not one sentence.** The obvious shape was `943 / 5424 MiB`
on the existing row, and it was wrong twice over. `n / m` next to the
word `vram` is the disk-usage idiom — most readers would take it as
*used of total*, and 5424 is not this card's total — and a single string
would have been the HUD composing a claim out of two services' numbers.
jv-context measured the first; jv-brain computed the second off a ladder
the HUD may not read (invariant 1). One row per publisher keeps each
number attributable, lets either be absent on its own, and costs nothing
but a line of a plate that is already only on screen when something is
wrong. The second row is named `llm` and not `vram` for the same reason:
it is the model's requirement, not a property of the card.

**The requirement never appears alone.** `needKnown` gates on
`reporting`, which is the reading's own gate — so a HUD that can see
jv-brain but not jv-context draws exactly what it drew before B46, and
the pair arrives and leaves together rather than leaving half a
comparison up. This is jv-brain's own rule for its `notes`, taken
literally: it quotes the floor only next to a reading it actually took.
jv-brain also withholds the gauge entirely once the brain is on the card
and on a machine with no card, so between the two of them there is no
state in which a reader is shown a number they cannot act on.

**Rounded up, always.** The unit ladder is now shared by both rows
(`amount(mb, up)`), so they are never in different units and the
comparison never needs arithmetic — but a measurement rounds to nearest
and a requirement rounds UP. The one way this row could lie is by
drawing a fit the ladder would not actually take (`943 MiB FREE` over
`NEEDS 943 MiB` on a ladder wanting 943.4), and that is worth a branch.
jv-brain already ceils its own floor, which makes this belt and braces;
for a number whose entire job is to be compared with another one, belt
and braces is right.

**And it is still inside the box.** The 300 px surface is measured
against `jv-compat DEGRADED` — seventeen characters of name plus detail
— and a test in tst_vramstate has pinned every branch of the reading to
that since B40. `NEEDS ` is six characters and the quantity is at most
eight (`9999 MiB`, `99.9 GiB`, `1024 GiB`), which is fourteen under a
three-letter name: seventeen exactly. The deficit form the plan
suggested (`4481 MiB SHORT`) is eighteen under `vram` and would have
been the first row in the HUD to break that line, which is how the
two-row shape got chosen over it.

- tests: `shell/jv-hud` headless suite **585, was 569** (16 new — 10 in
  tst_vramstate, 6 in tst_healthstate), plus tools **138, was 137**.
  **Nine mutations, nine caught**: the requirement standing with no
  reading beside it, the requirement rounded to nearest, a zero floor
  treated as a floor, the need row quoting the reading instead of the
  floor, the reading itself rounded up, any metric value accepted as a
  floor, a floor read off a heartbeat nobody expired, the plate losing
  the binding, and the plate drawing the requirement on the reading's
  gate. Two more against the shot gate (a floor jv-brain would not
  compute, and a shot that omits it) — both caught.
- photographed: `docs/hud/06-health.png` re-shot through the real
  plates. The sheet now shows the whole sentence: the rung, the card,
  and what the card would have to give back.
- build: `nix build .#jv-hud` (qmllint -W 0 over every QML file + the
  headless suite) and `nixos-rebuild build --flake .#ares` both green.
  Never test/switch. No schema change — `metrics` is free-form by schema
  and has been since v1. No jv-act, no boot path, no pins.
- files: shell/jv-hud/core/VramState.qml,
  shell/jv-hud/core/HealthState.qml, shell/jv-hud/HealthPlate.qml,
  shell/jv-hud/tests/tst_vramstate.qml,
  shell/jv-hud/tests/tst_healthstate.qml,
  tools/hudshots/scene/tst_shots.qml, tools/tests/test_hudshots.py,
  tools/tests/test_gen_theme_qml.py, docs/hud/README.md,
  docs/hud/06-health.png
- commit: 62efed3
- next: B45/B46 close the VRAM story as far as it can go without a
  decision. What is left in it is **B44**, and it is still explicitly a
  human's: the HUD can now see the card move and jv-brain still cannot —
  it learns its VRAM exactly once, at launch, from its own fork — and
  the question of whether a brain may ever unload or relaunch itself is
  a scheduling change, not an arithmetic one. **B43** (is a CPU brain a
  `degraded` health state?) is the other sentence of judgement waiting.
  The loop's own next small ones are unchanged: **B42** (the rung file
  decides a published state and is written non-atomically — one rename)
  and **B38** (jv-ears, jv-guard and jv-brain still beat on a timer
  alone, and B35 wrote the shape to copy). Track A remains blocked on
  decisions and on a human at ares, and **B10/A28** — one live recording
  of one spoken turn — is still the biggest thing a human can hand this
  loop.

## 2026-09-24 — iteration 69 — B38: the stall, said when it happens

`schemas/sys.health.json` has asked for this since v1, in one clause:
every service beats "every fixed period, **and immediately on state
change**". jv-ears only ever did the first half. So the failure this
service exists to report — PortAudio holding a stream open that delivers
nothing, which is the 2026-09-15 field bug verbatim — became a
`degraded` heartbeat somewhere in the next five seconds, and
`jv health --check` reads a **6 s** window: one nominal period plus a
margin. A stall landing just after a beat is a stall that check can
miss entirely, and it is the one thing a mic indicator must never be
wrong about (invariant 10).

**B35's shape could not be copied, and that is the interesting part.**
jv-context wakes its heartbeat with an `asyncio.Event` its system pump
sets, because there the state changes when a probe RAISES — somebody is
holding the news. jv-ears has nobody: its state is a function of a
CLOCK. A stream stalls by a chunk *not* arriving, `CaptureMeter.age_s`
crosses `STALL_S` while no code of ours runs, and there is no moment at
which a writer could set anything. A state nobody announces has to be
WATCHED — so `pump_health` re-reads it every 250 ms and publishes only
when the answer has moved. Four times a second, one property read and
two comparisons; the publish is the rare case.

**It compares against the bus, not against itself.** The pump keeps no
`last_state` variable. It is handed `said()` — the state the last
published FRAME carried — and compares the meter's answer now against
that. This is not stylistic: a chunk arriving between `health_body`
building a body and the loop's next read would leave a bookkeeping
variable claiming something the bus never heard, and the whole point of
this pump is that the bus's last word and the machine's state agree. The
one writer is the function that builds the frame.

**A floor, because every flap is a real state change.** A device
delivering a chunk just either side of `STALL_S` alternates ok/degraded
honestly — and without a floor the watch would publish each flip and put
`sys.health` at 4 Hz for as long as the hardware misbehaved, which is
exactly the "quiet topic" invariant 5 protects. `HEALTH_MIN_GAP_S` is
1 s (= `STALL_S`), so the news is at most a second late on a fault that
was already a second old when it became one — still four seconds inside
the window the check reads. And a flicker that undoes itself while the
floor holds publishes NOTHING: `said()` is still `ok` and `ok` is true
again, so there is nothing to say. A beat there would have reported a
state that had already ended.

**Only the enum is watched.** jv-ears' degraded note is
`microphone open but no audio for 3.2s` — a string that changes on every
read. A pump that woke on the note would beat on every tick for as long
as the fault lasted, which is how a 0.2 Hz heartbeat turns into a 4 Hz
one. The growing number rides out on the periodic beat, where a number
that changes belongs. `period_s` still says 5.0: the schema calls it
nominal, and every consumer in the repo uses it as an expiry
(`period_s * 2` in `MicState`, `HealthState`, `jv health`), which extra
beats only push further away. A `--wav` run is unaffected — no device
can stall, `meter.health()` is constant, and the pump degenerates to the
timer it replaced.

**What B38 asked for in jv-guard and jv-brain turned out to be a
different job.** Both already beat at the instant of their faults
(`_health("degraded", ...)` on a scan with no engine, on an `llm
error`) — the item's premise was wrong about them. Their gap is the
opposite one: the fault is not LATCHED, so the next periodic beat says
`ok` again while nothing has changed. A machine with no signature
scanner reports one `degraded` blip per screened binary and `ok` in
between; a dead llama-server reports one blip per failed turn. Latching
either is a few lines and makes `jv health --check` red for as long as
the condition lasts — which is precisely the judgement **B43** is
already waiting on. So it was NOT built: it is **B47**, to be answered
once for all three. jv-voice is the one service still unread for this.

- tests: `bash ops/ralph/runtests.sh jv-ears` — **114 green, was 104**
  (10 new, all in tst-style scripted time: a fake clock the pump's own
  sleeps wind, so every assertion is about seconds and none are spent).
  **Nine mutations, nine caught**: the change rule dropped (timer only),
  the floor dropped, the period not reset by a change beat, `said()`
  replaced by a second look at the state, the watch interval widened to
  the period, the floor raised above the period, main feeding the pump a
  constant state, main comparing against the meter instead of the bus's
  last word, and `done` ignored so the pump outlives the pipeline.
- build: `nixos-rebuild build --flake .#ares` green. No schema change
  (this is the schema's existing clause, finally honoured), no jv-act, no
  boot path, no pins. No QML touched, so no HUD shots to re-take.
- files: services/jv-ears/jv_ears/main.py,
  services/jv-ears/tests/test_health_watch.py, ops/ralph/PLAN.md
- commit: 3d01c31
- next: **B47** is the newly raised one and it is a human's, bundled with
  **B43** — the same question ("may a check be red on an ordinary day?")
  now in three services. The loop's own remaining small ones are
  unchanged: **B42** (jv-brain's rung file is written non-atomically and
  now decides a published state — one rename) and **B38's** last
  unexamined service, jv-voice. Track A is still blocked on decisions
  (A13/A21/A22/A25/A27 are all one human look at `docs/hud/`) and
  **B10/A28** — one live recording of one spoken turn on ares — remains
  the biggest thing a human can hand this loop.

## 2026-09-24 — iteration 70 — B42: the rung file written in one move

Track A is where the ladder points, and every open A item is either a
human's to answer (A13/A21/A22/A25/A27/A38/A62/A65/A68 — one look at
`docs/hud/`) or explicitly "do not build until that one is". So: the
B track's smallest complete thing, and the one B41 had already turned
from a nicety into a state.

**What this file is.** `jv-llm-launch` measures free VRAM, walks the
ladder, writes `/run/jarvis-llm/rung`, and then `execvp`s into
llama-server. That exec is the whole reason the file exists: the
process that knows which rung was picked is GONE a microsecond later,
so anything it learned that nobody can re-derive is either in that file
or lost. jv-brain re-reads it on every 5 s heartbeat — and since B39/B41
what it reads decides a published STATE (`degraded` + `rung 4 (CPU
fallback)`), not just the `llm_rung` gauge it used to be.

**The window was real.** `path.write_text()` is open-truncate-write, so
there is an instant in which the file exists and is empty or half a
record. jv-brain is only `after=` jv-llm, which orders STARTS and not
this write, and a restarted llama-server rewrites it under a running
brain. A torn read fails safe in the parser (`ValueError` → `index=None`)
— but "safe" now means the heartbeat says `ok` about a brain that may
be crawling on the CPU at 2 tokens/s, which is the sensor-truthfulness
failure invariant 10 exists against, arriving through the one topic
meant to catch it. `os.replace` closes it: a pid-stamped temp file
beside the target, then one rename. The reader gets the last whole
record or this one, and never the seam between them.

**The half I did not go looking for.** Writing the mode down turned up a
live bug, not a tidiness: the file's permissions were whatever the
launcher's umask made them. jv-llm writes it, jv-brain reads it — two
users, one group (`jarvis`), inside a 0750 `RuntimeDirectory` — so the
GROUP read bit is the entirety of the reader's access. systemd's default
umask is 0022 and today's 0644 works; a `UMask=0077` added to `harden`
one day (an obviously-correct hardening line) would hand jv-brain a file
it cannot open, and the failure is invisible by construction: an
unreadable file is caught as `OSError` and reads as "llama-server has
told me nothing", which is `ok` about a CPU brain — the exact same
silent direction as the torn read. `RUNG_FILE_MODE = 0o640`, fchmod'd on
the fd rather than passed to `O_CREAT` (that mode is umask'd too). The
world-read bit is dropped because a 0750 directory already made it
unreachable, so it was never access anyone had.

**No fsync, on purpose.** /run is tmpfs. A record that survived the
reboot which emptied it would be a claim about an llama-server that no
longer exists; durability is the opposite of what this file wants, and
the docstring says so where the next reader will look.

**The iteration's other finding, which cost more than the change did.**
The loop's mutation practice — rewrite the source, re-run pytest, expect
red — can silently grade UNMUTATED code. CPython validates a cached
`.pyc` on (mtime *seconds*, size), so an equal-length edit written
inside the same second as the one before it reuses stale bytecode: the
run passes because the mutant never executed. It showed up as one
mutation "surviving" and then a full-suite failure on a RESTORED file
that was still running the mutant's bytecode — the honest tell, and the
reason this is written down rather than shrugged off. `python -B` plus
clearing `__pycache__` fixes it and every number below was measured that
way. Raised as **B48**, including that pre-iteration-70 equal-length
mutations in this journal were measured without it.

- tests: `bash ops/ralph/runtests.sh jv-brain` — **114 green, was 109**
  (5 new: the whole previous record still readable at the instant of the
  rename, a failed write leaving the old record and no litter, a
  finished write leaving exactly one file, two overlapping writers each
  landing whole, and the group-readable mode measured under a 0077
  umask). **Six mutations, six caught**: `write_text` back, the fchmod
  dropped, the temp left behind on failure, the temp not pid-stamped,
  the write aimed at the target itself, the mode down to 0600. One
  survivor ON PURPOSE — 0644 is indistinguishable from 0640 behind a
  0750 directory, so no test claims the other-read bit and none should.
- build: `nixos-rebuild build --flake .#ares` green. No schema change,
  no jv-act, no boot path, no pins, no QML (so no HUD shots to re-take).
- files: services/jv-brain/jv_brain/launcher.py,
  services/jv-brain/tests/test_vram_guard.py, ops/ralph/PLAN.md
- commit: 2a81605
- next: **B48** is the loop's own and cheap — one `ops/ralph/mutate.sh`
  with `-B` baked in, so the practice stops being re-typed per
  iteration. **B38's** last unexamined service is jv-voice. Everything
  else small is a human's: **B43/B47** are one question asked three
  times ("may `jv health --check` be red on an ordinary day?"), and
  Track A is one look at `docs/hud/` away from unblocking five items.
  **B10/A28** — one live recording of one spoken turn on ares — is
  still the biggest thing a human can hand this loop.

## 2026-09-24 — iteration 71 — B48: the mutation numbers, with controls

Track A is still where the ladder points and still where every open item
is a human's to answer (A13/A21/A22/A25/A27/A38/A62/A63/A65/A68 — one
look at `docs/hud/`) or says "do not build before that one is". So the
B track again, and this time its smallest item is about the loop's own
evidence rather than about JarvisOS.

**What the claim was worth.** Sixty journal entries say some version of
"nine mutations, nine caught". That sentence is the only evidence in
this repo that the tests an iteration just wrote have teeth — nothing
else distinguishes a suite that pins behaviour from a suite that
executes code and asserts nothing. It was produced by hand: edit the
source, re-run pytest, read the colour, put the file back. Iteration 70
found the hole. CPython validates a cached `.pyc` against the source's
(mtime in whole **seconds**, size), so an equal-length edit written
inside the same second as the write before it reuses stale bytecode:
pytest passes, the loop writes "survived", and the mutant never ran.

**So this is not an automation of the old practice.** It is the old
practice plus the two controls it never had, which is the whole of why
it was worth a file.

*The canary.* Before a single mutation is graded, the target file is
made impossible to import — one `raise ImportError` appended at column
zero — and the suite MUST go red. If it stays green the tests do not
execute that file at all, every mutation of it would be a silent
survivor, and the harness reports NOTHING rather than a perfect score.
This asks the suite the question the hand practice assumed the answer
to, and it is stronger than any amount of reasoning about bytecode:
it is an experiment, not an argument.

*A cache that cannot be stale.* Every suite run gets its own empty
`PYTHONPYCACHEPREFIX`, so no run can read bytecode another compiled and
the in-tree `__pycache__` directories become unreachable rather than
deleted. Per-run and impossible to forget, which "remember to clear the
cache" is not.

**A correction to B48 as it was written, found by reproducing it.**
`python -B` alone does nothing about this bug. It sets
`dont_write_bytecode` — it stops the cache being WRITTEN, and the read
is the half that bites. Measured three ways in a subprocess, with an
equal-length edit and the mtime put back: plain reads the stale value,
`-B` reads the stale value, a fresh cache prefix reads the new one. The
half that actually worked in iteration 70 was clearing `__pycache__`.
Both un-fixed runs are kept in the test as controls, because a probe
that can only pass is not a probe — the same lesson A34 learned about
counting zero frames.

**The other things it refuses to do**, each because the hand practice
could get it wrong quietly: a red baseline aborts before anything is
touched (a broken suite catches every mutation for free); a hunk that
matches twice is an error, not a coin flip about which copy moved; a
mutation identical to the original is an error; the file is restored
even when the runner raises; and the suite runs ONCE MORE at the end
with the tree back as it was, because iteration 70's actual tell was a
failure on an already-restored file and the next thing the loop does
should not be built on a tree it has quietly broken.

**The re-run half of the item, and what it found.** B48 said past
equal-length numbers were "worth ONE re-run, not trusted". Iteration
69's three equal-length mutations on jv-ears went back through the
controls: 3/3 caught, that entry stands. Worth writing down WHY they
stand, because it is nearly luck — `test_health_watch.py` computes its
expectations from the very constants it mutates
(`TICKS_PER_PERIOD = HEALTH_PERIOD_S / HEALTH_WATCH_S`), so moving one
moves the code and the assertion together. What caught all three was
the two ABSOLUTE claims in that file (`HEALTH_MIN_GAP_S <
HEALTH_PERIOD_S`, `seen_at < HEALTH_PERIOD_S`). A suite parameterised
on its own constants needs at least one assertion that is not; raised
as **B50**, with the file/line limit of the canary.

- tests: `bash ops/ralph/runtests.sh tools` — **173 green, was 138**
  (35 new: the spec grammar and its eight refusals, the exactly-once
  edit rule, the canary's shape, the run's order
  (`clean → canary → mutant → clean`), one canary per FILE rather than
  per mutation, a red baseline aborting untouched, a canary that LIVES
  aborting the whole run with no mutation executed, restore through a
  raising runner, a tree still red after the last restore, and the four
  exit codes the loop reads with `$?`). **Twelve mutations on the
  harness, by the harness, twelve caught** — including the canary never
  planted, the cache prefix left shared, the restore dropped, and the
  escape check opened. The first self-run scored 11/12: the survivor was
  a `main()` that returned 0 with a mutation still standing, which is
  the one case the exit code exists for, and the four tests that close
  it were written because the harness found it.
  `bash ops/ralph/runtests.sh jv-ears` — 114, unchanged, run six times
  by the harness and green at both ends.
- build: `nixos-rebuild build --flake .#ares` green. No schema change,
  no jv-act, no boot path, no pins, no service touched, no QML (so no
  HUD shots to re-take). Nothing here is on the bus or in the closure —
  `tools/mutate.py` is read by no derivation.
- files: tools/mutate.py, tools/tests/test_mutate.py,
  ops/ralph/mutate.sh, ops/ralph/README.md, ops/ralph/PLAN.md
- commit: 3961e85
- next: **B49** extends the canary to QML and Rust, where the
  stale-bytecode half cannot bite but "does this suite even execute the
  file I am mutating" is exactly as unanswered — and the A track has
  been claiming QML mutation numbers for thirty iterations. **B38's**
  last unexamined service is jv-voice, and reading it for this iteration
  turned up that its only fault (`synthesis/playback error`) already
  beats immediately, so what is left there is B47's latching question
  and not a build. Everything else small is a human's: **B43/B47** are
  one question asked three times ("may `jv health --check` be red on an
  ordinary day?"), Track A is one look at `docs/hud/` away from
  unblocking five items, and **B10/A28** — one live recording of one
  spoken turn on ares — is still the biggest thing a human can hand
  this loop.

## 2026-09-24 — iteration 72 — B49: the harness in three languages, and what it found in two

Track A is still where the ladder points and still where every open item
is a human's (A13/A21/A22/A25/A27/A38/A47/A55/A62/A63/A65/A68 — one look
at `docs/hud/`, or one decision about an IPC seam) or says "do not build
before that one is". So B49, which iteration 71 raised and which is
about the loop's own evidence: `ops/ralph/mutate.sh` graded PYTHON only,
so the thirty-odd QML claims and every Rust one were still produced by
the hand practice iteration 70 caught out.

**What was built.** `--runner {tests,qml,cargo}`, with a `Language`
holding the four things that differ: which script runs the suite, which
file suffixes it may grade, what a canary looks like, and what a private
cache means. A `raise ImportError` for Python, an unparseable `***` line
for QML, a `compile_error!` for Rust. Each makes a slightly different
claim and the Rust one is the weakest — a `compile_error!` proves the
file is compiled into the crate, not that any test exercises it, so a
Rust survivor means "no test asserts this line" and never "the tests do
not load this file". Its docstring says so. The suffix check is not
pedantry: `--runner tests` on a `.qml` file would append a Python
`raise` to QML, which parses as nothing, so the canary would LIVE and
the abort would blame the tests for the operator's mistake.

**B49's own premise was wrong about both new languages.** It said the
stale-artifact half "cannot bite" QML and Rust. It bites both.

QML has the bug exactly. `qmltestrunner` writes compiled QML to
`$XDG_CACHE_HOME/qmltestrunner/qmlcache/*.qmlc` and validates it against
(mtime, size) just like a `.pyc`, so an equal-length edit with the mtime
put back passes a test asserting the value the source no longer holds.
Reproduced with the real Qt in a subprocess, with the un-fixed run as
the control, exactly the shape B48's `.pyc` test has. It is arguably
worse than the Python case: `__pycache__` sits beside the source where
someone might think to clear it, and this cache sits in the user's HOME
where nothing in this repo ever would. Both halves of the fix work
independently — a fresh `XDG_CACHE_HOME` and `QML_DISABLE_DISK_CACHE=1`
— and the harness sets both, so the guarantee does not depend on Qt
honouring the first.

Rust made the same lie from the mtime side, and **the harness's own new
control was the cause.** Cargo cannot be given a private cache cheaply
(a fresh `CARGO_TARGET_DIR` per run recompiles the world a dozen times),
so it got the other guarantee: every write stamped a whole second newer
than the last. The first real cargo grading then ended with the tree
byte-for-byte clean and `proto::tests::matching` FAILING — iteration
70's exact tell, in a third language. The counter started when the run
did and added one second per write; the run spent forty seconds
compiling; so the restored file claimed start+5 s while the artifacts
cargo had just written said start+35 s. Cargo asks only "is any source
newer than what I built", read the restore as thirty seconds old, and
skipped the rebuild. Every stamp now re-reads the clock, which is the
one line that makes the rule true for a suite of any speed. Worth being
plain about what caught it: **B48's run-the-suite-once-more-at-the-end
check, added for precisely this and firing on its first real use.**

**Two findings from USING it, which is the half a tool does not give
you.**

`--runner qml` grades `shell/jv-hud/core/` and nothing else. A canary on
`StatePlate.qml` LIVED — the suite stayed green with the file made
unparseable — because `shell/jv-hud/tests/*` import `"../core"` and
never a plate. So every QML mutation number ever claimed about a
top-level plate through `qmltest.sh` meant nothing, and the harness now
refuses those rather than grading them immune (exit 2, mutation never
executed). The plates ARE exercised, by `ops/ralph/hudshots.sh`, which
copies the whole shell into a stage and drives the real plates — and
which already isolates its own QML cache per run by construction.
Raised as **B51**: it is a fourth runner, and the only one that can
grade a plate at all.

Re-graded PlateStack's nine-caught claim from the A15 iteration through
the controls — three of the nine (the unaskable-child fail-safe
inverted, the children never consulted, the surface never unmapped),
3/3 caught, canary dead. That entry stands.

`--runner cargo` found a real survivor on its first honest run:
`topic_matches` compares `topic.len() > prefix.len() + 1`, so `audio.`
— the separator with an empty leaf — does not match `audio.*`, and the
`>=` mutant survived because nothing asserted it. Deliberate since the
matcher was written, written down nowhere. One line in `proto.rs`'s
test closes it and the re-grade caught the mutant. That is the harness
earning its keep rather than describing itself.

- tests: `bash ops/ralph/runtests.sh tools` — **190 green, was 173**
  (17 new: the three canaries and what each keeps intact, the QML
  stale-cache reproduction with its two controls, `qml_env` and the
  deliberately-empty `cargo_env`, the stamp that must not fall behind a
  slow clock, the stamp that must keep increasing, the restore that
  leaves bytes identical and mtime newer, the wrong-grader refusal
  before any suite runs, the language table checked against the scripts
  `ops/ralph/` really has, and the `--runner` flag reaching `run`).
  **Nine mutations on the new code, nine caught** — the QML canary
  reverted to the Python one, the Rust canary commented out, the QML
  disk cache left on, the QML cache prefix left pointing at HOME, the
  suffix guard opened, the clock re-read dropped (the cargo bug,
  restored), the stamp frozen, the language check deferred past the
  suite, and an unknown `--runner qml` target accepted.
  `bash ops/ralph/qmltest.sh` — 585, unchanged, run eight times by the
  harness and green at both ends. `bash ops/ralph/cargotest.sh jarvisd`
  — 128+39+8, one more than before, run nine times and green at both
  ends.
- build: `nix build .#jarvisd` and
  `nixos-rebuild build --flake .#ares` green. No schema change, no
  jv-act, no boot path, no pins, no QML touched (so no HUD shots to
  re-take), no service behaviour changed — the one non-harness edit is
  an assertion added to a test module.
- files: tools/mutate.py, tools/tests/test_mutate.py,
  services/jarvisd/src/proto.rs, ops/ralph/mutate.sh, ops/ralph/README.md
- commit: 4fa5991
- next: **B51** is the fourth runner and it is the one the A track needs
  — `hudshots.sh` is the only suite that loads a plate, so it is the
  only way a plate mutation can ever be graded, and it already stages a
  fresh copy with its own cache so most of the work is an output
  directory that is not `docs/hud/`. **B50** (a suite parameterised on
  its own constants needs one claim that is not) is now cheap to
  discharge service by service, since a re-grade is one pasted spec.
  Everything else small is a human's: **B43/B47** are one question asked
  three times ("may `jv health --check` be red on an ordinary day?"),
  **A47** is one decision (OCR, an IPC seam, or leave four checks saying
  what they say) that unblocks **A55** with it, Track A is one look at
  `docs/hud/` away from unblocking ten items, and **B10/A28** — one live
  recording of one spoken turn on ares — is still the biggest thing a
  human can hand this loop.

## 2026-09-24 — iteration 73 — B51: the runner that can grade a plate, and the two things it found

Track A is where the ladder points and every open item there is still a
human's (A13/A21/A22/A25/A27/A38/A47/A55/A62/A63/A65/A68 — one look at
`docs/hud/`, or one decision about an IPC seam) or says "do not build
before that one is answered". So B51, which iteration 72 raised and
which is Track A's tooling: `ops/ralph/mutate.sh` could not grade a
single one of the HUD's ten plates.

**Why it could not.** B49 measured what `--runner qml` covers and the
answer was `shell/jv-hud/core/` and nothing else: `qmltest.sh` imports
`"../core"` and never a top-level plate, so a canary on `StatePlate.qml`
LIVES and the harness refuses the file. The plates ARE exercised, by
`ops/ralph/hudshots.sh`, which copies the whole shell into a `mktemp`
stage, substitutes the two Quickshell-bound singletons and drives the
real plates through `tst_shots.qml` and `tst_sequence.qml`. It was one
argument away from being a runner.

**What was built.** `--runner shots hud`, the fourth runner. Two things
had to be solved and both are in the `Language` table rather than in a
special case: it writes thirteen PNGs and DEFAULTS to `docs/hud/` — the
committed contact sheet — so `scratch_out` hands it a directory inside
the run's own scratch, thrown away with the rest of it (the sheet is
never touched, and the run log naming `/tmp/jv-mutate-*/run001/shots` is
the proof). And its cost is measured rather than promised: **53 s a
suite run**, three times `qmltest.sh`'s 14 s, so `main` now prints the
run count — one baseline, one canary per file, one per mutation, one
baseline — before the first run starts. A three-mutation grading over
two files is seven runs and took 265 s.

**The canary means something weaker here, and it was checked rather than
assumed.** `hudshots.sh` runs `qmllint` over the whole staged shell
before either driver starts, so an unparseable `***` line is a LINT
failure: planting one on `StatePlate.qml` exits 255 out of qmllint with
no driver reached. That is the Rust canary's limit in a third language —
it proves the file is in the stage, not that anything instantiates it —
and the docstring says so, pointing at the gate that does make the
stronger claim (`test_every_plate_in_the_shell_is_lit_in_some_shot`,
next to the pin that ties `Corner.qml`'s membership and ORDER to
`shell.qml`'s). What it does catch is a file the stage DROPS, and that
was run rather than reasoned about: `--runner shots` on
`shell/jv-hud/shell.qml` aborts with exit 2 after two runs, because the
stage removes `shell.qml` and `tests/`. Worth saying plainly: **no
runner in this harness can grade `shell.qml`** — it is the Quickshell
half no other engine can load — and the abort now says which two files
those are instead of leaving the reader checking a target that was
correct.

**What it found on its first honest run: 1 of 3 caught.**

The first survivor is the one worth the iteration. `StatePlate.shown` is
`root.voice.known && !root.voice.idle`; drop the second half so the
plate lights while NOTHING is happening, and all thirteen photographs,
all fifteen tests the two drivers ran and all 585 QML tests came out
exactly as before. The reason is precise: no recording and no composed shot has
ever carried a KNOWN idle. jv-voice is in none of the recordings
(B10/A28), so `unknown` — the HUD unable to see — is covered everywhere
and `idle` — the machine at rest, which is a different claim and the
first decision this HUD ever made (A3, §06's earned emptiness) — had
never reached a plate at all. Closed here, because it is one test: a
hand-written `speech.state` frame from jv-voice, fresh at its own `ts`,
and the corner must stay dark. Re-graded through the same runner
afterwards: **1/1 caught**, 4 runs, 173 s.

The second survivor is reported and not closed. `dotColor` can spend the
ember on every state that is not idle — the exact opposite of "scarcity
is the point" — and nothing anywhere notices, because the sheet is
WRITTEN and never COMPARED. Nothing in this repo asserts what a plate
says or what colour it says it in; `litNames` asserts which plate is up,
which is A47's open question one layer further in. Raised as **B52**,
with the cheap shape noted: A45 already made the PNGs byte-reproducible,
so comparing a run's output against the committed sheet would turn all
thirteen into assertions at once.

- tests: `bash ops/ralph/runtests.sh tools` — **199 green, was 190**
  (9 new: the scratch output dir reaching `hudshots.sh` and never
  `docs/hud`, only the shots runner asking for one, a fresh unused
  scratch per run checked while the suite holds it rather than after the
  run has deleted it, `shots_env` disabling the disk cache the script
  itself does not set, the suffix guard, the abort naming `--runner
  shots` when a core canary lives, the abort naming the two files the
  stage drops, a target the shots runner does not grade, and the run
  count printed before a 53 s suite starts).
  **Nine mutations on the new code, nine caught** — the scratch dir not
  appended (a grading over the committed sheet), every runner asking for
  one, the shots suffixes opened to `.py`, its target check removed, the
  QML disk cache left on, both canary hints emptied, the run count short
  by the closing baseline, and the count computed but never printed.
  `bash ops/ralph/qmltest.sh` — 585, unchanged, green before and after.
  `bash ops/ralph/hudshots.sh` — **16, was 15**; the 13 shots came out
  byte-identical, which is the claim the new test had to leave intact.
  **Plates, through the new runner: 3 mutations, 1 caught, 2 survived**
  (both survivors described above), then **1/1** on the re-grade.
- build: `nixos-rebuild build --flake .#ares` green. No schema change,
  no jv-act, no boot path, no pins. `shell/jv-hud/` was not modified at
  all — the only QML edit is one test in `tools/hudshots/scene/`, which
  is why the sheet is byte-identical and there is no HUD diff to look at.
- files: tools/mutate.py, tools/tests/test_mutate.py,
  tools/hudshots/scene/tst_sequence.qml, ops/ralph/mutate.sh,
  ops/ralph/README.md
- commit: 9904c46
- next: **B52** is the sharpest thing left that is the loop's own — the
  sheet is thirteen pictures nothing compares, and A45 already made them
  byte-reproducible, so it is a comparison and a decision about where
  "expected" lives rather than new machinery. **B50** (a suite
  parameterised on its own constants needs one claim that is not) is
  still cheap service by service. **A56** matters slightly more now:
  `hudshots.sh` is a mutation runner and still not in `nix build
  .#jv-hud`. And the human-sized items have not moved: **B43/B47** are
  one question asked three times, **A47** is one decision that unblocks
  **A55** with it, Track A is one look at `docs/hud/` away from
  unblocking ten items, and **B10/A28** — one live recording of one
  spoken turn on ares — remains the biggest thing a human can hand this
  loop, and is now also what would put a real `speech.state idle` in a
  recording instead of in a hand-written frame.

## 2026-09-24 — iteration 74 — B52: the thirteen pictures, read back

Track A is where the ladder points and every open item there is still a
human's — one look at `docs/hud/`, or one decision about an IPC seam —
so this is iteration 73's own finding, closed. B51 built the runner that
can grade a plate and its first honest run found two survivors. A69 (the
`idle` plate) was closed there. This is the other one, and it was the
sharper of the two: `StatePlate.dotColor` can spend the ember — the one
accent §06 reserves for a machine that is genuinely doing something — on
every state that is not idle, the exact inversion of "scarcity is the
point", and all thirteen photographs, all fifteen driver assertions and
all 585 QML tests came back exactly as they were.

**The reason is one sentence.** `hudshots.sh` WRITES the sheet and never
READS it. Nothing in this repo had ever opened one of those PNGs.
`litNames` asserts which plate is UP, which is a different claim and is
A47's question one layer further in; what a plate SAYS, and what colour
it says it in, was asserted nowhere.

**Where "expected" lives.** The only real decision here, and it has to
be git. A run that renders into `docs/hud` and then compares against
`docs/hud` has compared a file to itself — and the refresh has to stay
one command, so a second committed copy would be two things to keep
matching. So both paths are checked against `HEAD:docs/hud`: the grading
run (which renders into `--runner shots`'s scratch directory) and the
refresh run (which renders over the sheet). The consequence is that a
deliberate HUD change now ends `hudshots.sh` nonzero — which is the
report and not a failure: the new PNGs are on disk, look at them, commit
them, the next run is green. `docs/hud/README.md` said the opposite in
so many words ("not byte-compared against anything — a pixel assertion
breaks when a font ships a new version"); that worry is answered by the
fonts and Qt both being pinned from the flake, which is what A45 made
these bytes reproducible for, and the paragraph is rewritten with a
test holding it.

**What it says.** Bytes first — identical bytes are the same picture and
that is the ordinary case, so thirteen comparisons cost nothing. When
they differ, both are DECODED (a small PNG reader: 8-bit truecolour,
all five scanline filters, multiple IDATs, refusing 16-bit, interlaced,
palette, a header that lies about its size, anything that is not the
shape Qt's offscreen grab writes) and the finding is a sentence. Not
"the PNGs differ": B51's survivor, re-graded through the same runner,
now reads

    02-listening.png: 36 px of 206400 differ (0.02%), inside x 187..192, y 31..36
        (187,34)  #41939A -> #BD5C3F
    03-heard.png: 36 px of 206400 differ (0.02%), inside x 195..200, y 31..36
        (195,34)  #59666F -> #BD5C3F

— one 6×6 dot, in the two shots where the mic is open and Jarvis is not
speaking, going from teal to ember. That is the ember spent where it was
not earned, said in the terms §06 uses. **1/1 caught.**

Two things the sheet gained on the way that are not the diff: the
comparison is in both directions, so a driver that quietly stops
photographing a plate is a finding rather than a smaller sheet; and
`01-quiet.png` is now asserted to be an unbroken field of the declared
backdrop — §06's earned emptiness, in bytes, for the first time. The
backdrop is deliberately not a theme colour, so any Jarvis ink anywhere
in the quiet shot is a plate that spoke when it should not have.

- tests: `bash ops/ralph/runtests.sh tools` — **228 green, was 199** (29
  new: the PNG reader under all five filters and across split IDATs, its
  four refusals, byte-equality vs pixel-equality, the counted and boxed
  and colour-named finding, sampling that spans the change, a size
  change reported as a size, an unreadable shot as a finding rather than
  a traceback, both directions of the sheet comparison, sheet order, the
  committed sheet against git, every shot at the scene's surface box,
  the quiet field, the script's wiring, the README's honesty, and three
  CLI runs end to end over the real thirteen).
  **Eleven mutations on the new module, eleven caught** — interlace and
  depth and data-length unchecked, Paeth predicting only from the left,
  truecolour filled transparent, a no-moved-pixels picture still
  reporting, alpha never shown in a colour, one sample instead of three,
  each direction of the sheet comparison dropped, and findings not
  failing the run. Canary died, baseline green before and after.
  `bash ops/ralph/qmltest.sh` — 585, unchanged. `bash ops/ralph/hudshots.sh`
  — 16, the 13 shots byte-identical and now compared.
  **B51's survivor, through `--runner shots`: 1/1 caught.**
- build: `nixos-rebuild build --flake .#ares` green. No schema change, no
  jv-act, no boot path, no pins. `shell/jv-hud/` was not modified at all,
  so the sheet is byte-identical and there is no HUD diff to look at.
- files: tools/hudsheet.py (new), tools/tests/test_hudsheet.py (new),
  ops/ralph/hudshots.sh, tools/mutate.py, ops/ralph/README.md,
  docs/hud/README.md
- commit: c15b6d0
- raised: **B53** — measured while closing this, not reasoned. With an
  uncommitted HUD change in the tree, `--runner shots` renders a sheet
  that differs from HEAD, the comparator exits 1, the BASELINE is red and
  the harness aborts with "fix the suite first". The refusal is right and
  the sentence is wrong: the suite is fine, the sheet is stale, and the
  fix is one `hudshots.sh` and a commit. One conditional line in
  mutate.py's abort.
- next: B51's two survivors are both closed, so the loop's own mutation
  story is as far as it goes without a human. **B50** (a suite
  parameterised on its own constants needs one claim that is not) is
  still the cheapest open item, service by service. **A56** — the
  sequence suite runs in `hudshots.sh` and not in `nix build .#jv-hud` —
  matters a little more each time that script grows a gate, and it now
  carries the sheet comparison too. The human-sized items have not
  moved: **B43/B47** are one question asked three times, **A47** is one
  decision that unblocks **A55** with it, Track A is one look at
  `docs/hud/` away from unblocking ten items, and **B10/A28** — one live
  recording of one spoken turn on ares — remains the biggest thing a
  human can hand this loop.

---

## 2026-09-25 — iteration 75 — B50: the constants nothing was holding

Track A is still one human look away from unblocking (A47/A55/A62/A63/A68
are all the same two questions asked about `docs/hud/`), and every item in
`docs/optimization-backlog.md` is human-review-required by construction, so
this took the B track's cheapest open item — and it turned out to have a
real bug under it.

B50's claim was a lesson learned once, in one file: a suite that computes
its expectations FROM the constants it tests moves the code and the
assertion together, so a whole class of mutation is ungradeable by
construction, and the only thing that saves it is one claim written in
absolute units. This iteration RAN that as a sweep instead of repeating it
as advice. Every Python suite that imports a constant out of the code it
tests was mutated at that constant and graded by `ops/ralph/mutate.sh`.

**Four survived, four were caught**, and the split is the lesson exactly:

- survived: `FIRST_BACKOFF_S` 0.5 -> 2.0 and `MAX_BACKOFF_S` 8.0 -> 30.0
  (jv-hud-bridge), `TURN_GAP_S` 0.5 -> 2.0 (jv-voice), `VERDICT_TIMEOUT_S`
  60 -> 300 (jv-compat).
- caught: `STALL_S` 1.0 -> 8.0 (jv-ears), `SAFETY_MARGIN_BYTES` x3 and -> 0
  (jv-brain), `ENTROPY_SUSPECT` 7.2 -> 5.0 and -> 7.99 (jv-guard),
  `ASR_LATENCY_S` 2.2 -> 4.4 (harness).

Every catch came from an assertion written in absolute units. The jv-ears
one is the cleanest illustration in the repo: five lines in
`test_capture_meter.py` say `capture_stall_s == CaptureMeter.STALL_S` and
one line in the middle of a different test says `clock.now += 5.0`, and
that sixth line is the entire reason an eight-second stall budget cannot
ship. Every survivor's file had no such line.

Each survivor now has one. Not a second copy of the tuning — bounds on
what the number exists to be true FOR, deliberately looser than the
shipped value in both directions, with the reasoning in the docstring:
the bridge's first retry has to land inside the grace `LinkState.qml`
waits out before it draws NO BUS and must not be a spin; its ceiling is
the worst-case staleness of the whole HUD after the bus returns; the
voice's gap bridges A BUS HOP and not the brain, which is what its own
comment says it deliberately does not do.

**The real find was jv-compat.** Asking what `VERDICT_TIMEOUT_S` had to be
true for turned up a disagreement between two services that never read
each other: jv-compat stopped listening for `guard.verdict` after 60 s and
then failed closed, while jv-guard's `ClamAVScanner` gives clamscan 120 s.
An installer whose scan ran 70 s was refused with "screening unavailable —
refusing to install (fail closed)" while the only authoritative engine on
this machine was still scanning it and about to publish `clean` onto a
topic nobody was reading. That is not invariant 8's guarantee working —
it is a clean binary refused for a reason that was not true. Raised to
180 s and the relation pinned, read out of jv-guard's SOURCE rather than
imported (invariant 1: services never import each other), in the shape
`RECONNECT_CADENCES` already uses for the two cadences `LinkState.qml`
depends on. Both directions of the fix were defensible; this one was taken
because refusing a clean binary is the worse failure, and the other is
written down as B54 for a human.

One more thing fell out of the same file: `test_fail_closed_when_no_verdict`
said "we shorten the timeout via monkeypatch" and then assigned
`inst_mod.VERDICT_TIMEOUT_S = 1.0` in place, never putting it back. Every
jv-compat test after it ran with a one-second screening window, and the
suite's result depended on its own order. It is a real `monkeypatch` now.

- tests: `runtests.sh jv-compat` **10 green, was 9** · `jv-hud-bridge`
  **26, was 25** · `jv-voice` **28, was 27** · `jv-guard` 33, unchanged.
  Re-graded after the fix: jv-hud-bridge **4/4 caught** (both retunes plus
  a ceiling below the first retry and a backoff of zero), jv-voice **3/3**
  — including the 0.5 -> 0.9 edit that `mutate.sh`'s own docstring uses as
  its usage example and that survived until today — and jv-compat **2/2**.
  The cross-service arm could not be graded by the harness and was checked
  by hand instead (see B55): with jv-guard's clamscan budget raised to 600
  the new test fails, and with its `"clamscan"` argv renamed so the regex
  misses, it fails with "cannot find clamscan's timeout ... which is how it
  drifted" rather than passing quietly.
- build: `nixos-rebuild build --flake .#ares` green. No schema change, no
  jv-act, no boot path, no pins. One production constant moved
  (`VERDICT_TIMEOUT_S`), in a non-forbidden service, with the relation that
  forced it pinned by a test.
- files: services/jv-compat/jv_compat/install.py,
  services/jv-compat/tests/test_compat.py,
  services/jv-hud-bridge/tests/test_bridge.py,
  services/jv-voice/tests/test_voice_service.py
- commit: 40e395f
- raised: **B54** (the 180 s wait is now the longest an install can sit
  with nothing on `compat.install` since `fingerprinted`, and the HUD says
  nothing during it — a human should weigh that against cutting clamscan's
  budget instead) and **B55** (the harness cannot grade a relation between
  two files when one is READ rather than imported; its canary correctly
  refused and exited 2, and there are now three such relations in the repo
  that must be checked by hand).
- honest note: the first jv-voice run after adding its test showed one
  unrelated failure in `test_streamed_reply_is_one_speaking_idle_pair` at
  50 s of wall clock against its usual 21 s — the jv-ears mutation was
  running on the same machine. It passed on every run since, alone. Worth
  remembering that this suite's timing assertions are not load-proof.
- next: **B53** is the one concrete cheap item left (one conditional line
  in mutate.py's red-baseline abort, so `--runner shots` says "the SHEET is
  stale" instead of "fix the suite first"), and **B55** is the same file
  with a harder question in it. Otherwise the loop is where it has been for
  several iterations: **Track A is one human look at `docs/hud/` away from
  unblocking ten items** (A47, A55, A62, A63, A68 and the A21/A22/A25
  cluster are two questions asked five ways), **B43/B47** are one question
  asked three times, and **B10/A28** — one live recording of one spoken
  turn on ares — remains the biggest thing a human can hand this loop.

## 2026-09-25 — iteration 76 — B53: the red baseline that was never the suite's fault

Track A is still one human look at `docs/hud/` away from unblocking ten
items, and `docs/optimization-backlog.md` is human-review-required by
construction, so this took the one concrete cheap item the last iteration
left: the abort the loop will hit the first time it mutates a plate it has
just changed.

The shape is worth stating because it is a harness lying about its own
health. `--runner shots` is the only one of the four runners that reads a
COMMITTED artifact back — B52 made `hudshots.sh` compare every PNG it
renders against `HEAD:docs/hud`, which is the only assertion in this repo
about what the HUD LOOKS like. The price is that an uncommitted change to a
plate makes the BASELINE run red, so the harness aborts with "the baseline
suite is RED before any mutation ... fix the suite first" — and the suite is
fine. The sheet is stale, and the fix is one command.

The refusal itself is right, and that is the point: it will not make a claim
it cannot make. Only the sentence was wrong, and it sent the reader to the
one place where nothing is broken.

So the red-baseline abort now carries a per-runner `baseline_hint`, and for
the runner that has this failure mode it is a MEASUREMENT of the working
tree rather than a fixed sentence — because a fixed sentence would be wrong
half the time. Three answers:

- plates differ from HEAD → name them, and print the refresh: run
  `hudshots.sh`, LOOK at the new PNGs, **commit** them. The "commit" is not
  politeness. `hudsheet.py` compares against `HEAD:docs/hud`, so PNGs that
  were re-rendered and left unstaged leave the baseline exactly as red as
  before, and the hint says so when it sees a modified `docs/hud`.
- the tree matches HEAD → say so. There is nothing for the read-back to
  disagree with, the red is real, and a harness that sent the reader off to
  re-render a contact sheet would be pointing at the wrong thing.
- git cannot answer → say NOTHING. `_modified` returns `None` for "I could
  not look" and `[]` for "nothing is modified", and the caller must not
  print the first sentence when it only has the second. The abort it
  decorates is a refusal to make a claim; a hint that guessed at the reason
  would be the one thing this harness never does. That distinction was not
  in the first draft — writing the mutation list for it is what found it,
  which is the second time this month that asking "what would catch this"
  changed the code rather than the tests.

**Verified end to end, not reasoned.** With the listening dot repainted
ember in the worktree (`Theme.teal` -> `Theme.ember` in `StatePlate.qml`,
restored after), a real `bash ops/ralph/mutate.sh --runner shots hud` now
aborts with: "The SHEET may be stale rather than the suite (B53): 1 file(s)
under shell/jv-hud differ from HEAD (shell/jv-hud/StatePlate.qml), and
hudshots.sh compares every PNG it renders against HEAD:docs/hud ... Run
`bash ops/ralph/hudshots.sh`, LOOK at the new PNGs, commit them, then
grade." One suite run, one abort, exit 2, the sheet in `docs/hud` untouched
(the grading run renders into its own scratch).

- tests: `runtests.sh tools` **234 green, was 229** — five new, four of them
  against a throwaway git repo because a hint that measures the tree cannot
  be tested against a bare directory. Graded with the harness on itself:
  **6 mutations, 6 caught** (the stale-sheet branch inverted, the
  could-not-look guard dropped, a git failure read as a clean tree, the
  advice stopping short of "commit", the uncommitted-sheet note inverted,
  and the hint never reaching the abort). Canary red, closing baseline green.
- build: `nixos-rebuild build --flake .#ares` green. No schema change, no
  jv-act, no boot path, no pins, no production code at all — this is the
  loop's own tooling.
- files: tools/mutate.py, tools/tests/test_mutate.py, ops/ralph/mutate.sh
- commit: 002ee84
- raised: **B56** — the harness prints ONE line of each suite log and keeps
  none of it. Measured today: the line it chose for the red baseline was
  "something drew a different picture than the one in docs/hud.", the tail
  of the comparator's closing paragraph, which is the sentence for the case
  that was NOT what happened. B53 fixes the one abort where the loop was
  actively misled; the general gap (a survivor or a dead canary cannot be
  investigated without re-running a 53 s suite by hand) is cheap to close —
  each run already has a private scratch directory to write its log into.
- next: **B56** is the natural follow-on and is small. Otherwise unchanged
  and worth repeating, because it is now several iterations old: **Track A
  is one human look at `docs/hud/` away from unblocking ten items** (A47,
  A55, A62, A63, A68 and the A21/A22/A25 cluster are two questions asked
  five ways), **B27** needs one decision between three named options before
  any HUD work on no-wake windows can start, **B43/B47/B54** are one
  question asked three times, and **B10/A28** — one live recording of one
  spoken turn on ares — remains the biggest thing a human can hand this
  loop.

## 2026-09-25 — iteration 77 — B56: the suite output the harness captured and threw away

Track A is still one human look at `docs/hud/` away from unblocking ten
items — every remaining A item is either a human decision or carries its
own "do NOT build this until X is answered" — so this took the follow-on
the last iteration raised and called small. It was, and it found two
things in itself on the way, which is the part worth writing down.

The gap: `script_runner` ran a suite with `capture_output=True`, printed
`(proc.stdout or proc.stderr).splitlines()[-1]`, and dropped the rest with
the scratch tree. For `--runner tests` that line is a pytest summary and is
roughly the right line. For `--runner shots` it is whatever the
comparator's closing paragraph happened to end with, and B53 is the record
of that being actively wrong at the worst moment. B53 fixed the one abort
where the loop was misled. What was left is the general shape: a survivor,
a canary that lived or a red baseline could not be investigated at all
without re-running the suite by hand — 53 s a run under `shots`.

Each run already had a private scratch directory. It now holds three
things, and the ordering of two of them is the only interesting decision:

- `suite.log` — the command, the exit code, and BOTH streams in full.
  Written by `script_runner` and not by `run()`, because only a runner
  knows whether it has output to keep.
- `WHAT` — what the run was, written **before** the suite starts. The
  `INDEX` line is appended after, with `pass`/`fail`, and that is the
  half a runner that dies takes with it. The run nobody can name is
  exactly the one being investigated, so the name goes down first.
- the tree is **kept** on a survivor or an abort and **swept** on a clean
  sweep. A grading where everything was caught has nothing in it anyone
  will open, and under `shots` it is a dozen runs of thirteen PNGs. Each
  abort names the one run that went wrong, not the tree; the CLI prints
  the tree under the summary, and says to delete it.

The printed line stays ONE line and now carries its run number. It is a
progress indicator, not the evidence, and keeping those two separate is
the whole lesson of B53: choosing one line out of a suite's output is a
guess about which line matters.

**Reproduced end to end on the real case, not reasoned.** With the
listening dot repainted ember (the same edit B53 used), a real
`--runner shots` grading aborted, and the printed line was still
"something drew a different picture than the one in docs/hud." — the
sentence for the case that was NOT what happened. Four lines above it in
the now-kept 41-line log: "If you changed the HUD on purpose, this is the
sheet catching up." Next to it, `run001/shots/` with all thirteen PNGs
that run drew, which under a surviving PLATE mutation is the only way to
SEE what the mutant looked like.

**Two things it found in itself.**

1. Keeping trees made the harness's own test suite leak. Dozens of tests
   drive `run()` to a survivor or an abort deliberately, and each now left
   a directory in the real `/tmp` forever — **189 of them after twelve
   suite runs**, which is how it was noticed rather than reasoned about.
   The harness is right to keep them (the caller is told where the tree is
   and owns it from there), so the fix belongs in the caller: an autouse
   fixture points `mkdtemp`'s default parent at pytest's `tmp_path`, and
   the trees stay real and inspectable while a test runs. A full suite run
   now leaves **0**. A new guard counts that nothing is created at all
   before the harness knows it has a file to mutate.
2. The first grading reported a genuine survivor, and it was a bad
   assertion rather than missing code: `test_the_cli_says_where_the_logs_
   were_kept` asserted the path alone, and `summary()`'s survivor line
   already contains that path as a prefix — so the assertion was satisfied
   by a different mechanism and graded the CLI's own line immune. `if
   report.logs is not None:` -> `if False:` survived. It asserts
   `f"kept: {kept}"` now, and the re-grade caught it.

- tests: `runtests.sh tools` **245 green, was 234** — eleven new, plus two
  existing ones updated for real behaviour changes (a run dir is no longer
  empty when the suite gets it — it holds the harness's own `WHAT`, and
  the test now pins that it holds *nothing else*; and the "the hint said
  nothing" test splits off the sentence every abort now ends with, so it
  still holds the strong claim rather than the recognisable one).
  Graded with the harness on itself: **11 mutations, 11 caught** — the
  truncated log, the unnamed printed line, the name written after the run
  instead of before, sweeping on an abort, sweeping a survivor, keeping a
  clean sweep, an INDEX with no pass/fail, the canary abort losing its
  run, the survivor losing its run, the CLI keeping the path to itself,
  and a tree made before the target file is known to exist. Canary red,
  closing baseline green, tree swept.
- build: `nixos-rebuild build --flake .#ares` green. No schema change, no
  jv-act, no boot path, no pins, no production code at all.
- files: tools/mutate.py, tools/tests/test_mutate.py, ops/ralph/mutate.sh
- commit: 6b2207b
- next: no new item raised — B56 closed what it described and the two
  things it found were fixed in the same commit. **B55** is the remaining
  harness gap and is a real design question rather than a flag (a canary
  for a source-READ relation must make the file unMATCHABLE, not
  unloadable), and there are now four such relations the grader declines
  to grade. Otherwise unchanged, and now several iterations old: **Track A
  is one human look at `docs/hud/` away from unblocking ten items** (A47,
  A55, A62, A63, A68 and the A21/A22/A25 cluster are two questions asked
  five ways), **B27** needs one decision between three named options,
  **B43/B47/B54** are one question asked three times, and **B10/A28** —
  one live recording of one spoken turn on ares — remains the biggest
  thing a human can hand this loop.

## 2026-09-25 — iteration 78 — B55: the five relations the grader kept refusing to grade

Track A is unchanged and still one human look at `docs/hud/` away from
unblocking ten items; every remaining A item is either a human decision
or carries its own "do NOT build this until X is answered", and the
optimization backlog is human-review-required end to end. B55 was the
one open item that was the loop's own, and it was raised as "a real
design question rather than a flag", which is what this is about.

**The gap, stated exactly.** Invariant 1 forbids one service importing
another. So every claim this repo makes about a relation BETWEEN two
services is made by reading the other's source and matching a line in it.
There are five:

- jv-compat's `VERDICT_TIMEOUT_S` against jv-guard's clamscan budget (B50)
- the HUD's wake-window fallback against `jv_ears/config.py`
- the HUD's capture-stall fallback against `jv_ears/audio.py`
- LinkPlate's grace against `jv_hud_bridge/bridge.py`'s first backoff
- LinkPlate's grace against `shell/jv-hud/Bus.qml`'s respawn interval

The harness declined to grade every one of them, and the refusal was
right: its canary makes the target impossible to LOAD, a suite that only
greps it never notices, the canary lives, and the run aborts rather than
printing a score it cannot stand behind. Both arms of B50's relation were
therefore checked by hand — edit, run, restore — which is the practice
B48 was written to delete.

**The design.** A canary for a source-read relation has to make the file
unMATCHABLE, not unloadable. So a file is offered its controls strongest
first — unloadable, then ERASED — and whichever kills the suite IS the
relation. Measured, never declared. That distinction is then carried all
the way into the report, because the two are genuinely different
sentences: a survivor on an executed file means "no test asserts this
line"; on a read file it means "no test matches this text". And it is not
only about survivors — "4 of 4 caught" against a file the suite greps is
a claim about a regex, so the summary says `the suite reads <file> — it
never runs it` whether or not anything survived.

Three decisions inside that, each with the alternative rejected in place:

1. **Erasure is EMPTY, not a marker.** Anything left in the file is
   something a regex somewhere might still find, and a canary that can be
   matched is not a canary. Its honest limit is the mirror of the Rust
   canary's and is written down rather than discovered later: a NEGATIVE
   claim ("this source contains nothing that looks like X") is green on
   an empty file too, so the harness will refuse to grade it. That is the
   refusing direction, which is the safe one — it declines to claim
   rather than claiming wrongly.
2. **The suffix stops being a refusal and becomes a choice of control.**
   `--runner tests` on a `.qml` used to be an error before any suite ran,
   and that error was wrong about a real case: the tools suite really
   does match a line in `shell/jv-hud/Bus.qml`. What the old rule was
   actually protecting — a Python `raise` appended to QML parses as
   nothing, so the canary would live for a reason that says nothing about
   the suite — is kept exactly: an off-language file is offered the ONE
   control it could ever fail, and never the wrong language's canary.
3. **A file that survives every control still aborts**, in two different
   sentences, because two different things went wrong. Both canaries
   lived = the suite has no relation with this file at all. Off-language
   and the erasure lived = the only relation this runner could have had
   is a read, and it does not read it. Naming an execution that was never
   on the table would send the reader looking for the wrong thing. Both
   live-canary runs are named now, not just the last — two live canaries
   are two suite logs, and which one you open depends on which relation
   you thought you had.

**Graded for real, which is the whole point.**

- `--runner tests jv-compat`, both arms of B50's relation, machine-run
  for the first time: **2/2 caught**. run002 is the load canary living on
  `scan.py` (10 passed), run003 the erasure killing it. The same grading
  put `install.py` through ONE canary, because it is imported — so both
  relations appear in one run and the summary distinguishes them.
- `--runner tests tools`, all four theme/budget mirrors **including the
  off-language `shell/jv-hud/Bus.qml`**: **4/4 caught**, 13 suite runs
  against a printed floor of 10. The three extra runs are exactly the
  three in-language files whose load canary had to be seen to live before
  erasure was the honest thing to try; `Bus.qml` cost one canary, not two.

The printed count says "at least" now for that reason.

- tests: `runtests.sh tools` **254 green, was 245** — nine new, plus
  three existing ones rewritten for a real behaviour change (the two that
  asserted "wrong grader" now assert which controls the suffix chooses,
  and the run-naming one asserts BOTH canary runs are named and the
  baseline is not). Graded with the harness on itself: **9 mutations, 9
  caught** — an erasure that left the file alone, an erasure that left a
  matchable marker, both directions of a `controls_for` that ignores the
  suffix, a relation reported as an execution whichever canary killed the
  suite, the summary's relation line dropped, the survivor caveat
  dropped, the read control handed the load canary, and an abort that
  names only its last run. Canary red, closing baseline green, tree swept.
- build: `nixos-rebuild build --flake .#ares` green. No schema change, no
  jv-act, no boot path, no pins, no production code at all.
- files: tools/mutate.py, tools/tests/test_mutate.py, ops/ralph/mutate.sh
- commit: 2c9800d
- next: **B57** raised — the harness can now grade a relation it could
  not, and grading four of the five in one run surfaced the next
  question: the erasure canary on `bridge.py` made FIVE tools tests fail,
  not one, so "the suite reads this file" is true of more than the
  relation being graded, and nothing distinguishes a suite that reads a
  file for one reason from one that reads it for five. Not a defect —
  the control proves what it claims — but it is the shape of the next
  overclaim if anyone reads the relation line as naming a single test.
  Otherwise unchanged and now several iterations old: **Track A is one
  human look at `docs/hud/` away from unblocking ten items** (A47, A55,
  A62, A63, A68 and the A21/A22/A25 cluster are two questions asked five
  ways), **B27** needs one decision between three named options,
  **B43/B47/B54** are one question asked three times, and **B10/A28** —
  one live recording of one spoken turn on ares — remains the biggest
  thing a human can hand this loop.

## 2026-09-25 — iteration 79 — B38: the period an off-schedule beat lands in

PLAN B38's last open half was one sentence — "jv-voice is the one service
nobody has read for this at all." The reading was the iteration. What it
found is not what B38 expected, and it is not B47 either.

**What B38 expected.** jv-voice publishes `degraded` the instant a
synthesis or playback failure reaches `_speak_one`'s handler, so it
already does the thing `schemas/sys.health.json` asks for ("every fixed
period, **and immediately on state change**"). Same as jv-guard, same as
jv-brain. Its gap is theirs — the fault is not LATCHED, the next periodic
beat says `ok` again while the condition is unchanged — and that is
**B47**, a human's call about what the CLI says on an ordinary day.
Nothing built for it here.

**What the reading actually found.** The schema asks for two things and
never says what the second does to the first. An off-schedule beat: does
it take over the period, or does the old timer keep running underneath
it? jv-voice, jv-guard and jv-brain all took the second answer, by
omission — they publish and leave `health_at` alone. **jv-ears and
jv-context took the first, and jv-ears wrote down why:**

> Before the publish, not after: the period is the beat's, not the bus's,
> and a change beat is this period's beat — leaving the timer alone would
> double-publish a change that happened to land near a boundary.
> — `jv_ears.main.pump_health`

Five services, one contract, two answers, and the two that are right are
right in two different shapes that share no code.

**Why the wrong answer costs something.** The `ok` that follows a fault
goes out with whatever was left of the period the fault interrupted.
Three quarters of the way through, the report has a quarter of a period
to live; at the boundary it has none. `bus.latest()` keeps ONE frame per
topic per publisher, so the HUD's HealthPlate and `jv health --check`
both read the newest: a `degraded` that was published truthfully, on
time, can be erased before anything could show it. That is a scan with no
signature engine, a dead sound card, an LLM that stopped answering — the
three reports each of these services exists to make.

jv-brain pays a second cost the others do not. Its `_state_model_share`
beat fires on the FIRST WORD OF EVERY SPOKEN TURN. Leaving the timer
alone made that an ADDED frame per turn on a topic meant to be quiet
(invariant 5), rather than that period's beat moved earlier. The fix
takes a frame off a busy machine; it never adds one.

**What was built.** `jarvis_bus.HealthBeat` — `due`, `beat()`, an
injected clock, a period it also declares so the body and the enforcement
cannot drift apart, and a `ValueError` for a period the schema's
`exclusiveMinimum: 0` forbids. The rule and its reasoning live in one
docstring instead of being rediscovered per service. Every beat in the
three services goes through it; jv-voice grew a `_beat()` so that there
is exactly one way for it to publish a heartbeat, which is the property
that makes "every beat owns a period" checkable by reading rather than by
remembering.

The stamp is taken BEFORE the publish, for jv-ears' reason. After the
await, the period would start from when the bus ACCEPTED the frame, so
every beat would drift later than the last — compounding, on the one
number consumers use to decide a service is dead.

**Three things deliberately not done.**
1. **jv-ears and jv-context are untouched.** Both already obey this, in
   shapes built around their own problems — a 4 Hz watcher with a 1 s
   flap floor because their state is a function of a clock; an
   event-driven pump woken by a fault setter. Rewriting either onto a
   common clock would risk behaviour that was reasoned out once and is
   correct, to unify code that is not duplicated.
2. **The latch is still B47's question.** All three still say `ok` again
   on the next beat. What changed is only WHEN that beat is.
3. **No schema change.** `period_s` is published as it always was; the
   only difference is that the number enforcing it and the number
   declared in the body are now the same object.

**Also: the gate was not testing the tree.** `ops/ralph/runtests.sh` runs
`python -m pytest` from the service's own directory, which puts that
directory first on `sys.path` — so `jv_guard` came from the worktree and
`jarvis_bus` came from the NIX STORE. Every suite but pylib's own has
been testing the shared library as last built, not as written. Found by
the first import of `HealthBeat` failing in a service whose test had just
been changed to use it. One `export PYTHONPATH` line. Nothing else moved:
all ten suites are green on both sides of it.

- tests: pylib **11 (was 4)**, jv-voice **29 (28)**, jv-guard **34 (33)**,
  jv-brain **115 (114)**. Unchanged and green under the new PYTHONPATH:
  jv-ears 114, jv-context 105, jv-compat 10, jv-hud-bridge 26, tools 254,
  harness 88.
- graded with `ops/ralph/mutate.sh`: **8 mutations, 8 caught.** Five on
  the clock (the deadline turned into a strictly-greater gap, a fresh
  clock that starts not-due, a `beat()` that forgets, a period of zero
  reaching the bus, and "only the periodic beat owns the clock"), and
  that last one again in each of the three services — the old behaviour
  reproduced exactly, one line each. Each service test measures the GAP
  after the fault rather than a silence, because a heartbeat that simply
  stopped would pass a silence; each also asserts the fault landed inside
  the period it was meant to interrupt, so a slow turn fails loudly
  instead of measuring nothing and passing.
- build: `nixos-rebuild build --flake .#ares` green. No schema change, no
  jv-act, no boot path, no pins.
- files: services/pylib/jarvis_bus/health.py (new),
  services/pylib/jarvis_bus/__init__.py, services/pylib/tests/test_health.py
  (new), services/jv-voice/jv_voice/service.py,
  services/jv-voice/tests/test_voice_service.py,
  services/jv-guard/jv_guard/service.py,
  services/jv-guard/tests/test_guard.py,
  services/jv-brain/jv_brain/service.py,
  services/jv-brain/tests/test_brain_service.py, ops/ralph/runtests.sh
- commit: d55348b
- next: **B58** raised — the PYTHONPATH finding is bigger than the line
  that fixed it. For as long as the loop has existed, a suite could have
  passed against a `jarvis_bus` that no longer matched the tree, which
  means the gate's own honesty is a property nothing tests. `mutate.sh`
  can grade that: a canary on `services/pylib/jarvis_bus/client.py` run
  against, say, `runtests.sh jv-guard` should kill it, and before today
  it would have LIVED — the harness would have called the file immune and
  said so. Otherwise unchanged: **Track A is one human look at `docs/hud/`
  away from unblocking ten items** (A47, A55, A62, A63, A68 and the
  A21/A22/A25 cluster are two questions asked five ways), **B27** needs
  one decision between three named options, **B43/B47/B54** are one
  question asked three times — and B47 just gained a third service that
  has now been READ for it, which is the whole of what B38 had left —
  and **B10/A28**, one live recording of one spoken turn on ares, remains
  the biggest thing a human can hand this loop.

## 2026-09-25 — iteration 80 — B58: the second meaning of a canary that lived

B48 gave this loop a control that makes every "n mutations, n caught"
sentence honest: before grading anything, make the target file impossible
to load and demand the suite go RED. A canary that LIVES has meant
exactly one thing since — the tests do not touch this file — and the
abort says so.

It has always had a second meaning. The tests touch **another copy** of
it. Iteration 79 found that in the wild: `runtests.sh` ran pytest from
the service's own directory, so every jv-* suite imported `jarvis_bus`
from the NIX STORE while importing its own package from the worktree. A
canary on `services/pylib` would have lived, and the harness would have
reported the file immune and been wrong about why.

**Nothing inside a suite run can tell the two apart.** Both are a green
suite with the file unloadable, and both are a green suite with it
erased. So the harness asks outside the run. `runtests.sh --origin
<module> <service>` resolves a module the way that suite resolves it —
same venv, same cwd, same PYTHONPATH — and prints the file or prints
nothing. The load question belongs to that script and to nothing else:
an answer from this interpreter's `find_spec` would be about a different
program.

Three answers, three sentences in the abort. **SHADOWED**, naming the
other copy, which also says every mutation graded against it would have
meant nothing. **"this very file"**, which does not excuse the canary —
it turns the original abort from an assumption into a measurement.
**Nothing**, when the question could not be asked, which is the same
discipline B53's stale-sheet hint follows: a hint that guessed would be
the one thing this harness never does. The probe is asked only on the way
out of a run already aborting, costs ~95 ms, and exists for `--runner
tests` alone — "where did this come from" has an answer for an
interpreter, and inventing one for a qmltestrunner import path or a cargo
module tree would be the overclaim the harness exists to prevent.

**And then the control was run for real, and found something.** B58's own
ask was: a canary on `services/pylib/jarvis_bus/client.py` graded against
jv-guard must kill that suite, where before d55348b it would have lived.
It killed it — the gate does reach the shared library now. Then both
mutations SURVIVED, and survived pylib's own suite too: `seq` never
advancing, and every publish claiming `conf: 1.0`. Invariant 4 ("every
producer publishes confidence") is implemented for the whole of Python by
one line in `BusClient.publish`, and nothing held it — the existing
round-trip test publishes `conf=0.93` and never looks at what arrived.
`seq` is the same shape: the envelope's only ordering handle, and a
client that published the same one forever was invisible to every
consumer that watches for a drop. Two tests against the real broker
close both, and the same three mutations are now caught 3/3.

That is the first thing this harness found by grading its own reach, and
it is worth stating plainly: the hole was not in the tests anyone wrote
for the bus client. It was that for as long as this loop has existed, the
one file every service depends on was the file the gate was least able to
grade.

- tests: tools **266 (was 254)**, pylib **13 (was 11)**. Green and
  unchanged under the changed `runtests.sh`: jv-brain 115, jv-ears 114,
  jv-voice 29, jv-context 105, jv-guard 34, jv-compat 10, jv-hud-bridge
  26, harness 88.
- graded with `ops/ralph/mutate.sh`: **12 mutations, 12 caught.** Nine on
  the harness (the package walk, the `__init__` name no importer says, a
  failed script still getting to answer, "no answer" becoming an answer,
  the two copies never compared, the note never reaching the abort, the
  module name never worked out, the python runner losing its probe, and
  the CLI building a probe for a runner that has none) and three on the
  bus client (seq that stops advancing, conf always 1.0, and a seq that
  advances in the client but goes onto the wire as 0).
- the abort path was also run for real, against a file jv-guard neither
  runs nor reads: it aborted correctly and the probe said nothing,
  because jv-guard's interpreter has never heard of `jv_brain` and
  `find_spec` RAISES on the missing parent. The probe now catches that
  and answers "no answer" instead of dying — found by running it, not by
  reading it.
- build: `nixos-rebuild build --flake .#ares` green. No schema change, no
  jv-act, no boot path, no pins.
- files: tools/mutate.py, tools/tests/test_mutate.py, ops/ralph/runtests.sh,
  ops/ralph/mutate.sh, services/pylib/tests/test_client.py
- commits: 3f347b4, 58ae92a
- next: **B59** raised, and it is the obvious next question rather than a
  new idea: `client.py` was untested on two of its five envelope fields,
  and nothing has asked what else the gate could not reach. The harness
  can now answer that per file — probe first, then grade — and `ts`,
  `src` and `v`, `next_frame`'s pong skip and its `BusError`, and
  `MAX_FRAME` are the rest of that file. Otherwise unchanged: **Track A
  is one human look at `docs/hud/` away from unblocking ten items** (A47,
  A55, A62, A63, A68 and the A21/A22/A25 cluster), **B27** needs one
  decision between three named options, **B43/B47/B54** are one question
  asked three times, and **B10/A28** — one live recording of one spoken
  turn on ares — remains the biggest thing a human can hand this loop.

## 2026-09-25 — iteration 81 — B59: the rest of the envelope, and the transport under it

Track A is still one human look at `docs/hud/` away from unblocking ten
items, and the A items that are NOT waiting on that (A11, A33, A35, A36,
A56, A59) all say in their own words "worth it the day X happens" or
"measure it on ares" — so this went to the B track and to the item the
last iteration raised.

B58 gave the gate its first honest reach into `services/pylib/jarvis_bus/
client.py` and the first two mutations it ever graded there both survived.
B59 was the obvious follow-on: ask the same question of the rest of the
file, which every Python service on the bus imports. Six mutations, one
per claim.

**Five of six survived.** Only `src` was held, and only because the
round-trip test happens to assert it. The other five:

- `ts` could be `0.0`. The broker validates the envelope's `ts` as a
  NUMBER and nothing more, so a wall-clock stamp routed perfectly too —
  and `ts` is what every latency figure in this repo subtracts from:
  `jv tap --latency`, HeardState's anchor, HealthState's expiry.
- `v` could ignore its caller and publish 1 forever. The broker only
  checks `v >= 1`. A bumped `v` is how a schema migration BEGINS, and a
  client that pinned it would make one impossible while breaking nothing
  today.
- a pong could be returned as EOF. The Python client has no `ping()`, so
  the skip branch was dead code as far as this suite knew — and a client
  that reports None there is telling every consumer the bus is GONE.
- the length-prefix guard could be a thousand times too generous.
- `JARVIS_BUS` could be ignored entirely, because every test in the file
  passes an address explicitly.

Five tests close them. Three ride the real broker; two deliberately do
not and say why. The pong test carries its own control — it pings a
separate connection first and asserts a pong is a real thing this broker
really sends — because otherwise it would pass without one ever arriving.
The prefix test feeds four bytes and then EOF, because the claim is that
the guard fires on the PREFIX ALONE: `readexactly(n)` allocates first and
asks later, and that prefix is the one number on the wire that is read
before anything is known about what follows.

The frame cap is now pinned to jarvisd's own `pub const MAX_FRAME` by
READING `services/jarvisd/src/proto.rs` — invariant 1 forbids importing
it. That makes it a B55-style relation, so it was graded as one: move the
Rust constant, the pylib suite goes red, and the harness reports "the
suite reads services/jarvisd/src/proto.rs — it never runs it". If the two
caps ever drift, the smaller silently becomes the real limit and the
larger one's error message is a lie about why the connection died.

Worth stating plainly, because it is the second iteration in a row to
find it: the file the gate could not see for this loop's entire history
is the file that turned out to be least tested. Two iterations of
grading it have now found seven unheld claims in one 130-line module.

- tests: pylib **19 (was 13)**. Green. Nothing else touched — the change
  is one test file.
- graded with `ops/ralph/mutate.sh`: **10 mutations, 10 caught.** Nine on
  `client.py` (ts zeroed, ts on the wall clock, src constant, v pinned,
  pong as EOF, the cap constant drifted, the guard comparison widened,
  the env var ignored, and a set-but-empty env var becoming an address)
  and one on `proto.rs` (the broker's cap moving while the client's does
  not). The first grading of the same six, before the tests, was **1/6**.
- build: `nixos-rebuild build --flake .#ares` green. No schema change, no
  jv-act, no boot path, no pins.
- files: services/pylib/tests/test_client.py
- commits: 9ad4eb7
- next: **B60** raised — `client.py` was one of pylib's THREE modules, and
  `health.py` and `schema.py` have never been graded at all. `to_body` /
  `from_body` encode and decode every body on the bus, so a survivor
  there is wrong in every service and every topic at once; `HealthBeat`
  is the clock d55348b just fixed a real bug in, found by reading rather
  than by grading. B60 also names two things left deliberately alone in
  `client.py`: `next_event`'s two indistinguishable EOF paths, and
  `connect()`'s address rule, under which a RELATIVE unix socket path
  containing a colon is dialled as TCP — harmless today because every
  real path is absolute, and a latent trap for the replay rig, which is
  the one thing that invents socket paths. Otherwise unchanged: **Track A
  is one human look at `docs/hud/` away from unblocking ten items** (A47,
  A55, A62, A63, A68 and the A21/A22/A25 cluster), **B27** needs one
  decision between three named options, **B43/B47/B54** are one question
  asked three times, and **B10/A28** — one live recording of one spoken
  turn on ares — remains the biggest thing a human can hand this loop.

## 2026-09-25 — iteration 82 — B60: the codec every body on the bus goes through

Track A is unchanged — still one human look at `docs/hud/` away from ten
items — so this took the item the last iteration raised. B59 graded
`client.py`, one of pylib's three modules. B60 named the other two:
`health.py`, whose `HealthBeat` is the clock every service's `sys.health`
beat is owed against, and `schema.py`, whose `to_body`/`from_body` are how
EVERY body on this bus is encoded and decoded.

**health.py: 4 mutations, 4 caught.** Its suite (written with d55348b) has
teeth. The deadline becoming a gap, a clock nobody has beaten not being
due, an off-schedule beat leaving the old schedule running, and a period of
zero being accepted are all held. Nothing to do there, which is worth
recording as plainly as a hole would be.

**schema.py: 9 mutations, 0 caught.** The codec is eleven lines each way
and had one test on it — `test_to_body_wire_rules`, on an `AudioWake`,
which is the one body in the frozen set with an empty `_optional`, no
nested field and no array. It exercises none of the rules the function
exists for. So: the nested-object branch, both array branches, the
Optional unwrap, the null-nested guard, the absent-key default and BOTH
halves of the omit rule could all be broken and the suite stayed green.

One of the nine was caught elsewhere, and it is worth being precise about:
`from_body`'s absent-key branch is held by **jv-context's** suite, which
decodes a `context.system` body with `battery_pct` missing and fails seven
tests when the branch goes. That is the only reason any of this was held
anywhere — a consumer's suite happening to use a shape. The other eight
were held by nothing in the repository.

A survivor here is not local. A survivor in jv-voice is wrong in jv-voice;
a survivor in this file is wrong in eight services and on every topic at
once, and it surfaces far from its cause: a nested dataclass left
unconverted is a `msgpack` TypeError thrown by the transport inside
`publish`, on a frame the calling code built correctly.

The sharpest claim is the omit rule, and it is really two rules facing each
other. **"Absent" and "present and null" are different words on this bus.**
Optional keys are declared with a bare type (`"type": "string"`), so an
explicit null in one fails validation — it must be omitted. But
`in_reply_to_utterance` is required AND nullable
(`"type": ["string", "null"]`), because a system announcement has no
triggering utterance and has to SAY so. A codec that omitted every None
would publish a `speech.say` rejected for a missing required key, and only
ever for unprompted speech: the proactivity path, the one that runs when
nobody is watching.

Three tests read `schemas/*.json` instead of restating it, which is the B55
shape — the frozen schema is the law (invariant 2) and the codec's whole
job is to agree with it, so the assertion is a RELATION: every emitted key
is a declared property, every required key survives the encode, and a null
is only ever on a key the schema permits null. Stated that way it holds all
five shapes at once, and it holds the next shape too, which a hand-written
expected dict would not.

A fourth reads `tools/gen_bindings.py`. `schema.py` says DO NOT EDIT and
means it: the codec is the generator's epilogue copied in verbatim, so a
fix applied to the generated file is erased by the next regeneration and a
fix applied only to the generator is not what any service imports. The
harness graded that one as a read relation and reported it in those words —
"the suite reads tools/gen_bindings.py — it never runs it". (Checked while
there: the generator's docstring claims CI runs `--check`, and
`.github/workflows/check.yml` really does. No drift item to raise.)

Two claims the grading turned up as behaviour worth PINNING rather than
holes to close. An unknown wire key is IGNORED — `from_body` iterates the
dataclass's fields, not the body's keys — which is the forward-compatibility
half of the envelope's `v`: a v2 producer that adds a key cannot crash a v1
consumer. And a body missing a REQUIRED key fails loudly at the decode
rather than being filled with None, because a required key is required
precisely because consumers may not check it.

- tests: pylib **63 (was 19)**. Green. One new file; no source touched.
- graded with `ops/ralph/mutate.sh`: **12 mutations, 12 caught** — 11 on the
  codec and 1 on the generator's epilogue. Before the tests: **0 of 9**.
  health.py separately: 4 of 4, before and after.
- build: `nixos-rebuild build --flake .#ares` green. No schema change, no
  jv-act, no boot path, no pins.
- files: services/pylib/tests/test_schema.py
- commits: 184b6b1
- next: **B61** raised, and it is the last of pylib: the two `client.py`
  claims B60 named and deliberately left. `next_event` returns None for a
  short read on the head and for a short read on the BODY, and neither is
  distinguishable from a frame that never came — a truncated frame and a
  closed bus produce the same answer to every consumer's reconnect logic.
  And `connect()`'s address rule (`":" in addr and not addr.startswith("/")`)
  dials a RELATIVE unix socket path containing a colon as TCP; every real
  path is absolute so it cannot bite today, and the replay rig is the one
  thing in this repo that invents socket paths. B61 says what the cheap
  honest half is: pin TODAY's rule with a test so a change to it is
  deliberate and visible, and leave the rule itself as a decision. With
  that, all three pylib modules will have been graded. Otherwise unchanged:
  **Track A is one human look at `docs/hud/` away from unblocking ten
  items** (A47, A55, A62, A63, A68 and the A21/A22/A25 cluster), **B27**
  needs one decision between three named options, **B43/B47/B54** are one
  question asked three times, and **B10/A28** — one live recording of one
  spoken turn on ares — remains the biggest thing a human can hand this
  loop.

## 2026-09-25 — iteration 83 — B61: the two rules in `client.py` every reader assumes wrong

Track A is still blocked on one human look at `docs/hud/`, and the A items
that are not blocked all say "not before X" in their own text (A18 waits on
a topic that does not exist, A33 on the mask being edited, A39 on A22 being
answered, A31/A35/A36/A56/A59 on a human). So this is B61, which the last
three iterations each raised and deferred, and which finishes the grading of
pylib: `client.py` was the last of the three modules.

Two claims, neither of them fixed.

`next_event` returns None for a short read on the HEAD and for a short read
on the BODY. Every consumer in this repo reads that None as "the bus is
gone" and leaves its loop — jv-ears' `follow_bus` returns, jv-brain's run
loop breaks, jv-guard's and jv-compat's the same — so the one condition that
means "the broker is mid-write and is still there" is spelled exactly like
the one that must trigger a reconnect. The body half is the worse half: the
prefix said 64 bytes and 8 arrived, which is the strongest evidence
available from outside that the other end is ALIVE, and it is reported as
the other end being gone.

`connect()`'s rule `":" in addr and not addr.startswith("/")` asks whether
the address is ABSOLUTE, not whether it is a path. Writing the table out
made the relative case sharper than B59 had described it: `run/jarvis:bus.sock`
does not dial some wrong host and time out — `rsplit(":", 1)` hands
`int()` the string `"bus.sock"` and the caller gets a ValueError while
holding what it believes is a filename. Still cannot bite today (no address
in this repo is relative; the replay rig is the one thing here that invents
socket paths), and that is exactly the kind of thing that changes without
anyone noticing it changed.

So: five tests that PIN today's behaviour, each saying PIN NOT ENDORSEMENT
in its own docstring. A clean EOF is the control; a short head, a short
body, and the same truncation arriving at consumers through `next_frame`
(pinned separately, because a fix could land in either method) are the
claim. The transport test is a six-row table with BOTH openers replaced, so
nothing dials and the test is about the decision rather than about anything
listening.

The grading is the part that says these are worth having. Two of the five
mutations are not inventions — they are the two edits a reader who noticed
the rule would actually make: drop the absoluteness test, or replace it with
`"/" not in addr`. Both are caught now and both passed before.

- tests: pylib **68 (was 63)**. Green. One test file; no source touched.
- graded with `ops/ralph/mutate.sh`: **5 mutations, 5 caught**. Before the
  tests: **1 of 5** — and the one that was caught was caught by accident,
  because swapping `host, port` breaks every test in the file that dials.
- build: `nixos-rebuild build --flake .#ares` green. No schema change, no
  jv-act, no boot path, no pins.
- files: services/pylib/tests/test_client.py
- commits: de510db
- next: **B62** raised, and unlike its three predecessors it is not the
  loop's to take: it is the DECISION B61 refused to make, in two halves —
  should a truncated frame be distinguishable from a closed bus (leave it /
  raise / sentinel, and the middle one is an edit in eight files), and
  should `connect()` route by absoluteness (today), by shape, or by an
  explicit `unix:`/`tcp:` prefix the caller writes. Both are cheap to change
  and neither is cheap to change by accident, which is what the new tests
  are for: whoever answers moves them in the same commit. With pylib graded
  end to end, the loop's remaining B work is B12/B20/B25/B28/B33/B36 and the
  two-minute human reads (B17 with B20). Otherwise unchanged: **Track A is
  one human look at `docs/hud/` away from unblocking ten items** (A47, A55,
  A62, A63, A68 and the A21/A22/A25 cluster), **B27** needs one decision
  between three named options, **B43/B47/B54** are one question asked three
  times, and **B10/A28** — one live recording of one spoken turn on ares —
  remains the biggest thing a human can hand this loop.

## 2026-09-25 — iteration 84 — A63: the crowded corner did not fit

Track A had been blocked for three iterations and the loop had been in the
B track grading pylib. Re-reading Track A for something that was the
loop's own rather than a human's, A63 turned out to be two questions
wearing one number: a PICTURE of a crowded corner (which wants A62
answered, because a photograph of eight unrelated plates stacked 8 px
apart is the confusion A62 is asking about) and an ASSERTION that the
corner the box is sized for fits in the box. The second one needs nobody.

`shell.qml`'s surface box had grown four times — 624 → 688 in two steps —
and every digit of it came out of an argument written in its own comment:
"ConfirmPlate wraps to three lines", "a refused binary and a failed
install can genuinely be up together". Four arguments, checked by nothing.
The only fit check that existed ran inside the contact sheet's loop, and
no shot in that sheet lights more than three plates, so it cleared 688 px
by more than five hundred and would have passed on a HUD that crops the
moment a fourth arrives.

`tools/hudshots/scene/tst_fit.qml` builds the case those paragraphs are
about. Every plate but `link` — which excludes all nine, since each of
them gates on the same link `LinkPlate` reports on, and a check holds that
split rather than assuming it — each drawing the widest thing its own cap
allows, over a health list as long as this machine has services. One
moment the machine can actually reach: Jarvis mid-answer into a muted
sink, the user talking over it (the `speaking` frame is stamped BEFORE the
transcript, which is the barge-in `HeardState` is written around), jv-act
holding a confirmation and reporting a separate failure, a refused binary,
a failed install, a live mic, and everybody complaining.

**That corner is 713 px tall. The box was 688.** It did not fit. A
layer-shell panel floating over every window was cutting its bottom plate
in half — and the bottom plate is `HealthPlate`, the thing that says what
is wrong, cropped exactly when everything is. Nothing errors and nothing
logs; the only way anyone would ever have found out is by having it
happen.

The box is 745 px now, and the number is no longer an argument: it is
2 × `insetPx` + the measurement. The second inset is new — §06 gives this
corner a gap at the top and the right and the bottom edge had none, so a
stack that exactly filled the box ended flush against the edge of a
floating panel, which reads as a crop whether or not it is one. Both shot
drivers use the same rule now, so the sheet's own (weak) fit check and
this one say the same thing.

Three controls, because a fit check is the easiest kind of test to make
vacuous — every way of staging one wrong produces a stack that measures
comfortably:

  · the crowd really IS nine plates, by `litNames`, which is the plates
    naming themselves rather than the harness assuming;
  · every plate that declares a text cap is really AT it;
  · no plate is wider than the surface (the half shot 13 raised).

The middle one earned its place immediately: `InstallState.plainSlug`
REFUSES a slug past `maxSlugChars` instead of truncating it, so the
over-long probe that made every other plate draw its widest made that one
draw an empty app name — the narrowest it can be, on a check about
crowding. Nothing failed. The corner measured 710 px, 3 px short of the
truth, and the fix moved the box with it.

Per-plate, settled, for whoever answers A70: confirm 260x112, heard
260x93, action 260x76, guard 260x57, install 260x57, health 180x149,
output 131x35, state 99x35, mic 58x35 — nine plates, eight 8 px gaps,
713 px, 260 px at the widest against a 300 px surface.

Four Python gates, because everything here is a copy of something:
each scene driver's surface box is pinned to `shell.qml`'s (three drivers
held an unchecked copy of it), both drivers' `everyPlate` to what
`Corner.qml` actually stacks, and the fit crowd's roster to `services/`.
A tenth service on this machine now fails a test instead of quietly making
the measured worst case one row short of the real one. One pre-existing
literal went with them: `test_hudsheet.py` hard-coded 206400 pixels, which
is 300x688, and it now reads the denominator off a committed shot.

The sheet is thirteen PNGs of the same HUD with 57 rows of backdrop under
it — checked pixel-identical above row 688 before committing, so the diff
is the box and not the plates.

Not done, on purpose, and it is the interesting half: nothing here says a
713 px corner SHOULD exist. That is half a 1440p screen, mostly
near-full-width plates about unrelated things, and `HealthPlate` calls
itself "the SHORT list" in its own header while having no cap at all.
Raised as **A70** with three named shapes and no pick — it is A62's
question with a number attached now, which is the most useful thing this
iteration could hand a human.

- tests: `bash ops/ralph/hudshots.sh` **23 (was 16)**, `... qmltest.sh`
  585, `... runtests.sh tools` **269 (was 265)**. All green.
- graded with eight mutations, **eight caught**, each by exactly one check
  and none by collateral: the box back to 688 (2 gates), a driver keeping
  the old box, `everyPlate` forgetting a plate, the roster dropping a
  service, the layout settle removed, `InstallState` refusing its probe,
  `ConfirmPlate` growing a fourth line (18 px over), `GuardPlate` widening
  past the surface (320 px). Before the tests: the two that move pixels
  would have registered as "the sheet moved" and said nothing about the
  surface being too small; the other six, nothing at all.
- build: `nixos-rebuild build --flake .#ares` green. No schema change, no
  jv-act, no boot path, no pins.
- files: tools/hudshots/scene/tst_fit.qml (new), tst_shots.qml,
  tst_sequence.qml, shell/jv-hud/shell.qml, tools/hudscreens/sheet.py,
  shoot.py, ops/ralph/hudscreens.sh, tools/tests/test_hudshots.py,
  test_hudsheet.py, docs/hud/README.md, docs/hud/*.png
- commits: 06d8284
- next: **A70** is the one to hand a human, and it is cheap to answer
  because the numbers are above — but it is also the first Track A item in
  a while that a human can settle in two minutes WITHOUT sitting at ares,
  which the rest of the blocked A track cannot say. Otherwise unchanged:
  **Track A is one human look at `docs/hud/` away from unblocking** A47,
  A55, A62, A63's picture half and the A21/A22/A25 cluster; **A56** asks
  whether this suite (and the sequence one) should be in the build gate at
  all, and A63 makes that question sharper, because the strongest assertion
  about what the HUD shows is now the one furthest from `nix build`;
  **B27** needs one decision between three named options; **B43/B47/B54**
  are one question asked three times; **B62** is B61's two decisions; and
  **B10/A28** — one live recording of one spoken turn on ares — remains the
  biggest thing a human can hand this loop.
