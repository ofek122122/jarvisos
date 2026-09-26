# Bluetooth (PLAN G1) — the stack was never declared: no `hardware.bluetooth`,
# no pairing GUI, nothing. Two lines and a package fix that; there is no tray
# yet (H10 is still `[ ]`), so the "GUI path" G1 asks for is `blueman-manager`
# reached the same way every other installed app is on this desktop — the
# app launcher (Mod+D, modules/theme.nix) and the tap-Super menu
# (modules/super-menu.nix) both already list every .desktop entry on the
# system, and blueman ships one, so nothing here needs to bind a key or
# autostart anything.
{ pkgs, ... }:
{
  hardware.bluetooth = {
    enable = true;
    powerOnBoot = true;
    # Headsets/speakers want more than the profile BlueZ enables by default;
    # this is the standard fix (NixOS wiki, "Bluetooth" > audio) and PipeWire
    # (modules/audio.nix) already speaks A2DP through wireplumber once BlueZ
    # advertises it.
    settings.General.Enable = "Source,Sink,Media,Socket";
  };

  # services.blueman is the reviewed NixOS module for this: it starts the
  # blueman-mechanism system service (the polkit-gated privileged half of
  # pairing/trusting a device) and puts blueman-manager's .desktop entry on
  # the machine — no hand-written polkit rule, no imperative "just install
  # the package" (CLAUDE.md: undeclared doesn't exist).
  services.blueman.enable = true;
}
