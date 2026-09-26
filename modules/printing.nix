# Printing (PLAN G2) — CUPS was never declared: no print queues, no drivers,
# no way to find a printer on the LAN. Two services close the gap: CUPS
# itself with a broad driver set (the same trio nixpkgs' own module docs
# give as the "broad coverage" example, plus Brother's laser driver) and
# Avahi for mDNS, which is the whole story for discovery — cups-browsed
# (services.printing.browsed.enable) already defaults to
# `config.services.avahi.enable`, so turning avahi on is what makes CUPS
# see network/AirPrint printers announcing themselves over DNS-SD, no
# second switch needed.
{ pkgs, ... }:
{
  services.printing = {
    enable = true;
    drivers = with pkgs; [ gutenprint hplip splix brlaser ];
  };

  # mDNS resolution (*.local names) and the multicast traffic cups-browsed
  # listens on for printer announcements (_ipp._tcp, _printer._tcp). This
  # machine only needs to DISCOVER and print TO printers, not share its own
  # over the network, so openFirewall covers exactly the inbound traffic
  # mDNS itself needs (5353/udp) — no IPP port opened, since nothing here
  # answers incoming print jobs from other hosts.
  services.avahi = {
    enable = true;
    nssmdns4 = true;
    openFirewall = true;
  };
}
