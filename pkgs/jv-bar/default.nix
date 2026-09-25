# jv-bar — the top bar (blueprint §06, PLAN D1): Quickshell running the QML
# in shell/jv-bar as a Wayland layer-shell strip along the top of every
# monitor under Niri.
#
# The package is the same thin, pinned launcher pkgs/jv-hud is: the QML is
# copied into the store (so the running bar is exactly what the flake
# declares — nothing reads out of the working tree) and `quickshell` is
# wrapped to load it. The build gate is qmllint plus the headless QML tests
# in shell/jv-bar/tests: a bar that does not parse — or whose model got the
# meaning of a workspace activation wrong — can never reach a
# `nixos-rebuild build`, let alone a screen.
#
# The wrapper also pins JV_BAR_NIRI to the niri the flake installs. Pinning
# it means the bar's only window onto the compositor is the one this flake
# declares — never whatever binary named `niri` happens to be first on
# $PATH — and it is a `niri msg` that can only READ: the event stream is the
# single subcommand this shell ever runs.
{
  lib,
  stdenvNoCC,
  makeWrapper,
  python3,
  quickshell,
  qt6,
  niri,
}:
stdenvNoCC.mkDerivation {
  pname = "jv-bar";
  version = "0.1.0";
  src = ../../shell/jv-bar;

  nativeBuildInputs = [
    makeWrapper
    python3 # the theme drift check below
    qt6.qtdeclarative # qmllint
  ];

  # Theme tokens are identity and live in personality/ (invariant 9); the
  # QML singleton is generated from them, for this shell exactly as for the
  # HUD's. Both are inputs here so the build itself can prove the committed
  # Theme.qml still matches the toml — a bar whose colours have drifted from
  # the file you can diff never gets built.
  themeToml = ../../personality/theme.toml;
  themeGen = ../../tools/gen_theme_qml.py;

  dontConfigure = true;
  dontBuild = true;
  # qtdeclarative is here only for qmllint; nothing in this package is a Qt
  # application, and the one binary is a wrapper around quickshell's own
  # already-wrapped entry point.
  dontWrapQtApps = true;

  doCheck = true;
  # -W 0: any warning at all fails the build. The one disabled category is
  # upstream's, not ours: every quickshell window type is registered
  # non-creatable (they are proxy interfaces resolved at runtime), so
  # `uncreatable-type` fires on correct code.
  checkPhase = ''
    runHook preCheck
    python3 $themeGen --check --shell jv-bar --theme $themeToml --out-dir .
    qmllint -W 0 --uncreatable-type disable \
      -I ${quickshell}/lib/qt-6/qml \
      -I ${qt6.qtdeclarative}/lib/qt-6/qml \
      $(find . -name '*.qml' | sort)
    # The headless QML tests (shell/jv-bar/tests). They can run at all only
    # because everything they exercise lives in core/, which imports nothing
    # but QtQuick: quickshell links its own QML plugin into its binary, so no
    # other QML engine — this one included — can ever import Quickshell.
    export QT_QPA_PLATFORM=offscreen
    export HOME=$TMPDIR
    qmltestrunner -input ./tests -import ${qt6.qtdeclarative}/lib/qt-6/qml
    runHook postCheck
  '';

  installPhase = ''
    runHook preInstall
    mkdir -p $out/share/jv-bar
    cp -r ./* $out/share/jv-bar/
    # The tests are a build gate, not part of the shell quickshell loads.
    rm -rf $out/share/jv-bar/tests
    makeWrapper ${lib.getExe quickshell} $out/bin/jv-bar \
      --add-flags "-p $out/share/jv-bar/shell.qml" \
      --set JV_BAR_NIRI ${niri}/bin/niri
    runHook postInstall
  '';

  meta.mainProgram = "jv-bar";
}
