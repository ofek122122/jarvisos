# schemas/ — the bus contract

**Schemas are law (CLAUDE.md invariant 2).** Every message on the bus is an
[`envelope.json`](envelope.json) frame whose `body` conforms to the schema of
its topic at version `v`. Services are written against these files, never
against each other.

## Status: FROZEN v1 — approved by Ofek, 2026-08-21

Freeze rules:

- **Freeze protects existing bodies.** Any change to an existing schema is
  its own reviewed commit with a `v` bump in the schema's `$id` (filename
  stays stable); codegen (Rust + Python bindings, checked into the repo)
  must be regenerated in the same commit — CI fails on drift.
- **Adding a NEW topic is an ordinary reviewed commit, not a freeze
  violation.** New phases add topics; they never silently change frozen
  ones.

## Topics

| Topic | Schema | Publisher → Consumer | Envelope `conf` means |
|---|---|---|---|
| (envelope) | `envelope.json` | everyone | — |
| `audio.wake` | `audio.wake.json` | jv-ears → brain, voice, HUD | wake score |
| `audio.vad` | `audio.vad.json` | jv-ears → anyone | VAD confidence |
| `audio.transcript` | `audio.transcript.json` | jv-ears → jv-brain | ASR confidence |
| `speech.say` | `speech.say.json` | jv-brain → jv-voice | 1.0 (command) |
| `speech.state` | `speech.state.json` | jv-voice → anyone | 1.0 (state) |
| `brain.request` | `brain.request.json` | CLI/replay/HUD → jv-brain | 1.0 (command) |
| `brain.response` | `brain.response.json` | jv-brain → requester, jv-voice | 1.0 in v0 |
| `sys.health` | `sys.health.json` | every service | 1.0 (state) |

## Conventions (part of the contract)

- **`ts` is CLOCK_MONOTONIC seconds**, not wall-clock — chosen so
  `jv tap --latency` can compute true per-hop latency across processes.
  Archival wall-time stamping is the archiver's job (jv-memory, Phase 4+).
- **Two ID kinds thread a voice interaction.** An INPUT `utterance_id`
  (UUID, the user speaking) is minted at VAD `speech_start` and flows
  through `audio.transcript` into `brain.response.utterance_id`. An OUTPUT
  `say_id` (UUID, Jarvis speaking) is minted by whoever publishes
  `speech.say`, which also carries a required nullable
  `in_reply_to_utterance` = the originating input utterance_id (null when
  nothing triggered it, e.g. a system announcement). End-to-end latency =
  VAD `utterance_id` → matching `in_reply_to_utterance`. Input and output
  utterances are different things; jv-memory (Phase 4) relies on the split.
- **`seq` gaps are meaningful**: jarvisd's slow-consumer policy drops oldest
  frames per subscriber rather than ever blocking a publisher (invariant 5);
  a subscriber seeing a gap knows it was dropped-on, and jarvisd reports
  drop counts on `sys.health`.
- **Subscriptions** are exact topics, a prefix ending in `.*`
  (e.g. `audio.*`), or the lone `*` (everything — debug tooling like
  `jv tap`). Wildcards never appear in published topics.
- **Harness session header** (`ts` is monotonic and resets on reboot, so a
  recorded session must anchor itself): `harness/record.py` writes, once
  per session file before any frames,
  `{"boot_id": "<from /proc/sys/kernel/random/boot_id>", "wall_time_utc":
  "<ISO 8601>", "monotonic_now": <CLOCK_MONOTONIC seconds at header write>}`.
  Wall time of any frame = `wall_time_utc + (frame.ts - monotonic_now)`,
  valid because boot_id proves the same boot. Replay preserves original
  relative timing from `ts` deltas.
- **Bodies are closed** (`additionalProperties: false`) except the
  explicitly free-form `sys.health.metrics`. New fields require a version
  bump — that's the point.
