# PLACEHOLDER — plausible for this board, but on install day you MUST:
#   nixos-generate-config --no-filesystems --root /mnt
# then diff the generated file against this one and audit every line
# before committing the result (BRIEF-phase0 task 1: "generated then
# audited"). Filesystems intentionally absent — disko.nix declares them.
{ modulesPath, ... }:
{
  imports = [ (modulesPath + "/installer/scan/not-detected.nix") ];

  boot.initrd.availableKernelModules = [
    "xhci_pci"
    "ahci"
    "nvme"
    "usbhid"
    "usb_storage"
    "sd_mod"
  ];
  boot.initrd.kernelModules = [ ];
  boot.kernelModules = [ "kvm-intel" ];
  boot.extraModulePackages = [ ];

  nixpkgs.hostPlatform = "x86_64-linux";
  hardware.cpu.intel.updateMicrocode = true;
  hardware.enableRedistributableFirmware = true;
}
