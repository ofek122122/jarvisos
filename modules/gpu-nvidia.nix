# GTX 1660 SUPER (Turing, 6 GB) — Wayland-native, CUDA-capable.
#
# CLAUDE.md: the driver version is pinned explicitly and changed
# deliberately, alone, in its own commit.
{ config, ... }:
{
  # Historical option name; it governs the kernel driver regardless of X11.
  services.xserver.videoDrivers = [ "nvidia" ];

  hardware.graphics.enable = true;

  hardware.nvidia = {
    # PIN: `production` resolves to a fixed version for a given flake.lock,
    # so the effective pin is nixpkgs' lock entry. After the first boot,
    # record the running version here and, if we ever need to diverge from
    # nixpkgs, hard-pin with:
    #   package = config.boot.kernelPackages.nvidiaPackages.mkDriver {
    #     version = "...", sha256_64bit = "...", ... };
    # RUNNING VERSION: TODO(install-day) — fill from `nvidia-smi`.
    package = config.boot.kernelPackages.nvidiaPackages.production;

    # Open kernel modules: supported on Turing and required direction for
    # new drivers. If Wayland glitches appear on first boot, `open = false`
    # is the first fallback to try — as its own commit.
    open = true;

    # Required for Wayland.
    modesetting.enable = true;

    powerManagement.enable = false; # desktop, not a laptop
    nvidiaSettings = false; # X11 tool, useless here
  };
}
