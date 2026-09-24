# The faces `personality/theme.toml` names, declared so that they exist.
#
# theme.toml has named Archivo and JetBrains Mono since A2, and until this
# module nothing installed either of them: the HUD asked for "JetBrains Mono",
# fontconfig found no such family, and quietly substituted whatever it liked.
# That is the worst shape a missing dependency can take — it does not fail, it
# just renders in a different face, and a versioned identity (invariant 9)
# cannot survive drifting silently.
#
# The family names are NOT written here. They are read out of theme.toml with
# `builtins.fromTOML`, the way `tools/gen_theme_qml.py` reads it for the HUD:
# one source of truth, so renaming a face in theme.toml moves the system with
# it instead of leaving the two halves to disagree. What lives here is the
# binding from a family NAME to something that provides it — and every step
# throws rather than guesses, because every guess here is invisible.
{ lib, pkgs, ... }:
let
  theme = builtins.fromTOML (builtins.readFile ../personality/theme.toml);

  # `[type] family_<role>` -> the face it names.
  # { sans = "Archivo"; mono = "JetBrains Mono"; }
  facesByRole = lib.mapAttrs' (key: family: lib.nameValuePair (lib.removePrefix "family_" key) family) (
    lib.filterAttrs (key: _: lib.hasPrefix "family_" key) theme.type
  );

  # Which fontconfig generic family each role stands for. theme.toml says
  # "fallbacks are the generic families"; this is where that sentence becomes
  # something the system actually does.
  genericOf = {
    sans = "sansSerif";
    mono = "monospace";
  };

  # The ONE place a family name is bound to something that provides it. Keep
  # it exhaustive in both directions: tools/tests holds this table against
  # theme.toml, and `assertions` below refuses an entry nothing asks for.
  providerOf = {
    "Archivo" = pkgs.callPackage ../pkgs/archivo { };
    "JetBrains Mono" = pkgs.jetbrains-mono;
  };

  genericFor =
    role:
    genericOf.${role} or (throw ''
      personality/theme.toml names a face for the role "${role}" (family_${role}),
      but modules/fonts.nix does not know which fontconfig generic family that
      role falls back to. Add it to genericOf — a face with no generic behind it
      has no fallback at all.'');

  packageFor =
    family:
    providerOf.${family} or (throw ''
      personality/theme.toml asks for the font family "${family}", and nothing in
      modules/fonts.nix provides it. An uninstalled family does not fail at
      runtime — fontconfig substitutes something else and the look changes with
      nobody told. Package the face and bind it in providerOf.'');

  # A font package is only worth installing if it really reports the family
  # name the theme asks for; the name lives inside the font binary and nothing
  # about a package's name or its file names guarantees it. So the system
  # installs the face it CHECKED — this is what lands in fonts.packages, and
  # its build fails if fontconfig, the same thing that will resolve the name
  # at runtime, cannot find the family in there.
  #
  # It also installs only the OUTLINE formats. jetbrains-mono ships every face
  # three times — opentype, truetype and WOFF2 — and fontconfig indexes the
  # web font like any other: against the system this module first produced,
  # `fc-match monospace` answered JetBrainsMono-Regular.woff2. Whether a WOFF2
  # renders at all depends on how the FreeType doing the rendering was built,
  # so shipping one is the same silent substitution this module exists to
  # stop, one layer further in. A face nothing can be sure of drawing has no
  # business in a font path.
  #
  # "The package PROVIDES the family", not "every file in it is that family":
  # upstream packages legitimately carry siblings (jetbrains-mono ships
  # JetBrains Mono NL next to JetBrains Mono), and refusing those would be
  # refusing the packaging rather than catching a drift.
  checkedFace =
    family:
    let
      slug = lib.strings.sanitizeDerivationName family;
    in
    pkgs.runCommand "jv-face-${slug}" { nativeBuildInputs = [ pkgs.fontconfig ]; } ''
      # fc-scan reads a font file and needs neither a font cache nor a system
      # config to do it; without these it complains about both, five lines per
      # face, and buries whatever this check actually found.
      export XDG_CACHE_HOME="$TMPDIR/fontconfig-cache"
      export FONTCONFIG_FILE=${pkgs.fontconfig.out}/etc/fonts/fonts.conf

      mkdir -p $out/share/fonts/${slug}
      find -L ${packageFor family}/share/fonts -type f \
          \( -iname '*.ttf' -o -iname '*.otf' -o -iname '*.ttc' \) \
          -exec ln -s -t $out/share/fonts/${slug} {} +

      faces=$(find -L $out/share/fonts -type f | sort)
      if [ -z "$faces" ]; then
        echo 'fonts: the package bound to "${family}" carries no outline font file at all' >&2
        exit 1
      fi

      families=$(printf '%s\n' "$faces" \
        | xargs -r -d '\n' -n1 fc-scan --format '%{family}\n' \
        | tr ',' '\n' | sort -u)
      if ! printf '%s\n' "$families" | grep -qxF '${family}'; then
        echo 'fonts: personality/theme.toml asks for "${family}", but the package' >&2
        echo '       bound to it provides only:' >&2
        printf '%s\n' "$families" | sed 's/^/         /' >&2
        exit 1
      fi
    '';

  unclaimed = lib.subtractLists (lib.attrValues facesByRole) (lib.attrNames providerOf);
in
{
  # Generic families must resolve to SOMETHING, or the fallback theme.toml
  # promises is a fallback to nothing. This is also why the machine could
  # render text at all until now: nothing here declared a single font.
  fonts.enableDefaultPackages = true;

  fonts.packages = lib.unique (lib.mapAttrsToList (_: checkedFace) facesByRole);

  # sansSerif -> [ "Archivo" ], monospace -> [ "JetBrains Mono" ]. Built by
  # zipping rather than by listToAttrs so that two roles sharing a generic
  # become a fallback chain instead of one of them silently winning.
  fonts.fontconfig.defaultFonts = lib.zipAttrsWith (_: families: families) (
    lib.mapAttrsToList (role: family: { ${genericFor role} = family; }) facesByRole
  );

  assertions = [
    {
      assertion = unclaimed == [ ];
      message =
        "modules/fonts.nix binds a provider for ${lib.concatStringsSep ", " unclaimed}, "
        + "which personality/theme.toml does not name. A face installed for no "
        + "declared reason is one more family fontconfig can substitute — drop the "
        + "binding, or name the face in theme.toml.";
    }
  ];
}
