// OutputPlate — Jarvis is speaking and none of it is reaching the room (A40).
//
// It exists to stop the plate above it from lying by omission. `StatePlate`
// has said SPEAKING since A3, and that word is about jv-voice, not about
// what you can hear: with the default sink muted, jv-voice accepts the
// utterance, Piper synthesises it, PortAudio plays it, every service
// reports `ok`, and the room stays silent. This is the one line that says
// so, and it is only ever on screen during the seconds it is true.
//
// The mapping lives next door in core/OutputState.qml, where it is pure
// QtQuick and tested headlessly (the A9 rule); this file is wiring and
// pixels.
//
// §06, and why it looks like this:
//   · `warn`, not ember and not risk. Ember means Jarvis is doing
//     something — it is doing it, that is the whole problem — and `risk`
//     is reserved for a machine that broke. Nothing here is broken; a
//     control is in a position that makes Jarvis pointless. That is
//     HealthPlate's severity vocabulary, which is why the two read as one
//     family.
//   · two words, because there are two different controls behind them.
//     OUTPUT MUTED is a toggle; OUTPUT AT ZERO is a slider. A single
//     "no sound" would send the user to the wrong one half the time.
//   · no number. The volume is not drawn, because the plate is not a
//     mixer readout — it appears only for silence, and silence has no
//     interesting value.
//   · nothing counts down and nothing pulses. The line leaves when
//     jv-voice stops speaking or when the sink comes back, both of which
//     are real signals; the only motion is the plate arriving and leaving
//     through `Ease`, which carries the reduced-motion switch with it (A7).
//
// It is a READOUT, like every other plate: the surface takes no keyboard
// and has an empty input region (invariant 10), so there is no unmute
// button here and there never will be. Changing this machine is jv-act's
// alone (invariant 3) — ask out loud, or reach for the key you already
// have.
import QtQuick
import "."
import "core"

Item {
  id: root

  // Whether anything Jarvis is saying can be heard. `Bus` is the read-only
  // link (A5): the HUD subscribes and can do nothing else.
  readonly property OutputState output: OutputState {
    bus: Bus
  }

  // The line, in the two words the mixer state earns. Kept here rather
  // than in core/ because it is language, not logic: the element decides
  // WHICH silence this is, and the plate decides what to call it.
  readonly property string line: root.output.reason === "muted" ? "OUTPUT MUTED" : root.output.reason === "zero" ? "OUTPUT AT ZERO" : ""

  // Which plate this is, in one word (A53). The stack collects these
  // so that "something arrived in the corner" can become "THIS plate
  // arrived" — see `litNames` in core/PlateStack.qml.
  readonly property string plateName: "output"

  // On screen exactly while Jarvis is speaking into a silent output.
  readonly property bool shown: root.output.unheard && root.line.length > 0

  // True while anything is still drawn, including the fade out, so
  // shell.qml can keep the surface mapped until the plate is really gone.
  readonly property bool lit: plate.opacity > 0

  implicitWidth: plate.implicitWidth
  implicitHeight: plate.implicitHeight

  // A plate answers for itself: it takes room in the stack exactly while
  // it is on screen, so a silent plate leaves no gap and the ones below it
  // close up. PlateStack reads the same two properties to decide whether
  // the surface is mapped at all (A15).
  visible: root.shown || root.lit

  Rectangle {
    id: plate

    implicitWidth: rows.implicitWidth + Theme.padPx * 2
    implicitHeight: rows.implicitHeight + Theme.padPx * 2
    radius: Theme.radiusPx
    color: Theme.groundDeep
    border.color: Theme.lineSoft
    border.width: Theme.hairlinePx

    opacity: root.shown ? Theme.plateOpacity : 0
    visible: plate.opacity > 0

    Ease on opacity {
      base: root.shown ? Theme.fadeInMs : Theme.fadeOutMs
    }

    Row {
      id: rows

      anchors.centerIn: parent
      spacing: Theme.gapPx

      Rectangle {
        // The same 6 px dot every plate uses: one HUD, one vocabulary.
        // Coloured by severity, like HealthPlate's rows.
        width: 6
        height: 6
        radius: width / 2
        anchors.verticalCenter: parent.verticalCenter
        color: Theme.warn
      }

      Text {
        text: root.line
        color: Theme.text2
        font.family: Theme.familyMono
        font.pixelSize: Theme.labelPx
        font.letterSpacing: Theme.labelPx * Theme.labelTrackingEm
      }
    }
  }
}
