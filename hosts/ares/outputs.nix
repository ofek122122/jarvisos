# hosts/ares/outputs.nix — THE MONITORS ares ACTUALLY HAS, declared once.
#
# Pure data, imported rather than a NixOS module, because the first thing that
# needs it is not a module: `flake.nix` fills `pkgs/jarvis-wallpaper`'s
# `outputs` argument from this list, and a package argument cannot come out of
# `config`. A module option that also read this file would be the same list
# said twice.
#
# WHY IT EXISTS (PLAN E10). The wallpaper composed a render for each of
# `2560x1440 1920x1080 3840x2160 2560x1080 1366x768` — a list written inside
# the package, three entries of which are geometries this machine cannot
# display and one of which (1366x768) it never will. An output NOT on that
# list gets the primary art scaled and cropped, which has been correct since
# PLAN E9 (the shell anchors to where the crop actually landed) but is still
# not art composed for it. So the list stays a list, and becomes the RIGHT
# list: the outputs this host declares. Add a monitor here and it has bespoke
# art on the next rebuild, sampled by the pixel gate (E11) the day it appears,
# with nobody remembering to edit a package.
#
# The numbers are the ones CLAUDE.md states and `jarvis-doctor` measures live
# on the machine: one 2560x1440 primary at 144 Hz (the HP 27xq, which needs
# 144.006 to be offered it at all — see memory/ares-hardware-firstboot) and
# two 1920x1080 at 60, to its right. `x` is the left edge of each output in
# the layout; it is what PLAN E5 will hand to niri when the per-output rules
# move into the flake, and it is here now so that E5 moves rules rather than
# re-deciding a layout.
#
# `primary = true` belongs to exactly one entry, and the wallpaper leans on it:
# `jarvisos.png` — the art the lock screen shows and the art every UNDECLARED
# geometry falls back to — is composed at the primary's size. Two primaries or
# none is a `throw` in the package, not a default.
[
  {
    name = "HDMI-A-1";
    width = 2560;
    height = 1440;
    refresh = "144.006";
    x = 0;
    primary = true;
  }
  {
    name = "DP-1";
    width = 1920;
    height = 1080;
    refresh = "60.000";
    x = 2560;
  }
  {
    name = "DP-2";
    width = 1920;
    height = 1080;
    refresh = "60.000";
    x = 4480;
  }
]
