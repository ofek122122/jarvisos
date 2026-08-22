# Decisions taken while Ofek is out — Phase 2 overnight stretch

Same rules (Ofek, 2026-08-22): reasonable option + record here; hard
stops (frozen v1 schema CHANGES, Phase 0 boot config, irreversibles) get
a BLOCKED note and that piece is skipped. Additive schemas are expected
and fine per BRIEF-phase2. Approved entries migrate to
DECISIONS-approved.md.

## Pre-approved in the bedtime Q&A (2026-08-22)

- **Capability mapping v0**: observe = file-search, unit-status; benign =
  launch, focus/move, close-window, volume/media, open path/URL, speak.
  Close is benign (apps guard their own unsaved state). No destructive
  tools in v0 — the confirm flow ships fully tested and waits for
  Phase 3+ tools.
- **Confirm answers**: scoped 10s NO-WAKE listening window opened by
  ears when action.confirm fires; yes/no-class answers only; anything
  else or silence = deny. `jv confirm <id> yes|no` also works. This is
  a deliberate, bounded exception to wake-every-time.
- **Guard posture**: FAIL CLOSED — no verdict, no prefix, said plainly.
- **context.window titles**: published, with the redaction blocklist
  PRE-SEEDED (Ofek: "empty-by-default means I get burned once first"):
  password managers (keepass*, bitwarden*, 1password*), private/incognito
  surfaces where the compositor exposes them, any app_id containing
  "private".
- Self-decided defaults announced before sleep: 15s confirm timeout →
  deny; action.confirm one topic (kind=request|answer, answered_by=
  voice|cli|timeout); registry TOML deployed to /etc/jarvis/tools.toml
  read by act (authoritative) + brain (tool defs) — config distribution,
  not IPC; no persistent grants in v0; audit at
  /var/lib/jarvis/act/audit.jsonl + `jv act-log`; greeting via oneshot
  user unit -> brain.request(source=system), shutdown stamp from a
  system unit; EICAR base64-materialized at test time, skipped on
  Windows, ClamAV mocked in CI (real scan TODO(machine)); bwrap
  arg-construction tested, spawn TODO(machine); installer fixtures =
  committed header bytes only.

## Taken while out

(chronological; format: what came up → chosen → why → alternative)

- **Scoped no-wake windows generalized into `dialog.listen`** (new
  additive topic) rather than a confirm-only mechanism inside ears.
  Ears opens the window and publishes transcripts normally; the
  REQUESTER (act for confirms, brain for onboarding/follow-ups)
  interprets them — ears never learns what "yes" means. Capped 60s,
  reason field audited. Why: your onboarding addition needs the same
  mechanism ("one question at a time", no wake per answer); one dumb
  primitive beats two smart ones. Alt: ears classifies yes/no itself
  (rejected: puts intent interpretation in a perception service).
- **User profile file**: JSON at $JARVIS_STATE_DIR/brain/profile.json
  (default /var/lib/jarvis/brain/, repo-local .state/ on dev, both
  gitignored). Structure mirrors the blueprint semantic tier: facts
  keyed by id with {value, kind, confidence, first_seen,
  last_confirmed, source}, plus pending_questions[] and
  onboarding_complete. Why: requirement 1 says schema-shaped seed for
  the Phase 4 store. It is user DATA — never in personality/, never
  committed.
- **`jv onboard --reset`**: deletes the profile file directly (state
  dir is group-jarvis writable, 0770) after an interactive y/N prompt.
  Alt: a bus round-trip to brain (rejected: reset must work when brain
  is stopped or broken).
- **Name capture**: rule-based extraction first ("call me X", "my name
  is X", "I'm X", bare name), LLM extraction as fallback; pronunciation
  confirmed by SAYING the name back through jv-voice and taking yes/no
  in the same dialog.listen window; a correction at any later time
  ("it's pronounced...", "actually call me...") updates the fact and
  bumps last_confirmed — corrections are just facts.
- **Follow-up trickle heuristic (v0)**: at most ONE pending question
  per session, asked only after the session's first completed exchange
  (never at greeting, never first boot), skipped entirely if the
  previous session asked one. Real §05 pause detection arrives with
  presence (Phase 4). Alt: timer-based (rejected: that's the survey
  antipattern §05 warns about).
- **system.md de-personalized** to template + injected "About your
  user" section assembled from the profile at prompt time; when no
  profile exists the section says it hasn't met its user yet, which is
  what makes the onboarding self-introduction in-character.

- **jv-compat is on-demand CLI in v0** (`jv-compat install <path>`), not
  a watch-folder daemon. Why: the brief's exit item is "double-click a
  .exe" which binfmt+MIME route to jv-compat; a persistent folder
  watcher is scope the brief doesn't ask for. Alt: inotify daemon
  (deferred).
- **suspicious verdict = refuse in v0** (with a spoken explanation of
  how it *would* be overridden). The confirmation-flow override the
  brief allows needs the HUD confirm surface (Phase 5) or at least the
  voice confirm path wired into compat; rather than half-wire it,
  compat refuses suspicious cleanly and says so. `blocked` is never
  overridable regardless. Alt: wire compat->act confirm now (rejected:
  couples two services ahead of the HUD; noted for review).
- **sha256 helper duplicated** in jv-compat rather than imported from
  jv-guard — services never import each other (invariant 1).
