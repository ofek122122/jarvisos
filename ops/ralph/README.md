# Ralph loop — operator guide

An autonomous builder that runs for days on branch `ralph/auto`, building JarvisOS
(UI/UX first) one small, verified, committed slice per iteration. It NEVER touches
`main`, NEVER switches the running system, and NEVER touches the forbidden areas
(see `GUARDRAILS.md`). It reads its memory from this directory every iteration.

## Files
- `GUARDRAILS.md` — absolute rules. Read by the loop every iteration.
- `PROMPT.md` — the standing prompt the loop re-runs each iteration.
- `PLAN.md` — prioritized backlog; the loop marks items done and adds follow-ups.
- `JOURNAL.md` — append-only log of every successful iteration.
- `updates.sh` — "stop and give me updates" — the delta reporter.

## One-time setup (isolated worktree on its own branch)
From your normal checkout (`~/jarvisos`, on `main`, clean):
```
git branch ralph/auto                    # create the loop's branch off main
git worktree add ~/jarvisos-ralph ralph/auto
git tag ralph-report-mark ralph/auto     # baseline for updates.sh
```
The loop runs **inside `~/jarvisos-ralph`**. Your `~/jarvisos` stays yours.

## Launch — auto-restarting service (survives crashes + reboots)
The `ralph-loop` plugin runs as a Stop hook INSIDE one long-lived `claude`
session. The `ralph-loop` systemd USER service keeps that session alive in tmux
and resumes it with `claude --continue` whenever it dies.

One-time install:
```
mkdir -p ~/.config/systemd/user
ln -sf ~/jarvisos/ops/ralph/ralph-loop.service ~/.config/systemd/user/ralph-loop.service
systemctl --user daemon-reload
systemctl --user enable --now ralph-loop.service
loginctl enable-linger "$USER"     # keep running while logged out / after reboot
```
Then arm the loop ONCE:
```
tmux attach -t ralph
# at the claude prompt, paste:
#   /ralph-loop Read ops/ralph/PROMPT.md in full and follow it exactly for ONE iteration then stop. Working dir is this repo on branch ralph/auto. Obey ops/ralph/GUARDRAILS.md absolutely.
# detach without stopping it: Ctrl-b then d
```
After that it's hands-off: on crash/OOM/reboot the service relaunches and
`--continue` resumes the armed loop automatically (the loop's state file
persists on disk). Watch anytime with `tmux attach -t ralph` or `updates.sh`.

Stop for good:
```
systemctl --user disable --now ralph-loop.service
tmux kill-session -t ralph
```

## "Stop and give me updates" (loop keeps running)
From either checkout, any time:
```
bash ops/ralph/updates.sh          # what changed since you last asked; advances the mark
bash ops/ralph/updates.sh --peek   # same, but don't advance (re-read the same window)
```

## Merging the loop's work into main (you, deliberately)
Review `git log main..ralph/auto`, build it yourself, then merge when happy:
```
cd ~/jarvisos && git checkout main
git merge --no-ff ralph/auto
nixos-rebuild build --flake .#ares   # review, then test, then switch — your call
```

## If it goes wrong
- Stop the loop (Ctrl-C its terminal / stop its unit). `main` is untouched and
  your live system was never switched — nothing to recover on the OS side.
- Bad commits live only on `ralph/auto`; delete or reset the branch and relaunch.
