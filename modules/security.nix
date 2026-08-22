# Phase 0 security groundwork (BRIEF-phase0 task 1):
# uinput access for the future jv-act, group-based camera/mic policy.
{ ... }:
{
  # Creates the `uinput` group and a udev rule granting it /dev/uinput.
  # Only jv-act (Phase 2+) and the interactive user belong to it —
  # CLAUDE.md invariant 3: only jv-act injects input.
  hardware.uinput.enable = true;

  # Camera/mic policy: raw device access is gated by the `video` and
  # `audio` groups. Phase 1+ gives each jv-* service its own user with
  # exactly the groups its sense requires — nothing more.
  users.groups.jarvis = { }; # umbrella group for jv-* state dirs (Phase 1)

  # No desktop automounter: nothing mounts the Windows NVMe or the 2 TB
  # disk by accident — both are permanently off-limits. Mounts are
  # declared in the flake or done by hand.
  services.udisks2.enable = false;
}
