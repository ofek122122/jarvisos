# Windows-binary support (BRIEF-phase2 §4, blueprint §08).
# Completed from the Phase 0 stub.
#
# TODO(machine): binfmt + wine render paths verified on ares only
# (exit item 5). Evaluation is CI-checked; runtime is install-day.
{ pkgs, ... }:
{
  # PE binaries as first-class executables: the kernel hands MZ files to
  # wine the way it hands #! scripts to bash (blueprint §08 Layer A).
  boot.binfmt.registrations.windows = {
    magicOrExtension = "MZ";
    interpreter = "${pkgs.wineWowPackages.stagingFull}/bin/wine";
    # fixBinary must stay false: nixpkgs asserts against it when the
    # interpreter resolves through a shell wrapper, which wine's launcher
    # is. (The blueprint's example used true; the wrapper makes it
    # invalid here — verified by flake eval.)
    fixBinary = false;
    preserveArgvZero = false;
    # bwrap confinement is applied by jv-compat per-recipe, not here —
    # binfmt is only the "double-click runs it" convenience.
  };

  environment.systemPackages = with pkgs; [
    wineWowPackages.stagingFull
    winetricks
    bottles # per-app prefix GUI (exploratory installs)
    umu-launcher # Proton-GE outside Steam
    bubblewrap # jv-compat confinement
    clamav # jv-guard screening engine
  ];

  # MIME associations so xdg-open routes installers correctly.
  environment.etc."jarvis/mimeapps.list".text = ''
    [Default Applications]
    application/x-ms-dos-executable=jv-compat.desktop
    application/x-msi=jv-compat.desktop
    application/x-ms-shortcut=jv-compat.desktop
  '';

  # ClamAV signature updater (jv-guard depends on a populated DB;
  # without it, guard fails closed rather than granting trust).
  services.clamav.updater.enable = true;
}
