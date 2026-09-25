#!/usr/bin/env bash
# ops/ralph/hudscreens.sh — photograph the REAL HUD, on a real compositor,
# on ares' three monitors (PLAN A30).
#
# The sibling of hudshots.sh, and deliberately the opposite trade. That one
# renders the plates with a plain QML engine into a 300x807 rectangle: the
# HUD's CONTENT, and it has to disclaim everything else — layer-shell, the
# empty input mask, the zero exclusive zone, the three screens. This one
# gives all of that up in exchange for the whole truth: a headless wlroots
# compositor with ares' monitor sizes, a real jarvisd, and the REAL
# `.#jv-hud` — quickshell, its layer-shell surface, its own read-only
# bridge — photographed with `grim`.
#
# Nothing is staged and nothing is stubbed. The binary this runs is the one
# a `nixos-rebuild switch` would install, which is why the pictures are
# worth measuring: tools/hudscreens/shoot.py checks that no space was
# reserved, that the keyboard never moved, that the HUD drew in the corner
# it claims on EVERY monitor, that a quiet HUD leaves the desktop
# pixel-identical, that a click over a painted plate reaches an ordinary
# window underneath it (A32), and that the HUD commits no Wayland frames
# at all while nothing changes — quiet, with a plate on screen, and four
# times with a plate on screen while a frame arrives every second, for
# four different sets of plates, the last two of which are the ones whose
# words come off a latch the arriving frame re-takes. The last of those
# four is also the only stretch in which anything has ever LEFT the
# screen: it is the same turn as the one before it, carried past the
# answer to the outcome, on the same broker and the same shell
# (A34/A42/A43/A48/A49).
# Those were all "verified by construction" for thirty iterations, which
# is a polite way of saying nobody had tried them.
#
# WHAT THIS STILL IS NOT. Not ares: the compositor is sway rather than
# Niri, the outputs are headless (no scanout, no real panel, no NVIDIA),
# and nothing here can tell you whether an 11 px label is comfortable to
# read from where you actually sit. Nor does the frame count price a
# frame: this renders with pixman, in software, so "0 fps when idle" is
# measured here and "< 2 ms of GPU per frame" is not. It answers "is the
# HUD on all three screens, in the right corner, asking to be drawn when
# it has nothing to say" — which is exactly what A13/A27 are blocked on,
# and not the same question as "does it look right".
#
# Run it after any change to shell/jv-hud or personality/theme.toml and
# commit docs/hud/screens/.
set -euo pipefail

root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
out="${1:-$root/docs/hud/screens}"

# Realize out of the flake's own pinned nixpkgs, rather than whatever this
# machine happens to have: a sheet rendered against a different Qt or a
# different sway would be a picture of a different machine.
nixpkgs() {
  nix build --no-link --print-out-paths --impure --expr \
    "(builtins.getFlake (toString $root)).inputs.nixpkgs.legacyPackages.\${builtins.currentSystem}.$1"
}

echo "hudscreens: realizing the compositor and the shell…" >&2
sway=$(nixpkgs sway)
swaybg=$(nixpkgs swaybg)
grim=$(nixpkgs grim)
# The second client the click probe needs (A32). An empty input region is
# a claim about a window UNDERNEATH the HUD, so it cannot be measured
# without one; wev is the smallest real Wayland toplevel available, and
# sway tiles it to fill the monitor the HUD docks to.
wev=$(nixpkgs wev)
# msgpack to speak the bus, numpy to measure 33 megapixels of screenshot.
# Neither enters any closure: this is a development harness, not a unit.
py=$(nixpkgs 'python3.withPackages (p: [ p.msgpack p.numpy ])')
hud=$(nix build "$root#jv-hud" --no-link --print-out-paths)
jarvisd=$(nix build "$root#jarvisd" --no-link --print-out-paths)

stage=$(mktemp -d)
cleanup() {
  [ -n "${swaypid:-}" ] && kill "$swaypid" 2>/dev/null || true
  rm -rf "$stage"
}
trap cleanup EXIT

# A private runtime dir, so this never shares a wayland socket with
# whatever the user is running — and so a crashed run leaves nothing
# behind in /run/user.
export XDG_RUNTIME_DIR="$stage/run"
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
export HOME="$stage"
export XDG_CACHE_HOME="$stage/cache"
export XDG_CONFIG_HOME="$stage/config"

# ares' monitors and the compositor's input rules come from
# tools/hudscreens/sheet.py — one source, read by the compositor here and
# by the checks in tools/tests/test_hudscreens.py.
"$py/bin/python" - "$root/tools/hudscreens" "$stage/sway.conf" <<'EOF'
import sys
sys.path.insert(0, sys.argv[1])
import sheet

open(sys.argv[2], "w").write(sheet.sway_config())
EOF

# Headless wlroots with software rendering: no DRM, no GPU, no seat. The
# HUD is a Wayland client and cannot tell the difference; what it CAN tell
# the difference about — layer-shell, exclusive zones, per-output surfaces
# — is all compositor protocol and all real here.
export WLR_BACKENDS=headless
export WLR_RENDERER=pixman
export WLR_HEADLESS_OUTPUTS=3
unset WAYLAND_DISPLAY || true

"$sway/bin/sway" -c "$stage/sway.conf" > "$stage/sway.log" 2>&1 &
swaypid=$!

for _ in $(seq 1 100); do
  sock=$(ls "$XDG_RUNTIME_DIR"/wayland-? 2>/dev/null | head -1 || true)
  [ -n "$sock" ] && break
  sleep 0.2
done
[ -n "${sock:-}" ] || { echo "hudscreens: sway never created a wayland socket" >&2; sed -n 1,40p "$stage/sway.log" >&2; exit 1; }
export WAYLAND_DISPLAY="$(basename "$sock")"
export SWAYSOCK="$(ls "$XDG_RUNTIME_DIR"/sway-ipc.*.sock | head -1)"

# The desktop behind the HUD. Without it every plate would be drawn over
# black and `plate_opacity = 0.86` — the glass the whole panel is made of
# — would be invisible. A flat grey that is deliberately not a Jarvis
# colour, so nobody can mistake the paper for the subject.
backdrop=$("$py/bin/python" -c "
import sys; sys.path.insert(0, '$root/tools/hudscreens'); import sheet; print(sheet.BACKDROP)")
"$swaybg/bin/swaybg" -c "$backdrop" -m solid_color > "$stage/swaybg.log" 2>&1 &
sleep 1

# Qt has to be told, or it picks xcb, fails to find a display, and the
# layer-shell attached properties quietly fail to attach — which looks
# like a HUD that loaded and drew nothing.
export QT_QPA_PLATFORM=wayland

export JV_SCREENS_OUT="$out"
export JV_SCREENS_STAGE="$stage"
export JARVISD_BIN="$jarvisd/bin/jarvisd"
export JV_HUD_BIN="$hud/bin/jv-hud"
export GRIM_BIN="$grim/bin/grim"
export WEV_BIN="$wev/bin/wev"
export SWAYMSG_BIN="$sway/bin/swaymsg"

"$py/bin/python" "$root/tools/hudscreens/shoot.py"
