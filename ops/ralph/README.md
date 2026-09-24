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

## Grading the tests themselves
Every journal entry claims a number like "six mutations, six caught" — the
loop's only evidence that the tests it just wrote have teeth. That claim is
produced by this, not by hand:
```
bash ops/ralph/mutate.sh jv-voice <<'EOF'
@ the inter-sentence gap widened
services/jv-voice/jv_voice/service.py
- TURN_GAP_S = 0.5
+ TURN_GAP_S = 0.9
EOF
```
It runs the suite clean (must be green), then with the target file made
impossible to load (must go RED — a suite that stays green does not execute
that file, so no mutation of it means anything), then once per mutation, then
clean again. Every run gets its own empty compiler cache and every write gets
an mtime newer than the clock, because both CPython (`.pyc`) and Qt (`.qmlc`)
validate a cached artifact against (mtime **in seconds**, size) and cargo asks
only whether a source is newer than what it built — so an equal-length edit is
otherwise graded without ever running. Exit 0 all caught, 1 a survivor, 2 the
harness will not make a claim. See `tools/mutate.py`.

Three languages (B49), each with its own canary:
```
bash ops/ralph/mutate.sh <service>              # .py   via runtests.sh
bash ops/ralph/mutate.sh --runner qml hud       # .qml  via qmltest.sh
bash ops/ralph/mutate.sh --runner cargo jarvisd # .rs   via cargotest.sh
```
`--runner qml` grades `shell/jv-hud/core/` only — measured, not assumed: the
canary LIVES on every top-level plate, because `qmltest.sh` imports `"../core"`
and never a plate. The harness refuses those rather than reporting them immune.
The Rust canary is the weakest of the three and says so in its docstring: a
`compile_error!` proves the file is compiled into the crate, not that a test
exercises it.

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
