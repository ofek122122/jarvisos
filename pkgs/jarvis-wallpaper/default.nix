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
  runCommand,
  resvg,
  jetbrains-mono,
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
in
runCommand "jarvis-wallpaper"
  { nativeBuildInputs = [ resvg ]; }
  ''
    mkdir -p "$out/share/backgrounds"
    fonts="${jetbrains-mono}/share/fonts"
    cat > wp.svg <<'SVG'
    <svg xmlns="http://www.w3.org/2000/svg" width="2560" height="1440" font-family="${monoFamily}, monospace">
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

      <rect width="2560" height="1440" fill="url(#ground)"/>
      <rect width="2560" height="1440" fill="url(#grid)"/>

      <!-- the instrument: concentric rings, lower-right, mostly off-canvas -->
      <g transform="translate(1880 980)" fill="none">
        <circle r="620" fill="url(#ember)"/>
        <circle r="300" stroke="${line}" stroke-width="1.5"/>
        <circle r="430" stroke="${lineSoft}" stroke-width="1.5"/>
        <circle r="560" stroke="${line}" stroke-width="1"/>
        <circle r="430" stroke="${text3}" stroke-opacity="0.28" stroke-width="6" stroke-dasharray="2 26"/>
        <!-- ember comet arc: the one warm signal -->
        <path d="M 0 -560 A 560 560 0 0 1 485 -280" stroke="${ember}" stroke-opacity="0.22" stroke-width="4" stroke-linecap="round"/>
        <path d="M 0 -560 A 560 560 0 0 1 396 -396" stroke="${ember}" stroke-width="6" stroke-linecap="round"/>
        <circle cx="0" cy="-560" r="9" fill="${ember}"/>
        <!-- teal secondary tick -->
        <path d="M -430 0 A 430 430 0 0 0 -304 304" stroke="${teal}" stroke-opacity="0.5" stroke-width="3" stroke-linecap="round"/>
        <!-- reticle core -->
        <circle r="20" stroke="${ember}" stroke-opacity="0.7" stroke-width="1.5"/>
        <circle r="6" fill="${ember}"/>
      </g>

      <!-- wordmark, bottom-left, quiet -->
      <text x="120" y="1330" font-size="46" font-weight="700" letter-spacing="2" fill="${text}">Jarvis<tspan fill="${ember}">OS</tspan></text>
      <text x="122" y="1372" font-size="20" letter-spacing="8" fill="${text3}">// NODE ARES</text>
    </svg>
    SVG
    resvg --skip-system-fonts --use-fonts-dir "$fonts" \
      wp.svg "$out/share/backgrounds/jarvisos.png" 2>resvg.log
    cat resvg.log

    # PER-OUTPUT RENDERS (PLAN D10). The art above is composed for a 16:9
    # 2560x1440 field; `swaybg -m fill` scaling that onto ares' two 1080p
    # panels cropped the instrument and the wordmark by an amount nobody
    # chose. resvg can rasterize the SAME vector at another pixel size, so
    # each connected geometry gets its own correctly-composed file and
    # nothing is ever scaled. jv-wall picks the file matching its screen.
    for geom in 2560x1440 1920x1080 3840x2160 2560x1080 1366x768; do
      w=''${geom%x*}; h=''${geom#*x}
      resvg --skip-system-fonts --use-fonts-dir "$fonts" \
        --width "$w" --height "$h" \
        wp.svg "$out/share/backgrounds/jarvisos-$geom.png" 2>>resvg.log
    done

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
