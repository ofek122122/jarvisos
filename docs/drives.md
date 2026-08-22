# Drive identities — ares

Recorded from Windows 11 on 2026-08-21 (`Get-PhysicalDisk` / `Get-Partition`,
read-only). **Triple-check against this table before any destructive command.
Match by SERIAL, never by device name or disk number — those reorder between
boots and between Windows and Linux.**

| Windows disk | Model | Serial | Size | Role |
|---|---|---|---|---|
| Disk 2 (C:) | Crucial **CT500P2SSD8** NVMe | `6479_A7FF_F000_1D71` ¹ | 465.8 GB | **Windows — NEVER TOUCH** |
| Disk 1 (E:) | **WD Green 2.5 1000GB** SATA SSD | `23440S448710` | 931.5 GB | **JarvisOS target — wiped on install** |
| Disk 0 (D:) | **WDC WD20EZAZ-00GGJB0** 2 TB HDD | `WD-WXL2A90L3KAP` | 1863 GB | **Off-limits, permanently** — Windows boots from its ESP here; os-prober reads it read-only; JarvisOS never writes to it |

> ⚠️ **E: is destroyed on install day.** disko `--mode destroy,format,mount`
> wipes the entire WD Green. E: has already been cleaned and is ready; there
> is nothing left to back up. The Crucial (C:/Windows) and the 2 TB (D:) are
> never written to and keep their data.
>
> **Windows chooser note:** the bootloader is GRUB (an at-every-boot
> JarvisOS + Windows menu) on the WD Green's ESP. GRUB's os-prober reads the
> **2 TB disk's ESP read-only** and chainloads Windows there — it never
> writes to any Windows disk. Windows detection can't be proven until
> install day; the runbook has the verify step + a manual-entry fallback,
> and F12 → Windows Boot Manager (on the 2 TB disk) is the always-works
> escape hatch.

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
- `ata-WDC_WD20EZAZ…WD-WXL2A90L3KAP` → 2 TB data disk → **off-limits, must never appear in any command** (os-prober reads its ESP read-only, that's all)

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

Windows therefore boots from the 2 TB disk's ESP. That is left exactly as
it is (see the decision below).

## Decision: the 2 TB disk is permanently off-limits; ESP migration CANCELLED

Chosen by Ofek, 2026-08-23 (supersedes the 2026-08-21 migration plan):

- **The 2 TB disk (D:) is off-limits, permanently — same standing as the
  Windows NVMe.** Nothing on it is ever created, modified, or deleted. The
  only permitted interaction is **os-prober reading its ESP read-only** to
  build the GRUB Windows-chainload entry.
- **The ESP migration and its 3-boot soak are cancelled.** Their purpose
  was to free the 2 TB disk for `/tank`; with the disk off-limits there is
  nothing to free. Windows keeps booting from its existing ESP on the 2 TB
  disk, and GRUB (on the WD Green) chainloads it there.
- **Accepted tradeoff:** Windows's ability to boot depends on the 2 TB
  disk's health — exactly as it does today. If that disk fails, Windows
  won't boot (unchanged from the current situation); JarvisOS lives entirely
  on the WD Green and is unaffected. F12 → Windows Boot Manager on the 2 TB
  disk remains the firmware-level escape hatch.
- **There is no `/tank`.** All JarvisOS storage — models, the episodic
  store, every state dir — lives on the WD Green root (btrfs, 931 GB, ample).
  `models/fetch.sh` and the service configs already default to
  `/var/lib/jarvis/...` on that root.

Note: no JarvisOS tooling or install command may ever write to the Windows
NVMe or the 2 TB disk. Both are strictly read-at-most (os-prober reads the
2 TB ESP read-only; nothing reads or writes the NVMe).

## Pre-flight progress log

- **2026-08-23 — BitLocker: NONE.** All four volumes (C:, D:, E:, F:)
  report `ProtectionStatus=Off`, `FullyDecrypted`, 0% — checked elevated
  via `Get-BitLockerVolume`. No recovery keys exist; toggling Secure Boot
  will NOT trigger any BitLocker recovery. (No key material is ever stored
  in this repo.) ✅
- **2026-08-23 — Fast Startup: OFF.** `HiberbootEnabled=0`, `powercfg /h
  off` ran clean (exit 0), no `hiberfil.sys`. ✅
- **2026-08-23 — NixOS installer USB:** F: (7.4 GB SanDisk Cruzer Blade)
  was too small for a recovery drive (<16 GB), so per plan it becomes the
  **NixOS installer**. NixOS **26.05** minimal ISO (x86_64, 1.59 GB)
  downloaded and **sha256 VERIFIED** against the official
  `2fdadb46…16592` — MATCH. ✅ Rufus 4.15 portable staged. Write to F:
  pending user "go" (GPT / UEFI / DD mode). ⏳
- Windows **recovery USB**: deferred to a ≥16 GB stick (still open). Note:
  with no BitLocker present, this is a general Windows-repair parachute,
  not required for the Secure Boot change.
