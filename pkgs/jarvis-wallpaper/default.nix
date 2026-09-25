# The JarvisOS desktop wallpaper — rendered from SVG by resvg at build time
# (no binary blob checked in; restyle by editing the heredoc). Blueprint §06:
# a dark instrument at rest — deep ground, one ember arc, earned emptiness.
{ runCommand, resvg, jetbrains-mono }:
runCommand "jarvis-wallpaper"
  { nativeBuildInputs = [ resvg ]; }
  ''
    mkdir -p "$out/share/backgrounds"
    fonts="${jetbrains-mono}/share/fonts"
    cat > wp.svg <<'SVG'
    <svg xmlns="http://www.w3.org/2000/svg" width="2560" height="1440" font-family="JetBrains Mono, monospace">
      <defs>
        <radialGradient id="ground" cx="62%" cy="58%" r="75%">
          <stop offset="0" stop-color="#0C1116"/>
          <stop offset="0.6" stop-color="#090D12"/>
          <stop offset="1" stop-color="#05080B"/>
        </radialGradient>
        <radialGradient id="ember" cx="50%" cy="50%" r="50%">
          <stop offset="0" stop-color="#F0714A" stop-opacity="0.30"/>
          <stop offset="1" stop-color="#F0714A" stop-opacity="0"/>
        </radialGradient>
        <pattern id="grid" width="64" height="64" patternUnits="userSpaceOnUse">
          <path d="M64 0H0V64" fill="none" stroke="#26323B" stroke-opacity="0.14" stroke-width="1"/>
        </pattern>
      </defs>

      <rect width="2560" height="1440" fill="url(#ground)"/>
      <rect width="2560" height="1440" fill="url(#grid)"/>

      <!-- the instrument: concentric rings, lower-right, mostly off-canvas -->
      <g transform="translate(1880 980)" fill="none">
        <circle r="620" fill="url(#ember)"/>
        <circle r="300" stroke="#26323B" stroke-width="1.5"/>
        <circle r="430" stroke="#212B32" stroke-width="1.5"/>
        <circle r="560" stroke="#26323B" stroke-width="1"/>
        <circle r="430" stroke="#64747F" stroke-opacity="0.28" stroke-width="6" stroke-dasharray="2 26"/>
        <!-- ember comet arc: the one warm signal -->
        <path d="M 0 -560 A 560 560 0 0 1 485 -280" stroke="#F0714A" stroke-opacity="0.22" stroke-width="4" stroke-linecap="round"/>
        <path d="M 0 -560 A 560 560 0 0 1 396 -396" stroke="#F0714A" stroke-width="6" stroke-linecap="round"/>
        <circle cx="0" cy="-560" r="9" fill="#F79070"/>
        <!-- teal secondary tick -->
        <path d="M -430 0 A 430 430 0 0 0 -304 304" stroke="#4FB8BF" stroke-opacity="0.5" stroke-width="3" stroke-linecap="round"/>
        <!-- reticle core -->
        <circle r="20" stroke="#F0714A" stroke-opacity="0.7" stroke-width="1.5"/>
        <circle r="6" fill="#F0714A"/>
      </g>

      <!-- wordmark, bottom-left, quiet -->
      <text x="120" y="1330" font-size="46" font-weight="700" letter-spacing="2" fill="#E6ECF0">Jarvis<tspan fill="#F0714A">OS</tspan></text>
      <text x="122" y="1372" font-size="20" letter-spacing="8" fill="#64747F">// NODE ARES</text>
    </svg>
    SVG
    resvg --skip-system-fonts --use-fonts-dir "$fonts" wp.svg "$out/share/backgrounds/jarvisos.png"
  ''
