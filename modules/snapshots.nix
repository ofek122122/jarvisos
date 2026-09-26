# btrfs snapshots + rollback (PLAN F3). `hosts/ares/disko.nix` already lays
# `@root` and `@home` down as their own btrfs subvolumes — the comment there
# has said "subvolume snapshots cover /home" since Phase 0 — but nothing ever
# declared a snapshot policy, so until this file the promise was prose with
# nothing behind it: delete a file by mistake and it was gone.
#
# snapper over btrbk: snapper ships a NixOS module that turns declared config
# into systemd timers directly (no separate cron/timer file to also write),
# understands "undo the changes between two snapshots" as one verb
# (`undochange`) rather than a raw `btrfs send`, and is what
# `pkgs/jv-snapshot-restore` wraps for the "documented one-command restore"
# half of this item.
#
# WHY THIS FILE DOES NOT TOUCH hosts/ares/disko.nix. Snapper's manual is
# explicit: a config's SUBVOLUME "has to contain a subvolume named
# .snapshots" (services.snapper.configs.*.SUBVOLUME's own description,
# nixpkgs nixos/modules/services/misc/snapper.nix) — but disko.nix is on the
# GUARDRAILS list of files this loop may only propose changes to, and a
# `.snapshots` child subvolume is not a partition-table decision the way the
# four top-level subvolumes are. So it is created at boot instead, by a
# oneshot unit ordered before every unit that expects it to exist, the same
# way `xdg-user-dirs` (modules/comfort.nix) reaches into $HOME without disko
# ever declaring a directory inside it.
{ config, lib, pkgs, self, ... }:
let
  # A retention policy that "cannot fill the disk" is a policy that BOUNDS
  # the snapshot count, not one that promises free space — btrfs snapshots
  # are cheap (metadata + the extents that have since changed) but not free,
  # and an unbounded timeline on a 1 TB drive that also holds every model
  # jv-brain and jv-dream load is exactly the kind of slow leak CLAUDE.md's
  # "6 GB VRAM is a scheduling problem" instinct says to plan for on disk
  # too. These numbers cap each subvolume's timeline at 6 + 7 + 4 + 6 = 23
  # scheduled snapshots plus up to 20 more from manual/boot use — small
  # enough that `snapper-cleanup.timer` (already declared by the upstream
  # module once any config exists) keeps the count flat forever rather than
  # merely slowing its growth.
  retention = {
    TIMELINE_CREATE = true;
    TIMELINE_CLEANUP = true;
    TIMELINE_LIMIT_HOURLY = 6;
    TIMELINE_LIMIT_DAILY = 7;
    TIMELINE_LIMIT_WEEKLY = 4;
    TIMELINE_LIMIT_MONTHLY = 6;
    TIMELINE_LIMIT_YEARLY = 0;
    # Spent by manual snapshots and by snapper-boot's `--cleanup-algorithm
    # number` (below) — the "number" algorithm this bounds rather than the
    # timeline one above.
    NUMBER_LIMIT = 20;
    NUMBER_LIMIT_IMPORTANT = 5;
    # Ofek can list/create/undochange without sudo; root is always implicit.
    ALLOW_USERS = [ "ofek" ];
  };

  # The subvolume every config's SUBVOLUME points at, keyed the same way
  # `services.snapper.configs` is — imported from hosts/ares/subvolumes.nix
  # so this and pkgs/jv-snapshots-init (built in flake.nix) read one
  # declaration instead of two hand-kept ones drifting (PLAN E10 is the same
  # lesson for the monitor layout).
  subvolumes = import ../hosts/ares/subvolumes.nix;

  jv-snapshot-restore = self.packages.x86_64-linux.jv-snapshot-restore;
  jv-snapshots-init = self.packages.x86_64-linux.jv-snapshots-init;
in
{
  services.snapper.configs = lib.mapAttrs (_: subvolume: retention // { SUBVOLUME = subvolume; }) subvolumes;

  # A snapshot of / before every boot — the closest this machine gets to a
  # filesystem-level "undo the last session" for root, alongside (not instead
  # of) the NixOS generations GRUB already offers: a generation rolls back
  # what the FLAKE changed, this rolls back what THE USER changed under it
  # (a stray `rm -rf`, an app that wrote garbage into a dotfile outside $HOME
  # config that home-manager would otherwise own — G10 is `[B]`).
  services.snapper.snapshotRootOnBoot = true;

  # snapper's own NixOS module writes /etc/snapper/configs/{root,home} and
  # the timeline/cleanup timers the moment `services.snapper.configs != {}`
  # (nixos/modules/services/misc/snapper.nix) — this unit is only the one gap
  # that module deliberately leaves: ".snapshots has to exist, and snapper
  # does not create it" (the same file's own comment on why `create-config`
  # is "not the NixOS way"). pkgs/jv-snapshots-init is the package that runs;
  # see its own comment for why this is a package and not an inline script.
  systemd.services.jv-snapshots-init = {
    description = "Create snapper's .snapshots subvolumes (PLAN F3)";
    requires = [ "local-fs.target" ];
    after = [ "local-fs.target" ];
    wantedBy = [ "multi-user.target" ];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      ExecStart = "${jv-snapshots-init}/bin/jv-snapshots-init";
    };
  };

  # Every unit the upstream module produces that touches a snapshot must wait
  # for the subvolume it snapshots into to exist first. `snapper-boot` is
  # only defined at all when snapshotRootOnBoot is set, but naming it in a
  # list NixOS merges is harmless either way — a merge into an option nobody
  # else defines is simply that option's whole value.
  systemd.services.snapper-timeline = {
    requires = [ "jv-snapshots-init.service" ];
    after = [ "jv-snapshots-init.service" ];
  };
  systemd.services.snapper-cleanup = {
    requires = [ "jv-snapshots-init.service" ];
    after = [ "jv-snapshots-init.service" ];
  };
  systemd.services.snapper-boot = {
    requires = [ "jv-snapshots-init.service" ];
    after = [ "jv-snapshots-init.service" ];
  };

  environment.systemPackages = [ jv-snapshot-restore ];
}
