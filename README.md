# JarvisOS

A NixOS-based operating system whose desktop assistant — Jarvis — perceives
through camera, microphone and system context, remembers its user long-term,
and acts on the machine. Design: [`docs/blueprint.html`](docs/blueprint.html).
Invariants: [`CLAUDE.md`](CLAUDE.md). Current phase: **0 — Ground**
([`BRIEF-phase0.md`](BRIEF-phase0.md)), prepared in advance from Windows,
awaiting install day.

## Locked decisions

| Decision | Choice |
|---|---|
| Host name | `ares` |
| Root filesystem | btrfs + zstd on LUKS2, WD Green 1 TB |
| Bootloader | systemd-boot on the WD Green's own ESP; Windows **not** registered — firmware F12 menu picks the OS |
| Compositor (Phases 0–4) | Niri (+ greetd/tuigreet) |
| Windows ESP | Migrate to NVMe with recovery-USB + 3-boot soak protocol (see below) |
| `/tank` (2 TB disk) | **Deferred** — disk completely untouched in Phase 0 |
| Kernel | Stock first; custom kernel is a second pass after first boot works |

Drive identities and serials: [`docs/drives.md`](docs/drives.md). **Read it
before every destructive step.**

---

## Runbook A — Pre-flight (Windows, before install day)

Do these in order. Nothing on this list is optional.

1. **Confirm the drive map** in `docs/drives.md` matches reality and that
   everything on **E: (WD Green)** is expendable or backed up — it will be
   fully wiped.
2. **Push this repo to a remote** (or copy it to a USB stick). It currently
   lives on `D:` — the 2 TB disk — and must be reachable from the live USB.
3. **Check BitLocker** (admin): `manage-bde -status C:`. If ON: back up the
   recovery key (Microsoft account or printout) *before* touching Secure
   Boot, or Windows may demand it on next boot.
4. **Create a Windows recovery USB** (`recoverydrive.exe`) and verify it
   appears in the F12 boot menu. Required before the ESP migration.
5. **Run the ESP migration** (Runbook B). Windows must be booting from the
   NVMe before install day.
6. **Disable Fast Startup**: Control Panel → Power Options → "Choose what
   the power buttons do" → untick "Turn on fast startup". Prevents
   hibernation-locked NTFS during dual boot.
7. **In the Gigabyte UEFI**: disable Secure Boot (lanzaboote may return
   later); confirm F12 shows the one-time boot menu.
8. **Write the NixOS minimal ISO** (x86_64) to a *spare* USB stick with
   Rufus in dd mode. Never one of the three internal drives.

## Runbook B — Windows ESP migration (manual, from Windows)

Why: Windows currently boots from an ESP on the **2 TB data disk**; the
NVMe has no ESP at all (`docs/drives.md`). Windows must become
self-contained on its own disk.

Safety protocol (decided 2026-08-21): recovery USB first; the old ESP on
the 2 TB disk stays **completely intact** until Windows has booted from the
NVMe successfully **at least 3 times across several days**. Only then may
the old ESP be removed.

1. Recovery USB created and boot-tested (Runbook A step 4). BitLocker key
   backed up (step 3).
2. **Shrink C: by 300 MB**: Disk Management → right-click C: → Shrink
   Volume → 300 MB.
3. **Create the new ESP** — admin terminal, `diskpart`:

   ```
   list disk                  <- identify the 465 GB Crucial CT500P2SSD8
   select disk <N>            <- ITS number; verify size/model, don't assume 2
   create partition efi size=300
   format quick fs=fat32 label=NVME-ESP
   assign letter=S
   exit
   ```

4. **Install the bootloader into it** (admin):

   ```
   bcdboot C:\Windows /s S: /f UEFI
   ```

5. Reboot → F12. There will now be **two** "Windows Boot Manager" entries;
   Gigabyte usually shows the disk next to each — pick the one on the
   **P2/Crucial NVMe**. In the UEFI setup, set it as the *default* boot
   entry so unattended boots use it.
6. **Verify which ESP actually booted** — admin PowerShell after boot:

   ```powershell
   Get-Disk | Select-Object Number, FriendlyName, IsSystem
   ```

   `IsSystem` must be **True on the Crucial CT500P2SSD8**, False elsewhere.
7. **Soak**: repeat the verification on ≥3 boots across several days. Log
   each success in `docs/drives.md`.
8. After the soak — and only after — the old ESP on the 2 TB disk may be
   removed. That step is bundled with the deferred `/tank` decision; leave
   it alone until then. (The stale firmware boot entry pointing at the old
   ESP can also be deleted from the UEFI then.)

## Runbook C — Install day (NixOS live USB)

The Windows NVMe is out of scope for every command below. If any command
would name it, stop.

1. F12 → boot the NixOS USB. Wired ethernet is simplest; confirm with
   `ping cache.nixos.org`.
2. Get the repo:

   ```sh
   git clone <remote-url> jarvisos && cd jarvisos
   ```

3. **Verify drive identity** (the step that protects Windows):

   ```sh
   ls -l /dev/disk/by-id/ | grep -v part
   lsblk -o NAME,MODEL,SERIAL,SIZE,MOUNTPOINTS
   ```

   Find the entry whose serial is `23440S448710` (WD Green). If its by-id
   path differs from `device` in `hosts/ares/disko.nix`, fix the file now
   and commit. The Crucial (`CT500P2SSD8`) and the 2 TB (`WD-WXL2A90L3KAP`)
   must not appear in any subsequent command.
4. **Partition + format + mount** (destroys the WD Green only; prompts for
   the LUKS passphrase — pick a strong one, it is asked at every boot):

   ```sh
   sudo nix --experimental-features "nix-command flakes" \
     run github:nix-community/disko/latest -- \
     --mode destroy,format,mount --flake .#ares
   ```

5. **Regenerate + audit hardware config**:

   ```sh
   nixos-generate-config --no-filesystems --root /mnt --show-hardware-config
   ```

   Diff against `hosts/ares/hardware.nix`, merge deliberately (keep the
   audit comments), commit.
6. **Install**:

   ```sh
   sudo nixos-install --flake .#ares
   ```

   Set the root password when prompted.
7. `reboot`, F12 → the **WD Green** entry ("Linux Boot Manager"). Enter the
   LUKS passphrase. Log in as `ofek` / `jarvis-first-boot` and immediately:

   ```sh
   passwd
   ```

8. Clone the repo onto the machine (e.g. `~/jarvisos`) and prove
   reproducibility from a clean clone (exit-checklist item):

   ```sh
   sudo nixos-rebuild switch --flake ~/jarvisos#ares
   ```

9. Fill in the small TODOs as their own commits: NVIDIA running version in
   `modules/gpu-nvidia.nix`, timezone confirmation, monitor layout in the
   Niri config (connector names are only knowable now).
10. **Verify**: inside the Niri session run `jarvis-doctor`. Work each FAIL
    until ALL PASS.
11. **Windows still boots**: reboot → F12 → Windows (NVMe entry). Confirm,
    then return to JarvisOS.

## Runbook D — Rollback drill (do once, deliberately)

1. Make any trivial change (e.g. add a package), `nixos-rebuild switch`.
2. Reboot → in the systemd-boot menu pick the **previous** generation.
3. Confirm the change is absent; reboot into the newest again.

Now you know the safety net works before you need it.

## Change flow (always)

```sh
nixos-rebuild build --flake .#ares    # 1. build only
nvd diff /run/current-system result   # 2. read the diff (or: nix store diff-closures)
sudo nixos-rebuild test --flake .#ares    # 3. activate WITHOUT touching the bootloader
sudo nixos-rebuild switch --flake .#ares  # 4. only when test behaves
```

- **Never** `switch` an untested kernel or boot change.
- **Never** garbage-collect old generations during active development.
- NVIDIA driver changes: deliberate, alone, in their own commit.

## Deferred / next

- `/tank` on the 2 TB disk — blocked on data backup + old-ESP removal.
- Custom kernel (localmodconfig seed, PREEMPT full, HZ=1000, uvcvideo +
  uinput built in) — second pass, own session, stock generation kept.
- Old-ESP removal on the 2 TB disk — after the soak, with `/tank`.
- Then: Phase 0 exit checklist in `BRIEF-phase0.md`, then request
  BRIEF-phase1 (the bus + the voice loop).
