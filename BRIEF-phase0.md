# BRIEF — Phase 0: Ground

Goal: a bootable, declared JarvisOS on the 1 TB WD Green SSD, dual-booting
cleanly beside the untouched Windows NVMe, with GPU + cameras verified.
Everything is code in this repo. Nothing else in Phases 1+ starts until the
exit checklist passes.

## Pre-flight (with the user, before any install)

1. Confirm drive identities from Windows first: which disk is the Windows
   NVMe (Crucial P2 500 GB), which is the WD Green 1 TB target, which is the
   2 TB data disk. Record serials in `docs/drives.md`. Triple-check — the
   install wipes the target drive.
2. Have the user: back up anything on the WD Green, disable Fast Startup in
   Windows, disable Secure Boot in the Gigabyte UEFI (or plan for lanzaboote
   later), and prepare a NixOS minimal USB.

## Tasks

1. **Flake skeleton.** `flake.nix` + `hosts/ares/` (hardware.nix generated
   then audited; default.nix) + `modules/` split: `gpu-nvidia.nix` (pinned
   driver, open modules, CUDA), `desktop.nix` (Hyprland or Niri — pick Niri
   if in doubt, greetd + tuigreet), `audio.nix` (PipeWire), `security.nix`
   (uinput group/udev rules, camera/mic group policy), `windows-compat.nix`
   (stub for Phase 2). Bootloader: systemd-boot on the WD Green's OWN ESP.
   Do not register Windows in it — firmware menu handles OS choice.
   > SUPERSEDED (2026-08-22): bootloader is **GRUB** (an at-every-boot
   > JarvisOS + Windows OS chooser), not systemd-boot. See
   > `modules/boot-grub.nix` and `docs/drives.md`.
2. **Storage layout.** LUKS2 on the WD Green root; btrfs+zstd.
   > SUPERSEDED (2026-08-23): there is **no `/tank`**. The 2 TB disk is
   > permanently off-limits (Windows boots from its ESP); models, the
   > episodic store, and all state live on the WD Green root. See CLAUDE.md
   > (hard rule) and `docs/drives.md`.
3. **Verification module.** A `jarvis-doctor` script (packaged in the flake)
   that checks and prints PASS/FAIL for: `nvidia-smi` sees the 1660 SUPER;
   CUDA runs a trivial kernel; `v4l2-ctl --list-devices` shows the Lenovo
   510's RGB *and* IR nodes and can capture a frame from each; PipeWire sees
   the mic; all three monitors at correct resolution+refresh under Wayland;
   Windows NVMe is NOT mounted and NOT in the bootloader.
4. **Kernel (second pass, only after first boot works).** Custom kernel via
   `boot.kernelPatches`/structured config: seed from localmodconfig on the
   running system, PREEMPT full, HZ=1000, uvcvideo + uinput built in. Keep
   the stock kernel generation available as fallback.
5. **Repo hygiene.** README with the boot/rollback runbook. `docs/` holds the
   blueprint. CI (even just a GitHub action or local script) that runs
   `nix flake check` on every commit.

## Exit checklist

- [x] Machine boots JarvisOS from firmware menu; Windows boots untouched.
      (2026-08-27: dual boot verified — GRUB chooser boots both; Windows
      NVMe untouched. 2026-09-15: themed GRUB + Plymouth verified too.)
- [x] `jarvis-doctor` all PASS. (2026-08-27, run as ofek in a real session.)
- [x] Clean-clone reproducibility. (2026-09-15: fresh `git clone` of
      8f1e68b from GitHub, `nix build ...toplevel` produced
      `llkyj9mh76l9kyjfd4nc8rngv7g4464p` — byte-identical to the store
      path the machine was running at that moment.)
- [x] Rollback demonstrated once. (2026-09-15, Runbook D: htop added as
      generation 8; user deliberately booted generation 7 from the GRUB
      submenu — htop absent; rebooted default — htop present.)
- [x] User has run the runbook themselves. (2026-08-27: pulled and
      applied the GRUB Windows-entry rebuild by hand; 2026-09-15: drove
      both rollback-drill reboots and generation selection at the GRUB
      menu.)

**PHASE 0 EXIT: COMPLETE (2026-09-15).**

Then request BRIEF-phase1 (the bus + the voice loop).
