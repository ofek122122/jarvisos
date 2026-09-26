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
  # EVERY FIELD CHECK 5 COMPARES IS THE KIND OF VALUE niri PRINTS (PLAN E16).
  # The expectation below is a TSV of STRINGS and doctor.sh compares each field
  # with what `niri msg outputs` printed, so a value `toString` mangles is not a
  # wrong monitor — it is a doctor that reports a correct machine as broken for
  # ever. `x = 2560.0` is the whole finding: it is the RIGHT position, it passes
  # the overlap arithmetic below (floats add and compare fine), it builds, and
  # the row it ships says `2560.000000` where the compositor says `2560`. The
  # other three ways this row goes wrong are each their own sentence in no
  # message at all: a quoted `x = "2560"` dies inside the overlap arithmetic
  # with "cannot coerce an integer to a string: 1920" — a number from another
  # field of another entry, naming no output and no file; an unquoted
  # `refresh = 144.006` dies in the interpolation with "cannot coerce a float to
  # a string"; and `name = ""` evaluates, builds, and makes check 5 tell two
  # lies at once, because `awk '$1 == n'` matches no live output (so the monitor
  # is "declared and the session has no such output") and the extra-outputs arm
  # keys its want-set on the empty string (so every live monitor is one this
  # flake never declared).
  #
  # WHAT IS DELIBERATELY NOT REFUSED: a value that is merely WRONG. `x = 2561`
  # and `refresh = "60.001"` are exactly the disagreements check 5 exists to
  # report, and moving them up here would turn a finding about the machine into
  # an evaluation error about the flake. The line is "cannot be right", not "is
  # not right": these six clauses are the TSV's schema and nothing more.
  #
  # The columns are a list rather than six conditions because the list IS the
  # row — same fields, same order as the `writeText` below and as doctor.sh's
  # `read -r name w h hz x y`, which is the drift `test_doctor.py` holds all
  # three of against each other.
  columns = [
    {
      field = "name";
      wanted = "a non-empty string";
      ok = v: lib.isString v && v != "";
    }
    {
      field = "width";
      wanted = "an integer number of pixels";
      ok = builtins.isInt;
    }
    {
      field = "height";
      wanted = "an integer number of pixels";
      ok = builtins.isInt;
    }
    {
      # A STRING, and the exact decimal niri prints: the primary's mode is
      # 144.006, which is also what it has to be asked for to be offered 144 at
      # all (memory/ares-hardware-firstboot). `toString 144.006` is
      # "144.006000" and `toString 144` is "144", and neither is a mode.
      field = "refresh";
      wanted = ''a string, the exact decimal niri prints ("144.006")'';
      ok = v: lib.isString v && v != "";
    }
    {
      field = "x";
      wanted = "an integer pixel coordinate";
      ok = builtins.isInt;
    }
    {
      field = "y";
      wanted = "an integer pixel coordinate";
      ok = builtins.isInt;
    }
  ];

  # The value as it will LOOK in the message, never coerced: interpolating the
  # thing we are refusing is itself the error we are trying to replace, and the
  # type is most of the finding — `"2560"`, `2560.0` and absent are three
  # different typos with three different fixes.
  shown = o: field: if o ? ${field} then lib.generators.toPretty { } o.${field} else "absent";

  # Safe even when `name` is the field that is wrong, which is why it exists:
  # `box` below takes the name straight off the entry, so a nameless entry that
  # reached the overlap check would make the message about a collision throw
  # instead of printing. It cannot — `faults` is refused first.
  named = o: if lib.isString (o.name or null) && o.name != "" then o.name else "an unnamed entry";

  faults = lib.concatMap (
    o:
    let
      bad = lib.filter (c: !(c.ok (o.${c.field} or null))) columns;
    in
    # All of an entry's bad fields at once, and every entry's: a refusal that
    # stops at the first one is a rebuild per typo.
    lib.optional (bad != [ ]) (
      "${named o}: "
      + lib.concatMapStringsSep ", " (c: "${c.field} = ${shown o c.field} (wants ${c.wanted})") bad
    )
  ) outputs;

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
    # BEFORE the overlap check, not after: a string or a float `x` is arithmetic
    # the overlap rule does with no complaint (a float) or dies inside with an
    # error about another entry's width (a string), so the position has to be a
    # position before anything measures a desk with it.
    else if faults != [ ] then
      throw ''
        jarvis-doctor was handed a declaration whose fields are not the ones
        check 5 can compare:
        ${lib.concatStringsSep "\n" faults}
        Check 5's expectation is a TSV of strings and it compares each field
        with what `niri msg outputs` printed, so a value `toString` mangles is
        not a wrong monitor — it is this doctor reporting a healthy machine as
        broken on every boot. The float 2560.0 is the right position and ships
        as "2560.000000"; the string "2560" is the right position and stops the
        overlap arithmetic with an error about another output's width; an empty
        `name` matches no live output AND makes every live output undeclared.
        A value that is merely WRONG is left alone — `x = 2561` is the kind of
        disagreement check 5 exists to report, and belongs in the session's
        output, not in an evaluation error about hosts/ares/outputs.nix.
      ''
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
