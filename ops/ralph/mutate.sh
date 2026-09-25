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
#   --runner tests  <service>  runtests.sh    · .py   (the default)
#   --runner qml    hud        qmltest.sh     · .qml  · shell/jv-hud/core/ ONLY
#   --runner qml    bar        bartest.sh     · .qml  · shell/jv-bar/core/ ONLY
#   --runner qml    notify     notifytest.sh  · .qml  · shell/jv-notify/core/ ONLY
#   --runner cargo  <crate>    cargotest.sh   · .rs
#   --runner shots  hud        hudshots.sh    · .qml  · the PLATES (~53 s a run)
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
# WHICH SHELL (PLAN D11). There are three QML shells now and three scripts to
# run them, one each — three rather than one with an argument because
# `tools/verify.py` runs a gate by its command string and derives which gate
# to run from what you touched, so one script pointed at three trees would
# send a toast's change to the HUD's tests. `--runner qml` therefore names a
# LANGUAGE and the target names the SUITE. Until this landed it named the
# HUD's suite and nothing else, so a canary in `shell/jv-bar/core` lived, the
# harness refused the file, and the hint blamed the plates: the bar's and the
# notifier's mutations could only be driven by hand. A mutation in a shell the
# chosen suite is not pointed at is now refused before any suite runs, naming
# the one that would grade it.
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
# WHEN A CANARY LIVES, IT MAY BE THE GATE AND NOT THE TESTS (B58). A file the
# suite never touches and a file the suite imports from ANOTHER COPY look
# identical from inside a suite run — and until d55348b every jv-* suite
# imported `jarvis_bus` from the nix store while importing its own package
# from the worktree. So a Python file that survives every control is not just
# refused: the harness asks `runtests.sh --origin <module> <service>` where
# that suite really imports it from, and the abort says SHADOWED and names the
# other copy, or says the copy is right, or (no answer) says nothing.
#
# BEING KILLED PUTS THE TREE BACK (B71). The restore is a `finally`, and a
# `finally` is code: SIGTERM's default action ends the process without running
# any, so a timeout or a Ctrl-C used to leave the worktree holding whichever
# mutation was in flight — and the next run said "the baseline suite is RED
# before any mutation", which is true and points at nothing. Two halves now:
# INT/TERM/HUP are trapped and unwind through the ordinary restore (one-shot,
# so a second Ctrl-C cannot interrupt the restore the first one asked for);
# and every mutant write is preceded by a note in this worktree's git
# directory saying what was overwritten and with what, which is what covers
# SIGKILL and a power cut. The next run reads that note FIRST, before it reads
# a single original, and either puts the file back and says RECOVERED, or —
# if the file is now neither the mutant nor the original, i.e. somebody has
# edited it since — refuses and tells you where the original text is kept.
#
# Exit: 0 every mutation caught · 1 a mutation survived · 2 the harness
# cannot make an honest claim (red baseline, a file that survived every canary
# it was offered — so the suite neither runs nor reads it — a bad spec, a tree
# still red after the last restore, a killed run).
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
