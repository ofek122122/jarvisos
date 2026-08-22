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
| Bootloader | **GRUB** on the WD Green's own ESP, as an at-every-boot OS chooser (JarvisOS + Windows). os-prober **reads the 2 TB disk's ESP read-only** and chainloads Windows there; F12 firmware menu stays as the escape hatch. Nothing ever writes to the Windows NVMe, the 2 TB disk, or their ESPs. |
| Compositor (Phases 0–4) | Niri (+ greetd/tuigreet) |
| 2 TB disk (D:) | **Off-limits, permanently** — Windows boots from its ESP here; os-prober reads it read-only; JarvisOS never creates/modifies/deletes anything on it. Models + episodic store + all state live on the WD Green. (ESP migration was considered and **cancelled** — accepted tradeoff: Windows boot depends on D:'s health, same as today. See `docs/drives.md`.) |
| Secure Boot | Off for the install; **lanzaboote lands right after Phase 0, then Secure Boot is re-enabled** (Riot Vanguard requires it on Windows 11) |
| Kernel | Stock first; custom kernel is a second pass after first boot works |

Drive identities and serials: [`docs/drives.md`](docs/drives.md). **Read it
before every destructive step.**

---

## Runbook A — Pre-flight (Windows, before install day)

Four items; nothing here is optional. (E: is already cleaned and ready —
disko wipes it on install day. The repo is on GitHub, reachable from the
live USB. The 2 TB disk and the NVMe are never touched, so there is no ESP
migration and no Windows-partition mount — Fast Startup no longer matters
for JarvisOS, though a clean full shutdown of Windows before install is
still tidy for os-prober.)

1. **Check BitLocker + back up the key** (admin): `manage-bde -status C:`.
   If ON, save the recovery key (Microsoft account or printout) *before*
   touching Secure Boot, or Windows may demand it on next boot.
2. **Create a Windows recovery USB** (`recoverydrive.exe`) and **boot-test
   it** (F12 → confirm it boots). Safety net for the Secure Boot change and
   general Windows repair.
3. **Secure Boot decision** in the Gigabyte UEFI. To install NixOS now you
   disable Secure Boot; confirm F12 shows the one-time boot menu.
   > ⚠️ **While Secure Boot is off, Riot Vanguard titles (Valorant, League
   > of Legends) will NOT launch on Windows 11** — Vanguard enforces Secure
   > Boot + TPM 2.0. This is temporary: the post-Phase-0 lanzaboote task
   > (below) signs JarvisOS for Secure Boot, after which you **re-enable
   > Secure Boot in the UEFI** and both OSes — and Vanguard — work again.
   > Plan the outage window accordingly.
4. **Write the NixOS minimal ISO** (x86_64) to a *spare* USB stick with
   Rufus in dd mode. Never one of the three internal drives.

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
4. **Partition + format + mount** (destroys the WD Green only). disko
   prints the plan and asks you to confirm wiping the disk, then prompts
   for the LUKS passphrase — pick a strong one, it is asked at every boot:

   ```sh
   sudo nix --experimental-features "nix-command flakes" \
     run github:nix-community/disko/latest -- \
     --mode destroy,format,mount --flake .#ares
   ```

   > **Dry-run verified.** This exact command + the by-id edit in step 3
   > were executed end to end against a virtual disk (see
   > `docs/dry-run.md`): it produces the 1 GiB ESP + LUKS2 + btrfs
   > (`@root`/`@home`/`@nix`/`@log`) layout and mounts it under `/mnt`.

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

   Set the root password when prompted. This is the first full **build**
   of the system (CUDA, NVIDIA driver, wine, llama.cpp, the jv-* services)
   — expect it to take a while. If a large fetch fails transiently
   (`cannot download … from any mirror` — the NVIDIA/CUDA blobs are the
   usual culprits), just run the command again; Nix resumes from what it
   already has. The dry run confirmed the whole closure builds.
7. `reboot`. The **GRUB OS chooser** should appear (dark theme, "JarvisOS"
   title, 5 s timeout, JarvisOS selected). Pick JarvisOS, enter the LUKS
   passphrase. Log in as `ofek` / `jarvis-first-boot` and immediately:

   ```sh
   passwd
   ```

   If GRUB doesn't appear, F12 at power-on → the **WD Green** entry is the
   escape hatch (it always works).

8. Clone the repo onto the machine (e.g. `~/jarvisos`) and prove
   reproducibility from a clean clone (exit-checklist item):

   ```sh
   sudo nixos-rebuild switch --flake ~/jarvisos#ares
   ```

9. Fill in the small TODOs as their own commits: NVIDIA running version in
   `modules/gpu-nvidia.nix`, timezone confirmation, monitor layout in the
   Niri config (connector names are only knowable now).
10. **Verify**: inside the Niri session run `jarvis-doctor`. Work each FAIL
    until ALL PASS. (In a VM most checks fail for want of hardware — see
    the expected-results table below so you can tell a normal gap from a
    real problem.)
11. **Verify the GRUB OS chooser + Windows chainload** (first real run —
    could not be proven in the dry run, which has no boot and no Windows):
    - GRUB menu shows **JarvisOS** (default) and a **Windows** entry
      (os-prober names it "Windows Boot Manager (on /dev/nvme…)").
    - Older generations live under the **"All configurations"** submenu.
    - Select the Windows entry → Windows boots. Then reboot → JarvisOS.
    - **If the Windows entry is missing** (os-prober didn't detect it),
      add it by hand: find the Windows ESP UUID and fill the template in
      `modules/boot-grub.nix` (`extraEntries`), then rebuild:

      ```sh
      # find the Windows ESP (vfat, ~100 MB, on the Crucial NVMe):
      lsblk -o NAME,MODEL,FSTYPE,SIZE,UUID | grep -iA4 CT500P2SSD8
      # put that UUID in modules/boot-grub.nix extraEntries, then:
      sudo nixos-rebuild switch --flake ~/jarvisos#ares
      ```

    - **Escape hatch, always**: F12 at power-on → "Windows Boot Manager"
      on the Crucial NVMe. This never depends on GRUB or os-prober.

### jarvis-doctor: expected results in a VM/dry-run vs on ares

On the real machine every check must PASS. In a VM (or the WSL dry run)
they split into two kinds of "fail" — this is how you tell them apart:

| Check | In a VM | Why | On ares |
|---|---|---|---|
| GPU sees GTX 1660 SUPER | FAIL | no GPU passthrough | must PASS |
| CUDA kernel runs | FAIL | no GPU | must PASS |
| Camera RGB + IR frames | FAIL | no webcam | must PASS |
| PipeWire mic + record | FAIL | no audio device | must PASS |
| 3 monitors at native res | FAIL | one virtual display | must PASS |
| **Windows NVMe not found** | FAIL* | the Crucial isn't in a VM | must PASS (present, unmounted) |
| **/boot ESP on "WD Green"** | FAIL* | model string differs in a VM | must PASS |
| **2 TB WD20EZAZ present, not mounted** | FAIL* | the disk isn't in a VM | must PASS (present, off-limits, unmounted) |
| No Windows entry in bootloader | PASS | genuinely true in a clean VM | must PASS |

**\*** = "environment artifact": the check looks for a specific real disk
by model that a VM lacks. Not a real problem — it flips to PASS on ares
where the disks exist. The **hardware** fails (GPU/camera/mic/monitors)
are the "no NVIDIA / no sensors / no triple-head" gaps and also pass once
the hardware is present. So: **a fully-failing doctor in a VM is normal;
on ares, any remaining FAIL is a real problem.**

> One doctor caveat to check on first boot: the ESP-on-WD-Green check
> greps the disk model for "WD Green" (with a space). If `lsblk` shows
> the model with underscores (`WD_Green_…`), tweak the grep in
> `pkgs/jarvis-doctor/doctor.sh`. Verify on ares.

## Runbook D — Rollback drill (do once, deliberately)

1. Make any trivial change (e.g. add a package), `nixos-rebuild switch`.
2. Reboot → in the GRUB menu open the **"All configurations"** submenu and
   pick the **previous** generation.
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

- **Secure Boot** (post-Phase-0, prioritized — it unblocks Vanguard gaming
  on Windows): create + enroll our own keys with `sbctl create-keys` +
  `sbctl enroll-keys --microsoft` (**`--microsoft` is mandatory** — it keeps
  Microsoft's certs in the db so Windows still boots), then **sign our GRUB
  EFI binary** (we boot GRUB, not systemd-boot, so lanzaboote — which is
  systemd-boot-specific — does not apply; the GRUB path is sbctl-signing
  GRUB, or shim). This IS a boot change → full build → diff → test → switch
  discipline; verify both OSes boot with Secure Boot off, then **re-enable
  Secure Boot in the UEFI** and verify JarvisOS boots, Windows boots, and a
  Vanguard title launches. Keep a live-USB + the recovery USB at hand.
- Custom kernel (localmodconfig seed, PREEMPT full, HZ=1000, uvcvideo +
  uinput built in) — second pass, own session, stock generation kept.
- Then: Phase 0 exit checklist in `BRIEF-phase0.md`, then request
  BRIEF-phase1 (the bus + the voice loop).
