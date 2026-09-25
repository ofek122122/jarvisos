#!/usr/bin/env bash
# ops/ralph/hudscreens.sh — photograph the REAL HUD, on a real compositor,
# on ares' three monitors (PLAN A30).
#
# The sibling of hudshots.sh, and deliberately the opposite trade. That one
# renders the plates with a plain QML engine into a 300x826 rectangle: the
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
# It then READS THE SHEET BACK (B74), the way hudshots.sh has since B52 —
# every screen it just took, against the one committed at HEAD, through
# tools/hudsheet.py. It cannot do that to the byte: two runs of an untouched
# HUD differ on antialiased glyph edges. So the comparison carries a MEASURED
# floor (`sheet.NOISE_PIXELS` / `sheet.NOISE_CHANNEL`, and the measurement is
# written down beside them), a difference under it is reported as the
# compositor's rounding rather than as news, and — when this is writing over
# the committed sheet — those files are put back to the bytes they were
# compared against, so a run of an unchanged HUD leaves a clean tree.
#
# Run it after any change to shell/jv-hud or personality/theme.toml and
# commit docs/hud/screens/. A run that really did change the HUD ends
# nonzero, naming the screens that moved: that is the refresh telling you
# what you changed, not a failure — look at the new PNGs and commit them.
#
# reads: docs/hud/screens flake.lock flake.nix personality/theme.toml
#        pkgs/jv-hud services/jarvisd shell/jv-hud tools/hudscreens
#        tools/hudsheet.py
#
# Declared and NOT bound (PLAN B72). `ops/ralph/verify.sh` runs every gate it
# plans; this one is named there instead, beside the paths that asked for it,
# so a green verdict cannot quietly stand in for a sheet nobody took. Two
# measured reasons, neither of them "it cannot run here" — it runs here fine:
#   1. 3m00s, and what it produces is not a verdict to collect but a
#      directory of pictures somebody has to look at.
#   2. it REWRITES the screens it is pointed at — which B72 could not
#      qualify and B74 now can. The rewrite is no longer unconditional:
#      a screen that only moved by rounding is restored to its committed
#      bytes, so a run of an unchanged HUD is idempotent and a dirty
#      `git status` here now means something. What remains true is that a
#      run which DID change the HUD leaves a new PNG per shot in the tree,
#      which is the right outcome for a human at a keyboard and the wrong
#      one for a gate computing a plan from that tree.
# Reason 1 is the one that still carries this on its own, and B75 asked the
# obvious follow-up: is there a CHEAPER HALF? The probes (the corner, the
# exclusive zone, the click, the idle frames) are verdicts a gate could
# collect; the screens are not. So the run books its own seconds — every
# phase, into one file both halves of this harness append to, classified in
# `sheet.PHASES` as a cost a picture-less run would still pay or one only the
# pictures need — and prints the table at the end. The answer is NO, and the
# numbers are why (measured here, and the table re-measures them):
#
#     probe  144.8 s  80.5%   ·   sheet  34.9 s  19.4%   of 179.8 s
#
# A run that kept no picture at all would still pay 2m25s of the 3m00s,
# because the pictures are not what costs: `grim` and the PNG encodes
# come to 0.9 s BETWEEN them, and almost the whole sheet half is the read-back
# against HEAD (34.3 s). What costs is the idle probe — 97.6 s, 54% of
# everything, five windows each deliberately holding still for ten seconds —
# and that is the least skippable verdict in the file. The 2m25s this header
# quoted until now is where the same measurement lands the other lesson: B74's
# comparison added 34 s to the run and nobody re-measured the total.
# The path list above is in `DECLARED_GATES` in tools/dependents.py, held
# equal to this one by tools/tests/test_dependents.py; `flake.lock` is in it
# on this script's own argument, that a sheet rendered against a different Qt
# or a different sway is a picture of a different machine.
set -euo pipefail

root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
out="${1:-$root/docs/hud/screens}"

# WHAT THE RUN COSTS, booked as it is spent (PLAN B75). Two clocks write one
# file: these three phases are the shell's, the rest are booked inside
# tools/hudscreens/shoot.py, and `sheet.PHASES` says which half of the run
# each belongs to — the half a verdict-only run would still pay, or the half
# only the pictures need. The table is printed at the end, below.
#
# `date` rather than bash's own $EPOCHREALTIME, and awk under LC_ALL=C:
# neither the stamp nor the subtraction may depend on a locale's idea of
# where the decimal point goes.
run_t0=$(date +%s.%N)
book() {  # book <phase> <start> — seconds from <start> until now
  LC_ALL=C awk -v n="$1" -v a="$2" -v b="$(date +%s.%N)" \
    'BEGIN { printf "%s\t%.3f\n", n, b - a }' >> "$cost"
}

# Realize out of the flake's own pinned nixpkgs, rather than whatever this
# machine happens to have: a sheet rendered against a different Qt or a
# different sway would be a picture of a different machine.
nixpkgs() {
  nix build --no-link --print-out-paths --impure --expr \
    "(builtins.getFlake (toString $root)).inputs.nixpkgs.legacyPackages.\${builtins.currentSystem}.$1"
}

echo "hudscreens: realizing the compositor and the shell…" >&2
realize_t0=$(date +%s.%N)
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
# The book cannot be opened before this line — the stage is where it lives —
# so the realization above is booked from its own stamp the moment it can be.
cost="$stage/cost.tsv"
book realize "$realize_t0"
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

compositor_t0=$(date +%s.%N)

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
book compositor "$compositor_t0"

export JV_SCREENS_OUT="$out"
export JV_SCREENS_STAGE="$stage"
export JARVISD_BIN="$jarvisd/bin/jarvisd"
export JV_HUD_BIN="$hud/bin/jv-hud"
export GRIM_BIN="$grim/bin/grim"
export WEV_BIN="$wev/bin/wev"
export SWAYMSG_BIN="$sway/bin/swaymsg"

"$py/bin/python" "$root/tools/hudscreens/shoot.py"

# And READ THEM BACK (B74). Until this line these were pictures that
# could only be overwritten: `hudshots.sh` has compared its own sheet against
# HEAD since B52, and the only reason this one did not was that it cannot do
# it to the byte. The floor that makes it possible is measured — see
# NOISE_PIXELS in tools/hudscreens/sheet.py — and it is stated in the report
# every time it absorbs anything, because a comparison whose tolerance is
# silent is a comparison nobody can audit.
#
# --accept-noise ONLY when this run is writing over the committed sheet: it
# puts the committed bytes back over screens that moved by rounding alone,
# which is what makes the run idempotent. A run pointed at a scratch
# directory — a measurement, or a grading run — must leave exactly what it
# rendered, or the next person to measure the noise measures the restore.
floor=$("$py/bin/python" -c "
import sys; sys.path.insert(0, '$root/tools/hudscreens'); import sheet
print(sheet.NOISE_PIXELS, sheet.NOISE_CHANNEL)")
accept=()
[ "$(realpath -m "$out")" = "$(realpath -m "$root/docs/hud/screens")" ] && accept=(--accept-noise)
compare_t0=$(date +%s.%N)
compare_status=0
"$py/bin/python" "$root/tools/hudsheet.py" \
  --root "$root" --out "$out" --sheet docs/hud/screens \
  --rerun "bash ops/ralph/hudscreens.sh" \
  --tolerance-pixels "${floor% *}" --tolerance-channel "${floor#* }" \
  "${accept[@]}" || compare_status=$?
book compare "$compare_t0"

# AND WHERE THE TIME WENT (PLAN B75). The comparison's status is caught
# rather than allowed to end the run, because the run whose cost anybody
# asks about is the one that found a changed HUD: it exits nonzero by
# design, and under `set -e` that would take this table with it.
"$py/bin/python" - "$root/tools/hudscreens" "$cost" "$run_t0" <<'EOF'
import sys, time
sys.path.insert(0, sys.argv[1])
import sheet

records = sheet.read_cost(open(sys.argv[2]).read())
total = time.time() - float(sys.argv[3])
print("\n".join(sheet.cost_table(records, total)))
EOF

exit $compare_status
