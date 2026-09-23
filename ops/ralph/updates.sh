#!/usr/bin/env bash
# ops/ralph/updates.sh — "stop and give me updates".
# Reports every commit + journal entry the loop produced on branch ralph/auto
# SINCE THE LAST TIME YOU RAN THIS, then advances the mark. The loop keeps
# running the whole time — this is read-only except for moving one git tag.
#
# Usage:  bash ops/ralph/updates.sh            # show delta since last ask, then re-mark
#         bash ops/ralph/updates.sh --peek     # show delta but DON'T move the mark
set -euo pipefail

BRANCH="ralph/auto"
MARK="ralph-report-mark"
peek=0
[ "${1:-}" = "--peek" ] && peek=1

cd "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"

if ! git rev-parse --verify --quiet "$BRANCH" >/dev/null; then
  echo "branch $BRANCH does not exist yet — the loop hasn't started."; exit 0
fi
git fetch -q origin "$BRANCH" 2>/dev/null || true

# Baseline: the mark, or the branch point if we've never reported.
if git rev-parse --verify --quiet "$MARK" >/dev/null; then
  base="$MARK"
else
  base="$(git merge-base main "$BRANCH" 2>/dev/null || git rev-list --max-parents=0 "$BRANCH" | tail -1)"
fi
tip="$(git rev-parse "$BRANCH")"

echo "==================================================================="
echo " JarvisOS — Ralph loop updates since your last check"
echo " range: ${base:0:9}..${tip:0:9}   branch: $BRANCH"
echo "==================================================================="

n=$(git rev-list --count "$base..$tip" 2>/dev/null || echo 0)
if [ "$n" = "0" ]; then
  echo; echo "No new commits since last time. (Loop may be mid-iteration or stuck —"
  echo "check the loop's terminal / systemd log if this persists.)"; exit 0
fi

echo; echo "### $n commit(s):"
git log --no-merges --pretty='  %h  %ad  %s' --date=format:'%m-%d %H:%M' "$base..$tip"

echo; echo "### files changed:"
git diff --stat "$base..$tip" | tail -40

echo; echo "### new JOURNAL entries:"
git diff "$base..$tip" -- ops/ralph/JOURNAL.md | grep '^+' | grep -v '^+++' | sed 's/^+//' || true

echo; echo "### PLAN status now:"
grep -E '^\- \[[ x]\]' ops/ralph/PLAN.md | sed 's/^/  /' | head -40

if [ "$peek" = "0" ]; then
  git tag -f "$MARK" "$tip" >/dev/null
  echo; echo "(mark advanced to ${tip:0:9} — next run reports only what comes after this.)"
else
  echo; echo "(--peek: mark left where it was.)"
fi
