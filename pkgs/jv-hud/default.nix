# jv-hud — the HUD shell (blueprint §06): Quickshell running the QML in
# shell/jv-hud as a Wayland layer-shell surface over Niri.
#
# The package is a thin, pinned launcher: the QML is copied into the store
# (so the running HUD is exactly what the flake declares — nothing reads
# out of the working tree) and `quickshell` is wrapped to load it. The
# build gate is qmllint: a HUD that does not parse can never reach a
# `nixos-rebuild build`, let alone a screen.
#
# The wrapper also pins JV_HUD_BRIDGE to the read-only bus bridge the HUD
# spawns as a child (see Bus.qml). Pinning it means the HUD's only window
# onto the bus is the one this flake declares — never whatever binary named
# `jv-hud-bridge` happens to be first on $PATH.
{
  lib,
  stdenvNoCC,
  makeWrapper,
  python3,
  quickshell,
  qt6,
  hudBridge,
}:
stdenvNoCC.mkDerivation {
  pname = "jv-hud";
  version = "0.1.0";
  src = ../../shell/jv-hud;

  nativeBuildInputs = [
    makeWrapper
    python3 # the theme drift check below
    qt6.qtdeclarative # qmllint
  ];

  # Theme tokens are identity and live in personality/ (invariant 9); the
  # QML singleton is generated from them. Both are inputs here so the build
  # itself can prove the committed Theme.qml still matches the toml — a HUD
  # whose colours have drifted from the file you can diff never gets built.
  themeToml = ../../personality/theme.toml;
  themeGen = ../../tools/gen_theme_qml.py;

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
    python3 $themeGen --check --theme $themeToml --out-dir .
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
      --add-flags "-p $out/share/jv-hud/shell.qml" \
      --set JV_HUD_BRIDGE ${hudBridge}/bin/jv-hud-bridge
    runHook postInstall
  '';

  meta.mainProgram = "jv-hud";
}
