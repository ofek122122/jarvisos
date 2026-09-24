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
# THE FILE THE SUITE READS AND NEVER RUNS (B55). Invariant 1 forbids one
# service importing another, so every claim this repo makes about a relation
# BETWEEN two of them is made by matching a line in the other's source —
# jv-compat's copy of jv-guard's scan budget, the HUD's fallback budgets
# against jv-ears', LinkPlate's grace against the two reconnect cadences. The
# canary that proves EXECUTION lives on all of them, and the harness used to
# abort. Each file is now offered its controls strongest first — unloadable,
# then ERASED — and whichever kills the suite is the relation the summary
# reports: "the suite reads <file> — it never runs it", under which a survivor
# means "no test matches that text", NOT "the tests never load this file".
# That also means the runner and the file need not share a language: the tools
# suite really does match a line in shell/jv-hud/Bus.qml, so an off-language
# file is graded (with the erasure canary only) rather than refused. Cost: one
# extra suite run per file the suite merely reads, which is why the printed
# count says "at least".
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
# cannot make an honest claim (red baseline, a file that survived every canary
# it was offered — so the suite neither runs nor reads it — a bad spec, a tree
# still red after the last restore).
#
# WHERE THE OUTPUT WENT (B56). One line of each suite run is printed, prefixed
# with the run it came from (run003). The WHOLE of it is in that run's own
# scratch directory as suite.log, and the run tree is KEPT whenever a mutation
# survived or the harness aborted — the path is in the abort, or printed under
# the summary. INDEX at the top names every run (baseline, canary <file>,
# mutation: <label>, closing baseline) and whether its suite passed. Nothing is
# kept when every mutation was caught. Delete a kept tree when you are done;
# it is in /tmp and under --runner shots it holds every PNG each run drew,
# which is the one way to SEE what a surviving plate mutation looked like.
#
# A RED BASELINE UNDER --runner shots IS USUALLY THE SHEET (B53). hudshots.sh
# compares every PNG it renders against HEAD:docs/hud, so an uncommitted change
# to a plate makes the baseline red with nothing wrong with the suite. The abort
# names the plates that differ from HEAD and tells you the fix: run
# `bash ops/ralph/hudshots.sh`, LOOK at the new PNGs, commit them, then grade.
set -euo pipefail
root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
exec python3 "$root/tools/mutate.py" "$@"
