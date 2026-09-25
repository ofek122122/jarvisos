# jv-notify — the notification corner (blueprint §06, PLAN D2): Quickshell
# running the QML in shell/jv-notify as this machine's
# org.freedesktop.Notifications daemon, drawn in the bottom-right corner of
# every monitor under Niri.
#
# The package is the same thin, pinned launcher pkgs/jv-hud and pkgs/jv-bar
# are: the QML is copied into the store (so the running daemon is exactly what
# the flake declares — nothing reads out of the working tree) and `quickshell`
# is wrapped to load it. The build gate is qmllint plus the headless QML tests
# in shell/jv-notify/tests: a daemon that does not parse — or that got the
# meaning of `expire_timeout = 0` wrong, and so let any process on this machine
# pin a plate over your work — can never reach a `nixos-rebuild build`, let
# alone a screen.
#
# Nothing is pinned into the wrapper, because this shell runs no child process
# and reads no file: its whole input is the D-Bus session bus. That is the
# smallest surface of the three shells and the reason this derivation has the
# fewest arguments.
{
  lib,
  stdenvNoCC,
  makeWrapper,
  python3,
  quickshell,
  qt6,
}:
stdenvNoCC.mkDerivation {
  pname = "jv-notify";
  version = "0.1.0";
  src = ../../shell/jv-notify;

  nativeBuildInputs = [
    makeWrapper
    python3 # the theme drift check below
    qt6.qtdeclarative # qmllint
  ];

  # Theme tokens are identity and live in personality/ (invariant 9); the QML
  # singleton is generated from them, for this shell exactly as for the other
  # two. Both are inputs here so the build itself can prove the committed
  # Theme.qml still matches the toml — a corner whose colours have drifted from
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
    python3 $themeGen --check --shell jv-notify --theme $themeToml --out-dir .
    qmllint -W 0 --uncreatable-type disable \
      -I ${quickshell}/lib/qt-6/qml \
      -I ${qt6.qtdeclarative}/lib/qt-6/qml \
      $(find . -name '*.qml' | sort)
    # The headless QML tests (shell/jv-notify/tests). They can run at all only
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
    mkdir -p $out/share/jv-notify
    cp -r ./* $out/share/jv-notify/
    # The tests are a build gate, not part of the shell quickshell loads.
    rm -rf $out/share/jv-notify/tests
    makeWrapper ${lib.getExe quickshell} $out/bin/jv-notify \
      --add-flags "-p $out/share/jv-notify/shell.qml"
    runHook postInstall
  '';

  meta.mainProgram = "jv-notify";
}
