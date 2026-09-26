# Syncthing (PLAN G7c) — the last slice split out of G7 (SSH/VPN/Syncthing
# were one item). `services.syncthing.enable` runs it as a system service
# under the real `ofek` user rather than nixpkgs' own module's dedicated
# `syncthing` user: that module only auto-creates a user/home
# (`users.users.syncthing`, `createHome = true`) when `cfg.user ==
# defaultUser`, so setting `user = "ofek"` here skips that path entirely and
# points `dataDir` at a folder in Ofek's own home instead — Syncthing creates
# that folder itself on first start, the same way it creates `configDir`
# under it, since it already has write access to its own home. `group =
# "users"` is declared explicitly rather than left at the module's default
# (a dedicated `syncthing` group) so files Syncthing writes land in Ofek's
# own primary group, not a group he isn't a member of.
#
# Which folders sync and with which remote devices is Ofek's own decision at
# run time through Syncthing's own web GUI — `guiAddress` defaults to
# 127.0.0.1:8384 (nothing here opens it past localhost), and no
# `services.syncthing.folders`/`devices`/`openDefaultPorts` is declared, same
# as G7a left the SSH key and G7b left the VPN endpoint to him.
{ ... }:
{
  services.syncthing = {
    enable = true;
    user = "ofek";
    group = "users";
    dataDir = "/home/ofek/Sync";
  };
}
