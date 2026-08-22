# JarvisOS GRUB theme derivation: theme.txt + three legible pf2 fonts
# generated at 2560x1440-appropriate sizes. DejaVu is used because it is
# always in nixpkgs and renders cleanly at boot; Phase 5 can swap in the
# blueprint's Archivo / JetBrains Mono here without touching the layout.
{ runCommand, grub2, dejavu_fonts }:
runCommand "jarvisos-grub-theme" { nativeBuildInputs = [ grub2 ]; } ''
  mkdir -p "$out"
  ttf=${dejavu_fonts}/share/fonts/truetype
  # --name sets the pf2 internal family name so theme.txt can reference
  # it deterministically (grub matches on the exact name).
  grub-mkfont --name="title" -s 48 -o "$out/title.pf2" "$ttf/DejaVuSans-Bold.ttf"
  grub-mkfont --name="item"  -s 28 -o "$out/item.pf2"  "$ttf/DejaVuSans.ttf"
  grub-mkfont --name="hint"  -s 18 -o "$out/hint.pf2"  "$ttf/DejaVuSansMono.ttf"
  grub-mkfont --name="mono"  -s 18 -o "$out/mono.pf2"  "$ttf/DejaVuSansMono.ttf"
  cp ${./theme.txt} "$out/theme.txt"
''
