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
# The loop's work is mechanical and repetitive — read PLAN, write the failing
# test, write the code, run verify.sh, commit — across ~60 backlog items over
# days. That volume, not any single iteration, is what this run costs, so the
# model choice here dominates everything else. Sonnet does this class of work
# well; override with RALPH_MODEL=opus for a stretch of genuinely hard items.
MODEL="${RALPH_MODEL:-sonnet}"
# A systemd user service inherits no locale, so Qt prints a four-line "locale C
# is not UTF-8" warning per invocation. `export LANG` here does NOT silence it —
# the QML gates run inside nix build sandboxes, which scrub the environment, so
# the setting cannot reach them (tried in 328daec; the warnings kept coming).
# Silencing it properly means touching the derivations for a cosmetic, so
# instead the noise is filtered out of the tail below, which is the only thing
# it was actually hurting: the 50-line window into an iteration that dies.
export LANG=C.UTF-8   # harmless, and does fix the non-sandboxed callers

# THE NEVER-BACKGROUND RULE LIVES HERE, not only in PROMPT.md. Twice now an
# iteration has backgrounded its verify gate, said "waiting for nixtest.sh to
# complete", ended its turn, and died holding finished work (iteration 3 of the
# first run, iteration 8 of the third). PROMPT.md STEP 3 already forbids it and
# that was not enough: a headless agent's own harness tells it backgrounded work
# re-invokes it automatically, which is true interactively and FALSE under -p.
# A rule in a file it reads loses to an affordance in the prompt it runs under,
# so the rule goes in the prompt it runs under.
BOOTSTRAP='Read ops/ralph/PROMPT.md in full and follow it exactly for ONE iteration, then stop. Working directory is this repository, on branch ralph/auto. Obey ops/ralph/GUARDRAILS.md absolutely. The repo is your only memory between iterations.

CRITICAL, AND IT OVERRIDES YOUR INSTINCTS: you are `claude -p`. Your turn ending IS your process being killed. There is no background-task notification, no re-invocation, no next turn — whatever your harness normally tells you about backgrounded work does not apply here. NEVER pass run_in_background, never say "waiting for X to complete", never end your turn expecting to be woken. Run every command — including ops/ralph/verify.sh and nixos-rebuild build, which legitimately take several minutes each — in the FOREGROUND, and sit blocked on the exit code inside this one turn. Minutes of silence while a gate runs is correct and expected. Two previous iterations died exactly this way and their finished work was orphaned.'

cd "$WT" || { echo "ralph: worktree $WT missing — run the one-time setup"; exit 1; }
[ -x "$CLAUDE" ] || { echo "ralph: claude not found"; exit 1; }

echo "ralph: loop starting in $WT on $(git rev-parse --abbrev-ref HEAD 2>/dev/null) [model: $MODEL]"
i=0
while :; do
  if [ -f "$STOP" ]; then
    echo "ralph: STOP file present ($STOP) — exiting cleanly. Remove it and restart to resume."
    exit 0
  fi
  # EVERY ITERATION STARTS CLEAN. An iteration that dies mid-work — killed,
  # out of tokens, or ending its turn while something was still running —
  # leaves files behind that the NEXT fresh agent did not write and cannot
  # account for. It would read a JOURNAL saying "F3 not started", find F3
  # half-built in the tree, and either commit code it never verified or waste
  # the iteration confused. So: salvage anything dirty into a stash (never
  # discard it — it may be good work, and `git stash list` keeps it reachable)
  # and hand the agent the clean tree its prompt assumes.
  if [ -n "$(git status --porcelain)" ]; then
    echo "ralph: WARNING — dirty tree at iteration start; the previous iteration"
    echo "ralph: did not finish. Salvaging to a stash so this one starts clean:"
    git status --short | sed 's/^/ralph:   /'
    git stash push -u -m "salvage: orphaned work from a died iteration $(date -u +%FT%TZ)" \
      && echo "ralph: salvaged — recover with 'git stash list' / 'git stash show -p stash@{0}'" \
      || echo "ralph: ERROR — could not stash; continuing anyway, the tree is NOT clean"
  fi

  i=$((i + 1))
  echo "=========== ralph iteration $i @ $(date -u +%FT%TZ) ==========="
  # A fresh, autonomous, headless agent iteration. Its own verify gate + commit
  # + push live in PROMPT.md; guardrails keep it on ralph/auto and off the OS.
  # The grep strips Qt's unsilenceable locale warning (see the LANG comment
  # above) so the 50 lines kept are 50 lines of the agent, not of boilerplate.
  "$CLAUDE" -p --model "$MODEL" --dangerously-skip-permissions "$BOOTSTRAP" 2>&1 \
    | grep -vE "Detected locale|Qt depends on a UTF-8 locale|If this causes problems, reconfigure|for more information\.$" \
    | tail -50 || true
  echo "=========== ralph iteration $i complete ==========="
  sleep 10   # a breather; also throttles a tight failure loop
done
