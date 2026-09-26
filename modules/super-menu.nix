# The Super key opens the app menu, the way it does on Windows.
#
# WHY THIS NEEDS A DAEMON. niri cannot bind a lone modifier — `Super { ... }`
# is rejected with "invalid key: Super", because a keybind needs a real key.
# So the tap has to become a key before the compositor can see it:
#
#   keyd (kernel-level, compositor-agnostic):
#     tap Super  -> F13   (a key no application uses)
#     hold Super -> Super (every existing Mod+… bind keeps working, untouched)
#   niri:
#     F13        -> the JarvisOS app menu
#
# The overlap rule is what makes this safe: keyd only emits F13 if Super went
# down and came back up with NOTHING pressed in between, so Mod+D, Mod+Q,
# Mod+Enter and friends behave exactly as before — this adds a gesture rather
# than taking one away.
{ config, lib, pkgs, ... }:
let
  theme = builtins.fromTOML (builtins.readFile ../personality/theme.toml);

  # The same helper modules/theme.nix and modules/fonts.nix use, for the same
  # reason: a face is identity (invariant 9), so it is named in
  # personality/theme.toml, bound to a package in modules/fonts.nix, and only
  # SPENT here. This menu is a second fuzzel instance beside the launcher in
  # modules/theme.nix, and a second config file is exactly where a face comes
  # to be spelled by hand and drift — it said `Archivo` until a tools gate
  # caught it.
  face =
    role:
    theme.type."family_${role}" or (throw ''
      modules/super-menu.nix sets a font for the role "${role}", and [type] in
      personality/theme.toml names no family_${role}.'');

  sansFamily = face "sans";
in
{
  # ---------------------------------------------------------------- the tap
  #
  # keyd needs two things the module does not give it on this system, and
  # WITHOUT EITHER IT FAILS SOFTLY — the daemon starts, logs one warning, and
  # simply never emits the remapped key (observed: "failed to set effective
  # group to keyd", and no virtual keyboard created). A silent no-op is the
  # worst shape for an input daemon, so both are declared here:
  #   1. the `keyd` group it drops privileges to, and
  #   2. membership of `uinput`, which owns /dev/uinput — the device it must
  #      open to create the virtual keyboard that carries F13.
  users.groups.keyd = { };
  systemd.services.keyd.serviceConfig = {
    SupplementaryGroups = [ "uinput" "input" ];
    # keyd setgid()s into the `keyd` group itself, and the module's hardened
    # CapabilityBoundingSet (CAP_SYS_NICE, CAP_IPC_LOCK) strips the capability
    # that needs — the daemon then dies with "setgid: Operation not permitted".
    # Add CAP_SETGID/CAP_SETUID to the bounding set rather than loosening the
    # rest of the sandbox.
    CapabilityBoundingSet = [
      "CAP_SYS_NICE"
      "CAP_IPC_LOCK"
      "CAP_SETGID"
      "CAP_SETUID"
    ];
    AmbientCapabilities = [ "CAP_SETGID" "CAP_SETUID" ];
  };

  services.keyd = {
    enable = true;
    keyboards.all = {
      ids = [ "*" ];
      settings = {
        main = {
          # `overload(layer, key)`: held -> the layer (the real Super modifier),
          # tapped -> the key. This is the whole mechanism.
          leftmeta = "overload(meta, f13)";
        };
      };
    };
  };

  # ------------------------------------------------------------- the menu
  # A full-screen application grid: every installed .desktop entry with its
  # real icon, searchable by typing. fuzzel already reads the desktop
  # database and the icon theme, so the "grid" is a wide, tall, icon-ful
  # instance of it — one config file, no new surface to maintain, and it
  # inherits the §06 palette from modules/theme.nix.
  #
  # PLAN E4 replaces this with a Quickshell grid; the KEY BINDING and the
  # keyd tap stay the same, so that swap is invisible to muscle memory.
  environment.etc."xdg/fuzzel/jarvis-menu.ini".text = ''
    [main]
    font=${sansFamily}:size=14
    icon-theme=Papirus-Dark
    terminal=alacritty -e
    prompt="  "
    # A grid, not a line: wide, many rows, large icons.
    width=64
    lines=16
    tabs=4
    horizontal-pad=40
    vertical-pad=32
    inner-pad=14
    image-size-ratio=1.0
    show-actions=yes
    match-mode=fzf
    sort-result=yes
    list-executables-in-path=yes

    [colors]
    # One step deeper than a window so the menu reads as lying OVER the
    # desktop; ember only on the selection and the match, as everywhere.
    background=0c1116f7
    text=9fadb7ff
    match=f0714aff
    selection=161d24ff
    selection-text=e4eaeeff
    selection-match=f0714aff
    border=f0714aff
    prompt=f0714aff

    [border]
    width=1
    radius=14
  '';

  environment.systemPackages = [
    # `jarvis-menu` is what the key is bound to — a named command, so the
    # binding never has to change when the menu implementation does.
    (pkgs.writeShellApplication {
      name = "jarvis-menu";
      runtimeInputs = [ pkgs.fuzzel ];
      text = ''
        # --config keeps the app grid separate from the plain Mod+D launcher.
        exec fuzzel --config /etc/xdg/fuzzel/jarvis-menu.ini "$@"
      '';
    })
  ];
}
