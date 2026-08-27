# JarvisOS Plymouth theme — a "script" module theme whose assets are all
# rendered from SVG by resvg at build time (nothing binary is checked in;
# restyle by editing the SVG heredocs below). Text is baked to PNG so the
# initrd needs no fonts. Spins are pre-rendered frames because Plymouth
# sprites can't rotate.
{ runCommand, resvg, jetbrains-mono }:
runCommand "jarvisos-plymouth-theme"
  { nativeBuildInputs = [ resvg ]; }
  ''
    t="$out/share/plymouth/themes/jarvis"
    mkdir -p "$t"
    fonts="${jetbrains-mono}/share/fonts"

    render() { resvg --skip-system-fonts --use-fonts-dir "$fonts" "$1" "$2"; }

    # ---- soft ember glow (opacity animated at runtime) ----
    cat > glow.svg <<'SVG'
    <svg xmlns="http://www.w3.org/2000/svg" width="760" height="760">
      <defs><radialGradient id="g" cx="50%" cy="50%" r="50%">
        <stop offset="0" stop-color="#F0714A" stop-opacity="0.5"/>
        <stop offset="1" stop-color="#F0714A" stop-opacity="0"/>
      </radialGradient></defs>
      <circle cx="380" cy="380" r="300" fill="url(#g)"/>
    </svg>
    SVG
    render glow.svg "$t/glow.png"

    # ---- static instrument: rings, crosshair, graduations, captions ----
    cat > rings.svg <<'SVG'
    <svg xmlns="http://www.w3.org/2000/svg" width="760" height="760" font-family="JetBrains Mono, monospace">
      <g transform="translate(380 380)" fill="none">
        <circle r="120" stroke="#26323B" stroke-width="1"/>
        <circle r="188" stroke="#212B32" stroke-width="1"/>
        <circle r="250" stroke="#26323B" stroke-width="1"/>
        <circle r="330" stroke="#26323B" stroke-width="1.5"/>
        <circle r="250" stroke="#64747F" stroke-opacity="0.35" stroke-width="6" stroke-dasharray="2 22"/>
        <g stroke="#64747F" stroke-opacity="0.3" stroke-width="1">
          <line x1="-330" y1="0" x2="-44" y2="0"/><line x1="44" y1="0" x2="330" y2="0"/>
          <line x1="0" y1="-330" x2="0" y2="-44"/><line x1="0" y1="44" x2="0" y2="330"/>
        </g>
        <g fill="#4A5762" font-size="15" letter-spacing="2" font-weight="500">
          <text x="140" y="-236">NODE // ARES</text>
          <text x="-330" y="318">0xEF1 // BOOT</text>
        </g>
      </g>
    </svg>
    SVG
    render rings.svg "$t/rings.png"

    # ---- reticle core (opacity animated) ----
    cat > core.svg <<'SVG'
    <svg xmlns="http://www.w3.org/2000/svg" width="200" height="200">
      <g transform="translate(100 100)">
        <circle r="18" fill="none" stroke="#F0714A" stroke-opacity="0.7" stroke-width="1.5"/>
        <circle r="5" fill="#F0714A"/>
      </g>
    </svg>
    SVG
    render core.svg "$t/core.png"

    # ---- wordmark ----
    cat > wordmark.svg <<'SVG'
    <svg xmlns="http://www.w3.org/2000/svg" width="820" height="160" font-family="JetBrains Mono, monospace">
      <text x="18" y="116" font-size="110" font-weight="700" letter-spacing="1" fill="#E6ECF0">Jarvis<tspan fill="#F0714A">OS</tspan></text>
    </svg>
    SVG
    render wordmark.svg "$t/wordmark.png"

    # ---- captions ----
    cat > label_boot.svg <<'SVG'
    <svg xmlns="http://www.w3.org/2000/svg" width="920" height="44" font-family="JetBrains Mono, monospace">
      <text x="460" y="30" text-anchor="middle" font-size="22" letter-spacing="6" font-weight="500" fill="#9BAAB4">INITIALISING JARVISOS</text>
    </svg>
    SVG
    render label_boot.svg "$t/label_boot.png"

    cat > label_unlock.svg <<'SVG'
    <svg xmlns="http://www.w3.org/2000/svg" width="920" height="44" font-family="JetBrains Mono, monospace">
      <text x="460" y="30" text-anchor="middle" font-size="22" letter-spacing="5" font-weight="500" fill="#F0714A">ENTER PASSPHRASE // UNLOCK JARVIS ROOT</text>
    </svg>
    SVG
    render label_unlock.svg "$t/label_unlock.png"

    # ---- passphrase bullet ----
    cat > bullet.svg <<'SVG'
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"><circle cx="12" cy="12" r="7" fill="#F0714A"/></svg>
    SVG
    render bullet.svg "$t/bullet.png"

    # ---- spinner: 36 frames of an ember comet arc, rotated in 10° steps ----
    cat > spin.tmpl <<'SVG'
    <svg xmlns="http://www.w3.org/2000/svg" width="760" height="760">
      <g transform="rotate(@ANGLE@ 380 380)">
        <path d="M 380 50 A 330 330 0 0 1 660 250" fill="none" stroke="#F0714A" stroke-opacity="0.22" stroke-width="3" stroke-linecap="round"/>
        <path d="M 380 50 A 330 330 0 0 1 601 138" fill="none" stroke="#F0714A" stroke-width="5" stroke-linecap="round"/>
        <circle cx="380" cy="50" r="7" fill="#F79070"/>
      </g>
    </svg>
    SVG
    for i in $(seq 0 35); do
      a=$(( i * 10 ))
      sed "s/@ANGLE@/$a/" spin.tmpl > spin.svg
      render spin.svg "$t/progress-$i.png"
    done

    # ---- theme manifest + script (patch @THEMEDIR@ to the store path) ----
    sed "s|@THEMEDIR@|$t|g" ${./jarvis.plymouth} > "$t/jarvis.plymouth"
    cp ${./jarvis.script} "$t/jarvis.script"
  ''
