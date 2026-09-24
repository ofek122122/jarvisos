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

## Test runners (the loop's inner loop)
The gate is always `nixos-rebuild build --flake .#ares`; these run the suites
against the WORKTREE source, fast, so a red/green loop does not rebuild the
world. One per language the repo actually has:
```
bash ops/ralph/runtests.sh jv-voice   # Python services (+ pylib, tools, harness)
bash ops/ralph/cargotest.sh jarvisd   # Rust crates
bash ops/ralph/qmltest.sh             # the HUD's QML, headless
bash ops/ralph/nixtest.sh             # the flake's own options -> the units ares gets
bash ops/ralph/hudscreens.sh          # the HUD photographed through a real compositor
```

## One-time setup (isolated worktree on its own branch)
From your normal checkout (`~/jarvisos`, on `main`, clean):
```
git branch ralph/auto                    # create the loop's branch off main
git worktree add ~/jarvisos-ralph ralph/auto
git tag ralph-report-mark ralph/auto     # baseline for updates.sh
```
The loop runs **inside `~/jarvisos-ralph`**. Your `~/jarvisos` stays yours.

## Launch (after installing the ralph loop plugin)
Run the loop in `~/jarvisos-ralph`, feeding it `ops/ralph/PROMPT.md` every
iteration with autonomous permissions. Keep it in tmux/systemd so it survives
disconnects. (Exact invocation depends on the installed plugin — the setup
session will finalize it.)

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
