// DictatePlate — push-to-talk dictation is recording (F5c).
//
// Invariant 10 applies to jv-dictate exactly as it does to jv-ears: this is
// on screen for as long as, and only as long as, the push-to-talk key has
// audio flowing to jv-dictate's own recorder — off in every other state,
// including one this HUD cannot read.
//
// It says nothing MicPlate does not already say about the room being
// recorded generally, and it is not derived from MicPlate: jv-ears' VAD and
// jv-dictate's push-to-talk key are two different processes opening the
// microphone for two different reasons, and a reader has to be able to tell
// dictation's short, deliberate recordings from the standing-open one.
//
// §06, and why it looks like MicPlate:
//   · a key not held draws NOTHING, the same earned emptiness MicPlate's
//     `off` and `unknown` both draw — a HUD that cannot see the bus has
//     nothing to claim about a device.
//   · teal, not ember: this is YOUR state (you are holding the key), the
//     same reasoning that keeps the microphone indicator off ember.
//   · nothing pulses, for the same GPU-cost reason MicPlate gives; the only
//     motion is the plate arriving, through `Ease`, which carries the
//     reduced-motion switch (A7).
import QtQuick
import "."
import "core"

Item {
  id: root

  // What jv-dictate's heartbeat says about the key. `Bus` is the read-only
  // link (A5): the HUD subscribes and can do nothing else.
  readonly property DictateState dictate: DictateState {
    bus: Bus
  }

  // Which plate this is, in one word (A53).
  readonly property string plateName: "dictate"

  // On screen exactly while the key is held and audio is being captured.
  // `idle` and `unknown` are both silence, for different reasons — a
  // released key has earned its dark indicator, and a HUD that cannot see
  // the bus has nothing to claim about a device.
  readonly property bool shown: root.dictate.recording

  // True while anything is still drawn, including the fade out, so
  // shell.qml can keep the surface mapped until the plate is really gone.
  readonly property bool lit: plate.opacity > 0

  implicitWidth: plate.implicitWidth
  implicitHeight: plate.implicitHeight

  // A plate answers for itself: it takes room in the stack exactly while it
  // is on screen, so a silenced plate leaves no gap and the ones below it
  // close up.
  visible: root.shown || root.lit

  Rectangle {
    id: plate

    implicitWidth: row.implicitWidth + Theme.padPx * 2
    implicitHeight: row.implicitHeight + Theme.padPx * 2
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
      id: row

      anchors.centerIn: parent
      spacing: Theme.gapPx

      Rectangle {
        // The same 6 px dot MicPlate and StatePlate use: one HUD, one
        // vocabulary.
        width: 6
        height: 6
        radius: width / 2
        anchors.verticalCenter: parent.verticalCenter
        color: Theme.teal
      }

      Text {
        // The one word this plate ever draws — `recording` is the only
        // word DictateState decides that reaches a screen, and `idle` and
        // `unknown` are both silence (`shown` above), which is exactly the
        // decision MicPlate's own `off`/`unknown` make for the same reason.
        text: "DICTATE"
        color: Theme.text2
        font.family: Theme.familyMono
        font.pixelSize: Theme.labelPx
        font.letterSpacing: Theme.labelPx * Theme.labelTrackingEm
      }
    }
  }
}
