# JarvisOS system theming — the desktop's look, declaratively (blueprint §06).
# Fonts live in modules/fonts.nix; this module owns everything else that makes
# ordinary apps and the session read as JarvisOS: GTK + Qt dark/ember, cursor
# and icon themes, the terminal + launcher palettes, and the wallpaper.
{ config, lib, pkgs, self, ... }:
let
  wallpaper = self.packages.x86_64-linux.jarvis-wallpaper;

  # Blueprint §06 tokens (kept in sync with personality/theme.toml).
  ground = "#090D12";
  panel = "#0C1116";
  ember = "#F0714A";
  ember2 = "#F79070";
  teal = "#4FB8BF";
  text = "#E6ECF0";
  muted = "#9BAAB4";
  faint = "#64747F";

  gtkSettings = ''
    [Settings]
    gtk-application-prefer-dark-theme=1
    gtk-theme-name=adw-gtk3-dark
    gtk-icon-theme-name=Papirus-Dark
    gtk-cursor-theme-name=Bibata-Modern-Ice
    gtk-cursor-theme-size=24
    gtk-font-name=Archivo 11
  '';
in
{
  environment.systemPackages = with pkgs; [
    swaybg # wallpaper
    adw-gtk3 # dark GTK theme (accent via GTK4/libadwaita)
    papirus-icon-theme
    bibata-cursors
  ];

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

  # Alacritty — the terminal in JarvisOS colours (Archivo has no mono; the
  # terminal stays JetBrains Mono, which the palette is designed around).
  environment.etc."xdg/alacritty/alacritty.toml".text = ''
    [font]
    normal = { family = "JetBrains Mono", style = "Regular" }
    size = 11.0

    [window]
    opacity = 0.96
    padding = { x = 14, y = 14 }

    [colors.primary]
    background = "${ground}"
    foreground = "${text}"

    [colors.cursor]
    cursor = "${ember}"
    text = "${ground}"

    [colors.normal]
    black   = "${panel}"
    red     = "${ember}"
    green   = "${teal}"
    yellow  = "${ember2}"
    blue    = "${teal}"
    magenta = "${ember2}"
    cyan    = "${teal}"
    white   = "${muted}"

    [colors.bright]
    black   = "${faint}"
    red     = "${ember2}"
    green   = "${teal}"
    yellow  = "${ember2}"
    blue    = "${teal}"
    magenta = "${ember2}"
    cyan    = "${teal}"
    white   = "${text}"
  '';

  # fuzzel launcher — JarvisOS palette, ember selection.
  environment.etc."xdg/fuzzel/fuzzel.ini".text = ''
    [main]
    font=Archivo:size=13
    icon-theme=Papirus-Dark
    prompt=">  "
    width=32
    lines=10
    horizontal-pad=24
    vertical-pad=18
    inner-pad=12

    [colors]
    background=${lib.removePrefix "#" panel}f2
    text=${lib.removePrefix "#" muted}ff
    match=${lib.removePrefix "#" ember}ff
    selection=${lib.removePrefix "#" ground}ff
    selection-text=${lib.removePrefix "#" text}ff
    selection-match=${lib.removePrefix "#" ember}ff
    border=${lib.removePrefix "#" ember}ff
    prompt=${lib.removePrefix "#" ember}ff

    [border]
    width=1
    radius=10
  '';
}
