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
// Anything that moves goes through `Ease`/`Motion` (A7), which carries §06's
// reduced-motion switch — so stillness is one setting, not a promise every
// element has to keep on its own.
// No sensor state is displayed yet, because no ELEMENT reads one yet
// (A3/A4 add `speech.state`, `audio.wake`, `audio.vad` — real frames or
// nothing; never a faked indicator). The read-only bus link exists as of
// A5 (`Bus`), but it is only touched under JV_HUD_SELFTEST, so an idle
// machine still runs no bridge process: the singleton is never built.
import QtQuick
import Quickshell
import Quickshell.Wayland
// The §06 tokens, generated from personality/theme.toml into Theme.qml next
// door (invariant 9: the look is identity, and identity is versioned). No
// QML file in this directory may carry a hex code of its own.
import "."

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
      // The inset is baked into the surface, not into `margins`: quickshell's
      // `margins` grouped property has no resolvable type in its qmltypes, and
      // a clean qmllint is worth more than two pixels of layout sugar.
      implicitWidth: 112
      implicitHeight: 62
      color: "transparent"
      mask: Region {} // empty: input passes through, always

      // Nothing real to show yet -> no surface at all.
      visible: surface.selfTest

      // Built only under the self-test. `active: false` means the plate's
      // bindings never run, so `Bus` is never constructed and no bridge
      // process is spawned: the empty HUD really does cost nothing.
      Loader {
        anchors.fill: parent
        active: surface.selfTest
        sourceComponent: plate
      }

      Component {
        id: plate

        Rectangle {
          anchors.fill: parent
          anchors.margins: Theme.insetPx
          radius: Theme.radiusPx
          color: Theme.ground
          opacity: Theme.plateOpacity
          border.color: Theme.ember // the one accent, used sparingly
          border.width: Theme.hairlinePx

          Column {
            anchors.centerIn: parent
            spacing: 2

            Text {
              text: "jv-hud"
              color: Theme.ember
              font.family: Theme.familyMono
              font.pixelSize: Theme.labelPx
              font.letterSpacing: Theme.labelPx * Theme.labelTrackingEm
            }

            // The state of the HUD's own bus link — a property of this
            // pipe, not of the room. It is NOT a sensor indicator and is
            // never dressed as one: no ember, no dot, just the word.
            Text {
              text: Bus.linkUp ? "bus up" : "bus down"
              color: Bus.linkUp ? Theme.text2 : Theme.text3
              font.family: Theme.familyMono
              font.pixelSize: Theme.labelPx
              font.letterSpacing: Theme.labelPx * Theme.labelTrackingEm

              // The one moving pixel in the HUD so far, and it moves only
              // because the link state actually changed (§06: ease toward
              // the target, never snap). `Ease` carries the reduced-motion
              // gate with it, so this settles or it assigns instantly —
              // either way it says the same true thing.
              Ease on color {}
            }
          }
        }
      }
    }
  }
}
