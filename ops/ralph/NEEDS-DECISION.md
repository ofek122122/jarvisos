# Needs a decision from Ofek

The loop appends here when an item requires a judgement it must not make alone
— usually because it touches an invariant, the login path, or how the system is
structured. Items here are marked `[B]` in PLAN.md and are NOT attempted.

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

