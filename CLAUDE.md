# JarvisOS — CLAUDE.md

You are building JarvisOS: a NixOS-based custom operating system whose desktop
assistant ("Jarvis") perceives through camera, microphone and system context,
remembers its user long-term, and acts on the machine. The full design is in
`docs/blueprint.html` — read it before any non-trivial task. This file states
the invariants that must never be violated, in any task, ever.

## The machine

- Intel i5 (Comet Lake, 6c/12t) · 32 GB DDR4 · GTX 1660 SUPER **6 GB VRAM**
- Drives: 500 GB NVMe (**Windows — never touch**), 1 TB WD Green SATA SSD
  (JarvisOS root), 2 TB disk (models + episodic store)
- Monitors: 2560x1440@144 (primary) + 2x 1920x1080@60 — Wayland only, never X11-first
- Sensors: Lenovo 510 FHD webcam (has an IR stream — use it), Ultraleap Leap
  Motion Controller 2 (desk-mounted, faces up), far-field mic array
- Dual boot via UEFI firmware menu. NEVER write to the Windows drive or its
  EFI partition. The Windows disk is out of scope for every command you run.

## Architecture invariants

1. **Every sense is its own process.** Services communicate ONLY via the bus
   (`jarvisd`, Unix socket `/run/jarvis/bus.sock`, MessagePack frames).
   No shared memory, no direct imports between services, no exceptions.
2. **Schemas are law.** All bus message types live in `schemas/` and are
   frozen before the services that use them are written. A service that needs
   a schema change proposes the change as its own reviewed commit first.
3. **Only `jv-act` mutates system state.** No other service writes files
   outside its own state dir, injects input, or spawns processes that do.
   Every `jv-act` tool declares a capability level; destructive tools require
   explicit user confirmation. All `jv-act` code is human-reviewed.
4. **Every producer publishes confidence.** Every frame carries `ts`, `seq`,
   `src`, `conf`. Consumers must handle missing/late/low-confidence input.
5. **Nothing blocks the bus.** Slow work happens off the hot path.
   Latency budget: gesture-to-effect < 100 ms end to end. Measure, don't assume.
6. **6 GB VRAM is a scheduling problem.** Daytime: 8B Q4 brain resident,
   vision < 1 GB, Whisper on CPU. Game launch → brain unloads. Night →
   `jv-dream` runs the big CPU model. Never assume free VRAM.
7. **Privacy is structural.** All models local. Episodic store encrypted at
   rest with its own key. "Forget that" performs real deletion across
   episodic, semantic and narrative tiers and reports what it removed.
   No frame or audio ever leaves the machine; `jv-guard` may send FILE HASHES
   only to reputation services.
8. **Windows binaries are untrusted by default.** One Wine prefix per app,
   bubblewrap-confined, no network or home access unless the recipe grants
   it. `jv-guard` screens every binary before `jv-compat` builds a prefix.
9. **Personality is versioned.** System prompt, voice chain, theme tokens and
   behaviour rules live in `personality/`. `jv-dream` may PROPOSE diffs to
   it; a human applies them. The proactivity budget (max unprompted
   utterances/day, self-adjusting per category) is enforced in `jv-brain`.
10. **The HUD never steals focus** and always truthfully shows sensor state
    (camera/mic live indicators are not optional and not fakeable). The
    workspace layer never parallaxes; ambient GPU cost < 2 ms/frame, 0 fps
    when idle, off on `prefers-reduced-motion`.

## NixOS discipline

- The entire OS is one flake in this repo. No imperative installs, no
  mutations outside the flake. If it isn't declared, it doesn't exist.
- Change flow: `nixos-rebuild build` → review the diff → `nixos-rebuild test`
  → only then `switch`. NEVER `switch` an untested kernel/boot change.
  Never garbage-collect old generations during active development.
- Pin the NVIDIA driver version explicitly. Change it deliberately, alone,
  in its own commit.

## Working style

- One service = one task = one session. Finish with tests + a systemd unit.
- The replay harness (`harness/`) is built in Phase 3 and used forever:
  recorded sensor sessions are the test fixtures for all perception work.
- Locked decisions: name = "Jarvis" (openWakeWord pretrained `hey_jarvis`),
  English voice in/out (Whisper may receive Hebrew; replies in English),
  runner stack = wine-staging + Proton-GE via umu, UI = Quickshell (QML) +
  wgpu overlay until Phase 5, brain = llama.cpp server, 8B-class Q4.
