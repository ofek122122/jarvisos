# Storage layout for ares — the WD Green 1 TB ONLY.
#
# ############################################################################
# #  SAFETY                                                                  #
# #  - This file may reference exactly one disk: the WD Green 1 TB,          #
# #    serial 23440S448710 (docs/drives.md).                                 #
# #  - The Windows NVMe (CT500P2SSD8) and the 2 TB HDD (WD-WXL2A90L3KAP)     #
# #    must NEVER appear here. The 2 TB disk also carries the live Windows   #
# #    ESP until the migration soak completes — see docs/drives.md.          #
# #  - INSTALL DAY, BEFORE RUNNING DISKO: confirm the exact by-id path on    #
# #    the live USB (`ls -l /dev/disk/by-id/ | grep 23440S448710`) and fix   #
# #    `device` below if it differs. The serial is the source of truth.      #
# ############################################################################
#
# Layout: GPT → 1 GiB ESP (systemd-boot) + LUKS2 → btrfs (zstd) subvolumes.
# btrfs over ext4: transparent compression shrinks the Nix store, checksums
# catch bit-rot on a DRAM-less budget SSD, and subvolume snapshots cover
# /home — NixOS generations already cover the OS itself.
#
# /tank (the 2 TB disk) is deliberately absent: decision deferred, disk
# untouched in Phase 0.
{ ... }:
{
  disko.devices.disk.jarvis = {
    type = "disk";
    # TODO(install-day): verify on the live USB; serial 23440S448710 must match.
    device = "/dev/disk/by-id/ata-WD_Green_2.5_1000GB_23440S448710";
    content = {
      type = "gpt";
      partitions = {
        esp = {
          size = "1G";
          type = "EF00";
          content = {
            type = "filesystem";
            format = "vfat";
            mountpoint = "/boot";
            mountOptions = [ "umask=0077" ];
          };
        };
        root = {
          size = "100%";
          content = {
            type = "luks";
            name = "jarvis-root";
            # Passphrase prompted interactively by `disko` at create time
            # and by the initrd at every boot.
            settings.allowDiscards = true;
            content = {
              type = "btrfs";
              extraArgs = [ "-f" "-L" "jarvis" ];
              subvolumes = {
                "@root" = {
                  mountpoint = "/";
                  mountOptions = [ "compress=zstd" "noatime" ];
                };
                "@home" = {
                  mountpoint = "/home";
                  mountOptions = [ "compress=zstd" "noatime" ];
                };
                "@nix" = {
                  mountpoint = "/nix";
                  mountOptions = [ "compress=zstd" "noatime" ];
                };
                "@log" = {
                  mountpoint = "/var/log";
                  mountOptions = [ "compress=zstd" "noatime" ];
                };
              };
            };
          };
        };
      };
    };
  };
}
