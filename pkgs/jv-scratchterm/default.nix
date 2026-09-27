# jv-scratchterm — PLAN H1: a drop-down scratchpad terminal, one key down,
# the same key away.
#
# niri's own wiki (Configuration: Window Rules > default-floating-position)
# documents the whole "dropdown terminal" shape wholesale: a floating window
# anchored to the top edge, sized to a proportion of the output, matched by a
# dedicated app-id — "you can use single-side relative-to to get a
# dropdown-like effect", with alacritty's own `--class` flag named as the way
# to set that app-id. `modules/niri.nix` declares that window-rule plus a
# named workspace, "jv-scratch" — niri's own docs: "named workspaces always
# exist, even when they have no windows" — pinned to ares' PRIMARY output
# (hosts/ares/outputs.nix's own `primary = true` entry) so the terminal
# always drops down in the same place. What niri does not ship is the toggle
# itself, which is the whole of this script.
#
# THE TOGGLE NEEDS NO STATE FILE OF ITS OWN. The named workspace's own
# `is_active` (`niri msg --json workspaces`) already answers "is it on
# screen right now" — that IS the hidden/shown flag PLAN G4's disk warning
# had to invent a state file for, because a workspace being active or not is
# a fact niri already tracks. Three cases, in the order the script checks
# them:
#   1. The workspace is active (the terminal is on screen) -> hide it:
#      `focus-workspace-previous`, back to wherever the user was.
#   2. It is not active, but a `jv-scratchterm` window already exists
#      (hidden on its own workspace) -> show it: `focus-workspace jv-scratch`.
#   3. Neither -> first run: spawn the terminal (the window-rule sends it to
#      "jv-scratch" and floats/sizes it), then show that workspace the same
#      way case 2 does, so the very first press already shows something
#      instead of merely creating it in the background.
#
# WHY `runtimeInputs` AND BARE COMMAND NAMES rather than pinning
# `${niri}/bin/niri` etc. literally into the text, the way pkgs/jv-lock pins
# swaylock. That rule is for surfaces nothing can safely re-point (a lock
# screen, a bus reader); this is an interactive keybind a human presses, and
# `writeShellApplication`'s own PATH assembly (runtimeInputs first, ahead of
# the inherited $PATH) is the same "the declared one wins, always" guarantee
# PLAN G3/G4's login/timer scripts already rely on — and, unlike a literal
# store-path interpolation, it lets `tools/tests/test_scratchterm.py` run the
# real extracted script against fake `niri`/`alacritty` stubs on PATH, the
# same technique those two suites use.
{
  writeShellApplication,
  niri,
  jq,
  alacritty,
}:
writeShellApplication {
  name = "jv-scratchterm";

  runtimeInputs = [
    niri
    jq
    alacritty
  ];

  text = ''
    app_id="jv-scratchterm"
    workspace="jv-scratch"

    active=$(niri msg --json workspaces \
      | jq -r --arg ws "$workspace" '[.[] | select(.name == $ws) | .is_active] | .[0] // false')

    if [ "$active" = "true" ]; then
      niri msg action focus-workspace-previous
      exit 0
    fi

    exists=$(niri msg --json windows \
      | jq -r --arg app "$app_id" '[.[] | select(.app_id == $app)] | length')

    if [ "$exists" -eq 0 ]; then
      alacritty --class "$app_id" &
      disown
    fi

    niri msg action focus-workspace "$workspace"
  '';

  meta = {
    description = "Drop-down scratchpad terminal, toggled by one key (PLAN H1)";
    mainProgram = "jv-scratchterm";
  };
}
