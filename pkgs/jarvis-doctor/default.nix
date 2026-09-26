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
  # NO TWO MONITORS CAN SHOW THE SAME PIXEL (PLAN E15). `x` and `y` are a
  # top-left corner, and since E14 gave the declaration a `y` there is nothing
  # stopping two outputs from being declared on top of each other: a legal Nix
  # file, a successful build, bespoke art composed for both, and a check 5 that
  # reports PASS — because it compares each connector's mode and position on
  # its own and never asks whether the desk they add up to exists. That is the
  # one property of this list no single entry can be wrong about, which is why
  # it is checked here, in the package that spends the position, rather than
  # left to the file that declares it.
  #
  # GAPS ARE LEGAL, AND ARES HAS ONE. Its two 1080p panels sit beside a 1440p
  # primary, so 1.4 Mpx of the layout's bounding box is no screen at all (the
  # 360 px under each panel). A desk is any arrangement of rectangles that do
  # not collide; requiring them to tile a rectangle would refuse this machine's
  # actual monitors. Edges that TOUCH are legal too — DP-1's left edge is the
  # primary's right edge, 2560 — which is why the comparison below is strict.
  box = o: {
    inherit (o) name;
    l = o.x;
    r = o.x + o.width;
    t = o.y;
    b = o.y + o.height;
  };

  # The intersection of two outputs, reported as a rectangle rather than as a
  # yes: "DP-1 and DP-2 overlap" is a sentence somebody then has to go and
  # measure, and a 1 px collision from a mistyped `x` is a different mistake
  # from a panel declared entirely inside another.
  overlap =
    a: b:
    let
      x = lib.max a.l b.l;
      y = lib.max a.t b.t;
      w = (lib.min a.r b.r) - x;
      h = (lib.min a.b b.b) - y;
    in
    lib.optional (w > 0 && h > 0) (
      "${a.name} and ${b.name} overlap by ${toString w}x${toString h} px "
      + "at ${toString x},${toString y}"
    );

  boxes = map box outputs;
  overlaps = lib.concatMap (
    i:
    lib.concatMap (j: overlap (builtins.elemAt boxes i) (builtins.elemAt boxes j)) (
      lib.range (i + 1) (builtins.length boxes - 1)
    )
  ) (lib.range 0 (builtins.length boxes - 1));

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
    else if overlaps != [ ] then
      throw ''
        jarvis-doctor was handed a layout whose monitors overlap:
        ${lib.concatStringsSep "\n" overlaps}
        Two outputs cannot show the same pixel, so this is not a desk any
        machine can produce — and check 5 would not say so: it compares each
        connector's mode and corner on its own, so it reports PASS on the
        session that failed to lay these monitors out as declared. A gap is
        legal (ares declares one); an overlap is a typo in the `x` or `y` of
        hosts/ares/outputs.nix.
      ''
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
