// jv-hud — the JarvisOS heads-up display (blueprint §06, Quickshell/QML).
//
// This is the skeleton (PLAN A1). It proves one thing: a layer-shell
// surface maps on every monitor under Niri, takes no keyboard focus, and
// reserves no screen space — and it renders NOTHING until a real signal
// gives it something truthful to show.
//
// Invariant 10 is enforced structurally here, not by convention:
//   · WlrKeyboardFocus.None + focusable:false — the surface CANNOT take
//     the keyboard, so it can never steal focus from your work.
//   · ExclusionMode.Ignore — zero exclusive zone, so no window is ever
//     resized or pushed around by the HUD.
//   · mask: Region {} — an empty input region: every click, scroll and
//     hover passes straight through to the window underneath.
//   · visible is false until something real is on screen. Earned
//     emptiness is the default state, and an unmapped surface costs
//     exactly 0 fps.
// No sensor state is displayed yet, because no sensor is subscribed yet
// (A3/A4 add `speech.state`, `audio.wake`, `audio.vad` — real frames or
// nothing; never a faked indicator).
import QtQuick
import Quickshell
import Quickshell.Wayland

ShellRoot {
  // One surface per connected monitor. Quickshell.screens is live, so a
  // hotplugged monitor gains a surface without restarting the shell.
  Variants {
    model: Quickshell.screens

    PanelWindow {
      id: surface

      required property var modelData

      // Self-test: `JV_HUD_SELFTEST=1 jv-hud` maps a small marker so a
      // human can confirm the layer-shell surface actually reaches the
      // screen. It reports that the SHELL loaded — never a sensor state.
      readonly property bool selfTest: Quickshell.env("JV_HUD_SELFTEST") === "1"

      screen: modelData

      // Top, not Overlay: the HUD floats over ordinary windows but yields
      // to fullscreen and lock surfaces. It is never the thing in the way.
      WlrLayershell.layer: WlrLayer.Top
      WlrLayershell.namespace: "jv-hud"
      WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
      focusable: false
      exclusionMode: ExclusionMode.Ignore

      anchors {
        top: true
        right: true
      }
      // 16 px of inset is baked into the surface, not into `margins`:
      // quickshell's `margins` grouped property has no resolvable type in
      // its qmltypes, and a clean qmllint is worth more than two pixels
      // of layout sugar.
      implicitWidth: 112
      implicitHeight: 44
      color: "transparent"
      mask: Region {} // empty: input passes through, always

      // Nothing real to show yet -> no surface at all.
      visible: surface.selfTest

      Rectangle {
        anchors.fill: parent
        anchors.margins: 16
        radius: 4
        color: "#0C1116" // ground, blueprint §06
        border.color: "#F0714A" // ember — the one accent, used sparingly
        border.width: 1

        Text {
          anchors.centerIn: parent
          text: "jv-hud"
          color: "#F0714A"
          font.pixelSize: 13
        }
      }
    }
  }
}
