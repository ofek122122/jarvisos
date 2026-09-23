#!/usr/bin/env bash
# ops/ralph/cargotest.sh <crate> [cargo args...] — run a Rust crate's tests
# against the WORKTREE source, fast, offline.
#
# `nix build .#jarvisd` does run cargo test in its checkPhase, but it copies the
# source into the store and rebuilds the world on every edit — far too slow for
# a red/green loop. This borrows the derivation's own build environment (cargo,
# rustc, and the vendored crate registry, so no network) and points cargo at a
# cached target dir outside the repo.
#
# Usage:  bash ops/ralph/cargotest.sh jarvisd
#         bash ops/ralph/cargotest.sh jarvisd --test cli
# NOTE: this is a fast INNER loop, not the gate. The gate is still
# `nix build .#jarvisd` + `nixos-rebuild build --flake .#ares`.
set -euo pipefail

crate="${1:?usage: cargotest.sh <crate> [cargo args...]}"; shift || true
root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
[ -d "$root/services/$crate" ] || { echo "no crate services/$crate"; exit 2; }

# jv-act is human-review-only (GUARDRAILS) but reading its tests is fine.
exec nix develop "$root#$crate" -c bash -euo pipefail -c '
  crate="$1"; root="$2"; shift 2
  home="$HOME/.cache/ralph-cargo"
  mkdir -p "$home/home"
  cat > "$home/home/config.toml" <<EOF
[source.crates-io]
replace-with = "vendored-sources"
[source.vendored-sources]
directory = "$cargoDeps"
EOF
  export CARGO_HOME="$home/home"
  export CARGO_TARGET_DIR="$home/target/$crate"
  cd "$root/services/$crate"
  exec cargo test --offline "$@"
' _ "$crate" "$root" "$@"
