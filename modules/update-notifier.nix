# Update notifier (PLAN G3) — a login-time, read-only "you have updates"
# check. `pkgs/jv-update-notifier` does the only work this file wires: a
# `git fetch` (never a merge, checkout or nixos-rebuild) against the flake
# clone at /home/ofek/jarvisos, and a desktop notification through jv-notify
# (modules/theme.nix's org.freedesktop.Notifications daemon) if the tracked
# upstream has commits this checkout does not.
#
# Oneshot, wanted by graphical-session.target: it runs once per login, the
# same trigger G3 asks for, not a recurring timer — a background poll was not
# asked for and would be scope this file does not need.
{ self, ... }:
let
  jv-update-notifier = self.packages.x86_64-linux.jv-update-notifier;
in
{
  systemd.user.services.jv-update-notifier = {
    description = "Check for JarvisOS flake updates (read-only, PLAN G3)";
    unitConfig.ConditionUser = "ofek";
    wantedBy = [ "graphical-session.target" ];
    partOf = [ "graphical-session.target" ];
    after = [ "graphical-session.target" ];
    serviceConfig = {
      Type = "oneshot";
      ExecStart = "${jv-update-notifier}/bin/jv-update-notifier";
    };
  };
}
