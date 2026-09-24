# Archivo — the grotesque `personality/theme.toml` names as `family_sans`,
# and the blueprint's §06 face for words.
#
# nixpkgs has no `archivo`. The only packaged source is `google-fonts`, whose
# src is 1.1 GiB to download and 2.7 GiB unpacked even when overridden to a
# single family — on a machine that builds its own system and, during active
# development, never garbage-collects. So the face is pinned upstream
# instead: 66 MiB of source for 3.4 MiB of installed face, one rev, one hash.
#
# Upstream ships no tags and no releases, so the pin is a commit.
#
# Only the BASE width is installed. Upstream also carries Condensed,
# SemiCondensed, Expanded, SemiExpanded, ExtraCondensed and an "AAA"
# accessibility cut; theme.toml names none of them, and a family that is
# installed but never asked for is one more thing fontconfig can reach for
# when the face we did ask for is missing — which is the exact failure this
# package exists to make impossible.
{
  lib,
  stdenvNoCC,
  fetchFromGitHub,
  fontconfig,
}:

stdenvNoCC.mkDerivation {
  pname = "archivo";
  # Upstream carries no version anywhere in the tree; this is the pinned
  # commit's date, in the nixpkgs unstable-version convention.
  version = "0-unstable-2026-09-02";

  src = fetchFromGitHub {
    owner = "Omnibus-Type";
    repo = "Archivo";
    rev = "211127690e8ff106c36c935f7e5e697114cff103";
    hash = "sha256-2A7Nuk7JHfWawO3fAJRQTvXPIxfyLGrGW3UkPBa9i9M=";
  };

  dontConfigure = true;
  dontBuild = true;

  # `Archivo-*` and not `Archivo*`: the hyphen is what keeps
  # ArchivoCondensed-Regular.ttf and friends out.
  installPhase = ''
    runHook preInstall
    install -Dm444 fonts/ttf/Archivo-*.ttf -t $out/share/fonts/truetype
    runHook postInstall
  '';

  # A font package is only useful if it provides the family NAME the theme
  # asks for, and nothing about the file names guarantees that — the family
  # lives inside the binary. Ask fontconfig, the same thing that will have to
  # find it at runtime.
  doInstallCheck = true;
  nativeInstallCheckInputs = [ fontconfig ];
  installCheckPhase = ''
    runHook preInstallCheck

    # fc-scan reads a font file and needs neither a font cache nor a system
    # config to do it; without these it prints five lines of complaint per
    # face and buries whatever this check actually found.
    export XDG_CACHE_HOME="$TMPDIR/fontconfig-cache"
    export FONTCONFIG_FILE=${fontconfig.out}/etc/fonts/fonts.conf

    faces=$(find $out/share/fonts -type f -name '*.ttf' | sort)
    if [ -z "$faces" ]; then
      echo "archivo: installed no font file at all — did upstream move fonts/ttf?" >&2
      exit 1
    fi

    bad=""
    for face in $faces; do
      if ! fc-scan --format '%{family}\n' "$face" | tr ',' '\n' | grep -qxF 'Archivo'; then
        bad="$bad $face"
      fi
    done
    if [ -n "$bad" ]; then
      echo "archivo: these faces do not belong to the family 'Archivo':" >&2
      for face in $bad; do
        echo "  $(basename "$face") -> $(fc-scan --format '%{family}\n' "$face")" >&2
      done
      exit 1
    fi

    # The upright text face specifically: a package that installed only
    # Thin and Black would pass the check above and still render nothing
    # anyone asked for.
    regular=$out/share/fonts/truetype/Archivo-Regular.ttf
    if [ ! -f "$regular" ]; then
      echo "archivo: no Archivo-Regular.ttf — the family is installed without the face that reads as text" >&2
      exit 1
    fi
    if ! fc-scan --format '%{style}\n' "$regular" | tr ',' '\n' | grep -qxF 'Regular'; then
      echo "archivo: Archivo-Regular.ttf does not report a Regular style" >&2
      exit 1
    fi

    echo "archivo: $(echo "$faces" | wc -l) faces, all family 'Archivo'"
    runHook postInstallCheck
  '';

  meta = {
    description = "Archivo — grotesque sans by Omnibus-Type (base width only)";
    homepage = "https://github.com/Omnibus-Type/Archivo";
    license = lib.licenses.ofl;
    platforms = lib.platforms.all;
  };
}
