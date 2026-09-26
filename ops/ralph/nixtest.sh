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

  t='niri itself accepts the config this flake would install'
  niri_bin=$(nix build --no-link --print-out-paths '.#nixosConfigurations.ares.pkgs.niri' 2>&1 | tail -1)
  tmp=$(mktemp)
  printf '%s' "$etc" > "$tmp"
  validated=""
  if [ -x "$niri_bin/bin/niri" ]; then
    validated=$("$niri_bin/bin/niri" validate -c "$tmp" 2>&1)
  fi
  rm -f "$tmp"
  if grep -q 'config is valid' <<<"$validated"; then ok "$t"
  else bad "$t" "niri at ${niri_bin:-<not built>} said: $(tail -5 <<<"$validated")"; fi
fi

printf '\n%d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
