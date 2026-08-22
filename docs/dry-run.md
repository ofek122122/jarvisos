# Install-day dry run

A pre-install rehearsal of Runbook C, executed on the dev machine in
**WSL2 Ubuntu** (a real Linux kernel with btrfs + dm-crypt) rather than a
GUI VM. Why WSL2: a headless agent can't drive an interactive NixOS
installer inside a Hyper-V/VirtualBox graphical console, and the installed
VirtualBox (6.0.14) predates Hyper-V coexistence. WSL2 runs the *substance*
of the runbook — disko against a virtual disk and the real system build —
which catches more than a hand-driven boot would.

## What was executed and PASSED

- **Clone** (Runbook C step 2) — clean checkout from the repo.
- **The by-id device adjustment** (step 3) — verified as the single
  `device = "…"` line in `hosts/ares/disko.nix`; disko targets whatever
  it names. In the dry run it was pointed at a loop-mounted 16 GiB image;
  on ares it's the WD Green's `/dev/disk/by-id/ata-WD_Green_…_23440S448710`.
- **disko `--mode destroy,format,mount`** (step 4) — produced exactly the
  declared layout: 1 GiB ESP (vfat) + LUKS2 + btrfs with subvolumes
  `@root`/`@home`/`@nix`/`@log`, all mounted. LUKS format/open ran
  non-interactively via a throwaway passwordFile (the real run keeps the
  interactive passphrase prompt).
- **`nix build` of the whole `ares` system** (`nixos-rebuild build`
  equivalent) — the flake **evaluates** to `nixos-system-ares…drv` and the
  custom packages **build on Python 3.14** (jarvis-bus, jv-brain,
  jv-context, jv-guard, jv-compat, and the Rust jarvisd/jv-act via the
  flake). This had never been built before — CI only evaluates.
- **GRUB boot change** — the GRUB config evaluates (`useOSProber=true`,
  `configurationName="JarvisOS"`, systemd-boot disabled) and the
  **GRUB theme derivation builds** (dark theme + three pf2 fonts).

## Two real build bugs the dry run caught (both fixed)

The full `nix build` of the system — never run before, only evaluated in
CI — surfaced two genuine packaging bugs in our own flake. Neither would
have been caught by CI (which evaluates but does not build); both would
have failed the install-day `nixos-install`:

1. **`jv-act` nix package** — `buildAndTestSubdir` alone left the
   `Cargo.lock` unfindable at the src root (`Missing Cargo.lock`), and
   `cargoRoot` alone ran the build at the wrong dir (`could not find
   Cargo.toml`). Fix: set **both** `cargoRoot` and `buildAndTestSubdir`
   to `"jv-act"` (src stays `services/` so the `../jarvisd` path dep
   resolves). Verified: `nix build .#jv-act` produces the binary.
2. **`piper-tts` wheel** — its 1.7.0 runtime deps (`requires_dist`) list
   `pathvalidate` alongside `onnxruntime`, which I'd omitted;
   `pythonRuntimeDepsCheck` failed with `pathvalidate not installed`.
   Fix: add `python3Packages.pathvalidate`. Verified: `voiceEnv` builds
   and `import piper, pathvalidate, onnxruntime` succeeds on Python 3.14.

**Not a bug — environmental:** the CUDA archives (`cuda_nvrtc`,
`cuda_nvcc`, `cuda_cccl`) failed with "cannot download from any mirror" —
the same flaky NVIDIA download servers that dropped the driver blob.
These fetch normally on a reliable connection; if a nixpkgs fetch fails
transiently on install day, just re-run `nixos-install` (nix resumes).

## Friction fixed in the runbook / repo as a result

- Documented the disko confirm + LUKS prompt in step 4.
- Committed a **`flake.lock`** so a clean clone resolves the *same*
  nixpkgs (without it, builds drift — today they pick up Python 3.14).
- Noted the `wineWowPackages` → `wineWow64Packages` deprecation (warning
  only; follow-up).

## WSL-only quirks (NOT problems on ares — the real ISO differs)

These are environment artifacts of running disko in WSL2, not flake bugs:

- WSL needs `systemd=true` (for udevd) and `losetup -P` for a loop device
  to expose partition nodes and `by-partlabel` symlinks. The NixOS ISO
  runs udev normally, so N/A.
- WSL2's **5.15 kernel** can't mount btrfs with `block-group-tree` (needs
  Linux ≥ 6.1), which btrfs-progs now enables by default. The dry run
  passed `-O ^block-group-tree` *for the test only*; ares ships a 6.x
  kernel and needs no such flag.
- Single-user Nix run via `sudo` needs `build-users-group=` empty and a
  clean `/nix` ownership — artifacts of the WSL setup, not install day.

## What the dry run could NOT prove (first run happens on ares)

There is no real boot in WSL, so these move to the install-day verify
list (Runbook C steps 7, 10, 11):

- **GRUB actually booting** and rendering the themed OS chooser + the
  generations submenu.
- **Windows chainload** via os-prober (no Windows exists in the dry run) —
  with the manual `extraEntries` fallback documented.
- `nixos-install` + bootloader install (needs the live ISO environment).
- `jarvis-doctor` on booted hardware (all its checks are hardware- or
  disk-specific — see the expected-results table in the README).
