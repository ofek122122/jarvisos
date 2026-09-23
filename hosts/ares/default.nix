# hosts/ares — the machine itself.
# i5 Comet Lake · 32 GB DDR4 · GTX 1660 SUPER 6 GB · 3 monitors (1440p144 + 2x 1080p60)
{ self, pkgs, ... }:
{
  imports = [
    ./hardware.nix
    ./disko.nix
    ../../modules/gpu-nvidia.nix
    ../../modules/desktop.nix
    ../../modules/audio.nix
    ../../modules/security.nix
    ../../modules/windows-compat.nix
    ../../modules/jarvis-services.nix
    ../../modules/boot-grub.nix
    ../../modules/boot-plymouth.nix
  ];

  # Branding: the OS calls itself JarvisOS — GRUB entries, /etc/os-release
  # NAME, the works. distroId stays "nixos" (tools key off it).
  system.nixos.distroName = "JarvisOS";

  networking.hostName = "ares";
  networking.networkmanager.enable = true;

  # Boot: GRUB as an at-every-boot OS chooser (JarvisOS + Windows),
  # installed on the WD Green's OWN ESP. See modules/boot-grub.nix.
  # Windows is detected read-only via os-prober and chainloaded; the
  # firmware F12 menu remains the always-works escape hatch. The hard
  # rule stands: nothing ever writes to the Windows NVMe or its ESP.
  boot.loader.efi.canTouchEfiVariables = true; # NVRAM only, not any disk
  boot.loader.efi.efiSysMountPoint = "/boot"; # the WD Green's ESP
  # No generation limit: every generation stays in the submenu. Do NOT
  # enable nix.gc during active development (CLAUDE.md: never garbage-
  # collect old generations while experimenting).

  time.timeZone = "Asia/Jerusalem"; # confirmed live 2026-09-15 (timedatectl)
  # Dual boot: Windows keeps the RTC in LOCAL time and we never touch
  # Windows, so JarvisOS matches it. Without this, every OS switch skewed
  # the clock ±3 h until NTP caught up (seen in the journal, 2026-09-15).
  time.hardwareClockInLocalTime = true;
  i18n.defaultLocale = "en_US.UTF-8";

  users.users.ofek = {
    isNormalUser = true;
    description = "Ofek";
    extraGroups = [ "wheel" "networkmanager" "video" "audio" "input" "uinput" "jarvis" ];
    # Placeholder for first login only — run `passwd` immediately after the
    # first boot (README runbook step). Not a secret; it is in a public repo.
    initialPassword = "jarvis-first-boot";
  };

  # 32 GB RAM: compressed swap in RAM, no swap partition. Hibernation is not
  # part of the design (dual boot goes through full shutdown anyway —
  # Fast-Startup-style hibernation is exactly what we disable on Windows).
  zramSwap.enable = true;

  # A plugged-in desktop: hold the CPU at full clock so a voice/gesture
  # burst starts computing immediately instead of paying the governor's
  # ramp-up tax on the <100 ms latency budget.
  powerManagement.cpuFreqGovernor = "performance";

  # The WD Green is DRAM-less and degrades under sustained writes without
  # TRIM. disko sets allowDiscards on the LUKS device (passthrough), but
  # nothing issued TRIM until now — the weekly fstrim timer does.
  services.fstrim.enable = true;

  nix.settings.experimental-features = [ "nix-command" "flakes" ];
  nixpkgs.config.allowUnfree = true; # NVIDIA + CUDA

  environment.systemPackages = [
    self.packages.x86_64-linux.jarvis-doctor
    pkgs.tmux # persistent session host for the ops/ralph autonomous build loop
  ];

  # Kernel: STOCK for the first boots. The custom kernel (localmodconfig
  # seed, PREEMPT full, HZ=1000, uvcvideo/uinput built in) is BRIEF-phase0
  # task 4 — a second pass only after first boot works, in its own commit,
  # with the stock generation kept as fallback.

  system.stateVersion = "25.11"; # do not change after install
}
