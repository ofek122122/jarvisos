#!/usr/bin/env bash
# ops/ralph/loop-run.sh — supervisor for the autonomous Ralph loop.
#
# Runs as the ExecStart of the `ralph-loop` systemd USER service. Keeps a tmux
# session running `claude` (armed with the ralph-loop Stop hook) alive on branch
# ralph/auto in the isolated worktree. When claude exits — crash, OOM, reboot —
# this script exits and systemd (Restart=always) relaunches it; on relaunch it
# RESUMES the same session with `claude --continue`, so the loop picks up on its
# own with no human. The loop's state file persists on disk across reboots.
#
# This script lives on the STABLE main checkout (the loop never touches main),
# but operates on the worktree. It never uses sudo and can never switch the OS.
set -euo pipefail

WT="$HOME/jarvisos-ralph"                     # the loop's isolated worktree
SES="ralph"
TMUX="/run/current-system/sw/bin/tmux"
CLAUDE="/run/current-system/sw/bin/claude"
STATE="$WT/.claude/ralph-loop.local.md"
PERM="--dangerously-skip-permissions"          # unattended: no interactive prompts

[ -d "$WT" ]      || { echo "ralph: worktree $WT missing — run the one-time setup"; exit 1; }
[ -x "$TMUX" ]    || { echo "ralph: tmux not found (rebuild with pkgs.tmux)"; exit 1; }
[ -x "$CLAUDE" ]  || { echo "ralph: claude not found on PATH"; exit 1; }

if ! "$TMUX" has-session -t "$SES" 2>/dev/null; then
  if grep -q '^active: true' "$STATE" 2>/dev/null; then
    # A loop was already armed — resume it (self-continues via the Stop hook).
    cmd="$CLAUDE --continue $PERM"
    echo "ralph: resuming armed loop with --continue"
  else
    # No loop armed yet — start a bare session; attach once and run /ralph-loop.
    cmd="$CLAUDE $PERM"
    echo "ralph: no active loop; starting bare claude (attach and run /ralph-loop once)"
  fi
  # claude IS the session's main process: when it exits, the session ends.
  "$TMUX" new-session -d -s "$SES" -c "$WT" "$cmd"
fi

# Block while the loop lives; exit non-zero when it dies so systemd restarts us.
while "$TMUX" has-session -t "$SES" 2>/dev/null; do
  sleep 20
done
echo "ralph: session ended — exiting for systemd restart (will --continue)"
exit 1
