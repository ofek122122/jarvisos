# Boot: GRUB as an at-every-boot OS chooser (JarvisOS + Windows).
# User-directed Phase 0 change, 2026-08-22 — replaces systemd-boot.
#
# HARD RULE (unchanged): nothing ever writes to the Windows NVMe or its
# ESP. GRUB installs ONLY to the WD Green's own ESP (/boot). os-prober
# READS the NVMe read-only to detect Windows Boot Manager and adds a
# chainload entry — it never writes there. efibootmgr writes firmware
# NVRAM variables only, not any disk.
{ pkgs, ... }:
let
  theme = pkgs.callPackage ./grub-theme { };
in
{
  boot.loader.systemd-boot.enable = false;

  # 5s menu, JarvisOS default, remember-last OFF (no savedefault) —
  # a predictable default beats convenience here.
  boot.loader.timeout = 5;

  boot.loader.grub = {
    enable = true;
    efiSupport = true;
    device = "nodev"; # EFI: no MBR target
    # Install to the WD Green's ESP only (efiSysMountPoint = /boot, set
    # in the host). Never install to, or as removable on, the NVMe.
    efiInstallAsRemovable = false;

    # The at-every-boot chooser: detect Windows on the NVMe (read-only)
    # and chainload it.
    useOSProber = true;

    default = 0; # "JarvisOS - Default" is entry 0
    # No `default = "saved"` and no savedefault: last choice is NOT
    # remembered — every boot starts on JarvisOS.

    # Clean main entry name. With older generations present this renders
    # as "JarvisOS - Default"; the generations themselves live in the
    # auto-generated "All configurations" submenu (no version spam up top).
    configurationName = "JarvisOS";

    theme = theme;
    splashImage = null; # theme paints the background (desktop-color)
    # Legibility first: ask for 1440p, fall back to whatever the firmware
    # offers. `keep` holds the mode through to the loaded kernel.
    gfxmodeEfi = "2560x1440,auto";
    gfxpayloadEfi = "keep";

    # Documented clean-"Windows" fallback (runbook C). If os-prober does
    # not detect Windows, OR you prefer the clean name over os-prober's
    # "Windows Boot Manager (on /dev/…)", drop the real ESP UUID in here
    # (found on install day) and it appears as a tidy "Windows" entry.
    # Left empty by default so it never points at a guessed partition.
    extraEntries = "";
    # Template (do NOT enable with a guessed UUID — see runbook C):
    #   menuentry "Windows" --class windows {
    #     insmod part_gpt
    #     insmod fat
    #     insmod chain
    #     search --fs-uuid --set=root <WINDOWS-ESP-UUID>
    #     chainloader /EFI/Microsoft/Boot/bootmgfw.efi
    #   }
  };
}
