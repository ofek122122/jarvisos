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

## The test gate
```
bash ops/ralph/verify.sh          # every suite and gate that reads what you changed
bash ops/ralph/verify.sh --list   # …and what that will cost, before you pay it
```
You do not choose what it runs: it asks the worktree what you touched, derives
the readers (below), runs all of them and exits non-zero if ANY is red. The
other half of the gate is `nixos-rebuild build --flake .#ares`, which is not a
suite derived from a path and is run beside it.

## Test runners (the loop's inner loop)
These run one suite each against the WORKTREE source, fast, so a red/green
loop does not rebuild the world. They are NOT the gate — `verify.sh` is, and
it calls them. One per language the repo actually has:
```
bash ops/ralph/runtests.sh jv-voice   # Python services (+ pylib, tools, harness)
bash ops/ralph/cargotest.sh jarvisd   # Rust crates
bash ops/ralph/qmltest.sh             # the HUD's QML, headless
bash ops/ralph/nixtest.sh             # the flake's own options -> the units ares gets
bash ops/ralph/hudscreens.sh          # the HUD photographed through a real compositor
```

## Which suites read what you changed
Invariant 1 forbids one service importing another, so every claim this repo
makes about a RELATION between two of its parts is made by a THIRD suite that
reads them both as source text — `tools` alone reads six services, the frozen
schemas, `personality/theme.toml` and every QML file in the HUD. "Run the
relevant suites" was therefore a guess, and three iterations in a row guessed
wrong and shipped a red `tools` (B65, B66, A71). So `runtests.sh` ends by
asking, every run:
```
python3 tools/dependents.py --changed     # or: <path> [<path> ...]
```
The map is derived from the suites themselves, never written down: a suite
reads what it NAMES (a `ROOT / "services" / "jv-compat"` expression, a
path-shaped string, an import — and everything that import imports), if what
it names exists. It is advice, not a verdict: the exit status stays pytest's,
and on a clean tree it prints nothing.

It reads the QML gates the same way (B69), which took a second rule because a
QML file names its subject by TYPE (`ReplyState {}`) and never by path — but a
type IS a file, found the way the engine finds it: the directories `import
"..."` puts on the path, and the `qmldir` those directories ship. So a change
to `shell/jv-hud/core/` names `qmltest.sh` AND `hudshots.sh` (through
`Corner` -> the plate -> the element), a change to a plate names the sheet
alone, and `tools/hudshots/stub/Bus.qml` — which no Python suite and no other
script opens — names the sheet too. WHERE that QML is assembled is the one
thing written down rather than derived: `hudshots.sh` stages a copy of the
shell with two singletons replaced, so `QML_GATES` in `tools/dependents.py`
holds that staging and `test_dependents.py` checks every directory of it
against the script itself. What is left unseen by the DERIVATION is Rust —
`jarvisd` and `jv-act` keep their tests inside the source they test, so there
is no third file naming a path — but the caveat's own sentence is a rule, and
`verify.sh` runs it: a changed file under a directory with a `Cargo.toml` is
that crate's `cargotest.sh`.

`verify.sh` (B70) is that notice with a verdict on it, because advice is what
had already failed. The price, measured: ten suites is 242 s and 60% of it is
jv-ears; a service change is that service plus `tools`, seconds; a HUD change
is about 80 s. Every step prints its own seconds so the figure can be
re-measured. Under the gate `runtests.sh` keeps its notice to itself
(`RALPH_GATE=1`) — it would otherwise urge the reader, once per step, to run
the suites the gate is running. What `verify.sh` still cannot plan is
`nixtest.sh` and `hudscreens.sh`: PLAN B72.

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

Four runners (B49, B51), each with its own canary:
```
bash ops/ralph/mutate.sh <service>              # .py   via runtests.sh
bash ops/ralph/mutate.sh --runner qml hud       # .qml  via qmltest.sh   (core/)
bash ops/ralph/mutate.sh --runner cargo jarvisd # .rs   via cargotest.sh
bash ops/ralph/mutate.sh --runner shots hud     # .qml  via hudshots.sh  (plates)
```
`--runner qml` grades `shell/jv-hud/core/` only — measured, not assumed: the
canary LIVES on every top-level plate, because `qmltest.sh` imports `"../core"`
and never a plate. The harness refuses those and names the runner that can:
`--runner shots` stages the whole shell the way `hudshots.sh` does and drives
the real plates, writing its PNGs into the run's own scratch so the committed
contact sheet in `docs/hud/` is never touched. It costs ~53 s a suite run
against qmltest.sh's ~14 s, so the run count (baseline + one canary per file +
one per mutation + baseline) is printed before the first one starts.
The Rust canary is the weakest of the four and says so in its docstring: a
`compile_error!` proves the file is compiled into the crate, not that a test
exercises it. The `shots` canary shares that limit for a different reason —
`hudshots.sh` lints the stage before either driver runs, so a syntax error is
a lint failure — and what it DOES catch is a file the stage drops entirely
(`shell.qml`, `tests/`). That a plate is instantiated and lit at all is gated
elsewhere, by `test_every_plate_in_the_shell_is_lit_in_some_shot`.

What `--runner shots` can grade about a plate's LOOK is B52's: `hudshots.sh`
now reads its own sheet back, comparing every PNG it just rendered against the
one committed at `HEAD` (`tools/hudsheet.py`), and naming the shots that moved,
the box they moved in and three of the pixels by colour. Expected lives in git
because a refresh run renders over `docs/hud` and a file cannot be compared to
itself. So a deliberate HUD change ends that script nonzero, with the new PNGs
on disk: look at them, commit them, and the next run is green.

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
