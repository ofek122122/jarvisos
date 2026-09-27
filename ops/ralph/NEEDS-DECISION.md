# Needs a decision from Ofek

The loop appends here when an item requires a judgement it must not make alone
— usually because it touches an invariant, the login path, or how the system is
structured. Items here are marked `[B]` in PLAN.md and are NOT attempted.

## G9 — Narrowed automount: re-enable udisks2, which security.nix disables on purpose?

**The decision:** plugging in a USB stick and having it just appear requires
udisks2, which `modules/security.nix` disables **deliberately** — it is the
mechanism that would otherwise automount the Windows NVMe and the 2 TB disk,
both of which are permanently off-limits. gvfs force-enables it, which is why
`modules/apps.nix` ships without gvfs today.

**What it needs from you:** explicit sign-off to turn udisks2 back on, narrowed
to removable USB only with both forbidden disks hard-excluded by serial
(`WD20EZAZ`/`WD-WXL2A90L3KAP` and the Crucial `CT500P2SSD8`). This is the one
item in the backlog that touches the disk rule directly, so the loop will not
attempt it on any reading of "probably fine" — it asks or it skips.

**If you say no:** everything else still works; you mount USB sticks by hand.

## G10 — home-manager: adopt it for declarative dotfiles?

**The decision:** whether to restructure where user config lives. It would make
things like `~/.config/niri/config.kdl` declarative in the flake rather than
hand-edited — the exact problem F1 just solved a different way, by generating
`/etc/niri/config.kdl` and having you move your user file aside.

**What it needs from you:** a yes/no on adopting home-manager at all. It is a
structural change to the repo's shape, not a feature, and F1's approach means
it is no longer *needed* for the one violation that motivated it.

## H14 — Graphical login greeter: when do we switch the greetd session command?

**The decision:** a §06-themed regreet login screen is buildable and testable
headless, but **switching the greetd session command is the one change that can
lock you out of your own machine** if it is wrong. GUARDRAILS forbids the loop
from switching it, full stop.

**What it needs from you:** a human-supervised switch, with a TTY escape open
and a known-good generation to roll back to. The loop will build it, prove it in
a nested/headless test, and park it — it will not flip the session command even
if every test is green.

## F4 — Game-launch VRAM handoff: who is allowed to stop `jv-llm.service`?

**The decision:** the blueprint's "game launch → brain unloads" needs two things
this loop must not create alone — a new frozen topic in `schemas/` for the "game
running" fact, and *privilege for an unprivileged per-user gamemode hook to stop
and restart the SYSTEM `jv-llm.service`*, which runs as its own system user.
That second half is exactly the boundary invariant 3 keeps inside `jv-act`.

The loop checked both shapes and found the "clean" one is not cleaner, only
differently placed — gamemode's own `[custom]` `start=`/`end=` hook needs no bus
round-trip and no schema, but still needs a polkit rule (or a sudo/setuid grant)
letting your session control another system user's unit. Full write-up: **R10**
in `docs/optimization-backlog.md`.

**What it needs from you:** pick the shape — (a) bus-side `sys.game` topic plus a
small privileged consumer, which also feeds I4's VRAM bar, or (b) gamemode
`[custom]` hook plus a narrow polkit rule — and review the privilege grant
either way. Nothing in `jv-brain`/`jv-llm-launch` has to change once the trigger
and the privilege exist; they already report whatever rung a starved launch
lands on.

## F5 — Dictation anywhere: the `jv-act` input-injection tool does not exist

**The decision:** "hold a key → speak → text is typed into the focused window"
needs a new `jv-act` tool (`input.type_text`). Invariant 3 is explicit that only
`jv-act` injects input, no injector of any kind exists in `services/jv-act`
today, and all `jv-act` code is human-reviewed. Write-up: **R11** in
`docs/optimization-backlog.md`.

**What it needs from you:** review and accept a new `jv-act` tool definition,
including its capability level and whether typing into the focused window needs
confirmation (it can type into anything — a terminal, a password field).

**Not blocking the rest:** the other three quarters are split out as **F5b** and
are being built behind a *fake* injector, so adopting the real tool later is a
one-call change.

## H2b — "Boot Windows" in the power menu: which mechanism, and do you have the NVRAM entry it needs?

**The decision:** the power menu itself (lock/suspend/reboot/shut down) shipped
this iteration with no "Boot Windows" fifth option, because that one option
needs either `modules/boot-grub.nix` changed (turning on `default = "saved"`,
which this file currently refuses on purpose — "a predictable default beats
convenience") or a brand-new privilege letting the desktop session write an
`efibootmgr` firmware NVRAM variable. Both are exactly the two classes of
change GUARDRAILS reserves for a human: `modules/boot-*.nix` by name, and a new
privileged grant with no confirmation step by consequence. Write-up: **R12** in
`docs/optimization-backlog.md`.

**What it needs from you:** run `efibootmgr -v` on ares and say whether a
native "Windows Boot Manager" NVRAM entry already exists (this decides which of
the two shapes R12 lays out is even possible), then pick a shape and review
the boot-config change or the privilege grant it needs.

**Not blocking the rest:** PLAN H2's four other entries (Lock, Suspend, Reboot,
Shut Down) are built, tested and require neither change — adding a fifth once
this is reviewed is a one-line addition to `pkgs/jv-power-menu`'s existing
`case` statement.

