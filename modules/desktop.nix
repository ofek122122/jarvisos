# Rented desktop for Phases 0-4: Niri (scrollable tiling, clean IPC that
# Jarvis will drive) + greetd/tuigreet. Wayland only — no X11 server exists
# on this system; legacy apps get XWayland via xwayland-satellite.
{ lib, pkgs, ... }:
{
  programs.niri.enable = true;

  # nix-ld: run prebuilt (non-Nix) dynamic binaries on NixOS by providing the
  # loader + a common library set. This is what lets Claude Code's OWN native
  # auto-update work: the store-built claude-code below can't rewrite itself
  # (/nix/store is read-only), so the official installer drops a writable,
  # self-updating claude into ~/.local/bin, and nix-ld makes that binary run.
  programs.nix-ld.enable = true;

  # Put ~/.local/bin on PATH (ahead of the system profile), so the
  # self-updating claude there shadows the pinned store one, which stays as a
  # fallback in environment.systemPackages.
  environment.localBinInPath = true;

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
    firefox # native Wayland; jv-guard never sees it — it is not a Windows binary
    vim
    claude-code # replaces the interim `nix profile install` — declared, like everything
    git # was riding along inside the old imperative claude wrapper — now explicit
    gh # GitHub CLI: push auth via `gh auth setup-git`
    htop # the Runbook D rollback-drill marker (and genuinely useful)
  ];

  environment.variables = {
    NIXOS_OZONE_WL = "1"; # Chromium/Electron on Wayland
  };

  # Monitor layout (1440p144 primary + 2x 1080p60) is per-user Niri config,
  # written on install day once connector names are known; jarvis-doctor
  # verifies all three modes are actually achieved.
}
