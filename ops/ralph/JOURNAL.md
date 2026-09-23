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
