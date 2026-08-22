# Decisions pending review

Same rules (Ofek): reasonable option + record here; hard stops (frozen
v1 schema CHANGES, Phase 0 boot config, irreversibles) get a BLOCKED
note and that piece is skipped. Approved entries migrate to
DECISIONS-approved.md.

_All Phase 1 and Phase 2 decisions have been reviewed and approved —
migrated to DECISIONS-approved.md. Nothing pending._

## Logged for a future schema bump (NOT a pending decision — needs the freeze process)

- **`audio.transcript` should gain a `listen_id` field** (nullable) at
  its next version bump, set by jv-ears when a frame is produced inside
  an open `dialog.listen` window. Then confirmation answers are tied to
  their window cryptographically (by id) instead of by envelope-ts
  window-membership, which is jv-act's v1 correlation defense. This is a
  frozen-v1 body change → its own reviewed schema commit + codegen
  regen; deferred, not done here.
