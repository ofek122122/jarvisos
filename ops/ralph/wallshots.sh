#!/usr/bin/env bash
# ops/ralph/wallshots.sh — photograph the animated wallpaper (PLAN E8).
#
# The fourth of these, after `hudshots.sh`, `notifyshots.sh` and `barshots.sh`,
# and a separate script for the same reason each of those is: `tools/verify.py`
# runs a gate by its command string and derives which gates to run from what you
# touched, so one script pointed at four shells would be one command, and
# editing a toast would rebuild the wallpaper's sheet as well.
#
# Writes docs/wall/*.png: the real field, over the real art
# pkgs/jarvis-wallpaper rasterizes from the SVG in this repo, with the real
# generated Theme deciding the ember and the real generated Motion deciding
# whether it moves at all. Run it after any change to shell/jv-wall or to the
# art and commit the diff — a desktop whose look changed and whose sheet did not
# is a desktop nobody looked at.
#
# WHY THIS SHELL NEEDED A SHEET, AND WHY IT IS THE LAST TO GET ONE. It is 6.5
# megapixels under every window on the machine, and nothing in this repo had
# ever looked at it: `nix build .#jv-wall` runs qmllint over it and
# `shellload.sh` proves it loads, and neither can say where the comet is. What
# held the sheet up is that this is the only one of the four surfaces whose
# subject is a PHASE rather than a state. The other three reach a state by
# feeding a model and waiting for it to settle; a wallpaper never arrives
# anywhere, and `wait(14000)` is a different picture on every machine. So the
# shell was given ONE number to move — see the paragraph above `phaseMs` in
# shell/jv-wall/shell.qml — and every shot on this sheet is that number, set.
# Nothing here waits for an animation, which is why the same pixels come out on
# any machine.
#
# WHAT THE SHEET IS EVIDENCE ABOUT, since most of its pixels belong to another
# package. Not the art: that is reproducible from pkgs/jarvis-wallpaper's own
# SVG and is the same file the running desktop shows. It is what the shell puts
# OVER the art and WHERE — which of the per-output renders each geometry
# resolves (a picture cannot tell a bespoke render from the primary art scaled;
# both are a picture of the same drawing), that the comet's head rides the
# instrument's outer ring at every geometry including the ones the art is not
# composed for, and that the 96 s lap takes the head off the bottom of the
# screen for about a third of it. All of those are properties of a laid-out
# surface at a real monitor size, and all of them were unmeasured.
#
# It then READS THE SHEET BACK, exactly as the other three do (B52): every PNG
# it just rendered, compared against the one committed at HEAD, by
# tools/hudsheet.py. A run whose field drew something else ends nonzero, naming
# the shots that moved and three of the pixels that moved in them. If the change
# was yours, that is the refresh telling you what you changed — look at the new
# PNGs, commit them, and the next run is green.
#
# WHY THERE IS A STAGING COPY. One file in this shell imports Quickshell and
# cannot be loaded by any other engine, because quickshell links its QML plugin
# into its own binary: `Motion` (it reads one environment variable through
# Quickshell.env). QML resolves a singleton through the directory's qmldir, so
# the only way to substitute one is to BE that directory. Everything else in the
# stage is a verbatim copy: the generated Theme and Ease, core/, the qmldir.
#
# WHAT THIS IS NOT. Not the compositor: the BACKGROUND layer, the empty input
# mask, `ExclusionMode.Ignore`, `WlrKeyboardFocus.None` and the
# one-surface-per-monitor `Variants` are shell.qml's, and a human at the machine
# is still the only thing that can confirm them. Not the frame budget either —
# §06's < 2 ms/frame and 0 fps when idle are measurements a compositor takes
# (PLAN E6), not pictures. This is the CONTENT of one surface.
set -euo pipefail

root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
out="${1:-$root/docs/wall}"

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
# THE ART, which is most of every shot on this sheet. Built rather than assumed:
# it is rasterized from an SVG by resvg at build time out of the same
# personality/theme.toml the generated Theme comes from, so a palette change
# moves the art and the ember over it together and this sheet is the only place
# the two are ever seen in the same pixel.
art=$(nix build "$root#jarvis-wallpaper" --no-link --print-out-paths)

stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT

# The shell, verbatim…
cp -r "$root/shell/jv-wall/." "$stage/"
# shell.qml is the Quickshell half — ShellRoot, Variants, PanelWindow, the
# layer-shell bindings, `Quickshell.screens`, `Quickshell.env` — and none of it
# can resolve here. It is linted where it belongs, in the jv-wall build, against
# quickshell's own qml import path; leaving it in the stage would only mean
# linting it against an import it cannot have. The surface inside it is staged as
# tools/wallshots/scene/Field.qml, and a test holds the two to the same
# composition.
rm -f "$stage/shell.qml"
# …with the one Quickshell-bound singleton replaced, and nothing else. It is
# registered in the shell's own qmldir, which is copied above unchanged — so
# `Motion` resolves here to this file by being in this directory, and a stage
# missing it would not fall back, it would fail to load.
cp "$root/tools/wallshots/stub/Motion.qml" "$stage/Motion.qml"
# The driver sits in a subdirectory with no qmldir of its own, so the staged
# shell next to it resolves by plain directory import (`import ".."`) — the same
# shape the other three harnesses use.
mkdir -p "$stage/shots"
cp "$root"/tools/wallshots/scene/*.qml "$stage/shots/"
# And the shared probe body (PLAN D38), which `warnprobe.qml` next to it
# instantiates. It lives in tools/qmlprobe because all four harnesses load their
# own scene the same way, and four copies of it would be four things to keep
# matching.
cp "$root/tools/qmlprobe/Probe.qml" "$stage/shots/"
# THE ART, at a path the driver can name. A QML test cannot read an environment
# variable — which is how the running shell is told, by `--set JV_WALL_DIR` in
# the wrapper — and the only absolute path a QML file knows is its own. So the
# store path is linked in beside the stage at a fixed name and the driver
# resolves it with `Qt.resolvedUrl("../art")`.
ln -s "$art/share/backgrounds" "$stage/art"

# The faces theme.toml names, pinned rather than borrowed from whatever this
# machine happens to have installed: a sheet rendered in DejaVu would be a
# picture of a fallback. Nothing this shell draws is type — the wordmark in the
# art is resvg's, set at build time, and pkgs/jarvis-wallpaper refuses a render
# whose face did not resolve — so this is here for the same reason the other
# three harnesses have it: the stage is a whole shell, and the next element
# anybody adds to this surface should not be the one that discovers it.
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
      echo "wallshots: \"$family\" resolves to \"$got\" — the sheet would be a picture of a fallback" >&2
      exit 1
      ;;
  esac
done

# The linter the jv-wall build runs, over the thing that will actually be
# rendered. The stub, the staged field and the driver live outside
# shell/jv-wall, so this is the only place they are ever linted; without it they
# would be the one corner of this shell with no gate on it.
"$qtdecl/bin/qmllint" -W 0 --uncreatable-type disable \
  -I "$qtdecl/lib/qt-6/qml" \
  $(find "$stage" -name '*.qml' | sort)

# THE SECOND ENGINE (PLAN D38). qmltestrunner drops every message logged while
# no test function is RUNNING, and the first driver in a directory has its whole
# scene built before the run begins — so a `console.warn` in
# `Component.onCompleted`, and every error thrown by a binding evaluated as that
# scene is built, never reach the log the scanner below reads. Measured, with
# two identical drivers in one directory: only the second one is heard.
#
# It matters more in this harness than in the other three, because here the
# first driver is the ONLY driver: `tst_shots.qml` is the whole sheet, so
# without this pass nothing would read what the scene said while it was being
# built. And what it probes is a state no shot is a picture of — the wallpaper
# with `JV_WALL_DIR` unset, where the per-output Image fails, the fallback fails
# after it, and the surface has to become transparent without a binding throwing
# on the way.
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
  --stage "$stage" --rerun "bash ops/ralph/wallshots.sh"

mkdir -p "$out"
# The driver writes relative to the working directory: a QML test cannot read an
# environment variable, so this is how it is told where to put its files.
cd "$out"
export QT_QPA_PLATFORM=offscreen
export HOME="$stage"
# The runner, with its output CAPTURED as well as shown (PLAN D36). `tee` keeps
# every line on the terminal — a gate behind a silent pipe is indistinguishable
# from a hang — and the copy is read by `tools/qmlerrors.py`, which ends this
# run non-zero if anything in the scene THREW. That is not the same question as
# "did a test fail": a QML handler that throws keeps the value the property
# already had and recovers on the next evaluation, so the surface stays
# plausible, the shots come out byte-identical and the totals come out green.
log="$stage/runner.log"
"$qtdecl/bin/qmltestrunner" \
  -input "$stage/shots" \
  -import "$qtdecl/lib/qt-6/qml" 2>&1 | tee "$log"
"$python/bin/python3" "$root/tools/qmlerrors.py" "$log" \
  --stage "$stage" --rerun "bash ops/ralph/wallshots.sh"

echo
echo "wallshots: wrote $(ls "$out"/*.png | wc -l) shots to $out"
echo

# And READ THEM BACK (B52), against the last COMMITTED sheet — never against the
# directory this run just wrote into, which would be comparing a file to itself.
# A deliberate change to the wallpaper ends here, nonzero, naming the shots that
# moved and the pixels that moved in them. That is the report, not a failure:
# the new PNGs are on disk, and committing them is the refresh.
"$python/bin/python3" "$root/tools/hudsheet.py" \
  --root "$root" --out "$out" \
  --sheet docs/wall \
  --subject "the animated wallpaper" \
  --rerun "bash ops/ralph/wallshots.sh"
