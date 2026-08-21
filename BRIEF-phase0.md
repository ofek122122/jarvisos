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
2. **Storage layout.** LUKS2 on the WD Green root; the 2 TB disk mounted at
   `/tank` (models, episodic store lives here later). ext4 or btrfs, your
   call, justified in the commit message.
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

- [ ] Machine boots JarvisOS from firmware menu; Windows boots untouched.
- [ ] `jarvis-doctor` all PASS.
- [ ] `nixos-rebuild switch --flake .#ares` from a clean clone reproduces it.
- [ ] Rollback demonstrated once: previous generation booted deliberately.
- [ ] User has run the runbook themselves, not just watched.

Then request BRIEF-phase1 (the bus + the voice loop).
