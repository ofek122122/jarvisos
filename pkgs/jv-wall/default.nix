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
    qt6.qtdeclarative # qmllint
  ];

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
    qmllint -W 0 --uncreatable-type disable \
      -I ${quickshell}/lib/qt-6/qml \
      -I ${qt6.qtdeclarative}/lib/qt-6/qml \
      "$src/shell.qml"
    runHook postCheck
  '';

  installPhase = ''
    runHook preInstall
    mkdir -p "$out/share/jv-wall" "$out/bin"
    cp -r "$src"/* "$out/share/jv-wall/"
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
