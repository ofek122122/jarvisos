# jv-hud — the heads-up display

Quickshell (QML) layer-shell surfaces over Niri. Blueprint §06: *every
moving pixel encodes a real signal*, and the HUD **never** steals focus or
fakes sensor state (invariant 10).

## What exists today (A1 skeleton)

`shell.qml` maps one layer-shell surface per connected monitor and renders
nothing. That is deliberate — the default state of the screen is your work
and nothing else, and an unmapped surface renders at 0 fps. The skeleton's
job is to pin the properties that make the HUD safe by construction:

| property | why |
|---|---|
| `WlrKeyboardFocus.None` + `focusable: false` | the surface cannot take the keyboard |
| `ExclusionMode.Ignore` | zero exclusive zone — no window is resized around it |
| `mask: Region {}` | empty input region — clicks pass through to what's below |
| `WlrLayer.Top` | over ordinary windows, yields to fullscreen and the lock screen |

## Running it

The HUD is packaged as `jv-hud` and installed system-wide, but it is not
started automatically yet — there is nothing truthful to display until the
bus-backed elements land (PLAN A3–A6). Start it by hand in a Niri session:

```sh
jv-hud                      # maps nothing (expected)
JV_HUD_SELFTEST=1 jv-hud    # maps a small marker: the shell loaded
```

`JV_HUD_SELFTEST` reports that the *shell* is alive. It never stands in for
a sensor: no camera or microphone indicator is drawn by this file at all.

## Theme tokens (A2)

Every colour, size, duration and inset the HUD uses comes from
`personality/theme.toml` — theme tokens are identity, and identity is
versioned next to the voice and the system prompt (invariant 9). The toml is
compiled into `Theme.qml`, a `pragma Singleton` that QML files read through
the directory import:

```qml
import "."
...
color: Theme.ground
border.color: Theme.ember
```

```sh
python tools/gen_theme_qml.py          # regenerate Theme.qml + qmldir
python tools/gen_theme_qml.py --check  # exit 1 if they drifted
bash ops/ralph/runtests.sh tools       # generator + drift + blueprint tests
```

`Theme.qml` and `qmldir` are generated and checked in — **never hand-edit
them.** Three gates keep the story honest: `nix build .#jv-hud` runs
`--check` before qmllint (a drifted Theme.qml cannot reach a build), qmllint
type-checks every token access (`Theme.emberr` is a build failure, not a
transparent rectangle at runtime), and a test asserts no QML file outside
`Theme.qml` contains a literal hex colour. A fourth test asserts the palette
still equals the blueprint's §06 dark tokens, so the theme cannot quietly
wander away from the design it came from.

The `qmldir` has no `module` line on purpose. Quickshell synthesizes a qmldir
per directory and steps aside when it finds one; ours registers the singleton
in the way a plain directory import (and qmllint) understands. Any future
singleton has to be added to it.

## The bus link (A5)

QML cannot open a Unix socket or unpack MessagePack, and the HUD is
forbidden from importing another service (invariant 1). So `Bus.qml` runs
one child process — `services/jv-hud-bridge`, pinned into the wrapper as
`JV_HUD_BRIDGE` — which subscribes to a few topics and writes each frame
as one line of JSON. Frames come in; nothing goes out. The bridge's pump
is handed a `ReadOnlyBus` that has no publish method to reach for, and a
test greps the source for `.publish` on top of that.

```
{"t":"frame","frame":{topic,ts,seq,src,conf,v,body}}
{"t":"link","up":true}                 subscribed to a live bus
{"t":"link","up":false,"err":"..."}    not subscribed, and why
```

`link` is deliberately not a bus topic — it describes this pipe, not the
machine, and a topic needs a reviewed schema commit (invariant 2). The HUD
needs it because **`Bus.frames` is emptied whenever the link drops**: a HUD
still drawing "listening" from a bus that died three minutes ago is lying,
and a stale indicator is worse than none (invariant 10).

What an element uses:

| member | meaning |
|---|---|
| `Bus.linkUp` | gate every piece of content on this |
| `Bus.latest(topic)` | last envelope, or `null` if unheard |
| `Bus.ageOf(env)` | seconds since capture, or `Infinity` if not yet knowable |
| `Bus.frameReceived(topic, env)` | per-frame signal |

`Bus.qml` itself is only the half that needs Quickshell: the child process,
the respawn timer, and the monotonic clock. The state machine those JSON
lines drive lives in `core/BusModel.qml` and imports nothing but QtQuick —
which is what makes it testable (see below). `Bus` forwards the whole API,
so an element still sees one `Bus`.

The singleton is built lazily, on first use. Nothing references it while
the HUD has nothing to show, so an idle machine runs no bridge process and
holds no socket — which is why the self-test plate lives inside a `Loader`
rather than merely being `visible: false`. Under `JV_HUD_SELFTEST=1` that
plate also prints `bus up` / `bus down`: the state of this pipe, in plain
words, never dressed up as a sensor indicator.

```sh
bash ops/ralph/runtests.sh jv-hud-bridge   # unit tests + a real-jarvisd e2e
```

Note on the build gate: qmllint type-checks *cross-file* access, so
`Bus.linkUpp` in any element is a build failure. It does **not** catch a
typo in a self-assignment inside a file — which is what the QML tests are
for.

## Headless QML tests (A9)

```sh
bash ops/ralph/qmltest.sh                          # inner loop, worktree source
bash ops/ralph/qmltest.sh BusModel::test_received_survives_a_link_drop
nix build .#jv-hud                                # the gate: qmllint + these tests
```

`shell/jv-hud/tests/` runs under `qmltestrunner -platform offscreen`: no
compositor, no bus, no bridge process. That works only because of how this
directory is split:

| directory | imports | who can load it |
|---|---|---|
| `shell/jv-hud/` | Quickshell | the `quickshell` binary, only |
| `shell/jv-hud/core/` | QtQuick | any QML engine — so, the tests |

Quickshell links its QML plugin **into its own binary**, so no other QML
engine can `import Quickshell` at all. And importing a directory resolves
every type its `qmldir` lists — so a single Quickshell import inside `core/`
would make the whole directory unloadable and silently take the HUD's only
tests with it. A test in `tools/` fails if that ever happens.

The rule that follows: **logic that deserves a test goes in `core/`.**
Anything left in a Quickshell file is beyond the reach of any test, so keep
those files to wiring. Components in `core/` are registered in `CORE` in
`tools/gen_theme_qml.py` (which writes `core/qmldir`), exactly like
singletons are registered in `SINGLETONS`.

The tests are a build gate, not shipped QML — `installPhase` drops them.

## Next

`A3` — the first data-backed element: Jarvis's state from real
`speech.state` / `audio.wake` frames, now that `Bus` can deliver them, and
now that its state machine is born tested.
