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
bash ops/ralph/bartest.sh             # the bar's QML, headless
bash ops/ralph/notifytest.sh          # the notifier's QML, headless
bash ops/ralph/nixtest.sh             # the flake's own options -> the units ares gets
bash ops/ralph/shellload.sh           # all three shells LOADED by a real quickshell
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
the suites the gate is running.

The last three gates are neither Python, QML nor Rust: what they read is a nix
EVALUATION (B72, D41). `nixtest.sh` asserts what a module option does to the
unit text ares gets — subject `.#nixosConfigurations.ares` — `hudscreens.sh`
photographs the real `.#jv-hud`, and `shellload.sh` LOADS all three shells;
a flake attribute names no path, so all three are
DECLARED, in `DECLARED_GATES`, against a `# reads:` header each script carries
about itself, which `test_dependents.py` holds equal. `nixtest.sh` is then a
step like any other (22 s, whenever `modules/`, `hosts/ares/`, `pkgs/`, `nix/`
or the flake itself moves), and so is `shellload.sh` (25 s, whenever any shell,
its package or the theme moves). `hudscreens.sh` is deliberately NOT one: it runs
here fine — 3m00s, measured — but it boots a compositor and what it produces
is seven photographs for a human rather than a verdict to collect. B74 took
away the other half of that argument (a run that changed nothing now restores
what it compared against, so it no longer dirties the tree the plan was
computed from) and B75 asked whether a cheaper, verdict-only half would be
bindable. It would not: the run books its own phases now, and 144.8 s of the
179.8 s is the probes. The pictures cost 0.9 s — `grim` and seven PNG encodes
— and the rest of that half is reading them back against HEAD. So it is
NAMED on every verdict instead, green or red, beside the paths that asked for
it, because a list of the gates that read your change which silently drops one
reads as coverage.

`shellload.sh` (D41) is the part of that question which DID have a cheap
answer, and it is a different gate rather than a flag on the old one. Until it,
`hudscreens.sh` was the only thing in this repo that ran a real quickshell, so
`shell/jv-hud/shell.qml` was the only `shell.qml` any engine ever opened: every
shot harness deletes `shell.qml` from its stage on purpose, because ShellRoot
and the layer-shell attached properties cannot resolve outside quickshell's own
binary. The bar's and the notifier's outermost file were held by qmllint alone
— and a `var` binding that throws is invisible to a linter, which is D34's and
D39's whole shape. So: one headless sway, one real quickshell per shell, a wait
on quickshell's own `Configuration Loaded`, and `tools/qmlerrors.py` over what
each said. 25 s, no screenshots, nothing to commit afterwards. It is not a
picture and says nothing about a pixel; what it covers is the outermost file,
the per-screen delegate and every binding evaluated whatever the state, because
the HUD runs there with no jarvisd and the bar with no niri. The notifier is
the exception and gets a real D-Bus client — which is also the first thing here
ever to prove that name is claimed and answers.

It also asks the compositor two things no log line can answer (D44). That sway
really has all three declared monitors, once, before any shell — every shell
builds one surface per screen, so a run that got one output would have loaded
one delegate and called it a shell, and nothing read the answer. And what each
surface RESERVED, per shell, three times: `swaymsg -t get_workspaces` is
shrunk by every exclusive zone, so the bar's 31 px strip has to be missing
from all three monitors while it is up and back on all three once it is gone.
That one is a proof of mapping — an unmapped surface reserves nothing —
and `Configuration Loaded` never was: it is the root component built, and a
`PanelWindow` whose layer-shell properties failed to attach gets that line
too. The HUD's and the notifier's readings are the other direction and a much
narrower claim than they look; the measured reason is in the D44 section of
`tools/shellload/shells.py`, and it is worth reading before counting either as
coverage.

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

Four runners (B49, B51), each with its own canary, and one of them is three
suites — the QML shells, picked by the target (D11):
```
bash ops/ralph/mutate.sh <service>              # .py   via runtests.sh
bash ops/ralph/mutate.sh --runner qml hud       # .qml  via qmltest.sh     (core/)
bash ops/ralph/mutate.sh --runner qml bar       # .qml  via bartest.sh     (core/)
bash ops/ralph/mutate.sh --runner qml notify    # .qml  via notifytest.sh  (core/)
bash ops/ralph/mutate.sh --runner cargo jarvisd # .rs   via cargotest.sh
bash ops/ralph/mutate.sh --runner shots hud     # .qml  via hudshots.sh    (plates)
```
Three scripts and not one with an argument, for the reason the gate has:
`verify.sh` runs a gate by its command string, so one runner pointed at three
trees would send a toast's change to the HUD's tests. Until D11 the harness had
only the HUD's, so a canary in `shell/jv-bar/core` lived, the file was refused,
and the hint blamed the plates — the bar's and the notifier's mutations could
only be driven by hand. A mutation in a shell the chosen suite is not pointed
at is now refused before any suite runs, naming the one that would grade it.
The first bar mutation ever graded found a real hole: nothing asserted that a
workspace already urgent in niri's opening snapshot is drawn urgent.

`--runner qml <shell>` grades that shell's `core/` only — measured, not assumed:
the canary LIVES on every top-level element, because every driver in every
`tests/` imports `"../core"` and nothing else. The HUD's are refused with the
runner that can take them:
`--runner shots` stages the whole shell the way `hudshots.sh` does and drives
the real plates, writing its PNGs into the run's own scratch so the committed
contact sheet in `docs/hud/` is never touched. It costs ~53 s a suite run
against qmltest.sh's ~14 s, so the run count (baseline + one canary per file +
one per mutation + baseline) is printed before the first one starts. The notifier has a
render harness of its own since D20 (`ops/ralph/notifyshots.sh`, which stages
the toast the same way and reads `docs/notify/` back) and the bar one since D13
(`ops/ralph/barshots.sh`, which stages the strip at real monitor widths and
reads `docs/bar/` back), but this harness is pointed at neither yet — PLAN D31.
Each shell's abort says so, rather than offering a runner that would not work.
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

## Launch — auto-restarting service (survives crashes + reboots)
The loop is the original "Ralph is a Bash loop": `loop-run.sh` feeds the SAME
prompt to a FRESH headless `claude -p` each iteration; the repo is the only
memory between iterations. (The `ralph-loop` PLUGIN's Stop-hook only works in an
interactive session where plugins load — a headless/systemd context can't run it,
so we don't use it.) No arming step; it builds immediately.

One-time install:
```
mkdir -p ~/.config/systemd/user
ln -sf ~/jarvisos/ops/ralph/ralph-loop.service ~/.config/systemd/user/ralph-loop.service
systemctl --user daemon-reload
systemctl --user enable --now ralph-loop.service
loginctl enable-linger "$USER"     # keep running while logged out / after reboot
```
Hands-off after that: on crash/OOM/reboot systemd relaunches it and it resumes
building (the repo state IS the memory). Watch:
```
journalctl --user -u ralph-loop -f     # live iteration output
bash ops/ralph/updates.sh              # commit + journal delta since last check
```

Pause / stop:
```
touch ~/jarvisos-ralph/.ralph-STOP           # clean pause after the current iteration
systemctl --user start ralph-loop.service    # (remove the STOP file first to resume)
systemctl --user disable --now ralph-loop.service   # stop for good
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
