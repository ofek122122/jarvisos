# JarvisOS system theming — the desktop's look, declaratively (blueprint §06).
# Fonts live in modules/fonts.nix; this module owns everything else that makes
# ordinary apps and the session read as JarvisOS: GTK + Qt dark/ember, cursor
# and icon themes, and the terminal + launcher palettes. Two graphical-session
# surfaces have their units here: the wallpaper (colours in
# pkgs/jarvis-wallpaper), the top bar (QML in shell/jv-bar) and the
# notification corner (QML in shell/jv-notify).
#
# The PALETTE IS NOT WRITTEN HERE. It is read out of `personality/theme.toml`
# with `builtins.fromTOML`, the way modules/fonts.nix reads the font families
# and `tools/gen_theme_qml.py` reads the whole file for the HUD. theme.toml
# says it is "the ONLY place a colour exists", and until this module that was
# true of the HUD and false of the desktop: this file carried a hand-copied
# palette under a "kept in sync" comment, and it had already drifted — the
# terminal and the launcher were painting text in #E6ECF0 / #9BAAB4 / #64747F,
# three colours that appear nowhere in blueprint §06 (#E4EAEE / #9FADB7 /
# #6E7E89), plus #F79070, which is not a token at all. That is the exact shape
# modules/fonts.nix was written to prevent for faces: nothing fails, the
# identity just quietly becomes a lookalike of itself. A tools gate now fails
# if any file under modules/ or pkgs/ grows a colour literal again.
#
# What lives here instead is the BINDING from a surface to the token it
# spends — which is a design decision, and belongs in the open.
{ config, lib, pkgs, self, ... }:
let
  wallpaper = self.packages.x86_64-linux.jarvis-wallpaper;
  jv-bar = self.packages.x86_64-linux.jv-bar;
  jv-notify = self.packages.x86_64-linux.jv-notify;

  theme = builtins.fromTOML (builtins.readFile ../personality/theme.toml);

  # Ask theme.toml for a token, and throw if it does not have it. A colour
  # that silently became "" would paint a surface black and pass every check.
  token =
    name:
    theme.palette.${name} or (throw ''
      modules/theme.nix spends the colour "${name}", and [palette] in
      personality/theme.toml does not have it. Either the token was renamed
      there (rename it here too — this is the desktop half of the same
      identity) or this module is asking for a colour §06 does not define.'');

  face =
    role:
    theme.type."family_${role}" or (throw ''
      modules/theme.nix sets a font for the role "${role}", and [type] in
      personality/theme.toml names no family_${role}. A face is identity
      (invariant 9): it is named there, bound to a package in
      modules/fonts.nix, and spent here.'');

  # --- the tokens this module spends, and what each one is for ------------
  #
  # §06's ground is the desktop's ground, and the wallpaper is painted in it.
  # `ground_deep` sits one step BELOW it — theme.toml calls it the HUD's own
  # plate — which is what makes a terminal read as a window lying on the
  # desktop rather than a hole cut in it. So: window grounds are deep, and
  # `ground` is the colour of the panel edges inside them.
  groundDeep = token "ground_deep";
  ground = token "ground";
  ember = token "ember";
  teal = token "teal";
  text = token "text";
  text2 = token "text_2";
  text3 = token "text_3";
  # §06 gives three hues and three status colours; ANSI wants sixteen slots.
  # The terminal therefore collapses (green, blue, cyan) onto teal, spends
  # `warn` on yellow — where caution is what yellow has always meant — and
  # `risk` on magenta and the bright reds. Every slot is a token; none of
  # them is a colour invented for the terminal.
  warn = token "warn";
  risk = token "risk";

  sansFamily = face "sans";
  monoFamily = face "mono";

  # fuzzel wants RRGGBBAA with no '#'.
  rgba = colour: alpha: (lib.removePrefix "#" colour) + alpha;

  gtkSettings = ''
    [Settings]
    gtk-application-prefer-dark-theme=1
    gtk-theme-name=adw-gtk3-dark
    gtk-icon-theme-name=Papirus-Dark
    gtk-cursor-theme-name=Bibata-Modern-Ice
    gtk-cursor-theme-size=24
    gtk-font-name=${sansFamily} 11
  '';
in
{
  environment.systemPackages = [
    jv-bar # the top bar, so it can also be started by hand while working on it
    jv-notify # the notification corner, for the same reason
  ]
  ++ (with pkgs; [
    swaybg # wallpaper
    adw-gtk3 # dark GTK theme (accent via GTK4/libadwaita)
    papirus-icon-theme
    bibata-cursors
  ]);

  # Qt follows the same dark identity as GTK.
  qt = {
    enable = true;
    platformTheme = "gnome";
    style = "adwaita-dark";
  };

  environment.variables = {
    GTK_THEME = "adw-gtk3-dark";
    XCURSOR_THEME = "Bibata-Modern-Ice";
    XCURSOR_SIZE = "24";
  };

  # GTK 3 + 4 dark, Papirus icons, Bibata cursor, Archivo UI — system default
  # for any user without their own overrides.
  environment.etc."xdg/gtk-3.0/settings.ini".text = gtkSettings;
  environment.etc."xdg/gtk-4.0/settings.ini".text = gtkSettings;

  # The wallpaper: swaybg, part of the graphical session (like jv-hud). Fills
  # every output; 0 cost once painted.
  systemd.user.services.jarvis-wallpaper = {
    description = "JarvisOS wallpaper";
    unitConfig.ConditionUser = "ofek";
    wantedBy = [ "graphical-session.target" ];
    partOf = [ "graphical-session.target" ];
    after = [ "graphical-session.target" ];
    serviceConfig = {
      ExecStart = "${pkgs.swaybg}/bin/swaybg -m fill -i ${wallpaper}/share/backgrounds/jarvisos.png";
      Restart = "on-failure";
      RestartSec = 2;
    };
  };

  # jv-bar — the top bar (blueprint §06, PLAN D1), the second Quickshell
  # surface on this machine and the first one that is resident. It lives here
  # rather than beside jv-hud in modules/jarvis-services.nix because it is
  # DESKTOP, not perception: it never opens the bus, never reads a sensor and
  # never needs commonEnv — its two sources are niri's event stream (pinned
  # into its wrapper, read-only) and the machine's clock.
  #
  # Unlike jv-hud it IS wanted by default, because it has something true to
  # say from the first frame: your workspaces and the time. The HUD is held
  # back for the opposite reason — an overlay with no signal yet is set
  # dressing — and both rules come from the same §06 sentence.
  #
  # `niri msg` finds the compositor through NIRI_SOCKET, which niri-session
  # exports into the user manager, so being part of the graphical session is
  # also what gives the bar its socket. Started before niri is up, it shows
  # no workspaces and retries — truthfully empty, never a guess.
  systemd.user.services.jv-bar = {
    description = "JarvisOS top bar (Quickshell layer-shell strip)";
    unitConfig.ConditionUser = "ofek";
    wantedBy = [ "graphical-session.target" ];
    partOf = [ "graphical-session.target" ];
    after = [ "graphical-session.target" ];
    serviceConfig = {
      ExecStart = "${jv-bar}/bin/jv-bar";
      Restart = "on-failure";
      RestartSec = 2;
    };
  };

  # jv-notify — the notification corner (blueprint §06, PLAN D2), and this
  # machine's org.freedesktop.Notifications daemon. Before it there was NO
  # notification daemon on ares at all: every app that asked the session bus
  # to show you something got an error, and you were never told.
  #
  # Here beside the bar rather than in modules/jarvis-services.nix, for the
  # same reason: it is DESKTOP, not perception. It never opens the bus, never
  # reads a sensor and never needs commonEnv — its one input is the session
  # bus, and what it draws is other programs' news. What Jarvis has to say
  # goes to jv-hud over the real bus (invariant 1), which is also why this
  # surface never spends the ember accent.
  #
  # Wanted by default, like the bar and unlike the HUD: a notification daemon
  # that was not running when an app went looking for one is a notification
  # nobody ever sees. The surface itself is still unmapped until something has
  # actually been sent.
  systemd.user.services.jv-notify = {
    description = "JarvisOS notification corner (org.freedesktop.Notifications)";
    unitConfig.ConditionUser = "ofek";
    wantedBy = [ "graphical-session.target" ];
    partOf = [ "graphical-session.target" ];
    after = [ "graphical-session.target" ];
    serviceConfig = {
      ExecStart = "${jv-notify}/bin/jv-notify";
      Restart = "on-failure";
      RestartSec = 2;
    };
  };

  # Alacritty — the terminal in JarvisOS colours (Archivo has no mono; the
  # terminal is family_mono, which the palette is designed around).
  environment.etc."xdg/alacritty/alacritty.toml".text = ''
    [font]
    normal = { family = "${monoFamily}", style = "Regular" }
    size = 11.0

    [window]
    opacity = 0.96
    padding = { x = 14, y = 14 }

    [colors.primary]
    background = "${groundDeep}"
    foreground = "${text}"

    [colors.cursor]
    cursor = "${ember}"
    text = "${groundDeep}"

    [colors.normal]
    black   = "${ground}"
    red     = "${ember}"
    green   = "${teal}"
    yellow  = "${warn}"
    blue    = "${teal}"
    magenta = "${risk}"
    cyan    = "${teal}"
    white   = "${text2}"

    [colors.bright]
    black   = "${text3}"
    red     = "${risk}"
    green   = "${teal}"
    yellow  = "${warn}"
    blue    = "${teal}"
    magenta = "${risk}"
    cyan    = "${teal}"
    white   = "${text}"
  '';

  # fuzzel launcher — JarvisOS palette, ember selection.
  environment.etc."xdg/fuzzel/fuzzel.ini".text = ''
    [main]
    font=${sansFamily}:size=13
    icon-theme=Papirus-Dark
    prompt=">  "
    width=32
    lines=10
    horizontal-pad=24
    vertical-pad=18
    inner-pad=12

    [colors]
    background=${rgba ground "f2"}
    text=${rgba text2 "ff"}
    match=${rgba ember "ff"}
    selection=${rgba groundDeep "ff"}
    selection-text=${rgba text "ff"}
    selection-match=${rgba ember "ff"}
    border=${rgba ember "ff"}
    prompt=${rgba ember "ff"}

    [border]
    width=1
    radius=10
  '';
}
