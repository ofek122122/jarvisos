# VPN support (PLAN G7b, split out of G7 — SSH/VPN/Syncthing were one item;
# this is the middle slice). Nothing here opens a server or picks a peer:
# `networking.networkmanager.enable` (hosts/ares/default.nix) is already on,
# and `networkmanagerapplet` (modules/apps.nix) already gives a human a GUI
# to add a connection through — what was missing is the protocol support
# NetworkManager needs before that GUI (or `nmcli`) can offer OpenVPN and
# OpenConnect at all. A real endpoint + keys/credentials are Ofek's own to
# add through nm-applet/nmcli once this lands; this file adds no
# `networking.wireguard.interfaces` or VPN connection profile of any kind.
{ pkgs, ... }:
{
  # OpenVPN and OpenConnect (Cisco AnyConnect / GlobalProtect-style SSL VPNs)
  # are NetworkManager VPN PLUGINS — separate packages NM loads at runtime —
  # so without this list neither protocol appears as an option in nm-applet
  # no matter how the connection is configured. WireGuard needs no plugin
  # here: it has been a native NetworkManager device type since 1.16 (this
  # machine's NetworkManager package already ships
  # `org.freedesktop.NetworkManager.Device.WireGuard.xml`), so nm-applet and
  # `nmcli` already offer it; `wireguard-tools` below is only the `wg`/
  # `wg-quick` CLI for generating/inspecting keys by hand.
  networking.networkmanager.plugins = with pkgs; [
    networkmanager-openvpn
    networkmanager-openconnect
  ];

  environment.systemPackages = [ pkgs.wireguard-tools ];
}
