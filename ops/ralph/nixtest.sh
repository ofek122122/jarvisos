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
# The same question for a TIMER unit, which has a [Timer] section instead of
# a [Service] one — is_unit alone would read a real timer's text as "not a
# unit" and pass a refused evaluation's error text right past it.
is_timer_unit() { grep -q '^\[Timer\]$' <<<"$1"; }

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

# sysunit <unit-name> — the same question as unit(), for a SYSTEM unit
# (systemd.services.*, not systemd.user.services.*): snapper's own module and
# jv-snapshots-init both land in config.systemd.units, not
# config.systemd.user.units.
sysunit() {
  nix eval --raw '.#nixosConfigurations.ares' --apply \
    "(c: c.config.systemd.units.\"$1\".text)" \
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

# PLAN E13. The Phase 0 verifier's monitor check no longer carries ares'
# monitors in a regex; it compares the live session against a TSV generated
# from hosts/ares/outputs.nix and interpolated into the package. That is the
# same hazard one package further along: a declaration that never reached the
# BUILT doctor still evaluates, still builds, and leaves check 5 printing PASS
# about a machine nobody declared — which is worse than the literal it
# replaced, because a literal at least says what it believes.
#
# So this reads the expectation out of the built wrapper's bytes, and both
# directions again: an output the doctor does not know about is a monitor it
# will never complain is missing, and one it knows about that ares does not
# declare is a FAIL on every healthy boot.
t='the doctor checks for every output ares declares, and for none it does not'
want=$(nix eval --raw --file hosts/ares/outputs.nix --apply \
  'l: builtins.concatStringsSep "\n" (map (o: "${o.name}\t${toString o.width}\t${toString o.height}\t${o.refresh}\t${toString o.x}\t${toString o.y}") l)' 2>&1)
# Realized rather than evaluated (PLAN E12), and cheap: cuda-smoke and the
# doctor are two small derivations, ~2 s warm.
doc_said=$(nix build --no-link --print-out-paths '.#jarvis-doctor' 2>&1)
doc=$(grep "^$store/" <<<"$doc_said" | tail -1)
tsv=""
[ -n "$doc" ] && [ -r "$doc/bin/jarvis-doctor" ] &&
  tsv=$(grep -m1 '^JARVIS_OUTPUTS=' "$doc/bin/jarvis-doctor" | cut -d= -f2- | tr -d "'")
row_re=$(printf '^[A-Za-z0-9_-]+\t[0-9]+\t[0-9]+\t[0-9]+\\.[0-9]+\t-?[0-9]+\t-?[0-9]+$')
if ! grep -qE "$row_re" <<<"$want"; then
  bad "$t" "hosts/ares/outputs.nix names no output the doctor could check; nix said: $(tail -3 <<<"$want")"
elif [ -z "$tsv" ] || [ ! -r "$tsv" ]; then
  bad "$t" "no readable declaration in ${doc:-.#jarvis-doctor}/bin/jarvis-doctor; \`nix build --no-link .#jarvis-doctor\` said: $(tail -3 <<<"$doc_said")"
elif [ "$(sort -u "$tsv")" = "$(sort -u <<<"$want")" ]; then
  ok "$t"
else
  bad "$t" "ares declares [$(tr '\t' ' ' <<<"$want" | tr '\n' '|')]; the doctor checks for [$(tr '\t' ' ' <"$tsv" | tr '\n' '|')]"
fi

# PLAN E15. The two cases above ask what the doctor believes about the machine
# this flake declares. This pair asks the opposite question — what it does with
# a declaration that is not a desk — and it is the only kind of question this
# gate can ask, because the refusal is an evaluation-time `throw`: the Python
# suites read source text, and a throw that was deleted passes every text
# search for its own message.
#
# The subject is `.#jarvis-doctor` with its `outputs` argument OVERRIDDEN, so
# both probes run against the package the desktop really gets rather than
# against a copy of it. Neither builds: `.outPath` instantiates and the throw
# fires first. ~1.5 s each against a warm eval cache.
override='d: (d.override { outputs = '
t='the doctor refuses a layout whose monitors overlap'
# The colliding pair is deliberately NOT adjacent in the list, and it collides
# by one row rather than obviously: A and C share 1920x1 px because C is
# declared one pixel too far down, while B between them is legal. A check that
# compared each output with the next one — which is what the old `x += width`
# rule was and what a pairwise loop regresses to — passes this declaration.
# The message has to carry the measurement too: a check that merely notices
# cannot tell that typo from a panel declared entirely inside another.
said=$(nix eval --raw '.#jarvis-doctor' --apply "$override"'[
  { name = "A"; width = 2560; height = 1440; refresh = "60.000"; x = 0; y = 0; }
  { name = "B"; width = 1920; height = 1080; refresh = "60.000"; x = 2560; y = 0; }
  { name = "C"; width = 1920; height = 1080; refresh = "60.000"; x = 100; y = -1079; }
]; }).outPath' 2>&1)
if grep -q 'A and C overlap by 1920x1 px at 100,0' <<<"$said"; then ok "$t"
elif grep -q "^$store/" <<<"$said"; then
  bad "$t" "two monitors sharing 1920 px of screen evaluated fine, to $(grep "^$store/" <<<"$said" | tail -1)"
else
  bad "$t" "the evaluation was refused, but not by the overlap check: $(tail -3 <<<"$said")"
fi

# PLAN E16. The pair above asks whether the layout is a desk; this pair asks
# whether the ROW check 5 compares is made of the kind of values `niri msg
# outputs` prints. It is a different failure with a worse ending: the layout is
# right, the build succeeds, and the doctor reports a healthy machine as broken
# on every boot, because `toString 2560.0` is "2560.000000" and no compositor
# ever prints that.
t='the doctor refuses a position that is not a pair of integers'
# The float is the case that BUILDS — it passes the overlap arithmetic, since
# floats add and compare like ints — and it is on the second entry with a string
# `y` beside it, so this also checks that both faults of one entry and every
# faulted entry are reported at once. A refusal that stopped at the first is a
# rebuild per typo.
said=$(nix eval --raw '.#jarvis-doctor' --apply "$override"'[
  { name = "A"; width = 2560; height = 1440; refresh = "144.006"; x = 0; y = 0; }
  { name = "B"; width = 1920; height = 1080; refresh = "60.000"; x = 2560.0; y = "0"; }
]; }).outPath' 2>&1)
if grep -qE 'B: x = 2560\.0 .*, y = "0" ' <<<"$said"; then ok "$t"
elif grep -q "^$store/" <<<"$said"; then
  bad "$t" "a monitor declared at x = 2560.0 evaluated fine, and ships 2560.000000 as its position: $(grep "^$store/" <<<"$said" | tail -1)"
else
  bad "$t" "the evaluation was refused, but not by the row check, naming the entry and both fields: $(tail -3 <<<"$said")"
fi

t='the doctor refuses a row niri could not have printed'
# The other three columns. `refresh = 144.006` is the rate ares really needs
# written as a number, `name = ""` BUILDS and makes check 5 tell two lies (no
# live output matches it, and every live output becomes undeclared), and an
# absent `height` must read as absent rather than as a Nix error about a
# missing attribute.
said=$(nix eval --raw '.#jarvis-doctor' --apply "$override"'[
  { name = ""; width = 2560; refresh = 144.006; x = 0; y = 0; }
]; }).outPath' 2>&1)
# The prefix is part of the claim: the message's own name for the entry cannot
# come straight off `o.name`, or the one entry whose NAME is the fault is
# reported by a blank (or, for a non-string name, by an interpolation that
# throws instead of printing).
if grep -q 'an unnamed entry: name = "" ' <<<"$said" &&
  grep -q 'height = absent' <<<"$said" &&
  grep -q 'refresh = 144.006' <<<"$said"; then ok "$t"
elif grep -q "^$store/" <<<"$said"; then
  bad "$t" "a row with a blank name and a float refresh rate evaluated fine: $(grep "^$store/" <<<"$said" | tail -1)"
else
  bad "$t" "the evaluation was refused, but not with all three columns named: $(tail -3 <<<"$said")"
fi

t='the doctor accepts a gap, a touching edge and a monitor above the primary'
# The other half, and not a formality: a refusal that also refuses the real
# desk is a refusal nobody can ship. All three of these are legal and ares has
# the first two — B's left edge IS A's right edge (2560), B leaves 360 px of no
# screen under itself beside a taller primary, and C is the layout E14 wrote a
# `y` for: detached, and above. It is the green half of the E16 row check as
# well: every column of all three entries is a value niri could have printed,
# so a schema that refused any of these would be a schema that refuses ares.
said=$(nix eval --raw '.#jarvis-doctor' --apply "$override"'[
  { name = "A"; width = 2560; height = 1440; refresh = "60.000"; x = 0; y = 0; }
  { name = "B"; width = 1920; height = 1080; refresh = "60.000"; x = 2560; y = 0; }
  { name = "C"; width = 1920; height = 1080; refresh = "60.000"; x = 9000; y = -720; }
]; }).outPath' 2>&1)
if grep -q "^$store/" <<<"$said"; then ok "$t"
else bad "$t" "a desk with a gap in it was refused: $(tail -5 <<<"$said")"; fi

# ------------------------------------------------------------- niri's config
# PLAN F1. modules/niri.nix declares /etc/niri/config.kdl — the file niri's
# own fallback search already looks for once nobody has a user config in the
# way — from modules/niri/config-base.kdl (Ofek's binds, `.text`'d verbatim
# apart from four colour markers) plus one `output { }` stanza per monitor in
# hosts/ares/outputs.nix. tools/tests/test_niri_config.py already proved
# config-base.kdl is the frozen original with only its tail and its colours
# changed, in a bare checkout with no nix; what only an EVALUATION can ask is
# whether the markers were actually spent with real tokens, whether the three
# stanzas this evaluation produces are the ones ares' own declaration names,
# and whether the result is config niri itself accepts — `niri validate`,
# not a hand-rolled parser guessing at KDL.
# stdout and stderr are kept APART for this one, unlike `unit()` above: the
# text below gets written to a real file and handed to `niri validate`, and a
# harmless "Git tree is dirty" warning on stderr — guaranteed on this branch,
# since verify.sh always runs against an uncommitted tree — would land as
# line 1 of that file and be reported as a syntax error that is really nix's,
# not niri.nix's.
niri_etc_err=$(mktemp)
etc=$(nix eval --raw '.#nixosConfigurations.ares' --apply \
  '(c: c.config.environment.etc."niri/config.kdl".text)' 2>"$niri_etc_err")
etc_rc=$?

t='the built /etc/niri/config.kdl is not a Nix evaluation error'
if [ "$etc_rc" -eq 0 ] && [ -n "$etc" ]; then ok "$t"
else bad "$t" "$(tail -5 "$niri_etc_err")"; fi
rm -f "$niri_etc_err"

if [ "$etc_rc" -eq 0 ] && [ -n "$etc" ]; then
  t='every colour marker was spent, and none was left behind'
  if grep -q '@@' <<<"$etc"; then bad "$t" "$(grep -n '@@' <<<"$etc")"
  else ok "$t"; fi

  # The tokens themselves, read out of personality/theme.toml the same way
  # modules/niri.nix does — impure only for this one read (PLAN F1's markers
  # are the one place this file touches personality/), never for the
  # evaluation of `.#nixosConfigurations.ares` itself above.
  palette() {
    nix eval --raw --impure --expr \
      "(builtins.fromTOML (builtins.readFile ./personality/theme.toml)).palette.$1" 2>&1
  }
  ember=$(palette ember); line=$(palette line); warn=$(palette warn); risk=$(palette risk)

  t='the focus ring is painted in the ember token, not a colour of its own'
  if grep -qF "active-color \"$ember\"" <<<"$etc"; then ok "$t"
  else bad "$t" "no active-color \"$ember\": $(grep -m1 'active-color' <<<"$etc")"; fi

  t='the four markers became the tokens modules/niri.nix names, and only those'
  spent=$(grep -cF "\"$line\"" <<<"$etc")
  if [ "$spent" -eq 2 ] && grep -qF "active-color \"$warn\"" <<<"$etc" \
     && grep -qF "urgent-color \"$risk\"" <<<"$etc"; then ok "$t"
  else bad "$t" "line token seen $spent time(s) (want 2); warn/risk: $(grep -E 'active-color|urgent-color' <<<"$etc" | tail -2)"; fi

  t='every bind config-base.kdl carries survives into the built /etc file'
  # The base is `.text`'d in FIRST, verbatim except its four markers — so once
  # the markers are known-good above, the built file must still START with
  # the base's own text with those same substitutions applied. `base_len` is
  # taken from the SUBSTITUTED copy: the markers and the tokens they become
  # are different lengths, so slicing `$etc` by the raw file's length would
  # compare against the wrong number of bytes.
  substituted=$(sed "s/@@EMBER@@/$ember/;s/@@LINE@@/$line/g;s/@@WARN@@/$warn/;s/@@RISK@@/$risk/" \
    modules/niri/config-base.kdl)
  base_len=${#substituted}
  if [ "$base_len" -gt 0 ] && [ "${etc:0:$base_len}" = "$substituted" ]; then
    ok "$t"
  else bad "$t" "the built file's own head does not match config-base.kdl with its markers spent"; fi

  t='all three of hosts/ares/outputs.nix are declared, positioned, mode and all'
  # A TSV, one row per declared monitor — the same shape the doctor's own
  # cases above read outputs.nix as — so each expected STANZA is built here
  # in bash and compared whole, rather than asking Nix to join multi-line
  # stanzas on a delimiter this file would then have to re-split.
  want=$(nix eval --raw --file hosts/ares/outputs.nix --apply \
    'l: builtins.concatStringsSep "\n" (map (o: "${o.name}\t${toString o.width}\t${toString o.height}\t${o.refresh}\t${toString o.x}\t${toString o.y}") l)' 2>&1)
  missing=""
  rows=0
  while IFS=$'\t' read -r oname ow oh ohz ox oy; do
    [ -z "$oname" ] && continue
    rows=$((rows + 1))
    stanza=$(printf 'output "%s" {\n    mode "%sx%s@%s"\n    position x=%s y=%s\n}' \
      "$oname" "$ow" "$oh" "$ohz" "$ox" "$oy")
    grep -qF "$stanza" <<<"$etc" || missing="$missing $oname"
  done <<<"$want"
  if [ "$rows" -gt 0 ] && [ -z "$missing" ]; then ok "$t"
  else bad "$t" "hosts/ares/outputs.nix names ${rows:-0} output(s); missing from /etc/niri/config.kdl:${missing:-<all>}"; fi

  # PLAN H1: the drop-down scratchpad terminal. Its window-rule/workspace
  # join config.kdl's own tail directly (ordinary "multipart" KDL nodes), but
  # its keybind cannot — a second top-level `binds { }` node in the SAME file
  # is a hard niri parse error, checked by hand against a real
  # `niri validate` before modules/niri.nix was written this way — so it
  # lives in a second file, `scratchterm-binds.kdl`, pulled in by a path
  # RELATIVE to config.kdl's own directory. `niri validate` on config.kdl
  # ALONE, the way F1 checked it, would silently never parse that bind at
  # all (a relative include that resolves to nothing next to a lone tmpfile
  # is not an error niri reports against the including file) — so both are
  # written into the SAME throwaway directory here, standing in for
  # `/etc/niri/` without ever touching it.
  # Stderr kept apart from stdout for the same reason the $etc read above
  # does: a harmless "Git tree is dirty" warning landing as line 1 of the
  # file handed to `niri validate` below would be reported as a syntax
  # error that is niri's complaint about nix, not about this module.
  binds_etc_err=$(mktemp)
  binds_etc=$(nix eval --raw '.#nixosConfigurations.ares' --apply \
    '(c: c.config.environment.etc."niri/scratchterm-binds.kdl".text)' 2>"$binds_etc_err")
  rm -f "$binds_etc_err"

  t='the scratchpad terminal workspace/window-rule/include are in config.kdl'
  if grep -qF 'workspace "jv-scratch"' <<<"$etc" \
     && grep -qF 'app-id=r#"^jv-scratchterm$"#' <<<"$etc" \
     && grep -qF 'include "scratchterm-binds.kdl"' <<<"$etc"; then ok "$t"
  else bad "$t" "$(grep -n 'jv-scratch\|include' <<<"$etc")"; fi

  t='the scratchpad workspace is pinned to the declared PRIMARY output'
  primary=$(nix eval --raw --file hosts/ares/outputs.nix --apply \
    'l: (builtins.head (builtins.filter (o: o.primary or false) l)).name' 2>&1)
  if [ -n "$primary" ] && grep -qF "workspace \"jv-scratch\" {
    open-on-output \"$primary\"" <<<"$etc"; then ok "$t"
  else bad "$t" "primary output '$primary' not pinned: $(grep -A1 'workspace \"jv-scratch\"' <<<"$etc")"; fi

  t='the include is a relative path, never /etc/niri itself'
  if grep -qF 'include "scratchterm-binds.kdl"' <<<"$etc" \
     && ! grep -q 'include "/' <<<"$etc"; then ok "$t"
  else bad "$t" "found an absolute include: $(grep -n include <<<"$etc")"; fi

  t='the built scratchterm-binds.kdl is not a Nix evaluation error'
  if [ -n "$binds_etc" ] && grep -qF 'Mod+Grave' <<<"$binds_etc" \
     && grep -qF 'spawn "jv-scratchterm"' <<<"$binds_etc"; then ok "$t"
  else bad "$t" "$binds_etc"; fi

  # PLAN H2: the power menu. Same shape as H1's own bind — it needs no
  # window-rule/workspace (a dmenu popup, not a placed window), so only its
  # include and its own bind file matter here.
  power_binds_etc_err=$(mktemp)
  power_binds_etc=$(nix eval --raw '.#nixosConfigurations.ares' --apply \
    '(c: c.config.environment.etc."niri/power-menu-binds.kdl".text)' 2>"$power_binds_etc_err")
  rm -f "$power_binds_etc_err"

  t='the power menu include is in config.kdl, as a relative path'
  if grep -qF 'include "power-menu-binds.kdl"' <<<"$etc" \
     && ! grep -q 'include "/' <<<"$etc"; then ok "$t"
  else bad "$t" "found no relative power-menu include: $(grep -n include <<<"$etc")"; fi

  t='the built power-menu-binds.kdl is not a Nix evaluation error'
  if [ -n "$power_binds_etc" ] && grep -qF 'Mod+Shift+Escape' <<<"$power_binds_etc" \
     && grep -qF 'spawn "jv-power-menu"' <<<"$power_binds_etc"; then ok "$t"
  else bad "$t" "$power_binds_etc"; fi

  t='the power menu is on PATH, because a keybind can only spawn a name'
  sys_pkgs=$(nix eval --raw '.#nixosConfigurations.ares' --apply \
    '(c: builtins.concatStringsSep "\n" (map (p: p.name) c.config.environment.systemPackages))' 2>&1)
  if grep -qx 'jv-power-menu' <<<"$sys_pkgs"; then ok "$t"
  else bad "$t" "jv-power-menu missing from environment.systemPackages"; fi

  t='niri itself accepts the config this flake would install'
  niri_bin=$(nix build --no-link --print-out-paths '.#nixosConfigurations.ares.pkgs.niri' 2>&1 | tail -1)
  tmpd=$(mktemp -d)
  printf '%s' "$etc" > "$tmpd/config.kdl"
  printf '%s' "$binds_etc" > "$tmpd/scratchterm-binds.kdl"
  printf '%s' "$power_binds_etc" > "$tmpd/power-menu-binds.kdl"
  validated=""
  if [ -x "$niri_bin/bin/niri" ]; then
    validated=$("$niri_bin/bin/niri" validate -c "$tmpd/config.kdl" 2>&1)
  fi
  rm -rf "$tmpd"
  if grep -q 'config is valid' <<<"$validated"; then ok "$t"
  else bad "$t" "niri at ${niri_bin:-<not built>} said: $(tail -5 <<<"$validated")"; fi

  t='jv-scratchterm pins niri/jq/alacritty into its own PATH, never trusts the ambient one'
  scratchterm_bin=$(nix build --no-link --print-out-paths '.#jv-scratchterm' 2>&1 | tail -1)
  script=""
  [ -x "$scratchterm_bin/bin/jv-scratchterm" ] && script=$(cat "$scratchterm_bin/bin/jv-scratchterm")
  if grep -q "PATH=\"$store/[^\"]*niri[^\"]*/bin:$store/[^\"]*jq[^\"]*/bin:$store/[^\"]*alacritty[^\"]*/bin" <<<"$script"; then
    ok "$t"
  else bad "$t" "jv-scratchterm at ${scratchterm_bin:-<not built>}: $(head -5 <<<"$script")"; fi

  t='jv-power-menu pins fuzzel/systemctl/jv-lock into its own PATH, never trusts the ambient one'
  power_menu_bin=$(nix build --no-link --print-out-paths '.#jv-power-menu' 2>&1 | tail -1)
  power_script=""
  [ -x "$power_menu_bin/bin/jv-power-menu" ] && power_script=$(cat "$power_menu_bin/bin/jv-power-menu")
  if grep -q "PATH=\"$store/[^\"]*fuzzel[^\"]*/bin:$store/[^\"]*systemd[^\"]*/bin:$store/[^\"]*jv-lock[^\"]*/bin" <<<"$power_script"; then
    ok "$t"
  else bad "$t" "jv-power-menu at ${power_menu_bin:-<not built>}: $(head -5 <<<"$power_script")"; fi
fi

# ---------------------------------------------------------- comfort basics
# PLAN F2. modules/comfort.nix declares four papercuts that used to be either
# an nixpkgs default nobody wrote down or a gap nobody filled: auto-lock on
# idle (plus lock-before-sleep), a night light, XDG user directories, and the
# firewall. Each is asked of the evaluation because each is an OPTION's
# effect, not source text tools/tests can read in a bare checkout.

t='idle auto-lock: the unit exists, waits for jv-lock to finish, and locks before sleep too'
out=$(unit jv-idle.service '')
if ! is_unit "$out"; then bad "$t" "not a unit: $(tail -3 <<<"$out")"
elif ! grep -q "$store/[^ ]*/bin/swayidle -w" <<<"$out"; then
  bad "$t" "does not run swayidle -w: $(grep ExecStart <<<"$out")"
elif ! grep -q "timeout 300 '$store/[^ ]*/bin/jv-lock'" <<<"$out"; then
  bad "$t" "no idle timeout raising jv-lock: $(grep -A2 ExecStart <<<"$out")"
elif ! grep -q "before-sleep '$store/[^ ]*/bin/jv-lock'" <<<"$out"; then
  bad "$t" "no before-sleep hook raising jv-lock: $(grep -A3 ExecStart <<<"$out")"
else ok "$t"; fi

t='idle auto-lock: part of the graphical session, not left to start on its own'
if grep -q 'WantedBy=graphical-session.target' <<<"$out" && grep -q 'PartOf=graphical-session.target' <<<"$out"; then
  ok "$t"
else bad "$t" "missing WantedBy/PartOf graphical-session.target: $(tail -3 <<<"$out")"; fi

t='night light: the unit exists and runs wlsunset at Jerusalem'"'"'s coordinates'
out=$(unit jv-nightlight.service '')
if ! is_unit "$out"; then bad "$t" "not a unit: $(tail -3 <<<"$out")"
elif grep -q -- "$store/[^ ]*/bin/wlsunset -l 31.7683 -L 35.2137" <<<"$out"; then ok "$t"
else bad "$t" "$(grep ExecStart <<<"$out")"; fi

t='the firewall is declared on, not just defaulted on'
firewall_err=$(mktemp)
out=$(nix eval '.#nixosConfigurations.ares.config.networking.firewall.enable' 2>"$firewall_err")
if [ "$out" = "true" ]; then ok "$t"
else bad "$t" "$out $(cat "$firewall_err")"; fi
rm -f "$firewall_err"

t='xdg-user-dirs ships, so ~/Desktop et al. get created at login'
names=$(nix eval --raw '.#nixosConfigurations.ares' --apply \
  '(c: builtins.concatStringsSep "\n" (map (p: p.name) c.config.environment.systemPackages))' 2>&1)
if grep -q '^xdg-user-dirs-' <<<"$names"; then ok "$t"
else bad "$t" "xdg-user-dirs is not in environment.systemPackages: $(tail -3 <<<"$names")"; fi

# -------------------------------------------------------------- bluetooth
# PLAN G1. modules/bluetooth.nix declares the stack that was never written
# down: the BlueZ daemon powers its radio on at boot, advertises the audio
# profiles PipeWire (modules/audio.nix) needs for a headset, and
# services.blueman ships the pairing GUI's .desktop entry — no tray to dock
# into yet (H10), so the app launcher/tap-Super menu are the "GUI path".

t='bluetooth radio: on, and powered on at boot (not left off after a reboot)'
bt_err=$(mktemp)
out=$(nix eval '.#nixosConfigurations.ares' --apply \
  '(c: if c.config.hardware.bluetooth.enable && c.config.hardware.bluetooth.powerOnBoot
       then "both on" else "not both on")' 2>"$bt_err")
if [ "$out" = '"both on"' ]; then ok "$t"
else bad "$t" "$out $(cat "$bt_err")"; fi
rm -f "$bt_err"

t='bluetooth: the real config BlueZ reads at boot carries both settings'
main_conf_drv=$(nix eval --raw '.#nixosConfigurations.ares.config.environment.etc."bluetooth/main.conf".source.drvPath' 2>/dev/null)
main_conf=$(nix build --no-link --print-out-paths "${main_conf_drv}^out" 2>&1 | tail -1)
if [ ! -f "$main_conf" ]; then bad "$t" "did not build: $main_conf"
elif grep -q '^AutoEnable=true$' "$main_conf" && grep -q '^Enable=Source,Sink,Media,Socket$' "$main_conf"; then
  ok "$t"
else bad "$t" "$(cat "$main_conf" 2>/dev/null)"; fi

t='blueman: the pairing GUI ships, so there is a way to pair with no tray yet'
if grep -q '^blueman-' <<<"$names"; then ok "$t"
else bad "$t" "blueman is not in environment.systemPackages: $(tail -3 <<<"$names")"; fi

# --------------------------------------------------------------- printing
# PLAN G2. modules/printing.nix declares CUPS with a broad driver set and
# turns Avahi on for mDNS — the comment above the module claims cups-browsed
# (services.printing.browsed.enable) needs no switch of its own because it
# already defaults to config.services.avahi.enable; that claim is a fact
# about the real evaluation, not this file, so it gets its own case.

t='printing: CUPS and Avahi are both on'
print_err=$(mktemp)
out=$(nix eval '.#nixosConfigurations.ares' --apply \
  '(c: if c.config.services.printing.enable && c.config.services.avahi.enable
       then "both on" else "not both on")' 2>"$print_err")
if [ "$out" = '"both on"' ]; then ok "$t"
else bad "$t" "$out $(cat "$print_err")"; fi
rm -f "$print_err"

t='printing: mDNS resolution is on and its firewall port is actually open'
print_err=$(mktemp)
out=$(nix eval '.#nixosConfigurations.ares' --apply \
  '(c: if c.config.services.avahi.nssmdns4 && (builtins.elem 5353 c.config.networking.firewall.allowedUDPPorts)
       then "mdns reachable" else "mdns not reachable")' 2>"$print_err")
if [ "$out" = '"mdns reachable"' ]; then ok "$t"
else bad "$t" "$out $(cat "$print_err")"; fi
rm -f "$print_err"

t='printing: cups-browsed turns on by itself once avahi is on (no second switch)'
print_err=$(mktemp)
out=$(nix eval '.#nixosConfigurations.ares.config.services.printing.browsed.enable' 2>"$print_err")
if [ "$out" = "true" ]; then ok "$t"
else bad "$t" "$out $(cat "$print_err")"; fi
rm -f "$print_err"

t='printing: the declared driver set reaches CUPS (gutenprint, hplip, splix, brlaser)'
driver_names=$(nix eval --raw '.#nixosConfigurations.ares' --apply \
  '(c: builtins.concatStringsSep "\n" (map (p: p.name) c.config.services.printing.drivers))' 2>&1)
missing=""
for d in gutenprint hplip splix brlaser; do
  grep -q "^${d}-" <<<"$driver_names" || missing="$missing $d"
done
if [ -z "$missing" ]; then ok "$t"
else bad "$t" "missing:$missing — got: $(tr '\n' ' ' <<<"$driver_names")"; fi

# ------------------------------------------------------ update notifier
# PLAN G3. modules/update-notifier.nix wires pkgs/jv-update-notifier (whose
# own shell logic tools/tests/test_update_notifier.py proves against a real
# git repo, in a bare checkout with no nix) to run once per login. What only
# an evaluation can see is whether it is actually the BUILT package that
# runs, and whether it runs at the right trigger.

t='jv-update-notifier is wired to run at login, once, as a user service'
un_out=$(unit jv-update-notifier.service '')
if ! is_unit "$un_out"; then bad "$t" "not a unit: $(tail -3 <<<"$un_out")"
elif grep -q '^Type=oneshot$' <<<"$un_out" \
  && grep -q '^WantedBy=graphical-session.target$' <<<"$un_out"; then
  ok "$t"
else bad "$t" "$(tail -6 <<<"$un_out")"; fi

t='the unit runs the actual built jv-update-notifier package, out of the store'
notifier=$(nix build --no-link --print-out-paths '.#jv-update-notifier' 2>&1 | tail -1)
if [ ! -x "$notifier/bin/jv-update-notifier" ]; then
  bad "$t" "\`nix build .#jv-update-notifier\` said: $notifier"
elif grep -qF "ExecStart=$notifier/bin/jv-update-notifier" <<<"$un_out"; then
  ok "$t"
else bad "$t" "unit does not run the built package: $(grep ExecStart <<<"$un_out")"; fi

# ------------------------------------------------------ disk-space warning
# PLAN G4. modules/disk-space-warning.nix wires pkgs/jv-disk-space-warning
# (whose own shell logic tools/tests/test_disk_space_warning.py proves
# against stubbed df/notify-send) onto a periodic TIMER rather than a
# login-only oneshot, because disk usage grows during a session and not just
# between them. What only an evaluation can see: the timer actually fires
# repeatedly under the session, and the service it triggers runs the real
# built package.

t='jv-disk-space-warning timer: fires periodically, tied to the graphical session'
dt_out=$(unit jv-disk-space-warning.timer '')
if ! is_timer_unit "$dt_out"; then bad "$t" "not a timer unit: $(tail -3 <<<"$dt_out")"
elif grep -q '^WantedBy=graphical-session.target$' <<<"$dt_out" \
  && grep -q '^OnUnitActiveSec=' <<<"$dt_out"; then
  ok "$t"
else bad "$t" "$(tail -6 <<<"$dt_out")"; fi

t='jv-disk-space-warning service: Type=oneshot, runs the actual built package'
dw_out=$(unit jv-disk-space-warning.service '')
diskwarn=$(nix build --no-link --print-out-paths '.#jv-disk-space-warning' 2>&1 | tail -1)
if ! is_unit "$dw_out"; then bad "$t" "not a unit: $(tail -3 <<<"$dw_out")"
elif [ ! -x "$diskwarn/bin/jv-disk-space-warning" ]; then
  bad "$t" "\`nix build .#jv-disk-space-warning\` said: $diskwarn"
elif grep -q '^Type=oneshot$' <<<"$dw_out" \
  && grep -qF "ExecStart=$diskwarn/bin/jv-disk-space-warning" <<<"$dw_out"; then
  ok "$t"
else bad "$t" "$(tail -6 <<<"$dw_out")"; fi

# ------------------------------------------------------------- snapshots
# PLAN F3. modules/snapshots.nix declares a snapper timeline over disko.nix's
# @root and @home subvolumes plus the one gap snapper's own module leaves
# (creating `.snapshots`); everything below is an OPTION's effect on the real
# evaluation, which tools/tests/test_snapshots.py (bare checkout, no nix)
# cannot see.

t='both configs point at the subvolumes disko.nix actually declares'
snap_err=$(mktemp)
subs=$(nix eval --raw '.#nixosConfigurations.ares' --apply \
  '(c: "${c.config.services.snapper.configs.root.SUBVOLUME} ${c.config.services.snapper.configs.home.SUBVOLUME}")' 2>"$snap_err")
if [ "$subs" = "/ /home" ]; then ok "$t"
else bad "$t" "root/home SUBVOLUME: $subs $(cat "$snap_err")"; fi
rm -f "$snap_err"

t='the timeline is bounded, not left at upstream defaults or unbounded'
snap_err=$(mktemp)
limits=$(nix eval --raw '.#nixosConfigurations.ares' --apply \
  '(c: with c.config.services.snapper.configs.root;
      "${toString TIMELINE_LIMIT_HOURLY} ${toString TIMELINE_LIMIT_DAILY} ${toString NUMBER_LIMIT}")' 2>"$snap_err")
if [[ "$limits" =~ ^[0-9]+\ [0-9]+\ [0-9]+$ ]]; then ok "$t"
else bad "$t" "hourly/daily/number limits not all bounded integers: $limits $(cat "$snap_err")"; fi
rm -f "$snap_err"

t='jv-snapshots-init creates .snapshots for / and /home, idempotently'
# A script embedded in ExecStart is only a STORE-PATH STRING to an evaluation
# (the derivation behind it was already coerced away) and cannot be `nix
# build`-ed from there, which is exactly why it is a flake package rather
# than an inline pkgs.writeShellScript (see pkgs/jv-snapshots-init's own
# comment) — built and read directly, the same way the lock screen is below.
init_said=$(nix build --no-link --print-out-paths '.#jv-snapshots-init' 2>&1)
init=$(tail -1 <<<"$init_said")
script=""
[ -x "$init/bin/jv-snapshots-init" ] && script=$(cat "$init/bin/jv-snapshots-init")
if [ -z "$script" ]; then bad "$t" "\`nix build .#jv-snapshots-init\` said: $(tail -3 <<<"$init_said")"
elif grep -qF 'target="/"' <<<"$script" && grep -qF 'target="/home"' <<<"$script" \
     && grep -q 'subvolume show' <<<"$script" && grep -q 'subvolume create' <<<"$script"; then
  ok "$t"
else bad "$t" "script does not check-then-create both / and /home: $script"; fi

t='jv-snapshots-init is the one that actually runs at boot, out of the store'
out=$(sysunit jv-snapshots-init.service)
if grep -qF "ExecStart=$init/bin/jv-snapshots-init" <<<"$out"; then ok "$t"
else bad "$t" "unit does not run the built package: $(grep ExecStart <<<"$out")"; fi

t='snapper-timeline/-cleanup/-boot all wait for jv-snapshots-init to finish'
for u in snapper-timeline.service snapper-cleanup.service snapper-boot.service; do
  out=$(sysunit "$u")
  if ! grep -q '^\[Unit\]$' <<<"$out"; then bad "$t" "$u is not a unit: $(tail -3 <<<"$out")"; break; fi
  if ! grep -q '^Requires=.*jv-snapshots-init.service' <<<"$out" || ! grep -q '^After=.*jv-snapshots-init.service' <<<"$out"; then
    bad "$t" "$u missing Requires=/After= jv-snapshots-init.service: $(grep -E 'Requires|After' <<<"$out")"
    break
  fi
  [ "$u" = snapper-boot.service ] && ok "$t"
done

t='root is snapshotted on every boot'
out=$(sysunit snapper-boot.service)
if grep -q -- '--cleanup-algorithm number' <<<"$out" && grep -q 'ConditionPathExists=/etc/snapper/configs/root' <<<"$out"; then
  ok "$t"
else bad "$t" "$(tail -5 <<<"$out")"; fi

t='jv-snapshot-restore ships on the machine'
names=$(nix eval --raw '.#nixosConfigurations.ares' --apply \
  '(c: builtins.concatStringsSep "\n" (map (p: p.name) c.config.environment.systemPackages))' 2>&1)
if grep -q '^jv-snapshot-restore$' <<<"$names"; then ok "$t"
else bad "$t" "jv-snapshot-restore is not in environment.systemPackages: $(tail -3 <<<"$names")"; fi


# ------------------------------------------------------------ dictation
# PLAN F5b. modules/dictate.nix wires jv-dictate (push-to-talk key -> the
# SAME faster-whisper weights jv-ears already uses -> a fake Sink until
# PLAN F5's jv-act tool exists, R11) as a user service. What only an
# evaluation can see: the unit actually exists, orders after PipeWire the
# same way jv-ears does (both open a capture stream), and points
# JARVIS_MODELS_DIR at the SAME directory jv-ears reads rather than a
# second copy of the weights (invariant 1 forbids the direct import that
# would otherwise prove this without asking the evaluation at all).

t='jv-dictate is wired as a user service, ordered after PipeWire like jv-ears'
dictate_out=$(unit jv-dictate.service '')
if ! is_unit "$dictate_out"; then bad "$t" "not a unit: $(tail -3 <<<"$dictate_out")"
elif grep -q '^ConditionUser=ofek$' <<<"$dictate_out" \
  && grep -q '^WantedBy=default.target$' <<<"$dictate_out" \
  && grep -q '^After=.*pipewire.service' <<<"$dictate_out" \
  && grep -q '^Wants=.*pipewire.service' <<<"$dictate_out"; then
  ok "$t"
else bad "$t" "$(tail -10 <<<"$dictate_out")"; fi

t='jv-dictate points at the SAME model directory jv-ears reads, not a second copy'
ears_out=$(unit jv-ears.service '')
ears_dir=$(grep -oP 'JARVIS_MODELS_DIR=\K[^"]*' <<<"$ears_out")
dictate_dir=$(grep -oP 'JARVIS_MODELS_DIR=\K[^"]*' <<<"$dictate_out")
if [ -n "$ears_dir" ] && [ "$ears_dir" = "$dictate_dir" ]; then ok "$t"
else bad "$t" "jv-ears=$ears_dir jv-dictate=$dictate_dir"; fi

t='jv-dictate runs the built jv-dictate binary, out of the store'
if grep -qE "ExecStart=$store/[^\"]*-env/bin/jv-dictate\$" <<<"$dictate_out"; then ok "$t"
else bad "$t" "$(grep ExecStart <<<"$dictate_out")"; fi

# ------------------------------------------------------------------- ssh
# PLAN G7a. The agent itself is nixpkgs' gcr-ssh-agent, already switched on
# by modules/apps.nix's gnome-keyring (see modules/ssh.nix's own comment) —
# `programs.ssh.startAgent` must stay OFF, because its own module refuses to
# evaluate at all with both agents on ("only one SSH agent can be installed
# at a time"), which is exactly the failure a `nix build` catches but this
# fast eval-only gate would not unless it asks by name. modules/ssh.nix's
# actual job is appending client-comfort defaults to the system-wide
# /etc/ssh/ssh_config via `programs.ssh.extraConfig`.

t='ssh: startAgent stays off — its own module conflicts with gcr-ssh-agent'
out=$(nix eval '.#nixosConfigurations.ares' --apply \
  '(c: c.config.programs.ssh.startAgent)' 2>&1)
if grep -qx 'false' <<<"$out"; then ok "$t"
else bad "$t" "$out"; fi

t='ssh: gcr-ssh-agent (via gnome-keyring) is the real per-session agent'
sock=$(nix eval --json '.#nixosConfigurations.ares' --apply \
  '(c: c.config.systemd.user.sockets."gcr-ssh-agent".wantedBy)' 2>&1)
svc=$(nix eval --json '.#nixosConfigurations.ares' --apply \
  '(c: c.config.systemd.user.services."gcr-ssh-agent".wantedBy)' 2>&1)
if grep -qx '\["sockets.target"\]' <<<"$sock" && grep -qx '\["default.target"\]' <<<"$svc"; then
  ok "$t"
else bad "$t" "socket=$sock service=$svc"; fi

t='ssh client config: comfort defaults reach the real /etc/ssh/ssh_config'
ssh_config=$(nix eval --raw '.#nixosConfigurations.ares' --apply \
  '(c: c.config.environment.etc."ssh/ssh_config".text)' 2>&1)
if grep -q '^AddKeysToAgent yes$' <<<"$ssh_config" \
  && grep -q '^ServerAliveInterval 60$' <<<"$ssh_config" \
  && grep -q '^ServerAliveCountMax 3$' <<<"$ssh_config"; then
  ok "$t"
else bad "$t" "$(tail -10 <<<"$ssh_config")"; fi

# ------------------------------------------------------------------- vpn
# PLAN G7b. NetworkManager already runs (hosts/ares/default.nix) and already
# has a GUI (networkmanagerapplet, modules/apps.nix) — modules/vpn.nix adds
# the protocol plugins NM needs before that GUI can offer OpenVPN/
# OpenConnect at all, plus the WireGuard CLI (native NM device type since
# 1.16 needs no plugin package, confirmed against the real evaluation
# below rather than assumed from nixpkgs docs).

t='vpn: OpenVPN and OpenConnect plugins reach NetworkManager, no peer config added'
plugins=$(nix eval --json '.#nixosConfigurations.ares' --apply \
  '(c: map (p: p.pname or p.name) c.config.networking.networkmanager.plugins)' 2>/dev/null)
wg_ifaces=$(nix eval --json '.#nixosConfigurations.ares.config.networking.wireguard.interfaces' 2>/dev/null)
if grep -qi 'networkmanager-openvpn' <<<"$plugins" \
  && grep -qi 'networkmanager-openconnect' <<<"$plugins" \
  && grep -qx '{}' <<<"$wg_ifaces"; then
  ok "$t"
else bad "$t" "plugins=$plugins wg_ifaces=$wg_ifaces"; fi

t='vpn: wireguard-tools (wg/wg-quick CLI) reaches environment.systemPackages'
pkgs_out=$(nix eval --json '.#nixosConfigurations.ares' --apply \
  '(c: map (p: p.pname or p.name) c.config.environment.systemPackages)' 2>/dev/null)
if grep -q 'wireguard-tools' <<<"$pkgs_out"; then ok "$t"
else bad "$t" "$(tr ',' '\n' <<<"$pkgs_out" | grep -i wireguard || echo 'not found')"; fi

t='vpn: NetworkManager itself already ships native WireGuard device support'
nm_pkg=$(nix eval --raw '.#nixosConfigurations.ares.config.networking.networkmanager.package' 2>/dev/null)
if [ -f "$nm_pkg/share/dbus-1/interfaces/org.freedesktop.NetworkManager.Device.WireGuard.xml" ]; then
  ok "$t"
else bad "$t" "no WireGuard device interface under $nm_pkg"; fi

# -------------------------------------------------------------- syncthing
# PLAN G7c, the last slice of G7. modules/syncthing.nix runs Syncthing as
# `ofek`, not nixpkgs' own dedicated `syncthing` user — that only matters
# because nixpkgs' module skips its own `createHome`/user-creation path
# entirely once `user != defaultUser`, so the case below reads the generated
# unit rather than assuming the module attrset means what modules/vpn.nix's
# neighbours assume.

t='syncthing: runs as ofek:users, GUI stays on localhost, no folders/devices declared'
st_unit=$(sysunit 'syncthing.service')
gui_addr=$(nix eval --raw '.#nixosConfigurations.ares.config.services.syncthing.guiAddress' 2>/dev/null)
folders=$(nix eval --json '.#nixosConfigurations.ares.config.services.syncthing.settings.folders' 2>/dev/null)
if is_unit "$st_unit" \
  && grep -q '^User=ofek$' <<<"$st_unit" \
  && grep -q '^Group=users$' <<<"$st_unit" \
  && [ "$gui_addr" = '127.0.0.1:8384' ] \
  && grep -qx '{}' <<<"$folders"; then
  ok "$t"
else bad "$t" "unit=$(tail -5 <<<"$st_unit") gui_addr=$gui_addr folders=$folders"; fi

t='syncthing: dataDir lives under ofek'"'"'s own home, not the dedicated user'"'"'s'
data_dir=$(nix eval --raw '.#nixosConfigurations.ares.config.services.syncthing.dataDir' 2>/dev/null)
if [ "$data_dir" = '/home/ofek/Sync' ]; then ok "$t"
else bad "$t" "dataDir=$data_dir"; fi

# ---------------------------------------------------------- notify sound
# PLAN G8, blueprint §06's "Sound as UI". pkgs/jv-notify-sound renders the
# chime from pure arithmetic (tools/gen_notify_sound.py, proven against
# tools/tests/test_gen_notify_sound.py in a bare checkout) and pkgs/jv-notify
# pins it — and `pw-play` — into its own wrapper, the one thing only an
# evaluation can see: whether the BUILT jv-notify actually spends the BUILT
# jv-notify-sound, both read out of the real store paths rather than assumed
# from either package's source.

t='jv-notify-sound builds a real mono .wav, not an empty or malformed file'
sound=$(nix build --no-link --print-out-paths '.#jv-notify-sound' 2>&1 | tail -1)
wav="$sound/share/jv-notify-sound/arrived.wav"
if [ ! -f "$wav" ]; then bad "$t" "\`nix build .#jv-notify-sound\` said: $sound"
elif [ "$(head -c4 "$wav")" = "RIFF" ] && [ "$(dd if="$wav" bs=1 skip=8 count=4 2>/dev/null)" = "WAVE" ]; then
  ok "$t"
else bad "$t" "no RIFF/WAVE header at $wav"; fi

t='jv-notify pins pw-play and the built chime into its own wrapper, not $PATH'
notify=$(nix build --no-link --print-out-paths '.#jv-notify' 2>&1 | tail -1)
script="$notify/bin/jv-notify"
if [ ! -f "$script" ]; then
  bad "$t" "\`nix build .#jv-notify\` said: $notify"
else
  play_line=$(grep -o "JV_NOTIFY_PLAY='[^']*'" "$script")
  sound_line=$(grep -o "JV_NOTIFY_SOUND='[^']*'" "$script")
  if [[ "$play_line" == "JV_NOTIFY_PLAY='$store/"*"/bin/pw-play'" ]] \
    && [ "$sound_line" = "JV_NOTIFY_SOUND='$wav'" ]; then
    ok "$t"
  else bad "$t" "play=$play_line sound=$sound_line (expected sound=JV_NOTIFY_SOUND='$wav')"; fi
fi

printf '\n%d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
