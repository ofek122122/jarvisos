# Ralph loop — PLAN (the prioritized backlog; the loop edits this)

Priority ladder: **UI/UX first** (blueprint §06), then features/backlog, then
creative additions. Mark items `[x]` done with the commit hash. Add follow-ups
you discover. Keep items small enough to finish in one iteration.

## Track D — JarvisOS desktop identity — NEW TOP PRIORITY
Full-desktop redesign so the OS *looks* like JarvisOS. Spec:
`docs/superpowers/specs/2026-09-25-jarvisos-desktop-identity-design.md`.
The CORE landed by hand (wallpaper, GTK/Qt/cursor/icon theming, alacritty +
fuzzel palettes in `modules/theme.nix`, ember niri focus ring). These items
extend it. All new on-screen surfaces are `graphical-session.target` user
services like jv-hud, consume the §06 palette, and keep the top-right free for
the HUD. Do NOT touch the login greeter's session command untested (a broken
greetd locks the user out) — style only, and leave the graphical greeter for a
human-reviewed step.

> **STEER (2026-09-25, human directive): do D2 (notifications) THEN D3 (lock
> screen) NEXT, before any more bar polish (D11–D17) or other Track D items.**
> The user wants the next *visible new surfaces*, not internal hardening. Give
> each a real, on-screen, §06 slice that a human can see; the polish items wait
> until D2 and D3 both exist. (This overrides the priority ladder for now.)

- [x] D1. **Top bar** (Quickshell, own module `shell/jv-bar` + `pkgs/jv-bar` +
      user service): slim bar — niri workspaces (left), clock (center).
      Leave the top-right corner for the HUD. Consume the shared Theme.
      qmllint clean; render-verify. (Done: a layer-shell strip on every
      monitor, `WlrLayer.Top`, `WlrKeyboardFocus.None`, `mask: Region {}` —
      it cannot take the keyboard and cannot be clicked — reserving exactly
      its own height so windows tile below it. Workspaces come from `niri
      msg --json event-stream`, one read-only child process, parsed by
      `shell/jv-bar/core/NiriModel.qml` against the REAL recorded stream in
      `harness/fixtures/niri`; the clock is Quickshell's `SystemClock` at
      Minutes precision. `tools/gen_theme_qml.py` now generates BOTH shells'
      Theme.qml from one renderer, byte for byte, so the corner and the strip
      cannot drift apart. New gate `ops/ralph/bartest.sh`, wired into
      `dependents.QML_GATES`. 31 headless QML tests; 9 mutations, 9 caught.
      NOT done, and deliberately: **net·audio·battery**, because none of the
      three has a real source in this repo yet — a battery pip on a desktop
      and a volume readout with nothing publishing volume are the fakery
      invariant 10 forbids. See **D17**.)
- [x] D2. **Notifications** — a Quickshell notification daemon of our own
      (`shell/jv-notify` + `pkgs/jv-notify` + a graphical-session user
      service), not mako themed. Before it, ares had NO notification daemon at
      all: every app that asked the session bus to show you something got an
      error and you were never told. Now the bottom-right corner of every
      monitor holds up to three plates in the HUD's own visual language, and
      `core/NotifyModel.qml` owns the lifecycle — 22 headless tests, 12
      mutations, 12 caught.
      The decisions worth knowing, because each one is a decision:
      · **NOT ember.** Any process with a session bus can send a notification
        and can put any string in `app_name`, including "Jarvis" — so spending
        the accent here would hand every program on this machine the ability
        to dress up as the assistant. Urgency is one channel, the 6 px dot:
        `risk` / `text_2` / `text_3`.
      · **`expire_timeout = 0` is refused.** The spec's "never expire" is a
        D-Bus call any process can make to pin a plate over your work for the
        session; a non-critical notification that asks for forever gets
        `maxDwellMs` (20 s) instead, and only `Critical` stays until its
        sender withdraws it. A declared dwell is clamped to [1.5 s, 20 s].
      · **The capability set is an honesty declaration.** `actionsSupported`,
        `bodyMarkupSupported`, `imageSupported`, `persistenceSupported` and
        four more are false because these pixels do not do them — the mask is
        empty, so there is no click to invoke an action with, and every Text
        is `Text.PlainText`. A tools gate reads both halves and fails if a
        capability outruns the pixels.
      · **Every monitor**, like the HUD and unlike the bar: nothing here
        publishes which screen you are looking at, and a toast you never saw
        is worse than three copies of one (**D21**).
      · **The box is derived**, not declared, so the A63 crop cannot happen
        here. Reduced motion is honoured through `Theme.reducedMotion` in one
        `Fade` component rather than a hand-copied MotionPolicy (**D18**).
        (D18 has since landed: `Fade` is gone, this shell has the generated
        `Ease`/`Motion`/`MotionPolicy`, and the fade now obeys the session
        override and the machine as well as the token.)
      New gate `ops/ralph/notifytest.sh`, wired into `dependents.QML_GATES`.
      Tests: `bash ops/ralph/verify.sh` GREEN; `nixos-rebuild build` green
      with `unit-jv-notify.service` in the closure. Never tested, never
      switched.
- [x] D3. **Lock screen** — `pkgs/jv-lock`, swaylock-effects with its whole
      argv fixed at build time, installed on PATH and asked for BY HAND. It
      shows the JarvisOS wallpaper (the same store PNG the wallpaper unit
      hands swaybg — `nixtest.sh` holds the two equal), a `ground_deep` disc
      with a `line` ring, and the clock in `face "mono"` at twice the type
      scale's readout.
      The decisions worth knowing:
      · **It never photographs your desktop.** `--screenshots` and the whole
        `--effect-*` family are refused: a blurred photograph of your desktop
        is still your desktop — window shapes, the outline of a document, the
        fact that you had eleven windows open — held on screen for as long as
        you are away. Blur is not redaction (invariant 7).
      · **No `--grace`.** A grace period is a stretch where the lock screen is
        up and any keypress dismisses it without a password: a machine that
        looks locked and is not, which is worse than one that is not locked,
        because you walk away from it.
      · **Teal is you, ember is the machine.** §06 assigns the two voices and
        the states follow it exactly: a keypress highlights `teal`, and the
        ONLY ember on this screen is the ring while your password is being
        checked — the one moment something is actually being computed.
        `risk` for a refusal, `warn` for Caps Lock (the thing that is about
        to make you wrong), `text_3` for a backspace.
      · **All fifteen state colours are declared**, because a channel this
        file does not paint keeps swaylock's own default, which is
        off-palette by construction — the identity would fail exactly in the
        moments that matter (being checked, being refused).
      · **`--timestr %H:%M`, not the default `%T`.** A seconds counter
        repaints every output once a second for as long as the machine is
        locked; §06 says 0 fps when idle, and that is a cost paid all night.
      · **`--color` is set** because swaylock's default background is WHITE:
        a full-brightness screen in a dark room the first time an image
        cannot be read.
      · **The geometry was LOOKED at**, not reasoned about — five
        combinations rendered on a nested headless sway at 2560x1440 and
        compared (see the journal). The ring is four hairlines because one
        disappears at this radius, and an invisible ring is an invisible
        "checking" and an invisible "wrong".
      · **Nothing auto-locks.** No idle timer, no `loginctl lock-session`
        handler, no before-sleep unit — see **D23**: arming an automatic lock
        before a human has proven the unlock path on this machine is the one
        way this surface can hurt somebody.
      New tools gate `tools/tests/test_jv_lock.py` (14 cases, in a checkout
      with no nix) plus 7 new `nixtest.sh` cases over the BUILT script and
      the generated PAM stack. 14 mutations, 14 caught. Tests:
      `bash ops/ralph/verify.sh` GREEN; `nixos-rebuild build` green with
      `sw/bin/jv-lock` and `/etc/pam.d/swaylock` in the closure. Never
      tested, never switched.
- [ ] D4. **Migrate the niri config into the flake** (`environment.etc."niri/config.kdl"`
      or a module), preserving the user's keybinds/outputs, so the whole look is
      declarative — the one core piece currently living in the user's home file.
      Add gaps/borders/inactive-dim in §06 while doing it.
- [ ] D5. **Custom launcher** (Quickshell): replace fuzzel with a JarvisOS
      launcher — search + app grid in §06. Until then fuzzel is themed.
- [ ] D6. **Login greeter** (CAREFUL): recolor tuigreet first (safe); then a
      graphical greeter (regreet themed) as its own reviewed step — never
      switch the greetd session command untested.
- [~] D7. **Boot continuity check**: confirm GRUB + Plymouth share the exact §06
      tokens the desktop now uses; unify any drift. — 824444f (the DESKTOP half)
      (Measured, and the answer was no: the boot path and the desktop were
      BOTH off §06, consistently, from the same hand-copy. `modules/theme.nix`
      now reads `personality/theme.toml` with `builtins.fromTOML` — the
      fonts.nix idiom, `token`/`face` helpers that throw on an unknown name —
      so the terminal and the launcher moved onto the blueprint's greys
      (#E4EAEE / #9FADB7 / #6E7E89, from #E6ECF0 / #9BAAB4 / #64747F) and
      #F79070 left the desktop: §06's three hues + three status colours cover
      all sixteen ANSI slots, with yellow = `warn` and magenta = `risk`.
      VERIFIED by reading the BUILT store output, not the source — 9 tokens,
      0 off-palette colours in `result/etc/xdg/{alacritty,fuzzel}`. Three
      tools gates, the desktop mirrors of the QML ones (no colour literal
      under modules/ or pkgs/, every `token "x"` a name [palette] defines,
      every family from [type]); the colour scan DISCOVERS its subjects, and
      its exception table is exhaustive both ways. 3 mutations, 3 caught.
      The boot path is NOT done and is not the loop's: proposal **R9** in
      `docs/optimization-backlog.md` measures its drift colour-by-colour.
      Tests: `bash ops/ralph/verify.sh`.)
- [x] D8. **The wallpaper's colours are its own** (`pkgs/jarvis-wallpaper`) —
      done, and the answer to the question it was held back for was NO.
      (Six literals gone; the file reads `personality/theme.toml` with
      `builtins.fromTOML` and the same throwing `token`/`face` helpers as
      modules/theme.nix, so `pkgs/jarvis-wallpaper/default.nix` is out of
      `COLOUR_EXCEPTIONS` and the table has no loop-owned entry left. The
      vignette was the open design question and LOOKING answered it: its old
      outer stop #05080B is darker than `ground_deep`, which is the colour a
      HUD plate is painted in — so every plate read as LIGHTER than the
      desktop behind it, the exact inversion of why `ground_deep` exists. The
      field is `ground` settling into `ground_deep` now (one continuous ramp,
      three levels where there were seven). Rejected by eye, not by argument:
      `surface` as the lit centre (lifts the whole field and paints the
      desktop in the plates' own colour), a plateau at 0.72 (a visible banding
      seam in the upper left), and a white-hot `text` comet head (the
      brightest pixel on the screen, meaning nothing). The head is `ember` and
      reads by mass. Also moved: the wordmark to `text`, the subtitle + tick
      ring to `text_3`, grid/outer rings to `line`, middle ring to
      `line_soft`. The face is `face "mono"` now too, and resvg's silent
      substitution — it warns and exits 0 — fails the build instead.
      VERIFIED in the store PNG the unit hands swaybg, not the source:
      head/reticle #F0714A, corners #090D12, wordmark #E4EAEE, subtitle
      #6E7E89, and byte-identical to the render I looked at. 4 mutations,
      4 caught. Tests: `bash ops/ralph/verify.sh`.)
- [ ] D10. **The wallpaper is composed for ONE of the three monitors.** It is
      a single 2560x1440 PNG and `swaybg -m fill` scales it to each output, so
      on the two 1920x1080 panels the instrument (translate(1880 980), already
      mostly off-canvas by design) and the bottom-left wordmark are cropped by
      a different amount than the composition allows for, and the 64 px grid
      stops being 64 px. Options: render one PNG per output geometry and give
      swaybg `-o <output> -i <png>` per monitor, or recompose so the
      instrument's anchor is a fraction of the canvas. Note the first option
      needs output NAMES, and the flake declares none — the outputs live in
      the user's own niri config, which is **D4**, so the second option is the
      one that is doable today and D4 is what unblocks the first. Found while
      doing D8: the render is 2560x1440 because the primary is, and nothing in
      the repo says what the other two get.
- [x] D11. **`tools/mutate.py` cannot grade the bar.** Its QML language entry
      was `script="qmltest.sh"`, `targets=("hud",)`, so a canary planted in
      `shell/jv-bar/core` was graded by the HUD's runner — which does not
      import the bar at all, so every canary there lived, the harness refused
      the file (which is honest) and the abort's hint sent the reader to
      `--runner shots`, which cannot see the bar either. The 9 mutations D1
      ran and the 12 D2 ran were driven by hand for that reason.
      (Done: `--runner qml` is now a LANGUAGE and the target names the SUITE —
      `mutate.SHELLS` holds the three (`hud`/`bar`/`notify` →
      `qmltest.sh`/`bartest.sh`/`notifytest.sh`), and `Language.for_target`
      turns the choice into a suite before anything runs. Three scripts rather
      than one with an argument is not this harness's decision to revisit: the
      gate runs a gate by its COMMAND STRING, so one runner pointed at three
      trees would be one gate. The un-resolved QML language has no script at
      all and `command()` refuses it, because defaulting to the HUD's runner
      is precisely the bug. Two things beyond the routing:
      · **A mutation in another shell is refused before a suite runs**
        (`misrouted`) — which shell a file is in is a fact about its path, and
        the old answer cost two suite runs and then explained somebody else's
        plates. Each shell's canary hint is now its own, and the bar's and the
        notifier's do NOT offer a `--runner shots` regrade, because neither
        has one (D13, D20).
      · **The shells this harness grades are the shells that have a gate** —
        `tools/dependents.py` already holds that table (it is what decides
        which suite `verify.sh` runs for a changed file), so a test holds the
        two equal. A fourth shell lands there first; without this, D11 simply
        happens again.
      And the payoff, the first time a bar mutation was ever graded: **the
      snapshot's `is_urgent` was asserted by nothing.** Every fixture in
      `tst_nirimodel.qml` sends `is_urgent: false`, so `raw.is_urgent === true`
      could be the literal `false` with the suite still green — urgency was
      only ever tested arriving by DELTA. That is the one path a window that
      went urgent before the bar started takes, and it was drawn calm. Closed
      here with the test that catches it. `active` and `focused` were mutated
      the same way and both were caught, so it was one hole and not four.)
- [ ] D12. **Record the niri deltas, with a human at the keyboard.**
      `harness/fixtures/niri/ares-desk.jsonl` is the connect snapshot only —
      every event the bar ACTS on (`WorkspaceActivated`,
      `WorkspaceUrgencyChanged`, a second `WorkspacesChanged`) is absent,
      because recording one means switching workspaces in a live session.
      Their field names were read out of the shipped niri binary's serde
      table rather than guessed (see the fixture README), but the model's
      behaviour on them is still inference from a shape. Recording a real
      switch + an urgent window would turn `tst_nirimodel.qml`'s delta cases
      from inference into evidence. It also unblocks the **occupancy pip**:
      `WorkspaceActiveWindowChanged` is the event that would say which
      workspaces have windows on them, and nothing here has ever seen one
      fire — a pip drawn from an event that might not arrive goes stale
      silently, which is the one failure mode a bar must not have.
      (`NiriModel.qml` names this item for that half.)
- [x] D13. **A render harness for the bar**, the way `hudshots.sh` is one for
      the HUD: stage `shell/jv-bar` with `Niri.qml` stubbed, drive
      `Workspaces`/`Clock` with the recorded desk, photograph the strip and
      read the sheet back. Today `Workspaces.qml`, `Clock.qml` and the strip
      itself are reached by NO QML gate — only qmllint inside `nix build
      .#jv-bar` and the Python sweeps over `shell/**`, which is why
      `test_dependents.py` writes that gap down instead of letting it be
      invisible. `Workspaces.qml` names this item.
      DONE (iteration 123): `ops/ralph/barshots.sh` + `tools/barshots/` +
      `docs/bar/` — nine shots, one gate, and the bar's ungated set is now
      exactly the other two shells' (`shell.qml` and the two Quickshell
      singletons). The decisions worth knowing:
      · **The shot is a WHOLE MONITOR**, 2560 or 1920 px wide by the 31 px the
        shell derives from the type scale — not a box the harness chose. This
        surface spans its output, so width is the one thing a harness cannot
        pick for itself: both questions only this sheet can answer (is the
        clock on screen, does the row reach the HUD's corner) are questions
        about a particular monitor. A 640 px shot is there for the third case,
        which ares does not have and `shell.qml` says "should fail visibly".
      · **Two numbers are asserted, not just photographed.** `hudOverflowPx`
        is 0 on every shot — the bar's side of a promise made in prose to a
        process on another layer that draws in that corner and cannot be asked
        — and `clockOverlapPx` is 0 against a clock centred on the SCREEN,
        which therefore cannot move out of the way.
      · **The paper is the bar's own ground**, unlike the other two sheets: a
        bar is opaque and reserves its own strip, so there is nothing behind it
        and a neutral grey would be the harness inventing one.
      · **Six shots are ares' real desk** (the recorded `WorkspacesChanged`,
        byte for byte, through the real `core/NiriModel.qml`); two are composed
        because this machine has no named workspaces, and the composer's every
        field is checked against the recording, so a composed shot cannot
        quietly be a picture of a message shape niri does not send.
      · **The caption and the colour are one decision.** `Workspaces.reading()`
        names what a workspace is doing in a word and `tint()` turns that word
        into a token, so the sheet cannot report `focused` over a label painted
        `text_3` — `Toast.urgencyName`'s argument, one shell over.
      · **The margin is printed, not pinned.** Every run says how much room is
        left between the last workspace and the clock, because that is
        arithmetic over glyph widths: asserting it would fail on a font update
        with nothing wrong, and never measuring it is how it runs out. See
        **D32**.
- [x] D14. **The bar moves, once, and only where a signal moved.** Closed by
      **D18**: the bar has the generated `Ease`/`Motion`/`MotionPolicy`, and
      `Workspaces.qml` eases exactly one property — the label colour, which IS
      the signal (your keyboard arriving on a workspace). Nothing else
      animates: a workspace appearing or vanishing snaps, because there is no
      intermediate state between "niri has this workspace" and "it does not",
      and the strip is 0 fps whenever the desk is unchanged. It took the
      HUD's shape, as the item asked — one gated `Behavior`, not a Behavior
      per binding — and the gate is now the whole §06 question (declared
      preference, `JV_REDUCED_MOTION`, battery, fullscreen) rather than the
      preference alone.
- [ ] D15. **Clicking a workspace to switch to it** — `mask: Region {}` means
      the bar receives no pointer input at all, and opening the mask is NOT
      the way to add this: switching a workspace is changing the state of this
      machine, which is `jv-act`'s alone (invariant 3). The path is a jv-act
      tool the bar ASKS, not a `niri msg action` from the shell. Needs human
      review of the tool, so it is a proposal, not a task. `shell.qml` names
      this item.
- [x] D16. **The bar reserved the HUD's corner by a number, not by asking.**
      `hudReservePx: 300 + Theme.insetPx` was a copy of the HUD's own
      `implicitWidth` in a file that cannot see it — two processes on two
      layers, and neither can detect the clash. The honest floor was a tools
      test that read both; the real fix asked for here was one place
      declaring "the HUD's corner is this wide" with both shells reading it.
      DONE (iteration 124): `geometry.hud_corner_px = 300` in
      `personality/theme.toml`, so `shell/jv-hud/shell.qml` says
      `implicitWidth: Theme.hudCornerPx` and `shell/jv-bar/shell.qml` says
      `hudReservePx: Theme.hudCornerPx + Theme.insetPx`. What is worth
      knowing about it:
      · **The width moved into identity and the HEIGHT did not**, which is
        the whole distinction the item was hiding: the corner's width is a
        DECLARED choice about how much of the screen Jarvis takes (and the
        one fact a second process needs), while `implicitHeight: 826` is the
        MEASURED total of the crowded stack — `tools/hudshots/scene/
        tst_fit.qml` computes it and would fail with the number it is over.
        A measurement has no business in a versioned theme, so it stayed a
        literal in the shell.
      · **`+ Theme.insetPx` is still the bar's own arithmetic**, because the
        token cannot carry it: the HUD sits that far off the edge, so a bar
        reserving the bare corner would leave a plate over the last inset.
        The gate pins the whole expression rather than the sum.
      · **Adding the token to `REQUIRED`** in `tools/gen_theme_qml.py` is
        what makes deleting it from theme.toml fail in the generator instead
        of in a shell — the HUD is now a consumer of it, and that table is
        the list of tokens a consumer is allowed to assume exists.
      · **Three harness copies of the box are now pinned to the token, not
        to a literal.** `tools/tests/test_gen_theme_qml.py` gained one
        resolver, `hud_surface_box()`, and `test_hudshots.py` (the three
        scene drivers) and `test_hudscreens.py` (`sheet.py`'s `SURFACE_W`)
        both read it. That mattered more than it looks: both of those gates
        matched `implicitWidth:\s*(\d+)` and would have passed `None` into
        `int()` the moment the shell stopped carrying digits — a crash, not
        a verdict, which is the cheap half. The expensive half is a regex
        that DOES still match something and pins the wrong thing.
      · **Nothing on screen moved**, which is the intended outcome and is
        evidence rather than a claim: all three shot sheets (hudshots,
        notifyshots, barshots) and the real-compositor `hudscreens.sh`
        compared byte-for-byte clean against the pictures at HEAD.
- [ ] D17. **net · audio · battery on the bar, when each has a real source.**
      The original D1 sketch had all three mid-right and none shipped, on
      purpose: nothing in this repo publishes link state or volume, and ares
      has no battery. Each is its own small item with its own honest source —
      audio wants a PipeWire/WirePlumber reading (jv-voice already knows the
      default sink, so the bus may be the right road), net wants the link, and
      battery should simply never appear on a desktop rather than showing
      100%. Until then the strip's right half stays empty, which §06 calls
      earned.
- [x] D18. **The motion trio is generated into every shell.**
      `Ease.qml` + `Motion.qml` + `core/MotionPolicy.qml` is the one place
      §06's stillness rule is decidable (declared preference, session
      override, battery, fullscreen), and it existed only in `shell/jv-hud`
      because `import "."` resolves inside ONE store copy. The fix was the
      mechanism that already keeps three `Theme.qml` files byte-identical:
      `tools/gen_theme_qml.py` renders the three files per shell from one
      renderer, and a test asserts all three copies are the same bytes — so
      one suite (`shell/jv-hud/tests/tst_motionpolicy.qml`) is the test for
      all of them. What it changed:
      · **The bar can move at all** (**D14**), and does, in one place.
      · **jv-notify's hand-rolled `Fade` is gone.** Its toast fade was gated
        on `Theme.reducedMotion` — the versioned preference and nothing else
        — and now asks the same question the HUD's plates ask. `Toast.qml`
        says `Ease on opacity`.
      · **One env var for the whole desktop**: `JV_HUD_REDUCED_MOTION` became
        `JV_REDUCED_MOTION`, because three shells draw one desktop and a
        session override that stilled the corner while the bar and the toasts
        kept moving is a preference half-obeyed.
      · **The generated types are registered without any shell naming them.**
        `Theme`/`Motion`/`Ease`/`MotionPolicy` are in `GENERATED_*` tables,
        not in the per-shell ones, so a fourth shell gets the trio by
        existing — the only way to end up with a private `Motion` was to copy
        one, and there is nothing left to copy.
      · **`Motion` derives its durations from the tokens**: one gated
        property per `*_ms` key in `[motion]`, so a new duration in
        theme.toml reaches every shell gated with no edit to the generator.
        `[motion] reduced_motion` is now REQUIRED — the generated wiring
        reads it, so a theme without it would generate a broken shell.
- [ ] D19. **A notification's actions cannot be offered, and are not
      claimed.** freedesktop lets a sender attach buttons; `mask: Region {}`
      means this surface receives no pointer input at all, so `jv-notify`
      declares `actionsSupported: false` rather than drawing a button nothing
      can press. Opening the mask is not the whole of it — invoking an action
      is a D-Bus call into another process, which is close enough to
      invariant 3's line that a human should draw it — and it needs a hover
      region that does not eat clicks meant for the window underneath. Same
      shape as **D15** (clicking a workspace): a proposal, not a task.
- [x] D20. **A render harness for the notification corner**, the way
      `hudshots.sh` is one for the HUD and **D13** wants one for the bar. It
      matters more here than for either: this is the only surface on the
      machine whose CONTENT comes from programs this repo did not write, so
      "what does a toast do with a 4000-character summary, a name that is all
      combining characters, or three criticals at once" is a question only
      pixels can answer. `Toast.qml`, `Fade.qml` and the strip are reached by
      no QML gate today — only qmllint inside `nix build .#jv-notify` and the
      Python sweeps over `shell/**`, which `test_dependents.py` writes down.
      DONE (iteration 122): `ops/ralph/notifyshots.sh` stages the shell with
      the two Quickshell singletons replaced (`Notifications`, `Motion`),
      rebuilds shell.qml's column as `tools/notifyshots/scene/Strip.qml`,
      drives the REAL `core/NotifyModel.qml`, and writes ten shots to
      `docs/notify/` — then reads the sheet back against HEAD like B52. Each
      shot asserts a caption the plate itself reports (`Toast.drew`: the
      urgency as a word, the rows really drawn, and `…` when a row ELIDED),
      so the elide is proved to have happened rather than to be configured.
      **It found a real bug on its first run**: an `app_name` with no space in
      it painted 656.5 px past a 320 px plate, over the desktop, on a surface
      with no input region — the name row was the one row with no width of its
      own. Bound and elided now, and every shot asserts `overflowPx == 0`.
      The stand-in `Motion` is generated (D29's `STANDINS` table), not copied.
      The gap `test_dependents.py` wrote down is now the HUD's three files.
- [ ] D21. **A toast appears on all three monitors at once.** Correct today
      and not free: nothing in this repo publishes which output has focus, so
      one monitor could only be chosen by a guess, and a guess is how a
      message is missed entirely. The honest fix has a real source —
      `niri msg --json event-stream` carries the focused output, and
      `shell/jv-bar/core/NiriModel.qml` already parses that stream — so this
      is really "the notifier needs the bar's view of the compositor", which
      is an argument for the niri model being shared rather than copied.
      Blocked on the same thing **D12** is: the deltas have never been
      recorded. `shell.qml` names this item.
- [ ] D22. **Nothing D-Bus-activates the notification daemon.** `jv-notify` is
      a `graphical-session.target` unit, so an app that sends a notification
      before the session is up (or after the unit has failed past its
      restarts) gets an error its user never sees. The freedesktop way is a
      `org.freedesktop.Notifications.service` activation file pointing at the
      unit, so the bus starts the daemon on demand. Small, and it wants a
      thought about what "the daemon was not running" should look like —
      today it looks like nothing at all. Found while finishing D2.
- [ ] D23. **Nothing on this machine can lock the screen for you, and that is
      deliberate until a human has unlocked it once.** `jv-lock` exists and is
      on PATH; nothing calls it. Three things want wiring and all three are
      blocked on the same one-line verification (`jv-lock`, type the password,
      get the desktop back): a niri keybind (which lands with **D4**, since
      the niri config is still the user's own file), a `loginctl lock-session`
      handler so other programs can ask, and a before-sleep unit. The order
      matters: an automatic lock armed before the unlock path has ever been
      proven on ares is the one way this surface can hurt somebody — the
      failure mode is a screen that never opens, and the only way out of it is
      a VT switch. The PAM stack is asserted (nixtest.sh) and swaylock fails
      BEFORE locking when PAM is missing, so the risk is small; it is not
      zero, and it is not the loop's to take.
- [ ] D24. **The lock screen has no gate that LOOKS at it.** Its argv is read
      as text (tools) and as built bytes (nixtest), and its pixels are read by
      nobody: the five renders that chose its geometry were a one-off in
      /tmp. `ops/ralph/hudscreens.sh` is the shape this wants — nested
      headless sway at ares' geometry, `grim`, a sheet read back against HEAD
      — and it is cheaper here than for the HUD (one client, no bus, no idle
      probe; the whole render took about 30 s). What it CANNOT photograph
      without a virtual-keyboard client is the four states that only exist
      while somebody is typing (clear / verifying / wrong / Caps Lock), which
      is exactly where the colour decisions live.
- [ ] D25. **The lock screen inherits D10 whole.** It shows the same single
      2560x1440 PNG, `--scaling fill`, on three differently-shaped outputs.
      The fix is the same fix, and `-i <output>:<path>` per monitor is the
      same blocked-on-**D4** option.
- [ ] D26. **Three files now carry their own `token`/`face` helpers**
      (modules/theme.nix, pkgs/jarvis-wallpaper, pkgs/jv-lock), and jv-lock
      added a third helper shape (`num`, for the type scale and the motion
      policy). They are identical by hand, which is the exact failure mode the
      helpers exist to prevent one level down. A `nix/theme.nix` returning
      `{ token; face; num; }` from one `fromTOML` would be read by all three;
      the gate that discovers painters (`_bearing_files`) already works by
      finding `token "x"` calls, so it would keep working unchanged.
- [ ] D27. **The bar's and the notifier's `core/` have never had a mutation
      sweep, and now they can.** D11 graded four lines of `NiriModel.qml` and
      one of `NotifyModel.qml` — five of perhaps forty — and one of the five
      found a real hole on the first try. Everything either model does
      (`workspacesOn`'s per-output sort, the activation-across-outputs rule,
      the dwell clamp, the three-plate queue, the withdraw path) is graded by
      nobody so far. ~15 mutations over the two is ~20 suite runs at ~14 s, so
      under five minutes — the cheapest evidence in the repo, and the only
      kind that says what these two suites are worth.
- [x] D29. **`tools/hudshots/stub/Motion.qml` is now a hand copy of a
      GENERATED file.** The stub exists for one real reason — the shots
      harness cannot import Quickshell, so `Quickshell.env` has to go — and
      everything else in it is meant to be the real file. That was a copy of
      a hand-written file before D18 and is a copy of a generated one now,
      which is the exact failure mode D18 just closed one level up.
      `test_hudshots.py` catches a MISSING member (the stub must offer
      everything the real one does), so a new duration token cannot slip; it
      cannot catch the stub answering the question differently. The fix is the
      generator rendering the stub too, from the same body with one line
      swapped — at which point "the shots animate for the reason the running
      HUD would" stops being a claim in a comment. Found while finishing D18.
      DONE (iteration 121): both renderings come out of one body through a
      `MotionTarget` naming the only three lines that cannot be shared (the
      Quickshell import, the root type, the `envOverride:` binding), held to
      exactly that difference by a test in both directions. `--out-dir` runs
      are guarded — pkgs/jv-hud's checkPhase renders one shell inside a sandbox
      with no `tools/` at all. 7 mutations, 7 caught; the sweep found one real
      hole first (`STUB_SHELL` pointed at another shell survived, because a
      repo-root `--check` names all three and rendered the stand-in anyway),
      and closing it is what pins WHICH shell the stand-in rides out with.
- [x] D30. **The bar now has an `Ease` and no gate loads it.** (Half closed by
      **D20**, and CLOSED by **D13** (iteration 123): `barshots.sh` stages
      `shell/jv-bar` whole and drives the real `Workspaces`, so the bar's
      `Ease`, `Motion`, `Theme` and `core/MotionPolicy` are all loaded by a
      gate now, and `03-focus-moved.png` is the picture of the one property
      this shell eases. Every shell has a render harness; A11 —
      `Motion.onBattery`/`fullscreen` have no source — is now the only part of
      this that stands, in all three. The original text follows.) The earlier
      half, from **D20**: `notifyshots.sh` loads `shell/jv-notify`'s `Ease`, `Toast` and
      the strip, so the notifier's half of this is done and the remaining one
      is the bar's — **D13**.) The original, for the half that stands:
      **The bar and the notifier now have an `Ease`, and no gate loads
      either one.** `shell/jv-bar/Ease.qml`, `Motion.qml`, `Workspaces.qml`
      and `shell/jv-notify/Ease.qml`, `Motion.qml`, `Toast.qml` are reached by
      no QML gate at all (`test_dependents.py` writes it down); only qmllint
      inside their nix builds and the Python sweeps see them. The HUD's copies
      ARE driven, by `hudshots.sh`, so the trio itself is exercised — what is
      not is the bar easing a colour and a toast fading in, which is precisely
      what **D13** and **D20** are for. Raised here because D18 moved both
      from "nothing to photograph" to "something that moves and is not
      photographed", and A11 (`Motion.onBattery`/`fullscreen` have no source)
      is now unsourced in three shells rather than one. Cheaper since D29:
      `render_motion_qml` takes a target now, so a bar shot harness needs a
      `MotionTarget`, not a second hand-written stand-in.
- [ ] D31. **`--runner shots` is the HUD's alone, and the notifier now has a
      render harness it could be pointed at.** D20 built `notifyshots.sh`,
      which stages `shell/jv-notify` whole and drives the real toasts — the
      exact thing `tools/mutate.py`'s `SHOTS` Language does with `hudshots.sh`
      — so `Toast.qml` is gradeable for the first time and nothing can grade
      it yet. The mechanism is already there and already general: `Language`
      has a `shells` table and `for_target` resolves it (that is how
      `--runner qml` picks between three scripts), so this is SHOTS gaining
      two `Shell` rows rather than new machinery. Two things do need care:
      `shots_baseline_hint` hard-codes `hudshots.sh`/`docs/hud`/`shell/jv-hud`
      in a sentence it MEASURES (B53), and ~15 tests in `test_mutate.py` pin
      the current single-suite shape. Worth doing before **D27**: the sweep
      D27 asks for is over `core/`, and the toast is the file whose content a
      stranger chooses. `tools/mutate.py`'s notify hint names this item.

- [x] D32. **The bar's workspaces row has no width of its own, and D13
      measured how much room is left: 274 px.** The row is a `Row`, which takes
      its width from its children; the clock is centred on the SCREEN, so it
      cannot move; and the HUD's corner is reserved by a number. Six
      long-named workspaces on a 1920 px monitor (`docs/bar/08-crowded.png`)
      leave 274 px before the two collide — about three more names. Nothing in
      the shell stops the seventh, and what happens then is a real §06
      decision rather than a clamp: dropping labels silently is the failure the
      notifier's `+N EARLIER` line exists to prevent, and eliding every label
      makes the one you are ON unreadable. The shape that fits this design
      language is probably "as many whole labels as fit, then `+N`", with the
      focused one never among the dropped — but that is a decision, and
      `barshots.sh` is now the thing that can photograph the answer.
      Discovered by D13, which prints the margin on every run so it stays a
      number somebody has seen. The fix wants a shot at the point of collision,
      which today would fail the sheet's own assertion — which is the right way
      round. — 8cdfca9
      · **The rule is `shell/jv-bar/core/RowFit.qml`**, pure arithmetic over
        numbers with no font in it, tested at round widths in
        `tests/tst_rowfit.qml`: as many whole labels as fit, then `+N` where
        the row was cut, and the workspace the OUTPUT IS SHOWING never among
        the dropped. "Showing" rather than "focused" because a monitor your
        keyboard is not on has no focused workspace and still has one it is
        displaying — and `NiriModel` will not let a workspace be focused
        without being active, so it is one property.
      · **The marker is a thing on screen, so it has a reading and a colour.**
        `warn` when one of the workspaces you cannot see is urgent, `text_3`
        otherwise — a row that hid a window's call for attention and said
        nothing would be doing the exact thing the marker exists to prevent.
        It is in `drew`, so the sheet's caption asserts it like any label.
      · **The widths are MEASURED.** `bench` is one invisible copy of each
        label in the row's own type; RowFit is handed what the words measure,
        not `length * advance`, which would be right about JetBrains Mono and
        wrong about the first name with an emoji in it — wrong in the
        direction that paints into another process's corner. Before every
        label is weighed the row is given no budget and draws everything.
      · **`roomPx` is the SURFACE's arithmetic**, in shell.qml and in the
        staged strip, because only the surface knows the monitor's width, the
        clock's centre and the HUD's corner. A tools gate compares the two
        expressions with the id normalised away, like `fits` before it.
      · **Two shots, and the nine that existed are byte-identical.**
        `docs/bar/10-collapsed.png` (keyboard on the first workspace: the run
        stops, the number is last) and `11-collapsed-focus-last.png` (keyboard
        on the last: "these, then some, then you", `+2` in warn). Both end
        clear of the clock — 63 px and 88 px — and 0 px into the HUD's corner.

- [x] D34. **The one animation in this shell never ran, and now a gate can
      tell.** (56136a8) It was not "may": measured first, red, on the real
      strip — every sample of the label colour was already at the target the
      instant the focus delta landed. The Repeater's model was the JS array
      `NiriModel` replaces wholesale on every delta (it must: a list mutated in
      place is a list no binding hears about); a Repeater handed a new array
      destroys its delegates; a Behavior does not animate an initial
      assignment. So each label was a new Text that had always been teal, with
      `Ease on color` attached to nothing, for as long as the row has existed.
      · **`shell/jv-bar/core/KeyedRows.qml`** — a ListModel synced BY KEY, and
        the row keys on niri's workspace id. A row whose key is still there
        keeps its delegate (moved, roles reassigned, which is a binding
        re-evaluation and therefore something an Ease can move THROUGH); a new
        key gets a new delegate and snaps, which is the honest reading of a
        workspace that has just come into existence. NOT by position: that
        sync hands each surviving delegate its NEIGHBOUR's workspace when the
        desk grows at the left, and cross-fades between two unrelated
        workspaces — a 200 ms lie about a change that is instantaneous.
      · **`tools/barshots/scene/tst_settle.qml`** — the gate. It samples the
        colour on the glyph DURING the move and requires an observation that
        is neither where it started nor where it is going, which is the only
        thing that separates a 200 ms ease from an assignment. Plus the half
        that fails if the row is keyed by position, plus the desk emptying and
        coming back. 12 cases headless in `tests/tst_keyedrows.qml` for the
        list itself, with a real Repeater and a real Behavior under them.
      · **The second fault, found by the first fix.** Syncing the list in
        `onShownChanged` reads `shown` EAGERLY, and `shown` was the end of a
        chain of four properties. QML notifies the dependents of `workspaces`
        in whatever order it likes, so `shown` could be composed from the
        PREVIOUS desk's plan over THIS desk's array — a ten-label run over no
        workspaces, once per emptied desk. It had been latent since D32 and
        could not show while nothing read `shown` eagerly. The derivation is
        now ONE binding over ONE argument, reaching only primitives.
      · **All 11 shots are byte-identical.** The rule changed nothing that was
        already settled, which is exactly the claim that deserves pictures.
      · `tools/barshots/scene/Desk.qml` now holds the recorded line and the
        composed-snapshot builder, once, for both drivers in that directory.

- [x] D36. **Nothing in any of the three shot harnesses failed on a QML that
      threw, and a green run of eleven correct PNGs was the proof.** (Done
      this iteration.) D34's second fault announced itself exactly once, as a
      `TypeError` in the middle of a run that ended `8 passed, 0 failed`.
      `tools/qmlerrors.py` now reads the runner's captured output and ends the
      run non-zero when anything in the scene threw; all three harnesses
      `tee` the runner into `$stage/runner.log` and hand it over before the
      sheet is compared, so a run that threw never reaches "wrote N shots".
      · **Ran all three first, as the item asked.** All clean at d605f4b:
        zero `QWARN` lines between them, and the only console voices are the
        two settle drivers' samples and the bar sheet's eleven "px between
        the workspaces and the clock" lines. So the rule went in green.
      · **The discriminator is the SHAPE the engine prints, not the words.**
        Console output is `qml: <text>`, with no source location; an error the
        engine caught is `file:///…/T.qml:7: TypeError: …`. So `NiriModel`'s
        refusal stays legitimate, and a `console.warn` whose text quotes
        "TypeError:" is still a voice. Seven ECMAScript error names, listed.
      · **Proved by injection, and the injection is the whole argument.** A
        handler in `Toast.qml` reading a property of `undefined`: the runner
        said `8 passed, 0 failed`, the ten PNGs came out BYTE-IDENTICAL —
        `git status docs/notify` clean — and `qmlerrors` refused, naming
        `Toast.qml:129`, the four test bodies it threw in, and the 23 lines
        it collapsed into them. Nothing else in this repo could have said so.
      · The first injection attempt was caught by `qmllint` before the runner
        ran, which is worth knowing: the statically visible version of this
        fault is already gated, and what reaches the engine is the
        dynamically typed one — exactly D34's shape.

- [x] D38. **Everything QML logs before the first test body runs is dropped,
      by QtTest, before D36 could see it.** (Done — this iteration.) A second
      ENGINE rather than a cleverer scan: `tools/qmlprobe/Probe.qml` loads the
      same staged scene under plain `qml`, which installs no message handler
      and prints the engine's own line with no `QWARN :` in front of it, and
      `tools/qmlerrors.py` now reads both outputs under one rule (the prefix
      turned out to be optional; the discriminator was never it). Wired into
      all three harnesses, before the runner, so a scene that threw writes no
      shots at all.
      · **THE HOLE IS ALPHABETICAL, which nobody knew.** QtTest drops what is
        logged while no test function is RUNNING — and a driver's scene is
        built before the run begins only if it is the FIRST file in the
        directory. Two identical drivers, and only the second is heard:
        `PASS : Probea::cleanupTestCase()` / `QWARN : UnknownTestFunc() …
        tst_b.qml:7: TypeError: …` / `PASS : Probeb::initTestCase()`. So which
        surface D36 covered was decided by a filename, and what covered the
        shell's own scene was the ACCIDENT of a second driver instantiating it
        after the run had started. The probe makes it deliberate.
      · **THE MEASUREMENT D38 ASKED FOR, taken: nothing is failing.** All
        three shells load clean in the state no sheet photographs — before a
        frame, a notification or a compositor event has arrived. The HUD's
        corner builds 78 objects, the bar's strip 11, the notifier's column 3,
        and not one binding threw in any of them.
      · **THE PROPERTY WALK WAS WRONG AND WAS REMOVED.** The first version
        read every property of every object (9,319 of them on the HUD) on the
        theory that a QML binding is lazy. It is not: an injected `property
        int injected: root.loose.nothingHere.count` on the bar's strip, and
        the identical fault as a `property var`, BOTH printed with the walk
        disabled and the census reading nothing. What is left is the census,
        which buys the one claim the run cannot otherwise make — that a scene
        was really built — and `Qt.exit(3)` when it was not.
      · **QT_FORCE_STDERR_LOGGING, and this is the discovery with the longest
        reach.** This Qt is built with the journald backend: with stderr in a
        pipe — which is exactly what `tee` makes it — `qml` prints NOTHING,
        not one line, not even its own census. Measured. qmltestrunner is
        unaffected (it writes its own `QWARN :` lines to stdout itself), which
        is why D36 worked. Anything else in this repo that pipes a Qt
        program's output is reading a silent stream.
      · **PROVED BY INJECTION, end to end.** A `var`-shaped fault on the
        staged strip's root — invisible to qmllint, D34's own shape — and
        `bash ops/ralph/barshots.sh` ends 1 at the probe, naming
        `shots/Strip.qml:31`, before a single PNG is written.

- [x] D39. **`hudscreens.sh` ran a real compositor for thirty iterations and
      nobody had read a line of what it said.** (Done this iteration.) The
      only gate that loads `shell.qml` at all starts TWELVE real quickshells
      in a pass — one per shot, one per idle window — and every one of them
      has written its output to a file since the first version of the
      harness, where nothing ever opened it. It scans them now, through the
      same `tools/qmlerrors.py` D36 wrote.
      · **D38's prediction was wrong, and the measurement says why.**
        `QT_FORCE_STDERR_LOGGING` is not needed here: quickshell installs a
        message handler of its OWN, so the journald backend never gets its
        output and a redirected file receives it whatever Qt would have done.
      · **THE REAL OBSTACLE WAS COLOUR.** Quickshell writes ANSI escapes
        whether or not anything is watching, so every level arrives as
        `\x1b[33m  WARN\x1b[97m scene\x1b[0m: `, which is not a prefix the
        scanner knows — a coloured log scans CLEAN. `NO_COLOR=1` is exported
        by the harness and is load-bearing; the coloured line is a recorded
        fixture, because the failure it prevents is silent.
      · **A THIRD SHAPE, and the same rule.** `WARN scene:
        @core/BusModel.qml[113:-1]: TypeError: …` — a level and a CATEGORY
        instead of `QWARN :`, a location written `@path[line:column]`
        relative to the shell's own root instead of `file:///…:line:`, and a
        column of -1 when the engine had none. Quickshell separates the voice
        from the fault at the source (`console.*` goes out under `qml`, the
        engine's errors under `scene`), which is a cleaner discriminator than
        the one D36 had to infer — but the location and the error name are
        still required, because a category is a claim someone else makes.
        `--prefix`, out of `sheet.SHELL_ROOT`, turns `@shell.qml` into
        `shell/jv-hud/shell.qml`; the constant lives in `sheet.py` because
        the script may not contain that path in any line it executes (the
        rule that keeps this harness from ever staging a HUD).
      · **THE ANSWER: the real HUD says nothing that throws.** 7,170 lines
        across the twelve logs of a full pass, clean, in 0.1 s.
      · **AND THE INSTRUMENT IS LIVE, proved by injection.** A `property var
        injectedFault: modelData.noSuchThing.count` on the PanelWindow — the
        D34 shape, invisible to qmllint — and the gate ends 1, naming
        `shell/jv-hud/shell.qml:90` in all twelve logs, three times in each
        (once per monitor). **Everything else about that run was green**:
        every probe passed — the corner, the zone, the focus, the growth, the
        click, 0 commits in every idle window — and all nine photographs
        still matched the sheet committed at HEAD. Without this scan that run
        was a perfect pass with a shell throwing on every screen.
      · No census is needed here, unlike the staged harnesses: the harness
        already waits on `Configuration Loaded` for every shell it starts,
        which is quickshell's own handler proving that log is being written.
        A test counts the two and holds them equal.
      · The run's cost was re-measured while it was open, which is the
        standing lesson of that paragraph: probe 154.8 s / 79.4%, sheet
        39.9 s / 20.5%, of 194.9 s. The scan itself is 0.1 s of it.

- [x] D37. **The notifier had the bar's exact shape, and it was worse there.**
      (Done 653b2cd.) `shell/jv-notify/shell.qml` repeated over
      `Notifications.toasts`, a JS array `NotifyModel` replaces wholesale, with
      `Ease on opacity` on the plate INSIDE the delegate. Measured the way D34
      was measured (`tools/notifyshots/scene/tst_settle.qml`, which samples
      during the fade), and it was real in all three directions at once:
      · a SECOND notification arriving refaded every plate already up,
      · a REPLACEMENT — the download-at-40%-then-80% case `NotifyModel` keeps
        in place on purpose — refaded both plates,
      · a WITHDRAWAL refaded the survivors.
      Every one of them went to opacity 0 and climbed back, so the corner
      blinked and the fade stopped meaning "this one is new".
      The fix: `core/KeyedRows.qml`'s body moved into `tools/gen_theme_qml.py`
      as `SHARED_CORE` — a third category between GENERATED_CORE ("every shell
      gets it", which is what §06's stillness rule is) and a shell's own table
      — and a shell opts in by naming it in its `*_CORE` registry, so it is
      generated into jv-bar and jv-notify and not into the HUD, which has no
      such list. `NotifyModel.onScreen` is the keyed list, carrying only the
      primitives a plate draws (`handle` and `deadline` stay in the model: a
      ListModel holds values, not objects).
      · **All ten shots are byte-identical**, before and after — which is the
        point: the sheet waits past `fadeInMs` before it grabs, so a corner
        that blinked on its way to the frame and one that never moved develop
        into the same file. No still picture could ever have caught this.
      · Three new headless assertions in `tst_notifymodel.qml` pin the thing
        that makes it work — the key at each index, across a replacement, an
        arrival, a withdrawal, and a counted notification scrolling into view
        (which IS a new row, and correctly fades).
      · `nixos-rebuild build` caught the one thing no suite could: the new
        generated file was untracked, so the flake's source filter excluded it
        and `--check` in pkgs/jv-notify called it stale.

- [ ] D40. **A fault in a DRIVER's own root is invisible to both halves, and
      that was measured rather than guessed.** D38 injected `property int
      injected: root.loose.nothingHere.count` into the root of
      `tools/barshots/scene/tst_settle.qml` — the FIRST driver in that
      directory — and ran the whole harness: `Totals: 8 passed, 0 failed`,
      eleven byte-identical PNGs, `qmlerrors: nothing threw` on both logs,
      exit 0. Completely green. QtTest dropped it because that scene is built
      before the run begins, and the probe never saw it because the probe
      loads `warnprobe.qml`, whose scene is the SHELL's, not a driver's.
      Which is the right target — a driver is test code and the shell is the
      product — but a driver whose own root silently throws is a driver whose
      arithmetic may be running on a default it never noticed, and every
      assertion it makes is downstream of that. Two candidate answers: a
      fourth probe document per harness whose subject is the driver (which
      means instantiating a `TestCase` outside a runner, and may not work at
      all), or renaming one driver per harness so the silent slot is held by
      a file that declares nothing — a trick, and a trick that the next
      alphabetical file would quietly inherit. Raised by D38.

- [x] D41. **Two of the three shells' `shell.qml` are never LOADED by
      anything.** (Done: `ops/ralph/shellload.sh` + `tools/shellload/` +
      `tools/tests/test_shellload.py`, option (a) exactly — one headless sway,
      one real quickshell per shell, a wait on quickshell's own `Configuration
      Loaded`, and the D39 scan per shell with its own `--prefix`. No pictures,
      no sheet, none of the 97.7 s idle probe. **25 s**, so unlike
      `hudscreens.sh` it is a verdict `verify.sh` collects: the third
      `DeclaredGate`, `runs_here=True`.
      **THE INSTRUMENT IS LIVE, PROVED BY INJECTION** rather than by reading
      the code, three times. `property var injectedFault:
      modelData.noSuchThing.count` on the bar's PanelWindow and on the
      notifier's — the D34 shape, invisible to qmllint, so `nix build` was
      GREEN for both — and the gate ends 1 naming `shell/jv-bar/shell.qml:83`
      and `shell/jv-notify/Toast.qml:51`, three times each, once per monitor.
      The third injection is the one that matters most: it was in `Toast.qml`,
      which only exists on screen because the gate SENDS a notification, so it
      proves the wake is doing real work.
      **AND THE BUS WAS THE MEASUREMENT NOBODY EXPECTED.** Run without
      `DBUS_SESSION_BUS_ADDRESS` replaced, `jv-notify` reaches the USER'S OWN
      live session bus and races the real notification daemon for
      `org.freedesktop.Notifications` — observed, as "presumably because one is
      already registered". Had it won, a gate would have taken over the
      notifications of the desktop it was running inside. So the run starts its
      own `dbus-daemon` with a config that has NO `<servicedir>`: the first
      version used `dbus-run-session`, which inherits the machine's service
      directories and started four xdg portals and a keyring inside a gate
      about three QML files.
      **AND THE NOTIFIER NOW HAS A REAL CLIENT, which is D22's first half.**
      `tools/shellload/load.py` asks the running daemon `GetCapabilities` over
      the private bus and gets exactly `['body']` — the honesty declaration in
      `Notifications.qml` surviving into the bus name, and a test holds the two
      halves equal — then `Notify` returns id 1. Nothing in this repo had ever
      proved that name was claimed or that it answered.)

- [x] D43. **The load probe evaluated almost none of the HUD's QML, and now
      the HUD is the half of it that is covered.** (Done.) `shellload.sh`
      starts a real `jarvisd` on the run's own socket, `tools/shellload/
      publish.py` puts eleven composed frames on it at 1 Hz, and the HUD's own
      read-only bridge — the child `pkgs/jv-hud` pins into the wrapper —
      carries them into the plates. Ten of the HUD's eleven plates light, on
      all three monitors, and it cost **1.8 s**: 25.4 s before, 27.2 s after.
      · **THE COVERAGE IS MEASURED, and the file it reaches is the one whose
        own header says no test can reach it.** `Bus.qml` — the Process, the
        SplitParser, the respawn timer, the monotonic clock — says in its
        first paragraph that "logic that lands in this file is logic no test
        can reach". A `var`-typed throw injected into its `latest()` forwarder
        (`model.latest(topic).body.nope.x`, the D34 shape qmllint cannot see)
        ended the gate 1 with **25,992 thrown lines** naming
        `shell/jv-hud/Bus.qml:48`. **And the control is the whole point: the
        SAME fault with the HUD pointed at a socket no broker was on reported
        `nothing threw in 8 lines`.** So the fault is not merely newly caught,
        it was entirely invisible to this repo an hour ago — and 8 lines
        versus 86 is how much of the HUD's own log existed before there was
        anything on the bus to say.
      · **THE CENSUS IS THE HUD'S OWN ACCOUNT, because nothing else could
        answer.** The HUD reserves no space, takes no focus, and with
        `ExclusionMode.Ignore` and no zone changes nothing a compositor
        reports when it maps — so "did the frames reach the plates" had no
        observable. `shell/jv-hud/shell.qml` now logs one line per surface
        naming the plates on it (`jv-hud: corner on HEADLESS-1 shows confirm
        state output heard reply action guard install mic health`), which is
        also a thing the real machine wanted: the corner is unmapped most of
        the time, so until now this machine kept no record of what it ever
        showed. NAMES ONLY, structurally — `plateName` is one word per
        element, so what reaches journald is WHICH readings were on screen and
        never the words jv-ears took down or the question jv-act asked
        (invariant 7).
      · **Per monitor, and the report names the plate.** A `guard.verdict`
        dropped from the frame list ends the gate 1 with `HEADLESS-1: showed
        [confirm state output heard reply action install mic health], missing
        ['guard']` on all three. A monitor that never wrote a line at all is
        told apart from one that went dark, because those are different
        repairs: a surface that was never built versus a plate that never lit.
      · **COMPOSED FRAMES, not the `--instant` replay this item asked for,
        and the reason is a measurement.** Every recorded session in
        `harness/fixtures/sessions` carries exactly three topics — audio.vad,
        audio.wake, audio.transcript — because they are recordings of a
        MICROPHONE. Replaying one lights two plates. Eight of the eleven
        frames are byte-equal to a named frame in `tools/hudscreens/sheet.py`
        (restated, with a test reading both, on the same argument `OUTPUTS`
        makes); the three that are new are `guard.verdict`, `compat.install`
        and `brain.response`, because nothing in this repo had ever composed
        one — which is why those three plates had never been fed a real frame
        by anything.
      · **The frame ORDER is load-bearing and is pinned.** `heard` goes dark
        once `speech.state` is stamped after the words (HeardState latches
        `answering`) and `action` goes the same way (ActionState's
        `noteExplained`), so the speaking frame goes FIRST. What the corner
        then shows is a barge-in mid-answer, which is a real state and not a
        contrivance. Republishing the whole set in order keeps it true every
        round: round 2's speaking frame latches `answering`, and round 2's
        transcript changes `transcriptKey` and clears it again.
      · **It republishes because one plate needs it to, and that is also how
        the subscription race stops mattering.** `output` reads jv-context's
        1 Hz snapshot and OutputState calls one older than 3 s stale. A bus
        has no backlog, so a frame sent before the bridge subscribed is simply
        gone and nothing this driver can ask would say when it landed.
      · **The gate now reads the bus, which it deliberately did not.** The old
        reason was good and is no longer true. `services/jarvisd`,
        `services/pylib` and `services/jv-hud-bridge` are declared reads now —
        the three paths a frame travels — so a Rust or bus-client edit pays
        27 s to learn that ten plates still light. A `services/pylib` change
        is now ten suites and this gate.

- [ ] D46. **The bar is the only shell this gate still loads cold, and the
      reason is its wrapper rather than a gap.** `JV_BAR_NIRI` is `--set` into
      `pkgs/jv-bar`, so `niri msg --json event-stream` cannot be pointed at a
      fake without staging the shell — which is the one thing this gate refuses
      (`test_the_gate_loads_the_shipped_binaries_and_stages_nothing`). So
      `linkUp` is false, the workspaces row builds no delegates, and what is
      covered for the bar is the outermost file, the per-screen `Variants`
      delegate and every binding evaluated whatever the state. The measured
      price of NOT having this is exactly the D43 measurement in reverse: a
      throw in the bar's equivalent of `Bus.qml` would report `nothing threw in
      8 lines`. Two shapes worth considering, neither free: a `--set`-able
      override the wrapper honours only when the pinned niri is absent (which
      is a hole in the pinning rule, on purpose, and needs the argument written
      down), or a tiny fake `niri` on PATH plus a wrapper that resolves it at
      runtime (same hole, different door). A third: accept the limit and say so
      where somebody would otherwise read the bar's green as coverage — which
      is what `shells.py` and the script header do today. Raised by D43.

- [x] D47. **One plate cannot be lit by the run that lights the other ten,
      and a second run costs five seconds.** (Done: `11d47c0`.) The HUD is
      loaded twice — the same shipped binary, a fourth quickshell,
      `JARVIS_BUS` pointed at a path that is not a socket, and a corner that
      names exactly `link` on all three monitors. 26.5 s → 31.9 s.
      · **TWO CLAIMS, and the second is the stronger one.** That the HUD says
        it is blind at all: `core/LinkState.qml`'s grace is the whole
        judgement in that file, and until now a HUD that reported instantly,
        or never, passed every gate here. And that the other ten stay DARK —
        every state machine under that corner is built to refuse rather than
        guess, a refusal and a calm machine draw the same nothing, and a
        corner naming exactly one plate is the only reading that tells them
        apart. `|| true` on `MicPlate`'s `shown` is named as
        `unexpected ['mic']` on all three monitors.
      · **The grace is READ, not copied**, unlike `bar_strip_px()` and
        `hud_corner_line()`, and the difference is what each number is for: a
        copy is an expectation the shell must meet, this is a duration the
        wait has to outlast, and a stale copy makes a gate flaky rather than
        red. A 600 s grace injected into the QML ends the run 1 and the
        report quotes the 600 back.
      · **And it is NOT a fourth log's worth of scan coverage**, which is the
        surprise. `JSON.parse("{")` injected into `LinkPlate.qml`'s own
        `text:` binding was reported by BOTH HUD logs, three times each: a
        plate's children are constructed WITH the plate — `visible` and
        `opacity` decide what is drawn, not what exists — so nearly every
        binding under a plate that never shows was already in the D39 scan.
        What this run adds is the STATE. Written into `shells.py` where it
        would otherwise be read as coverage. The fourth log is scanned all
        the same, for the ordinary reason, which is why `scan_targets()`
        iterates ENGINES rather than shells.
      · Two injections could not be built, and both are good news:
        `root.nothing.here` is a qmllint failure in `pkgs/jv-hud`, and a
        throw inside `LinkState`'s `reason` fails four of the HUD's own QML
        tests. The shape that survives a build is the D34/D39 one, which is
        the shape this gate is for.

- [x] D51. **This gate started two brokers and read neither of their logs.**
      (Done — `tools/brokerlog.py`, one invocation per broker at the foot of
      `ops/ralph/shellload.sh`, pointed by `shells.broker_targets()`.)
      · **The rule is stricter than "no ERROR lines", and both halves earn it.**
        Every line has to be a tracing line the broker wrote at INFO or below,
        AND one of them has to say it is listening on the socket this run told
        it to bind. The census is the floor: a log nobody wrote has no ERROR
        lines in it either, which is exactly how the three staged harnesses
        graded themselves clean before D38. `--listening` is per-broker, which
        is why this is one invocation per log rather than one scan over both —
        a reader handed both could only have checked neither.
      · **Refusing a line it cannot PARSE is what makes it more than a level
        filter.** What a Rust process writes when it is not well is mostly not
        tracing: `Error: Permission denied (os error 13)` is what `main`
        returning `Err` prints (recorded from the flake's own jarvisd), and a
        panic in a SPAWNED task does not end the process — it leaves the accept
        loop dead under a run that goes on waiting. Neither has a level to
        filter on, and this reader did not have to predict either shape.
      · **Both halves were injected into the real gate and both went red**,
        in one run, while everything else in it stayed green: `all 4 runs
        loaded and mapped`, four clean `qmlerrors` scans, exit 1. Injection A
        put the recorded anyhow line in front of the frames broker; injection B
        emptied `late-broker.log` before the readers ran. Reverted.
      · **`NO_COLOR=1` covers the brokers too, and the failure direction is
        the better one.** tracing colours its level as well, and a coloured
        broker log parses as NO lines at all — so the census fails and the run
        goes red rather than green. Red for the wrong reason, which is still
        the right way round, and is a fixture rather than a sentence.
      · **The frames broker's socket and log name moved into `shells.py`**
        (`FRAMES_BUS`, `FRAMES_BROKER_LOG`): the reader has to open the same
        file the script redirects, and two spellings of one path is how a gate
        ends up grading a file nobody writes.
      · Cost: **34.8 s**, unchanged — two file reads. 726 tools tests (19 new).

- [ ] D56. **The decode error D51 was named for is below the level the broker
      runs at.** PLAN D51 named "a broker logging a decode error per frame" as
      one of the two faults its reader is for, and that is the half
      `tools/brokerlog.py` cannot see: `services/jarvisd/src/broker.rs` logs it
      as `tracing::debug!("conn {id}: {e}")` and `bin/jarvisd.rs` defaults its
      `EnvFilter` to `info`, so in a shellload run the line is never written.
      MEASURED — with `RUST_LOG=jarvisd=debug` and four 0xff bytes down the
      socket the real broker says
      `DEBUG jarvisd::broker: conn 0: frame too large: 4294967295 bytes`, and
      `test_the_decode_error_this_reader_was_named_for_is_below_the_level_it_runs_at`
      holds all three facts together. The knob is the broker's own
      (`RUST_LOG=jarvisd=debug` on both, in the script, next to `NO_COLOR=1`),
      and the catch is the reason it was not taken here: `handle_conn`'s read
      loop logs at that level on ANY read error, and a publisher killed with
      SIGTERM at teardown could deliver an ECONNRESET rather than a clean EOF —
      which would make this gate flaky, the one thing worse than a gate that
      cannot see a fault. So the decision is whether to raise the level and
      make the reader ignore a *recorded* set of teardown lines (a list of
      excuses, which rots), or leave it and say so. Raised by D51.

- [ ] D57. **`hudscreens.sh` starts a broker too, and nothing reads its log
      either.** D51 is wired into `shellload.sh` alone; the other real-quickshell
      gate runs its own `jarvisd` (it is in that gate's `reads:` list) and has
      the same hole for the same reason — worse, because what it produces is a
      sheet of pictures a human compares, so a broker that stopped serving
      halfway through a 3 m run reads as a HUD that changed. The work is the
      wiring only: `tools/brokerlog.py` already exists, the gate already knows
      its own stage, and the one thing to find out is what its broker's socket
      and log are called. Raised by D51.

- [x] D52. **The corner comes back empty and nothing proves it ever fills
      again.** (Done — `recover()` in `tools/shellload/load.py`, called from
      inside `relink()` while its broker is still up.) The blind run now walks
      the whole outage cycle end to end, and it is the only place in this repo
      that does: **blind → says so → lets go → reports the machine again**.
      Measured, in that order, on one engine's own log:
      `1 plate` → `nothing` → `10 plates`.
      · **The fault it is for is a HUD that is LINKED, SILENT and certain it
        is fine.** The corner going dark is a reading of the SOCKET —
        `core/LinkState.qml` watches `Bus.linkUp`, never the traffic — so a
        HUD that came back linked and then never accepted another frame passes
        D49's census exactly as the shipped one does, and would have been a
        corner that reports a healthy machine as silence forever.
      · **And that is not the frames run's claim again.** This engine has been
        told the link is DOWN half a dozen times (one `{"t":"link","up":false}`
        per failed connect on the bridge's doubling backoff, against the frames
        run's one), every one of which emptied both `BusModel` caches and
        `HealthState`'s roster; then `LinkPlate` was the only thing on the
        surface; then the surface was DESTROYED, because `visible: selfTest ||
        stack.anyLit` and the corner said `nothing`. The ten plates have to
        come back on a surface that was torn down and rebuilt.
      · **Both halves were injected and both went red**, and the second is the
        measurement worth keeping. Pointing the late publisher at the inherited
        `JARVIS_BUS` (the script's broker, not the one the blind HUD can see)
        ends the run 1 — so the census really reads that engine on that bus.
        And making `core/BusModel.qml` drop frames after a SECOND link-down —
        a HUD that survives one outage and not two — ends it 1 while **the
        frames run stays green, D49's dark census stays green, and all 721 of
        the HUD's own headless QML tests pass**. One outage is all any of them
        ever stages.
      · **`HUD_PLATES_LIT` itself, not a copy**: the recovered corner has to be
        the SAME corner, and a third reading of one tuple is the point of it
        being a tuple.
      · **One number was split, and it is a correctness fix rather than a
        saving.** The publisher's `round 1` wait borrowed `HUD_LIT_TIMEOUT_S`,
        which is about a cold Qt building eleven plates; starting a python
        process and connecting to a socket that is already bound is the other
        kind of wait, and there are two publishers now. `HUD_PUBLISH_TIMEOUT_S`
        is 4 s — deliberately not 5, which is `LinkState`'s grace and which
        `test_the_grace_is_read_out_of_the_qml_rather_than_copied_into_this_gate`
        refuses here so that a read stays a read.
      · Cost: **34.8 s**, unchanged — the third act is sub-second. Ceilings:
        the blind engine is now **98 s of 100** (D53 is where the headroom is).

- [ ] D53. **The first quickshell pays for a cold Qt and the other three do
      not, and all four are given 30 s for it.** `READY_TIMEOUT_S` is written
      against the cold-font-cache argument, which is true of engine one and
      false of engines two, three and four — they load 0.40 s after their
      predecessor on a warm cache, measured on every run in the journal. That
      one number is 120 s of the run's 289 s pathological ceiling (D50), and
      it is the cheapest place to shrink it: a first-engine timeout and a
      warm-engine timeout, or a ceiling derived from the previous engine's
      MEASURED load time. Worth doing only with the D50 arithmetic in front of
      you — this is a bound on a hung engine, not a budget, so the value of
      shrinking it is that the bound stays honest rather than that the gate
      gets faster. Raised by D50. **Now load-bearing:** D52 took the blind
      engine to 98 of its 100 s ceiling, so this is the item that has to happen
      before that run grows a fourth act. 30 s of its 98 is a cold-font-cache
      argument that is false of every engine but the first.

- [ ] D54. **The compositor is never asked about the surface that came
      BACK.** `load_blind` reads the screens three times — before, while, after
      (D44) — and the `while` is taken when the corner is showing `link`. Then
      D52's cycle destroys that surface (`visible: selfTest || stack.anyLit`,
      and the dark census requires `nothing` on every monitor) and builds a new
      one for the ten plates, and nobody asks sway anything about it. The HUD
      reserves no space, so that reading is a refutation rather than a proof —
      but it is the one this gate has, and a HUD whose rebuilt surface came
      back with an exclusive zone on it would take a strip off all three
      monitors and pass. One more `check_zone(shell, "while", up=True)` inside
      `recover()`, after the census, is the whole of it; the arithmetic is the
      catch (`engine_ceilings()` has 2 s of room and `MAPPED_TIMEOUT_S` is 8),
      so this is D53's dependent rather than a free addition. Raised by D52.

- [ ] D55. **A plate that came back LIT and EMPTY passes the new census.**
      `test_the_corner_names_the_plates_and_never_what_they_say` states the
      limit deliberately and D52 inherits it whole: the corner line is a list
      of names, so `health` counts as recovered the moment it decides to show
      itself, whatever it has to show. That matters more after an outage than
      before one, because `core/HealthState.qml`'s roster is the thing the drop
      really destroyed — `publishersOf` is rebuilt from heartbeats, and a
      roster that came back with one service in it instead of two lights the
      same plate. The gate cannot read content without either the corner line
      growing a payload (which makes every plate's internals this harness's
      business) or `hudscreens.sh` photographing the recovered corner (3 m, and
      it does not stage an outage). The cheap third option is the one worth
      weighing: a second line the HUD already has the standing to write — how
      many services the health plate is naming — is one number, it is the one
      the outage is most likely to have eaten, and it is a real signal rather
      than a test hook. Raised by D52.

- [ ] D48. **A lit corner threw 25,992 times in about two seconds and nobody
      knows which of two things that measures.** The D43 injection put a
      throwing binding in `Bus.latest()` and the log came back with 25,992
      faults over roughly 2.5 s of a lit HUD. Either the HUD evaluates
      `latest()` some ten thousand times a second while holding still, or a
      binding that throws re-evaluates in a loop until something changes —
      and the difference matters: the first is a §06 problem (the corner is
      supposed to cost nothing while nothing happens) and the second is a
      property of the engine and nobody's bug. Nothing in this repo would
      notice either: `hudscreens.sh`'s idle probe counts Wayland COMMITS on
      the HUD's own side of the socket, which is frames, and a binding that
      re-evaluates without changing its value commits nothing. The cheap
      measurement is a counter in a `var` binding under the same lit corner,
      with the no-broker run as its control. Raised by D43.

- [x] D49. **The HUD is now proved to say it is blind, and nothing proved it
      ever stops saying it.** (Done.) `load_blind` has a second act: a real
      broker on the very socket that HUD has been failing to reach, and the
      corner has to go DARK again.
      · **THE READING IS NOT VACUOUS, and that is why it lives inside
        `load_blind`.** An empty corner is also what a HUD that never lit
        anything looks like — but the blind census has already required the
        NEWEST corner line on every monitor to be `link`, and
        `hud_corner_plates` reads the newest. So the only line that can satisfy
        `HUD_PLATES_RELINKED` is one the HUD wrote after the broker arrived.
      · **THE INJECTION THAT WORKS IS NOT THE OBVIOUS ONE, and that is the
        measurement worth keeping.** `blind: root.waited` in `LinkState.qml` —
        the latch this item is about — cannot be built: two of the HUD's own
        QML tests fail and `pkgs/jv-hud` goes red before the gate runs. The
        element's own suite already covers the element. What it cannot cover is
        `Bus.qml`, the Quickshell half no headless engine can build: dropping
        the bridge's `{"t":"link","up":true}` line there ends this run 1 with
        `HEADLESS-1: showed [link], unexpected ['link']` on all three monitors,
        and takes the frames run down with it. That is the shipped-level shape
        of this fault, and nothing in this repo could see it before.
      · **BOTH OF THE BROKER'S OWN FAILURE PATHS REPORT THEMSELVES.** A bad
        argument comes back as `the broker exited with 2 instead of listening
        on late-bus.sock` plus its stderr; a broker that comes up and never
        binds as `never created late-bus.sock in 4s`. The socket has its own
        short budget on purpose — spending the corner's 16 s on a socket that
        was never there would report the wrong repair — and the broker's log is
        quoted into the census failure too, because a latched plate and a
        broker that refused the bridge read identically from the corner alone.
      · `HUD_BLIND_BUS` is now `late-bus.sock`: nothing creates it while the
        blind census runs, and then something does. The wait is derived, like
        the grace — `bridge_max_backoff_s()` reads `MAX_BACKOFF_S` out of
        `services/jv-hud-bridge`, because by the time the broker appears the
        bridge's backoff has doubled its way to the ceiling and the socket can
        arrive one instant after a failed attempt.
      · The broker's own log is NOT scanned: `tools/qmlerrors.py` reads what a
        QML engine said, and a Rust tracing line under it would be graded by a
        reader of the wrong language (see D51).
      · Cost: 34.8 s against 32.0 s before — 2.6 s for the second act.

- [x] D50. **The gate's worst-case ceiling was 2 s from its own limit, and the
      next wait anybody added would have broken the test rather than the
      gate.** (Done, and it found a hole rather than only moving a number.) The
      ceiling is per-ENGINE now — `engine_ceilings()` in
      `test_shellload.py`, one entry per engine in `scan_targets()`, asserted
      against `ENGINE_CEILING_S = 100` — because that is the claim that stays
      true as runs are added: this gate starts a fresh quickshell per reading
      and no one of them may hang for minutes.
      · **AND THE OLD SUM WAS NOT THE WORST CASE.** It left out
        `READY_TIMEOUT_S` entirely — 30 s per engine, 120 s of the run — and a
        quickshell that comes up and then says nothing is exactly the run a
        ceiling is for. It was the one run the ceiling did not cover.
      · The per-engine numbers today (moved by D52, which split the
        publisher's wait off the corner's and added a third act): 54 s for the
        bar and the notifier (`READY` + three mapped readings), 78 s for the
        frames run, 98 s for the blind run — the grace, the socket, the corner
        going dark, then a publisher and the corner lighting again. That last
        is 2 s from the limit: **the next act added to the blind engine does
        not fit, and D53 is where the room is.** `RUN_CEILING_S` is
        asserted too, and only to keep it exactly four times the per-engine
        bound: the engines are sequential, so a per-engine ceiling is not a
        ceiling on the run, and a reader who saw only the small number would be
        reading a third of the true worst case (see D53).
      · Neither number is a budget. The MEASURED run is 34.8 s and that is what
        the gate's price claim rests on.

- [x] D44. **"It loaded" is not "it mapped", and nothing asked the second
      question for two of the three shells.** (Done.) `shellload.sh` now puts
      `swaymsg` in the driver's hands and asks the compositor two things no
      log line can answer.
      · **THE MONITORS, once, before any shell.** `WLR_HEADLESS_OUTPUTS=3` and
        the `output` lines in the config were both REQUESTS and nothing read
        the answer. All three shells build one surface per `Quickshell.screens`
        entry, so a run that got one output would have loaded one delegate,
        scanned one surface's worth of log and reported that every shell
        loads. `shells.OUTPUTS` is now checked against `get_outputs`, and it
        ends the run on its own rather than being counted with the shells.
      · **WHAT EACH SURFACE RESERVED, per shell, three times** — before it
        starts, while it is up, after it is stopped. sway shrinks every
        workspace rect by every exclusive zone, so the bar's strip is
        full → shrunk → full on all three monitors and the other two leave
        every monitor whole. The two outer readings are the control that makes
        the 31 missing pixels the BAR'S.
      · **THE BAR'S HALF IS A PROOF OF MAPPING AND THE INSTRUMENT IS LIVE.**
        `exclusiveZone: 0` injected into `shell/jv-bar/shell.qml` → exit 1,
        naming all three monitors and both numbers, while everything else
        about that run stayed green: loaded in 0.40 s, `Configuration Loaded`
        arrived, and the D39 scan said nothing threw on any of the three logs.
        A bar that silently stopped reserving its strip was invisible to every
        gate in this repo.
      · **AND THE LIMIT IS THE SHARPEST THING MEASURED, and not the one
        anybody would have guessed.** A 100 px zone injected into the notifier
        DID bite (2560x1340, 1920x980 — the zone off the bottom edge it is
        anchored to) — but only once the surface was ALSO made `visible:
        true`. With its own `visible: Notifications.anyLit`, false when the
        window is created and true a moment later, the identical zone is
        silently never published. **A conditionally-visible `PanelWindow` gets
        its exclusive zone at creation, and a zone declared while it was
        invisible does not reach the compositor.** Both of these shells are
        conditionally visible, and the HUD with no jarvisd is never lit, so no
        surface of its is created here at all. So: the bar's reading is a
        proof, the notifier's refutes a zone on a surface that was mapped when
        it was born, and the HUD's refutes nothing about today's HUD — it is
        the line that notices the day the corner becomes always-mapped and
        takes space, which is the future the bar already is. Written into
        `shells.py`, the script header and the README, because every one of
        these is a limit somebody would otherwise read as coverage.
      · Free: 25.4 s before and 25.4 s after. `bar_strip_px()` derives the
        strip from `type.label_px + geometry.pad_px * 2` and a test holds that
        equal to `shell/jv-bar/shell.qml`'s own `implicitHeight` expression —
        derived on both sides on purpose, so a change to the type scale the
        bar handles perfectly does not go red.

- [ ] D45. **All three `shell.qml` say `ExclusionMode.Ignore` means a zero
      exclusive zone, and it does not.** Measured while proving D44's
      instrument: the bar built with `exclusionMode: ExclusionMode.Ignore` and
      its `exclusiveZone: surface.implicitHeight` left alone STILL reserved
      all 31 px on all three monitors. What decides the strip is
      `exclusiveZone` (and the anchors wlr-layer-shell will honour one for);
      `exclusionMode` is about whose zones this surface is positioned AROUND.
      So the HUD's "ExclusionMode.Ignore — zero exclusive zone, so no window
      is ever resized", the notifier's copy of it, and the bar's
      "exclusionMode is no longer Ignore (invariant 10)" failure message in
      `tools/hudscreens/shoot.py` are all attributing an invariant-10
      guarantee to the wrong property. Nothing is BROKEN — none of the three
      sets a zone it does not mean — but a comment that names the wrong
      guardrail is the one somebody edits away. Three comment-only edits, plus
      one failure message, plus a rebuild of all three shells; worth its own
      commit rather than riding on the gate that found it. Raised by D44.

- [ ] D42. **`Proc` exists twice now.** `tools/hudscreens/shoot.py` and
      `tools/shellload/load.py` both hold a small class that starts a process,
      redirects it to a file and waits for a line in it — the second is the
      first without the log-offset machinery the frame counter needs. Two
      copies is a coincidence and three would be a pattern; the reason it was
      not extracted with D41 is that `shoot.py` is a declared read of a
      3-minute gate, so touching it to move thirty lines would bind that gate
      to a refactor. The right shape is probably `tools/qmlproc.py` beside
      `tools/qmlerrors.py`, taken when something needs the third copy — and the
      `wait_for` semantics are the part worth sharing, because both files got
      "a process that EXITED is reported as itself rather than waited out"
      right for the same reason. Raised by D41.

- [ ] D35. **A monitor narrower than the corner the HUD reserves gets an
      unbounded row.** `roomPx` negative means "nobody has said" — the right
      default, since a row that hid labels before its surface had a width would
      hide them in the first frame of every session — but the surfaces compute
      `(clock or width - hudReserve) - inset - gap`, which goes negative on an
      output under ~340 px and reads as the same "nobody has said". There is no
      such display; the 640 px shot is the narrowest thing anyone has asked
      about. The fix is a sentinel that is not a number (or a clamp in the
      surface, which is where the arithmetic is), and the reason it is not done
      is that both answers want the one shot nobody can take: a picture of a
      bar on a monitor that does not exist to photograph. Raised by D32.

- [ ] D33. **Two copies of the HUD's box survive D16, and both are outside a
      shell.** The corner's width is one token now and both shells read it —
      but `tools/hudshots/scene/tst_{shots,sequence,fit}.qml` still declare
      `width: 300`, and `tools/hudscreens/sheet.py` still declares
      `SURFACE_W = 300`. Neither is a drift risk today: `hud_surface_box()`
      pins all four to the declaration, and that pin is what D16 rewired. The
      question is whether they should stop being copies. The QML drivers
      could simply say `Theme.hudCornerPx` — they already import Theme — and
      the only argument for the literal is that a driver states the box it
      renders into, which is also the argument for a comment. `sheet.py` is
      the harder half and probably should NOT change: `shot_surface_box()`
      reads that file OUT OF GIT to learn what box the committed PNGs were
      photographed against, and a version of it that read theme.toml would be
      asking today's identity about yesterday's pictures — the exact
      confusion `test_the_shot_box_is_read_out_of_git_and_not_the_working_
      copy` exists to prevent. So: take the three drivers, leave the sheet,
      and write down why in the place that would otherwise look inconsistent.
      Raised by D16.

- [ ] D28. **The refusal D11 added is about PATHS, and the question it stands
      in for is about READS.** `tools/dependents.py` already walks the real
      QML imports and can say that `shell/jv-bar/Workspaces.qml` is read by NO
      gate at all — which is the thing a lived canary discovers after two
      suite runs. Asking it first would turn every "this file is ungradeable"
      into an instant answer rather than an expensive one. Not done with D11
      on purpose: a derived refusal that mis-resolves one import turns a
      working tool into a blocked one, and the canary is the honest backstop
      either way. It wants the import resolution to be trusted first, which is
      a measurement nobody has taken.
- [ ] D9. **Boot path onto §06** — blocked on human review (**R9**). Four
      files: `modules/grub-theme/{theme.txt,background.svg,default.nix}` and
      `modules/plymouth-theme/default.nix`. The real design in it is
      `background.svg`, a checked-in asset with no interpolation, so it needs
      placeholders or a generator. When it lands, its paths come out of
      `COLOUR_EXCEPTIONS` (a test fails if an exception outlives its drift).

## Track A — UI/UX (Quickshell/QML HUD + workspace) — PRIMARY
The HUD is a bus CONSUMER: it subscribes to real topics and reflects them
truthfully. Never fake a sensor/state indicator (invariant 10).

- [x] A1. Quickshell skeleton: a minimal shell that launches under Niri as a
      non-focus-stealing overlay layer (layer-shell, `exclusive_zone` 0, no
      keyboard focus). Prove it loads; qmllint clean. — 49046db
      (pkg `.#jv-hud`, qmllint `-W 0` in checkPhase, user unit installed but
      not auto-started; `JV_HUD_SELFTEST=1 jv-hud` proves the surface maps.
      Still needs a human to eyeball it once on ares — the sandbox has no
      compositor, so "it maps" is verified by construction, not by sight.)
- [x] A2. Theme singleton: a QML `Theme` object holding the blueprint §06 tokens
      (ground #090D12/#0C1116, ember #F0714A, teal #4FB8BF, text tiers) sourced
      from `personality/`. Everything else consumes it. — 6c0eafb
      (`personality/theme.toml` is the source of truth; `tools/gen_theme_qml.py`
      compiles it to `shell/jv-hud/Theme.qml` + `qmldir`; `--check` runs inside
      the jv-hud build, so a drifted theme cannot be built. Tests:
      `bash ops/ralph/runtests.sh tools`.)
- [x] A3. "Jarvis state" HUD element driven by REAL `speech.state` + `audio.wake`
      from the bus: idle / listening / speaking / interrupted. Ember accent only
      when genuinely active. This is the first real, data-backed UI. — 769dcdd
      (`core/SpeechState.qml` decides — 34 tests, 17 mutations run through them;
      `StatePlate.qml` draws a dot and one word and nothing else. `idle` and
      `unknown` both draw NOTHING, so the surface is unmapped unless a frame
      earned it. `listening` is inferred, since jv-ears publishes a window
      opening and never its close: Jarvis answering or an `audio.vad`
      speech_end closes it, `interrupted` does not, and `wakeWindowS` (8 s,
      mirroring ears' `wake_timeout_s`) is only the fallback. Frames are
      refused rather than guessed at — wrong schema `v`, a wake under its own
      threshold, a hedged `conf`, no numeric `ts`. Teal for listening (the open
      mic is yours), ember for speaking. Tests: `bash ops/ralph/qmltest.sh`.)
- [x] A4. Live mic indicator — truthful, not fakeable; nothing on screen when
      no microphone is open. (Camera indicator waits for a vision-phase
      signal.) — 6796579
      (NOT from `audio.vad`/`audio.wake` as this line used to say: those are
      a claim about attention, and jv-ears' VAD runs continuously whether or
      not a wake window is open. The mic is its own claim and needed its own
      signal, so jv-ears now counts what the DEVICE delivers —
      `CaptureMeter` — and reports `mic_open` / `capture_age_s` /
      `captured_s` in sys.health's FREE-FORM `metrics`; no schema change.
      A process being alive is not evidence about a device: that is exactly
      what stayed cheerful through the 2026-09-15 mic outage.
      `core/MicState.qml` decides — 26 new QML tests, 17 mutations caught —
      and refuses rather than guesses: "I cannot tell" never collapses into
      "off". `MicPlate.qml` draws a teal dot and `MIC`, or `warn` and
      `MIC NO AUDIO` when the device is open but silent. Nothing pulses.
      Also landed: `Bus.latestFrom(topic, src)` (sys.health has one
      publisher per service) and a tools test that fails the build if
      Bus.qml forgets to forward a BusModel function. Tests:
      `bash ops/ralph/qmltest.sh`, `bash ops/ralph/runtests.sh jv-ears`.)
- [x] A5. A tiny bus client for QML so HUD elements subscribe to the Unix-socket
      bus without violating invariant 1 (consumer only). — bae8e03
      (`services/jv-hud-bridge` writes one JSON line per envelope; `Bus.qml`
      reads it with `Process` + `SplitParser`. Consumer-only is structural: the
      pump holds a `ReadOnlyBus` with no publish method. `Bus.frames` is cleared
      whenever the link drops. (The singleton was lazy; since A3 an element
      watches the bus at load, so a running HUD always runs its bridge.) Tests: `bash ops/ralph/runtests.sh jv-hud-bridge` — 25, three of
      them against a real jarvisd; smoked against the live bus on ares.)
- [x] A7. Motion primitives on top of A2: an `Ease` Behavior and one
      reduced-motion switch every animated element honours. — 245926e
      (`core/MotionPolicy.qml` decides — tested, 25 new QML tests, 8 mutations
      run through them; `Motion.qml` binds it to real sources and republishes
      the §06 durations already gated; `Ease on color {}` is the one Behavior
      every moving value uses, and its `base` picks how long a move takes,
      never whether it happens. Sources: `personality/theme.toml [motion]
      reduced_motion` + `JV_HUD_REDUCED_MOTION=1/0`. A tools test fails the
      build if any HUD QML file animates without consulting `Motion`, so the
      off switch cannot be bypassed — VERIFIED it bites. Tests:
      `bash ops/ralph/qmltest.sh`, `bash ops/ralph/runtests.sh tools`.)
- [x] A8. Font packaging: theme.toml named Archivo + JetBrains Mono and
      nothing installed either. — 5e5ef8d
      (`modules/fonts.nix` reads the family names out of
      `personality/theme.toml` with `builtins.fromTOML` — the same source
      `tools/gen_theme_qml.py` compiles for the HUD, so the two cannot
      disagree about which faces are wanted. What the module owns is the
      binding from a NAME to something that provides it, and every step
      throws rather than guesses: an unbound family is an eval throw, a
      provider theme.toml does not name fails an assertion, a `family_<role>`
      with no fontconfig generic throws (theme.toml calls the generics the
      fallbacks; a role without one falls back to nothing). The system
      installs the face it CHECKED — each goes through a derivation that asks
      `fc-scan`, the thing that resolves the name at runtime, and fails if the
      family is not in there. "Provides the family", not "every file is that
      family": jetbrains-mono legitimately ships JetBrains Mono NL alongside.
      **The check caught a real one immediately**: as a plain symlinkJoin,
      `fc-match monospace` answered `JetBrainsMono-Regular.woff2`, because
      nixpkgs ships every face three times and fontconfig indexes web fonts
      too — whether a WOFF2 renders depends on how the reading FreeType was
      built. Outline formats only now; 0 woff2 in the built font path.
      `pkgs/archivo` is option (b) from the research: upstream pinned at a
      commit (no tags exist), 66 MiB of source for 3.4 MiB of face, BASE WIDTH
      only, with an install check that all 18 faces report family `Archivo`
      and that the upright Regular is there. Plus `enableDefaultPackages`, so
      the generic fallbacks resolve to something. Two tools gates: no QML file
      may name a family of its own, and theme.toml's faces must equal
      providerOf's keys (the module checks that at eval; tools/tests is where
      it can run without nix, i.e. CI's bare checkout). `Theme.familySans`
      still has no reader — every HUD element is mono, as A8 always said;
      Archivo is packaged because the toml declares it. 11 mutations, 11
      caught. Tests: `bash ops/ralph/runtests.sh tools`.)
- [x] A9. Headless QML tests for the HUD, wired into jv-hud's checkPhase.
      — 4c7c048
      (Quickshell links its QML plugin into its own binary, so its types can
      never load under `qmltestrunner`. The HUD is therefore split:
      `shell/jv-hud/core/` imports QtQuick ONLY and holds the logic —
      `core/BusModel.qml`, the bus state machine, with an injected clock;
      `Bus.qml` keeps the untestable half (bridge process, respawn timer,
      ElapsedTimer) and forwards the API. 27 tests, mutation-checked 9 ways;
      they found a real bug — a NaN clock offset made unknown-age frames read
      as fresh. `nix build .#jv-hud` runs them after qmllint, and a tools test
      fails if anything in core/ imports more than QtQuick.
      **The rule for every element from here: logic goes in `core/`, and
      Quickshell files stay wiring.** Tests: `bash ops/ralph/qmltest.sh`.)

- [ ] A11. Give `Motion.onBattery` and `Motion.fullscreen` real sources. Both
      are live inputs in `core/MotionPolicy.qml` with nothing feeding them, so
      two of §06's three "stop moving" rules cannot be honoured. Needs two
      additive fields in FROZEN schemas (`context.system.on_battery`,
      `context.window.fullscreen`) — proposal **R1** in
      `docs/optimization-backlog.md`. **Blocked on human review; do not build
      this autonomously.** When the schemas land it is one binding each in
      `Motion.qml` plus the jv-context publisher work. Discovered in A7.

- [x] A6. `sys.health` glance: a quiet, edge-docked readout of service health +
      llm rung, 0 fps when nothing changes. — 7406009
      (`core/HealthState.qml` decides — 35 new QML tests, 22 mutations run
      through them — and `HealthPlate.qml` draws the SHORT list: what is not
      well, worst first, and NOTHING when every service heard from says `ok`.
      The roster is who has SPOKEN: nothing on the bus announces which
      services are supposed to be running, so a service that never started is
      absent rather than dead. A heartbeat expires after the two periods the
      schema grants it, on ONE timer armed for the soonest deadline in the
      roster — a HUD with nothing on the bus runs no timer at all. Anything
      unreadable (wrong `v`, hedged `conf`, a body naming another service, no
      `period_s`, a state word outside the enum) is `unknown` and reported,
      and `unknown`/`lost` rank ABOVE `degraded`. The llm rung shows only
      when the brain is on the CPU floor, and never off a stale heartbeat.
      Also landed: `BusModel.publishersOf(topic)`, forwarded by `Bus`.
      Tests: `bash ops/ralph/qmltest.sh`, `bash ops/ralph/runtests.sh tools`.)
- [x] A10. The surface properties that make the HUD safe are asserted, not
      assumed. — fe43c88
      (Three gates in `tools/tests/test_gen_theme_qml.py`: every Quickshell
      window in shell/jv-hud binds `keyboardFocus: None`, `focusable: false`,
      `exclusionMode: Ignore`, `layer: Top`, `color: "transparent"` exactly
      once to exactly that value, `mask` is an EMPTY `Region {}`, and any
      `exclusiveZone` is 0 — qmllint only proved those names RESOLVE, and
      would have been as happy with `.Exclusive`. Per WINDOW, not per file, so
      a second surface is covered the day it is written; it parses each
      window's own lines, so the self-test marker's nested `color:
      Theme.ground` is not mistaken for the surface's. Plus: nothing in the
      HUD may reach for the keyboard, and nothing may wait on a pointer the
      empty mask can never deliver. A gate, deliberately NOT a `HudSurface`
      component — no way to run Quickshell here, so a change to the
      window-creation path would be verified by qmllint and nothing else.
      18 mutations, 18 caught. Also landed: `tools/tests` is a CI job, so the
      theme-drift check and the A7/A15/A10 gates stop depending on the loop
      remembering to run them. Still NOT proven: that Quickshell applies the
      properties — that needs a compositor, i.e. a human on ares. Tests:
      `bash ops/ralph/runtests.sh tools`.)

## Track B — Features / hardening (when UI is blocked, or for variety)
- [~] B1. Pull the next safe item from `docs/optimization-backlog.md` that is NOT
      marked human-review, and implement it under the verify gate. **Checked
      2026-09-24: there is no such item — all 27 are human-review-gated.** Leave
      this here in case a future pass adds auto-safe findings; do not re-check it
      every iteration.
- [x] B2. `jv tap`/CLI ergonomics: small, tested improvements to the debug CLI.
      — 62c440f
      (Every stream is bounded: `-n/--count`, `--for SECS`, Ctrl-C; an unmet
      `--count` exits 1 so `jv` is scriptable. `jv tap --latency` prints a
      per-topic p50/p95/max summary; end-to-end is reported once per utterance
      as time-to-FIRST-word, and the utterance map is a bounded ring. Logic
      moved to `jarvisd::cli`; 30 tests green, 8 of them running the real `jv`
      binary against a real broker. Tests: `bash ops/ralph/cargotest.sh jarvisd`,
      gate `nix build .#jarvisd`.)
- [x] B4. `jv act-log` / `jv confirm` are tested, and act-log stopped lying.
      — 3a3e8ec
      (Reading/tailing moved into `jarvisd::cli` — `act_log_render`,
      `act_audit_path_from`, `act_log_exit_code` — and an unreadable line is
      now RENDERED, warned about, and exits 1 instead of being skipped in
      silence: the line most likely to be torn is the last one written, i.e.
      the action that was running when something went wrong. `jv confirm`'s
      frame is pinned against the frozen `action.confirm` v1 binding, since
      jv-act acts only on kind=answer + answered_by=cli. Fallout:
      `broker::from_value_named` (the bus spells enums as snake_case strings,
      which `rmpv::ext::from_value` refuses — no Rust consumer could read a
      generated body back) and `common::subscribe_live` (the broker does not
      ack a Sub, so subscribing then spawning a one-shot publisher was a
      latent flake). 46 tests green, 14 mutations caught. Tests:
      `bash ops/ralph/cargotest.sh jarvisd`, gate `nix build .#jarvisd`.)

- [x] B5. `jv act-log` can be asked a question. — da134b9
      (`--since` — a duration back from now, 10m/2h/90s/3d, or a UTC
      timestamp — plus `--failed` and a repeatable `--outcome WORD`, the two
      of them mutually exclusive since `--failed` IS `--outcome` negated.
      ONE rule governs it: **a filter narrows what is shown and never hides
      what it could not evaluate** — an unreadable line has no ts and no
      outcome, a missing/nonsense `ts` cannot be proven older than the
      cutoff, a non-string `outcome` has not been shown to be `ok`; all
      three survive every filter and print `?` in the column the filter was
      about. A `--failed` view quietly missing the damaged entries is the
      same lie `act_log_render` already refuses about a torn line. Filters
      run BEFORE `--tail`, so `--failed --tail 1` is the newest FAILURE.
      Exit follows grep: a question nothing answers exits 1 and prints
      nothing (on a healthy machine "nothing failed" is the good answer),
      which is also the only thing between a typo'd `--outcome denyed` and a
      reassuring empty listing — so the words are deliberately NOT validated
      against jv-act's enum (a second hand-copy of a human-review-only file,
      and an old `jv` would refuse to display a record it did not
      recognise). `--tail` is a window, not a question, so `--tail 0` still
      exits 0. Wall clock, not `ts_mono`: `ts_mono` restarts at every boot
      and no human can type one. `iso_to_epoch` is the hand-written inverse
      of jv-act's `now_iso` (no chrono for one date function) and refuses an
      offset rather than ignoring it. 57 tests green (was 36), 27 mutations,
      27 caught. Tests: `bash ops/ralph/cargotest.sh jarvisd`.)

- [~] B8. WITHDRAWN — the premise is false, found while picking work in
      iteration 45. B8 assumed "jv-guard and jv-compat write their own
      records"; they do not. Nothing under `services/jv-guard/` or
      `services/jv-compat/` opens a file for writing, and neither has a
      state dir (`JARVIS_STATE_DIR` is set for one unit only) — both
      services publish their lifecycle on the bus and are read from there
      (`guard.verdict` by the HUD since A51, `compat.install` by nobody
      yet, which is A52). So there is no second caller for a shared record
      reader because there is no second record. If one is ever written,
      the shared-reader idea is still the right one; it is not a task
      today. Discovered in B5, withdrawn in B19's iteration.
- [x] B6. jv-brain subscribes to `audio.wake`: a barge-in stops the answer,
      not just the speaking of it. — 4d05900
      (A spoken turn runs as a CHILD task of the input worker, so the wake
      cancels THAT answer and not the worker that must handle the utterance
      the wake belongs to; `_respond` catches its own cancellation and
      returns what it said, while a cancellation this service did not ask
      for — shutdown — still propagates. An interrupted turn publishes NO
      `brain.response`: `finish_reason` is frozen at stop|length|error, and
      "stop" would claim the answer finished while "error" would blame the
      LLM for obeying the user (proposal **R3** asks a human for the word;
      until then the count rides in sys.health's free-form `metrics` as
      `barge_ins`). The turn is still RECORDED, with a marker, and it
      records what was SENT — jv-voice drops the tail it never played.
      `Conversation.repair_open_tool_calls` answers the tool calls a turn
      cancelled mid-tool left open, which a chat template refuses: one
      interruption would otherwise poison the conversation for the whole
      session. A SILENT turn is not cancellable (a wake does not say the
      CLI stopped wanting its answer), and a wake is acted on unless the
      frame refutes itself. 50 tests green (was 37), 13 mutations, 2 missed
      and both real. Tests: `bash ops/ralph/runtests.sh jv-brain`,
      `bash ops/ralph/runtests.sh jv-voice`.)
- [ ] B7. jv-ears now has a place to state its tuning (sys.health `metrics`,
      A14), and two more constants could one day be mirrored by another
      service the way `wake_timeout_s` was: `wake_refractory_s` and
      `suppress_tail_ms` (the half-duplex tail, which jv-voice's turn
      timing is implicitly tuned against). Publish them WHEN something
      actually reads them, not before — a gauge nobody consumes is noise
      on the bus and a second thing to keep true. Noted so the next
      hand-copied constant is recognised as one. Discovered in A14.
- [x] B3. More replay-harness fixtures for perception (recorded-session
      tests). — d2f9634
      (The harness had existed since Phase 3 with nothing recorded in it.
      `harness/fixtures/sessions/` now holds four: what the REAL pipeline
      — real openWakeWord, real Silero VAD, real faster-whisper —
      published while listening to each committed fixture WAV, so the
      requirements REVIEW-ears.md states are asserted twice: against the
      live models when installed, and against the recording ALWAYS, on a
      machine with no weights. `ts` is `EarsPipeline.clock()` (the sample
      clock, formerly a private `_t()` with no callers), so a session
      reproduces to the sample and a diff means perception changed rather
      than the machine being busy — and the header's `boot_id` is the
      `sample-clock` SENTINEL, because borrowing a real one would claim,
      in the field that exists to check the claim, that these ts line up
      against a live recording. `harness/session.py` is now the only
      reader of the format and can be asked `problems()`: envelope keys,
      closed bodies, required fields, `v`, and per-`(src, topic)` ts/seq
      ordering — all off the GENERATED bindings, never a hand-copy of
      schemas/. An unknown topic and a seq gap are deliberately NOT
      problems (the B5 rule: never refuse to show what you merely do not
      recognise). Nothing rots quietly: with models installed jv-ears
      re-records every WAV through the generator's own `frames_for()` and
      compares which frames arrived, when, and in what state, plus the
      normalized finals — not model scores, not partial texts, which are
      float noise from the machine that ran it. 78 harness tests green
      (was 3), 36 jv-ears (was 32). Tests:
      `bash ops/ralph/runtests.sh harness`, `... jv-ears`.)

- [x] B9. The HUD's QML tests hand-type the JSON lines the bridge writes;
      B3 means there are now REAL recordings to hand them instead. — 36a486d
      (`tests/tst_sessionreplay.qml`, a new file rather than an addition to
      `tst_speechstate.qml`: it shares no helper with it — a replay sends
      recorded lines, not composed ones. Each session goes through
      `core/BusModel` + `core/SpeechState` and the trajectory is asserted in
      the recording's own seconds — clean `unknown -> listening@1.44 ->
      thinking@3.76`, pause `1.36 -> 6.64` across 1.2 s of real mid-sentence
      silence with NO flicker (the trajectory is every change, so a flicker
      is two extra transitions), no-wake `unknown` start to finish. Two
      assertions are about the coupling and need real data: the recorded
      wakes clear SpeechState's self-consistency bar with openWakeWord's own
      score/conf (a 0.995 bar fails on BOTH the music bed's 0.963 and the
      quiet room's 0.990), and the longest recorded utterance (5.28 s) fits
      inside ears' 8 s `wake_timeout_s` — tune that below what a person says
      and a test fails instead of the plate blanking mid-sentence. QML cannot
      read a repo file, so `tools/gen_sessions_qml.py` compiles the
      recordings verbatim into `tests/Sessions.qml` — A2's theme pattern,
      with `--check` in the jv-hud build (VERIFIED: moving a wake 0.2 s fails
      the build). The generator knows nothing about schemas and is
      stdlib-only on purpose, so it runs under the build's plain python3 and
      CI's bare checkout. 250 QML tests (was 238), 52 tools tests (was 30).
      Tests: `bash ops/ralph/qmltest.sh`, `bash ops/ralph/runtests.sh tools`.)

- [ ] B10. Every trajectory in the replay test ends in "thinking" and then
      times out, because the committed sessions are jv-ears ALONE — nothing
      in the repo records a whole turn. Record one session off the LIVE bus
      on ares during a single real spoken turn (`harness/record.py` has
      always been able to; `live_header()` exists for exactly this), commit
      it, and the HUD replay gets the other half: `speaking`, the gaps
      between streamed sentences, the return to idle. It would also be the
      first committed session containing `sys.health`, which is why
      `MicState` and `HealthState` cannot be replayed at all today. Needs a
      human at the machine for one utterance — the SAME ask as the standing
      "nobody has looked at the HUD" item, so ask for both together.
      Discovered in B9.

- [x] B11. `jv health` can be asked a question. — c8b2967
      (`jv health --check` listens for one window — `--for SECS`, default 6,
      a nominal heartbeat period plus a margin — then prints one line per
      service HEARD FROM, worst first, the llm rung when jv-brain reports
      it, and a footer; exit 0 only when every service heard from is `ok`.
      Built on the same three rules as `core/HealthState.qml`, because they
      belong to `sys.health` and not to either reader: the roster is who has
      spoken, a heartbeat speaks for two of its own periods, and unreadable
      is `unknown` and ranks above `degraded`. Silence is NOT an all-clear —
      a bus nobody heartbeats on exits 1 — and `--check` conflicts with
      `--count` so a usage error (exit 2) is never read as "not well". 51
      unit + 27 integration tests, 22 mutations, 22 caught after two real
      survivors were fixed. Tests: `bash ops/ralph/cargotest.sh jarvisd`.)

- [ ] B12. `jv health --check` can say a service is not well and can never
      say one is MISSING: on a machine where jv-ears died at boot it prints
      a short, clean, exit-0 report. That is exactly R5's gap, now arriving
      in a SECOND reader — which is what R5 said it was waiting for, so the
      proposal is worth a human's attention with two callers behind it
      rather than one. Nothing to build until `sys.roster` exists; when it
      does this is one more section in the report and one more reason to
      exit 1. Discovered in B11.

- [x] B13. The one number the Phase 1 budget is judged on stops containing
      the user's own voice. — ee96c43
      (`jv tap --latency` printed "VAD start -> first speech.say" and
      nothing else, so the 5.4 s measured on ares on 2026-09-15 could not
      be held against the 2.5 s budget at all: 2-3 s of it was the user
      speaking. A turn is now split at the boundaries jv-ears itself
      publishes — `spoke` (you, talking), `hold` (its `vad_min_silence_ms`,
      the silence it deliberately sits through to bridge a mid-sentence
      pause), `respond` (ASR + brain + bus) — with a p50/p95/max per span
      and a stated rule: the machine's share is `hold + respond`. It does
      NOT re-state the budget; which span the 2.5 s applies to is a human's
      call, and the point is that the call can now be made against data.
      The hold is read off jv-ears' `sys.health` `metrics`
      (`vad_min_silence_s`, added for this reader — the free-form section
      `wake_timeout_s` already uses, so no schema change; B7's rule is
      "publish when something reads it", and this is the reader). There is
      deliberately NO fallback to ears' default, unlike the HUD, which has
      to draw something: an instrument that substitutes a constant for a
      reading is how a number stops meaning its label, so an unheard
      budget prints `?` and the table says which gauge was missing. Two
      real bugs fell out: an `audio.transcript` partial — emitted PART-WAY
      through an utterance — was allowed to define its start, silently
      measuring those turns short, and the one integration test covering
      any of this published `{"kind": "speech_start"}` on `audio.vad`,
      where the schema says `event`, which nothing noticed because the old
      reader never looked at the field. Anchored on the frames' own `ts`
      now rather than on when the tap got round to them. 63 unit + 31
      integration tests (was 57 + 27); seven mutations, one real survivor
      fixed. Tests: `bash ops/ralph/cargotest.sh jarvisd`,
      `bash ops/ralph/runtests.sh jv-ears`.)

- [x] B14. `respond` stops being one number over two services. — f7f1572
      (`jv tap --latency` splits `respond` at the `audio.transcript` final
      into `hear` — jv-ears' ASR — and `think` — jv-brain to its first word,
      plus a bus hop each way. No new publisher, no schema change: jv-ears
      runs whisper AFTER publishing `speech_end` and publishes the final
      when it is done, so that frame IS the seam. The final is an anchor
      INSIDE a turn and not a boundary, and is treated as one: it annotates
      an utterance `audio.vad` already bounded and never conjures one, only
      `kind: final` counts, and a seam that does not sit inside the span it
      would divide refuses BOTH halves rather than publishing a negative.
      An utterance with no final — jv-ears publishes none for one its ASR
      read as empty — prints `?` for both and keeps `respond` whole.
      Fixed on the way: `silent_broker()` in the tests was not silent. A
      tokio interval's first tick fires IMMEDIATELY, so jarvisd published a
      heartbeat at t=0, before its accept loop had taken a connection —
      reaching nobody on an idle machine and whoever was already accepted
      on a busy one. The new tests' load made that deterministic; the first
      beat is now due one whole period in. 71 unit + 8 bus + 32 integration
      (was 63 + 7 + 31), green five consecutive times; 11 mutations, 11
      caught after two real survivors were fixed. Tests:
      `bash ops/ralph/cargotest.sh jarvisd`.)

- [x] B16. `think` stops being one number over the model and the queue.
      — ceca526
      (jv-brain states the one moment nothing on the bus marks — when the
      completion request went out — as `llm_first_say_ms` plus a turn
      counter `llm_first_says` in its `sys.health` `metrics` (free-form by
      schema, so no schema change). `jv tap --latency` divides `think`
      into `model` (request -> first `speech.say`) and `wait` (the two bus
      hops, the input queue, and jv-brain's own pre-LLM work), as two
      table rows and one short second line per turn — the `>>> turn` line
      itself is deliberately no wider while B17 is open. Three refusals do
      most of the work: a turn that ran TOOLS publishes no gauge at all
      (tool time, confirm window included, is inside `think` and is not
      the model's, so the table prints `think unsplit` and names the gauge
      it wanted); the gauge is bound to its turn by frame ORDER, because
      jv-brain heartbeats immediately after the word it measures on the
      same connection, with the counter telling a fresh gauge from the
      same number re-stated on the next periodic beat; and the FIRST count
      a tap sees is recorded and not consumed, because it may describe a
      turn from before the tap connected. jv-brain 57 tests (was 53),
      jarvisd 82+8+34 (was 71+8+32); 18 mutations, 3 real survivors, all
      pinned. Tests: `bash ops/ralph/runtests.sh jv-brain`,
      `bash ops/ralph/cargotest.sh jarvisd`.)

- [x] B18. `jv health --check` answers "is generation slow right now?"
      without starting a tap and speaking to the machine. — 4bd95fd
      (The `llm` line gained `first_say=<ms> turn_age=<s>`, the gauge's
      second reader, which is what B7 says a gauge needs. The wording
      care this item asked for became the feature: jv-brain re-states the
      same number on every periodic beat forever, so the AGE is
      load-bearing, and it comes off `llm_first_says`. The count rose
      inside the window -> the turn is the frame that raised it and the
      age is a measurement (`turn_age=1.5s`); it never moved -> the turn
      predates the first heartbeat we read and the only honest statement
      is a lower bound (`turn_age>=6.0s`). Three more refusals, each with
      a test: the FIRST count is never fresh (it may predate the
      connection — the tap loop's rule), a count going BACKWARDS is a
      restart and not a newer turn, and a readable beat that dropped the
      gauge takes the number with it. `turn_age` and not "idle" because a
      tool turn publishes no gauge. jarvisd 89+8+36 (was 84+8+34); five
      mutations, all caught. Tests:
      `bash ops/ralph/cargotest.sh jarvisd`.)

- [ ] B20. Nothing has read the new `llm ... first_say= turn_age=` line
      on a real turn — the same complaint B17 makes about `>>> turn`, and
      now from the same missing two minutes of a human at a terminal. The
      two questions worth answering together: does `turn_age>=` read as
      "we could not date this" or as noise, and is the line still one
      terminal width once a rung, a backend, a number and an age are on
      it. Cheap to change afterwards — it is one `format!` and its
      tests — and not worth guessing at beforehand. Discovered in B18.

- [x] B19. A tool turn's `think` was the only span in the table with no
      decomposition at all, and the longest one a user can hit. — e8df1a2
      (`tool` is the UNION of the `intent.action` -> `action.result` round
      trips inside a turn's `think` — not their sum, since two outstanding
      requests are one moment of jv-act's time, and not the bracket from
      first request to last result, since jv-brain runs a completion
      between serial calls. It is jv-act's execution AND, for a confirming
      tool, the whole 15 s window it waited in, which is never spoken and
      today reads as a slow LLM. Five refusals, each tested: an unanswered
      request, a round trip outside the `think` it divides, a turn with no
      ASR seam, a turn past `ACTS_PER_TURN = 32` (the runaway tool loop is
      real — backlog #5 — and past the cap the COUNT survives and the
      measurement does not), and a frame that named nobody. `tool_calls`
      rides beside `tool_ms` because "no tool" and "a tool nobody could
      time" both print `?`. B17's width worry is respected: it prints its
      own line, like jv-brain's `wait`/`model` split, and `>>> turn` keeps
      its six numbers. No new publisher, no schema change. 106+8+38 tests
      (was 89+8+36), 13 mutations, 13 caught. Tests:
      `bash ops/ralph/cargotest.sh jarvisd`.)

- [x] B21. `tool` is one number over a window that is mostly the human
      deciding, and the half a faster machine could never shorten is
      exactly the half it cannot name. — cd47fde
      (`you` is the UNION of the `action.confirm` request -> answer
      windows inside a turn, and `ran` is `tool - you`. The seam that
      worked was NOT the one this item guessed at: `action.result`'s
      `duration_ms` is measured from jv-act's `t0`, BEFORE the
      confirmation, so it is the whole request including the wait — the
      same number, not its complement. The two `action.confirm` frames
      are, and they carry the `request_id` `intent.action` already named,
      so the join is `action.result`'s. Five refusals, each tested: no
      question asked (not a 0 ms window), a question still open when the
      reply landed, a window not NESTED inside its own call's round trip
      — which is also what makes `ran` a subtraction that cannot go
      negative — a `tool` nobody could measure, and a question for a
      request this tap never saw. jv-act ECHOES the answer it acted on
      onto the topic `jv confirm` publishes on, so one decision is two
      frames and the earliest is when the user stopped deciding. Its own
      line under the `tool` line; `>>> turn` keeps its six numbers. Also
      closed a hole in B19's width check, which filtered out 4-space
      indented lines and would have exempted these two rows from it.
      119+8+39 tests (was 106+8+38), seven mutations, seven caught.
      Tests: `bash ops/ralph/cargotest.sh jarvisd`.)

- [x] B22. B17's complaint now has a machine-checked half and an
      unchecked one. — dd0857b
      (The assertion was written first and failed at 133 columns — and not
      because of the id. The line was already 96 with the five-character
      id every test used: six numbers plus a label each do not fit a
      terminal at all, so B22 could not be closed by adding a test. A
      turn's report is now a LADDER, each rung dividing a span the rung
      above it valued — `total spoke hold`, `respond is hear + think`,
      `think includes tool`, `tool is you + ran` — in one grammar (`X is
      A + B` for a partition, `X includes Y` for a share) that
      `brain_split` already spoke. `Turn::lines` owns which rungs exist
      and in what order, so no rung can name a span no printed line
      valued; `confirm_line` gained a `think` guard so that holds of the
      TYPE and not only of its one caller. `short_id` caps the id at
      `ID_COLUMNS` = 11 — eight characters and `...`; an id that fits is
      never touched, and two ids that start alike print alike, which is a
      test and not a silence. The width test runs at the widest input
      that can reach these lines and names each bound: the id is capped
      by construction, both counts are two digits via `ACTS_PER_TURN`,
      and six-digit spans (16.7 minutes) are the one bound assumed rather
      than enforced. It carries A34's kind of control — a line far UNDER
      budget fails too. Tables held to the same 80. Also fixed a
      PRE-EXISTING flake: the confirm test compared three independently
      rounded numbers with `< 1.0` where the rounding error is exactly 1.
      124+8+39 tests (was 119+8+39), twelve mutations, twelve caught.
      Tests: `bash ops/ralph/cargotest.sh jarvisd`.)

- [x] B23. The per-frame `jv tap --latency` hop line was the one line the
      tap writes as a REPORT that B22's width test could not reach. — d932b42
      (`cli::hop_line`, beside the `HopStats` that accumulates it. The hole
      was not cosmetic: `{topic:<20} {src:<12}` PAD and do not truncate and
      `validate_envelope` bounds a topic's alphabet and a src's emptiness and
      NEITHER one's length, so a remote process chose how wide that line came
      out — `jv-hud-bridge` at 13 was already one past its column. Both are
      clipped now at named columns with `short_id`'s own `...`, which is why
      `short_id` collapsed into the `clip(s, columns)` it always was.
      `TOPIC_COLUMNS` = 22 serves BOTH views of a topic, the stream and the
      table under it — the value of either is that its columns line up, and
      one cap answers both; the stream grew 20 -> 22 to meet the table, so
      they agree for the first time. Assumed rather than enforced, and said
      so: `seq` eight digits and the hop eight columns, 16 of the 80 spare.
      Tests: 125 lib (was 124) + 39 e2e; nine mutations split across the two
      files, because a width assertion ALONE cannot catch `bin/jv.rs` keeping
      its own `format!` — every real topic fits either column — so the e2e
      pins WHERE the columns fall. Verified on the built binary against a
      real broker at 64 columns.)

- [x] B24. Clipping the hop TABLE's topic buys alignment and sells
      something the stream does not have to sell: two topics sharing their
      first 19 characters become two rows with the SAME label. — b7dea79
      (`table_topic_columns` picks the SMALLEST width from `TOPIC_COLUMNS`
      up at which every printed label is distinct, so identity outranks
      alignment in the table and only there. Nothing this bus carries
      moves it — `audio.transcript` is 16 of the 22 — so the common case
      is byte-identical and the table still lines up under the stream.
      Three things stated rather than left to the loop: growth is minimal
      (the test pair separates at 27, not 26, and 27+39 = 66 still fits);
      the search always terminates, because the topics are map keys and at
      the longest one's own length nothing is clipped; and PRINTED labels
      are compared, never the topics — comparing topics is tautological
      and the column would never grow. The width trade is pinned where it
      costs something: a test builds a pair that separates only past
      column 41 and asserts the rows go OVER `TAP_COLUMNS`, so the day
      someone tightens the width gate they are told which rule they are
      reversing. Corrected mid-iteration: a clipped label colliding with a
      WHOLE one needs a topic ending in `...`, and `validate_envelope`
      refuses an empty segment, so that case cannot reach a live tap — the
      test is kept and says so. 128 lib tests (was 125) + 39 e2e; seven
      mutations, all caught. Verified on the built binary against a real
      broker. Tests: `bash ops/ralph/cargotest.sh jarvisd`.)

- [ ] B25. The STREAM has the collapse B24 just closed for the table, and
      no cheap way out. Four frames on `context.window.changed.alpha` and
      `.beta` print four identical `context.window.chan...` lines above a
      table that now tells the two apart — verified on the built binary,
      not argued. The table could widen because it sees every topic it is
      about to print; a streamed line is written as a frame ARRIVES and
      cannot know what comes later, so the same fix does not exist here.
      Three options and none is free: (a) leave it — the frame is one
      `jv sub '*'` away whole, which is B23's standing answer and is why
      this is not a bug; (b) buffer the stream, which costs the one
      property `--latency` has (it prints as it happens); (c) clip from
      the MIDDLE (`context.win...hanged.a`), which separates prefix-alike
      topics with no lookahead and costs every reader the column they
      currently trace. A second cost of (a), now measured: when the table
      widens, the two views stop sharing a column boundary, so a reader
      tracing a topic out of one into the other has to re-find it. Worth
      an answer the day two topics on this bus share 19 characters —
      nothing does today. Discovered in B24.

- [x] B26. `dialog.listen` had no consumer: jv-act published it on every
      confirmation and jv-brain on every onboarding question, and jv-ears
      subscribed to `speech.state` and nothing else — so the one approved
      exception to wake-every-time had never once opened, and every
      spoken "yes" needed "hey jarvis" in front of it. — 4c4d350
      (`jv_ears/dialog.py` holds the window on the SAMPLE clock, the
      pipeline advances it once per chunk, and an utterance that STARTS
      inside it is gated without a wake. Three rules with plausible
      alternatives rejected: only TIME closes it (a window that shut
      itself after one utterance would be ears deciding the answer had
      arrived, which is the interpretation the approved decision keeps
      out of a perception service); it governs where you may START, so a
      deadline does not cut off a sentence under way and a window opening
      mid-sentence does not reach back the way a wake does; half-duplex
      outranks it, which is the ORDINARY case since jv-act asks while
      jv-voice is still speaking the question. Every refusal points at
      "closed" — unknown `v`, hedged `conf` on a command topic, unaudited
      reason, non-object body, empty `listen_id`, a `window_s` that is
      not a bounded positive number (`True` included). The cap, the
      reasons and the required-field list are read off the frozen schema
      by tests. Tests: `bash ops/ralph/runtests.sh jv-ears` 104, was 37;
      13 mutations, 13 caught; verified on the built closure against a
      real broker, where the same WAV went from silent to a final
      transcript on one `jv pub dialog.listen`.)

- [ ] B27. **The HUD half, and it is the loop's own to take.**
      `schemas/dialog.listen.json` says of its `reason` field: "audited,
      and the HUD will show it (sensor truthfulness, invariant 10)".
      Nothing shows it, and as of B26 the microphone really does open
      without a wake word — which is precisely the state invariant 10
      exists to make visible. `MicPlate` cannot answer it: it says the
      DEVICE is capturing, which it is all day; `StatePlate`'s
      "listening" is wake-driven and must stay that way (a no-wake window
      forges no `audio.wake`, and a test says so). The obstacle is the
      interesting part and it is not cheap: `dialog.listen` is a REQUEST.
      A plate drawn from it would show what jv-act ASKED for, not what
      the microphone is doing — the fakeable indicator invariant 10
      forbids, and it would be wrong in exactly the cases B26 spent its
      tests on (a refused frame, a window that expired, a window
      half-duplex is sitting on). Only jv-ears can say the window is
      open, and today its only voice is a 5 s heartbeat against a 15 s
      window, so a `sys.health` gauge would be up to 5 s late and 5 s
      stale on a plate whose whole job is to be true NOW. Three options:
      (a) an `ears.listen` state topic — a schema change, human review,
      and the honest shape; (b) the heartbeat gauge, accepting the
      granularity and drawing the plate only while the gauge is fresh;
      (c) leave it and write down that the HUD is silent about no-wake
      windows. Do not build (b) before deciding — a late plate about a
      microphone is the one kind of late this HUD has never shipped.
      Discovered in B26.

- [ ] B28. The window is invisible to `jv health` and to the audit for
      the same reason B27 is stuck: it exists only inside the ears
      process. The schema calls `reason` "audited" and nothing audits it
      — jv-act writes its own audit line for the confirmation, but
      whether the microphone actually opened, for how long, and whether
      ears REFUSED the frame is recorded nowhere at all. A refusal is the
      case that matters: a jv-act whose window never opened looks exactly
      like a user who said nothing, and the difference is a bug report
      nobody can file. Smaller than B27 and it shares B27's decision —
      if (a) lands, both are answered by the same topic. Discovered in
      B26.

- [x] B29. `NiriBackend` handled three of niri's four window events, and
      the missing one is the FIRST thing niri sends. — f00273f
      (`WindowsChanged` is the authoritative full window list —
      field-verified on ares as the third line of a live event stream,
      carrying the 3 windows already open. Dropping it meant: the first
      event about every pre-existing window said `opened`; a close or a
      focus of one carried `app_id: ""`, and the schema says
      focus_changed frames are what jv-act resolves "this window"
      against; and nothing said which window had focus until the user
      switched. The rule: events are forwarded, a RESYNC publishes only
      what it CHANGES — never `opened` for a window it cannot date,
      never `closed` for the difference between two lists. It seeds the
      id -> (app_id, title) cache and publishes the one `focus_changed`
      that makes "this" resolvable. `WindowFocusChanged {id: null}`
      publishes nothing (the frozen schema requires `window_id`) and is
      still forgotten, or the next resync dedups against a stale answer.
      Titles from a resync are redacted at publish like any other; two
      tests say so. Tests: `runtests.sh jv-context` 41, was 13 — the
      parser had ZERO coverage, and `events()` is now driven over a real
      unix socket; eight mutations, eight caught.)

- [ ] B30. **Human veto, cheap either way.** The resync's `focus_changed`
      is the only frame jv-context publishes that reports a STATE rather
      than a transition: focus did not change at that instant, the
      service merely learned who had it. It was taken because
      `schemas/context.window.json` makes focus_changed the frame that
      DEFINES the active window for jv-act, and the alternative is
      jv-act having no answer to "close this" until the user happens to
      switch windows — but the opposite (stay silent, let the first real
      focus event define it) is defensible and is two lines to revert.
      Discovered in B29.

- [x] B31. `context.window` has a `workspace` field and a `monitor`
      field and the niri backend has never populated either. — 752a834
      (`WorkspacesChanged` is the line ABOVE `WindowsChanged` on connect
      — field-verified on ares — and it is what turns a window's
      `workspace_id` into a name and an output. Tracked like the window
      list: authoritative, replaced wholesale, publishing no frame of its
      own, and resolved at PUBLISH time so a monitor unplugged mid-session
      cannot leave a frame pointing at a screen that is gone. The
      asymmetry is the design: on ares EVERY workspace is unnamed and
      every one has an output, so an unnamed workspace still reports its
      monitor and `workspace` stays ABSENT rather than being filled with
      `idx`, which is per-OUTPUT — three of the four live workspaces were
      `idx: 1`. Tests: `runtests.sh jv-context` 59, was 41; twelve
      mutations, twelve caught. Verified through the BUILT closure against
      the live compositor: the first frame it publishes now says
      `monitor: HDMI-A-1` and no workspace.)

- [ ] B32. **Human decision, and it is the reason B31 publishes half of
      what it could.** Every workspace on ares is unnamed, so `workspace`
      will be absent on every frame this machine ever produces — and
      jv-act's `window.move_workspace` requires a `workspace` STRING that
      nothing on the bus can now supply. Three ways out and they are not
      equal: (a) name the workspaces in the niri config, one line each,
      and the field fills itself (a human's config, not the loop's); (b)
      the schema gains a `workspace_id` or per-output index pair — a
      FROZEN schema change and therefore human review, and it would let
      jv-act target the same workspace niri does; (c) leave it and accept
      that "move this to workspace 2" is unanswerable until (a). Do not
      build (b). Discovered in B31.

- [ ] B33. A `WorkspacesChanged` that MOVES a workspace to another output
      — which is what unplugging a monitor does — publishes no frame, so
      every consumer keeps the old `monitor` until the next window event
      touches that window. The frame is correct when it comes and the
      table is right immediately; what is stale is the bus's last word.
      The fix is the same shape as B30 and wants the same answer: publish
      a `focus_changed` restating where the focused window now is, which
      is a frame reporting a STATE rather than a transition. Cheap either
      way, and it should be decided together with B30. Discovered in B31.

- [ ] B34. The A track's multi-monitor questions (A13/A27/A38 — one
      plate drawn on all three screens) have had no bus data behind them
      and now have some: `context.window` says which output the focused
      window is on. That is not the whole answer (the HUD would have to
      subscribe, and "the screen you are looking at" is not the same
      claim as "the screen the focused window is on" — the Leap and the
      camera are the senses that could say the former, and neither is
      wired). But it turns "there is nothing to drive it" into a design
      question a human can actually answer, and it should be answered
      with A13 rather than before it. Discovered in B31.

- [x] B35. The 1 Hz system snapshot could invent a reading, and could
      stop entirely while the heartbeat went on saying `ok`. — dc04e77
      (`WpctlProbe` returned `(0.0, False)` for an unreadable mixer —
      wpctl missing, exiting non-zero, or printing its own error text on
      stdout — and the HUD's `OutputState` reads `audio_volume <= 0`
      during an utterance as YOU CANNOT HEAR THIS. A plate about a mixer
      nobody managed to read is the fakeable indicator invariant 10
      forbids. Unparseable output was worse than wrong: it raised
      `ValueError` out of `_pump_system`, killing the snapshot task for
      the life of the process, while jv-context stayed alive pumping
      window events — so `Restart=on-failure` never fired and
      `_pump_health` kept publishing `ok` about a service that had
      stopped doing half its job. Now: `ProbeUnavailable` instead of a
      number, a failed tick publishes NOTHING (every field a probe feeds
      is required by the frozen schema, so there is no legal partial
      frame, and a substituted number or a restated old one both say
      more than was measured — the bus's last word ages out, which
      consumers already handle), and the failure MOVES to the heartbeat
      as `degraded` with a note. The beat is immediate on the
      transition, which is what `schemas/sys.health.json` asks every
      service for and what jv-context never did — and only on the
      transition, so a steadily-blind probe does not put 1 Hz onto a
      quiet topic. The unit now names `wireplumber` on its `path` the
      way jv-act does, since `wpctl` is not in this service's closure.
      Tests: `runtests.sh jv-context` 82, was 59; thirteen mutations,
      thirteen caught. Verified through the BUILT closure: the real sink
      reads on ares, and the same binary with wpctl gone says
      `ProbeUnavailable` instead of zero.)

- [ ] B36. `context.system.net_online` is documented as "default route
      exists and resolves" and published as "any non-loopback interface
      is up" — so a cable into a dead switch, or a lone `docker0`, reads
      as online, and the field can only go false when every interface on
      the machine is down. Nothing reads it yet, which is exactly why it
      is cheap now. The fix starts by rewording a FROZEN schema's
      description down to what can be measured without emitting a
      packet, so it is proposal **R8** in `docs/optimization-backlog.md`
      and **human review, not a build**. Discovered in B35.

- [x] B37. `gpu_vram_free_mb` has never once been on the bus on ares. — befd1da
      (`nvidia-smi` lives in the NVIDIA driver's `bin` output, not in
      jv-context's closure, and nothing put it on the unit PATH — so every
      1 Hz snapshot since v1 raised FileNotFoundError and dropped the one
      number behind invariant 6's "6 GB VRAM is a scheduling problem".
      Nothing was lying: the schema makes the field optional and the probe
      degraded to absent. It was simply never measured. The unit now names
      `config.hardware.nvidia.package.bin` the way `jv-llm` already did —
      READING hardware.nvidia, never setting it, so gpu-nvidia.nix and its
      pin are untouched. **Verified through the BUILT closure on ares: the
      shipped jv_context read 943 MiB free of 6144 off the GTX 1660 SUPER,
      cross-checked against nvidia-smi itself.**
      The probe was rewritten around the fact that an OPTIONAL field's
      absence is a CLAIM — the schema says "free VRAM if a GPU is present",
      so absent has to mean "no GPU", not "the reading did not work out".
      `GpuProbe` therefore answers three ways: `None` (no card, not a
      fault), a float, or `ProbeUnavailable` (there IS a driver and it went
      quiet — which now reaches `sys.health` as `degraded` with a note,
      while `context.system` keeps flowing, because one optional field must
      never cost the four required ones). `parse_nvidia_smi_vram` rejects
      what `float()` would have swallowed: `[N/A]`, `[Not Supported]`, NVML
      init errors on stdout, `nan`/`inf`, negatives, and a number printed
      alongside a non-zero exit. A missing binary LATCHES the probe off —
      the PATH is a store path fixed at unit start, so it cannot grow an
      nvidia-smi later, and that is half of backlog 14 gone without
      touching the cadence decision that is the human's.
      Tests: `runtests.sh jv-context` 105, was 82; eleven mutations,
      eleven caught.)

- [x] B39. **jv-brain's VRAM guard has the same probe, with none of the
      fixes, and it is the one that actually decides.** — 05117db
      `jv_brain/launcher.py:probe_free_vram_bytes` shells out to the same
      nvidia-smi query and returns `None` on EVERY failure — OSError,
      timeout, non-zero exit, and `int()` choking on `[N/A]` — and `None`
      goes straight into `pick_rung`, which reads it as "no usable GPU"
      and drops Jarvis to the CPU rung for the life of that llama-server.
      So a driver hiccup at launch is indistinguishable from a machine
      with no card, and the only trace is a stdout line in the unit's
      journal: nothing on the bus, no heartbeat note, and the rung file
      says `free_vram_mb=-1` for both. Its unit DOES have the driver on
      its path (`modules/jarvis-services.nix` jv-llm), so this is not
      B37's bug — it is B37's second half, which B37 deliberately did not
      widen into. The shape to copy is the one jv-context now has: a
      strict parse, and "could not read" told apart from "not there".
      Note it runs ONCE per launch, so backlog 14's fork cost does not
      apply and neither does the latch. Discovered in B37.
      (Three answers now: `measured` / `absent` / `unreadable`. Strict
      parse rejects `[N/A]`, `[Not Supported]`, NVML init errors on
      stdout, `nan`/`inf`, negatives, and a number printed alongside a
      non-zero exit; only a missing nvidia-smi is still a silent None.
      The CPU floor holds for all three — nothing about rung choice
      changes — but the rung file now carries `vram=` and, when
      unreadable, nvidia-smi's own words in `vram_note=`, and jv-brain
      turns its heartbeat `degraded` with that reason attached (never
      erasing a worse note; a GPU-less machine stays `ok`). Writer and
      reader now live together in launcher.py. Verified through the
      BUILT closure on ares under the jv-llm unit's own PATH: the real
      card reads 943 MiB free of 6144 and lands on rung 4 — ares is on
      CPU with a healthy card, which until today was byte-for-byte
      identical to a failed probe. Tests: `runtests.sh jv-brain` 85, was
      57; seventeen mutations, seventeen caught.)

- [x] B40. **The HUD half.** Nothing read `context.system.gpu_vram_free_mb`,
      and as of B37 there was finally something to read — on ares, 943 MiB
      free of 6144 with a healthy card, which is why the brain launches onto
      the CPU rung. — 86cffcb
      (`core/VramState.qml` + one dim row under `HealthPlate`'s rung line:
      `vram 943 MiB FREE`. The rung line has read as a fault since A6 and is
      not one; this is the sentence that says so. Not a gauge — the gate
      `brainOnCpu` is an INPUT fed from `HealthState.llmOnCpu`, so the figure
      is on screen only while something is being paid for the shortage, and
      an unfed VramState is silent; a python test pins the binding, because
      plates cannot be tested headless. Absent stays absent: a card-less
      machine reports `llm_gpu = 0` too, and a defaulted 0 would explain a CPU
      brain with a shortage that never existed. The row is bounded by
      construction — MiB, then GiB, then GiB with no decimal — so no card can
      widen it past the line the 300 px surface was measured against. Tests:
      the headless suite 569, was 536; 20 mutations, 20 caught. Re-shot:
      docs/hud/06-health.png. **The brain half is NOT closed — see B44.**)

- [x] B41. Nothing on the bus ever says WHICH rung the brain is on in
      words. `sys.health.metrics.llm_rung` is a float and `llm_gpu` a
      0/1, so a reader has to know the ladder by heart to turn `4.0`
      into "CPU fallback, replies will be slow" — and the rung file's
      own `label=` (the one human-readable string the launcher writes)
      is read by nobody. — 6f6119b
      (`describe_rung` reads the label into `rung 4 (CPU fallback)`;
      `rung_finding` decides when those words are a FINDING and puts
      them in `notes`, which `jv health` already prints. The half that
      mattered: jv-brain published `ok` while on the CPU rung with a
      healthy card, which is `sys.health`'s own worked example of
      `degraded`. Quiet on a card-less machine and on GPU rungs 1-3.
      Verified through the built closure: 943 MiB free off the real
      card → "llm on rung 4 (CPU fallback) — no GPU layers, replies
      will be slow; 943 MiB VRAM free at launch". Tests:
      `runtests.sh jv-brain` 98, was 85; sixteen mutations, sixteen
      caught. **Raised B43 — a human may want to overrule the verdict
      change.**)

- [ ] B43. **A human's call, not the loop's.** B41 made jv-brain report
      `degraded` while it runs on the CPU rung on a machine that has a
      working GPU, so `jv health --check` exits 1 on ares any day the
      desktop and a browser hold the 6 GB — which is most days, as
      measured (943 MiB free, twice this week). The argument for it:
      `schemas/sys.health.json` names this case verbatim as what
      `degraded` means, invariant 6 exists to keep the 8B Q4 resident,
      and a green check over a brain answering in minutes is exactly the
      lie the health CLI was written against. The argument against: a
      check that is red on an ordinary day is a check people stop
      reading, and the condition is not a fault — it is the ladder doing
      its job. If the answer is "back to ok", the one-line change is in
      `jv_brain.service.rung_finding` (drop `fell` from the state
      escalation, keep the words in `notes`); a middle answer is to keep
      `degraded` but teach `jv health --check` that jv-brain-on-CPU is
      an expected finding. Discovered in B41.

- [ ] B44. **The other half of B40, and a human's call.** The HUD can now
      SEE the card move; jv-brain still cannot. It learns about VRAM exactly
      once, at launch, from its own fork, so it cannot notice the 943 MiB
      becoming 5 GB when a browser closes (a GPU brain is one restart away
      and nothing says so) or becoming 200 MiB when a game starts, which is
      the moment invariant 6 exists for. Reading
      `context.system.gpu_vram_free_mb` in jv-brain is five lines; deciding
      what it DOES with the number is a scheduling change and pairs with
      backlog 14 (the game-launch unload). The smallest honest first step is
      not a reaction at all: publish the live figure alongside the rung so
      `jv health` shows both, and let the human decide whether an unload or a
      relaunch may ever be automatic. (**B46 made the question visible
      rather than answering it**: the HUD now draws the card's free VRAM
      and the ladder's requirement one under the other, so a human can SEE
      the moment a GPU brain became possible. Nothing reacts to it, and
      nothing may until this item is decided.) Do not build the reaction before that
      decision — a brain that unloads itself at the wrong moment is worse
      than a slow one. Discovered in B37, halved by B40.
      **Cheaper after B45**: the threshold the live figure would be compared
      against is now a function jv-brain can call (`launcher.gpu_floor_mb`),
      so "is a GPU brain one restart away?" is one comparison away from a
      `context.system` subscription. It is still the DECISION that is open,
      not the arithmetic.

- [x] B45. The HUD quotes the free-VRAM figure and cannot judge it, because
      the rung ladder's VRAM requirements live in `jv_brain/config.py` and
      are not on the bus (invariant 1 says the HUD may not know them). So
      the one sentence a reader still has to supply themselves is the useful
      one: "5 GB free and still on rung 4 — restart jv-llm and you get a GPU
      brain." One free-form gauge in jv-brain's heartbeat — the VRAM its
      chosen rung actually needed — would let `VramState` say it, and the
      gate for it already exists. Small, and it is jv-brain's to publish, not
      the HUD's to guess. Pairs with B44; do not build it twice.
      Discovered in B40. — 532566f
      (`launcher.gpu_floor_mb` — the least free VRAM at which `pick_rung`
      would still land on the card, a `min()` over the GPU rungs so a
      reordered ladder cannot publish a non-floor, in whole MiB rounded UP
      so it can never claim an early fit. On ares' ladder: **5424 MiB of a
      6144 MiB card**, which is why "5 GB free and still on the CPU" is the
      ladder working and not a fault. Published as
      `sys.health.metrics.llm_gpu_floor_mb` only while something waits on it
      — never while already on the GPU, never on a machine with no card —
      and in words in `notes` next to a measured reading only. Tests:
      jv-brain 109, was 98; 10 mutations, 10 caught.
      **The HUD half is NOT closed — see B46.**)

- [x] B46. **The other half of B45.** jv-brain now publishes the floor
      (5424 MiB) and the HUD does not read it: `VramState` still draws
      `vram 943 MiB FREE` alone, and the comparison that makes the figure
      actionable — free vs needed — happens in the reader's head or not at
      all. The gauge arrives on `sys.health` from jv-brain, which
      `HealthState` already owns (it is where `llmOnCpu` comes from), so the
      wiring is the shape B40 used: `HealthState` exposes the floor,
      `VramState` takes it as an INPUT and never guesses it, unfed means the
      row is exactly what it is today. The hard part is not the plumbing, it
      is the ROW: the 300 px surface is sized to `jv-compat DEGRADED` and
      every branch of `render()` is thirteen characters at its widest by
      construction, so "943 / 5424 MiB FREE" has to earn its width or find a
      shorter true form (`943 of 5424 MiB`? a second dimmer line? the deficit
      — `4481 MiB SHORT` — which is the number a reader would act on and is
      one subtraction from both). Whichever wins, the absent cases stay
      absent: no floor published (brain on the GPU, or no card) must draw
      exactly today's row, never an invented `of 0`. Re-shoot
      `docs/hud/06-health.png` after. Discovered in B45. — 62efed3
      (TWO rows, not one: `vram 943 MiB FREE` over `llm NEEDS 5424 MiB`.
      `n / m` beside the word `vram` is the disk-usage idiom and would
      have been read as *used of total*, and one composed string would be
      the HUD synthesising a claim out of two services' numbers — so one
      row per publisher, each attributable, either able to be absent
      alone. The deficit form was measured and dropped: `4481 MiB SHORT`
      under `vram` is eighteen characters against the seventeen the 300 px
      box is measured to, where `NEEDS ` + eight under a three-letter name
      is seventeen exactly. `HealthState.llmGpuFloorMb` reads the gauge
      (positive and finite only), `VramState.gpuFloorMb` takes it as an
      INPUT and never derives it, and `needKnown` gates on `reporting`, so
      the requirement is never on screen without a reading beside it and
      an unfed HUD draws exactly what it drew before. Requirements round
      UP, measurements round to nearest, both through one shared unit
      ladder. Tests: jv-hud 585, was 569; tools 138, was 137; 11
      mutations, 11 caught. `docs/hud/06-health.png` re-shot.)

- [x] B42. jv-brain's heartbeat re-reads the rung file on every beat
      (`_rung()` in `_health`, once per 5 s, plus once per turn for
      `brain.response.backend`). The file is written once, by a process
      that has already exec'd away, and lives on tmpfs — so it cannot
      change while llama-server lives, and a service that dies is a
      service whose file is stale anyway. Not a cost worth chasing on
      its own (a tmpfs read is nothing next to the 5 s period), but B39
      made it the read that decides a STATE. A torn read fails SAFE
      today — a half-written `rung=` raises ValueError and reads as
      `index=None`, `vram=absent`, which degrades nothing — so this is
      a nicety, not a bug. But jv-brain is only `after=` jv-llm, which
      orders starts and not this write, so the window is real and the
      next reader of this file may not be as forgiving. Worth one look
      at write-temp-then-rename before anything else depends on it.
      Discovered in B39.
      **Sharpened by B41**: something less forgiving now exists, and it
      is jv-brain itself — this file decides a published STATE, not just
      a gauge. A torn read still fails safe (`index=None`,
      `vram=absent`, no finding), but "fails safe" now means "reports
      `ok` while the brain crawls on the CPU". One rename.
      **DONE — 2a81605.** `write_rung_file` writes a pid-stamped temp
      file beside the target and `os.replace`s it in: a reader gets the
      last whole record or this one, never the seam, and a write that
      fails leaves the old record and no litter (the next thing that
      happens in this process is an exec). The mode is explicit (0640)
      instead of umask-derived — that was the second, unlooked-for half:
      jv-llm writes this file and jv-brain reads it, two users in one
      group inside a 0750 runtime directory, so the GROUP read bit is
      the whole of the reader's access and a launcher under a tighter
      umask would hand jv-brain a file it cannot open — failing silently
      in exactly the `ok`-about-a-CPU-brain direction this item names.
      No fsync: /run is tmpfs and a record that outlived the reboot that
      emptied it would describe an llama-server that no longer exists.
      Tests: jv-brain 114, was 109; six mutations, six caught. One
      survivor on purpose — 0644 is indistinguishable from 0640 behind a
      0750 directory, so nothing asserts the other-read bit.

- [x] B38. jv-context is now the only service that beats immediately on
      a state change; `schemas/sys.health.json` asks EVERY service for it
      ("every fixed period, and immediately on state change"). jv-ears,
      jv-guard and jv-brain publish on a timer alone, so jv-ears going
      degraded (`microphone open but no audio`) is up to its full period
      of silence — and `jv health --check` defaults to a 6 s window,
      which is one nominal period plus a margin, so a state change that
      lands just after a beat is a state change that check can miss.
      jv-voice already does it for the error case and not the others.
      Small and mechanical per service, and B35 wrote the shape to copy
      (`_set_fault` + an `asyncio.Event` the health pump waits on with a
      timeout). Discovered in B35.
      **jv-ears half DONE — 3d01c31** (`pump_health` in
      `jv_ears/main.py`: the meter's state is re-read every 250 ms and
      published the moment it stops matching what the bus was last told,
      with a 1 s floor so a flapping device cannot beat at the watch
      rate). B35's shape could NOT be copied: jv-ears' state is a
      function of a CLOCK — a stream stalls by a chunk not arriving — so
      there is no writer to set an Event, and a state nobody announces
      has to be watched.
      What is LEFT is a different job, and that is this item's finding:
      jv-guard and jv-brain ALREADY beat at the instant of their faults
      (`_health("degraded", ...)` in both — a scan with no engine, an
      `llm error`). Their gap is the opposite one — the fault is not
      LATCHED, so the next periodic beat says `ok` again while the
      condition is unchanged. Fixing that changes what the CLI says on an
      ordinary day, which is B43's judgement call again, so it is raised
      as **B47** rather than built. jv-voice is the one service nobody
      has read for this at all.
      **CLOSED — d55348b.** jv-voice was read, and it is jv-guard's and
      jv-brain's case exactly: it beats `degraded` at the instant a
      synthesis or playback failure lands, and does not latch it. So
      every one of the five services now answers B38's question, and
      what is left of the un-latched half is B47's, for a human.
      The reading found a DIFFERENT defect the schema never spells out,
      and that is what the commit fixes: an off-schedule beat did not
      take over the period it landed in. jv-voice, jv-guard and jv-brain
      published and left the period timer alone, so the next `ok` went
      out with whatever was left of the period the fault interrupted —
      at the boundary, nothing. `bus.latest()` keeps one frame per
      publisher, so a truthful `degraded` could be erased before the HUD
      or `jv health --check` could show it. jv-brain paid twice, because
      its first-word gauge beat then ADDED a frame per turn to a quiet
      topic rather than being that period's beat. jv-ears and jv-context
      already had it right, in two shapes sharing no code, and jv-ears
      had written the reason down. That rule is now
      `jarvis_bus.HealthBeat` and the three services beat through it.
      jv-ears and jv-context are deliberately NOT migrated: both obey it
      already in shapes built around their own problems (a watcher with a
      flap floor; an event-driven pump), and unifying correct,
      un-duplicated code is not worth the risk.

- [ ] B47. **A human's call, and it is B43's question in two more
      services.** jv-guard and jv-brain both publish `degraded` at the
      instant of a fault and then go back to saying `ok` on the next
      periodic beat, because neither service KEEPS the fault: jv-guard's
      "no signature scan engine available" is a property of the machine
      — true of every scan until clamav is installed — reported as one
      blip per screened binary, and jv-brain's `llm error` is one blip
      per failed turn even if llama-server is gone for good. So a
      heartbeat can be `ok` about a guard that cannot scan and a brain
      that cannot answer, which is the sensor-truthfulness failure the
      health topic exists against. Latching them is a few lines each
      (jv-context's `_system_fault` is the pattern, and B38 just built
      the watch half in jv-ears) and it changes what `jv health --check`
      says on an ORDINARY day: a machine with no signature scanner would
      be `degraded` permanently and the check would exit 1 until a human
      installed one. That is exactly the trade-off B43 states, in two
      more places, and it should be answered once for all three. Cheap
      either way; nothing else waits on it. Discovered in B38.
      **THREE services now, not two** (d55348b closed B38 by reading the
      last one): jv-voice publishes `degraded` at the instant synthesis
      or playback fails and does not keep it either, so a sound card that
      is gone for good is one blip per utterance. Its blip now survives a
      full period rather than possibly none of one — the beat owns the
      period it lands in — which makes the un-latched window WIDER and
      the question unchanged. Still one decision, still for a human, now
      covering jv-guard, jv-brain and jv-voice.

- [x] B48. **The loop's own mutation harness can silently test
      UNMUTATED code, and it did once in this iteration.** — 3961e85
      (`ops/ralph/mutate.sh` + `tools/mutate.py`: a spec of `@ label` /
      file / `-`/`+` hunks on stdin, graded with the two controls the
      hand practice never had. **The canary** — the target file made
      impossible to import, which the suite MUST go red for, or it does
      not execute that file and every mutation of it would be a silent
      survivor; the harness then reports NOTHING rather than a perfect
      score. **A cache that cannot be stale** — every suite run gets its
      own empty `PYTHONPYCACHEPREFIX`, so no run can read another's
      bytecode and the in-tree `__pycache__` dirs are unreachable rather
      than deleted. Plus: green baseline before anything is touched, one
      more clean run at the END (iteration 70's real tell was a failure
      on an already-restored file), a hunk that matches twice is an error
      rather than a coin flip, restore even when the runner raises.
      **A correction to this item's stated fix: `python -B` alone does
      NOTHING here.** It stops bytecode being WRITTEN, not read — the
      half that worked in iteration 70 was clearing `__pycache__`. One
      test reproduces the bug in a subprocess with both un-fixed runs
      (plain, and `-B`) as its controls. Tests: `runtests.sh tools` —
      **173, was 138**; twelve mutations on the harness by the harness,
      twelve caught. The re-run half: iteration 69's three EQUAL-LENGTH
      claims on jv-ears (the floor dropped, the floor raised above the
      period, the watch interval widened) re-measured through the
      controls — **3/3 caught**, so that entry stands. Every other past
      entry is now one pasted spec away from the same treatment, which is
      as far as "worth ONE re-run" can be discharged by building a tool.)

- [x] B49. The harness's runner graded PYTHON only, so the QML claims
      ("nine mutations, all caught") and the Rust ones were still
      hand-run. — 4fa5991
      (`--runner {tests,qml,cargo}`, with a `Language` holding the four
      things that differ: the script, the suffixes it may grade, the
      canary, and what a private cache means. A `raise ImportError` for
      Python, an unparseable `***` line for QML, a `compile_error!` for
      Rust — the last is the weakest and says so in its docstring: it
      proves the file is COMPILED into the crate, not that a test
      exercises it, so a Rust survivor means "no test asserts this line"
      and never "the tests do not load this file".
      **This item's own premise was wrong about both new languages.** It
      said the stale-artifact half "cannot bite" them. QML has the bug
      exactly — `qmltestrunner` writes `.qmlc` to
      `$XDG_CACHE_HOME/qmltestrunner/qmlcache/` and validates it against
      (mtime, size) like a `.pyc`, reproduced with the real Qt in a
      subprocess with the un-fixed run as the control, and it is worse
      than the Python case because that cache lives in the user's HOME.
      Rust made the same lie from the mtime side, and the harness's own
      new control caused it: a stamp counter that started when the run
      did fell forty seconds behind a suite that spent forty seconds
      compiling, so the restore looked OLDER than the artifacts cargo had
      just built and cargo skipped the rebuild — `proto::tests::matching`
      failed with the tree byte-for-byte clean. Every stamp now re-reads
      the clock. B48's run-the-suite-once-more-at-the-end check is what
      caught it, on its first real use.
      Two findings from USING it: `--runner qml` grades
      `shell/jv-hud/core/` and nothing else, because the canary LIVES on
      every top-level plate (raised as B51); and a real Rust survivor in
      `topic_matches`, closed by one line in proto.rs's test.
      Tests: `bash ops/ralph/runtests.sh tools` — 190, was 173, with nine
      mutations on the new code and nine caught. PlateStack's nine-caught
      claim re-graded three-of-nine through the controls: 3/3, canary
      dead, that entry stands.)

- [x] B51. **The fourth runner, and the only one that can grade a
      plate.** — 9904c46
      (`--runner shots hud` drives `ops/ralph/hudshots.sh`: the whole
      shell staged, the two Quickshell singletons substituted, the real
      plates driven by `tst_shots.qml` and `tst_sequence.qml`. Two things
      solved, both in the `Language` table: `scratch_out` hands the script
      an output directory inside the run's own scratch, so a grading never
      writes over the committed contact sheet; and the cost is MEASURED —
      53 s a suite run against qmltest.sh's 14 s — so `main` prints the run
      count (baseline + one canary per file + one per mutation + baseline)
      before the first one starts. The canary means the RUST thing here and
      was checked rather than assumed: hudshots.sh lints the stage before
      either driver runs, so a `***` line dies in qmllint (exit 255, no
      driver reached) and proves only that the file is IN the stage. What
      it does catch is a file the stage drops — `--runner shots` on
      `shell/jv-hud/shell.qml` aborts with exit 2, because the stage
      removes `shell.qml` and `tests/`, and the abort now names both.
      **No runner in this harness can grade `shell.qml`**; what it claims
      is gated by `tools/tests/test_hudshots.py`, which reads it as text.
      First honest run: 3 plate mutations, 1 caught, 2 survived. One
      survivor closed here (see A69), one raised as B52. Tests:
      `bash ops/ralph/runtests.sh tools` 199, nine mutations and nine
      caught; `bash ops/ralph/hudshots.sh` 16, the 13 shots byte-identical.)

- [x] A69. `idle` — the machine at rest — had never reached a plate.
      — 9904c46
      (Found by B51's new runner, not by reading: `StatePlate.shown` is
      `root.voice.known && !root.voice.idle`, and dropping the second half
      so the plate lights while NOTHING is happening left all thirteen
      photographs, all fifteen driver tests and all 585 QML tests exactly
      as they were. jv-voice appears in no recording (B10/A28), so every
      dark corner in this repo is dark because the state is UNKNOWN — the
      HUD unable to see — and `idle`, which is a different claim and the
      first decision this HUD ever made (A3, §06's earned emptiness), was
      asserted nowhere above `core/`. Closed with one hand-written frame in
      `tst_sequence.qml`: a fresh `speech.state idle` from jv-voice, and the
      corner must stay dark. Re-graded through the same runner: 1/1 caught.
      The frame is hand-written because it does not exist in any recording,
      which is one more thing B10/A28 would fix at the source.)

- [x] B52. **The contact sheet is thirteen pictures, and now they are
      assertions.** — c15b6d0
      (`tools/hudsheet.py` reads the sheet back: `hudshots.sh` renders, then
      compares every PNG against the one committed at `HEAD:docs/hud`. Bytes
      first — identical bytes are the same picture and that is the ordinary
      case — and when they differ both are DECODED by a small PNG reader
      (8-bit truecolour, all five scanline filters, split IDATs, refusing
      16-bit/interlaced/palette/a header that lies about its size) and the
      finding is a sentence: how many pixels moved, the box they moved in,
      three of them named in colour. Expected lives in git because a refresh
      run renders over `docs/hud` and a file cannot be compared to itself; so
      a deliberate HUD change ends the script NONZERO, with the new PNGs on
      disk — look at them, commit them, next run green. Two things gained on
      the way: the comparison runs in both directions, so a driver that stops
      photographing a plate is a finding and not a smaller sheet; and
      `01-quiet.png` is asserted to be an unbroken field of the declared
      backdrop — §06's earned emptiness, in bytes, for the first time.
      B51's surviving `dotColor` mutation, re-graded through `--runner
      shots`: **1/1 caught**, reported as 36 px in each of 02-listening.png
      and 03-heard.png, `#41939A -> #BD5C3F` — one 6x6 dot going teal to
      ember. `docs/hud/README.md` said in so many words that the PNGs were
      not compared, because a pixel assertion breaks when a font ships a new
      version; the fonts and Qt are both pinned from the flake, which is what
      A45 made these bytes reproducible for, and the paragraph is rewritten
      with a test on it. Tests: `bash ops/ralph/runtests.sh tools` 228, was
      199, with eleven mutations on the new module and eleven caught.)

- [x] B53. `--runner shots` cannot grade a plate while the sheet is out of
      date, and the abort does not say so. Measured while closing B52, not
      reasoned: with an uncommitted change to `StatePlate.qml` in the tree,
      `bash ops/ralph/mutate.sh --runner shots hud` renders a sheet that
      differs from `HEAD:docs/hud`, the comparator exits 1, the BASELINE run
      is red and the harness aborts — "the baseline suite is RED before any
      mutation ... fix the suite first". That refusal is right (it will not
      make a claim it cannot make) and the sentence is wrong: the suite is
      fine, the SHEET is stale, and the fix is one command — run
      `hudshots.sh`, look at the new PNGs, commit them, then grade. The
      comparator says exactly that, but its four lines are the tail of a
      suite log the harness prints one line of. One line in mutate.py's
      red-baseline abort, conditional on the runner, with a test: cheap, and
      the loop will hit this the first time it mutates a plate it has just
      changed. Discovered in B52. — 002ee84
      (A per-runner `baseline_hint` on `Language`, and for the one runner with
      this failure mode it is a MEASUREMENT of the tree rather than a fixed
      sentence: it names the plates that differ from HEAD and prints the
      refresh — hudshots.sh, LOOK at the PNGs, **commit** them, since the
      comparison is against HEAD and a re-rendered uncommitted sheet is still
      stale — or it says the tree matches HEAD and the red is real, or, when
      git cannot answer, it says NOTHING. `_modified` returns `None` for "I
      could not look" and `[]` for "nothing is modified" for exactly that
      reason: the abort it decorates is a refusal to make a claim. Verified end
      to end with the listening dot repainted ember in the worktree, not just
      in unit tests. Tests: `runtests.sh tools` 234, was 229; 6 mutations on
      the new code, 6 caught.)

- [x] B56. The harness prints ONE LINE of each suite log and keeps none of it.
      That line is chosen as "the last line of stdout", which is a pytest
      summary for `--runner tests` and, for `--runner shots`, whatever the
      comparator's closing paragraph happened to end with — while closing B53
      the printed line was "something drew a different picture than the one in
      docs/hud.", which is the sentence for the case that ISN'T what happened.
      B53 fixes the one abort where the loop was actively misled, and the
      general shape is still there: a survivor, a canary that lived or a red
      baseline cannot be investigated without re-running the suite by hand,
      because every run's output is captured and dropped. Each run already gets
      a private scratch directory; writing `run003.log` into it and keeping the
      tree on a nonzero outcome (or just printing the last ~15 lines instead of
      the last 1 when a run is RED) is cheap and would have replaced a 53 s
      re-run today. Discovered in B53. — 6b2207b
      (Each run's private scratch now holds three things: `suite.log` (the
      command, the exit code and BOTH streams in full, written by
      `script_runner` because only a runner knows whether it has output to
      keep), `WHAT` — written BEFORE the suite starts, because the `INDEX`
      line is appended after and that is the half a runner that dies takes
      with it, and the run nobody can name is exactly the one being
      investigated — and, under `--runner shots`, the thirteen PNGs that run
      drew, which is the only way to SEE a surviving plate mutation. The tree
      is KEPT on a survivor or an abort and swept on a clean sweep; each abort
      names the one run that went wrong. The printed line stays ONE line and
      now carries its run number: it is a progress indicator and not the
      evidence, which is B53's whole lesson. Reproduced on the real case —
      a `--runner shots` abort still printed "something drew a different
      picture than the one in docs/hud.", the sentence for the case that was
      not what happened, four lines below "this is the sheet catching up" in
      the now-kept 41-line log. Found two things in itself: the harness's own
      suite leaked 189 /tmp directories after twelve runs, fixed in the CALLER
      (an autouse fixture points mkdtemp's default parent at pytest's
      tmp_path) plus a guard that nothing is made before the target file is
      known to exist; and its first grading reported a real survivor — the CLI
      test asserted the path alone, which `summary()`'s survivor line already
      contains as a prefix, so it was satisfied by a different mechanism and
      graded the CLI immune. Tests: `runtests.sh tools` 245, was 234; 11
      mutations, 11 caught.)

- [x] B50. The canary proves the suite executes the FILE and never the
      LINE, which is the honest meaning of a survivor and also its
      blind spot: "the tests do not cover this branch" and "this branch
      is dead code" are the same report. The other half is sharper and
      showed up in the jv-ears re-run: `test_health_watch.py` computes
      its expectations FROM the constants it tests
      (`TICKS_PER_PERIOD = HEALTH_PERIOD_S / HEALTH_WATCH_S`), so moving
      a constant moves the code and the assertion together and a whole
      class of mutation is ungradeable by construction. Those three were
      caught anyway — by the two ABSOLUTE assertions in that file
      (`HEALTH_MIN_GAP_S < HEALTH_PERIOD_S`, `seen_at <
      HEALTH_PERIOD_S`), which is the lesson worth generalising rather
      than a defect to fix: a suite parameterised on its own constants
      needs at least one claim that is not. Worth one pass over the
      other services' constant-derived expectations the next time a
      journal entry wants to mutate one. Discovered in B48. — 40e395f
      (The pass was RUN, not reasoned: every suite that imports a constant
      from the code it tests was mutated at that constant and graded.
      **Four survived** — jv-hud-bridge `FIRST_BACKOFF_S` and
      `MAX_BACKOFF_S`, jv-voice `TURN_GAP_S`, jv-compat
      `VERDICT_TIMEOUT_S` — and **four were caught**: jv-ears `STALL_S`,
      jv-brain `SAFETY_MARGIN_BYTES`, jv-guard `ENTROPY_SUSPECT`, the
      harness's `ASR_LATENCY_S`. The split is exactly the lesson: every
      catch came from the one assertion in the file written in ABSOLUTE
      units (`clock.now += 5.0`, not `STALL_S + 0.5`), and every survivor
      had none. Each survivor now carries one claim that is not derived —
      bounds on what the number exists to be true FOR, deliberately looser
      than the shipped value in both directions so it is the promise and
      not a second copy of the tuning. Re-graded: 4/4, 3/3, 2/2 caught,
      including the 0.5 -> 0.9 `TURN_GAP_S` edit that mutate.sh's own
      docstring uses as its usage example and that survived until today.
      Asking the question of `VERDICT_TIMEOUT_S` found a REAL bug — see
      B54 — and the test naming it was rewriting a module global in place
      and never putting it back, so the jv-compat suite's result depended
      on its own order.)

- [ ] B54. **Closed by the same commit that found it, and worth a human's
      eye anyway.** jv-compat waited 60 s for `guard.verdict` and then
      failed closed; jv-guard's `ClamAVScanner` gives clamscan 120 s. An
      installer whose scan ran 70 s was refused with "screening
      unavailable — refusing to install" while the only authoritative
      engine on this machine was still scanning it and about to publish
      `clean` onto a topic nobody was reading — a clean binary refused for
      a reason that was not true, which is not what invariant 8's
      fail-closed guarantee is for. Raised to 180 s (120 s of scan plus the
      re-hash of a large installer and jv-guard's 0.1 s poll) and the
      relation pinned in jv-compat's suite, read out of jv-guard's source
      rather than imported. What a human should still weigh: 180 s is now
      the longest an install can sit with nothing on `compat.install` since
      `fingerprinted`, and the HUD says nothing at all during it (A62's
      corner has no "still screening" plate). Either direction of the fix
      was defensible — the other is to cut clamscan's budget instead —
      and this one was taken because refusing a clean binary is the worse
      failure. Discovered in B50.

- [x] B55. The mutation harness could not grade a relation between two
      files when one of them is READ rather than imported. — 2c9800d
      (There were FIVE, not three: jv-compat's copy of jv-guard's scan
      budget, the HUD's two fallback budgets against jv-ears', and
      LinkPlate's grace against both reconnect cadences. A file is now
      offered its controls strongest first — unloadable, then ERASED — and
      whichever kills the suite IS the relation, measured rather than
      declared, and carried into the report: a survivor on an executed
      file means "no test asserts this line", on a read file "no test
      matches this text", and the summary says `the suite reads <file> —
      it never runs it` whether or not anything survived, because "4 of 4
      caught" against a file the suite greps is a claim about a regex.
      Erasure is EMPTY and not a marker (anything kept is something a
      regex might still find) with its limit written down: a NEGATIVE
      claim is green on an empty file too, so the harness refuses — the
      safe direction. The suffix stopped being a refusal and became a
      choice of control, because the refusal was wrong about a real case:
      the tools suite really does match a line in `shell/jv-hud/Bus.qml`.
      An off-language file gets the one control it could ever fail, so a
      Python `raise` is never appended to QML. Graded for real: B50's
      relation 2/2 caught, all four theme/budget mirrors 4/4 including the
      off-language one, 13 runs against a printed floor of 10. Tests:
      `bash ops/ralph/runtests.sh tools` 254, was 245; 9 mutations, 9
      caught.)

- [ ] B57. "The suite reads this file" is true of more than the relation
      being graded, and nothing distinguishes the two. The erasure canary
      on `services/jv-hud-bridge/jv_hud_bridge/bridge.py` made FIVE tools
      tests fail, not the one that holds `RECONNECT_CADENCES` — so the
      control proves the suite depends on that file's text somehow, which
      is exactly what it claims and is weaker than a reader will assume.
      A relation line naming a single test would be a stronger and
      different claim, and the harness cannot make it: it knows which
      suite went red, never which assertion. Two honest ways: leave it and
      say so where the line is printed (it already says "reads", not
      "asserts"), or have the runner report WHICH tests the erasure killed
      and intersect that with the tests the mutation killed — real work,
      and per-runner, since only pytest names them cheaply. Worth deciding
      the day a read relation reports a survivor nobody can explain.
      Discovered in B55.

- [x] B58. The gate has never been testing the tree it is run on. Until
      d55348b, `ops/ralph/runtests.sh` ran `python -m pytest` from the
      service's own directory, which puts that directory first on
      `sys.path` — so `jv_guard` came from the worktree and `jarvis_bus`
      came from the NIX STORE. Every suite but pylib's own has been
      asserting against the shared library AS LAST BUILT, for as long as
      this loop has existed. One `export PYTHONPATH` line fixed it and
      all ten suites stayed green, which is the reassuring half. The
      unreassuring half is that nothing tests the gate's own honesty, and
      `mutate.sh` can: a canary on `services/pylib/jarvis_bus/client.py`
      graded against `--runner tests jv-guard` must kill that suite, and
      before d55348b it would have LIVED — the harness would have
      reported the file immune and been wrong about why. That is a real
      control to add and it generalises: a canary that lives because the
      suite read a DIFFERENT COPY of the file is indistinguishable today
      from one that lives because no test touches it. Small, and it is
      the harness grading its own reach for the first time.
      Discovered in B38. — 3f347b4, 58ae92a
      (`runtests.sh --origin <module> <service>` resolves a module the way
      that suite resolves it — same venv, cwd and PYTHONPATH — and prints the
      file or prints nothing. The harness asks it only when every control has
      LIVED on a Python file, and the abort carries one of three sentences:
      SHADOWED with the other copy named, "this very file" (the old abort,
      now measured rather than assumed), or nothing at all when the question
      could not be asked. One runner only: "where did this come from" has an
      answer for an interpreter and not for a qmltestrunner import path.
      B58's own control is a test —
      `test_the_gate_imports_the_worktrees_shared_library_and_not_the_nix_store`
      — and it is the first test in tools/ that would have failed at every
      point in this loop's history before d55348b. Running the control for
      real then found B59. tools 266, was 254; 9 mutations, 9 caught.)

- [x] B59. **What else could the gate not reach?** B58's control was run for
      real and its first finding was not about the harness: a canary on
      `services/pylib/jarvis_bus/client.py` killed jv-guard's suite (so the
      gate does reach the shared library now), and then BOTH mutations
      survived — `seq` never advancing, and every publish claiming
      `conf: 1.0`. Invariant 4 is implemented for the whole of Python by one
      line in `BusClient.publish` and nothing held it; the round-trip test
      publishes `conf=0.93` and never looks at what arrived. Two tests closed
      those two (58ae92a, 3/3 caught). What has not been asked is the rest of
      the same file, which every service on the bus depends on: `ts`, `src`
      and `v` on the envelope, `next_frame`'s pong skip and its `BusError`
      path, `MAX_FRAME`, and `default_addr`'s env override. The method is now
      cheap and honest — probe the file, then grade a mutation per claim — and
      the likely shape of the answer is that the file was undertested for
      exactly as long as the gate could not see it. Small, mechanical, and it
      is the one file where a silent survivor costs every service at once.
      Discovered in B58. — 9ad4eb7
      (Six mutations, one per claim, and the prediction held: FIVE SURVIVED.
      Only `src` was already held, by the round-trip test. `ts` could be
      0.0 or a wall clock and route fine — the broker validates it as a
      NUMBER and nothing more, and every latency figure in this repo
      subtracts from it. `v` could ignore its caller, which is how a schema
      migration would begin and the one thing that must not be pinned. A
      pong could be read as EOF — the Python client has no `ping()`, so
      that branch was dead code as far as the suite knew, and returning
      None there reports the bus GONE to every consumer. The length-prefix
      guard could be a thousand times too generous. `JARVIS_BUS` could be
      ignored entirely, because every test in the file passes an address.
      Five tests close them; two need no broker and say so. The frame cap
      is now pinned to jarvisd's own declaration by READING proto.rs, and
      that relation was graded the B55 way — move the Rust constant, pylib
      goes red, and the harness reports "reads it, never runs it". pylib 19,
      was 13; 10 mutations, 10 caught.)

- [x] B60. **`client.py` was one of pylib's three modules.** The other two
      are now graded. — 184b6b1
      (`health.py`: 4 mutations, 4 caught — its suite already had teeth.
      `schema.py`: **9 mutations, 0 caught**. The codec that encodes and
      decodes every body on this bus had one test on it, on the one body in
      the frozen set with an empty `_optional`, no nested field and no array.
      Both halves of the omit rule, both array branches, the Optional unwrap,
      the null-nested guard and the absent-key default were all unheld — and
      the absent-key one only looked held because **jv-context's** suite
      happens to decode a `context.system` with `battery_pct` missing. Three
      of the new tests read `schemas/*.json` rather than restating it (the
      B55 shape: every emitted key declared, every required key surviving, a
      null only where the schema permits null), and a fourth reads
      `tools/gen_bindings.py`, because the codec is the generator's epilogue
      copied verbatim and a fix to the generated file is erased by the next
      regeneration. pylib 63, was 19; 12 mutations, 12 caught.)

- [x] B61. **The last of pylib: the two `client.py` claims B60 named and
      left.** (a) `next_event` returns None for a short read on the HEAD and
      for a short read on the BODY, and nothing distinguishes either from a
      frame that never came — so a truncated frame and a closed bus give
      every consumer's reconnect logic the same answer, and the one that
      means "the broker is mid-write" is the one that should not trigger a
      reconnect. (b) `connect()`'s rule `":" in addr and not
      addr.startswith("/")` dials a RELATIVE unix socket path containing a
      colon as TCP. No real path is relative, so it cannot bite today; the
      replay rig is the one thing in this repo that invents socket paths.
      The cheap honest half of both is the same and should come first: pin
      TODAY's behaviour with a test, graded, so that changing either rule is
      deliberate and visible in a diff — then the rule itself is a decision
      someone can make on purpose rather than a thing that quietly differs
      from what every reader assumes. With this, all three pylib modules
      will have been graded. Discovered in B59, deferred by B60. — de510db
      (Five tests, each saying PIN NOT ENDORSEMENT in its own docstring:
      a clean EOF as the control, a short head, a short body, the same
      truncation reaching consumers through `next_frame`, and a six-row
      address table with both openers replaced so the test is about the
      DECISION and nothing dials. The relative-path case turned out to be
      sharper than B59 described it: `run/jarvis:bus.sock` does not dial
      the wrong host and time out, it raises ValueError out of `int(port)`
      while the caller holds what it believes is a filename. pylib 68, was
      63; 5 mutations, 5 caught, including both "fixes" a reader reaches
      for first — before the tests, 1 of 5. All three pylib modules are
      now graded.)

- [ ] B62. **The decision B61 deliberately did not make, and it is two
      decisions.** (a) Should a TRUNCATED frame be distinguishable from a
      closed bus? Today both are None and eight services read that as "the
      bus is gone". Three shapes: leave it (a torn frame on a unix socket
      to a local broker essentially means the broker died anyway, and the
      reconnect is right by accident); raise a distinct error out of
      `next_event` for a short read after a valid prefix, which makes every
      caller's `frame is None` branch incomplete and is therefore an edit
      in eight files; or return a sentinel the callers may ignore, which is
      the cheap one and the one that silently keeps today's behaviour for
      everyone who does not opt in. (b) Should `connect()` decide unix-vs-TCP
      by ABSOLUTENESS (today), by shape (`"/" not in addr`), or should the
      caller say — a `unix:` / `tcp:` prefix, which is the only rule with no
      ambiguous address at all and the only one that touches `JARVIS_BUS` in
      every unit file. Both halves are cheap to change and neither is cheap
      to change ACCIDENTALLY, which is what B61's tests are for: whoever
      answers this moves those tests in the same commit. Raised by B61.

- [x] B63. **The sandbox invariant 8 is built on had never been entered
      once, and it did not work.** — 4a9e2f2
      (`bwrap_args` has been argv-shaped since Phase 2 and `RealRunner`
      says `TODO(machine)`, so the confinement had two tests, both
      built on `Path("/prefixes/x")` — a path the code cannot produce,
      since `prefixes_root()` puts every prefix under `$HOME` — and both
      asserting that three strings were present. Running it found two
      fatal failures, neither of them visible in an argv:
      `--symlink usr/bin /bin` is an FHS distro's layout and this is
      NixOS, where `/usr` holds one file and every binary including
      wine's is in `/nix/store`, so the sandbox had no `/bin/sh` and
      could not execvp ANYTHING; and the prefix was bound at its own
      host path before the private home was bound over `$HOME`, which
      is its parent, so the second mount hid the first and
      `$WINEPREFIX` named a path that did not exist inside. A third:
      `install()` put the installer's HOST path in the inner argv and
      nothing bound the file, so wine was being handed a path to a file
      the sandbox cannot see — invisible because the only pipeline test
      uses `MockRunner`, which never opens anything.
      Fixed by giving the sandbox a view that does not depend on the
      host: the prefix at `/jarvis/prefix`, the installer read-only at
      `/jarvis/installer/<name>`, and the private home mounted FIRST so
      nothing the app needs can be under it. `grant_dest` refuses a
      `home_paths` entry that is absolute, empty, or contains `..` —
      `home_paths = ["."]` used to mount the user's whole home over the
      private one, invariant 8 inverted by one line of TOML.
      `tests/test_sandbox.py` runs a real `/bin/sh` inside the real
      sandbox and asks it what it can see, in POSIX builtins only: the
      prefix is writable and the writes land on the host, the installer
      is readable and NOT writable, `$HOME` shows the prefix's `home/`
      and not the user's files, a granted folder is the user's real one
      while its sibling is hidden, and `/proc/net/dev` holds only `lo`
      when the network is denied and exactly the host's interfaces when
      it is granted. 27 tests, was 10. 10 mutations, 10 caught,
      including both original bugs re-introduced. Tests:
      `bash ops/ralph/runtests.sh jv-compat`.)

- [x] B64. `--new-session`, `--unshare-ipc` and `--unshare-uts` are in the
      argv, each with the instrument that watches it. — 8b5efc9
      (`--new-session`: `sh_on_a_tty` opens a pty and the child `setsid()`s
      and claims it with TIOCSCTTY before bwrap starts, so the terminal is
      really the confined process's controlling one; with the flag removed
      the sandbox writes INJECTED-FROM-THE-SANDBOX and the bytes reach the
      terminal, with it `/dev/tty` is ENXIO. `legacy_tiocsti` is 0 on this
      kernel and is a host setting this repo does not own, so the door is
      measured, not that one burglar. `--unshare-ipc`: the suite MAKES the
      SysV segment it looks for via ctypes `shmget`, which is what dissolves
      the host-dependence B63 named. `--unshare-uts` carries `--hostname`:
      every prefix is told the machine is `jarvis-sandbox`, and the test
      states the premise that the constant is not the real name rather than
      assuming it. Every claim has a CONTROL — same probe, same argv, that
      one flag removed — and `without()` asserts the flag was there to begin
      with. 33 tests, was 27. 8 mutations, 8 caught. Tests:
      `bash ops/ralph/runtests.sh jv-compat`.)

- [x] B65. A grant naming a folder the user does not have yet aborts the
      whole install with a bwrap error: `--bind` fails on a missing source.
      Decided and built while no recipe with a grant is committed, which is
      what made it free. Discovered in B63. — e36eee5
      (**Refuse, loudly, before any work.** `grant_problems(recipe)` answers
      "can THIS machine honour this recipe", names EVERY bad grant so one fix
      covers them all, and the pipeline turns a non-empty answer into
      `blocked` — already the word for "jv-compat refuses", which fail-closed
      uses for its own reason and not the guard's, where `failed` would claim
      an installer ran. `--bind-try` rejected as quieter AND worse: the app
      finds an empty folder, indistinguishable from "no saves yet", writes
      into its private home, and the user's real folder stays empty — a
      failure that surfaces days later as missing work. Creating it rejected
      by invariant 3, and via jv-act it would add a second confirmation to an
      install that already has one. NOT at recipe-DB load, where the item
      guessed it belonged: a recipe for an app nobody is installing must not
      stop `find_recipe` answering about the one that is. It also closed an
      unfiled hole — `grant_dest`'s ValueError was raised inside `bwrap_args`
      with nothing catching it, so `home_paths = ["."]` ended `jv-compat
      install` in a traceback with no terminal frame at all. Two deliberate
      non-refusals, each tested: the predicate follows symlinks because
      `--bind` does, and a grant may name a single FILE, which is narrower
      than the folder around it. The premise is EXECUTED — test_sandbox.py
      builds the argv, removes the granted folder, and watches bwrap refuse
      to exec. Tests: `bash ops/ralph/runtests.sh jv-compat` 42, was 33;
      9 mutations, 9 caught.)

- [x] B66. `grant_dest` promised a grant "stays under the app's private home"
      and checked the STRING. — a0d02ef
      (The three properties it listed were not equally undecidable, and the
      split is what made this buildable: a grant resolving to the real home
      ITSELF or to an ancestor of it is the `["."]`/`["../.."]` bug reaching
      the same place through a symlink, needs no judgement, and nothing
      legitimate wants it — so that is refused, in `grant_problems`, where a
      recipe meets a machine. A grant resolving to a SIBLING of the home —
      the relocated-to-another-disk case — is honoured AND pinned by a test,
      so the strong reading cannot arrive by accident; it is B67. The
      premise is executed: `test_sandbox.py` reads `tax-return.pdf` through
      the link and lists the whole machine through `Root -> /` BEFORE
      asserting the refusal, so deleting the check shows as a leak. Both
      sides of the comparison are resolved — a `$HOME` that is itself a link
      has two names for one home, and the first draft compared one against
      the other and let it through; the mutation that found that is now a
      test. 49 tests (was 42), 8 mutations, 7 caught, the eighth provably
      equivalent. Width documented in `recipes/README.md`.)

- [ ] B67. **The half of B66 deliberately left open, and it is a decision
      with a human in it.** A grant resolving to a SIBLING of the home is
      accepted: `~/Documents -> /mnt/games/Documents` (ordinary, and the
      reason B66 did not take the strong reading), but also `-> /etc`
      (already `--ro-bind` in the confinement, so the grant silently turns
      it read-WRITE) and `-> ~/.local/share/jarvis/prefixes` (every other
      app's prefix, inside an untrusted one). Every candidate property
      refuses some real setup: a uid check fails an ntfs mount with
      `uid=0`, which on a dual-boot machine is exactly where a Wine app's
      saves would live; "not under any path the confinement already binds"
      is narrower and answers nothing about another disk. The third option
      is to leave it and rely on the recipe review, which is what
      `recipes/README.md` now says. Cheap either way and still free —
      no recipe with a grant is committed. Discovered in B66.

- [x] B68. **A red suite stayed quiet for two iterations, and the reason
      generalises.** — 60ea576 (with the repair in 5a3f1e9) `test_the_install_shots_photograph_events_jv_compat_
      publishes` has raised `NameError` since B65 (e36eee5): that commit
      added a fourth `_event("blocked", ...)` to jv-compat whose sentence
      is built from a recipe's grant problems, and the gate — which lifts
      jv-compat's OWN refusal expressions out by `ast` and evaluates them
      over the photographed verdict — had nothing to bind `problems` to.
      A71 fixed it (it now skips a refusal naming anything but `verdict`,
      because that is not a sentence a verdict shot could be showing and
      inventing a binding would put a made-up refusal into the set).
      The interesting part is not the bug. It is that iterations 87 and 88
      both ran `runtests.sh jv-compat`, both were right that it was the
      relevant suite for a jv-compat change, and both were wrong — because
      invariant 1 forbids one service importing another, so every relation
      this repo asserts BETWEEN two of them is asserted by a THIRD suite
      reading their source (B55's whole subject). `tools` reads jv-compat,
      jv-guard, jv-brain, jv-ears, jv-act and jv-hud-bridge; a change to
      any of them can turn it red with nothing in that service's own suite
      noticing. The verify gate says "the relevant test suite(s) for what
      you touched", and the honest reading of that is now wider than any
      one author will reliably guess. Three options and the loop should
      not pick blind: (a) `runtests.sh tools` joins every iteration's gate
      unconditionally — it is 5 s and it is the suite most likely to be
      reading what you changed; (b) a small map from service directory to
      the suites that read it, generated by grepping for the path, so the
      gate names its own dependents; (c) leave it and write the rule in
      PROMPT.md, which is what has just been shown not to work. (a) is
      nearly free and is the loop's to take; (b) is the one that would
      also catch the next reader nobody thought of. Discovered in A71.

      **Done, and it was (b).** `tools/dependents.py` derives the map from the
      suites themselves — a suite reads what it NAMES (a `ROOT / "services" /
      "jv-compat"` expression, a path-shaped string literal, an import, plus
      everything that import imports), if what it names exists — and
      `runtests.sh` ends by printing it. Advice, not a verdict: the exit
      status stays pytest's and a clean tree prints nothing. Two findings
      about the repo, neither of them the tool: jv-ears' suite names
      `jarvis_bus` nowhere and runs it anyway (through its own `main.py`), so
      imports are followed transitively; and jv-brain's `assert ("tools" in
      warm)` is a word, not a path, so a plain string must carry a slash while
      a `/`-built expression need not. 302 tests (was 270), 12 mutations, 12
      caught. (a) was not taken as well — `tools` is named automatically
      whenever it reads what changed, which in practice is most service
      changes, and naming it for the rest would be the guess this replaces.

- [x] B69. **The two gates `dependents.py` cannot see, and the reason is one
      line of QML.** — af794cc `ops/ralph/qmltest.sh` and `ops/ralph/hudshots.sh` are
      the strongest assertions this repo makes about `shell/jv-hud`, and B68's
      map is blind to both: a QML test names its subject by TYPE (`ReplyState
      {}`, `import "../core"`), never by path, so there is no string for the
      reader to find. Today the tool prints both scripts as a standing caveat
      whenever it says anything, which is honest and is not an answer. It is
      mechanical to fix and the loop's: in this repo a QML type IS the
      basename of a `.qml` file on the import path, so `shell/jv-hud/core/
      ReplyState.qml` -> `ReplyState` -> any `tests/tst_*.qml` naming that
      type -> `qmltest.sh`; the plates resolve the same way through
      `tools/hudshots/scene/`. Worth pinning the direction that matters most
      first — a `core/` file changed by a plate author who then runs only
      `hudshots.sh`, and the reverse. Discovered in B68.
      (Done both directions. The gates are walked the way the engine walks
      them: from the files the runner is handed, outward through the types
      they name, resolved on each file's OWN import path and through the
      `qmldir` the directory ships. Comments and string literals are blanked
      first — `Sessions.qml` is recorded bus frames and every driver opens
      with a paragraph naming its plates. `core/ReplyState.qml` names both
      gates; a plate names the sheet alone, because nothing under
      `shell/jv-hud/tests` imports `".."`. The ONE thing not derived is where
      `hudshots.sh` assembles its stage — four lines of `QML_GATES`, each
      directory of which is checked against the script that stages it, plus a
      whole-HUD sweep asserting the only unreached `.qml` are `shell.qml` and
      the two singletons the sheet replaces. 321 tests (was 302), 17
      mutations, 17 caught. The standing caveat is now Rust, which really has
      nothing to derive from. Raised while doing it: **B71**.)

- [x] B70. **The notice is a verdict, and the cost question was answered by
      measuring it.** — (this iteration)
      (`ops/ralph/verify.sh` + `tools/verify.py`: ask the worktree what
      changed, ask `dependents` who reads it, run every one of them, exit
      non-zero if ANY is red. The author no longer picks the suites.
      **The measurement the decision was missing**, one suite at a time on
      warm venvs: pylib 1.6 s · jv-hud-bridge 1.6 s · jv-compat 2.7 s ·
      harness 3.4 s · jv-guard 3.9 s · jv-context 11.4 s · tools 12.2 s ·
      jv-voice 23.0 s · jv-brain 36.3 s · jv-ears **145.8 s** — all ten
      **241.7 s**. So the expensive case is four minutes, ONCE, for the one
      change in the repo that names every suite, and 60% of it is jv-ears
      alone. Shape **(a)**, and (b) was rejected on an argument rather than a
      price: a `<= 3 suites` cutoff is not a cheaper (a), it is (a) with the
      `services/pylib/` case removed, and that case is the only one where the
      author could not possibly have guessed the readers. A rule that drops
      coverage exactly where coverage is the point is not a compromise.
      Four decisions worth their own line. Every step runs even after one
      fails — fail-fast hands back the partial picture this replaces and
      costs a second full run. Output is NOT captured: a 146 s suite behind a
      pipe cannot be told from a hang. The Rust caveat became a step, because
      "a change under a directory with a Cargo.toml is that crate" is a rule
      and a rule can be run — read off the directory, so a third crate needs
      no edit. And an empty plan exits **2**, not 0: the gate runs before the
      commit, so being asked about a clean tree means it was asked after, and
      that is 5a3f1e9 exactly — `--since HEAD~1` is how you ask about what a
      commit actually took. The verdict names the paths it covers for the
      same reason: nothing here can see the index.
      `runtests.sh` keeps its notice to itself under `RALPH_GATE=1`, or a
      ten-step run would urge the reader ten times to run the suites it is in
      the middle of running. PROMPT.md STEP 3 now names one command.
      The gate found a bug in its own first real run: the `RALPH_GATE` it
      exports reaches the suites it spawns, and B68's test for the notice
      read it — that test now states which half of the pair it is.
      Tests: `runtests.sh tools` **372** (was 347); 11 mutations, 10 caught
      on the first pass. The survivor was the spawn-failure branch: the test
      for it deleted the SCRIPT, and bash starts fine and exits 127, so
      nothing ever reached the `except OSError` that stands between "one step
      could not run" and "no verdict at all". Re-graded 1/1. Raised while
      doing it: **B72**.)

- [x] B72. `verify.sh` plans the two gates that are a nix evaluation, and
      says so about the one it will not run. — caffd09
      (Shape (a) for `nixtest.sh` and shape (b) for `hudscreens.sh`, which is
      what B72 proposed — but the reason given for (b) was wrong and the
      measurement is the point. `hudscreens.sh` RUNS here: twice this
      iteration, 2m25s each, green, seven screens, into a scratch directory
      so the tree stayed clean. What disqualifies it is that its product is
      pictures a human looks at, and that they are NOT reproducible — the two
      runs differ from each other and from HEAD in five of the seven files,
      by 3 and 4 pixels of 3.7 M, one channel, by one. A bound run would
      dirty the tree the plan was computed from, every time, with churn no
      eye can tell from a real change. So it is named on every verdict,
      green or red, ABOVE the verdict rather than under it, beside the paths
      that asked for it. `nixtest.sh` is an ordinary step now (22 s) and is
      deliberately not bound to `services/`: a service's source moves a store
      path inside an ExecStart and nothing that gate asserts, and a gate that
      is mostly noise is one somebody switches off. Both declarations are
      checked against a `# reads:` header each script carries about itself,
      the way `test_dependents.py` already checks the staging `hudshots.sh`
      performs — and a gate reads its own script implicitly, which is not in
      the header because a header that names itself is stating a rule and not
      a subject. Tests: `runtests.sh tools` 385 (was 372), 7 mutations, 7
      caught on the first pass.)

- [x] B71. `mutate.sh` no longer leaves the mutation applied when it is
      killed. — c007204
      (Shape (a) plus the half of (b) that was actually load-bearing, which
      is why the decision the PLAN reserved for a human did not need making.
      `restore_on_signal` traps INT/TERM/HUP and turns them into an unwind,
      so the restore that was already written runs on the ordinary way this
      harness dies — one-shot, so a second Ctrl-C from an impatient hand
      cannot interrupt the restore the first one asked for. SIGKILL cannot
      be trapped, so `InFlight` writes a note before every mutant write, in
      this WORKTREE's git directory — `--absolute-git-dir`, so two worktrees
      never read each other's, and nothing a `git add -A` can commit.
      `recover_inflight` reads it at the very top of `run()`, BEFORE a single
      original is read: a stale mutant captured as the "original" is the one
      way this harness could have made the damage permanent, and it is its
      own mutation. Three outcomes, only one of which writes — the file is
      still exactly the mutant (put it back, say RECOVERED), the file is
      already the original (sweep the note), or it is neither, meaning
      somebody has edited it since, and the harness refuses and says where
      the original text is kept rather than overwriting work with a text
      from a dead process. NOT taken: (b) proper, a copy of the worktree per
      run. What it would still buy over the note is one `write_text` wide —
      a kill part-way through the mutant write — and that case is reported,
      not guessed. Tests: `runtests.sh tools` 347 (was 331), including a real
      subprocess killed mid-mutation by a real SIGTERM, its untrapped control
      that reproduces B71 verbatim, and the same driver under SIGKILL feeding
      the recovery. 9 mutations, 8 caught on the first pass — the survivor
      was the arm-before-write ORDER, which no test could see because both
      orderings look identical once the run is over; it is a method
      (`InFlight.swap_in`) now, asserted at the moment of the write, and
      caught on the re-grade.)

- [x] B73. The four gates that could not see a change to themselves.
      — b7b1abd
      (One sentence, finished on every code path that had it: **the thing
      that runs a gate is read by it.** `qml_reads` seeds its read-set with
      `gate.script`, so editing `qmltest.sh` or `hudshots.sh` runs THAT gate
      — and not the other one, which is the sharp half of the test, since a
      rule spelled `{g.script for g in QML_GATES}` would pass every loose
      version of it. `runtests.sh` is read by every suite it can RUN: no
      suite names it (a suite cannot import its own runner) and it picks the
      interpreter, layers the venv, and sets the PYTHONPATH that decides
      which copy of `jarvis_bus` all ten of them import — the line that did
      exactly that is sitting in its header. `cargotest.sh` is the same rule
      for Rust and lives in `verify.py` with the rest of the Rust half:
      both crates, always. Each guarded on the script being THERE, the
      refusal the QML and declared gates already make — a deleted runner is
      a changed path like any other and `bash ops/ralph/runtests.sh tools`
      is still a command that cannot run. Before this, all four named
      `tools` alone, which reads them as TEXT for the service-list check —
      a real reader, and not the one at risk.
      The price is the 241.7 s case and it is bought rarely: 6 commits in
      262 have touched `runtests.sh`, 1 `cargotest.sh`, 1 `qmltest.sh`,
      3 `hudshots.sh`. The claim is now made ONCE over the tables rather
      than five times per kind — `test_every_gate_this_repo_names_is_
      planned_by_a_change_to_itself` walks `QML_GATES`, `DECLARED_GATES`
      and the two runners, so the fifth gate is covered the day it is
      added and not the day somebody notices. Tests: `runtests.sh tools`
      420 (was 411); ten mutations, ten caught — one only after it earned
      a test, because every assertion in the file changed the runner and
      NOTHING else, so "every crate reads the runner" and "every crate
      reads everything" were the same answer until a README was edited
      beside it. Raised: **B76**.)

- [x] B74. `docs/hud/screens/` is compared against the HUD this repo draws,
      and stops being a sheet that can only be overwritten. — e305ac9
      (`hudsheet.Tolerance`, a floor of **256 px per screen and 3 per
      channel**, measured rather than guessed: four renders of an untouched
      HUD compared six ways, 3..111 px apart, never more than 3 on one
      channel and never more than 1 between two renders taken back to back,
      always inside the plate on glyph edges and its own rounded corner.
      B74's premise was half wrong and the measurement says so: a COUNT can
      never discriminate here, because the noise (111 px) is already past
      A34's smallest real change (a 4x4 ember square, 16 px). What separates
      them is AMPLITUDE — §06's quietest ink is >100 from the glass it is
      drawn on, so every word, colour and box a plate can change is two
      orders of magnitude above the floor, and the count is the backstop for
      the one change that is faint AND enormous (a plate opacity of
      0.86 -> 0.855 moves every pixel of the glass by one). `hudscreens.sh`
      now ends by reading its own sheet back, names what the floor absorbed
      on every green run, and — only when it is writing over the committed
      sheet — restores the screens that moved by rounding alone to the bytes
      they were compared against. So the run is idempotent: 5 of 7 screens
      absorbed, `git status` clean, and a dirty one now means the HUD really
      did draw something else. Tests: `runtests.sh tools` 407 (was 385), nine
      mutations, nine caught — including the one that survived the first pass
      and the test it earned, a refresh where one screen changed for real
      while the other six jittered. Raised: **B75**, whether B72's decision
      survives losing half its argument.)

- [x] B75. B72 kept `hudscreens.sh` out of the verify gate for two reasons
      and B74 measured one of them away. The rewrite is no longer
      unconditional — a run that changed nothing now restores what it
      compared against and leaves a clean tree — so "it dirties the tree the
      plan was computed from" is only true of a run that DID change the HUD,
      which is the run whose output a human is supposed to look at anyway.
      What still carries the decision on its own is reason 1: 2m25s, and
      seven pictures rather than a verdict. The honest options are (a) leave
      it named-but-not-run, which is today; (b) bind it, and accept 2m25s on
      every change to `shell/jv-hud`; (c) bind a CHEAPER half — the probes
      (corner, exclusive zone, click, idle frames) are verdicts and the
      screens are not, and nothing has measured what the probes cost without
      the seven `grim` captures and the comparison. (c) is the one that needs
      a measurement before anyone can choose, and the loop can take it.
      Discovered in B74. — 2bee285
      (The measurement (c) asked for, and it RETIRES (c). Every phase of a run
      is booked now — one file both halves of the harness append to, each
      phase classified in `sheet.PHASES` as a cost a picture-less run would
      still pay (`probe`) or one only the seven screens need (`sheet`) — and
      the table is printed at the end of every run, so the answer is
      re-measurable rather than quoted. **179.8 s total: probe 144.8 s
      (80.5%), sheet 34.9 s (19.4%).** A verdict-only gate would save 19% and
      still cost 2m25s, so (a) stands: named, not run. The pictures are not
      what this gate costs — `grim` and the seven PNG encodes come to **0.9 s
      between them**, and nearly all of the sheet half is B74's read-back
      against HEAD (34.3 s). What it costs is the idle probe: **97.6 s, 54%
      of everything**, and it is the least skippable verdict in the file. Two
      things fell out of the measurement. The **2m25s** quoted in six files
      was stale by exactly the price of B74's comparison (145 + 34 = 179) and
      now says 3m00s everywhere. And the only real lever on this price is the
      idle probe's staging, not the camera — raised as **B77**. Fourteen
      mutations over two gradings, one survivor (a book that never closed a
      phase, which would refuse every phase after the first) and the test
      that now catches it.)

- [ ] B77. The only lever on `hudscreens.sh`'s price is the idle probe, and
      pulling it is a trade nobody has measured either. B75 put numbers on
      the run: 97.6 s of 179.8 s is `probe_idle_frames`, and **74.8 s of that
      is deliberate stillness** — ten `IDLE_SETTLE_S` (4 s) feeds, five
      `IDLE_WINDOW_S` (6 s) windows, three `SETTLE_S` — with the remaining
      ~23 s in four brokers and five shells starting up and in the loops that
      wait for a plate to arrive. The windows are long for a reason and it is
      the probe's whole subject: §06 asks for "0 fps when idle", the thing
      that breaks it is a slow blink, and a 6 s window catches a
      once-a-second pulse six times where a 2 s one catches it twice. So the
      constants are the wrong thing to touch. What is NOT load-bearing is the
      five separate stagings: each window brings up its own shell (and four
      of the five their own broker) to reach a state the window before it had
      already reached, which is startup paid five times for a claim about
      stillness. One broker and one shell driven through all five states in
      sequence would cut that without shortening a single window — a rewrite
      of the probe, not a constant, and worth doing the day somebody wants
      this gate bound. Nobody does today; B75 chose (a). Discovered in B75.

- [ ] B76. B73's runner rule has no granularity, and it is the first place
      in this table where a COMMENT-only edit buys four minutes. Touching
      the `# Services:` header of `runtests.sh` — which is prose for a
      human, pinned by a `tools` test — now plans all ten Python suites,
      241.7 s, to learn nothing. B72 made the opposite call one table over
      and said why: `nixtest.sh` is deliberately NOT bound to `services/`
      because "paying 22 s on every Python edit would be the noise that
      gets a gate switched off". The trade is defensible here and the
      numbers are why — the runner has changed 6 times in 262 commits and
      `services/` changes most iterations — so this is a note and not a
      bug. The option, if it ever stops being defensible: read the script's
      CODE and not its comments, which is a rule `names()` already applies
      to Python and `_qml_scrub` to QML, and which nothing applies to a
      bash file. Do not build it on a hunch; build it the first time a
      four-minute run is bought by a paragraph. Discovered in B73.

- [ ] B17. Every `>>> turn` line is now six numbers wide and a summary
      table six rows deep, and `jv tap --latency` prints a hop table above
      both. Nothing has ever looked at that output on a real turn — the
      only eyes on it are tests with 20 ms holds. Worth one read-through
      by a human the first time B10's live recording is made, together
      with A13/A27: if the live line wraps in a terminal it is worse than
      the one number it replaced. Discovered in B14.
      **HALF CLOSED by B22** (dd0857b): "does it wrap" is a test now, at
      the widest input that can reach those lines, and the line that
      prompted this worry turned out to be 133 columns on a live id. What
      is left is the half that genuinely needs eyes, and it is a NEW
      question because the output changed: four lines per tool turn is
      more output than one, and does the ladder read as a decomposition or
      as noise? Same two minutes at a terminal, same trigger (B10/A28),
      now shared with B20.

- [ ] B15. Nothing measures the last hop. `jv tap` stops at `speech.say`,
      which is jv-brain handing words to jv-voice — the user hears nothing
      until Piper has synthesised and the device has started playing.
      **CORRECTION (found while building A37): `speech.state` `speaking`
      is NOT that moment.** `_speak_one` in jv-voice publishes `speaking`
      BEFORE it hands the text to Piper (service.py: `await
      self._state("speaking", say_id)` and only then the synth executor),
      so the frame means "jv-voice accepted this utterance", and the whole
      CPU synthesis of the first sentence sits between it and the first
      audible sample. Measuring to it and calling the result "until you
      hear it" is exactly the "a number stops meaning its label" failure
      B13 was written against. So this needs a decision first and the
      options are not equal: moving the publish to after synth would make
      the HUD go dark for the length of a synth (StatePlate reads the same
      frame) and would leave an utterance interrupted mid-synth with an
      `interrupted` it never said `speaking` for; publishing time-to-first
      -audio as a jv-voice `sys.health` gauge is B16's shape and is
      per-turn data on a heartbeat topic. Not a schema question either way
      — `speech.state`'s enum is frozen and neither option adds a state. Adding it would
      make `total` the thing the budget actually names ("hey jarvis" →
      spoken reply) instead of a proxy for it. Worth doing WITH the human
      decision B13 leaves open, because moving the end of the measurement
      and choosing which span the budget covers are one conversation.
      Discovered in B13.

## Track C — Creative (within blueprint + invariants)
- [ ] C1. Propose and add genuinely new, on-brand capabilities here before building
      them — one line each, so a human can veto in the next `updates` read.

- [x] A12. A "thinking" state for the gap between Jarvis hearing you and you
      hearing anything back. — 7eca614
      (It used to read `idle`, which draws NOTHING, so the HUD went dark at
      the one moment the user was waiting on it. Nothing on the bus says
      "the brain accepted this", so the prompt is RECOGNISED: a wake-gated
      utterance ending (ears disarms and transcribes there; jv-brain answers
      every transcript final) or a `brain.request` from the non-voice
      frontends. Ungated speech in the room is not a prompt — ears' VAD runs
      continuously. It ends on `brain.response` (the only thing that can for
      a silent or errored reply), on the first `speaking` frame after it, or
      on a 30 s floor that mirrors no service's constant on purpose.
      `listening` still outranks everything, and what jv-voice says is
      AUDIBLE outranks thinking — observations beat inferences. The "we
      already heard this answer start" fact is a LATCH, not a binding:
      `bus.latest()` keeps only the newest frame per topic, so the
      `speaking` frame is gone once the idle after it lands, and jv-brain
      speaks one sentence per speech.say — derived, it flipped the word back
      to `thinking` once per sentence. No schema change; the bridge just
      subscribes to two already-frozen topics. 31 new QML tests, 18
      mutations run through them. Tests: `bash ops/ralph/qmltest.sh`,
      `bash ops/ralph/runtests.sh jv-hud-bridge`.)

- [x] A16. jv-voice speaks TURNS, not sentences: one answer is one
      `speaking`→`idle` pair. — 8944abe
      (jv-brain publishes one speech.say per sentence, so an answer used to
      blink once per sentence. Not only cosmetic: **jv-ears releases its
      half-duplex gate on `idle`**, so every inter-sentence idle reopened
      the microphone gate for the length of the next Piper synth while
      Jarvis was still talking. `_speak_turn` now speaks a reply_group as
      one thing — a `speaking` per sentence (each with its own say_id) and
      ONE idle when the turn drains. Two real bugs fell out: `_speaking`
      used to be cleared between sentences, so a wake in the gap was
      IGNORED and the next sentence played over the user; and `_drop_group`
      only purged what was queued, while jv-brain (which has no barge-in
      path) keeps publishing the rest of an interrupted reply — a dropped
      group is remembered now, bounded at 8. `TURN_GAP_S` (0.5 s) bridges
      the bus, not the brain, and the gap is reactive: two timing
      assertions pin that a turn resumes when the sentence LANDS and ends
      the instant a wake does. No schema change. 17 tests green (was 10),
      11 mutations caught 11. Tests: `bash ops/ralph/runtests.sh jv-voice`.)
- [x] A14. jv-ears states the budgets it enforces; the HUD reads them
      instead of mirroring them by hand. — 042438a
      (`EarsPipeline.budgets()` publishes `wake_timeout_s` off the
      SAMPLE-CLOCK count the code compares against — not off cfg, same
      reason CaptureMeter counts what the device delivered — and
      `CaptureMeter.metrics()` adds `capture_stall_s`, which rides from
      the first heartbeat because a budget is not a measurement and must
      not wait for one. Free-form `metrics`, so no schema change.
      `health_body` takes them as a REQUIRED argument, so a caller that
      forgets is a TypeError rather than a consumer guessing.
      `core/EarsBudgets.qml` is the one place that reads them; the plates
      feed them to SpeechState/MicState. The shipped defaults stay as
      fallbacks — the HUD must say something before the first heartbeat —
      but they are PINNED: tools/tests fails the build if a default drifts
      from the Python, if a mirror is renamed out of the gate's sight, if
      a ceiling drops to or below ears' tuning, or if a plate stops
      binding the reported value and quietly runs on the fallback.
      A reported budget must be a number (`"12"` is not twelve), positive
      and under a ceiling; refused means fall back, never zero. Budgets
      deliberately do NOT expire with their heartbeat the way MicState's
      gauges do — a gauge describes a moment, a budget describes how a
      service is configured. 35 mutations; the first round missed three,
      all real: an `isFinite` no input could reach (deleted — the ceiling
      does that work), a numeric string nothing tested, and a `linkUp`
      guard BusModel can never exercise. Tests:
      `bash ops/ralph/qmltest.sh`, `bash ops/ralph/runtests.sh tools`,
      `bash ops/ralph/runtests.sh jv-ears`.)
- [x] A15. `shell.qml`'s `visible` is no longer a hand-maintained OR of every
      plate's `shown`/`lit`. — 0dbe844
      (`core/PlateStack.qml` is a Column that asks its own children — `shown`
      (something true to say now) or `lit` (still on screen, fade included) —
      and the surface is mapped while `stack.anyLit`. Nothing upstream keeps a
      list. Both properties are load-bearing: `shown` MAPS the surface, and
      waiting for `lit` would deadlock, because an unmapped window has no
      animation driver to run the fade that would light it. A JS block, not a
      chain of ORs, because QML tracks what a binding READS — so a plate added
      later counts, and the early return is safe. A child that answers NEITHER
      question is counted as drawing: idle frames are cheaper than a plate that
      never appears. Two tools gates keep that branch unreachable — every direct
      child of the stack must be a `*Plate` declaring `shown`, `lit` and its own
      `visible: shown || lit`, and the surface's `visible` may not name a plate
      again. 11 new QML tests, 9 mutations run through them, 5 more through the
      gates. Tests: `bash ops/ralph/qmltest.sh`,
      `bash ops/ralph/runtests.sh tools`.)
- [x] A17. A wake newer than the open prompt ends the thinking window:
      the user abandoned that question. — b0c8262
      (Narrower than this item was written, and the tests narrowed it. The
      VOICE path was never broken: `utteranceEnded` requires
      `vad.ts >= wake.ts`, so a newer wake disqualifies the speech_end that
      WAS the prompt and the window closes by arithmetic nobody planned —
      that test passed before the fix existed and is kept as its pin. The
      real hole was `brain.request`, whose frame stays readable and stays
      the prompt: the CLI, the harness, later the HUD. Only a SPOKEN turn
      is abandoned, because only a spoken turn is what jv-brain cancels —
      `body.speak !== false`, the schema's own default. Latched, not
      derived (`bus.latest()` keeps one frame per topic, so the wake that
      ended the window is gone the moment the next detection lands), and
      checked on the WAKE edge only: a prompt arriving AFTER a wake is a
      new question, not an abandoned one. 9 new QML tests, 14 mutations,
      14 caught; two first-round survivors were real — a topic check that
      could not change an answer (deleted), and the null-wake guard, which
      only shows up as a log line and now has a `failOnWarning(/TypeError/)`
      test. Tests: `bash ops/ralph/qmltest.sh`,
      `bash ops/ralph/runtests.sh tools`.)

- [ ] A18. The voice path's immunity to A17's bug is ACCIDENTAL. Nothing
      in `core/SpeechState.qml` says "a newer wake ends a spoken prompt";
      it falls out of `prompt` being the audio.vad frame and
      `utteranceEnded` comparing that frame against the wake. It is
      pinned by a test, so it cannot break silently — but if the spoken
      prompt ever stops being the vad frame (say jv-brain one day
      publishes something that means "I accepted this", which is the
      thing A12 wanted and could not have), the bug returns and the
      abandon latch would then be the only thing standing. Either make
      the rule explicit there or leave this note as the warning. Small,
      and worth doing the day that topic appears. Discovered in A17.

- [x] A19. The hand-check from iteration 21 is a build gate. — be1b264
      (`jv-fonts-resolve` in `system.checks`: a check, not a dependency, so
      `nixos-rebuild build` runs it and nothing of it enters the closure. It
      resolves against `config.fonts.fontconfig.confPackages` — the conf
      packages the fontconfig module really links into /etc — reading the
      real `fonts.conf` with one edit, its absolute `<include>` of conf.d,
      because there is no /etc inside a build. Two rules, both stated as
      PROPERTIES rather than as a copy of the mechanism that implements them:
      every installed file is an sfnt by its own first four bytes (NOT by
      extension, which is what the find filter goes by; NOT by fc-scan's
      `%{fontformat}`, which calls a WOFF2 "TrueType" whenever the reading
      FreeType has woff2 support — which is exactly the property at issue),
      and asking for each family by name AND for the generic behind it
      answers that family in a file this module linked (the only check that
      covers `defaultFonts` at all). A generic is only a question if
      fontconfig has heard of it: `49-sansserif.conf` answers any
      unrecognised family with the sans-serif default, so a misspelled alias
      resolved to Archivo and passed — the vocabulary gate greps fontconfig's
      OWN `conf.avail`, never the conf.d this module helped generate.
      `genericOf` now carries both spellings per role (the NixOS option and
      fontconfig's word). Two tools gates because CI instantiates the system
      but never builds it: the check must stay wired into `system.checks`
      (unwiring it is invisible to everything else), and genericOf's roles
      must equal theme.toml's. Worth recording: with the filter widened,
      `fc-match` still answered the .otf — the resolve half alone would NOT
      have caught the regression this item was about. 12 mutations, 12
      caught. Tests: `bash ops/ralph/runtests.sh tools`.)

- [x] A20. The confirmation you can only HEAR gets a readable copy. — 6779708
      (`core/ConfirmState.qml` decides — 34 QML tests, 15 mutations run
      through them — and `ConfirmPlate.qml` draws jv-act's question, its
      words verbatim, with the tool id underneath. jv-act stops in front of
      every destructive tool (invariant 3), speaks the question and opens a
      15 s window in which silence is a no; until now nothing about that
      handshake was visible, so a question you did not hear was answered by
      a timeout you never knew was running. The plate cannot ANSWER, and
      that is structural rather than a decision: the surface has an empty
      input region and takes no keyboard (invariant 10, pinned by a tools
      test), so there is no path from these pixels to an authorization —
      answering stays where invariant 3 put it, your voice or `jv confirm`.
      The request has to be LATCHED, and the bus forces it: `bus.latest()`
      keeps one frame per topic and the ANSWER lands on the SAME topic as
      the request, so a derived "something is pending" would see the
      question only in the instant it arrived. Three ways to let go — an
      answer naming THIS `request_id` (not any answer: jv-act keeps a
      single outstanding slot, but the HUD is not what enforces that), the
      link dropping, and the window jv-act DECLARED in the frame running
      out (A14's rule; `windowFallbackS` is for a request that declares
      none and mirrors no service's constant). Refusing to read a frame is
      never the same as being answered: an unreadable frame leaves a
      pending question exactly where it was. A mutation found a real one —
      the words are gated on the question still being OPEN, not on the
      latch still being held, or an expired question stays readable and
      answerable-looking. New build gate: every topic a `core/` element
      reads must be one jv-hud-bridge subscribes to — an element reading an
      unsubscribed topic builds, lints, passes its own tests and draws
      nothing forever on a surface that is unmapped by design. Tests:
      `bash ops/ralph/qmltest.sh`, `bash ops/ralph/runtests.sh tools`,
      `... jv-hud-bridge`.)

- [ ] A21. `ConfirmPlate` shows that a window is open and never how much of
      it is left. The window closing is a real signal and §06 would let it
      move a pixel — a hairline that shortens, say — but it would be the
      only thing in this HUD that animates continuously, and it has to go
      through `Motion`, which means the one user who asked for no motion
      would get the one indicator with no sense of time. Whether that reads
      as urgency or as a nag is a question for a human eye on ares, so it
      was deliberately not built blind. Discovered in A20.

- [ ] A22. The plate simply vanishes when the question is answered — the
      same exit for granted, denied and timed out. Those are three
      different facts and the user saw none of them; "it went away" is
      indistinguishable from "it expired while I was reading it". A brief,
      quiet outcome (the word, then gone) is the obvious answer and is also
      the first thing in this HUD that would be on screen for a fixed time
      rather than for as long as its signal is true — a new rule, worth
      deciding deliberately rather than as a side effect. Discovered in A20.
      **The reading half is built (A79, 67a9cfc):** `ConfirmState.outcome`
      is "granted" / "denied" / "unknown", `answeredBy` is the route, and
      `answeredTool` / `answeredSummary` keep the words of the question
      that ended. So whoever answers this is deciding a design and not
      also writing a reader — what is left is what the plate SAYS, in what
      colour, and for how long.

- [x] A23. The HUD says when it has stopped being able to see the machine.
      — 34f9af8
      (Every element in this HUD refuses rather than guesses — MicState will
      not call a mic it cannot see "off", SpeechState will not call an
      invisible bus "idle", BusModel empties its cache on `up:false` — and
      every one of those refusals draws the SAME NOTHING that a calm, well
      machine draws. So the corner meant two opposite things with the same
      pixels, and the more dangerous one was silent: a dark recording light
      over a microphone the HUD simply could not see. `core/LinkState.qml`
      decides — 22 QML tests, 18 mutations run through them — and
      `LinkPlate.qml` says NO BUS / SENSOR STATE UNKNOWN plus the bridge's
      own explanation ("connect: ...", "bus closed the connection"),
      clipped to a glance and stripped of line breaks it would otherwise
      break the plate with. No dot and no accent: this is the panel talking
      about its own pipe, never a sensor row — the rule the self-test
      marker already stated for "bus up / bus down", now where a user can
      see it. First in the stack, because it qualifies everything under it.
      The judgement is the WAIT: a down link is ordinary (jv-hud-bridge
      retries 0.5 s after jarvisd restarts, Bus.qml respawns the bridge
      2 s after it dies), and a plate that blinked through every rebuild
      would be ignored on the day it was true — so nothing is said for 5 s,
      and a new tools gate fails the build if EITHER of those cadences,
      in two files that have no reason to think about the HUD, ever grows
      past the grace (VERIFIED it bites from both sides). The wait belongs
      to the OUTAGE, not to the last line about it: the bridge re-announces
      "down" on every failed retry with a backoff climbing to 8 s, so an
      element that re-armed on each one would push the report past its own
      grace forever. Three mutation survivors were all real and all fixed:
      a reported outage handing its verdict to the next brief blip, the
      outage the HUD BOOTS into (a machine where nothing is running —
      `linked` is false from the first instant, so no change signal ever
      fires for it) never being timed at all, and an `onBusChanged` no
      path could reach, deleted. Tests: `bash ops/ralph/qmltest.sh`,
      `bash ops/ralph/runtests.sh tools`.)

- [x] A24. `LinkPlate` reports the pipe; nothing reports the PROCESSES.
      **Written up as proposal R5** in `docs/optimization-backlog.md`; the
      build stays blocked on a human. No code: the deliverable IS R5.
      (A bus that is up says only that jarvisd is up, and the HUD's roster
      (A6) is "who has spoken": a service that DIED is caught — HealthState
      expires a heartbeat at `period_s * 2` — but one that never started is
      absent, and absent is indistinguishable from not installed and from a
      well machine. R5 proposes one new frozen topic, `sys.roster`,
      published by jarvisd: the services this generation expects (written
      into jarvisd's config by the module that declares the units, so the
      list is a property of the running generation) and the ones holding a
      bus connection right now. jarvisd because it is the only process that
      already knows the second list and gains no privilege by saying so.
      Two shapes were considered and rejected in writing: baking the roster
      into the HUD at build time, which answers only the half that never
      changes and puts a fact about the system inside a view; and jv-context
      polling systemd, which answers "the unit is active" when the question
      is "can it speak on the bus".)

- [x] A26. The HUD stops being unable to say what it heard. — d7ac325
      (`core/HeardState.qml` decides — 34 QML tests, 25 mutations run
      through them — and `HeardPlate.qml` draws jv-ears' transcript
      verbatim, teal-dotted, under the state plate. Until now the commonest
      failure of a voice assistant was the one thing this screen had no
      word for: "it misheard me", "it never heard me" and "it is just slow"
      were the same dark corner, and the user found out only when a wrong
      answer came back. FINALS ONLY, which is the schema's own line —
      partials are provisional and only finals are acted on — and it is why
      the line must be LATCHED: partials ride the same topic, so a derived
      reading would blank itself the instant the user started speaking
      again. The exit is a REAL SIGNAL and deliberately not a timer: the
      line leaves when Jarvis starts answering, because from then on the
      answer is the better report on whether you were heard. That is what
      keeps this out of the "on screen for a fixed duration" territory A22
      flagged as needing a human decision. `holdS` is only the backstop for
      a turn nobody ever answers, and a new tools gate fails the build if it
      ever drifts from SpeechState's `thinkWindowS` — the two are the same
      claim about the same turn. NO CONFIDENCE BAR, and the recordings are
      why: the three real finals in `harness/fixtures/sessions/` carry
      0.886, 0.863 and 0.739 and all three transcribe their sentence
      correctly, so any bar inside that spread flags a word-perfect
      transcript and any bar below it never fires — exp(avg_logprob) is
      measuring the room. `tst_sessionreplay` pins that against the real
      numbers, so changing the decision costs an argument with data. The
      privacy line held because jv-ears transcribes ONLY wake-gated
      utterances: everything on this topic was said TO Jarvis, and
      `speech-no-wake` — a real room, real speech, no wake word, no
      transcript at all — is replayed through the element to say so. Two
      mutation survivors were real: an `idle` jv-voice read as an answer
      (the words would vanish while the user was still waiting), and a
      final with no `ts` DISPLACING a good line instead of being refused at
      the door. Two more survive as equivalences and are recorded in the
      journal. Tests: `bash ops/ralph/qmltest.sh`,
      `bash ops/ralph/runtests.sh tools`, `... jv-hud-bridge`.)

- [ ] A27. The heard line is drawn on EVERY monitor, and it is the user's
      own words — which makes A13's question ("three copies of LISTENING
      across three screens: right, or noise?") sharper rather than new.
      There is also no way to turn it off. Both are the same human call and
      should be answered together with A13 — and as of A30 by looking at
      `docs/hud/screens/02-heard-desk.png`, which is your own sentence
      repeated across three real-sized monitors, rather than at ares.
      Nothing was built toward either answer: the plate is
      one `HeardPlate {}` in the stack and a `personality/` switch would be
      the obvious shape if the answer is "sometimes". Discovered in A26.

- [ ] A28. B10 would now buy more than it did. A live-bus recording of one
      real turn is the only way to replay the heard line LEAVING: the exit
      is a `speech.state` `speaking` frame, and nothing committed has ever
      contained one. Today `tst_sessionreplay` can prove the words arrive
      and can only prove the departure with hand-written frames — which is
      exactly the gap B9 set out to close. Same ask, more to gain.
      Discovered in A26.

- [ ] A25. The blind plate cannot say how long the HUD has been blind, for
      the same reason A21's window cannot shorten: a duration on screen is
      the first thing in this HUD that would animate continuously. "NO BUS
      FOR 4 MIN" as a still, coarse line (recomputed on a slow timer, not
      per frame) may be the version that fits §06 — a minute-resolution
      label is not motion. Worth one human opinion alongside A21/A22 rather
      than three separate answers to the same question. Discovered in A23.

- [ ] A13. `StatePlate` is drawn on EVERY monitor, because every surface
      builds one. Three copies of "LISTENING" across three screens may be
      right (you see it wherever you look) or noise. **No longer needs a
      seat at ares**: `docs/hud/screens/02-heard-desk.png` is that exact
      picture, at ares' real monitor sizes (A30). It is a two-minute human
      opinion now, and it should be answered together with A27.
      Discovered in A3.

- [x] A29. The HUD can be looked at without sitting at ares. — fea019c
      (`docs/hud/*.png`: seven shots of one real surface at its real size,
      written by `ops/ralph/hudshots.sh`. The plates are the real files,
      the theme is generated from `personality/theme.toml`, the faces are
      JetBrains Mono and Archivo pinned from the flake, and every frame
      goes in through the same `core/BusModel.qml` the running HUD uses —
      three shots replay `harness/fixtures/sessions` verbatim (B3) and the
      rest are composed, which `docs/hud/README.md` states per shot,
      because a composed picture is a picture of an intention and only a
      recorded one is evidence about the machine. The harness STAGES a
      copy of `shell/jv-hud` with exactly two files replaced — `Bus.qml`
      and `Motion.qml`, the only two that import Quickshell, whose QML
      plugin is linked into the quickshell binary — so `pkgs/jv-hud` is
      untouched and the shipped shell has no idea this exists. Three
      duplications are gated in `tools/tests/test_hudshots.py` (the scene's
      plate stack against shell.qml's, the stubs' members against the real
      singletons', the shots taken against the shots committed); all four
      gates were mutation-checked. The PNGs are not byte-compared — a pixel
      assertion breaks when a font ships a new version. Tests:
      `bash ops/ralph/runtests.sh tools`.)

- [x] A30. The surface stops being verified by reading the source.
      — d56b12e
      (`ops/ralph/hudscreens.sh` runs the SHIPPED `.#jv-hud` — quickshell,
      layer-shell, its own bridge — against a real jarvisd on a headless
      wlroots compositor carrying ares' three monitors, and photographs
      every screen with grim into `docs/hud/screens/`. Nothing is staged,
      which is the one claim A29's sheet cannot make and the first thing a
      future run would give up, so a tools gate reads the driver and fails
      on any `cp`/`ln -s`/`shell/jv-hud` outside a comment. The pictures
      are the smaller half: no PNG is written unless the HUD drew on EVERY
      monitor and only inside the 300x560 box shell.qml anchors to the
      top-right corner at `inset_px`; unless the seat's keyboard is the
      same node it was before the HUD existed; unless the quiet shot comes
      back pixel-identical to the bare desktop on all three screens; and
      unless every workspace still has its whole monitor. Five mutations
      built and photographed, three caught by three different checks
      (anchored left, `WlrKeyboardFocus.Exclusive`, a health plate that
      reports a well machine); a sixth, one surface instead of one per
      screen, caught by the corner check. ONE EQUIVALENCE RECORDED: on a
      CORNER-anchored surface the layer-shell protocol ignores an
      exclusive zone entirely, so `ExclusionMode.Normal` and `.Auto` both
      change nothing — the anchor is what keeps the HUD out of the way and
      `Ignore` is the belt to its braces. That check is kept for the day
      the anchors change and VERIFIED to bite then (left+right+top with
      `Auto` → usable 2560x880). Not ares: sway is not Niri and the
      outputs are headless, so this answers "on all three, in the right
      corner, costing nothing" and never "does it look right". 10 tools
      mutations, 10 caught. Tests: `bash ops/ralph/runtests.sh tools`.)

- [ ] A31. A29 cannot photograph time. A21 (the confirm window shortening),
      A22 (granted / denied / timed out leaving differently) and A25 (how
      long the HUD has been blind) are all questions about what a plate
      does over seconds, and a still frame answers none of them — the sheet
      makes those three EASIER to reason about and no closer to decided.
      The honest still-image version is a strip: the same shot at fade
      start, mid and settled, side by side, which is a picture of a
      transition without pretending to be motion. Cheap once A29 exists
      (one more loop in the driver); worth building only if the human
      answering A21/A22/A25 says the stills were not enough. Discovered in
      A29.

- [x] A32. The empty input mask stops being a claim nobody tested.
      — 48d9c74
      (`probe_click_through` in tools/hudscreens/shoot.py runs after the
      photographs, puts an ordinary Wayland toplevel under the HUD on the
      primary monitor and a second one on a side monitor to hold the
      keyboard, and clicks three points: a CONTROL clear of the surface
      — without it a harness whose clicks went nowhere would report a
      perfect pass-through — a pixel the HUD actually PAINTED, read out
      of the capture rather than guessed, and a point inside the 300x560
      box it painted NOTHING on, because an input region that tracks the
      content is the likelier mistake and looks reasonable in a diff. All
      three must end with the keyboard on the window underneath. It starts
      NO jarvisd: the probe needs a lit state that does not expire, every
      other one is a frame ageing out, and a bus the HUD cannot see is the
      one thing it says indefinitely. The witness is sway's own ROUTING,
      read back over IPC — `node_at_coords` consults each layer surface's
      input region before it looks at a window — and NOT the client's
      wl_pointer, which never fires because a headless seat advertises no
      pointer capability; the README says so. Three mutations, three
      caught by two different points: no mask at all (the painted pixel),
      a mask over only the lower unpainted half of the box (the third
      point, which is how that point earned its place), and a LinkState
      grace so long the plate never arrives (the guard against the whole
      stage going vacuous). The compositor config moved into
      `sheet.sway_config()` and gained `focus_follows_mouse no`, because
      `cursor set` is a warp and a compositor that follows the mouse would
      move focus before any button existed. 83 tools tests (was 77), eight
      mutations through six new gates. Tests:
      `bash ops/ralph/runtests.sh tools`.)

- [ ] A33. The probe answers CLICK and says nothing about scroll or
      hover, which ride the same input region and are the two a user
      would notice next — a scroll eaten over a plate is a page that
      stops moving for no reason. `swaymsg seat - cursor` has no scroll
      verb, so this needs the axis event to come from somewhere else
      (a virtual pointer held open for the length of the probe, which
      would also give the client a real wl_pointer and turn the whole
      measurement from sway's routing into the client's own log). Worth
      it the day the mask is ever edited; not before. Discovered in A32.

- [x] A34. "0 fps when idle" stops being an argument about how Qt works.
      — d420e24
      (`probe_idle_frames` in tools/hudscreens/shoot.py counts the HUD's
      own Wayland commits — libwayland's `WAYLAND_DEBUG` log, client side,
      which is what actually costs a composite and needs no cooperation
      from Qt — over two six-second windows: a live bus with nothing on it
      (surface unmapped) and a plate on screen with no further input. Both
      read ZERO. The instrument moved into `sheet.py` so a test with no
      compositor can execute it over real log lines. The point of the
      whole thing is the two CONTROLS, because every way of breaking a
      probe that passes on zero also returns zero: each window is paired
      with a stretch that MUST contain commits — a real jv-ears heartbeat
      waking the HUD (44), the blind plate arriving (42) — counted by the
      same code through the same log. Both controls bit for real: the
      first version's pattern expected `wl_surface@41` where this
      libwayland writes `wl_surface#41`, and deleting `WAYLAND_DEBUG` from
      the lit stage fails there rather than reporting a perfect zero. The
      headline mutation — a 4 px ember square on `loops:
      Animation.Infinite` inside LinkPlate, which qmllint, 347 QML tests
      and every photograph accept without complaint — reads 1110 commits
      in 6 s. 89 tools tests (was 83). Tests:
      `bash ops/ralph/runtests.sh tools`, `bash ops/ralph/hudscreens.sh`.)

- [ ] A35. The QUIET window is very nearly tautological, and the pulsing
      mutation proved it: with a HUD animating at ~62 fps on three
      surfaces, the quiet window still read 0, because an unmapped surface
      cannot commit whatever the scene graph is doing. All the work is
      done by the LIT window — and there is exactly ONE lit state that can
      be held still long enough to measure: LinkPlate with no bus. Every
      other plate is a frame ageing out (a heartbeat speaks for two of its
      own periods, a confirmation for jv-act's window), so ConfirmPlate,
      HeardPlate, StatePlate, MicPlate and HealthPlate have never been
      watched standing still. A heartbeat with a long `period_s` would buy
      the mic and health plates; the other three need a frame clock the
      harness can hold. Worth building the day a second element is allowed
      to move, which is exactly what A21/A25 are asking for. Discovered in
      A34. **A42 DID the cheaper half (4c63122): the lit-and-still
      measurement now exists on a live bus, with `OutputPlate` as the
      plate. What is left of A35 is the other four plates — tracked as
      A43, which inherits A42's `feed_snapshots`.**

- [ ] A36. The probe counts frames and never milliseconds. §06 budgets the
      ambient scene at "< 2 ms of GPU per frame AND 0 fps when idle", and
      only the second half is measurable here: sway renders with pixman,
      in software, on a headless backend, so no frame in this harness took
      any time on a 1660 SUPER. The first half is also not yet a question
      — there IS no ambient scene; the whole HUD is static glass, and the
      parallax/reticle layers §06 budgets are Phase 5 wgpu work that no
      sensor feeds yet. Re-read this the day the first moving layer lands,
      and measure it on ares rather than here. Discovered in A34.

- [x] A37. The HUD says what Jarvis did to your machine when it did not
      work. — 7bc1eb5
      (`core/ActionState.qml` decides — 35 QML tests, 8 mutations run
      through them — and `ActionPlate.qml` draws ACTION FAILED, the
      registry tool name verbatim, and the schema's own error word, in
      `risk` rather than ember. Invariant 3 gives one process the right to
      change this computer and the HUD could show the QUESTION jv-act asks
      before a destructive tool (A20) and never the outcome of any tool at
      all. Three decisions: FAILURES ONLY (a success draws nothing — the
      machine visibly doing the thing is the report that it was done,
      HealthPlate's argument applied to actions); NEVER A TOOL IT CANNOT
      PROVE (`action.result` has a request_id and no tool name, the name
      is in the `intent.action` that asked, `bus.latest()` holds one frame
      per topic — so the ids must match or the failure is reported
      nameless, and the pair is latched TOGETHER at the moment the failure
      is accepted because both sources keep moving); and NOT `denied` /
      `confirm_timeout`, which are how a CONFIRMATION ended and therefore
      A22's question for a human — passed over here, and passed over as NO
      NEWS so a denial cannot silently clear a real failure. The exit is a
      real signal and not a timer, the same three HeardState uses: Jarvis
      starting to explain, a newer outcome (including a SUCCESS — holding
      a failure under a retry that worked describes a machine that is not
      the one in front of you), and the link dropping, with `holdS` as the
      backstop. `intent.action` + `action.result` joined the bridge's
      topic list, and a new tools gate fails the build if any element
      under `core/` so much as names `args` or `detail` — the 08-action
      shot composes frames carrying both, so the sheet is the
      demonstration. Tests: `bash ops/ralph/qmltest.sh` (384, was 347),
      `bash ops/ralph/runtests.sh tools` (90), `... jv-hud-bridge`.)

- [ ] A38. `ActionPlate` is drawn on EVERY monitor, like every other
      plate, so the A13/A27 question ("three copies across three screens:
      right, or noise?") now has a third instance — and this one is the
      least ignorable of the three, because it is the one that says
      something went wrong. Nothing was built toward an answer: it is one
      `ActionPlate {}` in the stack, and a `personality/` switch is the
      obvious shape if the answer is "sometimes". Answer it with A13/A27,
      not separately. Discovered in A37. **A40 added a fourth instance
      (`OutputPlate`), which does not change the question.** **A52 added a
      fifth (`InstallPlate`) — three copies of "the app did not install",
      one per monitor — and does not change it either.**

- [ ] A39. A22 now has a ready-made shape if the human answering it wants
      one. `ActionState` deliberately passes over `denied` and
      `confirm_timeout` because they are how a confirmation ENDED, but it
      already reads the topic, already latches, and already leaves on a
      real signal — so "the word, then gone" would be one line in
      `apply()` and one more `reportableReasons` entry, with no timer and
      no new rule. Do NOT build it until A22 is answered; this note exists
      so that answering it is cheap. Discovered in A37.

- [x] A40. The HUD stops saying SPEAKING while the room is silent.
      — b643c22
      (`core/OutputState.qml` decides — 36 QML tests, 17 mutations run
      through them — and `OutputPlate.qml` draws ONE line, OUTPUT MUTED or
      OUTPUT AT ZERO, directly under the word it qualifies. SPEAKING is a
      claim about jv-voice and not about the room: with the default sink
      muted, jv-voice accepts the utterance, Piper synthesises it,
      PortAudio plays it, every service heartbeats `ok`, and you hear
      nothing — no error anywhere in the sequence, which makes it the
      failure with the least evidence attached. Four decisions: ONLY WHILE
      SPEAKING (a muted machine is a choice, not news — §06's earned
      emptiness); SILENCE, NOT QUIETNESS (muted or zero, with no threshold
      on "too quiet", which would be a guess about your room — and two
      words because they are two different controls, a toggle and a
      slider); THE RAW jv-voice WORD rather than `SpeechState`'s, which
      lets the microphone claim outrank the speaking one; and A LIVE
      READING, NOT A LATCH — both inputs describe the present, so there is
      nothing to forget, and the one timer in the file exists to stop
      BELIEVING a frame, armed on the earlier of two deadlines (three 1 Hz
      periods for the snapshot, the rate stated by the schema itself; 30 s
      under a `speaking` frame a dead jv-voice would never retract).
      `context.system` joined the bridge's topic list — the first
      NON-EVENT topic the HUD subscribes to, a frame every second forever
      — so the idle probe's QUIET window stopped being a bus with nothing
      on it and became a bus TALKING: six ordinary snapshots over six
      seconds, 0 Wayland commits, both controls still biting at 45 and 41.
      Tests: `bash ops/ralph/qmltest.sh` (423, was 384),
      `bash ops/ralph/runtests.sh tools` (90), `... jv-hud-bridge` (25),
      `bash ops/ralph/hudshots.sh`, `bash ops/ralph/hudscreens.sh`.)

- [x] A41. **The one place `OutputPlate` could be confidently wrong**, and
      it no longer is. — d504ba4
      (jv-voice publishes `output_device_pinned` in `sys.health.metrics`
      on every heartbeat including the degraded ones — 1 if it opened a
      device it was configured to open, 0 if it took PortAudio's default
      — and `core/OutputState.qml` says OUTPUT MUTED only on the 0. No
      schema change: `metrics` is free-form numbers, which is also why
      this is a 1/0 and not a device name. **Unknown is not 0**: silence
      from jv-voice, a v2 body, a hedged beat, a missing `metrics`, a
      non-numeric gauge, a 2, and another service's gauge on the topic
      all leave the plate dark — it never speaks about a sink nobody
      said Jarvis uses. The gauge is deliberately NOT aged, unlike the
      two frames either side of it: it is jv-voice's configuration
      rather than a reading of the world, and `sayWindowS` is already
      the backstop for a dead jv-voice. The knob is real —
      `JARVIS_VOICE_OUTPUT_DEVICE`, empty reads as unset, and
      `SoundDevicePlayer` passes it to `sd.play`. Both screenshot
      harnesses learned the fact and one taught back: publishing the
      beat ONCE made `HealthPlate` arrive mid-window saying *jv-voice
      lost*, so the live-lit feed now carries the heartbeat with the
      snapshot. Seven mutations, seven caught — the link guard only
      after `test_a_bus_still_handing_out_frames_on_a_dead_link` gained
      an `ownSink` assertion, because a third reader's guard is
      unobservable through `unheard`. Tests:
      `bash ops/ralph/qmltest.sh` (435, was 423),
      `bash ops/ralph/runtests.sh jv-voice` (27, was 17), `... tools`
      (96), `bash ops/ralph/hudshots.sh`, `bash ops/ralph/hudscreens.sh`.
      The other half — PipeWire muting jv-voice's STREAM while the sink
      is open — is proposal **R6** in `docs/optimization-backlog.md`.)

- [x] A42. "0 fps when idle" stops being measured only on a HUD with no
      bus. — 4c63122
      (A third window in `probe_idle_frames`: a real broker, jv-voice
      `speaking`, and a MUTED `context.system` snapshot re-published at
      1 Hz, so SPEAKING + OUTPUT MUTED sit on screen for the whole six
      seconds while the `seq` moves, OutputState's expiry timer re-arms
      and every binding downstream of the snapshot re-evaluates to the
      same value. 0 commits under 6 snapshots. Lit in TWO steps — audible
      sink first, then the mute — and the region must grow DOWNWARDS with
      its top and right edges unmoved, so the thing held still provably
      includes A40's plate and not just StatePlate; the first check of
      A40's decision through a compositor. The box is re-measured BEFORE
      the count is judged, because a plate that expired mid-window commits
      the traffic of leaving. Three mutations: the feed replaced by a
      sleep is caught on the box (shrunk back to SPEAKING alone, 28
      commits of OutputPlate leaving); an infinite animation is caught by
      A34's window too, so it proves nothing here; and a "freshness" fade
      bound to `ageOf(snapshot)` — no animation, no timer, invisible to
      every photograph — reads 0 / 0 / **18**, which is the whole
      justification for the window. Two premises were wrong first time:
      the top-LEFT corner does move (OUTPUT MUTED is a longer line than
      SPEAKING), and `feed_snapshots` has to run inside the WAIT loops too
      or a slow capture outlasts `snapshotS`. Tests:
      `bash ops/ralph/runtests.sh tools` (96), `bash ops/ralph/qmltest.sh`
      (423), `bash ops/ralph/hudscreens.sh`.)

- [x] A43. The mic and health plates get watched standing still.
      — fed202f
      (The idle probe's fourth window. ONE jv-ears heartbeat describing a
      device that is open and delivering nothing says both `MIC NO AUDIO`
      — `core/MicState.qml` against jv-ears' own `capture_stall_s` — and
      `jv-ears DEGRADED`, so re-publishing that single frame at 1 Hz
      holds two plates. No long `period_s` was needed: jv-ears' real 5 is
      long enough, and faking one would be a picture of a machine that
      does not exist. Lit in two steps like A42's, growing 41 px
      downwards through `sheet.grew_downwards`. Carries one guard the
      other three do not, and it is window 3's inverted: those plates
      OUTLIVE a six-second silence, so the feed is the subject rather
      than life support and a dead feed would pass every other check — so
      the heartbeats inside the window are counted and fewer than two
      fails. Read 0; verified it bites with A42's "freshness" fade moved
      to the mic dot, which windows 1-3 all read 0 for and this one read
      18. The failure message's first guess was wrong and was kept:
      HealthPlate's `Repeater` model IS rebuilt on every heartbeat and it
      costs no commit. Also tightened the probe's own gates, which were
      greps of the form "somewhere after LIVE AND LIT" that this window
      was about to satisfy on window 3's behalf. Tests:
      `bash ops/ralph/runtests.sh tools` (110),
      `bash ops/ralph/hudscreens.sh`.)

- [x] A48. The two plates whose words come off a latch get watched
      standing still. — 9e322a1
      (The cheap first step answered the question and the answer was the
      good one: a re-published frame RE-TAKES the latch — the envelope
      replaced, `requestKey`/`transcriptKey` moved, `armExpiry`/`armHold`
      run, a one-shot timer restarted — and does NOT re-run the fade,
      because both elements clear `expired` before anything downstream
      reads it and `pending`/`heard` never go false in between. So the
      fifth idle window holds HEARD and CONFIRM on a live bus at 1 Hz and
      reads 0. It is the only one of the five with a latch in it: every
      plate the other four hold is a reading. The mutation is A21's own
      temptation in its most considerate form — the CONFIRM dot's opacity
      bound to the age of jv-act's question, no animation, no timer —
      windows 1-4 read 0 and the fifth read 15, three surfaces times five
      re-publishes, box unmoved. The other refusal is written down: the
      declared window is jv-act's 15 s and not the 600 that would have
      made the feed unnecessary, which means the latches outlive a
      six-second silence and A43's `< 2` guard is needed here too. A test
      pins the declared window against the schema's own description.
      `03-confirm` and the window now read one `CONFIRM_REQUEST`. Tests:
      `bash ops/ralph/runtests.sh tools` (117), `bash ops/ralph/qmltest.sh`
      (435, unchanged — no QML edited), `bash ops/ralph/hudscreens.sh`.)

- [x] A49. `ActionPlate` was the only plate in the stack that had never
      been watched standing still. — 4b62514
      (The decision the item asked for was made and it was NO SIXTH PAIR
      OF PROCESSES: the same broker, the same shell and the same TURN as
      A48's window, carried to its end — the user answers, jv-act runs
      `fs.trash`, it fails. The probe still starts exactly five shells
      and the WAYLAND_DEBUG count pins that. Running the story forward
      earned a step nothing in this harness had ever taken: an outcome
      landing while `ConfirmPlate` still stood would be jv-act reporting
      a tool it was still asking permission for, so the answer goes on
      the bus first and the region has to SHRINK — `grew_downwards` read
      with its arguments swapped — back to (2284, 16, 2543, 84), the box
      the heard line held before it was asked, to the pixel. The failure
      then arrives 78 px taller for 36 commits. Window: 0 commits in 6 s
      under 5 re-publishes, and the re-publish does more here than in
      A48 — re-taking `ActionState.failure` also re-runs `toolFor()`,
      which re-reads `intent.action` and re-resolves the tool name from
      scratch, a binding that reads a SECOND topic every time the first
      arrives. Mutation: the ACTION FAILED dot's opacity bound to the age
      of the failure — qmllint-clean, builds, windows 1-5 read 0, the
      sixth read 18, box unmoved. Also paid A20's honesty debt: `fs.trash`
      is not in jv-act's registry and the sheet now says so, pinned by a
      test. Tests: `bash ops/ralph/runtests.sh tools` (125),
      `bash ops/ralph/qmltest.sh` (435, unchanged),
      `bash ops/ralph/hudscreens.sh`.)

- [ ] A50. **Human review.** The entire confirmation path has never once
      been driven by the registry this machine deploys.
      `services/jv-act/tools.toml` is v0 — "observe + benign only" — and
      the confirmation rule is structural: ONLY destructive and
      privileged tools are ever confirmed. So there is no tool on ares
      today that can produce an `action.confirm` at all, and everything
      downstream of one — `ConfirmPlate`, `ConfirmState`, jv-act's 15 s
      window, its yes/no classifier, the `03-confirm` shot and two idle
      windows — is exercised by composed frames only. The machinery is
      built and reviewed and the composition is fair (registry v0 says
      the destructive tools "arrive in later phases with their own
      review"); what is missing is the first real one. Adding it is a
      `services/jv-act/**` change, which GUARDRAILS forbids this loop
      from touching, so it goes to `docs/optimization-backlog.md` as a
      proposal for a human. Discovered in A49.

- [x] A44. The live-lit window held a state nobody had photographed.
      — 3052b8f
      (`docs/hud/screens/04-unheard-primary.png`: SPEAKING with OUTPUT
      MUTED under it, on the 1440p primary, through the real shell. Two
      mechanisms had to exist first. `hold` — a frame list the settle
      republishes at jv-context's 1 Hz, because `OutputState` is a
      reading of the present and not an event — and `grows_from`, a
      thrown-away first exposure with an AUDIBLE sink that the real shot
      must have grown DOWNWARDS from, because StatePlate says SPEAKING on
      jv-voice's frame alone and "the HUD drew something" would be true
      of a picture where A40's plate never appeared. Measured
      (2444,16,2543,48) → (2412,16,2543,89), 41 px taller; verified it
      bites by making the two exposures identical (exit 1, and no PNG
      written, because the check runs before `write_png`). The growth
      rule moved out of A42's window into `sheet.grew_downwards()` with
      eight unit tests that need no compositor. Honest footnote: the
      `hold` is margin, not necessity — publishing once writes the same
      PNG byte for byte, because one exposure beats the 3 s expiry by
      under a second. Every comment claiming otherwise was corrected.
      Tests: `bash ops/ralph/runtests.sh tools` (104),
      `bash ops/ralph/hudscreens.sh` (7 screens).)

- [x] A51. The HUD says when this machine refused to run a program.
      — ecc89c5
      (Invariant 8 makes jv-guard's screening the only moment JarvisOS
      says NO to something its user asked for, and it was the one moment
      with no pixels. `core/GuardState.qml` decides — 41 QML tests, 10
      mutations run through them — and `GuardPlate.qml` draws BINARY
      BLOCKED in `risk` or BINARY SUSPICIOUS in `warn`, over the file's
      own name. REFUSALS ONLY; NOT the scanner's `reasons`, which the
      schema says are spoken on request and which are the only text on
      this topic a schema does not fix; the NAME IS SANITISED, because it
      is the one string this HUD draws that an attacker chose — whitespace
      collapsed first, then C0/C1, zero-width marks and bidi overrides
      stripped, then capped, and a name with nothing left falls back to
      the first 12 hex of the sha256 labelled as a hash; and NO SPOKEN
      EXIT, because a verdict is not part of a voice turn, which makes the
      30 s hold the ordinary exit rather than a backstop. `guard.verdict`
      joined the bridge's topics; the surface box grew 560 → 624 and three
      other files carry that number. Tests: `bash ops/ralph/qmltest.sh`
      (476), `... runtests.sh tools` (125), `... jv-hud-bridge` (25),
      `bash ops/ralph/hudshots.sh` (10 shots, `10-guard.png` new),
      `bash ops/ralph/hudscreens.sh` (7 screens, green against the real
      `.#jv-hud`).)

- [x] A52. The HUD reads jv-compat now, and says which app did not get
      installed. — caa7c75
      (`core/InstallState.qml` decides — 36 QML tests, 14 mutations run
      through them — and `InstallPlate.qml` draws INSTALL FAILED over the
      app's slug, in `risk`, under GuardPlate: the two halves of invariant
      8 said by the two processes that enforce it. Four decisions.
      FAILURES ONLY, which is also how the progress question was left
      alone rather than answered — see A60. NOT `blocked`, because that is
      how the SCREENING ended and GuardPlate already draws it from
      jv-guard's own frame; passed over as NO NEWS, so a refusal cannot
      clear a real failure. NOT the `error` text, which on a failed frame
      is the last 500 bytes of a confined Windows installer's stdout — the
      element does not expose the field, so no plate can draw it. And THE
      SLUG MUST LOOK LIKE ONE: `app` is an identifier, so it is drawn only
      if it still has the shape of a prefix directory name and REFUSED
      rather than repaired otherwise (a scrubbed identifier is another
      app's name), falling back to the sha256 prefix — which is the one
      place this element parts company with GuardState, where a file NAME
      is sanitised and drawn. `compat.install` joined the bridge's topics;
      the surface box grew 624 -> 688 and four other files carry that
      number. Tests: `bash ops/ralph/qmltest.sh` (536, was 498),
      `... runtests.sh tools` (131), `... jv-hud-bridge` (25),
      `bash ops/ralph/hudshots.sh` (11 shots, `11-install.png` new),
      `bash ops/ralph/hudscreens.sh` (7 screens, green against the real
      `.#jv-hud`).)

- [ ] A60. **Human decision, and the half of A52 deliberately left
      undone.** An install is the only thing on this bus that takes
      MINUTES, and the HUD now draws exactly one of its six events. So
      "what is jv-compat doing right now" is still unanswerable from the
      screen: `fingerprinted`, `screened` and `prefix_created` go by
      invisibly, and a user who ran `jv-compat install` and walked away
      cannot tell a running install from one that never started. The
      shape is the problem, not the data — every plate in this stack is
      about a MOMENT, and a progress indicator is a thing §06 does not
      have: it would be the first element on screen for minutes at a
      time, the first whose whole point is that it changes, and the first
      that competes with the voice turn for the corner. Three ways out
      for whoever answers: (a) leave it — the terminal that started the
      install is the progress indicator, and the HUD is for what you
      would otherwise miss; (b) a one-line plate that says the app and
      the stage and nothing else, holding the rhythm of the rest of the
      stack; (c) a genuinely new §06 shape, which is a design decision
      and not an implementation one. Discovered in A52.

- [x] A61. `10-guard.png` and `11-install.png` are the two halves of one
      story and no picture has ever shown them together, though the box
      was grown for precisely that case. — 542797a
      (`12-guard-install.png`, caption `guard install mic`. The
      refusal-then-retry this item described CANNOT produce it: jv-guard
      screens the retried build too, and a `clean` verdict is newer news
      from the same screener, so `GuardState` lets the refusal go before
      the retry can fail. The refusal has to be the NEWER screening about
      a DIFFERENT binary — which is just two overlapping installs, and an
      install takes minutes: a long installer gets its prefix, the user
      installs something else while waiting and jv-guard refuses it, and
      the first install dies fourteen seconds later. Every frame is one
      `install.py`/`jv-guard` really publish, in order, at real
      timestamps, including the `blocked` on `compat.install` that lands
      mid-lifecycle and that `InstallState` reads as no news — the shape
      that makes A52's rule matter, on a screen for the first time. The
      sheet also stopped taking the FIT on faith: every shot now asserts
      `insetPx + stack.height <= surface height`, mutation-checked with a
      170 px box. Tests: `bash ops/ralph/hudshots.sh` (12 shots, the
      other eleven byte-identical), `... runtests.sh tools` (131),
      `... qmltest.sh` (536, untouched).)

- [ ] A62. The corner can show two plates about two unrelated things and
      has no way to say so. `12-guard-install.png` is the first picture of
      it: `codec_pack_setup.exe` was refused, `fl-studio` failed, the two
      have nothing to do with each other, and they are stacked 8 px apart
      in the same severity colour. A reader who assumes one story reads
      "the thing that was blocked then failed", which is the one sentence
      those frames do not support. Every plate in this HUD is true alone
      and the stack has no grammar for relating two of them — and the pair
      that reads MOST like one story (guard + install, joined in the
      schemas by a sha256) is the pair that most often is not. This is a
      design question and a human's: (a) leave it — a HUD is a list of
      facts and the voice is where relationships live; (b) join what can
      be joined (the sha256 IS in both frames, so "same binary" is
      knowable and "different binary" therefore assertable); (c) a §06
      shape for grouping, which is new design. Do not build (b) before
      answering (a). Discovered in A61.

- [x] A63. The corner the box is sized for did not fit in the box. — ae4299c
      (ASSERTED, not photographed: `tools/hudshots/scene/tst_fit.qml`
      stacks every plate but `link` — the one that excludes all nine, and
      a check holds that split — each drawing the widest thing its own cap
      allows, over a health list as long as this machine has services.
      That corner is **713 px**, in a box that was **688**. A layer-shell
      panel floating over every window was cutting its BOTTOM plate in
      half, and the bottom plate is `HealthPlate`: the thing that says
      what is wrong, cropped exactly when everything is. The box is 745 px
      now — two insets and the measurement, because §06 gave the corner an
      `insetPx` gap at the top and the right and the bottom had none, so a
      stack that exactly filled the box ended flush against the edge.
      Three controls, because a fit check is the easiest test to make
      vacuous: the crowd really is nine plates (`litNames`), every capped
      plate really is AT its cap, no plate is wider than the surface. The
      middle one caught the only real mistake in the file — `InstallState`
      REFUSES an over-long slug rather than eliding it, so the probe that
      made every other plate widest made that one narrowest and the corner
      measured 3 px short with nothing failing. Four Python gates stop the
      copies drifting (each driver's box to shell.qml's, both drivers'
      `everyPlate` to Corner.qml, the crowd's roster to `services/`).
      Eight mutations, eight caught, each by one check. Tests:
      `bash ops/ralph/hudshots.sh` 23, `... qmltest.sh` 585,
      `... runtests.sh tools` 269.
      **The PICTURE half is deliberately not taken and is still A62's:**
      a shot of eight unrelated plates 8 px apart is a photograph of
      exactly the confusion A62 raises, and "does a 713 px corner read as
      a HUD or as a wall" is a question only a human looking at one can
      answer — see A70.)

- [ ] A70. **A human's look, and it is A62's question with a number on
      it.** A63 proved the crowded corner FITS; nothing says it should
      exist. 713 px is half a 1440p screen and two thirds of a 1080p one,
      most of it several near-full-width plates about unrelated things, and
      the alternative was never considered because nothing had measured the
      case: `HealthPlate` calls itself "the SHORT list" in its own header
      and has no cap at all, so nine unwell services are nine rows. Three
      shapes, and the loop should not pick: (a) leave it — the corner is
      only that tall when the machine really is that broken, and cropping
      it then is the worst possible moment; (b) cap the health list at N
      findings with an "and 4 more" row, which is new §06 vocabulary and
      shrinks the box; (c) cap the STACK — a corner that stops at N plates
      and says so, which is the general answer and the largest change.
      Whoever answers it can look at the numbers without running anything:
      the per-plate measurements are in the A63 journal entry. Raised by
      A63.

- [x] A64. `GuardPlate`'s entire `warn` branch was unreachable on this
      machine: `decide()` returned `clean` or `blocked` and nothing else,
      so the approved policy's middle rung lived in the schema's policy
      note, jv-compat's override message and the HUD's second colour —
      and in no code path. — eca239e
      (Took the first of the two ways out: jv-guard grew a local,
      hash-free SHAPE engine. `jv_guard/pe.py` reads the section table
      and refuses to guess at anything it cannot parse confidently;
      `jv_guard/heuristics.py` raises a concern for an EXECUTABLE section
      at entropy >= 7.2, one that is also writable (W+X), or one with no
      bytes in the file but virtual space to unpack into. "Executable" is
      the whole difference between a rung and a nuisance: every
      Inno/NSIS/7z installer carries a ~8-entropy compressed payload in a
      DATA section, and a test says so. Engines now declare a KIND —
      SIGNATURE is authoritative, HEURISTIC is advisory — because without
      it the new engine would have silently deleted fail-closed: ClamAV
      down + shape engine ordinary would have become `clean`. `decide()`
      returns None unless an authoritative engine ran, even when the
      advisory one is shouting (the outage clause forbids inviting an
      override too). Missing Authenticode was rejected with reasons in the
      docstring: it fires on nearly every binary this machine will screen,
      and signature PRESENCE is not trust. Tests:
      `bash ops/ralph/runtests.sh jv-guard` (33, was 6; five mutations),
      jv-compat 9 and pylib 4 unchanged.)

- [ ] A65. **Human decision, and it just stopped being theoretical.** The
      `suspicious` override path is now the only exit from a verdict this
      machine can actually produce. A UPX-packed freeware tool and a
      Themida/VMProtect-wrapped game installer both read as packed —
      because they are — and v0 refuses them with a message describing a
      confirmation nobody can give. That is invariant 8 behaving exactly
      as written, and it is also a class of install that used to succeed
      and now stops. Three things a human could decide: (a) wire the
      override through the confirm surface that already exists
      (`ConfirmPlate` + jv-act owns confirmations — this is the designed
      answer and the biggest); (b) leave it refusing and accept that
      packed installers need a human at a terminal; (c) tune which
      concerns reach `suspicious` (W+X alone is rarer than packing; the
      thresholds are two named constants with a calibration test).
      Discovered in A64.

- [x] A66. The thirteenth contact-sheet shot A61 refused to take is now
      honest. `GuardPlate`'s `warn` colour has a producer, so a composed
      frame of a `suspicious` verdict is a picture of something jv-guard
      really publishes rather than of an intention. — a1d3a53
      (`docs/hud/13-suspicious.png`: the same element as `10-guard.png`,
      one word and one colour apart, and unreachable code until A64. The
      file is deliberately not malware — a decade-old widescreen patch
      run through UPX, which ClamAV recognises nothing in and which is
      shaped byte for byte like something hiding. Half of A66's premise
      was wrong and saying so is part of the result: the reasons are NOT
      a test of the plate's wrapping, because they reach no pixel —
      `core/GuardState.qml` never reads `reasons`, which the schema says
      are spoken on request. They are quoted in `docs/hud/README.md`
      instead. What the shot does test is that the warn branch renders
      and that a real file name fits (27 chars, ~211 px of a 240 px cap).
      The part worth keeping is the gate: this is the sheet's only frame
      that QUOTES another service, so `tools/tests/test_hudshots.py`
      builds a UPX-shaped PE with jv-guard's own fixture builder, runs
      the real `PEHeuristicScanner` and the real `decide()`, and holds
      the scene's literal to the verdict, all three reasons and
      `scanned_by` that come back. Five mutations, including one to the
      wording inside `jv_guard/heuristics.py` — which fails the tools
      suite, proving the gate points at the producer and not at a copy.
      Tests: `bash ops/ralph/runtests.sh tools` (132, was 129),
      `bash ops/ralph/hudshots.sh` (13 shots, the other twelve
      byte-identical).)

- [x] A67. Shot 13 is the only composed frame in the sheet whose words
      are pinned to the service that would say them, and it is not the
      only one that QUOTES a service. `08-action.png` carries jv-act's
      `execution_failed` and an exec error, `11-install.png` carries a
      wine loader failure, `05-confirm.png` carries a tool name and a
      window in seconds, `06-health.png` carries jv-brain's `llm_rung`.
      Every one of those is a hand-typed sentence attributed to a real
      producer, and nothing checks that the producer could emit it —
      which is exactly the gap the A66 gate closed for one frame out of
      four. The generalisation is cheap where the producer is importable
      and pure (jv-compat's lifecycle events, jv-act's error enum) and
      expensive where it needs a running service, so this is a per-frame
      judgement rather than one sweep: do the cheap ones, and say in the
      README which quotations are still only plausible. Discovered in
      A66. — fa08188
      (All four cheap ones done, and three frames turned out to be
      wrong. jv-brain's ladder and jv-compat's fingerprinter are
      imported; `install.py` is parsed for its event vocabulary and for
      the fields each call site attaches; jv-act's registry is TOML and
      its Rust is read for tool names, arg names, capabilities, error
      words, the 15 s window, the `kind` literal and the question's
      format string. jv-act was READ only — never written to. The gate
      worth copying is shot 12's refusal: comparing against
      `"; ".join(reasons)` computed in the test went green when
      `install.py` was mutated to reword it, so it now lifts every
      `error=` expression out of the three `blocked` call sites with
      `ast` and evaluates jv-compat's own code over the verdict in the
      picture. `08-action.png` was wrong three ways — `args.name` where
      the registry declares `app`, no `needs_confirmation`, and a Go
      runtime's `exec: ... not found in $PATH` where jv-act is Rust and
      plans `gtk-launch -- <app>` — none of which reaches a pixel, which
      is why nobody caught them. `05-confirm.png` changed on screen and
      got worse: jv-act sends
      `format!("{} — yes or no?", spec.description)`, so the question is
      generic by construction and the old frame was a picture of a
      machine that names what it is about to touch. Free text stays
      free text, per shot, in the README. Tests:
      `bash ops/ralph/runtests.sh tools` (136, was 132; fifteen
      mutations, five of them to the producers),
      `bash ops/ralph/hudshots.sh` (13 shots, twelve byte-identical),
      `... qmltest.sh` (536, untouched).)

- [ ] A68. **Human decision, discovered by photographing it.** A
      confirmation cannot name its object. jv-act's question is
      `format!("{} — yes or no?", spec.description)` — the tool's
      registry description and nothing about the invocation — so the
      plate can only ever read "Move files to the trash — yes or no?"
      whether it is two files or four hundred, and the thing the user is
      being asked to authorise is in `intent.action.args`, which no
      element under `shell/jv-hud/core` may name (invariant 7: args are
      content, not vocabulary). Three ways out, and they are not equal:
      (a) widen jv-act's summary to include the args it was given — its
      own commit, human-reviewed, and the only one where the sentence
      stays a sentence jv-act says; (b) have the HUD draw `args` beside
      the question, which is a privacy decision about the one plate
      whose whole job is to be read before you answer; (c) leave it —
      the voice has the detail, the plate is a prompt and not a
      contract. Nothing should be built before (a)/(b)/(c) is answered.
      Note that A21 (the window closing) and A22 (how it ends) are about
      the same plate, so whoever looks at `05-confirm.png` can answer
      all three at once. Discovered in A67.


- [x] A53. `10-guard.png` is a picture only a human can tell apart from a
      picture of `ActionPlate`. — 754a49b
      (Answered with the QML-side probe, which turned out to be cheap where
      it counts: every plate declares `plateName`, pinned to its own file
      name by a tools gate so it cannot drift into a confident lie, and
      `core/PlateStack.qml` collects `litNames` — the plates on screen, in
      reading order, as the plates themselves report it. `anyLit` is
      untouched: it maps the surface, it is the only safety-critical answer
      here, and a test holds the two to agreeing in every case. The contact
      sheet now asserts its CAPTION per shot instead of one bit that nine
      of ten shots answered identically; `07-no-bus.png` is checked for
      A23's actual argument (`link` ALONE, every plate under it gone rather
      than stale); a plate the sheet renders but never LIGHTS fails a test;
      and `docs/hud/README.md` carries a machine-checked `**On screen:**`
      line per shot. Mutation-checked with the exact confusion this item
      names: 10-guard.png expecting `action` FAILS now and passed before.
      Tests: `bash ops/ralph/qmltest.sh` (487), `... runtests.sh tools`
      (130), `bash ops/ralph/hudshots.sh` (10 shots, byte-identical).)

- [x] A54. The corner is only ever checked at one settled instant, and a
      plate that arrives one frame late or leaves one frame early is a
      SEQUENCE bug no still picture can catch. — 8b2fa24
      (Answered where the real plates can actually be built: the shot
      harness's stage. `tools/hudshots/scene/tst_sequence.qml` replays the
      committed recordings through the real nine-plate corner and asserts
      the whole trajectory — every `litNames` change with the `ts` of the
      frame that caused it — plus four claims only a sequence can make: no
      recording lights a plate no service in it reported, the words are
      never up without the state plate above them, an unanswered turn
      empties the corner by itself, and losing the bus takes every plate
      down BEFORE the link plate arrives (the 5 s of grace `07-no-bus.png`
      settles past). Motion is suppressed through the real reduced-motion
      path so a plate's arrival is a frame and not a fade; one test holds
      that. Both drivers now build ONE corner —
      `tools/hudshots/scene/Corner.qml`, pinned to `shell.qml` for
      membership and ORDER, with a second gate against a driver keeping its
      own copy. Tests: `bash ops/ralph/hudshots.sh` (15, and the 10 shots
      byte-identical), `... runtests.sh tools` (131). Eight mutations
      caught; one honest miss reported in the journal.)

- [x] A71. The one way a turn can end that nothing on this machine
      reported. — d049a9c
      (`schemas/brain.response.json` has ended every turn with one of
      three words since v1 and the HUD read the frame only to learn that
      a turn had ENDED (A12), never how. `stop` is the ordinary case and
      draws nothing. `error` already reaches the corner — the same
      `except` block in jv-brain publishes a `degraded` heartbeat one
      `await` later and HealthPlate draws it, so a second plate about one
      event is A62's confusion built on purpose. `length` means the
      context or token limit was hit and THE TEXT IS TRUNCATED, and
      nothing said so: no service calls it a fault, jv-brain speaks the
      reply as it streams so there is no later sentence to carry the
      news, and the frame is well-formed on a healthy machine. On ares it
      is the likely case rather than the exotic one — a CPU rung with a
      2048-token context under a conversation budget sized for rung 0
      (backlog §4, a human's).
      `core/ReplyState.qml` decides, `ReplyPlate.qml` draws `REPLY CUT
      OFF` and the schema's word in `warn`: nothing is broken. Not one
      word of the reply reaches a pixel; `text` is read only because the
      schema allows an empty string "only with finish_reason=error", so a
      `length` with nothing in it is refused rather than announcing that
      something never said got cut off. The exits are the family's minus
      one: a newer non-`length` response (including `error` — a newer
      TURN), the user starting again (a wake or a brain.request stamped
      after the reply, checked on their edges AND when the truncation
      lands), the link, and `holdS`. `speech.state` is deliberately NOT
      an exit — brain.response is published when the STREAM closes and
      jv-voice is still reading the sentences it was handed, so that
      frame is the truncated reply itself.
      Tests: `bash ops/ralph/qmltest.sh` 615 (was 585) — 31 new, graded
      with 10 mutations; `... hudshots.sh` 23; `... runtests.sh tools`
      270. Shot 14, `14-cut-off.png`, is a real recording plus the two
      frames that end a turn, and its `finish_reason` is pinned to the
      frozen enum AND to the one line of jv-brain that can still produce
      it.)

- [ ] A72. **The corner grew again and A70 got bigger, not answered.**
      A71 put a tenth plate in the stack: the crowd measured **775 px**
      (was 713) and the surface is **807** (was 745). A70 asks whether a
      corner more than half a 1440p screen tall should exist at all, and
      the loop deliberately did not pick between its three shapes — but
      the number in the question has now moved twice without a human
      seeing either measurement. Nothing here is broken and nothing is
      urgent; this exists so that whoever answers A70 knows the trend is
      upward and that every new plate pays for itself in box height.
      Raised by A71.

- [ ] A73. `docs/hud/screens/` was photographed against a box that no
      longer exists, and its README says a THIRD number. The compositor
      sheet's prose has said `300x560` since A30 while the surface went
      688 -> 745 -> 807, and the committed PNGs are monitor-sized
      screenshots taken at 745. No gate holds any of it: the only pinned
      copy is `tools/hudscreens/sheet.py`'s `SURFACE_H`, which follows
      `shell.qml` and is now 807, and the measurements that use it run
      only when the harness runs — which needs a real compositor and
      therefore a human, like A47 and A55. Two honest ways: re-shoot the
      directory on a machine with a compositor (which is the same seat at
      ares B10/A28 and A47 are waiting for), or add the gate that would
      have caught the 560 five plates ago — pin that README's box to
      `sheet.py` the way `test_hudscreens.py` already pins `sheet.py` to
      `shell.qml`. The second is the loop's and is worth doing first:
      a stale number nobody checks is how the first one survived three
      growths. Raised by A71.
      **THE LOOP'S HALF IS DONE** — c8099c2. Every WxH the README quotes
      is now pinned to a box this harness declares (the surface, a monitor,
      the desk, or the box the pictures were taken against), with the
      scanner in `sheet.py` where a test can run it. The pictures' own box
      is DERIVED, not written down: `sheet.shot_surface_box` asks git which
      commit last wrote a PNG here and what `sheet.py` declared at it — and
      the first thing that derivation did was correct this item, which says
      745 where git says **688**. The prose now says so in a paragraph that
      cannot go stale and that a re-shoot deletes rather than edits. What
      is left is the half that needs a compositor: **re-shoot the directory
      on ares**, which is the same seat A47, A55 and B10/A28 are waiting
      for. Ten mutations, ten caught.

      **The staleness notice is RETIRED — fe69aa8, and not the way this
      item expected.** Nobody re-shot the directory at ares; B93 added a
      screen, and `shot_surface_box` answers "the box the pictures were
      taken against" by asking which commit last wrote a PNG here — which
      is now B93's, declaring today's `300x826`. So `then == now` and the
      paragraph deleted itself, exactly as designed. Read the derivation
      honestly: what it establishes is that the NEWEST picture is current.
      That the other seven are too is established by something else and
      something better — B74 re-takes all of them every run and compares
      them to the committed bytes, so a screen that had stopped being the
      HUD ends the run nonzero. The prose now says that instead. The
      phrase the gate keys on ("older than the box") is reserved: the
      paragraph that replaced the notice deliberately avoids it, because a
      substring search cannot tell prose saying a condition is OVER from
      prose saying it holds — which cost one red gate to learn. What is
      still open is the part that was never about the box: nobody has
      LOOKED at these screens on ares' real panels (A47, A55).

- [x] A74. **The sibling sheet quotes the same box and nothing holds it
      either.** `docs/hud/README.md` opens with "300 × 807 px, the box" —
      the same sentence A73 just pinned one directory down, unpinned, and
      correct today only because A71 happened to update it. `test_hudsheet.py`
      already derives that box from `tools/hudshots/scene/tst_shots.qml` to
      check every committed PNG's size, so the gate is `sheet.boxes_in_prose`
      over that README against that box — five lines, and the same argument
      A73 made. Two small decisions for whoever takes it: the contact sheet
      deliberately disclaims everything a compositor owns, so a monitor size
      appearing in its prose is probably wrong rather than allowed (the
      screens sheet is where monitors are quoted); and unlike A73's, this
      sheet's PNGs are re-rendered by `hudshots.sh` on every HUD iteration,
      so there is no "older than the box" case to state — the pictures are
      never stale. NOT taken in A73's iteration to keep one finished thing;
      the cost is one `runtests.sh tools` and one `hudshots.sh`. Raised by
      A73. — b1ccf6b
      (Both decisions kept as written. The allowed set is ONE box — the one
      `tst_shots.qml` renders, which `test_hudshots.py` pins to `shell.qml`,
      so the derivation runs prose -> scene -> shell with no literal in it —
      and no staleness notice, because the test above measures all fourteen
      committed PNGs against that same box. The scene box is a `scene_box()`
      helper now, shared with that test. The README also says the number is
      held, in prose that quotes no box of its own. Six mutations, six caught.)

- [x] A75. **The bus's own drop count is on the bus, and the HUD cannot say
      it.** — 1764a52 `schemas/sys.health.json` has carried `drops` since v1 — "frames
      dropped since the last heartbeat, keyed by topic, published by jarvisd
      per slow subscriber" — and `broker.rs` really publishes it: every
      subscriber's out-queue overflow (`drops.add(&d.topic, 1)`) plus the
      broadcast lag (`_lagged`) and control frames (`_ctl`), summed across
      every connection, drained into each heartbeat. `jv health` prints the
      map (`drops={"audio.vad":2}`). Nothing in `shell/jv-hud` reads the
      field at all: `seq` appears in eleven core/ files and in every one of
      them it is an identity component, never a gap check, and `HealthState`
      reads `state`, `notes` and `metrics` and not `drops`. So invariant 5's
      one failure — something on this machine blocked the bus long enough
      that frames were thrown away — is visible to a human at a terminal and
      invisible on screen, under a corner every plate of which is drawn from
      frames that may be the ones that got through. One row in `HealthPlate`,
      the `VramState` pattern (a core/ element that decides, a row drawn only
      while it offers one), no schema change and no new topic. The care is in
      the wording: the count is an AGGREGATE over every subscriber, so the
      HUD may not be the reader that lost anything and must not say it was.
      Discovered while orienting at iteration 100.
      (`core/DropState.qml` decides — 32 QML tests, 24 mutations over five
      gradings — and `HealthPlate` draws one row, `bus 41 DROPPED`, ABOVE the
      findings, because it is a claim about the list rather than an item in
      it. Five rules: zero/empty/absent are all silence (the opposite of
      `VramState`, where 0 is the reading that explains the most); the row
      names no topic, no key and no subscriber, with a tools gate failing the
      build if either file spells `_lagged`; the count speaks for ONE
      `period_s` and not the two the schema grants a service's liveness; the
      broker is read by NAME; and one unreadable value refuses the whole total
      rather than being skipped past. `shown` counts the row — `ok` beside a
      non-empty map is what `broker.rs` really writes, and
      `HealthState.rank("ok")` is 0, so a plate bound to `HealthState` alone
      would compose the row and never map the surface. Shot 15 is that
      machine. Two of the eight first-pass survivors were real bugs: the
      broker read by recency (invisible to every name test, fatal on a machine
      where nine services beat every 5 s) and an `expired` never cleared, so
      the row could not come back for a second interval. The box grew for the
      first time without a plate: 775 -> 794 makes the surface **826**, and
      `tst_fit.qml` said so rather than a paragraph.)

- [ ] A76. **jarvisd reports `state: "ok"` while it is throwing frames
      away.** `publish_health` in `services/jarvisd/src/broker.rs` hardcodes
      `SysHealthState::Ok` — the broker is the one service on this machine
      that can never say it is unwell — and it does so in the same body that
      carries a non-empty `drops` map. Every consumer inherits that: `jv
      health` prints `jarvisd ok drops={...}`, and `HealthState.rank("ok")`
      is 0, so `HealthPlate`'s "what is not well" list omits the one service
      that knows something is. A75 works around it with its own row; the
      question underneath is whether the broker should call itself
      `degraded` for the period in which it dropped something, which would
      put it on the existing list with no new reader anywhere. Not obvious
      and not the loop's to take blind: `degraded` on a per-period counter
      flaps by construction (one heartbeat degraded, the next ok), it is
      what `jv health --check` would then exit 1 on, and a broker that
      reports itself impaired for one lost frame is the boy who cried wolf
      on the one topic that must stay readable. A human's call, and it is
      cheap either way — one enum and its tests. Raised with A75.

- [ ] A77. **A75 sums three different failures into one number, and two of
      them are not topics.** The broker's map is keyed by topic for an
      out-queue overflow, by `_lagged` when a subscriber fell so far behind
      the broadcast channel that the ring wrapped, and by `_ctl` for a
      control frame. Those are not the same event: an overflow lost one
      frame of one topic, a lag means the reader missed an unknown stretch
      of EVERYTHING, and a lost `_ctl` is a subscription that may not have
      taken effect. A75 deliberately draws one total in the broker's own
      word (DROPPED) and leaves the map to `jv health`, for two stated
      reasons — the 300 px box cannot hold a topic name (`context.window`
      is 14 characters before a count) and, more importantly, the count is
      aggregated across every subscriber, so naming a topic would invite
      "audio.vad is broken" when the fault is a slow consumer three
      processes away. Whether the corner should ever tell a lag from an
      overflow is a §06 design question with a real argument on the other
      side (a lag is the one of the three that means the HUD's own picture
      may be missing a stretch). Do not build it before answering it.
      Raised with A75.

- [x] A78. **The service that keeps dying is the one that always says it
      is fine.** — 3b9bf1b
      (`HealthState.lives` is the only memory in that file and the comment
      says why: `latestFrom` keeps one frame per publisher, so the beat that
      proves a restart is gone by the time the next one lands. A trusted
      heartbeat whose `uptime_s` is BELOW the last one from the same service
      was written by a different process; `restarted` is the element's own
      word, like `lost` and `unknown`, and a heartbeat that publishes it is
      outside the frozen enum and comes out `unknown`. It ties with
      `degraded` rather than outranking it — the service is running and
      answering, and a three-line list would otherwise drop a jv-voice that
      cannot reach the speakers for a jv-ears that crashed once at boot —
      and it loses that tie to the service's own word. News for
      `period_s * 2`, the same span this file already believes one heartbeat
      for, read off the frame's own body, so **no timer is involved**: the
      beat carrying too large an uptime is the one that takes the row off.
      Forgotten whole on a link drop. `HealthPlate` draws `jv-ears
      RESTARTED 3x`, capped at `99+x` because a tally is the only figure in
      this corner not bounded by a name or an enum. Also: `trust()` now
      requires `period_s` to be a NUMBER — the note A75 left about this file
      (`"5" > 0` is true), acted on the iteration the value became a window
      inside which the HUD calls a service unwell. 26 new QML tests (679,
      was 653), 18 mutations over three gradings, five survivors closed —
      four of them the freshness window hiding the mutation from the
      assertion, one an infinity the bridge cannot deliver at all. Shot 16
      on the contact sheet; `tst_fit`'s crowded corner now drives jv-act
      past the cap (101 heartbeats counting down) so the widest tally this
      plate can print is measured rather than argued. Raised: A81, A82,
      B78.)

- [x] A79. **A confirmation's outcome is on the bus and the HUD throws it
      away.** — 67a9cfc `action.confirm.granted` is the one body field of that
      schema no element reads — `answered_by` IS read, so `ConfirmState`
      knows an answer arrived and by which route (voice, cli, timeout) and
      cannot tell yes from no. A22 asks for the design half (three exits
      drawn differently, and it would be the first fixed-duration element
      in this HUD, so it is deliberately a human's), but the READING half
      is not blocked by that decision and is what A22 would be built on:
      today there is nothing in `core/` that can say a destructive tool
      was GRANTED. Worth separating, because a human answering A22 should
      not also have to write the reader. Raised in iteration 101.
      (`ConfirmState` latches the ending beside the question: `outcome`
      ("granted" / "denied" / "unknown"), `answeredBy` ("voice" / "cli" /
      "timeout" / ""), and the `answeredRequestId` / `answeredTool` /
      `answeredSummary` of the question that ended — kept rather than
      read back off `request`, because everything `textOf` returns is
      gated on `pending` and by then nothing is. Three refusals: only for
      a question this element was HOLDING, only from an answer FRAME
      (`expired` ends the asking and settles nothing; a LATE answer is
      still taken), and `granted` decides and nothing else does — a
      timeout whose `granted` is missing reads `unknown`, because
      inferring the denial off the route would be a second copy of a rule
      the frame already states (A14). Forgotten by a new question and by
      a link drop; nothing else forgets it, which is A22's question. 20
      QML tests (699, was 679), 6 mutations, 6 caught. Nothing DRAWS it
      yet, on purpose. Raised: A83, B79.)

- [ ] A80. **The machine under load is the other half of the sentence
      `HealthPlate` already starts.** `context.system.load1` and
      `mem_used_pct` are unread, and they are the same shape as B40's VRAM
      row: not a gauge (an all-day readout is one nobody reads), but the
      WHY of a Jarvis that took thirty seconds — and unlike the rung, load
      explains a slow turn on a machine whose brain is on the card. The
      whole design question is the GATE, since §06 forbids the standing
      dashboard: `VramState` is gated on `brainOnCpu`, and the honest gate
      here is `SpeechState`'s `thinking` — the one moment a reader is
      waiting and the number is news. That crosses two elements, which is
      why it is a proposal and not a patch. Raised in iteration 101.

- [ ] A81. The restart count VANISHES under a louder word, and the
      collapse is documented rather than solved. `jv-voice DEGRADED` is
      what a jv-voice that is both impaired and crash-looping draws:
      `restarts` is still on the roster entry, and `HealthPlate.detailOf`
      only prints it beside `RESTARTED`, because a bare `3x` next to a
      different word is a tally of nothing a reader can name. The two
      honest ways out are both design questions and neither is free — a
      second line for the same service (the list is three deep, and A70
      already asks what the corner does with several stories at once), or
      a mark that is not a number (a second dot? a different tone?),
      which spends the one vocabulary this plate has on a qualifier.
      §06 question, worth deciding with A70 rather than alone.
      Discovered in A78.

- [ ] A82. **The memory starts when the HUD starts, and the boot crash is
      exactly the one it misses.** A78 claims nothing about the first
      heartbeat it hears — correctly, since a small `uptime_s` is what
      every service looks like on a machine that just booted — but that
      means a jv-ears which died four times before the HUD's bridge
      connected is a jv-ears the corner says nothing about, and the boot
      crash loop is the most likely one there is. systemd knows the
      number (`NRestarts` on the unit), the bus does not, and invariant 1
      says the HUD may not go and ask systemd. Which makes this R5's
      question again with a second caller behind it: a `sys.roster` topic
      that says which services are SUPPOSED to be running could carry how
      many times each has been started, and one publisher reading systemd
      is a different proposition from every consumer doing it. Do not
      build it here — it is a schema, and R5 is already written.
      Discovered in A78.

- [x] B78. The terminal view has the same blind spot the HUD just lost,
      and only one of its two readers could close it. `jv health` prints
      `uptime_s` (cli.rs) and is a SNAPSHOT — one read of `latest`, no
      memory, no second frame to compare against — so it can never say a
      service restarted, however long it runs. `jv tap` watches the
      stream and could: it already holds per-turn state across frames,
      and "jv-ears restarted (3rd time)" on the wire is the line that
      would explain a turn that lost its ASR mid-sentence. Cheap, and it
      is the B-track half of A78 rather than a new idea. What it must NOT
      become is a second implementation of the rule: the freshness window
      and the monotonicity argument live in `core/HealthState.qml`, and
      two readers that disagreed about what a restart is would be worse
      than one that cannot see them. Discovered in A78. — 4b3441d
      (`cli::Lives` is `jv tap`'s only memory of the processes behind the
      heartbeats, and prints `restart jv-ears: 2x (was up >=8.2s)` on the
      beat whose `uptime_s` went backwards. It argues nothing:
      `HealthState`'s rules are kept verbatim — a first sighting claims
      nothing (so A82's boot crash loop is invisible here exactly as it is
      on screen), an unreadable `uptime_s` is SKIPPED and not forgotten so
      the next good frame compares against the last good one, and `<` not
      `<=` because two beats a coarse clock stamped alike are one process.
      The trust gate is now one function, `trust_health`, shared with `jv
      health --check`, so the two readers of `sys.health` in this binary
      cannot come to believe different frames; it is stricter than the
      HUD's in one place (a state word off the frozen enum refuses the
      whole frame), and strictness can only LOSE a death, never invent one.
      The rule deliberately NOT carried over is `restartsOf`'s freshness
      window: it bounds how long a plate DISPLAYS a claim, and a line
      printed once into a stream has no duration to bound. `3x` is
      `HealthPlate`'s notation for the same fact and `>=` is `SayGauge`'s
      mark for a bound — the dead process is only known to have REACHED
      the uptime it last heartbeated. The roster is capped at 64 and past
      the cap a new name is REFUSED rather than evicting the oldest, which
      is the opposite of `Confirmations` and for a stated reason. 11 unit
      tests (151, was 140) + 2 integration (42, was 40), 12 mutations, 12
      caught. Raised: B82, B83.)

- [ ] A83. **An answer to a question the HUD never saw is dropped on the
      floor, and the case is not exotic.** A79 will only write an ending
      for a request_id it was holding — the rule that keeps a stranger's
      answer from blanking a live question — but the HUD starting during
      an open window, or a bridge reconnecting mid-question, means the
      REQUEST frame was missed and the answer lands against an empty
      latch. The user heard the spoken question (jv-voice said it) and the
      screen then says nothing about how it ended, which is the A20 gap
      again one frame further along. Two honest readings, and choosing is
      a §06 call: keep the refusal (the corner reports the end of a
      question it showed, and never a verdict out of nowhere), or accept
      an ending with no question attached and draw it with the tool name
      the answer frame does not carry — which is the real obstacle, since
      `tool` and `summary` are request-only in the frozen schema and an
      ending that can only say "GRANTED" names nothing. Belongs with A22.
      Discovered in A79.

- [x] B79. The terminal has the same half-story A79 just closed for the
      HUD, and jv-act already keeps the other half. `jv act-log` reads the
      audit (services/jv-act/src/audit.rs records `granted` and
      `answered_by`) and is the record AFTER the fact; `jv tap` watches
      the wire, so a confirmation on the stream is two lines a reader has
      to correlate by request_id — the question, then an answer whose
      `granted` is a raw field among others. One line that says "jv-act
      asked: empty the trash — granted (voice, 4.1 s)" is the tap's job,
      and it is the B-track half of A79 exactly as B78 is of A78. Same
      caution as B78: the REFUSALS live in `core/ConfirmState.qml` (only
      a question we saw asked, only an answer frame, `granted` and never
      the route), and a second reader that disagreed about what a denial
      is would be worse than one that only prints fields. Discovered in
      A79. — ca95b21
      (`cli::Confirmations` holds the question half until the answer lands
      and prints `confirm req-4: fs.delete -> granted (cli, 0.2s)`. It
      decides nothing: the three `ConfirmState` refusals are kept verbatim
      — only a question this tap saw asked, only an answer FRAME (nothing
      here times a window out), `granted` and never the route, so an
      absent or non-boolean `granted` is `unknown` even under
      `answered_by: "timeout"`. Seconds, not the ladder's ms, because this
      number is a person deciding. jv-act's echo of the answer is
      deduplicated by the same rule that drops a stranger's answer. 11
      tests (140 unit + 40 integration), 10 mutations, 10 caught. Raised:
      B80, B81.)

- [ ] B80. **The `summary` — the words the user actually HEARD — is on no
      line the tap writes, and under `--latency` it is nowhere at all.**
      B79 prints the tool and not jv-act's spoken question, because eighty
      columns holds one of them and the tool is the name the same event
      goes by in `intent.action`, in the audit and in `jv act-log`. In
      plain `jv tap` that is defensible: the request frame is printed
      verbatim two lines up. Under `--latency` it is not — that mode
      prints hop lines instead of frames, so "Delete 3 files from
      Downloads" exists in the process and is discarded. The honest ways
      out are a SECOND line under the confirm line (the shape the turn
      ladder already uses for a span it divides) or a `--wide` that stops
      pretending 80 columns is the budget, and both are choices about what
      `jv tap` is for rather than patches. Discovered in B79.

- [ ] B81. **A question nobody answered is the one case this prints
      nothing for, and it is jv-act dying mid-window.** B79 writes a line
      only when an answer frame closes a question, on purpose: timing a
      window out here would be the tap inventing an ending the machine
      never stated, which is exactly the refusal `ConfirmState` makes
      (`expired` settles nothing). But the consequence is that a jv-act
      which asked and then died leaves `jv tap` silent about the most
      alarming confirmation there is — the question sits in
      `Confirmations` until the cap pushes it out, unreported. The HUD has
      the same hole and answers it with a backstop it OWNS and labels as
      its own (`windowFallbackS`); the tap's equivalent would be a line at
      the summary, "1 question was never answered", which is a report
      about the TAP's own observation and not a verdict about the tool.
      That is a different kind of line from every `>>>` the tap writes
      today, which is why it is a proposal. Discovered in B79.

- [ ] B82. **`jv health --check` holds a window and still cannot see a
      restart, and it is now one line from being able to.** B78 put the
      memory in `jv tap` because that is where PLAN said it went, but
      `HealthCheck` already keeps per-service state across a whole `--for`
      window (`says` does exactly the backwards-counter trick for
      `llm_first_says`) and already reads `uptime_s` through the shared
      `trust_health`. So a service that died and came back INSIDE the six
      seconds `--check` listens is a service `--check` currently reports
      as `ok`, and its exit status says the machine is well. The question
      that makes this a proposal rather than a patch is what it should do
      about it: `--check`'s whole contract is one word per service out of
      the frozen enum plus `lost`/`unknown`, and `restarted` would be an
      eighth word AND a new non-zero exit — which is `jv health --check`
      failing a machine that is, at the moment it is asked, entirely
      healthy. The HUD chose to rank `restarted` level with `degraded`
      (A78); doing the same here makes a boot-time crash loop fail the
      check for one window and pass the next, which is a flapping gate.
      Worth deciding with A76, which is the same flap question about the
      broker. Discovered in B78.

- [ ] B83. **The restart line says how many, and nothing anywhere says
      when.** `restart jv-ears: 2x` counts deaths since the tap connected,
      and two deaths four hours apart print identically to two deaths four
      seconds apart — the crash loop and the unlucky afternoon read the
      same. `was up >=8.2s` carries the distinction only for the life that
      just ended, which is the wrong half: a reader chasing a crash loop
      wants the RATE. The tap has the frame's `ts` in hand and could say
      it (`2x, 11.4s apart`), and under `--latency` the hop line above
      already carries the clock — but a third number on a line that is
      already three is the kind of growth `Turn::lines` exists to refuse,
      and the honest alternative is a count at the SUMMARY, where `jv tap`
      already says what it saw once the stream stops and where "jv-ears
      restarted 26 times in 4 minutes" is a sentence rather than a
      fragment. That summary does not exist for anything but latency
      today, which is the real cost and why this is a proposal. Discovered
      in B78.

- [x] B84. **jv-ears throws captured audio away without counting it, and a
      comment says otherwise.** `MicSource.chunks` in
      `services/jv-ears/jv_ears/audio.py` hands PortAudio a callback with
      two silent discards in it: `except queue.Full: pass` (the mic queue
      is `maxsize=64`, drop-newest, so a pipeline that falls behind loses
      whole chunks of the room) and `if status: pass` under the comment
      "Overruns are logged by the caller via health" — nothing anywhere
      logs them, so the comment asserts a mechanism that does not exist.
      Neither loss reaches `sys.health`: `CaptureMeter` counts what the
      device DELIVERED, which is the wrong side of the queue, so the
      heartbeat says `ok`, `capture_age_s` stays fresh, `captured_s` keeps
      rising and `MicPlate` draws a calm MIC while the ASR is being fed a
      recording with holes in it. It is the 2026-09-15 field bug's twin —
      ears up and cheerful, audio gone — and it is the missing MEASUREMENT
      behind two human-review items (optimization-backlog §2, the O(n^2)
      partial re-transcribe on the perception thread, and §6, the ~2.2 s
      final transcribe): both are arguments about whether the mic starves,
      and nothing on this machine can currently answer it. No schema
      change — `state` is the frozen enum and `degraded` is in it, and
      jv-ears already degrades for a stall, so this is the same publisher
      making the same shape of claim about the same fault. The flap worry
      that blocks A76 does not apply: `HEALTH_MIN_GAP_S` already floors
      the transition beat at 1 s. Raised in iteration 105. — 97bac94
      (`Loss` is two facts and not one total, because they send a reader to
      different places: `samples` is what jv-ears dropped and PortAudio
      tells the callback exactly how many frames went with it, `overruns`
      is what the DEVICE dropped and its length is not knowable — so it
      stays a count and is never made into seconds. `_overflowed` reads
      the one flag that means discarded input rather than the truthy
      `CallbackFlags`, so an output underflow cannot put a fault on the
      heartbeat that never happened, and `getattr` keeps a differently
      shaped status object from becoming an exception on the audio thread.
      The queue policy is untouched — this is the measurement, not the
      fix. The fault ships on `state` + `notes` and adds NO gauge (B7;
      A84 is where the numbers go), so every existing consumer reads it:
      HealthPlate, `jv health`, and `jv health --check`, which now exits 1
      on it. Two orderings are decisions with a test each: a stall
      outranks a loss (both degraded, and "no audio at all" is the note
      wanted first), and a loss outranks `starting`, because the queue can
      fill before the pipeline thread has pulled its first chunk and the
      discard is then the only evidence there is. `callback()` is a method
      rather than a closure so the code that decides what counts as lost
      audio can be called without a sound card. 22 tests (136, was 114),
      12 mutations, 12 caught — the twelfth only after a run showed
      `test_every_discard_moves_the_stamp_forward` passing for the wrong
      reason: its fake clock started at 0.0, and 0.0 is falsy, so
      `last_loss_at or clock()` restamped anyway. Raised: B86, and it is
      about the gate rather than about ears.)

- [x] A84. **The mic indicator draws MIC while audio is being lost — the
      HUD half of B84.** Once jv-ears counts its discards, `MicState`'s
      three words (`live` / `stalled` / `off`) are one short: a device that
      is open, delivering, and losing chunks reads as `live`, which is the
      "not fakeable" half of invariant 10 quietly over-claiming. The shape
      is already there — `stalled` is a freshness rule over a gauge and a
      published budget (A14, `core/EarsBudgets.qml`), and a loss window is
      the same rule over a different gauge — so it is one derived reading,
      one second word on `MicPlate` ("MIC LOSING AUDIO" beside the
      existing "MIC NO AUDIO"), and one `BUDGET_MIRRORS` entry. What it
      needs first is the gauge: B84 deliberately ships the fault on
      `state` + `notes` only, because B7 forbids putting a number on the
      bus before something reads it, so the gauges this element wants
      (`mic_lost_s`, `mic_loss_age_s`, `mic_loss_window_s`) arrive WITH
      this item or not at all. The one real argument against: HealthPlate
      already draws `jv-ears DEGRADED` off B84, and ReplyState (A71)
      refused `finish_reason: error` for exactly that reason — two plates,
      one corner, one event, which is A62. The counter-precedent is in
      this same plate: `stalled` is already both a `degraded` heartbeat
      AND a MicPlate word, because the privacy indicator answers "what is
      being recorded" and the health list answers "what is unwell", and
      those are different questions. Worth building on that precedent,
      but it is the corner's crowding question again (A62/A70). Raised in
      iteration 105. — 40e5a90
      (Built on that precedent, and TWO gauges rather than the three
      guessed above. `capture_loss_age_s` is the measurement — absent
      until something HAS been discarded, so its absence is "nothing was
      lost" and not an ears that forgot to say — and `capture_loss_window_s`
      is the budget, riding from the first heartbeat beside
      `capture_stall_s`, because before the first loss the window is what
      tells a reader what the absence MEANS. The third, how MUCH was lost,
      was left off deliberately and that is B7 answered rather than
      ignored: half of it can never be a number (a device overrun has no
      length), so a run losing audio only that way would publish a zero
      total beside a degraded state — B13's number that stopped meaning
      its label. The amounts stay in `notes`, named by culprit, where
      nothing computes with them.
      The word is ranked, not added: `stalled` outranks `losing` outranks
      `live`, which is jv-ears' own order in `CaptureMeter.health()`, so
      the plate cannot contradict the heartbeat it was drawn from, and
      `<=` is the same inclusive boundary on both sides. `capturing`
      stays TRUE through `losing` — a microphone dropping chunks is still
      recording the ones it keeps, and the privacy light is not a quality
      light. A loss age that is present but unreadable reads as `losing`,
      not `live`: jv-ears publishes it only once something was discarded,
      so the PRESENCE is the evidence and the value only dates it — the
      same asymmetry that already makes an unreadable `capture_age_s`
      come out `stalled`.
      Tests: 10 new QML cases (652 test functions, was 642; `qmltest.sh`
      709 passed) and 7 new ears (142, was 136),
      plus the `BUDGET_MIRRORS` entry (three mirrored budgets now) and
      the plate-binding row that fails the build if MicPlate ever runs the
      loss window off the fallback. One more in `tools`: the screenshot
      sheet's two mic exposures are now PINNED to carry no loss gauge,
      because the A43 growth window measures a plate ARRIVING and a
      MicPlate that silently got wider would measure something else.
      `hudscreens.sh` re-run and looked at: the mic exposure still draws
      the narrow `MIC` at (2485, 16, 2543, 50) and the deaf pair still
      grows 43 px, so nothing already photographed moved. Raised: A85,
      B89.)

- [x] B85. **`speech.state.reason` is read by nothing in this repo, and it
      is the only field of that frozen schema in that position.** The enum
      has four words — `completed`, `wake`, `preempted`, `error` — and they
      say how an utterance ENDED: jv-voice publishes them at
      `services/jv-voice/jv_voice/service.py` (`idle`+`completed` for a
      finished turn, `interrupted`+`wake` for a barge-in,
      `interrupted`+`preempted` for an urgent utterance cutting one off,
      `idle`+`error` when synthesis or playback threw). Nothing reads
      `reason`: not `core/SpeechState.qml`, which draws INTERRUPTED for
      both of the middle two, and not `cli.rs`/`jv.rs`, where
      `SpeechStateReason` is a typed enum in `schema.rs` with no caller.
      Two halves, and they are not equal. The HUD half is WEAK and should
      probably stay unbuilt: `error` rides an `idle` frame (so the plate
      draws nothing), but the same `except` block beats `degraded` with
      the failure in its notes one `await` later, and HealthPlate draws
      that — reporting it again is the duplication A71 refused. What is
      left there is `wake` vs `preempted`, and "you stopped me" versus "I
      stopped myself to say something more urgent" is a real distinction
      worth maybe one word. The TAP half is the stronger one: `jv tap
      --latency` measures a turn to `speech.say` and never says how the
      turn ENDED, so a reply that died mid-synthesis and one spoken in
      full are timed identically and reported identically — the
      measurement says `respond 2.1s` about words nobody heard. That is
      B13's "a number stops meaning its label" failure with the label
      still attached. Raised in iteration 105.

      **Done — the TAP half only, c0f8632.** `cli::Endings` reads the
      ending back onto the turn with no new publisher and no schema
      change: jv-voice publishes exactly ONE terminal `speech.state` per
      reply (`_speak_turn` speaks a whole `reply_group` and leaves it),
      that frame carries a `say_id`, and the `speech.say` beside it
      already threaded the same id to an `in_reply_to_utterance`. One
      line per turn — `turn utt-4: reply ended wake (you cut it off)` —
      and a table under the turn summary that says how many of them did
      not complete. Three things the item did not know. The `say_id` seam
      is a JOIN and not a field read, which is why this cost a reader
      rather than a line. Two written-down lists were avoidable and both
      were avoided (B87's lesson bought cheaply): the vocabulary is
      parsed by the GENERATED `schema::SpeechStateReason`, so it is the
      schema's and not a copy of it, and `ending_slot` is an exhaustive
      match over that enum, so a fifth word stops this file COMPILING
      rather than going untallied. And silence had to be said out loud:
      a tap that reported turns and saw none of them end prints the gap
      and names the frame it wanted, because an empty table reads as
      "they all finished". 12 unit + 2 integration tests; six mutations,
      six caught. The HUD half stays unbuilt as argued. Raised: B91, B92.

- [x] B86. **`verify.sh` cannot see a whole service, and jv-ears is that
      service.** `tools/dependents.py` resolves an import to a path with
      `_module_path`, which asks for `<base>/<top>/__init__.py` or
      `<base>/<top>.py` — and `services/jv-ears/jv_ears/` is the ONE service
      package in this repo with no `__init__.py` (the other seven have one;
      `[tool.setuptools.packages.find]` finds it anyway because setuptools'
      pyproject discovery defaults to `namespaces = true`). So `import
      jv_ears` resolves to nothing, the closure walk stops at the first
      edge, and `bash ops/ralph/verify.sh` over a change to
      `jv_ears/audio.py` plans ONE gate — `runtests.sh tools`, which reaches
      it as TEXT — and never `runtests.sh jv-ears`, the suite that actually
      executes it. Field-verified in iteration 105: the gate went green in
      35.8 s over a change whose own 136-test suite it had not run. It is
      B68's exact failure with the roles reversed — there the guess missed
      the third suite, here the derivation misses the first one — and it is
      silent in the direction that matters, because a suite that is never
      named cannot report that it was skipped. Two fixes and they are not
      equal: `touch services/jv-ears/jv_ears/__init__.py` closes THIS hole
      in one line and consistently with the other seven, and leaves the next
      namespace package to reintroduce it silently; teaching `_module_path`
      that a directory of `*.py` with no `__init__.py` is importable (PEP
      420, and it is how this one is really imported) closes the class. Do
      both — the second is the gate's own rule and wants a `tools` test
      pinning it, the first is what makes jv-ears look like its siblings.
      Discovered while verifying B84. — 1da7d1d
      (Both, and the second in TWO passes rather than one: a directory with
      no `__init__.py` is a namespace *portion*, which the interpreter does
      not stop at either — it keeps searching and lets a real package or a
      plain module found later win — so resolving it eagerly, on the accident
      of which base sorts first, would aim an import at source Python does
      not read, and a wrong suite is more confident than a missing one.
      Narrowed in one place: a portion must be a directory with Python under
      it, asked of `_module_files`, so `import docs` cannot claim every PNG
      in the repo. Four new `tools` tests (440, was 436), two RED first; the
      proof is the gate itself, which now plans `runtests.sh jv-ears` for a
      change to `jv_ears/audio.py` and did not before. Five mutations, five
      caught — after TWO survived the first grading, both real test
      weaknesses: the precedence decoy sat under `svc-c`, which loses to
      `svc-a` on sorted bases even with the passes merged, and the depth of
      the Python-under-it rule had no test at all. Raised: B87, B88.)

- [ ] B87. **The file test was written down and it was wrong (B86); the BASE
      LIST is written down too.** `_package_bases` returns `["", "tools",
      "harness"] + services/*`, which is right today only because all eight
      `pyproject.toml` files in this repo live under `services/`. A ninth
      Python package anywhere else — `shell/jv-hud/tools/`, a `bench/`, a
      second library beside `pylib` — is a directory no base names, so every
      `import` of it resolves to nothing and the closure walk stops at the
      first edge again. That is B86's failure by a different mechanism: B86
      was the FILE test being a written-down rule, this is the SEARCH PATH
      being one, and both fail the same silent way, because a suite that is
      never named cannot report being skipped. The derivation is sitting
      there: a base is a directory with a `pyproject.toml` in it, plus the
      repo root and the two package directories that have none (`tools`,
      `harness` — and `harness/` has no `__init__.py` either, so it is this
      repo's SECOND namespace package; nothing imports it by that name today,
      which is the only reason B86 had one instance and not two). Wants a
      `tools` test pinning that every pyproject directory is a base.
      Discovered while fixing B86.

- [ ] B88. **Every Python file in this repo is read by at least one suite —
      measured, 0 unread — and nothing asserts it.** What B86 landed is the
      claim that a service suite reads its own package; the whole-repo form
      is the one that catches a file no gate covers AT ALL, which is a
      different and worse gap than a missed reader (there some suite still
      runs it; here none does). It is true right now: every `*.py` outside
      `SKIP_DIRS`, checked against `dependents.suites(ROOT)`, has a reader —
      so this is a green test waiting to be written rather than a fix. Note
      what it would NOT have caught: before B86 `tools` read every `jv_ears`
      module as TEXT, so the whole-repo claim was already true while the gate
      was already broken. It guards a different edge — a new `tools/` script
      or harness module that no suite names — and its failure message has to
      say so, or the next author to add a file will read it as a mysterious
      veto. Discovered while fixing B86.

- [x] A85. **The new word is on no photograph.** `docs/hud/screens/` has
      a mic-and-health window (A43) precisely because ONE jv-ears
      heartbeat can light two plates at once — and the A84 word is the
      same coincidence one fault along: a device that is open, delivering
      and discarding chunks is `MIC LOSING AUDIO` on MicPlate AND
      `jv-ears DEGRADED` on HealthPlate, off a single re-published beat.
      So the sheet has a ready-made shape for it and does not use it: the
      only mic line anyone can see in the repo is `MIC NO AUDIO`, and the
      wider one ships unphotographed. It is a `sheet.MIC_LOSSY` fixture
      (MIC_OPEN's body plus `capture_loss_age_s`, `state: degraded`, the
      loss note) and a window that measures the plate getting WIDER
      rather than a plate arriving — which is a growth assertion this
      harness does not have yet, and is the interesting half. Cost is the
      real objection: the probe is already 158 s of the gate's 193 s and
      every window is another idle hold. Discovered while building A84.

      **Measured against, on paper, before anybody builds it (iteration
      108).** The widening this item wants to assert may be worth about a
      pixel. `MIC LOSING AUDIO` is 16 monospace characters, so MicPlate
      comes to pad·2 + dot + gap + 16·(6.6 + 1.54) ≈ 165 px; `jv-ears
      DEGRADED` on HealthPlate comes to pad·2 + dot + gap + 7 chars + gap
      + 8 chars ≈ 165 px as well. The two plates are in the same
      right-docked column, so `drawn_box`'s left edge is the WIDER of
      them, and the only pair that isolates the mic line — `deaf →
      lossy`, where the health line is identical under both — would move
      it by a pixel or two or not at all. (`open → lossy` is not that
      pair: it brings HealthPlate with it, so it grows downwards too and
      is A47 all over again.) That is arithmetic and not a measurement,
      and it should be MEASURED before the assertion is designed, because
      if the answer is zero the shape of this item is wrong. The awkward
      part is that `losing` can never be the only plate lit: a losing
      device is `degraded` by `CaptureMeter.health()`, so MicPlate and
      HealthPlate are welded — which is the same coincidence that made
      this item attractive. Noted while building B89.

      **The cost objection above is wrong, measured (iteration 111).** It
      prices this as another idle hold, and B93 showed a SHOT is not one:
      adding `05-preempted` moved the run from 183.8 s to 184.0 s, because
      a shot costs a settle and a jarvisd/jv-hud pair while an idle window
      costs six seconds plus its control. So the PHOTOGRAPH half of this
      item — a `sheet.MIC_LOSSY` fixture and a shot that puts `MIC LOSING
      AUDIO` on the sheet — is ~2 s and should just be taken. What stays
      expensive is the half this item leads with: the growth assertion,
      for a widening its own paragraph above computes at about a pixel.
      Split it: take the picture, and leave the assertion to whoever wants
      to measure the pixel first.

      **Done, the photograph half — and only that half — 61a326e.**
      `sheet.MIC_LOSSY` and `06-lossy`, one primary-only shot of one
      heartbeat, with seven tests in `tools/tests/test_hudscreens.py`
      and a caption. The growth
      assertion this item LEADS with is NOT done and is now A86: it was
      split off rather than dropped, and the pixel it would measure has
      still never been measured.

      Four things the item did not know. (1) The fixture is the first one
      in this sheet held to what the service actually sends: its gauges
      are the exact set `CaptureMeter.metrics()` writes for an open,
      delivering, losing device, and its `notes` is the sentence
      `loss_note()` composes. MIC_OPEN and MIC_DEAF are NOT — they carry
      a narrower pre-A84 gauge set and a hand-waved note — and MIC_OPEN's
      narrowness is load-bearing, because A43's window is measured on the
      absence of the loss pair. MIC_DEAF's note is not load-bearing and is
      simply wrong; see A87. (2) The method is `metrics()`, not
      `gauges()` — the test asserting the fixture against it was written
      against the wrong name and went red immediately, which is the gate
      working. (3) "Which plates does this frame light" could not be
      answered by grepping plate files for the element names: every plate
      NAMES the others in prose, and `MicState|HealthState` matched
      LinkPlate and StatePlate. It has to be the declaration
      (`MicState {`), and the fifth reader — EarsBudgets, which StatePlate
      also takes — lights nothing on its own and needed saying separately.
      (4) The shot needs no `hold`: jv-ears declares `period_s: 5` and
      both readers believe a beat for two periods, so ten seconds against
      a shot that is over in about four. 04-unheard needs a feed because a
      `context.system` snapshot expires in three SECONDS, which is a
      different number than the one that paragraph implies.

- [x] B89. **A plate can silently stop drawing a word its state element
      can produce.** MicState now has five readings and MicPlate draws
      three of them, two by deliberate silence — and the mapping lives in
      one ternary in the plate with nothing anywhere asserting it covers
      the enum. Add a sixth word tomorrow and the plate draws `MIC` over
      it: no test goes red, because the QML suites test the ELEMENT (they
      are headless, and plates import the Quickshell singletons a headless
      run cannot load, A56) and the screenshot sheet only photographs the
      states somebody remembered to stage. It generalises past this plate
      — SpeechState, ReplyState, ActionState and HealthState all publish
      derived words some plate switches on — so the shape is one `tools`
      test reading both files as TEXT: collect the string literals an
      element can return for its `state`, collect what the plate's file
      mentions, and fail on a word the plate never names. It is B88's
      class (a claim about a relation nothing asserts) and it has the
      same trap: the failure message has to say "drawing it as nothing is
      a decision — name it and say so", or the next author reads a
      mysterious veto. Discovered while building A84.

      **Done — 5a5ccf0.** Built as described, in
      `tools/tests/test_gen_theme_qml.py`, and it was RED on the three
      words MicPlate never named (`live`, `losing`, `stalled`); the plate
      says which line each one draws now, and which of them the ternary
      reaches by falling off the end. Three things the item did not know.
      One literal had to be excluded and exactly one — the operand of
      `typeof m.capture_age_s === "number"`, a JavaScript type name
      sitting inside MicState's `state` block. "Names it" had to mean
      backticks or quotes rather than a bare occurrence, because `live` is
      already in MicPlate's first line inside "the live-microphone
      indicator" and a gate a passing sentence satisfies fires on nothing.
      And it needed non-vacuity at BOTH ends: it finds its work by a
      convention (a `state` block in an element a plate declares), so it
      asserts it found pairs at all AND that every element in `core/` with
      a word set is drawn by a plate it checked. What it does NOT cover is
      B90.

- [ ] B90. **B89's gate finds its work by a convention, and four other
      closed word sets do not follow it.** An element that decides between
      a fixed set of words calls the result `state` and writes it as a
      block — that is how the new gate finds a word set at all, and only
      `core/MicState.qml` and `core/SpeechState.qml` do it.
      `core/ConfirmState.qml` (`outcome`, `answeredBy`),
      `core/LinkState.qml` (`reason`), `core/OutputState.qml` (`silence`)
      and `core/HealthState.qml` (`llmBackend`) each decide between
      literals in exactly the same way under a different name, and every
      one of them is read by a plate. So the silent failure B89 closed is
      still open four times over. The naive generalisation does not work
      and it is worth writing down why: "every block-bodied `readonly
      property string` in an element" also collects
      `HealthState.beatKey`, whose literals are separators like `"@"`, and
      a gate demanding a plate name `"@"` is one the next author deletes.
      The options are a convention (rename the four, which moves a lot of
      code for a test) or a rule that can tell a word set from a key
      builder — perhaps "every literal reachable at a `return`, plus every
      literal an `===` compares the returned variable against", which is
      the shape SpeechState already forces. Neither is obviously right.
      Discovered while building B89.

- [x] B91. **Two readers of `speech.state`, and only one of them reads the
      whole frame.** `jv tap` now tells `wake` from `preempted` — "you
      stopped me" from "I stopped myself to say something more urgent" —
      and `shell/jv-hud/core/SpeechState.qml` still draws INTERRUPTED for
      both, because it reads `state` and not `reason`. That is the first
      time in this repo two consumers of one topic disagree about how much
      of it is legible, and the asymmetry points the wrong way: the CLI a
      developer runs for an hour knows something the HUD a user watches all
      day does not. B85 called this half WEAK and it still is — it is worth
      exactly one word, and the honest objection is that `preempted` is
      rare enough that nobody has seen one — but the argument has changed
      shape now that the distinction exists somewhere. What it would cost:
      a fifth word out of `SpeechState`, which is B89's gate territory (the
      plate must NAME it), and A62's corner is already crowded. Raised
      while building B85's tap half.

      **Done — 4c2dead.** Built as one word, as the item asked.
      `interrupted` + `reason: preempted` is PREEMPTED; `wake`, a missing
      `reason`, a non-string one, a word a later schema adds, and one that
      contradicts its own state are all INTERRUPTED, which stays true of
      every one of them. Three things the item did not know. (1) The plate
      cannot GROW: `preempted` is 9 characters against `interrupted`'s 11,
      so the crowded-corner objection does not apply to this word and this
      is not an A85. (2) The test helper was already lying — `speech(voice,
      state, over)` put its third argument on the ENVELOPE, and four call
      sites passed `{"reason": "completed"}` into it, so a body field was
      landing where nothing reads one; the helper now takes `(voice, state,
      body, over)` like `wake`/`ask`/`reply` beside it, and those four
      fixtures say what they meant. (3) `reason` rides transitions other
      than `interrupted` — `completed` and `error` land on the following
      `idle` — and reading it there would have put a word on a plate that
      must keep drawing nothing, so the check is nested under the
      `interrupted` branch rather than standing beside `listening`. What it
      does NOT do is put the word on a photograph, which is B93.

- [ ] B92. **The endings table counts them and the percentiles still mix
      them.** `--- turn endings: 9 ... 4 of these 9 did not complete` is a
      warning printed UNDER the very rows it is a warning about: `respond`
      p50 is still one distribution over the turns that were heard in full
      and the turns that were talked over after two words. B85's own
      sentence — "the measurement says `respond 2.1s` about words nobody
      heard" — is now SAID and not yet FIXED. The fix is a split: `respond`
      and `total` over completed turns, beside the same spans over the ones
      that ended some other way, which is the shape `you`/`ran` already
      have under `tool`. Two obstacles, and the second is the real one.
      (1) `TurnStats::push` happens at the first word and the ending lands
      later, so a sample would have to be MOVED between two vectors after
      the fact — `brain_split` already does exactly that for `think`, so
      there is a pattern. (2) The two tables are over DIFFERENT SETS and
      nothing measures the difference: a reply whose input boundaries this
      tap never heard is an ending with no turn, and a turn whose ending
      never came is a turn with no ending. `Endings::summary` says so in
      prose precisely because it cannot say it in a fraction. A split
      distribution would have to refuse the unmatched turns rather than
      quietly bin them as completed — which is the whole rule, and the one
      a naive implementation breaks. Raised while building B85's tap half.

- [x] B93. **The new word is on no photograph, and this time it is cheap.**
      `docs/hud/screens/` has no StatePlate shot of PREEMPTED (B91), the
      same gap A85 records for `MIC LOSING AUDIO` — but without A85's two
      difficulties. The word needs exactly ONE composed frame (`speech.state`
      with `state: interrupted, reason: preempted`, src `jv-voice`), no
      heartbeat behind it, and no second plate welded to it: nothing else in
      the corner reacts to a `reason`, so the window isolates one plate
      saying one word. And it cannot be a growth assertion — `preempted` is
      SHORTER than `interrupted`, so the box does not move and the
      assertion is the ordinary one this harness already has (a plate
      arrived, with this caption). The objection is the only one that
      matters here and it is A85's: the probe is already most of the gate's
      3 minutes and every window is another idle hold. Worth pairing with
      A85 in one iteration if anybody ever pays that cost, since they buy
      two words for one hold. Raised while building B91.

      **Done — fe69aa8, and the cost objection was wrong.** `05-preempted`
      is one composed `speech.state` on the primary, and adding it took the
      run from 183.8 s to 184.0 s: a shot is a settle and a process pair
      (~2 s), not an idle window (~20 s). A85's cost paragraph, and this
      one's, were both pricing a shot as if it were a window — so the
      objection that held both of them up does not apply to the half that
      is a PHOTOGRAPH, and A85's photograph half is now cheap for the same
      reason. What is still expensive in A85 is what it always was: the
      growth assertion this harness does not have, for a widening its own
      iteration-108 note computes at about a pixel.

      Three things the item did not know. (1) FOUR elements in `core/`
      read `speech.state`, not two — ActionState and HeardState read it as
      an exit from an outcome and a heard line. The shot is still one
      plate, but for three separate reasons (each of the three needs a
      subject topic this shot does not publish), and the test states each
      of them rather than the one the item assumed. (2) Adding a picture
      retires A73's staleness notice, because the notice derives the
      pictures' box from the commit that last wrote one — see A73.
      (3) **B94**, which is the real find.

- [ ] B94. **Human decision: the HUD draws two words nobody can read.**
      Photographing PREEMPTED (B93) is what made this visible.
      `services/jv-voice/jv_voice/service.py` publishes `interrupted` and
      then `idle` in the very next statement, with nothing awaited between
      them (`_speak_one`, both branches) — and core/SpeechState.qml draws
      `idle` as NOTHING. So INTERRUPTED and PREEMPTED are on screen for as
      long as it takes one frame to follow another over a Unix socket.
      That has been true of INTERRUPTED since A3 and nothing in this repo
      said so until the caption under `05-preempted-primary.png` did.

      It is a human's call because every fix is a decision the loop should
      not make alone, and they are in three different places:

        · **jv-voice stops sending the redundant idle**, or delays it. It
          is a service change in the publisher, it changes what every
          consumer sees, and `interrupted` already means the turn is over
          — the `idle` after it carries no `say_id` and tells nobody
          anything. Cheapest, and the most likely to be right.
        · **SpeechState holds the word** for a second or two the way
          HeardState and ConfirmState hold theirs. A latch, in the element
          that has been careful not to grow one; and a HUD asserting a
          state the bus has replaced is the direction this file has always
          refused to err in.
        · **Nothing** — the word is for a log or a replay, not a screen,
          and the plate should simply not draw it. That is a real answer
          and it retires B91's screen half rather than fixing it.

      Whichever it is, `docs/hud/screens/05-preempted-primary.png` is the
      picture to argue over — it is what the word looks like when it IS on
      screen. Note the shape this shares with A22 (what the corner should
      do with a confirmation that ENDED) and A62/A70: all of them are "the
      HUD has something true and momentary to say, and nobody has decided
      how long it says it for." Raised while building B93.

- [x] A86. Nobody had ever measured the plate getting WIDER. — 0aa0865
      (The measurement came FIRST, as A86 demanded, and the answer is
      **zero**: `deaf -> lossy` photographed through the real compositor
      draws at (2380, 16, 2543, 93) under BOTH readings. `MIC LOSING
      AUDIO` and `jv-ears DEGRADED` are both sixteen characters of 11 px
      mono, both plates measure 164 px, and the union of them is the same
      four numbers whichever word the microphone line is saying — A85's
      "about a pixel" was generous. So the item was wrong in shape exactly
      as it said it might be, and became the other thing it named: the
      rectangle is the plate's OWN BAND.
      `sheet.row_bands` cuts the drawn rows into plates (the stack leaves
      `Theme.gapPx` of untouched desktop between them and every plate is a
      filled rectangle of glass, so a contiguous run IS a plate),
      `drawn_bands` measures each, and `sheet.widened` is the geometry one
      plate has: top, bottom and right pinned exactly, left strictly
      further out. Strictly — the two readings differ by four characters
      and nothing else. `06-lossy` declares `widens_from: [MIC_DEAF]`, the
      only fixture it can be measured against (same `degraded`, same
      service, so HealthPlate is identical and only the mic line can
      move), and the run refuses a pair whose plate COUNT changed or whose
      OTHER bands moved. Measured: band 0 goes (2412, 16, 2543, 50) ->
      (2380, 16, 2543, 50), **32 px wider**, band 1 and the union
      unchanged. The trap has its own test: this shot declares no `hold`,
      so without an explicit re-publish the settle SLEEPS and the picture
      committed is of the exposure that was supposed to be thrown away —
      passing every check, because the plate really did widen when it was
      measured. Costs ~2 s. Tests: `bash ops/ralph/runtests.sh tools`,
      `bash ops/ralph/hudscreens.sh` (199.0 s, 9 screens, all matching
      HEAD — nothing on screen moved, which was the condition).)

- [x] A87. `MIC_DEAF`'s note was not a sentence jv-ears can send. — 93605f8
      (Landed in iteration 113, whose journal and plan commit was never
      made; marked done here from the commit. It found a third fault A87
      had not seen: all THREE mic fixtures said `capture_stall_s: 2.0`,
      and that gauge is `CaptureMeter.STALL_S` shipped verbatim, which is
      1.0. `notes` became the age `CaptureMeter.health()` really sends,
      `capture_loss_window_s` was added to both older fixtures, and the
      gauge A87 said nobody should add — `capture_loss_age_s` on MIC_OPEN,
      which A43's idle window is measured on the absence of — was not
      added. Nothing on screen moved and that was the condition for doing
      it at all.)

- [ ] A88. **The other six growth assertions are blind in exactly the way
      A86 just fixed.** `drawn_bands` exists and is asked by ONE shot.
      All six `sheet.grew_downwards` callers — the idle probe's five
      (A49's window asks twice) and `04-unheard`'s `grows_from` in the
      shot loop — measure `drawn_box`, the union, so a plate that stayed put
      and said a longer word is invisible to all of them, which is the
      thing A86 photographed and found to be worth zero pixels of union.
      This is not "convert them all": each of those six is asking a
      question the union genuinely answers (did a plate ARRIVE), and a
      band rule bolted onto them would be a second claim nobody asked for.
      What is worth doing is naming which of them has a widening it should
      care about. Discovered in A86.

- [ ] A89. **A band's WIDTH is very nearly the word, and that is the
      closest anything in this harness has come to A47.** A47 is the open
      question that `grew_downwards` can prove a plate arrived and never
      WHICH plate. The bands measured in A86 say the corner's 11 px mono
      is linear and tight: `MIC` (3 chars) is 59 px, `MIC LOSING AUDIO`
      and `jv-ears DEGRADED` (16) are 164 px each — 8.08 px per character
      over 34.8 px of plate — and 02-heard's top band of 99 px lands on 8
      characters to within a twentieth of one. So a band of width W
      implies a character count, and a plate that said a DIFFERENT
      sixteen-character line would still pass A86's gate.
      Whether that should become an assertion is the open part, and the
      trap is real: the fit is measured over three points from two shots,
      on one font at one size, under a software renderer. A width-to-chars
      rule that drifted would fail pictures that are right. Measure more
      of the sheet's bands against the words their captions name before
      writing any rule. Discovered in A86.

- [ ] A56. The sequence suite runs in `ops/ralph/hudshots.sh` and NOT in
      `nix build .#jv-hud`, so the strongest assertion about what the HUD
      shows is not in the build gate. The obstacle is real: the plates need
      the stage (two Quickshell singletons substituted), the stage is
      assembled by a shell script that shells out to nix, and a derivation
      cannot run that — so gating it means a SECOND implementation of the
      staging, which is a thing that drifts, and the drift would mean the
      sheet and the gate photograph and assert different HUDs. Options, for
      a human: (a) accept it — the loop runs `hudshots.sh` on every HUD
      iteration; (b) move the staging into a small generator both the script
      and the derivation call; (c) put the stubs in the shell as build-only
      files so no staging is needed at all (invites a stub reaching a real
      screen, and is probably wrong). Discovered in A54.

- [x] A57. The two windows that hold up the pair of plates a turn puts on
      screen were pinned equal at 30 s and kept time DIFFERENTLY. — 3f6c144
      (`HeardState.anchor`: the hold is timed from the `audio.vad
      speech_end` of the utterance those words belong to — the same frame
      SpeechState times "thinking" from — matched by `utterance_id`, with
      the transcript's own `ts` as the fallback when that boundary was not
      seen. The fallback is the old behaviour and errs the old way, too
      long rather than too short; nothing here decides whether the line is
      SHOWN. `audio.vad` was already subscribed and is never rendered.
      Eight new cases in `tst_heardstate.qml` (495, was 487), one of them
      pairing the two real elements on one bus with real timers; nine
      mutations, all caught; one redundant guard removed rather than
      shipped untested. `tst_sequence.qml` could NOT show it and says so:
      the fixture generator stamps the final at the same `ts` as the
      speech_end, so every replay has an instantaneous ASR — see A58.)

- [x] A58. Every committed recording had an INSTANTANEOUS ASR, and that is
      why A57 lived through five suites. — 746166e
      (`generate_sessions.asr_delay()` adds `ASR_LATENCY_S` = 2.2 s to a
      final transcript's `ts` — the figure measured on ares,
      PHASE1-STATUS.md's "ASR is ~2.2 s fixed", the same span `jv tap
      --latency` calls `hear`. A declared constant and not a measurement
      taken while generating: the recordings stay reproducible to the
      sample. Partials are deliberately NOT delayed — see A59. The three
      finals were restamped in place, one number per recording, because
      the loop's machine has no weights; the weights-gated staleness
      check is what proves a regeneration agrees. `tst_sessionreplay`
      now reads A57's anchor off a real recording and pairs the two real
      elements on one bus (498, was 495); `tst_sequence`'s three
      trajectories moved to the second the words arrive and its
      shortened window grew from 200 ms to 3 s, which a budget under the
      ASR could not be. The 10 shots came out byte-identical. Four
      mutations caught. Tests: `runtests.sh harness` 88 (was 78),
      `qmltest.sh` 498, `hudshots.sh` 15, `runtests.sh tools` 131.)

- [ ] A59. The recordings model the FINAL's ASR and not the partials',
      and the asymmetry is stated rather than resolved. Every partial
      also costs a `transcribe()` and also reaches the bus after it
      returns, so a live partial is late too — but nothing has measured
      by how much, and modelling it honestly means modelling the sample
      clock falling BEHIND the room and catching up, because the
      transcribe runs inline on the one thread that feeds wake and VAD
      (docs/optimization-backlog.md §6: a live mic backs its queue up and
      drops). That would move every other frame in these recordings
      instead of one, so it is a different and larger claim than A58 was.
      Two honest ways out: measure it on ares alongside the 2.2 s (a
      human at the machine, and it pairs with A28), or decide the
      partials are close enough to free to leave alone and say so in one
      place instead of two. What must NOT happen is a second invented
      constant. `test_a_provisional_sentence_is_stamped_while_the_
      utterance_is_still_open` is the guard that holds until then.
      Discovered in A58.

- [ ] A55. "What is the HUD showing right now" is answerable only by
      looking at the screen. `litNames` is the string a `jv hud` subcommand
      would print, and the B track has wanted a terminal view of the HUD's
      state since B15 asked which span the 2.5 s budget names — a `jv tap`
      that can say the corner went from `state heard mic` to `state mic` is
      a latency measurement of the LAST hop, not just of the bus. The
      obstacle is real and worth stating: the HUD is the only bus consumer
      that is a separate process with no way to be asked anything, so this
      is the same seam A47 wants for hudscreens and it should be decided
      ONCE, for both. Do not build it before A47 is answered. Discovered
      in A53.

- [ ] A47. The growth check proves a plate ARRIVED, never WHICH plate.
      `grows_from` (A44) and A42's live-lit window both measure the same
      thing: the drawn region got taller from the same top-right corner.
      A `HealthPlate` saying `jv-voice lost` would do that too, in the
      same direction, by a similar number of pixels — which is not
      hypothetical, since it is exactly what A42 hit when a heartbeat
      lapsed mid-window. Today the only thing that distinguishes them is
      the picture, read by a human, which is fine for a sheet whose whole
      purpose is to be looked at and not fine for a check that claims to
      prove the caption. No cheap answer: reading the words needs OCR or
      a QML-side probe, and both are new machinery in a harness whose
      value is that it stages nothing. Worth writing down so nobody reads
      more into the measurement than it says. Discovered in A44.
      A48 makes it three: `grew_downwards` is now asked by three idle
      windows and the shot loop, and all four of them prove only that
      SOMETHING arrived under the thing above it.
      A49 makes it four, and adds a mirror image: its shrink check proves
      something LEFT the screen and is equally unable to say what. The
      answer is the same for both, and so is the cost of getting one.
      **A53 closed the fifth instance and NARROWED this one** (754a49b):
      the QML-side probe exists now — `plateName` on every plate,
      `litNames` on the stack — and it answers completely inside
      `tools/hudshots`, where the scene is built by a QML test that can
      read a property. What remains is `tools/hudscreens` ONLY, and it is
      the harder half by construction: it photographs the real `.#jv-hud`
      binary under a real compositor with `grim`, so there is no QML engine
      to ask. Two honest options and neither is cheap — OCR (the captions
      are 11 px mono; tesseract is unreliable there), or an IPC seam in the
      SHIPPED shell that reports `litNames`, which stages something in
      production code for a test's benefit and this harness's whole value
      is that it stages nothing. **One human decision: OCR, an IPC seam, or
      leave those four checks saying exactly what they say.** Until then the
      four measurements are correct about growth and silent about identity,
      and `tools/hudscreens/shoot.py` says so.

- [x] A45. `docs/hud/screens/*.png` are not byte-reproducible, and the
      README now says so with numbers. — 3052b8f
      (Half of this was already true: that README has carried a
      "two runs are not byte-identical" paragraph since A30, which is
      why nobody noticed a journal entry leaning on the opposite. It now
      states what was measured over three runs of an untouched HUD —
      `01-quiet` (draws nothing) and `04-unheard` (two short monospace
      labels) identical every time, `02-heard` and `03-confirm` moving by
      2-5 px per monitor, one channel, one value, on glyph edges inside
      the plate — and a test pins the disclaimer so it cannot quietly
      leave. NOT made reproducible: the cause is below this harness, the
      shots that carry a long wrapped sentence are the only ones that
      drift, and a picture nobody byte-compares does not need to be a
      fixture. Done as part of A44, which rewrites the directory anyway.)

- [x] A46. `JARVIS_VOICE_OUTPUT_DEVICE` (A41) is honoured by the process
      and declared nowhere. — 61f26a4
      (`jarvis.voice.outputDevice`, a `types.nullOr types.str` defaulting
      to null, threaded into jv-voice's unit environment and NO other
      unit's. The repo's first NixOS option, so the module grew an
      `options`/`config` split to hold it. The empty string is refused by
      an assertion, because jv-voice reads an empty variable as "no
      device" and `outputDevice = ""` would be a configuration claiming a
      device is pinned while the service it configures reports none.
      Tests: `bash ops/ralph/nixtest.sh` — NEW machinery, 7 cases, each a
      `nix eval` of an `extendModules`-overridden ares asserting the
      GENERATED UNIT TEXT rather than the attrset, with four mutations run
      through it. The toplevel derivation path is identical to its
      parent's: a knob on ares, and not a byte of what ares would boot.
      Committed in iteration 43 and journalled in iteration 44 — the
      iteration that built it never wrote it down.) `modules/jarvis-services.nix` builds
      `systemd.user.services.jv-voice` with `environment = commonEnv`
      and no way to name a device, so pinning one today means editing a
      unit by hand — the imperative mutation the NixOS discipline
      forbids ("if it isn't declared, it doesn't exist"). The fix is one
      option (`jarvis.voice.outputDevice`, a `types.nullOr types.str`
      defaulting to null) threaded into that unit's `environment`, which
      also makes the HUD's new quiet-when-pinned path reachable on ares
      without touching a running system. Nothing is blocked on it — the
      default IS unpinned and that is the honest state of this machine —
      so it is small, tidy, and worth doing before anyone actually
      plugs in a dedicated speaker. Discovered in A41.

## Done
- A51 — the HUD says when this machine refused to run a program: jv-guard's
  verdict on a plate, the reasons deliberately left for the voice, and the
  one string in this HUD an attacker chose made safe to draw (ecc89c5,
  2026-09-24)
- A46 — the speaker Jarvis talks into becomes something the machine
  declares: `jarvis.voice.outputDevice`, the repo's first NixOS option, and
  `ops/ralph/nixtest.sh` to assert what options do to units (61f26a4,
  2026-09-24)
- A49 — the last plate in the stack gets watched standing still, and the
  turn gets an ending: a sixth measured window on the fifth's own broker
  and shell, the first check of a plate LEAVING, 0 commits, and a
  mutation the other five windows are blind to (4b62514, 2026-09-24)
- A48 — the two plates whose words come off a latch get watched standing
  still: a fifth idle window, a re-published frame re-taking a latch once
  a second, 0 commits, and a mutation the other four windows are blind to
  (9e322a1, 2026-09-24)
- A43 — the mic and health plates get watched standing still: a fourth
  idle window, two plates off one re-published heartbeat, 0 commits, and
  a mutation the other three windows are blind to (fed202f, 2026-09-24)
- B18 — `jv health --check` answers "is generation slow right now?": the
  brain's own gauge beside the rung, dated off its turn counter so a
  re-stated number can never pass as a current condition (4bd95fd,
  2026-09-24)
- A44/A45 — the screen sheet photographs the state where two plates
  disagree about whether Jarvis is working, and stops being mistaken for
  a fixture (3052b8f, 2026-09-24)
- A41 — the HUD stops assuming the sink it can see is the one Jarvis
  speaks into: jv-voice publishes `output_device_pinned`, OutputPlate
  goes quiet rather than confidently wrong (d504ba4, 2026-09-24)
- A42 — "0 fps when idle" stops being measured only on a HUD with no bus:
  a plate held lit on a LIVE bus, 0 commits under 6 snapshots, and a
  mutation the other two windows cannot see (4c63122, 2026-09-24)
- B16 — `think` stops being one number over the model and the queue: the
  model's share of it, stated by the only service that can see it
  (ceca526, 2026-09-24)
- A40 — the HUD stops saying SPEAKING while the room is silent
  (b643c22, 2026-09-24)
- A37 — the HUD says what Jarvis did to your machine when it did not work
  (7bc1eb5, 2026-09-24)
- A34 — the HUD renders nothing while nothing changes, counted off its own
  Wayland socket instead of argued from how Qt Quick works
  (d420e24, 2026-09-24)
- B14 — `respond` stops being one number over two services: split at the
  final transcript into `hear` (ASR) and `think` (the brain), and the
  broker's first heartbeat stops being a scheduling race
- B13 — `jv tap --latency` stops reporting one number: a turn split into
  spoke / hold / respond, and the gauge jv-ears had to publish for it
  (ee96c43, 2026-09-24)
- A32 — a click over the HUD reaches the window underneath, measured
  rather than read (48d9c74, 2026-09-24)
- A30 — the HUD on three monitors, and the four invariant-10 claims that
  stopped being verified by construction (d56b12e, 2026-09-24)
- A29 — the HUD, photographed: docs/hud contact sheet rendered from the
  real plates (fea019c, 2026-09-24)
- B11 — `jv health --check`: the machine can be asked whether it is well,
  and answers with its exit code (c8b2967, 2026-09-24)
- A26 — the HUD says what it heard: HeardState/HeardPlate, and the
  recordings that refused it a confidence bar (d7ac325, 2026-09-24)
- A24 — "which services are supposed to be running" written up as proposal
  R5 rather than built (2026-09-24)
- A1 — jv-hud Quickshell layer-shell skeleton (49046db, 2026-09-23)
- A2 — theme tokens in personality/theme.toml -> generated Theme singleton
  (6c0eafb, 2026-09-24)
- A5 — read-only bus link for QML: jv-hud-bridge + Bus.qml (bae8e03, 2026-09-24)
- B2 — jv CLI: bounded, scriptable streams + --latency (62c440f, 2026-09-24)
- A9 — headless QML tests + the core/ split that makes them possible
  (4c7c048, 2026-09-24)
- A7 — one motion switch: MotionPolicy/Motion/Ease, and a build gate that
  stops an element from animating around it (245926e, 2026-09-24)
- A3 — the first data-backed element: SpeechState + StatePlate, the HUD's
  first pixels that mean something (769dcdd, 2026-09-24)
- A4 — the recording light: CaptureMeter in jv-ears + MicState/MicPlate,
  and the counters that make it honest (6796579, 2026-09-24)
- B4 — `jv act-log`/`jv confirm` tested; a torn audit log now reads as torn
  (3a3e8ec, 2026-09-24)
- A6 — the sys.health glance: HealthState/HealthPlate, a corner that stays
  empty until something is actually wrong (7406009, 2026-09-24)
- A12 — "thinking": the HUD stops going dark while Jarvis is working
  (7eca614, 2026-09-24)
- A16 — jv-voice speaks turns, not sentences: one answer, one speaking/idle
  pair, and the half-duplex gate stays shut across it (8944abe, 2026-09-24)
- B3 — perception's real output becomes a fixture anyone can test on: four
  recorded sessions + one reader that can be asked `problems()` (d2f9634,
  2026-09-24)
- B9 — the HUD's tests stop typing their own frames: real sessions compiled
  into QML and replayed, trajectories asserted in real seconds (36a486d,
  2026-09-24)
- A15 — PlateStack: the surface asks the stack whether anything is on screen,
  so the list that could rot is gone (0dbe844, 2026-09-24)
- A10 — invariant 10 gets a witness: every HUD surface's safety properties
  pinned, and tools/tests finally run in CI (fe43c88, 2026-09-24)
- A14 — jv-ears states its own budgets and the HUD stops mirroring them
  (042438a, 2026-09-24)
- B6 — the brain stops generating when the user barges in, and the turn it
  lost is recorded as interrupted (4d05900, 2026-09-24)
- A17 — the question you gave up on stops reading "thinking" (b0c8262,
  2026-09-24)
- A8 — the faces theme.toml names finally exist on the machine, and the one
  that was silently a web font does not (5e5ef8d, 2026-09-24)
- B5 — `jv act-log` can be asked a question: --since/--failed/--outcome, and
  a filter that never hides what it could not evaluate (da134b9, 2026-09-24)
- A20 — the confirmation stops being only audible: ConfirmState/ConfirmPlate,
  jv-act's question on screen for exactly as long as it can be answered
  (6779708, 2026-09-24)
- A19 — the font module stops promising and starts proving: fc-match run
  against the system's own fontconfig config, every build (be1b264,
  2026-09-24)
