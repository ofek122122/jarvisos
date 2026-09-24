#!/usr/bin/env bash
# ops/ralph/qmltest.sh — run the HUD's headless QML tests against the WORKTREE.
#
# The sibling of runtests.sh (Python) and cargotest.sh (Rust). Same tests the
# jv-hud build runs in its checkPhase; this is the INNER loop, not the gate —
# `nix build .#jv-hud` is the gate.
#
# Nothing here needs a compositor or a bus: the tests exercise BusModel.qml,
# which is pure QtQuick on purpose. The Quickshell half (Bus.qml, the bridge
# process) cannot be tested this way at all — quickshell links its QML plugin
# into its own binary, so no other QML engine can import it.
set -euo pipefail

root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
qtdecl=$(nix eval --raw --impure --expr \
  "(builtins.getFlake (toString $root)).inputs.nixpkgs.legacyPackages.\${builtins.currentSystem}.qt6.qtdeclarative.outPath")

export QT_QPA_PLATFORM=offscreen
exec "$qtdecl/bin/qmltestrunner" \
  -input "$root/shell/jv-hud/tests" \
  -import "$qtdecl/lib/qt-6/qml" \
  "$@"
