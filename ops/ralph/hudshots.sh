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

mkdir -p "$out"
# The sheet's driver writes relative to the working directory: a QML test
# cannot read an environment variable, so this is how it is told where to
# look. The runner takes the whole directory, so both drivers run.
cd "$out"
export QT_QPA_PLATFORM=offscreen
export HOME="$stage"
"$qtdecl/bin/qmltestrunner" \
  -input "$stage/shots" \
  -import "$qtdecl/lib/qt-6/qml"

echo
echo "hudshots: wrote $(ls "$out"/*.png | wc -l) shots to $out"
