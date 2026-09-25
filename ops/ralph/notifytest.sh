#!/usr/bin/env bash
# ops/ralph/notifytest.sh — run the NOTIFIER's headless QML tests against the
# WORKTREE.
#
# The third of its kind: `qmltest.sh` does this for the HUD, `bartest.sh` for
# the bar, and each shell gets its own script rather than one with an argument.
# That is not duplication for its own sake — `tools/verify.py` runs a gate by
# its command string and derives which gates to run from what you touched, so
# one script pointed at three trees would be one command, and editing a toast
# would run the HUD's tests instead of the notifier's.
#
# Same tests the jv-notify build runs in its checkPhase; this is the INNER
# loop, not the gate — `nix build .#jv-notify` is the gate.
#
# Nothing here needs a compositor or a D-Bus session: the tests exercise
# shell/jv-notify/core, which is pure QtQuick on purpose, with the monotonic
# clock injected so time is wound by hand. The Quickshell half
# (Notifications.qml, the org.freedesktop.Notifications server itself) cannot
# be tested this way at all — quickshell links its QML plugin into its own
# binary, so no other QML engine can import it.
set -euo pipefail

root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
qtdecl=$(nix eval --raw --impure --expr \
  "(builtins.getFlake (toString $root)).inputs.nixpkgs.legacyPackages.\${builtins.currentSystem}.qt6.qtdeclarative.outPath")

export QT_QPA_PLATFORM=offscreen
exec "$qtdecl/bin/qmltestrunner" \
  -input "$root/shell/jv-notify/tests" \
  -import "$qtdecl/lib/qt-6/qml" \
  "$@"
