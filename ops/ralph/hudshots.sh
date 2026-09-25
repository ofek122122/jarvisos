#!/usr/bin/env bash
# ops/ralph/hudshots.sh — photograph the HUD, so looking at it stops
# requiring a seat at ares (PLAN A29).
#
# Writes docs/hud/*.png: the real plates, over the real theme, in the real
# faces personality/theme.toml names, driven through the real
# core/BusModel.qml by real recordings where a recording exists. Run it
# after any change to shell/jv-hud and commit the diff — a HUD whose look
# changed and whose sheet did not is a HUD nobody looked at.
#
# It then READS THE SHEET BACK (B52): every PNG it just rendered, compared
# against the one committed at HEAD, by tools/hudsheet.py. A run whose plates
# drew something else ends nonzero, naming the shots that moved and three of
# the pixels that moved in them. If the change was yours, that is the refresh
# telling you what you changed — look at the new PNGs, commit them, and the
# next run is green.
#
# It also runs the one suite that needs this same stage and takes no
# pictures: tst_sequence.qml (A54) replays the recorded sessions through the
# real plates and asserts the corner's TRAJECTORY — which plates go up, in
# what order, at which second of a real turn. A shot is one settled instant;
# a plate that arrives a frame late or leaves a frame early only shows in
# the sequence.
#
# WHY THERE IS A STAGING COPY. The plates reach for two singletons that
# import Quickshell — `Bus` (it runs the bridge child through
# Quickshell.Io) and `Motion` (it reads one environment variable through
# Quickshell.env) — and quickshell links its QML plugin into its own
# binary, so no other engine can resolve either. QML resolves a singleton
# through the directory's qmldir, so the only way to substitute one is to
# be that directory. Everything else in the stage is a verbatim copy:
# every plate, every core/ element, the generated Theme and qmldir.
#
# WHAT THIS IS NOT. Not the compositor: layer-shell, the empty input mask,
# the zero exclusive zone and the three monitors are shell.qml's, and a
# human at the machine is still the only thing that can confirm them. This
# is the CONTENT of one surface, which is the part five blocked plan items
# (A13, A21, A22, A25, A27) are actually asking about.
set -euo pipefail

root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
out="${1:-$root/docs/hud}"

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
# The comparator that reads the sheet back (B52). Pinned like everything
# else here rather than borrowed from the machine's PATH: this script
# already refuses to render in whatever fonts happen to be installed, and
# the same argument applies to the thing that grades what it rendered.
python=$(nixpkgs python3)
sans=$(nix build "$root#archivo" --no-link --print-out-paths)

stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT

# The shell, verbatim…
cp -r "$root/shell/jv-hud/." "$stage/"
rm -rf "$stage/tests"
# shell.qml is the Quickshell half — ShellRoot, PanelWindow, the layer-shell
# bindings — and none of it can resolve here. It is linted where it belongs,
# in the jv-hud build, against quickshell's own qml import path; leaving it
# in the stage would only mean linting it against an import it cannot have.
rm -f "$stage/shell.qml"
# …with the two Quickshell-bound singletons replaced, and nothing else.
cp "$root/tools/hudshots/stub/Bus.qml" "$stage/Bus.qml"
cp "$root/tools/hudshots/stub/Motion.qml" "$stage/Motion.qml"
# The drivers sit in a subdirectory with no qmldir of its own, so the
# recordings and the shared corner next to them resolve by plain directory
# import — the same shape shell/jv-hud/tests uses, and the same generated
# file. Both drivers run: tst_shots.qml writes the contact sheet, and
# tst_sequence.qml asserts the corner's trajectory across a whole recorded
# turn (A54) — which plates go up, in what order, at which second. It needs
# the same stage and nothing else, so it runs here rather than in a second
# copy of this assembly.
mkdir -p "$stage/shots"
cp "$root"/tools/hudshots/scene/*.qml "$stage/shots/"
# And the shared probe body (PLAN D38), which `warnprobe.qml` next to it
# instantiates. It lives in tools/qmlprobe because all three harnesses load
# their own scene the same way, and three copies of it would be three things
# to keep matching.
cp "$root/tools/qmlprobe/Probe.qml" "$stage/shots/"
cp "$root/shell/jv-hud/tests/Sessions.qml" "$stage/shots/"

# The faces theme.toml names, pinned rather than borrowed from whatever
# this machine happens to have installed: a sheet rendered in DejaVu would
# be a picture of a fallback. This proves the DECLARED look — that ares
# itself resolves these families is a different claim, and the one
# `jv-fonts-resolve` in system.checks makes (A19).
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
      echo "hudshots: \"$family\" resolves to \"$got\" — the sheet would be a picture of a fallback" >&2
      exit 1
      ;;
  esac
done

# The linter the jv-hud build runs, over the thing that will actually be
# rendered. The stubs, the shared corner and both drivers live outside
# shell/jv-hud, so this is the only place they are ever linted; without it
# they would be the one corner of the HUD with no gate on it.
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
  --stage "$stage" --rerun "bash ops/ralph/hudshots.sh"

mkdir -p "$out"
# The sheet's driver writes relative to the working directory: a QML test
# cannot read an environment variable, so this is how it is told where to
# look. The runner takes the whole directory, so both drivers run.
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
  --stage "$stage" --rerun "bash ops/ralph/hudshots.sh"

echo
echo "hudshots: wrote $(ls "$out"/*.png | wc -l) shots to $out"
echo

# And READ THEM BACK (B52). Until this line the sheet was thirteen pictures
# nothing ever opened: B51's first grading run painted the ember — the one
# accent §06 spends on nothing else — on every state that is not idle, and all
# thirteen photographs, all fifteen driver assertions and all 585 QML tests
# came back unchanged. A45 made the shots byte-reproducible, so the expected
# bytes already exist; the only real question was where "expected" lives, and
# the answer has to be git. A run that renders INTO docs/hud and compares
# against docs/hud has compared a file to itself, so both paths — the grading
# run that renders into a scratch directory and the refresh run that renders
# over the sheet — are checked against the last COMMITTED sheet.
#
# Which means a deliberate HUD change ends here, nonzero, naming the shots
# that moved and the pixels that moved in them. That is the report, not a
# failure: the new PNGs are on disk, and committing them is the refresh.
"$python/bin/python3" "$root/tools/hudsheet.py" --root "$root" --out "$out"
