# jarvis-doctor — packaged Phase 0 verifier. `writeShellApplication` runs
# shellcheck over the script at build time and pins every tool it calls.
#
# `outputs` is the monitors this host declares (hosts/ares/outputs.nix), and it
# is what check 5 compares the running session against. It has NO default, for
# PLAN E10's reason one package further along: a default is the same guess made
# where nobody looks, `callPackage` would supply it without a word, and the
# doctor would go back to verifying a machine somebody typed out rather than the
# one this flake declares.
{
  lib,
  writeShellApplication,
  writeText,
  outputs,
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
let
  # The expectation check 5 spends, generated rather than written (PLAN E13).
  # A FILE and not a shell string, the same file-not-string hop jv-wall's
  # `JV_WALL_DIR` makes (PLAN E12): its bytes are in the store, so
  # `ops/ralph/nixtest.sh` can read what the BUILT doctor will actually compare
  # against, and an interpolation that evaluated to the wrong list cannot look
  # right in this file.
  #
  # One row per output, tab-separated:  name  width  height  refresh  x  y
  # `refresh` stays the declaration's exact string (the primary is 144.006, not
  # 144) because that is what `niri msg outputs` prints, and `x  y` is the
  # output's top-left corner in the layout — the whole position, since PLAN E14
  # gave the declaration a `y`. A column added here and not read in doctor.sh
  # shifts every field after it, which is what `test_doctor.py` holds the two
  # halves of this hop together for.
  declared =
    if outputs == [ ] then
      throw (
        "jarvis-doctor was given an empty `outputs` list. Check 5 would then "
        + "have nothing to compare the session against and would PASS on any "
        + "monitor at all, which is the one failure this check cannot have."
      )
    else
      writeText "jarvis-declared-outputs.tsv" (
        lib.concatMapStrings (
          o:
          "${o.name}\t${toString o.width}\t${toString o.height}\t${o.refresh}\t${toString o.x}\t${toString o.y}\n"
        ) outputs
      );
in
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

  runtimeEnv = {
    CUDA_SMOKE = lib.getExe cuda-smoke;
    JARVIS_OUTPUTS = "${declared}";
  };

  text = builtins.readFile ./doctor.sh;
}
