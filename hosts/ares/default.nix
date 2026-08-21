# hosts/ares — the machine itself.
# i5 Comet Lake · 32 GB DDR4 · GTX 1660 SUPER 6 GB · 3 monitors (1440p144 + 2x 1080p60)
{ self, ... }:
{
  imports = [
    ./hardware.nix
    ./disko.nix
    ../../modules/gpu-nvidia.nix
    ../../modules/desktop.nix
    ../../modules/audio.nix
    ../../modules/security.nix
    ../../modules/windows-compat.nix
  ];

  networking.hostName = "ares";
  networking.networkmanager.enable = true;

  # systemd-boot on the WD Green's OWN ESP. Windows is deliberately NOT
  # registered here — the firmware F12 menu is the OS switch (CLAUDE.md).
  boot.loader.systemd-boot.enable = true;
  boot.loader.systemd-boot.editor = false;
  boot.loader.efi.canTouchEfiVariables = true;
  # No configurationLimit: every generation stays in the boot menu.
  # Do NOT enable nix.gc during active development (CLAUDE.md: never
  # garbage-collect old generations while experimenting).

  time.timeZone = "Asia/Jerusalem"; # TODO(ofek): confirm
  i18n.defaultLocale = "en_US.UTF-8";

  users.users.ofek = {
    isNormalUser = true;
    description = "Ofek";
    extraGroups = [ "wheel" "networkmanager" "video" "audio" "input" "uinput" ];
    # Placeholder for first login only — run `passwd` immediately after the
    # first boot (README runbook step). Not a secret; it is in a public repo.
    initialPassword = "jarvis-first-boot";
  };

  # 32 GB RAM: compressed swap in RAM, no swap partition. Hibernation is not
  # part of the design (dual boot goes through full shutdown anyway —
  # Fast-Startup-style hibernation is exactly what we disable on Windows).
  zramSwap.enable = true;

  nix.settings.experimental-features = [ "nix-command" "flakes" ];
  nixpkgs.config.allowUnfree = true; # NVIDIA + CUDA

  environment.systemPackages = [
    self.packages.x86_64-linux.jarvis-doctor
  ];

  # Kernel: STOCK for the first boots. The custom kernel (localmodconfig
  # seed, PREEMPT full, HZ=1000, uvcvideo/uinput built in) is BRIEF-phase0
  # task 4 — a second pass only after first boot works, in its own commit,
  # with the stock generation kept as fallback.

  system.stateVersion = "25.11"; # do not change after install
}
