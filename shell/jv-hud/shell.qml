// jv-hud — the JarvisOS heads-up display (blueprint §06, Quickshell/QML).
//
// A layer-shell surface on every monitor under Niri that takes no keyboard
// focus, reserves no screen space, and shows NOTHING unless a real bus
// frame gives it something truthful to say.
//
// Invariant 10 is enforced structurally here, not by convention:
//   · WlrKeyboardFocus.None + focusable:false — the surface CANNOT take
//     the keyboard, so it can never steal focus from your work.
//   · ExclusionMode.Ignore — zero exclusive zone, so no window is ever
//     resized or pushed around by the HUD.
//   · mask: Region {} — an empty input region: every click, scroll and
//     hover passes straight through to the window underneath.
//   · visible is false whenever nothing is on screen. Earned emptiness is
//     the default state, and an unmapped surface costs exactly 0 fps.
// Anything that moves goes through `Ease`/`Motion` (A7), which carries §06's
// reduced-motion switch — so stillness is one setting, not a promise every
// element has to keep on its own.
//
// What it shows today: `StatePlate` (A3), which is what jv-voice and
// jv-ears actually published — idle / listening / speaking / interrupted,
// or nothing at all when the bus is quiet or unreachable. The mapping is
// in core/SpeechState.qml, where it is tested; no element in this shell
// can display a state that did not come off the bus. The mic and camera
// indicators (A4) and the sys.health glance (A6) come next.
//
// The HUD is a live bus consumer as of A3, so `Bus` is constructed on load
// and its read-only bridge child runs for as long as the shell does. That
// is the cost of telling the truth about the machine; the surface itself
// still maps only when there is something to draw.
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
      // screen. It reports that the SHELL loaded — never a sensor state,
      // which is why it sits in the corner the real elements do not use.
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
      // The edge inset is baked into the surface rather than into
      // `margins`: quickshell's `margins` grouped property has no
      // resolvable type in its qmltypes, and a clean qmllint is worth more
      // than two pixels of layout sugar. The box is the stack of plates
      // plus its inset, with room for the longest word any of them draws —
      // a surface no bigger than what it may ever draw.
      implicitWidth: 260
      implicitHeight: 120
      color: "transparent"
      mask: Region {} // empty: input passes through, always

      // Mapped only while something is genuinely on screen — including
      // while a plate is fading out, or the exit would be a surface
      // vanishing out from under it rather than an element evaporating.
      visible: surface.selfTest || statePlate.shown || statePlate.lit || micPlate.shown || micPlate.lit

      // The corner stack. Every plate in it draws nothing until it has
      // something true to say, and a Column skips children that are not
      // visible — so an empty plate costs no gap, and the survivors close
      // up rather than leaving a hole where a signal used to be.
      Column {
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.topMargin: Theme.insetPx
        anchors.rightMargin: Theme.insetPx
        spacing: Theme.gapPx

        // What Jarvis is doing, from speech.state + audio.wake + audio.vad.
        // Draws nothing while idle or while the bus cannot be seen.
        StatePlate {
          id: statePlate

          anchors.right: parent.right
          visible: statePlate.lit
        }

        // Whether the microphone is open, from jv-ears' own capture
        // counters. Below the state plate on purpose: what Jarvis is doing
        // changes minute to minute, while the recording light is a
        // standing fact about the room and belongs where it can sit still.
        MicPlate {
          id: micPlate

          anchors.right: parent.right
          visible: micPlate.lit
        }
      }

      // Built only under the self-test, in the opposite corner: it is a
      // developer marker, and it must never sit where a sensor state does.
      Loader {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.topMargin: Theme.insetPx
        anchors.leftMargin: Theme.insetPx
        active: surface.selfTest
        sourceComponent: plate
      }

      Component {
        id: plate

        Rectangle {
          implicitWidth: marker.implicitWidth + Theme.padPx * 2
          implicitHeight: marker.implicitHeight + Theme.padPx * 2
          radius: Theme.radiusPx
          color: Theme.ground
          opacity: Theme.plateOpacity
          border.color: Theme.ember // the one accent, used sparingly
          border.width: Theme.hairlinePx

          Column {
            id: marker

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

              // §06: ease toward the target, never snap. `Ease` carries
              // the reduced-motion gate with it, so this settles or it
              // assigns instantly — either way it says the same true thing.
              Ease on color {}
            }
          }
        }
      }
    }
  }
}
