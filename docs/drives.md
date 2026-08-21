# Drive identities — ares

Recorded from Windows 11 on 2026-08-21 (`Get-PhysicalDisk` / `Get-Partition`,
read-only). **Triple-check against this table before any destructive command.
Match by SERIAL, never by device name or disk number — those reorder between
boots and between Windows and Linux.**

| Windows disk | Model | Serial | Size | Role |
|---|---|---|---|---|
| Disk 2 (C:) | Crucial **CT500P2SSD8** NVMe | `6479_A7FF_F000_1D71` ¹ | 465.8 GB | **Windows — NEVER TOUCH** |
| Disk 1 (E:) | **WD Green 2.5 1000GB** SATA SSD | `23440S448710` | 931.5 GB | **JarvisOS target — wiped on install** |
| Disk 0 (D:) | **WDC WD20EZAZ-00GGJB0** 2 TB HDD | `WD-WXL2A90L3KAP` | 1863 GB | Future `/tank` — **decision deferred, untouched in Phase 0** |

¹ Windows WMI mangles NVMe serials; on Linux it will appear differently
(`nvme-CT500P2SSD8_<serial>` in `/dev/disk/by-id/`). Match on the model
string `CT500P2SSD8`, which is unambiguous — it is the only NVMe drive.

## On the NixOS live USB: verify before touching anything

```sh
ls -l /dev/disk/by-id/ | grep -v part
lsblk -o NAME,MODEL,SERIAL,SIZE,MOUNTPOINTS
```

Expected:

- `ata-…23440S448710` → the WD Green 1 TB → **the only disk disko may write to**
- `nvme-CT500P2SSD8…` → Windows → must never appear in any command
- `ata-WDC_WD20EZAZ…WD-WXL2A90L3KAP` → 2 TB data disk → must never appear in any command (Phase 0)

The exact by-id name of the WD Green must be confirmed on the live USB and,
if it differs, corrected in `hosts/ares/disko.nix` **before** running disko.

## Finding: the Windows bootloader does NOT live on the Windows drive

Partition scan from Windows (2026-08-21):

- **Disk 2 (Crucial NVMe, Windows C:) has no EFI System Partition at all.**
  Layout: MSR + C: + 2× Recovery.
- **Disk 0 (2 TB HDD) carries the live ESP** (100 MB, `IsSystem=True`) —
  Windows currently boots from the 2 TB data disk.
- Disk 1 (WD Green) carries a **stale** ESP (100 MB) from an apparent old
  Windows install. Nothing boots from it; it is destroyed with the rest of
  the WD Green on install day.

Consequence: wiping or repurposing the 2 TB disk as `/tank` without first
moving the ESP would make Windows unbootable.

## Decision: migrate the Windows ESP to the NVMe (with soak protocol)

Chosen by Ofek, 2026-08-21:

1. **Before anything else:** create a Windows recovery USB.
2. From Windows: shrink C: by ~300 MB, create a new ESP on the NVMe,
   `bcdboot` into it. (Step-by-step in README → "ESP migration".)
3. **The old ESP on the 2 TB disk stays completely intact until Windows has
   booted from the NVMe ESP successfully at least 3 times across several
   days.** Only after that soak period may the old ESP be removed.
4. The 2 TB disk's future as `/tank` remains a separate, deferred decision;
   Phase 0 does not mount, format, or reference it.

Note: this migration is a **manual, user-performed operation from Windows**.
It is the single sanctioned exception to "never write to the Windows NVMe",
decided explicitly by the user — no JarvisOS tooling or install script may
ever write to the NVMe.
