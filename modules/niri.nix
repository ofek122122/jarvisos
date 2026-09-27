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
#
# PLAN H1 adds a drop-down scratchpad terminal (pkgs/jv-scratchterm) the same
# way: appended after config-base.kdl, never spliced into it. Its
# window-rule and named workspace are ordinary "multipart" KDL nodes (niri's
# own parser, niri-config/src/lib.rs, explicitly allows repeats of
# `window-rule`/`workspace`/`output`/`include`), so they join the tail
# straight after the output stanzas. Its keybind cannot: `binds` is NOT in
# that multipart list, and a SECOND top-level `binds { }` node is a hard
# parse error ("duplicate node `binds`, single node expected" — checked by
# hand against this exact ares' `niri validate` before writing this comment,
# since the wiki never says so). The one thing niri's own parser treats
# differently is `include "other.kdl"`: each included file gets its own
# `binds { }` allowance, and the config's own doc comment for that merge path
# ("import some preconfigured-dots.kdl, then override some binds with your
# own") is exactly this shape. So the new bind lives in a second `/etc/niri/`
# file, pulled in with a path RELATIVE to config.kdl's own directory (not
# absolute), which is also what lets `ops/ralph/nixtest.sh` validate both
# files together out of a throwaway directory that is never `/etc/niri`
# itself.
#
# PLAN H2 adds a power menu (pkgs/jv-power-menu) the same way as H1's
# keybind: its own `include`d file, `power-menu-binds.kdl`, since it needs no
# window-rule/workspace of its own (it is a themed dmenu popup, not a window
# niri places). "Boot Windows" is deliberately not one of its choices — see
# pkgs/jv-power-menu/default.nix's own comment and PLAN H2b.
#
# PLAN H3 adds clipboard history (pkgs/jv-clip-menu), the same shape again —
# its own `clipboard-binds.kdl`, no window-rule (another themed dmenu popup).
{ lib, self, ... }:
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

  # PLAN H1: which output the scratchpad terminal's workspace is pinned to —
  # ares' own declared primary (hosts/ares/outputs.nix), not a second guess
  # at which monitor that is.
  primaryOutput = lib.findFirst (o: o.primary or false) (throw ''
    modules/niri.nix pins the scratchpad terminal's workspace to the primary
    output, and hosts/ares/outputs.nix names none of its monitors
    `primary = true`.'') outputs;

  # The workspace + window-rule half of H1: both are "multipart" KDL nodes
  # (niri accepts any number of them), so they join the tail directly.
  scratchtermRule = ''
    workspace "jv-scratch" {
        open-on-output "${primaryOutput.name}"
    }

    window-rule {
        match app-id=r#"^jv-scratchterm$"#
        open-on-workspace "jv-scratch"
        open-floating true
        default-floating-position x=0 y=0 relative-to="top"
        default-window-height { proportion 0.5; }
        default-column-width { proportion 0.8; }
    }

    include "scratchterm-binds.kdl"
  '';

  # The keybind half of H1, in its own file: a second top-level `binds { }`
  # node in the SAME file is a hard niri parse error ("duplicate node
  # `binds`"), but niri merges one `binds { }` per INCLUDED file — see the
  # comment at the top of this module.
  scratchtermBinds = ''
    binds {
        Mod+Grave hotkey-overlay-title="Toggle the scratchpad terminal" { spawn "jv-scratchterm"; }
    }
  '';

  # PLAN H2: the power menu. It needs no window-rule/workspace of its own —
  # jv-power-menu is a themed dmenu popup, not a window niri has to place —
  # so its half of the tail is only the include line; the bind itself gets
  # its OWN included file for the same reason scratchtermBinds does (a
  # second top-level `binds { }` node in config.kdl is a hard parse error,
  # but each `include`d file gets its own single allowance).
  powerMenuRule = ''
    include "power-menu-binds.kdl"
  '';

  powerMenuBinds = ''
    binds {
        Mod+Shift+Escape hotkey-overlay-title="Power menu: lock / suspend / reboot / shut down" { spawn "jv-power-menu"; }
    }
  '';

  # PLAN H3: clipboard history. Same shape as H2 — no window-rule/workspace
  # (a dmenu popup, not a placed window), just its own include and bind file.
  clipboardRule = ''
    include "clipboard-binds.kdl"
  '';

  clipboardBinds = ''
    binds {
        Mod+Shift+C hotkey-overlay-title="Clipboard history" { spawn "jv-clip-menu"; }
    }
  '';
in
{
  # `spawn "jv-scratchterm"`/`spawn "jv-power-menu"`/`spawn "jv-clip-menu"`
  # (above) look the name up on PATH exactly the way config-base.kdl's own
  # `spawn "jv-lock"` does (modules/theme.nix puts jv-lock on PATH the same
  # way) — niri's `spawn` execs argv[0] via the environment it started in,
  # not a store path this module could pin into the KDL text itself.
  environment.systemPackages = [
    self.packages.x86_64-linux.jv-scratchterm
    self.packages.x86_64-linux.jv-power-menu
    self.packages.x86_64-linux.jv-clip-menu
  ];

  environment.etc."niri/config.kdl".text =
    builtins.replaceStrings
      [ "@@EMBER@@" "@@LINE@@" "@@WARN@@" "@@RISK@@" ]
      [ (token "ember") (token "line") (token "warn") (token "risk") ]
      (builtins.readFile ./niri/config-base.kdl)
    + lib.concatMapStrings outputStanza outputs
    + scratchtermRule
    + powerMenuRule
    + clipboardRule;

  environment.etc."niri/scratchterm-binds.kdl".text = scratchtermBinds;
  environment.etc."niri/power-menu-binds.kdl".text = powerMenuBinds;
  environment.etc."niri/clipboard-binds.kdl".text = clipboardBinds;
}
