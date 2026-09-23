# jv-hud — the HUD shell (blueprint §06): Quickshell running the QML in
# shell/jv-hud as a Wayland layer-shell surface over Niri.
#
# The package is a thin, pinned launcher: the QML is copied into the store
# (so the running HUD is exactly what the flake declares — nothing reads
# out of the working tree) and `quickshell` is wrapped to load it. The
# build gate is qmllint: a HUD that does not parse can never reach a
# `nixos-rebuild build`, let alone a screen.
{
  lib,
  stdenvNoCC,
  makeWrapper,
  quickshell,
  qt6,
}:
stdenvNoCC.mkDerivation {
  pname = "jv-hud";
  version = "0.1.0";
  src = ../../shell/jv-hud;

  nativeBuildInputs = [
    makeWrapper
    qt6.qtdeclarative # qmllint
  ];

  dontConfigure = true;
  dontBuild = true;
  # qtdeclarative is here only for qmllint; nothing in this package is a Qt
  # application, and the one binary is a wrapper around quickshell's own
  # already-wrapped entry point.
  dontWrapQtApps = true;

  doCheck = true;
  # -W 0: any warning at all fails the build. The one disabled category
  # is upstream's, not ours: every quickshell window type is registered
  # non-creatable (they are proxy interfaces resolved at runtime), so
  # `uncreatable-type` fires on correct code.
  checkPhase = ''
    runHook preCheck
    qmllint -W 0 --uncreatable-type disable \
      -I ${quickshell}/lib/qt-6/qml \
      -I ${qt6.qtdeclarative}/lib/qt-6/qml \
      $(find . -name '*.qml' | sort)
    runHook postCheck
  '';

  installPhase = ''
    runHook preInstall
    mkdir -p $out/share/jv-hud
    cp -r ./* $out/share/jv-hud/
    makeWrapper ${lib.getExe quickshell} $out/bin/jv-hud \
      --add-flags "-p $out/share/jv-hud/shell.qml"
    runHook postInstall
  '';

  meta.mainProgram = "jv-hud";
}
