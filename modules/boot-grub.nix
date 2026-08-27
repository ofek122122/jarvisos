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

    # Windows is added explicitly below (extraEntries), NOT via os-prober.
    # os-prober produced no Windows entry on ares (2026-08-27) even with
    # this on; a `search --file` chainload is deterministic and reviewable.
    # Off also means nothing scans/mounts the Windows disks at rebuild time.
    useOSProber = false;

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

    # Explicit Windows chainload — the at-every-boot chooser's second entry.
    # `search --file` locates the Windows ESP by the bootloader file itself
    # (only the 2 TB disk's ESP holds /EFI/Microsoft/Boot/bootmgfw.efi), so
    # NO install-day UUID is hardcoded and nothing ever points at a guessed
    # partition. GRUB reads that ESP READ-ONLY to hand off — the one
    # permitted interaction with the off-limits 2 TB disk (see CLAUDE.md).
    # Secure Boot is disabled, so bootmgfw.efi chainloads directly.
    extraEntries = ''
      menuentry "Windows" --class windows {
        insmod part_gpt
        insmod fat
        insmod chain
        search --no-floppy --file --set=root /EFI/Microsoft/Boot/bootmgfw.efi
        chainloader /EFI/Microsoft/Boot/bootmgfw.efi
      }
    '';
  };
}
