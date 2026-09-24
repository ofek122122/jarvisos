#!/usr/bin/env bash
# ops/ralph/mutate.sh <service> [spec] — grade a set of mutations against a
# service's test suite, with the two controls the loop's hand-run practice
# never had: a canary that proves the suite EXECUTES the file being mutated,
# and a private, empty bytecode cache per run so no suite can read stale
# `.pyc` for source that no longer exists (PLAN B48). The logic, and the
# tests that hold it, live in tools/mutate.py — a shell script cannot be
# tested and this claim is the loop's evidence about its own tests.
#
# Usage:  bash ops/ralph/mutate.sh jv-voice <<'EOF'
#         @ the inter-sentence gap widened
#         services/jv-voice/jv_voice/service.py
#         - TURN_GAP_S = 0.5
#         + TURN_GAP_S = 0.9
#         EOF
#
# Exit: 0 every mutation caught · 1 a mutation survived · 2 the harness
# cannot make an honest claim (red baseline, a canary that lived, a bad spec).
set -euo pipefail
root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
exec python3 "$root/tools/mutate.py" "$@"
