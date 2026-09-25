#!/usr/bin/env bash
# ops/ralph/verify.sh — the test gate. Runs EVERY suite and gate that reads
# what you changed, and exits non-zero if any of them is red (PLAN B70).
#
# The siblings are inner loops: runtests.sh (one Python suite), cargotest.sh
# (one crate), qmltest.sh / hudshots.sh (the HUD), nixtest.sh (module options).
# This is the outer one, and the difference is that you do not choose what it
# runs — `tools/dependents.py` derives that from what the worktree says you
# touched, so "which suite is relevant" stops being a guess made fresh each
# iteration by someone who cannot see the readers (B68, B69).
#
# Usage:  bash ops/ralph/verify.sh                 # the uncommitted tree
#         bash ops/ralph/verify.sh --list          # the plan and its price
#         bash ops/ralph/verify.sh --since HEAD~1  # what a commit took
#         bash ops/ralph/verify.sh path/one ...    # plus paths you name
#
# Exit: 0 green, 1 at least one gate red, 2 nothing to verify.
#
# This is not the WHOLE gate. `nixos-rebuild build --flake .#ares` is not a
# test suite derived from a path and is still run beside this — see PROMPT.md
# STEP 3.
set -euo pipefail

root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
exec python3 "$root/tools/verify.py" --root "$root" "$@"
