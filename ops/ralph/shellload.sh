#!/usr/bin/env bash
# ops/ralph/shellload.sh — LOAD all three shells under a real quickshell, on a
# real compositor, and refuse a run whose QML threw (PLAN D41).
#
# THE HOLE THIS FILLS, measured rather than argued. Before it,
# `ops/ralph/hudscreens.sh` was the only gate in this repo that ran a real
# quickshell, and the HUD's `shell.qml` was the only one any engine ever
# opened. The bar's and the notifier's were qmllint-clean and nothing more:
# every shot harness deletes `shell.qml` from its stage on purpose, because
# ShellRoot, PanelWindow and the layer-shell attached properties cannot resolve
# outside quickshell's own binary. So the two surfaces that reserve screen
# space and take this machine's org.freedesktop.Notifications name had their
# outermost file held by a linter alone — and the D34/D39 shape, a `var`
# binding that throws and leaves the surface plausible, is exactly what a
# linter cannot see.
#
# WHAT IT COSTS, and the price is the whole reason it is a separate gate.
# `hudscreens.sh` is 3m15s, of which 97.7 s is an idle probe holding still, and
# what it produces is a directory of pictures somebody has to look at — so it
# is named to you rather than run for you (B72/B75). This is the CHEAP HALF
# B75 asked about, for the one question that is a verdict: did the shell load,
# and did it say anything that throws. One sway, three quickshells, no
# screenshots, no sheet to compare. `verify.sh` runs it.
#
# WHAT IT IS NOT, and every line of this is a limit somebody will otherwise
# read as coverage:
#   · Not a picture. Nothing here looks at a pixel. A surface that loaded
#     cleanly and drew in the wrong corner passes this and fails hudscreens.
#     It DOES now ask the compositor what each surface RESERVED, which is the
#     strongest thing available without a picture (PLAN D44): sway shrinks
#     every workspace rect by every exclusive zone, so the bar's strip has to
#     be missing from all three monitors while it is up and back on all three
#     once it is gone, and the other two have to leave every monitor whole.
#     The bar's half is a proof of mapping — an unmapped surface reserves
#     nothing, so 31 px cannot go missing unless the strip is really there.
#     The other two are a refutation and a NARROW one; the measured reason is
#     in the D44 section of tools/shellload/shells.py and is worth reading
#     before anybody counts this as coverage of the HUD.
#   · A shell with nothing to say evaluates almost none of its own QML. The
#     HUD runs with no jarvisd (every plate unmapped, the bus blind) and the
#     bar with no niri (`linkUp` false, no workspace delegates). What this
#     covers for those two is the outermost file, the per-screen `Variants`
#     delegate, and every binding evaluated whatever the state — which is
#     where D34's and D39's faults both were, and is not the whole shell.
#   · The notifier is the exception, deliberately: it gets a real client.
#     `tools/shellload/load.py` asks the running daemon what it can do and
#     then sends it one notification over the private bus, so the corner maps
#     and the Repeater builds a Toast. That is also the first thing in this
#     repo ever to prove the D-Bus name is claimed and answers (PLAN D22).
#
# TWO THINGS THE ENVIRONMENT MUST DO, both measured, neither optional:
#   1. DBUS_SESSION_BUS_ADDRESS is REPLACED, not inherited. Run without that,
#      `jv-notify` reaches the user's own live session bus and tries to claim
#      org.freedesktop.Notifications on it — observed, as "presumably because
#      one is already registered". Had it won, this gate would have taken over
#      the notifications of the desktop it was running inside. The bus below is
#      this run's own and has NO activatable services, which is the other half:
#      `dbus-run-session` inherits the machine's service directories and the
#      first version of this started four portals and a keyring inside a gate
#      about three QML files.
#   2. NO_COLOR=1. Quickshell colours its log with ANSI escapes whether or not
#      anything is watching, and `\x1b[33m` in front of every level is not a
#      prefix `tools/qmlerrors.py` knows — so the scan would come back clean
#      over a shell that threw on every frame. Same load-bearing line
#      `hudscreens.sh` carries, for the same reason.
#
# reads: flake.lock flake.nix personality/theme.toml pkgs/jv-bar pkgs/jv-hud
#        pkgs/jv-notify shell/jv-bar shell/jv-hud shell/jv-notify
#        tools/qmlerrors.py tools/shellload
#
# Declared, like the other two nix gates (PLAN B72): what it reads is a set of
# flake attributes, and an attribute is not a path any syntax tree names. The
# list above is in `DECLARED_GATES` in tools/dependents.py, held equal to this
# one by tools/tests/test_dependents.py. `flake.lock` is in it on the same
# argument `hudscreens.sh` makes for its own: a shell loaded against a
# different Qt or a different quickshell is a different shell.
#
# It does NOT read `services/jarvisd`. Nothing here starts a broker — see the
# second limit above — so a change to the bus cannot move this verdict, and
# binding it would spend this gate's seconds on every Rust edit to learn that.
#
# NOTE — the paths above are the shells, and this script may not name them.
# `tools/shellload/shells.py` holds the three roots, and
# `test_the_gate_loads_the_shipped_binaries_and_stages_nothing` refuses the
# string `shell/` in any line executed here. The rule is blunt and it is the
# right one: a `cp` out of the working tree is exactly how a gate on what ships
# stops being one.
set -euo pipefail

root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
tool="$root/tools/shellload"

# Realize out of the flake's own pinned nixpkgs rather than whatever this
# machine has: the version of sway and of Qt are part of what is being asked.
nixpkgs() {
  nix build --no-link --print-out-paths --impure --expr \
    "(builtins.getFlake (toString $root)).inputs.nixpkgs.legacyPackages.\${builtins.currentSystem}.$1"
}

echo "shellload: realizing the compositor, the bus and the shells…" >&2
sway=$(nixpkgs sway)
# `.out` rather than the bare attribute: dbus is a multi-output derivation and
# `--print-out-paths` would hand back its man pages as well.
dbus=$(nixpkgs 'dbus.out')
# The notifier's one real client. `glib.bin` is where gdbus lives.
glib=$(nixpkgs 'glib.bin')
# stdlib only, on purpose: this harness measures nothing and needs no numpy.
py=$(nixpkgs python3)

stage=$(mktemp -d)
cleanup() {
  [ -n "${swaypid:-}" ] && kill "$swaypid" 2>/dev/null || true
  [ -n "${dbuspid:-}" ] && kill "$dbuspid" 2>/dev/null || true
  rm -rf "$stage"
}
trap cleanup EXIT

# A private runtime dir, so this never shares a wayland socket with whatever
# the user is running — and so a crashed run leaves nothing in /run/user.
export XDG_RUNTIME_DIR="$stage/run"
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
export HOME="$stage"
export XDG_CACHE_HOME="$stage/cache"
export XDG_CONFIG_HOME="$stage/config"

# The session bus, this run's own. See limit 1 in the header — without this
# line the notifier competes with the user's real notification daemon.
"$py/bin/python" - "$tool" "$stage" <<'EOF'
import sys
sys.path.insert(0, sys.argv[1])
import shells

open(f"{sys.argv[2]}/dbus.conf", "w").write(shells.dbus_conf(f"{sys.argv[2]}/run"))
EOF
dbusout="$("$dbus/bin/dbus-daemon" --config-file="$stage/dbus.conf" \
  --print-address --print-pid --fork)"
export DBUS_SESSION_BUS_ADDRESS="$(echo "$dbusout" | sed -n 1p)"
dbuspid="$(echo "$dbusout" | sed -n 2p)"
# Nothing here is a system service and nothing may look for one.
unset DBUS_SYSTEM_BUS_ADDRESS || true

# The monitors and the compositor's rules come from tools/shellload/shells.py —
# one source, read by the compositor here and by the checks in
# tools/tests/test_shellload.py.
"$py/bin/python" - "$tool" "$stage/sway.conf" <<'EOF'
import sys
sys.path.insert(0, sys.argv[1])
import shells

open(sys.argv[2], "w").write(shells.sway_config())
EOF

# Headless wlroots with software rendering: no DRM, no GPU, no seat. A shell is
# a Wayland client and cannot tell the difference; what it CAN tell the
# difference about — layer-shell, exclusive zones, per-output surfaces — is all
# compositor protocol and all real here.
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
[ -n "${sock:-}" ] || {
  echo "shellload: sway never created a wayland socket" >&2
  sed -n 1,40p "$stage/sway.log" >&2
  exit 1
}
export WAYLAND_DISPLAY="$(basename "$sock")"
# The IPC socket, which is a different socket from the wayland one and the only
# way to ask what a surface reserved (PLAN D44). sway writes it beside the
# other, in this run's own private runtime dir.
export SWAYSOCK="$(ls "$XDG_RUNTIME_DIR"/sway-ipc.*.sock | head -1)"

# Qt has to be told, or it picks xcb, fails to find a display, and the
# layer-shell attached properties quietly fail to attach — which looks like a
# shell that loaded and drew nothing.
export QT_QPA_PLATFORM=wayland
# See limit 2 in the header. Load-bearing: without it every line of every log
# below is unprefixed noise to the scanner.
export NO_COLOR=1

export JV_SHELLLOAD_STAGE="$stage"
export GDBUS_BIN="$glib/bin/gdbus"
# The compositor's own IPC, which is the only thing here that can say whether a
# surface MAPPED rather than merely loaded (PLAN D44).
export SWAYMSG_BIN="$sway/bin/swaymsg"
# Every shell, realized by the attribute tools/shellload/shells.py names, and
# handed over in the variable it names. The loop is here rather than in the
# driver because `nix build` is the one thing in this harness that is not a
# measurement — and because the driver must never be able to build anything.
while IFS=$'\t' read -r attr var; do
  out=$(nix build "$root#$attr" --no-link --print-out-paths)
  export "$var=$out/bin/$attr"
done < <("$py/bin/python" - "$tool" <<'EOF'
import sys
sys.path.insert(0, sys.argv[1])
import shells

for shell in shells.SHELLS:
    print(f"{shell.attr}\t{shell.env}")
EOF
)

load_status=0
"$py/bin/python" "$tool/load.py" || load_status=$?

# AND READ WHAT EACH SHELL SAID (PLAN D36/D39), whatever the loading said: a
# shell that reached `Configuration Loaded` and threw on every screen is the
# failure this gate was written for, and it is invisible to every exit code
# above.
#
# One scan per shell rather than one over all three, because each needs its own
# `--prefix`: quickshell prints the paths it throws on relative to the root it
# loaded, which at runtime is a store path, so `core/MotionPolicy.qml` without
# a root is three directories in this repository. The roots come out of
# `shells.py` rather than being written here — see the NOTE in the header.
#
# The statuses are collected rather than allowed to end the run, so a second
# shell's faults are not hidden behind the first one's.
scan_status=0
while IFS=$'\t' read -r attr shellroot; do
  "$py/bin/python" "$root/tools/qmlerrors.py" "$stage/$attr.log" \
    --prefix "$shellroot" --rerun "bash ops/ralph/shellload.sh" || scan_status=$?
done < <("$py/bin/python" - "$tool" <<'EOF'
import sys
sys.path.insert(0, sys.argv[1])
import shells

for shell in shells.SHELLS:
    print(f"{shell.attr}\t{shell.root}")
EOF
)

# A shell that threw is the worse news of the two and the one that invalidates
# the other: "it loaded" is a claim about a scene that was throwing while it
# did. So it wins the exit code.
[ "$scan_status" -ne 0 ] && exit "$scan_status"
exit $load_status
