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
