# The JarvisOS desktop wallpaper — rendered from SVG by resvg at build time
# (no binary blob checked in; restyle by editing the heredoc). Blueprint §06:
# a dark instrument at rest — deep ground, one ember arc, earned emptiness.
#
# THE COLOURS ARE NOT WRITTEN HERE, for the same reason they are not written in
# modules/theme.nix: `personality/theme.toml` says it is "the ONLY place a
# colour exists", and every surface that hand-copied the palette drifted off it
# — the terminal and the launcher did, and so did this file. Five of the six
# literals it used to carry were not §06: #E6ECF0 and #64747F are the greys D7
# took off every other desktop surface, #F79070 is a hotter lookalike of ember
# that is not a token at all, #26323B sits between `line` and `line_soft`, and
# #05080B is darker than every colour the theme defines. Nothing failed,
# because until D7 nothing was asking; a tools gate asks now.
{
  lib,
  runCommand,
  resvg,
  jetbrains-mono,
  python3,
  # THE CANVASES THIS ART IS COMPOSED FOR (PLAN E10), and deliberately WITHOUT
  # a default. It used to be a list of five geometries written in the builder
  # below, three of which no monitor on this machine can display; it is now
  # whoever instantiates this package saying which outputs exist —
  # `hosts/ares/outputs.nix` for the desktop, `tools/wallshots/outputs.nix` for
  # the contact sheet. A default here would be that guess again, one level up
  # and harder to see: `callPackage` would supply it silently and the host's
  # real monitors would never reach the art. Missing is an evaluation error,
  # which is the outcome we want.
  #
  # Shape: a list of attrsets with at least `width` and `height` (ints) and a
  # `name` for the messages, exactly one of which carries `primary = true`.
  # Everything else on an entry (`refresh`, `x`) belongs to the layout and is
  # none of this package's business.
  outputs,
}:
let
  theme = builtins.fromTOML (builtins.readFile ../../personality/theme.toml);

  # Ask theme.toml for a token, and throw if it does not have it — the same
  # helper as modules/theme.nix, for the same reason: a colour that silently
  # became "" is an SVG attribute resvg ignores, and the shape it paints just
  # disappears from the wallpaper with nobody told.
  token =
    name:
    theme.palette.${name} or (throw ''
      pkgs/jarvis-wallpaper spends the colour "${name}", and [palette] in
      personality/theme.toml does not have it. Either the token was renamed
      there (rename it here too) or the wallpaper is asking for a colour §06
      does not define.'');

  face =
    role:
    theme.type."family_${role}" or (throw ''
      pkgs/jarvis-wallpaper sets the wordmark in the face for the role
      "${role}", and [type] in personality/theme.toml names no family_${role}.
      A face is identity (invariant 9): named there, bound to a package in
      modules/fonts.nix, spent here.'');

  # --- the tokens the wallpaper spends, and what each one is for ----------
  #
  # The field is §06's `ground`, and it settles into `ground_deep` at the far
  # edges. That is the one step the theme already owns — theme.toml spends it
  # to put a HUD plate BELOW the page ground so a floating panel reads as
  # nearer — and here the same step is spent as distance instead of elevation.
  # It is a shallower vignette than the one it replaces (three levels across
  # the field where there were seven), and that is the point: the old outer
  # stop was #05080B, darker than every token and darker than the plates that
  # float on it, so a HUD panel read as LIGHTER than the desktop behind it,
  # the exact inversion of what `ground_deep` is for.
  ground = token "ground";
  groundDeep = token "ground_deep";

  # Ember is the one warm signal on the whole screen: the comet, the reticle,
  # the glow behind them, and the OS in the wordmark. The comet's head was
  # #F79070, a hotter hue invented for it; it is ember now, and it still reads
  # as a head because it has more MASS than the arc, not a different colour.
  ember = token "ember";
  # Teal is the second, cooler voice. One tick, once.
  teal = token "teal";

  # Structure: the grid and the outer rings are `line`, the middle ring is
  # `line_soft`. Two weights of hairline, and no third.
  line = token "line";
  lineSoft = token "line_soft";

  # Words: the wordmark in `text`, the subtitle and the dashed tick ring in
  # `text_3` — the quiet tier, which is what a legend and a scale are.
  text = token "text";
  text3 = token "text_3";

  monoFamily = face "mono";

  # --- WHERE THE INSTRUMENT GOES, and the one contract this package has -----
  #
  # Three fractions, and the only numbers in this repo that are written in two
  # languages on purpose. The art puts its instrument's centre at
  # `instrumentX` x `instrumentY` of whatever canvas it is composed on, with its
  # outer ring at `instrumentR` of the canvas's SHORTER side; shell/jv-wall
  # anchors the ember it moves over the art at the same three, and
  # tools/tests/test_wallshots.py compares the numbers rather than trusting two
  # comments to agree.
  #
  # Until PLAN E9 they only agreed by accident, and on 16:9 only. The art was one
  # 2560x1440 drawing and `resvg --width 2560 --height 1080` over it kept the top
  # 1080 rows — so the instrument stayed at y=980 while the shell anchored at
  # 68.1% of an 1080 px surface (y=735), 245 px away, and the wordmark at y=1330
  # was not in the file at all. Every render below is now COMPOSED at its own
  # geometry instead: same drawing, laid out for that canvas, so the fractions are
  # true by construction on every aspect ratio rather than on the one the SVG
  # happened to be authored at. docs/wall/06-ultrawide.png is the before picture.
  instrumentX = 0.734;
  instrumentY = 0.681;
  instrumentR = 0.39;

  # The rest of the instrument, as multiples of that outer ring rather than as
  # pixels: the two inner rings, and the glow that is wider than all of them.
  # They were 300, 430 and 620 against an outer 560, and these are those ratios —
  # a drawing that keeps its proportions at every size is the whole point.
  ringMid = 430.0 / 560.0;
  ringInner = 300.0 / 560.0;
  ringGlow = 620.0 / 560.0;

  # And the two things that do NOT scale with the canvas, because they are not
  # part of the composition: the wordmark sits a fixed distance up from the
  # bottom-left corner (type is type — a 46 px face is 46 px on every monitor,
  # and §06's faces are declared in px), and the grid is a texture at a fixed
  # pitch. Both were already absolute; naming them is what makes that a decision
  # instead of a leftover.
  wordmarkUp = 110;
  subtitleUp = 68;

  # AND THE GATE THAT READS THE PIXELS BACK (PLAN E11). `tools/artsample.py`
  # decodes each PNG this builder writes and samples the three fractions above in
  # the raster — because until it existed nothing in this repo had ever opened a
  # render of this art, and E9 shipped a build where the drawing had collapsed
  # into the top-left corner while resvg, this package and every gate exited 0.
  # The decoder is the contact sheet's, unchanged, which is why this is two files
  # and not a dependency: pure Python, and about a microsecond per pixel.
  sampler = ../../tools/artsample.py;
  decoder = ../../tools/hudsheet.py;

  # --- AND WHICH CANVASES ARE COMPOSED, WHICH IS NOW ASKED (PLAN E10) -------
  #
  # Every geometry below comes out of the `outputs` argument. The three throws
  # are the whole reason this is fifteen lines instead of one `map`: each of
  # them is a way for a bad declaration to produce a wallpaper that BUILDS.
  # `width = "2560"` (a string, easy to type in a file full of quoted refresh
  # rates) interpolates to `2560` and renders correctly, and then `lib.unique`
  # stops de-duplicating the two identical 1080p panels because 1920 and "1920"
  # are different values. `width = 0` reaches resvg, which rasterizes a 0 px
  # PNG and exits 0. And an empty list renders nothing but the primary art,
  # which is a machine with no monitors.
  named = o: o.name or "an unnamed entry";

  geometry =
    o:
    if !(builtins.isInt (o.width or null)) || !(builtins.isInt (o.height or null)) then
      throw ''
        pkgs/jarvis-wallpaper was handed the output "${named o}" without an
        integer width and height. A quoted "2560" renders the same PNG and then
        compares unequal to the int 2560, so two identical panels stop being one
        composition; write the pixels as numbers.''
    else if o.width < 1 || o.height < 1 then
      throw ''
        pkgs/jarvis-wallpaper was handed the output "${named o}" at
        ${toString o.width}x${toString o.height}. resvg rasterizes a zero-sized
        canvas without complaining and the desktop would show nothing.''
    else
      "${toString o.width}x${toString o.height}";

  # Emptiness is checked HERE, in the binding both of the two below go through,
  # rather than beside either of them. An empty list has no primary either, so
  # the `primary` throw would fire first and report "0 outputs with primary =
  # true" about a declaration whose actual problem is that it declares nothing.
  declared =
    if outputs != [ ] then
      outputs
    else
      throw ''
        pkgs/jarvis-wallpaper was handed an empty `outputs` list. The art is
        composed per output; with none declared there is nothing to compose for,
        and the fallback art alone is a desktop that scales and crops on every
        monitor.'';

  geometries = lib.unique (map geometry declared);

  # The PRIMARY output, whose geometry `jarvisos.png` is composed at — the art
  # the lock screen shows (pkgs/jv-lock) and the art shell/jv-wall falls back to
  # and crops on any geometry not in the list above. It is declared rather than
  # inferred: "the biggest one" would silently move the lock screen's image the
  # day a bigger panel is plugged in beside the one a human is looking at.
  primaries = builtins.filter (o: o.primary or false) declared;
  primary =
    if builtins.length primaries == 1 then
      builtins.head primaries
    else
      throw ''
        pkgs/jarvis-wallpaper needs exactly one output with `primary = true`, and
        was handed ${toString (builtins.length primaries)} of them
        (${lib.concatMapStringsSep ", " named declared}). The primary's geometry
        is what jarvisos.png is composed at, which is the lock screen's image and
        every undeclared monitor's fallback.'';
in
runCommand "jarvis-wallpaper"
  { nativeBuildInputs = [ resvg python3 ]; }
  ''
    mkdir -p "$out/share/backgrounds"
    fonts="${jetbrains-mono}/share/fonts"
    # COMPOSE, NEVER SCALE (PLAN E9). One function, called once per geometry,
    # that writes an SVG laid out for exactly that canvas: the instrument at the
    # three fractions above, the wordmark a fixed distance up from the corner,
    # the grid at its fixed pitch. resvg then rasterizes each one at its own
    # declared size, so there is no `--width`, no `--height`, no
    # `preserveAspectRatio` and nothing anywhere in this package that scales,
    # fits or crops a drawing. That is what makes the art's instrument land on
    # the shell's anchor on an aspect ratio nobody authored for.
    #
    # awk does the arithmetic because a shell has no floats, and it prints
    # `name=value` for the shell to take back rather than printing the SVG
    # itself: the drawing stays one readable heredoc that a person can edit,
    # which is the whole reason there is no PNG checked in.
    compose() {
      local w=$1 h=$2 svg=$3 numbers
      # AND IF THE ARITHMETIC FAILS, STOP — which is here because it did not.
      # `-v sub=...` names a gawk builtin, gawk refused the whole program with
      # one line on stderr, `eval ""` set nothing, and every coordinate in the
      # drawing below expanded to the empty string: `translate( )`, `r=""`,
      # `y=""`. resvg IGNORES an invalid attribute rather than failing, so it
      # rendered a wallpaper with the instrument collapsed into the top-left
      # corner and exited 0, and so did this build. It is exactly the silent
      # substitution the font check at the bottom of this file refuses, one
      # level up, so it is refused the same way.
      numbers=$(awk -v w="$w" -v h="$h" \
                  -v fx=${toString instrumentX} \
                  -v fy=${toString instrumentY} \
                  -v fr=${toString instrumentR} \
                  -v km=${toString ringMid} \
                  -v ki=${toString ringInner} \
                  -v kg=${toString ringGlow} \
                  -v wordUp=${toString wordmarkUp} \
                  -v subUp=${toString subtitleUp} 'BEGIN {
        # The instrument: centre at a fraction of the canvas, radii at a
        # fraction of its shorter side, so a wide canvas gets a wider field
        # around the same-sized instrument rather than a bigger instrument.
        m = (w < h) ? w : h;
        ro = m * fr;
        printf "cx=%.2f cy=%.2f\n", w * fx, h * fy;
        printf "ro=%.2f rm=%.2f ri=%.2f rg=%.2f\n", ro, ro * km, ro * ki, ro * kg;
        # The comet arc, drawn on the outer ring from twelve oclock: the solid
        # stroke to 45 degrees and the fainter trail on to 60. sin/cos written
        # out because these are two fixed angles, not a sweep.
        printf "ax=%.2f ay=%.2f bx=%.2f by=%.2f\n", \
               ro * 0.707107, -ro * 0.707107, ro * 0.866025, -ro * 0.5;
        # The teal tick, on the middle ring, from nine oclock round to 135.
        printf "tx=%.2f ty=%.2f\n", -ro * km * 0.707107, ro * km * 0.707107;
        # And the words, up from the bottom edge rather than down from the top:
        # a wordmark belongs to the corner it sits in.
        printf "wordY=%d subY=%d\n", h - wordUp, h - subUp;
      }') || exit 1
      eval "$numbers"
      if [ -z "$cx" ] || [ -z "$ro" ] || [ -z "$wordY" ]; then
        echo "jarvis-wallpaper: the composer produced no coordinates for" >&2
        echo "$w by $h — the drawing below would be a page of empty attributes" >&2
        echo "that resvg rasterizes without complaining." >&2
        exit 1
      fi
      cat > "$svg" <<SVG
    <svg xmlns="http://www.w3.org/2000/svg" width="$w" height="$h" viewBox="0 0 $w $h" font-family="${monoFamily}, monospace">
      <defs>
        <radialGradient id="ground" cx="62%" cy="58%" r="75%">
          <stop offset="0" stop-color="${ground}"/>
          <stop offset="1" stop-color="${groundDeep}"/>
        </radialGradient>
        <radialGradient id="ember" cx="50%" cy="50%" r="50%">
          <stop offset="0" stop-color="${ember}" stop-opacity="0.30"/>
          <stop offset="1" stop-color="${ember}" stop-opacity="0"/>
        </radialGradient>
        <pattern id="grid" width="64" height="64" patternUnits="userSpaceOnUse">
          <path d="M64 0H0V64" fill="none" stroke="${line}" stroke-opacity="0.14" stroke-width="1"/>
        </pattern>
      </defs>

      <rect width="$w" height="$h" fill="url(#ground)"/>
      <rect width="$w" height="$h" fill="url(#grid)"/>

      <!-- the instrument: concentric rings, lower-right, mostly off-canvas -->
      <g transform="translate($cx $cy)" fill="none">
        <circle r="$rg" fill="url(#ember)"/>
        <circle r="$ri" stroke="${line}" stroke-width="1.5"/>
        <circle r="$rm" stroke="${lineSoft}" stroke-width="1.5"/>
        <circle r="$ro" stroke="${line}" stroke-width="1"/>
        <circle r="$rm" stroke="${text3}" stroke-opacity="0.28" stroke-width="6" stroke-dasharray="2 26"/>
        <!-- ember comet arc: the one warm signal -->
        <path d="M 0 -$ro A $ro $ro 0 0 1 $bx $by" stroke="${ember}" stroke-opacity="0.22" stroke-width="4" stroke-linecap="round"/>
        <path d="M 0 -$ro A $ro $ro 0 0 1 $ax $ay" stroke="${ember}" stroke-width="6" stroke-linecap="round"/>
        <circle cx="0" cy="-$ro" r="9" fill="${ember}"/>
        <!-- teal secondary tick -->
        <path d="M -$rm 0 A $rm $rm 0 0 0 $tx $ty" stroke="${teal}" stroke-opacity="0.5" stroke-width="3" stroke-linecap="round"/>
        <!-- reticle core -->
        <circle r="20" stroke="${ember}" stroke-opacity="0.7" stroke-width="1.5"/>
        <circle r="6" fill="${ember}"/>
      </g>

      <!-- wordmark, bottom-left, quiet -->
      <text x="120" y="$wordY" font-size="46" font-weight="700" letter-spacing="2" fill="${text}">Jarvis<tspan fill="${ember}">OS</tspan></text>
      <text x="122" y="$subY" font-size="20" letter-spacing="8" fill="${text3}">// NODE ARES</text>
    </svg>
    SVG
    }

    # THE PRIMARY ART, at the geometry of the output declared `primary = true`
    # (${named primary}, ${geometry primary}). It is also the FALLBACK: an
    # output with no bespoke render below gets this file, and shell/jv-wall
    # crops it to fit — the one path where the art is scaled after all, which is
    # why that shell derives its anchor from where the crop actually put the
    # drawing rather than from a percentage of its own surface.
    compose ${toString primary.width} ${toString primary.height} wp.svg
    resvg --skip-system-fonts --use-fonts-dir "$fonts" \
      wp.svg "$out/share/backgrounds/jarvisos.png" 2>resvg.log
    cat resvg.log

    # PER-OUTPUT RENDERS (PLAN D10, composed rather than rasterized-and-cropped
    # since E9, and one per DECLARED output since E10). `swaybg -m fill` scaling
    # one drawing onto ares' two 1080p panels cropped the instrument and the
    # wordmark by an amount nobody chose; the first fix gave each connected
    # geometry its own file, and this one makes each of those files its own
    # COMPOSITION. jv-wall picks the file matching its screen.
    #
    # The list is the `outputs` argument, de-duplicated — ares' two 1080p panels
    # are one composition — so there is no geometry in this package that no
    # surface asked for, and a monitor added to the declaration has bespoke art
    # on the next rebuild.
    for geom in ${lib.concatStringsSep " " geometries}; do
      w=''${geom%x*}; h=''${geom#*x}
      compose "$w" "$h" "$geom.svg"
      resvg --skip-system-fonts --use-fonts-dir "$fonts" \
        "$geom.svg" "$out/share/backgrounds/jarvisos-$geom.png" 2>>resvg.log
    done

    # NOW LOOK AT WHAT WAS DRAWN (PLAN E11), which nothing in this repo had ever
    # done. Six renders, six pixels each: the reticle at the instrument's centre
    # and the comet's head one outer ring above it must be the ember exactly —
    # both are absolute-radius opaque discs, so the sample lands inside a solid
    # fill at every geometry — and the four corners of the field must still be
    # the field, cool and no brighter than the grid's own hairline.
    #
    # The fractions and the colours are the SAME BINDINGS the drawing above is
    # composed from, interpolated rather than restated: a checker pointed at a
    # hand-written 0.734 would keep passing the day somebody edits `instrumentX`,
    # and a hex literal here would be one more place a colour lives (invariant 9).
    # tools/tests/test_artsample.py is the third party that holds this call to
    # both, since neither this file nor the checker can say it about itself.
    #
    # It is pointed at the OUTPUT DIRECTORY and not at a list of names, so the
    # geometry the loop above gains next is checked without anybody remembering —
    # and a glob that matches nothing is an error inside the sampler rather than
    # an empty green.
    mkdir -p sampler
    cp ${decoder} sampler/hudsheet.py
    cp ${sampler} sampler/artsample.py
    python3 sampler/artsample.py \
      --at ${toString instrumentX},${toString instrumentY} \
      --radius ${toString instrumentR} \
      --warm '${ember}' \
      --field '${ground}' --field '${groundDeep}' --field '${line}' \
      "$out/share/backgrounds"/*.png

    # A font family that does not resolve is not an error to resvg: it warns,
    # substitutes whatever it can find, and exits 0 — so the wordmark quietly
    # changes face and the PNG still builds. That is the same silent
    # substitution modules/fonts.nix refuses one level up (it makes fontconfig
    # answer for every declared family at build time), and the wallpaper is
    # the one surface that bakes a face into a raster, where nothing can
    # notice later. Refuse it here.
    if grep -q 'No match for' resvg.log; then
      echo "jarvis-wallpaper: resvg found no font for the theme's mono face" >&2
      echo "(${monoFamily}); the wordmark would silently be set in something" >&2
      echo "else. Bind the face theme.toml names into this package." >&2
      exit 1
    fi
  ''
