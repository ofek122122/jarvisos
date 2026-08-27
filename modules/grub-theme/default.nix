# JarvisOS GRUB theme derivation.
#   - background.png: rendered from background.svg by resvg at build time
#     (no binary asset checked in; edit the SVG and rebuild to restyle).
#   - three pf2 fonts cut from JetBrains Mono — the blueprint's mono face,
#     matching the HUD. grub-mkfont --name sets the pf2 internal family so
#     theme.txt can reference it deterministically (jbitem / jbsel / jbhint).
# Fonts are located with `find` so the exact JetBrains Mono file names
# don't have to be hard-coded.
{ runCommand, grub2, jetbrains-mono, resvg }:
runCommand "jarvisos-grub-theme" { nativeBuildInputs = [ grub2 resvg ]; } ''
  mkdir -p "$out"
  fonts="${jetbrains-mono}/share/fonts"

  bold=$(find "$fonts" -iname '*Bold.ttf'    ! -iname '*Italic*' | sort | head -1)
  reg=$( find "$fonts" -iname '*Regular.ttf' ! -iname '*Italic*' | sort | head -1)
  med=$( find "$fonts" -iname '*Medium.ttf'  ! -iname '*Italic*' | sort | head -1)
  : "''${med:=$reg}"

  if [ -z "$reg" ] || [ -z "$bold" ]; then
    echo "grub-theme: JetBrains Mono Regular/Bold not found under $fonts" >&2
    exit 1
  fi

  grub-mkfont --name="jbitem" -s 30 -o "$out/jbitem.pf2" "$reg"
  grub-mkfont --name="jbsel"  -s 30 -o "$out/jbsel.pf2"  "$bold"
  grub-mkfont --name="jbhint" -s 18 -o "$out/jbhint.pf2" "$med"

  # Render the designed background. Fonts resolve ONLY from JetBrains Mono
  # so the build is deterministic and never picks up a system face.
  resvg --skip-system-fonts --use-fonts-dir "$fonts" \
    ${./background.svg} "$out/background.png"

  cp ${./theme.txt} "$out/theme.txt"
''
