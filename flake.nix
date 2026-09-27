{
  description = "JarvisOS — a declared operating system with an assistant that remembers you";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    disko = {
      url = "github:nix-community/disko";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, disko }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs {
        inherit system;
        config.allowUnfree = true; # NVIDIA driver + CUDA
      };
      pyEnvs = import ./nix/jarvis-python.nix { inherit pkgs; };
    in
    {
      nixosConfigurations.ares = nixpkgs.lib.nixosSystem {
        inherit system;
        specialArgs = { inherit self; };
        modules = [
          disko.nixosModules.disko
          ./hosts/ares
        ];
      };

      packages.${system} = {
        jarvisd = pkgs.rustPlatform.buildRustPackage {
          pname = "jarvisd";
          version = "0.1.0";
          src = ./services/jarvisd;
          cargoLock.lockFile = ./services/jarvisd/Cargo.lock;
          meta.mainProgram = "jarvisd";
        };
        # jv-act — the privileged service. REVIEW-PASSED 2026-08-22.
        # It depends on the jarvisd crate as its bus library (path dep
        # ../jarvisd), so src is services/ (both crates as siblings) and
        # we build the jv-act subdir.
        jv-act = pkgs.rustPlatform.buildRustPackage {
          pname = "jv-act";
          version = "0.1.0";
          src = ./services;
          # The crate + its Cargo.lock live in services/jv-act; src stays
          # services/ so the ../jarvisd path dep resolves. cargoRoot finds
          # the Cargo.lock, buildAndTestSubdir runs cargo there. Needing
          # BOTH was caught by the VM build (each alone fails a different
          # phase).
          cargoRoot = "jv-act";
          buildAndTestSubdir = "jv-act";
          cargoLock.lockFile = ./services/jv-act/Cargo.lock;
          meta.mainProgram = "jv-act";
        };
        # jv-hud — the Quickshell/QML HUD (blueprint §06). Pure QML in the
        # store plus a wrapped quickshell; its check phase is qmllint, so a
        # HUD that does not parse cannot reach a `nixos-rebuild build`.
        jv-hud = pkgs.callPackage ./pkgs/jv-hud {
          # The bridge is pinned into the wrapper, not looked up on PATH:
          # the HUD's view of the bus is exactly the one the flake declares.
          hudBridge = pyEnvs.hudBridgeEnv;
        };
        # jv-bar — the top bar (blueprint §06, PLAN D1). Same shape as jv-hud:
        # the QML in the store plus a wrapped quickshell, with qmllint and the
        # headless bar tests as its check phase.
        # `niri` comes in as an ordinary callPackage argument: the bar's one
        # window onto the compositor is `niri msg --json event-stream`, pinned
        # into the wrapper rather than found on PATH, the same rule the HUD's
        # bridge follows. modules/desktop.nix runs that same `pkgs.niri`.
        jv-bar = pkgs.callPackage ./pkgs/jv-bar { };
        # jv-notify-sound — PLAN G8's one arrival chime, rendered from
        # arithmetic at build time (no binary blob), the same discipline
        # jarvis-wallpaper uses for the desktop art.
        jv-notify-sound = pkgs.callPackage ./pkgs/jv-notify-sound { };
        # jv-notify — the notification corner (blueprint §06, PLAN D2), and
        # this machine's org.freedesktop.Notifications daemon. Same shape as
        # the other two shells: the QML in the store plus a wrapped
        # quickshell, with qmllint and the headless notifier tests as its
        # check phase. Its own input is only the session bus; the one thing
        # pinned into its wrapper is PLAN G8's arrival chime (`pw-play` plus
        # `jv-notify-sound`'s generated .wav), the same "pin the store path,
        # never trust $PATH" rule `jv-bar` follows for `niri`.
        jv-notify = pkgs.callPackage ./pkgs/jv-notify {
          jv-notify-sound = self.packages.${system}.jv-notify-sound;
        };
        # jv-lock — the lock screen (blueprint §06, PLAN D3), and the one
        # surface here that is NOT a Quickshell shell: it is
        # swaylock-effects with its whole argv fixed at build time, because
        # swaylock's own config search path ends in the user's home or in
        # the sysconfdir of its own store path — neither of which this flake
        # can declare. The wallpaper comes in as an ordinary argument, the
        # same way the bar takes `niri` and the HUD takes its bridge: the
        # image the lock screen shows is the one the desktop already shows,
        # pinned, rather than a file looked up at runtime.
        jv-lock = pkgs.callPackage ./pkgs/jv-lock {
          inherit (self.packages.${system}) jarvis-wallpaper;
        };
        # The face personality/theme.toml names as family_sans. nixpkgs has
        # no `archivo`; see pkgs/archivo for why it is pinned upstream rather
        # than carved out of google-fonts. modules/fonts.nix installs it —
        # this output exists so it can be built and checked on its own.
        archivo = pkgs.callPackage ./pkgs/archivo { };
        # jarvis-wallpaper — the art, composed once per output THIS HOST
        # declares (PLAN E10). The geometry list used to live inside the
        # package: five sizes, three of which no monitor here can display, and
        # a real one plugged in tomorrow would have got the primary art scaled.
        # It is an argument now, and `hosts/ares/outputs.nix` is where the
        # answer lives — the same file PLAN E5 will hand to niri, so the
        # machine's layout is declared in one place and spent in several.
        jarvis-wallpaper = pkgs.callPackage ./pkgs/jarvis-wallpaper {
          outputs = import ./hosts/ares/outputs.nix;
        };
        # …and the same art composed for the contact sheet's own outputs, which
        # are ares' plus one 21:9 canvas no panel here has: `ops/ralph/
        # wallshots.sh` photographs a composed non-16:9 render, and that shot
        # (docs/wall/06-ultrawide.png) is the only evidence in this repo that
        # PLAN E9's composer works off 16:9. Building it here rather than
        # keeping the geometry in the machine's own art is the difference
        # between a desktop that carries renders for monitors it does not have
        # and a documentation gate that asks for what it photographs.
        jarvis-wallpaper-sheet = pkgs.callPackage ./pkgs/jarvis-wallpaper {
          outputs = import ./tools/wallshots/outputs.nix;
        };
        # jv-wall — the animated wallpaper; same pinned-launcher shape as
        # jv-hud/jv-bar, with the per-output renders pinned into its wrapper.
        jv-wall = pkgs.callPackage ./pkgs/jv-wall {
          jarvis-wallpaper = self.packages.${system}.jarvis-wallpaper;
        };
        cuda-smoke = pkgs.callPackage ./pkgs/cuda-smoke { };
        # jarvis-doctor — the Phase 0 verifier. Its monitor check is generated
        # from the same declaration the wallpaper composes for (PLAN E13), so
        # "the machine is the machine this flake declares" is one list checked
        # two ways and not two lists that agree today.
        jarvis-doctor = pkgs.callPackage ./pkgs/jarvis-doctor {
          outputs = import ./hosts/ares/outputs.nix;
          cuda-smoke = self.packages.${system}.cuda-smoke;
        };
        # jv-snapshot-restore — the one-command restore half of PLAN F3
        # (modules/snapshots.nix declares the snapper timeline it restores
        # from).
        jv-snapshot-restore = pkgs.callPackage ./pkgs/jv-snapshot-restore { };
        # jv-snapshots-init — the other half of PLAN F3: creates the
        # `.snapshots` subvolume snapper's own module expects to already
        # exist, for every subvolume hosts/ares/subvolumes.nix declares.
        jv-snapshots-init = pkgs.callPackage ./pkgs/jv-snapshots-init {
          subvolumes = builtins.attrValues (import ./hosts/ares/subvolumes.nix);
        };
        # jv-update-notifier — the login-time "you have updates" check (PLAN
        # G3): a read-only `git fetch` plus a notification, never a rebuild
        # (modules/update-notifier.nix wires it to run once per login).
        jv-update-notifier = pkgs.callPackage ./pkgs/jv-update-notifier { };
        # jv-disk-space-warning — PLAN G4: a `df`-on-a-timer check that warns
        # once per crossing when the disk holding /nix/store gets full
        # (modules/disk-space-warning.nix wires the timer).
        jv-disk-space-warning = pkgs.callPackage ./pkgs/jv-disk-space-warning { };
        # jv-scratchterm — PLAN H1: the drop-down scratchpad terminal's
        # toggle (modules/niri.nix wires its window-rule/workspace/keybind).
        jv-scratchterm = pkgs.callPackage ./pkgs/jv-scratchterm { };
        # jv-power-menu — PLAN H2: lock/suspend/reboot/shut-down, one themed
        # dmenu pick (modules/niri.nix wires its keybind). Reuses jv-lock
        # rather than a second lock mechanism of its own.
        jv-power-menu = pkgs.callPackage ./pkgs/jv-power-menu {
          inherit (self.packages.${system}) jv-lock;
        };
        # jv-clip-menu — PLAN H3: clipboard history, the first "super-menu
        # mode" — a themed dmenu pick over cliphist's own history
        # (modules/clipboard.nix runs the store daemons; modules/niri.nix
        # wires the keybind).
        jv-clip-menu = pkgs.callPackage ./pkgs/jv-clip-menu { };
        # jv-emoji-menu — PLAN H3b: emoji picker, the second "super-menu
        # mode" — a themed dmenu pick over a curated emoji table baked into
        # the derivation (modules/niri.nix wires the keybind; no daemon,
        # unlike H3a, since an emoji is a fixed table, not an observed
        # history).
        jv-emoji-menu = pkgs.callPackage ./pkgs/jv-emoji-menu { };
        default = self.packages.${system}.jarvis-doctor;
      };

      formatter.${system} = pkgs.nixfmt-rfc-style;
    };
}
