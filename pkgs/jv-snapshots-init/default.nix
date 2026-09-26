# jv-snapshots-init — the one gap snapper's own NixOS module leaves on
# purpose (PLAN F3). Its manual is explicit: a config's SUBVOLUME "has to
# contain a subvolume named .snapshots", and nixpkgs' module comment on why it
# does not create one is "snapper/config-templates/default is only needed for
# create-config, which is not the NixOS way to configure" — so declaring a
# `services.snapper.configs` entry alone leaves `snapper-timeline.service`
# failing every hour against a path that has never existed.
#
# A FLAKE PACKAGE rather than an inline `pkgs.writeShellScript` in
# modules/snapshots.nix, for the reason `nixtest.sh` needs: a script embedded
# in a systemd unit's ExecStart is a plain STRING by the time an evaluation
# can see it (the derivation behind it was already coerced to its store path),
# and a string cannot be `nix build`-ed to read what it actually runs. Every
# other wrapper this repo tests this way — jv-lock, jv-wall — is a package for
# the same reason.
#
# No default for `subvolumes`: CLAUDE.md's NixOS discipline is "if it isn't
# declared, it doesn't exist", and disko.nix's own subvolumes (`@root` at "/",
# `@home` at "/home") are what modules/snapshots.nix passes in — a default
# here would be a second, silently agreeing copy of that list.
{
  lib,
  writeShellApplication,
  btrfs-progs,
  subvolumes,
}:
writeShellApplication {
  name = "jv-snapshots-init";

  runtimeInputs = [ btrfs-progs ];

  text = ''
    ${lib.concatMapStringsSep "\n" (subvolume: ''
      target="${subvolume}"
      target="''${target%/}/.snapshots"
      # Idempotent: a oneshot that unconditionally `create`s fails outright
      # (EEXIST) on every boot after the first, which would take
      # snapper-timeline/-cleanup/-boot down with it (they order themselves
      # after this unit finishing, not merely starting).
      if ! btrfs subvolume show "$target" >/dev/null 2>&1; then
        btrfs subvolume create "$target"
      fi
    '') subvolumes}
  '';

  meta = {
    description = "Create snapper's .snapshots subvolumes (PLAN F3)";
    mainProgram = "jv-snapshots-init";
  };
}
