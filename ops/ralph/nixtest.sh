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
# It also asks two questions of a PACKAGE the evaluation produces rather than
# of a unit (PLAN D3): the lock screen's built argv, and the PAM stack it has
# to ask to let anybody back in. Both are still this layer — a store path is
# what a module option evaluated TO — and neither can be asked anywhere else:
# the Python suites run in a checkout with no nix, and nothing but an
# evaluation can hold the lock screen and the wallpaper unit side by side.
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

# Where the store is, asked of Nix rather than assumed (PLAN E12). The
# lock-screen section below matches store paths out of unit text and out of a
# built script, and a `grep -o` that matches nothing does not fail here — it
# returns the empty string, which each of those checks reads as a confident
# sentence about the flake ("the wallpaper unit does not start jv-wall"). On a
# relocated store a hardcoded /nix/store makes the gate say all of them.
store="${NIX_STORE_DIR:-/nix/store}"

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

# --------------------------------------------------------- the lock screen
# PLAN D3. pkgs/jv-lock is one wrapper whose whole argv is fixed at build
# time, and tools/tests/test_jv_lock.py reads that argv as TEXT — in a bare
# checkout, with no nix. What only an evaluation can ask is here: whether the
# thing that would actually run on ares says the same, whether it shows the
# same image as the desktop it covers, and whether there is a PAM stack for
# it to ask. The last one is the only question in this file whose wrong
# answer is a screen that never opens again.

lock=$(nix build --no-link --print-out-paths '.#jv-lock' 2>&1 | tail -1)
script="$lock/bin/jv-lock"

t='the lock screen builds, and what it ships is one script'
if [ -x "$script" ]; then ok "$t"
else bad "$t" "no jv-lock at $script ($lock)"; fi

# The refusals, in the BYTES rather than in the expression that produced
# them. A `lib.optional` whose condition flipped, an interpolation that
# evaluated to the wrong string, a flag appended by a wrapper: none of those
# are visible in the source and all of them are visible here.
if [ -x "$script" ]; then
  t='the built lock screen photographs nothing and grants no grace'
  spent=""
  for flag in --screenshots --effect-blur --effect-pixelate --effect-greyscale \
              --effect-compose --effect-custom --grace --daemonize; do
    grep -q -- "$flag" "$script" && spent="$spent $flag"
  done
  if [ -z "$spent" ]; then ok "$t"; else bad "$t" "the built argv spends:$spent"; fi

  t='the built lock screen forwards no arguments'
  if grep -q '"\$@"' "$script"; then bad "$t" "$(grep -n '"\$@"' "$script")"
  else ok "$t"; fi

  t='it is swaylock that runs, out of the store, not a name on $PATH'
  if grep -qE "^exec $store/[^ ]*swaylock" "$script"; then ok "$t"
  else bad "$t" "$(grep -m1 exec "$script")"; fi

  # The one claim neither half of the test suite can make alone: two
  # surfaces, two modules, one set of art. The lock screen shows a PNG, and if
  # it ever stops being art the desktop draws, the screen you lock stops being
  # the desktop you were looking at.
  #
  # ONE HOP LONGER THAN IT USED TO BE, because the wallpaper stopped being
  # swaybg. The unit handed swaybg the PNG on its command line, so the file was
  # in the ExecStart and this was a `grep` of one string against another. It now
  # starts `jv-wall`, a Quickshell shell that picks its own file PER OUTPUT out
  # of a directory `--set` into its wrapper — so the unit names no PNG at all,
  # and the honest question became "is the lock screen's image art THIS
  # wallpaper would draw" rather than "is it the same string". The directory is
  # read out of the built wrapper rather than out of pkgs/jv-wall, for the same
  # reason every other check here reads the built bytes: an interpolation that
  # evaluated to the wrong store path looks right in the source.
  t='the lock screen shows art the wallpaper unit would draw'
  wallpaper_unit=$(unit jarvis-wallpaper.service '')
  wall_bin=$(grep -o "$store/[^ ]*/bin/jv-wall" <<<"$wallpaper_unit" | head -1)
  #
  # AND A STORE PATH AN EVALUATION PRODUCED IS NOT ONE THAT WAS BUILT (PLAN
  # E12). Every other case in this file reads text `nix eval` printed, and
  # text is always there; this one has to open a file. Any change under
  # `pkgs/` that jv-wall depends on moves this hash, and until something
  # realizes it the wrapper is simply absent — which used to fall into the
  # `-z "$art"` branch below and be reported as "sets no JV_WALL_DIR", an
  # accusation about the contents of a file that does not exist. (E11 moved
  # the jarvis-wallpaper hash and cost an iteration a `--baseline` run
  # learning that.) So realize it, and say what happened if it is still not
  # there. `.#jv-wall` is the same derivation modules/theme.nix installs, and
  # its expensive half — jarvis-wallpaper's six rasterized renders — was
  # already built for `.#jv-lock` above, so this costs a wrapper.
  wall_built=""
  if [ -n "$wall_bin" ] && [ ! -r "$wall_bin" ]; then
    wall_built=$(nix build --no-link --print-out-paths '.#jv-wall' 2>&1 | tail -3)
  fi
  art=""
  [ -r "$wall_bin" ] && art=$(grep -o "JV_WALL_DIR='[^']*'" "$wall_bin" | head -1 | cut -d"'" -f2)
  lock_png=$(grep -o "$store/[^ ]*\.png" "$script" | head -1)
  if ! is_unit "$wallpaper_unit"; then bad "$t" "no wallpaper unit: $(tail -3 <<<"$wallpaper_unit")"
  elif [ -z "$wall_bin" ]; then bad "$t" "the wallpaper unit does not start jv-wall: $(grep ExecStart <<<"$wallpaper_unit")"
  elif [ ! -r "$wall_bin" ]; then bad "$t" "$wall_bin is not in the store, so its bytes cannot be read; \`nix build --no-link .#jv-wall\` said: $wall_built"
  elif [ -z "$art" ]; then bad "$t" "$wall_bin sets no JV_WALL_DIR, so nothing says which art it draws"
  elif [ -z "$lock_png" ]; then bad "$t" "the lock screen names no png: $(grep -m1 -- --image "$script")"
  elif [ "$(dirname "$lock_png")" = "$art" ]; then ok "$t"
  else bad "$t" "the wallpaper draws out of $art; the lock screen shows $lock_png"; fi
fi

# swaylock is not setuid: it asks PAM under its own service name, and with no
# /etc/pam.d/swaylock there is nothing to ask and it refuses to start. The
# flake declares the service in modules/theme.nix beside the surface itself;
# nixpkgs' niri module also brings it in, which is exactly why this is
# checked rather than assumed — an inherited default can be dropped by a
# bump, and the symptom would be a lock screen that never opens.
t='the lock screen has a PAM stack, and it can authenticate a password'
pam=$(nix eval --raw '.#nixosConfigurations.ares' --apply \
  '(c: c.config.security.pam.services.swaylock.text)' 2>&1)
if grep -qE '^auth .*pam_unix\.so' <<<"$pam"; then ok "$t"
else bad "$t" "no unix auth line in /etc/pam.d/swaylock: $(tail -3 <<<"$pam")"; fi

t='the lock screen is on PATH, because a keybind can only spawn a name'
names=$(nix eval --raw '.#nixosConfigurations.ares' --apply \
  '(c: builtins.concatStringsSep "\n" (map (p: p.name) c.config.environment.systemPackages))' 2>&1)
if grep -qx 'jv-lock' <<<"$names"; then ok "$t"
else bad "$t" "jv-lock is not in environment.systemPackages: $(tail -3 <<<"$names")"; fi

# AND THE ART ITSELF HAS THE RIGHT RENDERS IN IT (PLAN E10). The geometries the
# wallpaper composes for used to be a list inside pkgs/jarvis-wallpaper — five
# sizes, three of which no output on this machine can display — and are now the
# outputs hosts/ares/outputs.nix declares, handed in by flake.nix as a package
# argument. That is a chain of four files, and nothing in the Python suites can
# walk it: they read source text, and what a `${lib.concatStringsSep}` came out
# to is an evaluation's answer.
#
# So this asks the DIRECTORY the running desktop draws from. `JV_WALL_DIR` out of
# the built jv-wall wrapper, listed — the same file-not-string hop the lock
# screen's case makes above and for the same E12 reason, one attribute further
# along: a declaration that never reached the package still evaluates, still
# builds, and leaves a monitor showing art composed for a different one. Both
# directions are checked, because they are different mistakes: a MISSING render
# is a panel that falls back to a scaled crop, and an EXTRA one is the defect
# E10 removed, which no surface ever asks for and nothing would ever report.
t='the wallpaper composes for every output ares declares, and for none it does not'
want=$(nix eval --raw --file hosts/ares/outputs.nix --apply \
  'l: builtins.concatStringsSep "\n" (map (o: "jarvisos-${toString o.width}x${toString o.height}.png") l)' 2>&1 \
  | sort -u)
# Realized rather than evaluated, for PLAN E12's reason: a store path an
# evaluation printed is not one whose bytes can be read. Cheap here — the
# expensive half (the renders themselves) was built for `.#jv-lock` above.
# `--print-out-paths` shares stdout with whatever nix wants to say — on a dirty
# worktree that is a warning ABOVE the path — so the path is taken as the line
# that is one, and everything nix said is kept for the message.
wall_said=$(nix build --no-link --print-out-paths '.#jv-wall' 2>&1)
wall=$(grep "^$store/" <<<"$wall_said" | tail -1)
art_dir=""
[ -n "$wall" ] && [ -r "$wall/bin/jv-wall" ] &&
  art_dir=$(grep -o "JV_WALL_DIR='[^']*'" "$wall/bin/jv-wall" | head -1 | cut -d"'" -f2)
if ! grep -q '^jarvisos-[0-9]*x[0-9]*\.png$' <<<"$want"; then
  bad "$t" "hosts/ares/outputs.nix names no geometry; nix said: $(tail -3 <<<"$want")"
elif [ -z "$art_dir" ] || [ ! -d "$art_dir" ]; then
  bad "$t" "no readable art directory in ${wall:-.#jv-wall}/bin/jv-wall; \`nix build --no-link .#jv-wall\` said: $(tail -3 <<<"$wall_said")"
elif [ ! -r "$art_dir/jarvisos.png" ]; then
  bad "$t" "$art_dir holds no jarvisos.png, which is what every undeclared output falls back to"
elif [ "$(cd "$art_dir" && ls jarvisos-*.png | sort -u)" = "$want" ]; then
  ok "$t"
else
  bad "$t" "ares declares $(tr '\n' ' ' <<<"$want"); the art holds $(cd "$art_dir" && ls jarvisos-*.png | tr '\n' ' ')"
fi

printf '\n%d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
