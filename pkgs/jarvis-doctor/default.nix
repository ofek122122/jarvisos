# jarvis-doctor — packaged Phase 0 verifier. `writeShellApplication` runs
# shellcheck over the script at build time and pins every tool it calls.
{
  lib,
  writeShellApplication,
  cuda-smoke,
  v4l-utils,
  util-linux,
  pipewire,
  wireplumber,
  systemd,
  gawk,
  gnugrep,
  gnused,
  coreutils,
}:
writeShellApplication {
  name = "jarvis-doctor";

  runtimeInputs = [
    v4l-utils # v4l2-ctl
    util-linux # lsblk, findmnt
    pipewire # pw-record
    wireplumber # wpctl
    systemd # bootctl
    gawk
    gnugrep
    gnused
    coreutils # timeout, mktemp
    # nvidia-smi and `niri msg` come from the running system/session —
    # they must match the booted generation, not this package's pins.
  ];

  runtimeEnv.CUDA_SMOKE = lib.getExe cuda-smoke;

  text = builtins.readFile ./doctor.sh;
}
