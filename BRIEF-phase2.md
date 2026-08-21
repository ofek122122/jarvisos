# BRIEF — Phase 2: It acts

Goal: Jarvis stops being a chatbot. jv-context tells the brain what is
happening on the machine; jv-act gives it capability-gated hands; jv-compat
+ jv-guard make .exe files first-class and screened. Like Phase 1, nearly
all of this is buildable and CI-testable on Windows behind mocks; the exit
checklist waits for ares.

Standing constraints: CLAUDE.md invariants apply throughout. Invariant 3 is
the heart of this phase — read it twice before writing jv-act.

## Schemas first (additive — new topics, no changes to frozen v1 bodies)

- `context.window.json` — active window/workspace/app_id, monitor, title
  (title behind a redact flag — titles can contain secrets)
- `context.system.json` — battery/network/audio-sink/load snapshot (1 Hz)
- `intent.action.json` — brain → act: tool name, args, request_id,
  capability level, needs_confirmation
- `action.result.json` — act → brain: request_id, ok/error, output,
  duration_ms
- `action.confirm.json` — act → HUD/voice when confirmation required, and
  the user's answer back
- `compat.install.json` — install lifecycle events (fingerprinted, screened,
  prefix_created, installed, failed, blocked)
- `guard.verdict.json` — jv-guard screening result: clean | suspicious |
  blocked, reasons[], hashes

## 1. services/jv-context (Python)

Niri event-stream IPC → context.window at event rate; system snapshot →
context.system at 1 Hz. Abstract the compositor behind an interface (mock
for CI + a future custom-compositor backend, per blueprint Phase 5).
No polling loops where events exist.

## 2. services/jv-act (Rust — the privileged one)

- Tool registry: every tool declares name, args schema, capability level
  (observe | benign | destructive | privileged), timeout, and whether it
  needs confirmation. Registry is data (TOML), not code.
- v0 toolset: app launch (.desktop), window focus/move via compositor IPC,
  volume/media (wpctl/playerctl), file search (fd/rg wrappers, read-only),
  open path/URL, systemd unit status (observe only), speak-notification.
- NO uinput synthetic input in this phase (that arrives with hands, Phase 3
  of the roadmap) and NO shell-execution tool yet. Registry design must
  accommodate both later.
- Confirmation flow: destructive+ tools publish action.confirm and block
  that request (not the service) until answer or timeout→deny.
- Every action logged to an append-only audit file with request_id,
  timestamps, result. jv CLI gains `jv act-log` to read it.
- Full test suite against a mock bus + mock tool executors. Human review
  gate per invariant 3: build it, but the PR/commit series for jv-act is
  marked REVIEW-REQUIRED in PHASE2-STATUS.md and I read it before it ever
  runs on ares.

## 3. jv-brain v1: tool calling

Wire Qwen3-8B function calling to the registry (schemas → tool defs at
startup). Loop: transcript → tool calls → results → spoken summary.
Hard rules: max 5 tool calls per user turn; never invent tool names
(reject-and-say-so on hallucinated calls, log them); destructive intent
without confirmation = refuse politely. Stub-server tests for all paths
including the hallucination case.

## 4. services/jv-compat + services/jv-guard

- windows-compat.nix completed: binfmt_misc PE registration, wine-staging +
  umu/Proton-GE + bottles in the flake, MIME associations.
- jv-compat (Python): fingerprint (arch, installer framework, .NET/VC++
  deps) → recipe lookup (recipes/ TOML in-repo) → dedicated prefix under
  ~/.local/share/jarvis/prefixes/<app> → silent install where the framework
  allows → .desktop harvest + icon extract. bubblewrap confinement template
  per recipe: default deny-network, private home. Publishes compat.install.
- jv-guard (Python) v0: hash → local ClamAV scan → (config-gated, off by
  default until user enables) hash-only VirusTotal lookup → verdict on the
  bus. jv-compat refuses non-clean verdicts; user can override `suspicious`
  via confirmation flow, never `blocked`.
- CI: fingerprinting + recipe engine tested against a few real installer
  headers committed as fixtures (NSIS, Inno, MSI stubs — headers only, no
  payloads); guard logic tested with EICAR.

## 5. Greeting v0 (cheap now, the payoff is install day)

On user-session start: jv-brain publishes a greeting via speech.say —
time-of-day aware (good morning/afternoon/evening), uses last-shutdown gap
from a state file. One or two sentences, template + LLM phrasing, never a
dashboard. Personality-file-driven. This is the "good morning" moment the
whole project promised — make first boot feel like meeting someone.

## Exit checklist (on ares, after Phase 1's own checklist passes)

- [ ] "Jarvis, open Firefox" → it opens, focused, spoken confirmation
- [ ] "Turn it down a bit" → volume drops, context-aware
- [ ] "Close this" resolves via context.window to the active window
- [ ] A destructive tool asks first; silence = denied
- [ ] Double-click a real .exe installer → screened → prefix → desktop entry
- [ ] EICAR file → blocked, explained out loud
- [ ] `jv act-log` shows every action from the session
- [ ] I have read every line of jv-act and the registry TOML

Then request BRIEF-phase3 (hands + engagement gate + replay-driven tuning).
