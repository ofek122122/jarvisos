# Decisions — APPROVED log

**All Phase 1 autonomous decisions below reviewed by Ofek (with advisor)
2026-08-22: ALL APPROVED, nothing overruled.** New in-flight decisions go
to DECISIONS-pending.md; approved ones migrate here.

Rules in effect (Ofek, 2026-08-21): take the reasonable option, record it,
keep going. Hard stops (frozen schemas / Phase 0 boot config / hard to
reverse) get a BLOCKED proposal instead.

## Pre-approved in the departure Q&A (not pending — recorded for context)

- ASR: **faster-whisper** (CT2 int8, distil-small.en) — brief said
  whisper.cpp; deviation approved.
- Units: **hybrid** — jarvisd + jv-brain system; jv-ears + jv-voice user
  session (PipeWire); bus stays at /run/jarvis/bus.sock.
- Models: **fetch.sh + SHA256** to /var/lib/jarvis/models (until /tank).
- Wake UX v0: **wake word every time**, no follow-up window.
- Self-decided defaults announced before departure: continuous VAD,
  wake-gated transcription, 8s wake timeout, ~0.5s partials; sounddevice
  I/O; offline-DSP voice chain w/ intensity knob (default 0.4);
  brain = OpenAI client to llama-server, stub server in CI, ~16-turn
  rolling context, 10-min idle reset, Qwen3 thinking off; JSONL sessions;
  TTS-generated fixtures; CI model caching.

## Taken while out

(chronological; format: what came up → chosen → why → alternative)

- **Dev model cache location** → `./models-cache/` (gitignored), overridden
  by `JARVIS_MODELS_DIR`; production default stays /var/lib/jarvis/models.
  Why: keeps 300+ MB of weights out of the repo and the same fetch.sh
  works on Windows dev, CI, and ares. Alt: commit small models into the
  repo (rejected: repo bloat, no git-lfs).
- **Python packaging** → one `pyproject.toml` per service + shared
  `services/pylib` (jarvis-bus package), pytest, editable installs in a
  repo-local `.venv` (gitignored). Alt: monolithic requirements.txt
  (rejected: services must stay independent — invariant 1 in spirit).
- **Fixture WAVs committed to the repo** (4 files, ~1 MB total, 16 kHz
  mono) plus the deterministic generator script. Why: CI must not depend
  on TTS to test ears; the WAVs ARE the contract. Alt: generate in CI
  (rejected: nondeterministic piper versioning would move the test target).
- **Wake phrase stays in the transcript** ("Hey Jarvis, what time is
  it?"). Ears publishes what was said; stripping the address is jv-brain's
  job (it gets the system prompt context to handle it). Alt: strip in ears
  (rejected: ears would need language knowledge it shouldn't have).
- **Retroactive wake gating**: the wake phrase sits inside the VAD
  utterance (VAD confirms at ~200 ms, wake needs ~1 s), so a wake fired
  mid-speech gates the already-running utterance and keeps its pre-roll
  audio. Alt: only gate speech that starts after wake (rejected: would
  drop every normal "hey jarvis, <command>" said as one breath — i.e.
  the main use case).
- **Q4_K_S rung source**: Qwen's official GGUF repo ships no Q4_K_S, so
  ladder rung 3 pins bartowski/Qwen_Qwen3-8B-GGUF (hash-pinned like all
  models). Alt: skip rung 3 (rejected: your ladder spec named it).
- **Octave-up shimmer via full-wave rectification** (|x| doubles the
  fundamental, band-passed 900–5000 Hz) instead of a phase-vocoder pitch
  shifter. Why: zero extra deps, deterministic, plenty subtle at the
  -20 dB-ish levels the blueprint calls for. Alt: librosa pitch_shift
  (rejected: heavy dependency for one effect; revisit if your ears
  disagree with the samples).
- **Ring modulator (55 Hz) fades in only above intensity 0.5** — so your
  0.2/0.4 candidates are "processed natural" and 0.7 is overtly synthetic;
  a `dry.wav` reference sample was added alongside the three requested.
- **Preempted speech is dropped, not resumed** (v0). Why: resuming
  mid-sentence sounds broken; the brain can re-say if it matters. Alt:
  requeue the interrupted utterance (rejected for v0 complexity).
- **VRAM guard lives in `jv-llm-launch`**, the ExecStart of the
  llama-server unit — it probes free VRAM at launch, picks the rung,
  writes /run/jarvis/llm-rung, and execs llama-server. jv-brain reads
  the rung file and surfaces it as sys.health metrics (llm_rung,
  llm_gpu) and brain.response.backend. Why: the guard must run where
  the loading happens; the brain shouldn't manage a sibling unit's
  process. Alt: brain spawns llama-server itself (rejected: brief says
  own systemd unit; a brain crash shouldn't kill the model server).
- **KV-cache budget from Qwen3-8B geometry** (36 layers x 8 KV heads x
  128 dim -> ~147 KB/token f16), pinned by a unit test. Compute
  overhead 400 MB + safety margin 300 MB. On the real card the numbers
  get verified at exit-checklist time; constants live in config.py.
- **personality/system.md v0 drafted** (spoken-style, English replies,
  disagree-with-reason, no-tools honesty, the §05 "point outward" mental
  -health line). Marked DRAFT — your review pass is expected.
- **Wake-prefix stripping in jv-brain** via regex ("hey/ok jarvis," at
  utterance start only); an utterance that is ONLY the wake word is
  passed through unchanged so the brain can respond to being called.

---

## Phase 2 overnight — APPROVED by Ofek + advisor 2026-08-22

All decisions from the Phase 2 stretch reviewed and approved, including
the binfmt fixBinary correction and suspicious=refuse-in-v0. jv-act read
line by line; architecture approved; four fixes required and applied
(see PHASE2-STATUS.md REVIEW-PASSED). Full list migrated below.

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
- **binfmt fixBinary=false** (blueprint §08 example showed true). nixpkgs
  asserts fixBinary is invalid when the interpreter is a shell wrapper,
  which wine's launcher is; flake eval caught it. Functionally fine —
  fixBinary only pre-resolves the interpreter at registration; without
  it the lookup happens at exec, which is what we want across rebuilds
  anyway. This corrects a blueprint example, touches no Phase 0 config.
