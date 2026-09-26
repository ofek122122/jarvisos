# SSH agent + client config (PLAN G7a, split out of G7 — SSH/VPN/Syncthing
# were one item; SSH is the smallest, purely-client, no-daemon-exposed slice,
# so it goes first). Nothing here opens `services.openssh` (this machine is
# not an SSH server) and nothing writes into $HOME.
#
# The agent half is ALREADY DONE, by a module that was not written for this:
# `modules/apps.nix` turns on `services.gnome.gnome-keyring.enable` (so apps
# can store secrets), and nixpkgs' own `gcr-ssh-agent` module defaults its
# `enable` to that same flag — so ares already runs a per-session SSH agent,
# `gcr-ssh-agent.socket`/`.service` (`systemctl --user status gcr-ssh-agent`),
# backed by the keyring rather than a bare `ssh-agent`, which is the more
# comfortable of the two: `ssh-add`ed keys can be unlocked once per login via
# the keyring prompt instead of once per key. `programs.ssh.startAgent` is
# nixpkgs' OTHER agent (a plain `ssh-agent.service`) and its own module
# refuses to evaluate at all if both are on at once ("only one SSH agent can
# be installed at a time") — so this file leaves it off, on purpose, rather
# than fighting the agent already running.
#
# What was actually missing is the client-comfort config, which is agent-
# agnostic: `programs.ssh.extraConfig` reaches the system-wide
# `/etc/ssh/ssh_config`, applying to every user with no dotfile to maintain.
{
  programs.ssh.extraConfig = ''
    # Any key an agent already holds (gcr-ssh-agent, above) is offered before
    # ssh asks for an identity file — the standard "don't make me type a
    # passphrase per shell" comfort ask.
    AddKeysToAgent yes
    # Detect a dead/asleep peer (a laptop suspend, a dropped Wi-Fi) rather
    # than hanging a terminal on a stale TCP connection.
    ServerAliveInterval 60
    ServerAliveCountMax 3
  '';
}
