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
        # The face personality/theme.toml names as family_sans. nixpkgs has
        # no `archivo`; see pkgs/archivo for why it is pinned upstream rather
        # than carved out of google-fonts. modules/fonts.nix installs it —
        # this output exists so it can be built and checked on its own.
        archivo = pkgs.callPackage ./pkgs/archivo { };
        jarvis-wallpaper = pkgs.callPackage ./pkgs/jarvis-wallpaper { };
        cuda-smoke = pkgs.callPackage ./pkgs/cuda-smoke { };
        jarvis-doctor = pkgs.callPackage ./pkgs/jarvis-doctor {
          cuda-smoke = self.packages.${system}.cuda-smoke;
        };
        default = self.packages.${system}.jarvis-doctor;
      };

      formatter.${system} = pkgs.nixfmt-rfc-style;
    };
}
