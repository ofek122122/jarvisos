#!/usr/bin/env bash
# ops/ralph/bartest.sh — run the BAR's headless QML tests against the WORKTREE.
#
# The sibling of qmltest.sh, which does the same for the HUD. Two scripts
# rather than one with an argument, because `tools/verify.py` runs a gate by
# its command string and derives which gates to run from what you touched:
# one script pointed at two trees would be one command, and touching a bar
# element would have run the HUD's tests instead of the bar's.
#
# Same tests the jv-bar build runs in its checkPhase; this is the INNER loop,
# not the gate — `nix build .#jv-bar` is the gate.
#
# Nothing here needs a compositor or a running niri: the tests exercise
# shell/jv-bar/core, which is pure QtQuick on purpose, driven with the lines
# `niri msg --json event-stream` really writes (harness/fixtures/niri). The
# Quickshell half (Niri.qml, the child process) cannot be tested this way at
# all — quickshell links its QML plugin into its own binary, so no other QML
# engine can import it.
set -euo pipefail

root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
qtdecl=$(nix eval --raw --impure --expr \
  "(builtins.getFlake (toString $root)).inputs.nixpkgs.legacyPackages.\${builtins.currentSystem}.qt6.qtdeclarative.outPath")

export QT_QPA_PLATFORM=offscreen
exec "$qtdecl/bin/qmltestrunner" \
  -input "$root/shell/jv-bar/tests" \
  -import "$qtdecl/lib/qt-6/qml" \
  "$@"
