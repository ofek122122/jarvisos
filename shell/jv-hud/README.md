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

## Next

`A2` theme singleton (tokens out of `personality/`), then `A3` the first
data-backed element: Jarvis's state from real `speech.state` / `audio.wake`
frames off the bus, via a consumer-only bridge (invariant 1).
