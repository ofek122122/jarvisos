# Disk-space warning (PLAN G4) — pkgs/jv-disk-space-warning read on a timer,
# so a slowly-filling store gets caught before it wedges a rebuild rather
# than after. A timer rather than a login-only oneshot (unlike G3's update
# check): disk usage grows DURING a session, not just between them, so
# checking only at login could miss the exact moment that matters.
#
# Tied to graphical-session.target, the same lifecycle jv-idle/jv-nightlight
# already use (modules/comfort.nix): the check needs a user session for
# notify-send to reach a screen, so it has no reason to run — or keep a timer
# alive — outside one.
{ self, ... }:
let
  jv-disk-space-warning = self.packages.x86_64-linux.jv-disk-space-warning;
in
{
  systemd.user.timers.jv-disk-space-warning = {
    description = "Periodic disk-space check (PLAN G4)";
    wantedBy = [ "graphical-session.target" ];
    partOf = [ "graphical-session.target" ];
    timerConfig = {
      OnStartupSec = "5m";
      OnUnitActiveSec = "30m";
    };
  };

  systemd.user.services.jv-disk-space-warning = {
    description = "Warn once per crossing when the store's disk gets full (PLAN G4)";
    unitConfig.ConditionUser = "ofek";
    serviceConfig = {
      Type = "oneshot";
      ExecStart = "${jv-disk-space-warning}/bin/jv-disk-space-warning";
    };
  };
}
