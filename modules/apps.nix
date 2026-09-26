# The applications JarvisOS ships with, and the plumbing that makes a desktop
# feel like a desktop: portals (file pickers, screen share), MIME defaults,
# thumbnails, a keyring, mounting, and an app menu with real icons.
#
# Everything here is DECLARED (CLAUDE.md: if it isn't declared, it doesn't
# exist). jv-store (modules/store.nix) adds to `jarvis.apps.extra` rather than
# installing imperatively, so a click in the store still ends up in the flake.
{ config, lib, pkgs, ... }:
let
  cfg = config.jarvis.apps;
in
{
  options.jarvis.apps.extra = lib.mkOption {
    type = lib.types.listOf lib.types.package;
    default = [ ];
    description = ''
      Applications added through the JarvisOS store (jv-store writes this list
      into a generated nix file that this option reads). Declared like
      everything else — the store is a friendly front-end to the flake, never
      an imperative installer.
    '';
  };

  config = {
    # ---------------------------------------------------------------- portals
    # Without these, "Open File" in a Wayland app silently does nothing, which
    # is the single biggest "this desktop feels broken" bug.
    xdg.portal = {
      enable = true;
      extraPortals = [ pkgs.xdg-desktop-portal-gtk ];
      config.common.default = [ "gtk" ];
      xdgOpenUsePortal = true;
    };

    # Thumbnails in the file manager, trash/mount support, MIME + icon lookup.
    # gvfs is deliberately NOT enabled: nixpkgs' gvfs module force-enables
    # udisks2, and modules/security.nix disables udisks2 on purpose — an
    # automounter would be free to mount the Windows NVMe or the off-limits
    # 2 TB disk, both permanently out of scope (CLAUDE.md). The cost is that
    # Nautilus has no trash/network-mount integration; the safety rule wins.
    # Removable media is mounted deliberately instead.
    services.tumbler.enable = true; # thumbnails
    programs.dconf.enable = true; # GTK apps remember settings
    security.pam.services.greetd.enableGnomeKeyring = lib.mkDefault true;
    services.gnome.gnome-keyring.enable = true; # apps can store secrets

    # Fonts a real desktop needs (emoji in chat apps, CJK in web pages).
    fonts.packages = with pkgs; [
      noto-fonts
      noto-fonts-cjk-sans
      noto-fonts-color-emoji
      liberation_ttf
      dejavu_fonts
      font-awesome
    ];

    environment.systemPackages =
      with pkgs;
      [
        # ---- everyday essentials -----------------------------------------
        nautilus # file manager (GTK, portal-aware)
        loupe # image viewer
        mpv # video/media player
        celluloid # GTK front-end for mpv
        gnome-text-editor # simple editor
        papers # PDF viewer
        file-roller # archives
        gnome-disk-utility
        baobab # disk usage
        grim
        slurp
        satty # screenshot + annotate
        wf-recorder # screen recording
        wl-clipboard
        gnome-system-monitor
        pavucontrol # audio mixer GUI
        networkmanagerapplet

        # ---- productivity --------------------------------------------------
        libreoffice-fresh
        gnome-calculator
        gnome-calendar
        gnome-contacts
        obsidian # notes
        evolution # mail/calendar
        zathura # keyboard-driven PDF

        # ---- media & creative ----------------------------------------------
        gimp # raster
        inkscape # vector
        krita # painting
        obs-studio # streaming/recording
        audacity # audio editing
        blender # 3D
        darktable # photo RAW
        shotcut # video editing
        rhythmbox # music library
        easyeffects # audio FX

        # ---- dev tools -------------------------------------------------------
        vscode
        neovim
        helix
        lazygit
        gitui
        tig
        jq # JSON (also fixes the status line's old dependency)
        yq
        ripgrep
        fd
        bat
        eza
        fzf
        zoxide
        tldr
        httpie
        curl
        wget
        tree
        ncdu
        btop
        dust
        procs
        hyperfine
        tokei
        direnv
        nix-tree
        nix-output-monitor
        nixpkgs-fmt
        nil # nix LSP
        shellcheck
        gcc
        gnumake
        python3
        nodejs
        rustup
        go

        # ---- web / comms -----------------------------------------------------
        chromium
        thunderbird
        telegram-desktop
        signal-desktop
        discord
        element-desktop

        # ---- system / utilities ----------------------------------------------
        gparted
        usbutils
        pciutils
        lm_sensors
        smartmontools
        p7zip
        unzip
        zip
        rsync
        wev # wayland event viewer (debugging input)
        wlr-randr
      ]
      ++ cfg.extra;
  };
}
