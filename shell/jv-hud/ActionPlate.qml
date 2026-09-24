// ActionPlate — what Jarvis tried to do to your machine, and could not (A37).
//
// Invariant 3 gives one process the right to change this computer, and
// the HUD could already show the question it asks before a destructive
// tool (A20). What it could never show is the outcome — so "it did it",
// "it refused", "it broke" and "nothing was ever asked" were the same
// empty corner, and the only report on any of them was a sentence the
// language model composed afterwards.
//
// The mapping lives next door in core/ActionState.qml, where it is pure
// QtQuick and tested headlessly (the A9 rule); this file is wiring and
// pixels.
//
// §06, and why it looks like this:
//   · `risk`, not ember. Ember means Jarvis is doing something, and this
//     plate is the opposite: Jarvis tried and the machine did not move.
//     It borrows HealthPlate's rule — colour is severity here, never
//     identity — for the same reason the two plates read as one family.
//   · FAILURES only. An action that worked draws nothing: the machine
//     visibly doing the thing is the report that it was done, and a
//     corner that lights up for every volume change is one nobody reads
//     on the day it matters.
//   · the tool's registry name, verbatim — `app.launch`, not "launching
//     an app". It is the same string the audit log and `jv act-log` use,
//     so what you read on screen is what you can go and grep for. And
//     nothing at all when the HUD never saw the intent that names it: a
//     tool name taken on faith is a lie about what touched your machine.
//   · the error in the schema's own word, `execution_failed`, in the
//     quiet tier. Underscores and all — it is vocabulary out of a frozen
//     enum, and a friendlier paraphrase would be a word nobody can look
//     up in schemas/action.result.json.
//   · nothing counts down and nothing pulses. The line leaves when Jarvis
//     starts explaining, which is a real signal rather than a timer, and
//     the only motion is the plate arriving and leaving through `Ease`,
//     which carries the reduced-motion switch with it (A7).
//
// It is a READOUT, like every other plate: the surface takes no keyboard
// and has an empty input region (invariant 10), so there is no retry
// button here and there never will be — acting is jv-act's alone, and
// asking it to act again is what your voice and `jv` are for.
import QtQuick
import "."
import "core"

Item {
  id: root

  // How the last thing Jarvis did went. `Bus` is the read-only link (A5):
  // the HUD subscribes and can do nothing else.
  readonly property ActionState action: ActionState {
    bus: Bus
  }

  // How wide a tool name may be before it elides. The surface is 300 px
  // and the plate sits inside its inset; same number as HeardPlate and
  // ConfirmPlate, because it is the same box.
  property int maxTextPx: 240

  // On screen exactly while the last action is a failure nobody has
  // explained yet.
  readonly property bool shown: root.action.failed

  // True while anything is still drawn, including the fade out, so
  // shell.qml can keep the surface mapped until the plate is really gone.
  readonly property bool lit: plate.opacity > 0

  implicitWidth: plate.implicitWidth
  implicitHeight: plate.implicitHeight

  // A plate answers for itself: it takes room in the stack exactly while
  // it is on screen, so a silent plate leaves no gap and the ones below
  // it close up. PlateStack reads the same two properties to decide
  // whether the surface is mapped at all (A15).
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

    Column {
      id: rows

      anchors.centerIn: parent
      // Half the plate rhythm: the label, the tool and the reason are one
      // reading, not three stacked plates.
      spacing: Theme.gapPx / 2

      Row {
        spacing: Theme.gapPx

        Rectangle {
          // The same 6 px dot every plate uses: one HUD, one vocabulary.
          // Coloured by severity, like HealthPlate's rows.
          width: 6
          height: 6
          radius: width / 2
          anchors.verticalCenter: parent.verticalCenter
          color: Theme.risk
        }

        Text {
          // Past tense, and the word the audit log would use. This is a
          // thing that has finished happening, not one in progress.
          text: "ACTION FAILED"
          color: Theme.text2
          font.family: Theme.familyMono
          font.pixelSize: Theme.labelPx
          font.letterSpacing: Theme.labelPx * Theme.labelTrackingEm
        }
      }

      Text {
        id: toolText

        // The registry tool name, or nothing. The brightest tier, because
        // on the rare occasion this plate is up, WHAT was attempted is
        // the thing the user is here to read.
        text: root.action.tool
        visible: root.action.tool.length > 0
        width: Math.min(toolText.implicitWidth, root.maxTextPx)
        elide: Text.ElideRight
        color: Theme.text
        font.family: Theme.familyMono
        font.pixelSize: Theme.bodyPx
      }

      Text {
        id: reasonText

        // The schema's error word, when jv-act sent one this HUD knows.
        text: root.action.reason
        visible: root.action.reason.length > 0
        width: Math.min(reasonText.implicitWidth, root.maxTextPx)
        elide: Text.ElideRight
        color: Theme.text3
        font.family: Theme.familyMono
        font.pixelSize: Theme.labelPx
      }
    }
  }
}
