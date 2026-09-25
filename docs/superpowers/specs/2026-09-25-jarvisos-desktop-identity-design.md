# JarvisOS Desktop Identity — design spec

**Date:** 2026-09-25
**Status:** approved (scope + execution), building the core
**Author:** setup session (Claude) with Ofek

## Purpose
Make the whole desktop *look and feel* like JarvisOS — a cohesive dark,
cinematic, instrument-like identity — rather than default niri/NixOS. The
top-right corner stays the one live element (the Jarvis HUD, already built);
everything else is the redesigned, mostly-static shell around it. niri stays
the compositor; we style the environment on top of it.

## Design language (anchor — blueprint §06, do not drift)
- Ground `#090D12` / panels `#0C1116`; one **ember** accent `#F0714A`; teal
  `#4FB8BF` secondary; text `#E6ECF0` / `#9BAAB4` / `#64747F`.
- UI font **Archivo**; mono **JetBrains Mono** (both already in the tree).
- Earned emptiness; motion only when it encodes a signal; no parallax; honor
  `prefers-reduced-motion`. Everything reads as one instrument.

## Architecture
One shared palette (`personality/theme.toml` → the HUD's `Theme` singleton, and
a new `modules/theme.nix` exposing the same tokens to system theming). Each
surface is an independent module so the loop can extend one without touching the
others. All Quickshell surfaces run as `graphical-session.target` user services,
like `jv-hud`.

| Surface | Mechanism | Phase |
|---|---|---|
| Wallpaper | generated SVG→PNG package + `swaybg` graphical-session service | **core (now)** |
| App theming | `modules/theme.nix`: GTK (dark+ember), Qt (dark), icon + cursor theme, fonts | **core (now)** |
| Terminal | alacritty JarvisOS palette via `environment.etc` | **core (now)** |
| Launcher | fuzzel restyled via `environment.etc`; custom Quickshell launcher later | **core (now)** → loop |
| niri window styling | ember focus ring, gaps, quiet borders, dim inactive | **core (now)**, then migrate config into the flake (loop) |
| Boot continuity | verify GRUB + Plymouth already share these tokens | **core (now, verify)** |
| Top bar | Quickshell bar (workspaces / clock / net·audio·battery), leaves top-right for HUD | loop |
| Notifications | Quickshell notification daemon, quiet + ember | loop |
| Lock screen | swaylock-effects (JarvisOS) → Quickshell later | loop |
| Login greeter | recolor tuigreet now (safe); graphical greeter later, carefully tested | loop |

## Safety / constraints
- Everything additive and reversible; rollback = previous generation.
- The **login greeter is the one danger** (a broken greetd locks the user out):
  only recolor tuigreet now; the graphical greeter is a later, carefully-tested
  step, never switched untested.
- niri validates + hot-reloads config and refuses to apply an invalid one, so a
  styling edit cannot break the running session.
- No jv-act / schema / boot / disko / NVIDIA-pin changes.

## Testing
qmllint on QML; `nixos-rebuild build`; launch each surface in the live session to
confirm it renders before `switch`; build → test → switch discipline.

## Execution
Core built by hand this session and switched in so it is visible immediately.
The remaining surfaces (bar, notifications, lock, greeter, custom launcher, and
migrating the niri config into the flake) are seeded into `ops/ralph/PLAN.md` as
a prioritized track for the autonomous loop, which reviews-merges as usual.
