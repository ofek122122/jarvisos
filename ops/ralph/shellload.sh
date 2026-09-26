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
#   · A shell with nothing to say evaluates almost none of its own QML, and
#     the BAR is now the only one of the three in that state: it runs with no
#     niri, so `linkUp` is false and the workspaces row builds no delegates.
#     What this covers for it is the outermost file, the per-screen `Variants`
#     delegate, and every binding evaluated whatever the state — which is
#     where D34's and D39's faults both were, and is not the whole shell.
#     `JV_BAR_NIRI` is `--set` into the wrapper, so its event stream cannot
#     be pointed at a fake without staging the shell, which is the one thing
#     this gate refuses (PLAN D43).
#   · The other two ARE woken, each by the only thing that can reach it.
#     `tools/shellload/load.py` asks the notification daemon what it can do
#     and then sends it one notification over the private bus, so the corner
#     maps and the Repeater builds a Toast — the first thing in this repo ever
#     to prove the D-Bus name is claimed and answers (PLAN D22). And the HUD
#     gets a real broker: `jarvisd` on this run's own socket below,
#     `tools/shellload/publish.py` putting eleven composed frames on it at
#     1 Hz, and the HUD's own read-only bridge carrying them in. Ten of its
#     eleven plates light, the surface is CREATED (with no jarvisd it never
#     was), and the corner says which plates it is showing so this gate can
#     tell a HUD that received the frames from one that ignored them
#     (PLAN D43).
#   · AND THE HUD IS LOADED TWICE, because its eleventh plate is on screen
#     exactly while the other ten cannot be. `LinkPlate` says this HUD cannot
#     SEE the bus, so a fourth quickshell runs the same shipped binary with
#     `JARVIS_BUS` pointed at nothing, waits out `core/LinkState.qml`'s grace,
#     and the corner has to name exactly `link` (PLAN D47). That is the first
#     thing anywhere to prove the HUD ever admits it is blind — and the only
#     reading that can tell a plate REFUSING (every state machine under this
#     corner is built to, and a refusal draws the same nothing a calm machine
#     does) from a plate with nothing to say.
#   · AND THEN THAT RUN IS GIVEN A BUS, which is the more dangerous half
#     (PLAN D49). `LinkState` never clears the flag its grace set, so a plate
#     that latched on forever passes the census above exactly as the shipped
#     one does — and a permanent NO BUS over a healthy machine teaches the user
#     to ignore the one plate that qualifies all the others. A real broker is
#     started on the very socket that HUD has been failing to reach, the bridge
#     retries forever by design, and the corner has to go DARK again.
#   · AND THEN IT HAS TO WORK AGAIN (PLAN D52), which is what turns two
#     readings into a cycle: blind → says so → lets go → reports the machine.
#     The recovered HUD is shown the same eleven frames on that late broker and
#     its corner has to light the same ten plates — on an engine whose
#     `BusModel` caches the outage emptied and whose link went down, repeatedly,
#     before it came back. Measured, by making `BusModel.ingest` drop frames
#     after a second link-down: the frames run stays green, the dark census
#     above stays green, this one goes red, and all 721 of the HUD's own
#     headless QML tests pass. It is the only reading in this repo that can see
#     a HUD which is linked, silent, and certain it is fine.
#   · AND BOTH BROKERS ARE NOW READ (PLAN D51), which nothing did until now.
#     Every claim above about the HUD is a reading of what a `jarvisd` did, and
#     the only thing that had ever opened either broker's log was the failure
#     message D49 quotes it into — so a broker that came up and then refused
#     the bridge's subscription reads from the corner as a HUD that ignored its
#     frames, which is the wrong repair by a whole process.
#     `tools/brokerlog.py` is the second reader, because `tools/qmlerrors.py`
#     knows three QML engines' prefixes and a Rust tracing line is not one of
#     them: over a broker's log it says "nothing threw" whatever the log says.
#     The rule is every line is one the broker wrote at INFO or below, plus a
#     census — it has to have announced the socket this run told it to bind,
#     which is what keeps a log nobody wrote from reading clean.
#   · AND ONE OF THE OUTPUTS IS NOT A MONITOR (PLAN D75). The compositor is
#     given a fourth screen, 768 px tall, which is under the floor
#     `shell/jv-hud/shell.qml` declares its corner is for. D74 settled that
#     question as a declared floor rather than as a clamp — the compositor
#     crops the bottom of the stack, every plate is still drawn, and the shell
#     SAYS SO — and until this output the saying-so was a regex over a file no
#     engine in this repo loads. Here it is a behaviour: the warn has to arrive
#     naming that screen and its own height, the corner there has to name the
#     same ten plates as everywhere else (a HUD that had grown a height clamp
#     would name nine), and the three monitors have to be left out of it. The
#     assertion is in `tools/shellload/load.py` and not in the scan below,
#     because `tools/qmlerrors.py` wants a source location and an ECMAScript
#     error name: a warning is invisible to it by design.
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
#      `hudscreens.sh` carries, for the same reason. It covers the brokers too,
#      for the same reason and with a better failure direction: tracing colours
#      its level as well, and a coloured broker log parses as NO lines at all,
#      so `tools/brokerlog.py`'s census fails and the run goes red rather than
#      green — red for the wrong reason, which is still worth knowing.
#
# reads: flake.lock flake.nix personality/theme.toml pkgs/jv-bar pkgs/jv-hud
#        pkgs/jv-notify services/jarvisd services/jv-hud-bridge services/pylib
#        shell/jv-bar shell/jv-hud shell/jv-notify tools/brokerlog.py
#        tools/qmlerrors.py tools/shellload
#
# Declared, like the other two nix gates (PLAN B72): what it reads is a set of
# flake attributes, and an attribute is not a path any syntax tree names. The
# list above is in `DECLARED_GATES` in tools/dependents.py, held equal to this
# one by tools/tests/test_dependents.py. `flake.lock` is in it on the same
# argument `hudscreens.sh` makes for its own: a shell loaded against a
# different Qt or a different quickshell is a different shell.
#
# IT NOW READS THE BUS, and it deliberately did not until D43. The old reason
# was that nothing here started a broker, so a change to the bus could not move
# this verdict and binding it would spend these seconds on every Rust edit to
# learn that. The HUD's half of this gate is that broker, so the three paths it
# runs on are in the list: `services/jarvisd` is the broker, `services/pylib`
# is the client both the publisher and the bridge speak through, and
# `services/jv-hud-bridge` is the child process the HUD's own wrapper pins —
# the one thing that carries a frame from the bus into a plate. Every one of
# them can turn ten lit plates into none, which is what this gate now asks.
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
# msgpack and nothing else on top of the stdlib. The bus speaks MessagePack, so
# `tools/shellload/publish.py` cannot put a frame on it without the one library
# `services/pylib` imports; everything else here is stdlib, and in particular
# there is still no numpy — this harness measures no pixels.
py=$(nixpkgs 'python3.withPackages (ps: [ ps.msgpack ])')

stage=$(mktemp -d)
cleanup() {
  [ -n "${swaypid:-}" ] && kill "$swaypid" 2>/dev/null || true
  [ -n "${dbuspid:-}" ] && kill "$dbuspid" 2>/dev/null || true
  [ -n "${buspid:-}" ] && kill "$buspid" 2>/dev/null || true
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
# HOW MANY, from `shells.py` rather than from here (PLAN D75). The backend
# makes this many outputs and the config above names them, and the two are one
# number: a config naming four against a backend making three leaves the fourth
# at whatever size wlroots defaults to — a real screen, drawn on, and not the
# 768 px one this gate added in order to ask what the HUD does on a screen
# shorter than its own corner.
export WLR_HEADLESS_OUTPUTS=$("$py/bin/python" -c "
import sys; sys.path.insert(0, '$tool'); import shells
print(len(shells.ALL_OUTPUTS))")
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

# THE BUS, this run's own, on a socket inside the stage (PLAN D43). The HUD's
# whole view of the machine comes through it: `Bus.qml` runs `jv-hud-bridge` as
# a child, the bridge subscribes, and without a broker to subscribe TO every
# plate is unmapped and the surface is never created. It is realized from the
# flake like the shells, because the broker this gate runs must be the one the
# flake declares — and it is started here rather than in the driver for the same
# reason the shells are: `nix build` is the one thing in this harness that is
# not a measurement, and the driver must never be able to produce a binary.
#
# `--health-period` is left at its default. A heartbeat from the broker itself
# is not something any plate reads — `core/HealthState.qml` keys on the service
# NAMED in the body and refuses one that disagrees with the sender — so the
# cadence changes nothing here, and a number chosen by this gate would be a
# number the real jarvisd does not run at.
jarvisd=$(nix build "$root#jarvisd" --no-link --print-out-paths)
# The socket it binds and the file it writes are named in `shells.py`, not
# here: the reader at the foot of this script has to open the same log this
# line redirects, and two spellings of one path is how a gate ends up grading
# a file nobody writes (PLAN D51).
IFS=$'\t' read -r brokerlog busname < <("$py/bin/python" - "$tool" <<'EOF'
import sys
sys.path.insert(0, sys.argv[1])
import shells

print(f"{shells.FRAMES_BROKER_LOG}\t{shells.FRAMES_BUS}")
EOF
)
export JARVIS_BUS="$stage/$busname"
"$jarvisd/bin/jarvisd" --bus "$JARVIS_BUS" > "$stage/$brokerlog.log" 2>&1 &
buspid=$!
for _ in $(seq 1 100); do
  [ -S "$JARVIS_BUS" ] && break
  sleep 0.1
done
[ -S "$JARVIS_BUS" ] || {
  echo "shellload: jarvisd never created $JARVIS_BUS" >&2
  sed -n 1,40p "$stage/$brokerlog.log" >&2
  exit 1
}

export JV_SHELLLOAD_STAGE="$stage"
export GDBUS_BIN="$glib/bin/gdbus"
# The broker, handed over rather than rebuilt: the blind HUD's second act needs
# one started on ITS bus, after it has been failing to connect (PLAN D49), and
# the driver may not build anything. Same store path as the broker above, so
# the two acts of that run cannot be about two different brokers.
export JARVISD_BIN="$jarvisd/bin/jarvisd"
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
#
# One per ENGINE rather than one per shell, which is why the pairs come out of
# `scan_targets()`: the HUD is started twice — once with a broker and once with
# `JARVIS_BUS` pointed at nothing (PLAN D47) — and a loop over the three shells
# would have left the blind run's log unread. Both of its logs are reported
# under the HUD's root, because both are the same store path.
scan_status=0
while IFS=$'\t' read -r logname shellroot; do
  "$py/bin/python" "$root/tools/qmlerrors.py" "$stage/$logname.log" \
    --prefix "$shellroot" --rerun "bash ops/ralph/shellload.sh" || scan_status=$?
done < <("$py/bin/python" - "$tool" <<'EOF'
import sys
sys.path.insert(0, sys.argv[1])
import shells

for logname, root in shells.scan_targets():
    print(f"{logname}\t{root}")
EOF
)

# AND READ WHAT EACH BROKER SAID (PLAN D51), which is the half of this run
# nothing has ever opened. Two `jarvisd` run here — the one above and the one
# `relink()` starts on the blind HUD's own socket (PLAN D49) — and every claim
# this gate makes about the HUD is a reading of what they did. A broker that
# came up and then refused the bridge's subscription, or logged an error per
# frame, reads from the corner as a HUD that ignored its frames, which is the
# wrong repair by a whole process.
#
# Its own reader rather than `tools/qmlerrors.py`: that one knows three QML
# engines' prefixes and a Rust tracing line is not one of them, so over a
# broker's log it reports "nothing threw" whatever the log says. One
# invocation per broker, because the census is that each announced ITS OWN
# socket and a reader handed both logs could only have checked neither.
broker_status=0
while IFS=$'\t' read -r logname busfile; do
  "$py/bin/python" "$root/tools/brokerlog.py" "$stage/$logname.log" \
    --listening "$stage/$busfile" --rerun "bash ops/ralph/shellload.sh" \
    || broker_status=$?
done < <("$py/bin/python" - "$tool" <<'EOF'
import sys
sys.path.insert(0, sys.argv[1])
import shells

for logname, busfile in shells.broker_targets():
    print(f"{logname}\t{busfile}")
EOF
)

# A shell that threw is the worse news of the three and the one that
# invalidates the others: "it loaded" is a claim about a scene that was
# throwing while it did. So it wins the exit code, and the broker's verdict
# comes next — it invalidates the loading for the same reason one step further
# out, since a corner with nothing to show is what a broken broker looks like
# from here.
[ "$scan_status" -ne 0 ] && exit "$scan_status"
[ "$broker_status" -ne 0 ] && exit "$broker_status"
exit $load_status
