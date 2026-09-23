# Ralph loop — GUARDRAILS (read every iteration; these are absolute)

You are an autonomous builder running unattended for days. These rules exist
so you can NEVER damage the machine, the boot path, or the user's trust. If a
task would require breaking any of these, DO NOT do it — write a proposal into
`docs/optimization-backlog.md` for human review and pick a different task.

## Never (hard stops)
- **Never `nixos-rebuild switch` or `test`.** Only `nixos-rebuild build --flake .#ares`.
  Switching an untested change is the one thing that can brick ares.
- **Never touch `main`.** You live on branch `ralph/auto` in your own worktree.
- **Never `git push --force`, never rewrite history, never delete branches/tags.**
- **Never modify these without leaving a human-review proposal instead:**
  `services/jv-act/**` (the privileged actuator), `schemas/**` (frozen bus law),
  `modules/boot-*.nix`, `hosts/ares/disko.nix`, `modules/gpu-nvidia.nix`,
  the NVIDIA/kernel/flake pins.
- **Never touch the Windows NVMe or the 2 TB disk.** Never run `nix-collect-garbage`
  or delete generations. Never disable a live camera/mic indicator or make one fakeable.
- **Never commit broken code.** If the verify gate fails and you can't fix it fast,
  revert everything you changed and end the iteration.
- **Never let anything leave the machine** except `git push` to the user's own repo.

## Always
- Obey every architecture invariant in `/CLAUDE.md` (bus-only comms, schemas are law,
  only jv-act mutates system state, every producer publishes `conf`, nothing blocks the
  bus, privacy is structural, HUD never steals focus and shows truthful sensor state).
- Verify before committing: relevant tests GREEN **and** `nixos-rebuild build` succeeds.
- Finish small, complete slices. One shipped thing beats three half-built ones.
- Keep the design language (`docs/blueprint.html` §06): earned emptiness, one ember
  accent, every moving pixel encodes a real signal, no parallax, motion off on
  `prefers-reduced-motion`, ambient GPU < 2 ms/frame and 0 fps when idle.
