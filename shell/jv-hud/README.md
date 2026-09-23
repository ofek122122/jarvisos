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

## Next

`A3` — the first data-backed element: Jarvis's state from real `speech.state` / `audio.wake`
frames off the bus, via a consumer-only bridge (invariant 1).
