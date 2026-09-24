#!/usr/bin/env bash
# ops/ralph/mutate.sh [--runner tests|qml|cargo|shots] <target> [spec] — grade a
# set of mutations against a suite, with the three controls the loop's hand-run
# practice never had (PLAN B48, B49): a canary that proves the suite EXECUTES
# the file being mutated, a private empty compiler cache per run so no suite
# can read stale artifacts for source that no longer exists, and an mtime on
# every write that is always newer than the clock. The logic, and the tests
# that hold it, live in tools/mutate.py — a shell script cannot be tested and
# this claim is the loop's evidence about its own tests.
#
# Usage:  bash ops/ralph/mutate.sh jv-voice <<'EOF'
#         @ the inter-sentence gap widened
#         services/jv-voice/jv_voice/service.py
#         - TURN_GAP_S = 0.5
#         + TURN_GAP_S = 0.9
#         EOF
#
#   --runner tests  <service>  runtests.sh   · .py   (the default)
#   --runner qml    hud        qmltest.sh    · .qml  · shell/jv-hud/core/ ONLY
#   --runner cargo  <crate>    cargotest.sh  · .rs
#   --runner shots  hud        hudshots.sh   · .qml  · the PLATES (~53 s a run)
#
# WHICH QML RUNNER (B49 measured it, B51 fixed it). `qmltest.sh` imports
# "../core" and never a top-level plate, so a canary on StatePlate.qml LIVES
# and `--runner qml` refuses it rather than grading it immune. The plates are
# exercised by `hudshots.sh`, which stages the whole shell and drives them
# through both harnesses — that is `--runner shots`, and it writes its PNGs
# into the run's own scratch so the committed contact sheet is never touched.
# It costs ~53 s a suite run against qmltest.sh's ~14 s, and the grading is
# one baseline + one canary per file + one per mutation + one baseline: the
# count is printed before the first run starts.
#
# Exit: 0 every mutation caught · 1 a mutation survived · 2 the harness
# cannot make an honest claim (red baseline, a canary that lived, a bad spec,
# the wrong grader for the file, a tree still red after the last restore).
set -euo pipefail
root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
exec python3 "$root/tools/mutate.py" "$@"
