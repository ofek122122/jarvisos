# The btrfs subvolumes disko.nix declares for ares that snapper needs to know
# about (PLAN F3) — `@root` at "/" and `@home` at "/home"; `@nix` and `@log`
# are deliberately absent (the Nix store regenerates from derivations, and
# log churn is exactly what a snapshot timeline should not be paying to keep).
#
# A plain file, imported by both flake.nix (to build pkgs/jv-snapshots-init,
# which needs the list at the PACKAGE level to be `nix build`-able and
# testable on its own — see that package's own comment) and
# modules/snapshots.nix (to build `services.snapper.configs`), so the two
# spend one declaration instead of agreeing by hand — the same shape
# hosts/ares/outputs.nix already is for the monitor layout (PLAN E10).
{
  root = "/";
  home = "/home";
}
