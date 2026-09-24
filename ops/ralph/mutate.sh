#!/usr/bin/env bash
# ops/ralph/mutate.sh [--runner tests|qml|cargo] <target> [spec] — grade a set
# of mutations against a suite, with the three controls the loop's hand-run
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
#   --runner qml    hud        qmltest.sh    · .qml
#   --runner cargo  <crate>    cargotest.sh  · .rs
#
# NOTE (B49, measured): `--runner qml` grades shell/jv-hud/core/ ONLY. The
# canary LIVES on every top-level plate — qmltest.sh imports "../core" and
# never a plate — so the harness refuses those rather than grading them
# immune. The plates are exercised by ops/ralph/hudshots.sh, which is not yet
# a runner here; see PLAN B51.
#
# Exit: 0 every mutation caught · 1 a mutation survived · 2 the harness
# cannot make an honest claim (red baseline, a canary that lived, a bad spec,
# the wrong grader for the file, a tree still red after the last restore).
set -euo pipefail
root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
exec python3 "$root/tools/mutate.py" "$@"
