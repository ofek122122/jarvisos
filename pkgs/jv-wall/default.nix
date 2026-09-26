# jv-wall — the animated wallpaper (blueprint §06, PLAN D10/E1): Quickshell
# running shell/jv-wall as a Wayland BACKGROUND layer on every monitor.
#
# Same thin, pinned launcher shape as pkgs/jv-hud and pkgs/jv-bar: the QML is
# copied into the store (the running wallpaper is exactly what the flake
# declares) and `quickshell` is wrapped to load it. qmllint is the build gate.
#
# JV_WALL_DIR is pinned to the jarvis-wallpaper package, which renders the art
# once PER OUTPUT GEOMETRY — the shell picks the file matching its screen, so
# nothing is scaled or cropped on the 1080p panels.
{
  lib,
  stdenvNoCC,
  makeWrapper,
  python3,
  quickshell,
  qt6,
  jarvis-wallpaper,
}:
stdenvNoCC.mkDerivation {
  pname = "jv-wall";
  version = "0.1.0";
  src = ../../shell/jv-wall;

  nativeBuildInputs = [
    makeWrapper
    python3 # the theme drift check below
    qt6.qtdeclarative # qmllint
  ];

  # Theme tokens are identity and live in personality/ (invariant 9); this
  # shell's Theme.qml is generated from them, exactly as jv-hud's, jv-bar's and
  # jv-notify's are. Both are inputs here so the build itself proves the
  # committed singleton still matches the toml — a wallpaper whose ember has
  # drifted from the file you can diff never gets built.
  themeToml = ../../personality/theme.toml;
  themeGen = ../../tools/gen_theme_qml.py;

  dontConfigure = true;
  dontBuild = true;
  # quickshell is already wrapped; this package only copies QML and makes a
  # launcher, so it needs no Qt wrapping of its own (same as jv-hud/jv-bar).
  dontWrapQtApps = true;

  # A wallpaper that does not parse must never reach a screen. Same gate the
  # other shells use: -W 0 (a warning fails the build) with uncreatable-type
  # disabled, because every quickshell window type is registered non-creatable
  # and would otherwise fire on correct code.
  doCheck = true;
  checkPhase = ''
    runHook preCheck
    python3 $themeGen --check --shell jv-wall --theme $themeToml --out-dir .
    # Every QML file, not just the entry point: `import "."` now resolves the
    # generated Theme and Motion out of this directory, and a singleton that
    # does not lint is a wallpaper that loads to a black screen.
    qmllint -W 0 --uncreatable-type disable \
      -I ${quickshell}/lib/qt-6/qml \
      -I ${qt6.qtdeclarative}/lib/qt-6/qml \
      $(find . -name '*.qml' | sort)
    runHook postCheck
  '';

  installPhase = ''
    runHook preInstall
    mkdir -p "$out/share/jv-wall" "$out/bin"
    cp -r ./* "$out/share/jv-wall/"
    makeWrapper ${lib.getExe quickshell} "$out/bin/jv-wall" \
      --add-flags "-p $out/share/jv-wall/shell.qml" \
      --set JV_WALL_DIR "${jarvis-wallpaper}/share/backgrounds"
    runHook postInstall
  '';

  meta = {
    description = "JarvisOS animated wallpaper (Quickshell background layer)";
    mainProgram = "jv-wall";
  };
}
