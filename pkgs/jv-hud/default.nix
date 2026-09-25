# jv-hud — the HUD shell (blueprint §06): Quickshell running the QML in
# shell/jv-hud as a Wayland layer-shell surface over Niri.
#
# The package is a thin, pinned launcher: the QML is copied into the store
# (so the running HUD is exactly what the flake declares — nothing reads
# out of the working tree) and `quickshell` is wrapped to load it. The
# build gate is qmllint plus the headless QML tests in shell/jv-hud/tests:
# a HUD that does not parse — or whose bus state machine got the meaning of
# a dropped link wrong — can never reach a `nixos-rebuild build`, let alone
# a screen.
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
  # `--shell jv-hud` because there are two shells now and the sandbox holds
  # one: this tree is the HUD's, so the qmldir checked against it is the
  # HUD's registries and not the bar's (pkgs/jv-bar does the mirror).
  themeToml = ../../personality/theme.toml;
  themeGen = ../../tools/gen_theme_qml.py;

  # The recorded perception sessions the QML tests replay (PLAN B9). A QML
  # engine cannot read a file out of the repository, so the recordings are
  # compiled into tests/Sessions.qml — and that generated file is only worth
  # having while it is still the recording, which is what the --check below
  # proves. Re-record perception without regenerating and this build fails,
  # rather than the HUD's tests quietly asserting against last week's room.
  # Only the *.jsonl are inputs: the generator's own directory also holds a
  # README and the script that writes them, and neither changes the fixture.
  sessions = lib.sources.sourceFilesBySuffices ../../harness/fixtures/sessions [ ".jsonl" ];
  sessionsGen = ../../tools/gen_sessions_qml.py;

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
    python3 $themeGen --check --shell jv-hud --theme $themeToml --out-dir .
    python3 $sessionsGen --check --sessions $sessions --out-dir ./tests
    qmllint -W 0 --uncreatable-type disable \
      -I ${quickshell}/lib/qt-6/qml \
      -I ${qt6.qtdeclarative}/lib/qt-6/qml \
      $(find . -name '*.qml' | sort)
    # The headless QML tests (shell/jv-hud/tests). They can run at all only
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
    mkdir -p $out/share/jv-hud
    cp -r ./* $out/share/jv-hud/
    # The tests are a build gate, not part of the shell quickshell loads.
    rm -rf $out/share/jv-hud/tests
    makeWrapper ${lib.getExe quickshell} $out/bin/jv-hud \
      --add-flags "-p $out/share/jv-hud/shell.qml" \
      --set JV_HUD_BRIDGE ${hudBridge}/bin/jv-hud-bridge
    runHook postInstall
  '';

  meta.mainProgram = "jv-hud";
}
