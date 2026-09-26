#!/usr/bin/env bash
# ops/ralph/notifyshots.sh — photograph the notification corner (PLAN D20).
#
# The sibling of `hudshots.sh`, one shell over, and a separate script for the
# same reason `notifytest.sh` is separate from `qmltest.sh`: `tools/verify.py`
# runs a gate by its command string and derives which gates to run from what
# you touched, so one script pointed at two shells would be one command, and
# editing a toast would rebuild the HUD's sheet instead of this one.
#
# Writes docs/notify/*.png: the real Toast, over the real theme, in the real
# faces personality/theme.toml names, driven through the real
# core/NotifyModel.qml. Run it after any change to shell/jv-notify and commit
# the diff — a corner whose look changed and whose sheet did not is a corner
# nobody looked at.
#
# WHY THIS SHELL NEEDS A SHEET MORE THAN THE OTHER TWO. It is the only surface
# on this machine whose CONTENT comes from programs this repo did not write.
# The HUD is fed by the bus and the bus is schema'd; a notification is any
# string, of any length, in any script, from any process with a D-Bus session —
# landing on a plate that floats over every window and has no input region, so
# nothing can move it out of the way. "What does a toast do with a
# 4000-character summary, an app name that is one unbroken 120-character word,
# or three criticals at once" is a question only pixels answer, and
# `tst_shots.qml` next door is where each one is asked.
#
# It then READS THE SHEET BACK, exactly as hudshots.sh does (B52): every PNG it
# just rendered, compared against the one committed at HEAD, by
# tools/hudsheet.py. A run whose plates drew something else ends nonzero,
# naming the shots that moved and three of the pixels that moved in them. If
# the change was yours, that is the refresh telling you what you changed — look
# at the new PNGs, commit them, and the next run is green.
#
# WHY THERE IS A STAGING COPY. Two files in this shell import Quickshell and
# cannot be loaded by any other engine, because quickshell links its QML plugin
# into its own binary: `Notifications` (it IS the
# org.freedesktop.Notifications server) and `Motion` (it reads one environment
# variable through Quickshell.env). QML resolves a singleton through the
# directory's qmldir, so the only way to substitute one is to BE that
# directory. Everything else in the stage is a verbatim copy: Toast.qml, the
# generated Theme and Ease, core/, the qmldir.
#
# WHAT THIS IS NOT. Not the compositor: layer-shell, the empty input mask, the
# zero exclusive zone, the unmapped-when-empty surface and the three monitors
# are shell.qml's, and a human at the machine is still the only thing that can
# confirm them. Not a daemon either — there is no D-Bus session here. This is
# the CONTENT of one surface.
set -euo pipefail

root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
out="${1:-$root/docs/notify}"

# Realize a package out of the flake's own pinned nixpkgs, rather than
# evaluating a store path that may never have been built on this machine.
nixpkgs() {
  nix build --no-link --print-out-paths --impure --expr \
    "(builtins.getFlake (toString $root)).inputs.nixpkgs.legacyPackages.\${builtins.currentSystem}.$1"
}

qtdecl=$(nixpkgs qt6.qtdeclarative.out)
fontconfig=$(nixpkgs fontconfig.out)
fcbin=$(nixpkgs fontconfig.bin)
mono=$(nixpkgs jetbrains-mono.out)
# The comparator that reads the sheet back (B52), pinned like everything else
# here rather than borrowed from the machine's PATH.
python=$(nixpkgs python3)
sans=$(nix build "$root#archivo" --no-link --print-out-paths)

stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT

# The shell, verbatim…
cp -r "$root/shell/jv-notify/." "$stage/"
rm -rf "$stage/tests"
# shell.qml is the Quickshell half — ShellRoot, PanelWindow, the layer-shell
# bindings — and none of it can resolve here. It is linted where it belongs, in
# the jv-notify build, against quickshell's own qml import path; leaving it in
# the stage would only mean linting it against an import it cannot have. The
# stack inside it is staged as tools/notifyshots/scene/Strip.qml, and a test
# holds the two to the same composition.
rm -f "$stage/shell.qml"
# …with the two Quickshell-bound singletons replaced, and nothing else. Both
# are registered in the shell's own qmldir, which is copied above unchanged —
# so `Notifications` and `Motion` resolve here to these files by being in this
# directory, and a stage missing one of them would not fall back, it would fail
# to load.
cp "$root/tools/notifyshots/stub/Notifications.qml" "$stage/Notifications.qml"
cp "$root/tools/notifyshots/stub/Motion.qml" "$stage/Motion.qml"
# The driver sits in a subdirectory with no qmldir of its own, so the staged
# shell next to it resolves by plain directory import (`import ".."`) — the
# same shape hudshots.sh uses.
mkdir -p "$stage/shots"
cp "$root"/tools/notifyshots/scene/*.qml "$stage/shots/"
# And the shared probe body (PLAN D38), which `warnprobe.qml` next to it
# instantiates. It lives in tools/qmlprobe because all three harnesses load
# their own scene the same way, and three copies of it would be three things
# to keep matching.
cp "$root/tools/qmlprobe/Probe.qml" "$stage/shots/"

# The faces theme.toml names, pinned rather than borrowed from whatever this
# machine happens to have installed: a sheet rendered in DejaVu would be a
# picture of a fallback. This proves the DECLARED look — that ares itself
# resolves these families is a different claim, and the one `jv-fonts-resolve`
# in system.checks makes (A19).
export XDG_CACHE_HOME="$stage/cache"
mkdir -p "$XDG_CACHE_HOME"
cat > "$stage/fonts.conf" <<EOF
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>
  <include ignore_missing="yes">$fontconfig/etc/fonts/conf.d</include>
  <dir>$mono/share/fonts</dir>
  <dir>$sans/share/fonts</dir>
  <cachedir>$stage/cache/fontconfig</cachedir>
</fontconfig>
EOF
export FONTCONFIG_FILE="$stage/fonts.conf"

for family in "JetBrains Mono" "Archivo"; do
  got=$("$fcbin/bin/fc-match" --format '%{family}' "$family")
  case ",$got," in
    *",$family,"*) ;;
    *)
      echo "notifyshots: \"$family\" resolves to \"$got\" — the sheet would be a picture of a fallback" >&2
      exit 1
      ;;
  esac
done

# The linter the jv-notify build runs, over the thing that will actually be
# rendered. The stubs, the staged strip and the driver live outside
# shell/jv-notify, so this is the only place they are ever linted; without it
# they would be the one corner of this shell with no gate on it.
"$qtdecl/bin/qmllint" -W 0 --uncreatable-type disable \
  -I "$qtdecl/lib/qt-6/qml" \
  $(find "$stage" -name '*.qml' | sort)

# THE SECOND ENGINE (PLAN D38). qmltestrunner drops every message logged while
# no test function is RUNNING, and the first driver in a directory has its
# whole scene built before the run begins — so a `console.warn` in
# `Component.onCompleted`, and every error thrown by a binding evaluated as
# that scene is built, never reach the log the scanner above reads. Measured,
# with two identical drivers in one directory: only the second one is heard.
# Which of a harness's surfaces D36 covers is therefore decided by
# alphabetical order, and the uncovered one is the first.
#
# So the same stage is loaded a second time, under plain `qml`: not QtTest, no
# handler of its own, the engine's messages straight to stderr as the engine
# wrote them. Same scanner, same rule, the half of the scene the runner cannot
# speak for. `tools/qmlprobe/Probe.qml` also counts what the scene built, so a
# probe that quietly loaded nothing cannot pass as a clean one.
#
# QT_FORCE_STDERR_LOGGING because this Qt is built with the journald backend:
# with stderr in a pipe — which is exactly what `tee` makes it — every message
# goes to the journal instead. Measured, not assumed: without it this prints
# nothing at all, not even its own count.
probelog="$stage/probe.log"
QT_QPA_PLATFORM=offscreen QT_FORCE_STDERR_LOGGING=1 \
  timeout 120 "$qtdecl/bin/qml" -I "$qtdecl/lib/qt-6/qml" \
  "$stage/shots/warnprobe.qml" 2>&1 | tee "$probelog"
"$python/bin/python3" "$root/tools/qmlerrors.py" "$probelog" \
  --stage "$stage" --rerun "bash ops/ralph/notifyshots.sh"

mkdir -p "$out"
# The driver writes relative to the working directory: a QML test cannot read
# an environment variable, so this is how it is told where to look.
cd "$out"
export QT_QPA_PLATFORM=offscreen
export HOME="$stage"
# The runner, with its output CAPTURED as well as shown (PLAN D36). `tee`
# keeps every line on the terminal — a gate behind a silent pipe is
# indistinguishable from a hang — and the copy is read by
# `tools/qmlerrors.py`, which ends this run non-zero if anything in the scene
# THREW. That is not the same question as "did a test fail": a QML handler
# that throws keeps the value the property already had and recovers on the
# next evaluation, so the surface stays plausible, the shots come out
# byte-identical and the totals come out green. D34 shipped exactly that, and
# one QWARN line in output nobody reads was the only evidence it ever gave.
# `console.warn` stays a legitimate voice — the rule is about an error the
# engine attributed to a file and a line number.
log="$stage/runner.log"
"$qtdecl/bin/qmltestrunner" \
  -input "$stage/shots" \
  -import "$qtdecl/lib/qt-6/qml" 2>&1 | tee "$log"
"$python/bin/python3" "$root/tools/qmlerrors.py" "$log" \
  --stage "$stage" --rerun "bash ops/ralph/notifyshots.sh"

echo
echo "notifyshots: wrote $(ls "$out"/*.png | wc -l) shots to $out"
echo

# And READ THEM BACK (B52), against the last COMMITTED sheet — never against
# the directory this run just wrote into, which would be comparing a file to
# itself. A deliberate change to the corner ends here, nonzero, naming the
# shots that moved and the pixels that moved in them. That is the report, not a
# failure: the new PNGs are on disk, and committing them is the refresh.
"$python/bin/python3" "$root/tools/hudsheet.py" \
  --root "$root" --out "$out" \
  --sheet docs/notify \
  --subject "the notification corner" \
  --rerun "bash ops/ralph/notifyshots.sh"
