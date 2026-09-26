# modules/niri.nix — PLAN F1: the window-manager config, declared.
#
# ~/.config/niri/config.kdl carried every keybind Ofek actually uses (the
# F13/Super-menu tap, the ember focus ring, the jv-lock bind) and named only
# ONE of ares' three monitors, with no position — undeclared, so a clean-clone
# rebuild reproduced neither the binds nor the desk. Fixing this needed no new
# mechanism: niri already ships a system-wide slot for exactly this file.
# Its own docs (`Configuration: Introduction` > Loading) say so —
#   "niri will load configuration from $XDG_CONFIG_HOME/niri/config.kdl or
#    ~/.config/niri/config.kdl, falling back to /etc/niri/config.kdl"
# — and `niri-config/src/lib.rs` + `src/main.rs` in niri 26.04's own source
# hardcode that second path as `system_config_path()`. So this module writes
# THAT file, and niri only reads it once nobody has a user config in the way
# — the reason F1 is `[H]`: removing (or renaming) ~/.config/niri/config.kdl
# is a change to Ofek's own home directory, which nothing here does for him
# (PLAN's own rule: "nothing lands as an imperative tweak to a file in
# $HOME" cuts both ways — this module does not delete one either).
#
# `modules/niri/config-orig.kdl` is a frozen, byte-exact copy of the file this
# replaces, kept so `tools/tests/test_niri_config.py` can prove
# `config-base.kdl` (this module's other half) is that same file with its
# tail — the single-output stanza — removed and NOTHING ELSE, even one comment
# byte. `config-base.kdl` is `.text`'d in verbatim; only the output stanza is
# regenerated, from `hosts/ares/outputs.nix` — the same declaration PLAN E10
# already composes the wallpaper for and E13 already checks the doctor
# against, so this is the THIRD place that list is spent and not a second
# place the layout is decided.
{ lib, ... }:
let
  outputs = import ../hosts/ares/outputs.nix;

  # One `output "NAME" { mode "..."; position x=.. y=..; }` stanza per
  # declared monitor. `refresh` is already the exact decimal niri prints
  # (hosts/ares/outputs.nix's own rule, PLAN E16), so the mode string is
  # built the same way `jarvis-doctor` and `jarvis-wallpaper` read that file:
  # never rounded, never re-decided here.
  outputStanza = o: ''
    output "${o.name}" {
        mode "${toString o.width}x${toString o.height}@${o.refresh}"
        position x=${toString o.x} y=${toString o.y}
    }
  '';

  # The same helper modules/theme.nix, modules/fonts.nix and
  # modules/super-menu.nix use, for the same reason (invariant 9): a colour
  # is identity, named once in personality/theme.toml and only SPENT here.
  # config-base.kdl is niri's own default template plus one changed line
  # (the focus ring's active-color, which Ofek set to the ember accent) —
  # every hex literal it shipped with, including the ones inside the
  # disabled `border { off ... }` block, is still a colour, so all four are
  # markers rather than literals: `@@EMBER@@` for the accent this ring is
  # actually painted with, `@@LINE@@` for the stock neutral grey (both
  # inactive-color spots), `@@WARN@@` for the stock gold (border's
  # active-color), `@@RISK@@` for the stock red (border's urgent-color, the
  # closest existing token to "a window demanding attention").
  theme = builtins.fromTOML (builtins.readFile ../personality/theme.toml);
  token =
    name:
    theme.palette.${name} or (throw ''
      modules/niri.nix spends the colour "${name}", and [palette] in
      personality/theme.toml does not have it.'');
in
{
  environment.etc."niri/config.kdl".text =
    builtins.replaceStrings
      [ "@@EMBER@@" "@@LINE@@" "@@WARN@@" "@@RISK@@" ]
      [ (token "ember") (token "line") (token "warn") (token "risk") ]
      (builtins.readFile ./niri/config-base.kdl)
    + lib.concatMapStrings outputStanza outputs;
}
