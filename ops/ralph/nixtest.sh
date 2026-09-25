#!/usr/bin/env bash
# ops/ralph/nixtest.sh — assert what the flake's own OPTIONS do to the units
# that ares actually gets.
#
# The sibling of runtests.sh (Python), cargotest.sh (Rust) and qmltest.sh (QML),
# for the layer none of them can reach: a module option is not code any of those
# suites import, it is an argument to a NixOS evaluation. Every check here reads
# the GENERATED UNIT TEXT — the bytes systemd is handed — and not the attrset the
# module wrote, so a check cannot pass because of how the option happens to be
# expressed (a null `environment` entry, for one, is absent from the unit but
# present in the attrset).
#
# Fast: each case is one `nix eval` of an `extendModules`-overridden ares, ~2 s
# against a warm eval cache — 22 s for the file. That is cheap enough to be
# BOUND rather than recommended, so `ops/ralph/verify.sh` runs it whenever the
# evaluation it reads has changed underneath it (PLAN B72).
#
# reads: flake.lock flake.nix hosts/ares modules nix pkgs
#
# Declared, because it cannot be derived: the subject of every case below is
# the flake attribute `.#nixosConfigurations.ares`, and an attribute names no
# path that any reader of this file could walk. `flake.nix` assembles that
# configuration out of `hosts/ares`, `modules`, `pkgs` and `nix`, and
# `flake.lock` decides which nixpkgs all of it is evaluated against. NOT
# `services`: a service's source moves a store path inside an ExecStart and
# nothing asserted here. The same list is in `DECLARED_GATES` in
# tools/dependents.py, and tools/tests/test_dependents.py holds the two equal.
set -uo pipefail

root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
cd "$root"

pass=0; fail=0
ok()   { pass=$((pass+1)); printf '  ok   %s\n' "$1"; }
bad()  { fail=$((fail+1)); printf '  FAIL %s\n       %s\n' "$1" "$2"; }

# A refused evaluation prints an error where the unit text should be, and an
# error contains no environment variable either — so every "the variable is
# absent" check must first prove it is looking at a unit at all. Without this
# the whole file passes on a flake that never declared the option.
is_unit() { grep -q '^\[Service\]$' <<<"$1"; }

# unit <unit-name> <extra-module-nix> — the generated unit text, or "" + stderr
# on an evaluation that refused to produce one.
unit() {
  nix eval --raw '.#nixosConfigurations.ares' --apply \
    "(c: (c.extendModules { modules = [ $2 ]; }).config.systemd.user.units.\"$1\".text)" \
    2>&1
}

# ---------------------------------------------------------------- the knob
# PLAN A46 / A41: jv-voice honours JARVIS_VOICE_OUTPUT_DEVICE, and until this
# option existed the only way to set it was editing a unit by hand — the
# imperative mutation the NixOS discipline forbids.

DEV='alsa_output.usb-Focusrite_Scarlett_2i2'

t='unpinned by default: no unit names an output device'
out=$(unit jv-voice.service '')
if ! is_unit "$out"; then bad "$t" "not a unit: $(tail -3 <<<"$out")"
elif grep -q 'JARVIS_VOICE_OUTPUT_DEVICE' <<<"$out"; then
  bad "$t" "$(grep JARVIS_VOICE_OUTPUT_DEVICE <<<"$out")"
else ok "$t"; fi

t='a declared device reaches jv-voice as its environment variable'
out=$(unit jv-voice.service "{ jarvis.voice.outputDevice = \"$DEV\"; }")
if grep -qF "Environment=\"JARVIS_VOICE_OUTPUT_DEVICE=$DEV\"" <<<"$out"; then ok "$t"
else bad "$t" "$(tail -3 <<<"$out")"; fi

t='a declared device reaches ONLY jv-voice'
for u in jv-ears.service jv-context.service jv-hud.service jv-act.service; do
  out=$(unit "$u" "{ jarvis.voice.outputDevice = \"$DEV\"; }")
  if ! is_unit "$out"; then bad "$t" "$u is not a unit: $(tail -3 <<<"$out")"; break
  elif grep -q 'JARVIS_VOICE_OUTPUT_DEVICE' <<<"$out"; then
    bad "$t" "$u carries it: $(grep JARVIS_VOICE_OUTPUT_DEVICE <<<"$out")"; break
  fi
  [ "$u" = jv-act.service ] && ok "$t"
done

t='an explicit null is the same as saying nothing'
out=$(unit jv-voice.service '{ jarvis.voice.outputDevice = null; }')
if ! is_unit "$out"; then bad "$t" "not a unit: $(tail -3 <<<"$out")"
elif grep -q 'JARVIS_VOICE_OUTPUT_DEVICE' <<<"$out"; then
  bad "$t" "$(grep JARVIS_VOICE_OUTPUT_DEVICE <<<"$out")"
else ok "$t"; fi

t='the option is typed: a device that is not a string is refused'
out=$(unit jv-voice.service '{ jarvis.voice.outputDevice = 44100; }')
# The refusal has to come from THIS option, by name. Any old refusal is not
# evidence: an undeclared option rejects a number, and so does the systemd
# module downstream if the value is passed through untyped — both of which
# would leave `jarvis.voice.outputDevice` with no type of its own.
if grep -q "jarvis.voice.outputDevice' is not of type" <<<"$out"; then ok "$t"
else bad "$t" "not a type error from the option itself: $(tail -3 <<<"$out")"; fi

# The empty string is the one value that would make the config LIE: jv-voice
# reads an empty variable as unset (services/jv-voice/jv_voice/config.py), so a
# machine declaring `outputDevice = ""` would publish output_device_pinned=false
# while its own configuration says a device is pinned, and the HUD's OutputPlate
# would go on trusting a default sink nobody promised. Refuse it at build time.
t='the empty string is refused, loudly, by name'
out=$(nix eval --raw '.#nixosConfigurations.ares' --apply \
  '(c: builtins.concatStringsSep "\n" (map (a: a.message)
       (builtins.filter (a: !a.assertion)
         (c.extendModules { modules = [ { jarvis.voice.outputDevice = ""; } ]; }).config.assertions)))' 2>&1)
if grep -q 'jarvis.voice.outputDevice' <<<"$out"; then ok "$t"
else bad "$t" "no failing assertion names the option: $(tail -3 <<<"$out")"; fi

t='...and that refusal stops a build, not just an attrset'
out=$(nix eval --raw '.#nixosConfigurations.ares' --apply \
  '(c: (c.extendModules { modules = [ { jarvis.voice.outputDevice = ""; } ]; }).config.system.build.toplevel.drvPath)' 2>&1)
if grep -q 'jarvis.voice.outputDevice' <<<"$out"; then ok "$t"
else bad "$t" "toplevel evaluated anyway: $(tail -3 <<<"$out")"; fi

printf '\n%d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
