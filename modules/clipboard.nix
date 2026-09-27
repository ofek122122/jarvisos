# Clipboard history (PLAN H3) — the daemon half. `pkgs/jv-clip-menu` is the
# picker a keybind spawns (modules/niri.nix wires Mod+Shift+C to it); this
# module runs the two background watchers that actually fill cliphist's
# store, the same "one file per feature" shape modules/comfort.nix's
# jv-idle/jv-nightlight and modules/dictate.nix already use.
#
# TWO SERVICES, NOT ONE. cliphist's own docs recommend a `wl-paste --watch`
# per MIME class, because a single watcher only ever reports the one type it
# was started with — one for `--type text`, one for `--type image`, so a
# copied screenshot is captured exactly like a copied sentence rather than
# silently dropped.
{ pkgs, ... }:
let
  # writeShellApplication's PATH-pinning guarantee (the same reason
  # pkgs/jv-scratchterm gives for `runtimeInputs`) does not apply here — a
  # systemd ExecStart has no ambient PATH to shadow in the first place, so
  # the store paths are interpolated directly, the same way
  # modules/comfort.nix pins swayidle/wlsunset/jv-lock into jv-idle's own
  # ExecStart.
  cliphist = "${pkgs.cliphist}/bin/cliphist";
  wlPaste = "${pkgs.wl-clipboard}/bin/wl-paste";

  watcher = mimeType: {
    description = "Clipboard history: ${mimeType} (wl-paste --watch cliphist store)";
    unitConfig.ConditionUser = "ofek";
    wantedBy = [ "graphical-session.target" ];
    partOf = [ "graphical-session.target" ];
    after = [ "graphical-session.target" ];
    serviceConfig = {
      ExecStart = "${wlPaste} --type ${mimeType} --watch ${cliphist} store";
      Restart = "on-failure";
      RestartSec = 2;
    };
  };
in
{
  systemd.user.services.jv-clip-store-text = watcher "text";
  systemd.user.services.jv-clip-store-image = watcher "image";
}
