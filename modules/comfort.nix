# Comfort basics (PLAN F2) — four small papercuts that were never declared:
# the screen never locked itself, sleep never asked for a password first,
# new folders never appeared under $HOME, the panels never warmed at night,
# and the firewall's only "on" was nixpkgs' own default rather than this
# flake's. None is big enough to earn its own module; they land together
# because they are the same kind of gap — "works on a hand-built desktop,
# was never written down here" (CLAUDE.md: if it isn't declared, it doesn't
# exist).
{ config, lib, pkgs, self, ... }:
let
  jv-lock = self.packages.x86_64-linux.jv-lock; # modules/theme.nix, PLAN D3

  # hosts/ares/default.nix already pins time.timeZone to Asia/Jerusalem;
  # wlsunset computes sunrise/sunset from these coordinates itself (no
  # geoclue, no network round-trip) — CLAUDE.md invariant 7, nothing but a
  # file hash is ever allowed to leave this machine, and a sunset lookup
  # would be a second thing that does.
  latitude = "31.7683";
  longitude = "35.2137";
in
{
  # Auto-lock on idle, and lock BEFORE sleep rather than after waking to an
  # already-unlocked screen. swayidle owns both timers; jv-lock is the one
  # screen it is allowed to raise (invariant 3 stops this file from raising
  # any other). `-w` makes swayidle wait for each command to exit before
  # continuing, which is what makes "before-sleep" actually block suspend
  # until the lock screen is up rather than racing it.
  systemd.user.services.jv-idle = {
    description = "Auto-lock on idle and before sleep (swayidle -> jv-lock)";
    unitConfig.ConditionUser = "ofek";
    wantedBy = [ "graphical-session.target" ];
    partOf = [ "graphical-session.target" ];
    after = [ "graphical-session.target" ];
    serviceConfig = {
      ExecStart = ''
        ${pkgs.swayidle}/bin/swayidle -w \
          timeout 300 '${jv-lock}/bin/jv-lock' \
          before-sleep '${jv-lock}/bin/jv-lock'
      '';
      Restart = "on-failure";
      RestartSec = 2;
    };
  };

  # Night light: warms the panels after sunset and cools them back at
  # sunrise, on the same clock the rest of the machine already keeps.
  systemd.user.services.jv-nightlight = {
    description = "Night light (wlsunset, Jerusalem sunrise/sunset)";
    unitConfig.ConditionUser = "ofek";
    wantedBy = [ "graphical-session.target" ];
    partOf = [ "graphical-session.target" ];
    after = [ "graphical-session.target" ];
    serviceConfig = {
      ExecStart = "${pkgs.wlsunset}/bin/wlsunset -l ${latitude} -L ${longitude}";
      Restart = "on-failure";
      RestartSec = 2;
    };
  };

  # XDG user directories (~/Desktop, ~/Downloads, ~/Documents, ...). There is
  # no home-manager on this machine (Track G10 is `[B]`, not adopted), so the
  # declared path is the package's own XDG-autostart entry rather than a
  # user-session unit hand-rolled here: `xdg.autostart` (nixpkgs default,
  # on) links every package's `etc/xdg/autostart/*.desktop` into
  # `/etc/xdg/autostart`, `modules/niri.nix`'s niri already
  # `Wants=`/`Before=` `xdg-desktop-autostart.target`, and
  # `systemd-xdg-autostart-generator` turns the .desktop entry into a run of
  # `xdg-user-dirs-update` at every login — the same mechanism GNOME and
  # Plasma use, just without either desktop attached to it.
  environment.systemPackages = [ pkgs.xdg-user-dirs ];

  # The firewall was already on — this is nixpkgs' own default — but an
  # inherited default is not a declaration, and CLAUDE.md's NixOS discipline
  # is explicit: if it isn't declared, it doesn't exist. Written here so a
  # future nixpkgs release changing that default changes ares only if this
  # line changes with it.
  networking.firewall.enable = true;
}
