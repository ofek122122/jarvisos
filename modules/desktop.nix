# Rented desktop for Phases 0-4: Niri (scrollable tiling, clean IPC that
# Jarvis will drive) + greetd/tuigreet. Wayland only — no X11 server exists
# on this system; legacy apps get XWayland via xwayland-satellite.
{ lib, pkgs, ... }:
{
  programs.niri.enable = true;

  services.greetd = {
    enable = true;
    settings.default_session = {
      command = "${lib.getExe pkgs.tuigreet} --time --remember --cmd niri-session";
      user = "greeter";
    };
  };

  environment.systemPackages = with pkgs; [
    alacritty # terminal
    fuzzel # launcher (until jv-brain replaces it — blueprint Phase 2)
    wl-clipboard
    xwayland-satellite # rootless XWayland for the stray legacy client
    brightnessctl
  ];

  environment.variables = {
    NIXOS_OZONE_WL = "1"; # Chromium/Electron on Wayland
  };

  # Monitor layout (1440p144 primary + 2x 1080p60) is per-user Niri config,
  # written on install day once connector names are known; jarvis-doctor
  # verifies all three modes are actually achieved.
}
