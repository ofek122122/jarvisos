#!/usr/bin/env bash
# ops/ralph/loop-run.sh — the autonomous Ralph loop supervisor.
#
# "Ralph is a Bash loop": a while-true that feeds the SAME prompt to a FRESH
# headless `claude -p` each iteration. The repo is the only memory between
# iterations (git history + ops/ralph/{PLAN,JOURNAL}.md), exactly as PROMPT.md
# expects. No plugin needed — the plugin's Stop-hook only works in an interactive
# session where plugins load, which a systemd/headless context does not provide.
#
# Runs as ExecStart of the `ralph-loop` systemd USER service (Restart=on-failure,
# WantedBy=default.target + linger) so it survives crashes and reboots. It lives
# on the STABLE main checkout, operates on the isolated worktree, never uses sudo,
# and can never switch the OS.
#
# Watch:  journalctl --user -u ralph-loop -f   and   bash ops/ralph/updates.sh
# Pause:  touch ~/jarvisos-ralph/.ralph-STOP   (clean exit; `systemctl --user start` to resume)
# Stop:   systemctl --user stop ralph-loop.service
set -uo pipefail   # deliberately NOT -e: one failed iteration must not end the loop

WT="$HOME/jarvisos-ralph"
CLAUDE="/run/current-system/sw/bin/claude"
STOP="$WT/.ralph-STOP"
BOOTSTRAP='Read ops/ralph/PROMPT.md in full and follow it exactly for ONE iteration, then stop. Working directory is this repository, on branch ralph/auto. Obey ops/ralph/GUARDRAILS.md absolutely. The repo is your only memory between iterations.'

cd "$WT" || { echo "ralph: worktree $WT missing — run the one-time setup"; exit 1; }
[ -x "$CLAUDE" ] || { echo "ralph: claude not found"; exit 1; }

echo "ralph: loop starting in $WT on $(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
i=0
while :; do
  if [ -f "$STOP" ]; then
    echo "ralph: STOP file present ($STOP) — exiting cleanly. Remove it and restart to resume."
    exit 0
  fi
  i=$((i + 1))
  echo "=========== ralph iteration $i @ $(date -u +%FT%TZ) ==========="
  # A fresh, autonomous, headless agent iteration. Its own verify gate + commit
  # + push live in PROMPT.md; guardrails keep it on ralph/auto and off the OS.
  "$CLAUDE" -p --dangerously-skip-permissions "$BOOTSTRAP" 2>&1 | tail -50 || true
  echo "=========== ralph iteration $i complete ==========="
  sleep 10   # a breather; also throttles a tight failure loop
done
