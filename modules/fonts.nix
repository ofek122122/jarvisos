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
{ config, lib, pkgs, ... }:
let
  theme = builtins.fromTOML (builtins.readFile ../personality/theme.toml);

  # `[type] family_<role>` -> the face it names.
  # { sans = "Archivo"; mono = "JetBrains Mono"; }
  facesByRole = lib.mapAttrs' (key: family: lib.nameValuePair (lib.removePrefix "family_" key) family) (
    lib.filterAttrs (key: _: lib.hasPrefix "family_" key) theme.type
  );

  # Which fontconfig generic family each role stands for. theme.toml says
  # "fallbacks are the generic families"; this is where that sentence becomes
  # something the system actually does. `option` is the name NixOS sets the
  # alias under, `alias` the name fontconfig itself answers to — they are not
  # always the same word, and the resolve check below has to ASK in
  # fontconfig's spelling.
  genericOf = {
    sans = {
      option = "sansSerif";
      alias = "sans-serif";
    };
    mono = {
      option = "monospace";
      alias = "monospace";
    };
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

  # role -> everything the rest of this file needs to say about that role:
  # the family theme.toml asked for, the generic fontconfig will be asked in
  # its place, and the ONE derivation that installs it. Built once so that the
  # thing `fonts.packages` installs and the thing the resolve check looks for
  # cannot be two different store paths.
  declared = lib.mapAttrs (role: family: {
    inherit family;
    generic = genericFor role;
    face = checkedFace family;
  }) facesByRole;

  # /etc/fonts as this configuration will really have it: the same list of
  # conf packages the fontconfig module links into the system. The check below
  # resolves against THIS, not against a config of its own invention — a test
  # that builds its own fontconfig setup proves something about that setup.
  fcEtc = pkgs.buildEnv {
    name = "jv-fonts-etc";
    paths = config.fonts.fontconfig.confPackages;
    ignoreCollisions = true;
  };

  # Everything above is about what gets INSTALLED. This is about what gets
  # ANSWERED — the only question the HUD actually asks. `checkedFace` proves a
  # family is present in a package; it says nothing about which file fontconfig
  # hands back when something asks for that name, and those are different
  # claims: the family can be present in three formats, and for fifteen
  # iterations the winner was a WOFF2.
  #
  # Two rules, both stated as properties rather than as a copy of the
  # mechanism that implements them (a gate that restates its implementation
  # passes whenever the implementation changes):
  #
  #   1. Every file in a face this module installs is an sfnt — raw TrueType,
  #      CFF or a collection — read from the file's own first four bytes. NOT
  #      from its extension, which is what `checkedFace`'s find filter goes by
  #      and therefore cannot be the witness for; and not from fc-scan's
  #      `%{fontformat}`, which reports a WOFF2 as plain "TrueType" whenever
  #      the FreeType doing the scanning was built with woff2 support. That is
  #      precisely the property at issue: whether a face renders depends on the
  #      library that opens it, so "some FreeType could read it" is not the
  #      question. Widen the find filter and this fails on content.
  #
  #   2. Asking for each declared family BY NAME, and for the generic it backs,
  #      returns that family, in a file this module linked. This is the whole
  #      promise of the module in one sentence, and it is the only one that
  #      covers `defaultFonts`: nothing else here checks that `monospace` ends
  #      up at JetBrains Mono rather than at DejaVu Sans Mono.
  resolveCheck =
    pkgs.runCommand "jv-fonts-resolve"
      {
        nativeBuildInputs = [ pkgs.fontconfig ];
      }
      ''
        export XDG_CACHE_HOME="$TMPDIR/fontconfig-cache"

        # The system's own fonts.conf, with the single edit that lets it run
        # before it is installed: it includes conf.d by the ABSOLUTE path
        # /etc/fonts/conf.d, and inside a build there is no /etc. Everything
        # else — rendering, rejections, the generated aliases, the font dirs,
        # the prebuilt caches — is read from the real thing.
        sed 's|/etc/fonts/conf.d|${fcEtc}/etc/fonts/conf.d|' \
            ${pkgs.fontconfig.out}/etc/fonts/fonts.conf > "$TMPDIR/fonts.conf"
        export FONTCONFIG_FILE="$TMPDIR/fonts.conf"

        fail=0

        # sfnt magic: 0x00010000 (TrueType), OTTO (CFF), ttcf (collection),
        # true (older Apple TrueType). A web font announces itself as wOFF or
        # wOF2 in the same four bytes.
        outlines() {
          local file magic
          for file in $(find -L "$1" -type f | sort); do
            magic=$(head -c 4 -- "$file" | od -An -tx1 | tr -d ' \n')
            case "$magic" in
              00010000 | 4f54544f | 74746366 | 74727565) ;;
              *)
                echo "fonts: $file is not an outline font (first bytes $magic)." >&2
                echo "       Only sfnt formats belong in the font path: whether" >&2
                echo "       anything else renders depends on how the reading" >&2
                echo "       FreeType was built, which is a coin flip nobody sees." >&2
                fail=1
                ;;
            esac
          done
        }

        # A generic is only a question if fontconfig has heard of it. Its
        # `49-sansserif.conf` answers ANY family it does not recognise with
        # the sans-serif default — so `fc-match sansSerif` cheerfully returns
        # Archivo, and asking the wrong word would look exactly like asking
        # the right one. fontconfig's OWN shipped configuration is the
        # vocabulary here, never the conf.d this module helped generate:
        # otherwise the answer comes from the same place as the question.
        generic() {
          if ! grep -qF -- "<family>$1</family>" \
               ${pkgs.fontconfig.out}/share/fontconfig/conf.avail/*.conf; then
            echo "fonts: fontconfig's own configuration never names '$1' as a" >&2
            echo "       family, so it is not a generic and asking for it proves" >&2
            echo "       nothing — an unknown family falls through to the" >&2
            echo "       sans-serif default and answers anyway." >&2
            fail=1
          fi
        }

        # $1 what to ask fontconfig for, $2 the family that must answer,
        # $3 the face directory the answering file must come from.
        resolves() {
          local got file
          got=$(fc-match -f '%{family}' "$1")
          file=$(fc-match -f '%{file}' "$1")
          if ! printf '%s\n' "$got" | tr ',' '\n' | grep -qxF "$2"; then
            echo "fonts: asking fontconfig for '$1' answers \"$got\", not \"$2\"." >&2
            echo "       personality/theme.toml asks for that family and the HUD" >&2
            echo "       will render in whatever this line says instead." >&2
            fail=1
          elif [ "''${file#$3/}" = "$file" ]; then
            echo "fonts: asking fontconfig for '$1' answers with" >&2
            echo "         $file" >&2
            echo "       which is not a file modules/fonts.nix installed for" >&2
            echo "       \"$2\" ($3). Some other package on the system is" >&2
            echo "       answering for this name." >&2
            fail=1
          else
            echo "fonts: $1 -> $file"
          fi
        }

        ${lib.concatMapStringsSep "\n" (d: ''
          outlines ${d.face}/share/fonts
          resolves ${lib.escapeShellArg d.family} ${lib.escapeShellArg d.family} ${d.face}/share/fonts
          generic ${lib.escapeShellArg d.generic.alias}
          resolves ${lib.escapeShellArg d.generic.alias} ${lib.escapeShellArg d.family} ${d.face}/share/fonts
        '') (lib.attrValues declared)}

        [ $fail -eq 0 ] || exit 1
        touch $out
      '';

  unclaimed = lib.subtractLists (lib.attrValues facesByRole) (lib.attrNames providerOf);
in
{
  # Generic families must resolve to SOMETHING, or the fallback theme.toml
  # promises is a fallback to nothing. This is also why the machine could
  # render text at all until now: nothing here declared a single font.
  fonts.enableDefaultPackages = true;

  fonts.packages = lib.unique (lib.mapAttrsToList (_: d: d.face) declared);

  # sansSerif -> [ "Archivo" ], monospace -> [ "JetBrains Mono" ]. Built by
  # zipping rather than by listToAttrs so that two roles sharing a generic
  # become a fallback chain instead of one of them silently winning.
  fonts.fontconfig.defaultFonts = lib.zipAttrsWith (_: families: families) (
    lib.mapAttrsToList (_: d: { ${d.generic.option} = d.family; }) declared
  );

  # Built by `nixos-rebuild build`, present in no closure: a check, not a
  # dependency. If the faces stop resolving, the build fails here rather than
  # on ares three weeks later in a face nobody chose.
  system.checks = [ resolveCheck ];

  assertions = [
    {
      # `confPackages`, which resolveCheck reads, is only populated while
      # fontconfig is enabled — and with it off nothing resolves a family
      # name at all, so the whole module would be installing faces into a
      # system that cannot find them.
      assertion = config.fonts.fontconfig.enable;
      message =
        "modules/fonts.nix declares the faces personality/theme.toml names, but "
        + "fonts.fontconfig.enable is false — nothing on this system would resolve "
        + "\"${lib.concatStringsSep "\", \"" (lib.attrValues facesByRole)}\" to them.";
    }
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
