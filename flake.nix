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
        # jv-notify — the notification corner (blueprint §06, PLAN D2), and
        # this machine's org.freedesktop.Notifications daemon. Same shape as
        # the other two shells: the QML in the store plus a wrapped
        # quickshell, with qmllint and the headless notifier tests as its
        # check phase. It takes no extra argument at all — the daemon runs no
        # child process and reads no file, only the session bus.
        jv-notify = pkgs.callPackage ./pkgs/jv-notify { };
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
        jarvis-doctor = pkgs.callPackage ./pkgs/jarvis-doctor {
          cuda-smoke = self.packages.${system}.cuda-smoke;
        };
        default = self.packages.${system}.jarvis-doctor;
      };

      formatter.${system} = pkgs.nixfmt-rfc-style;
    };
}
