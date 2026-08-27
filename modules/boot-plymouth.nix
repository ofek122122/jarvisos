# Plymouth boot splash — the animated JarvisOS sequence AFTER GRUB hands
# off, covering kernel init through to greetd. This is the layer that can
# actually move (GRUB cannot). It also owns the graphical LUKS passphrase
# prompt (root is LUKS2, asked at every boot — see hosts/ares/disko.nix).
#
# Deliberately NOT switching to systemd-initrd: this enables Plymouth on
# the existing legacy initrd to keep the change small and the unlock path
# familiar. If the passphrase prompt isn't drawn graphically, typing it
# still unlocks, and the previous generation (no Plymouth) is one GRUB
# submenu away — press ESC during the splash to drop to text.
{ pkgs, ... }:
let
  jarvisPlymouth = pkgs.callPackage ./plymouth-theme { };
in
{
  boot.plymouth = {
    enable = true;
    themePackages = [ jarvisPlymouth ];
    theme = "jarvis";
  };

  # A clean splash: hush the kernel/udev chatter, hide the console cursor.
  # loglevel=3 still lets real errors through.
  boot.kernelParams = [
    "quiet"
    "splash"
    "loglevel=3"
    "rd.udev.log_level=3"
    "vt.global_cursor_default=0"
  ];
  boot.initrd.verbose = false;
  boot.consoleLogLevel = 3;
}
