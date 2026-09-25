// ReplyPlate — Jarvis stopped mid-answer, and it was not finished (A71).
//
// `schemas/brain.response.json` ends every turn with one of three words,
// and `length` means the reply you just heard is TRUNCATED — the context
// or token limit was reached and the rest of the sentence does not exist.
// The user hears exactly that: a reply that stops. Nothing said why, and
// nothing could: no service calls it a fault, so no heartbeat changes;
// jv-brain speaks the reply as it streams, so there is no later sentence
// to put the news in; and the frame that carries the word is a
// well-formed frame on a perfectly healthy machine.
//
// On ares this is not the exotic case. The brain runs on a CPU rung with
// a 2048-token context (invariant 6's ladder doing its job on a card with
// 943 MiB free) against a conversation budget sized for rung 0, so the
// limit is reachable in ordinary conversation — see
// docs/optimization-backlog.md §4, which is a human's to answer and is
// about the brain rather than about the screen. This plate is only the
// part the screen owes the user: when the answer stops early, say so.
//
// The mapping lives next door in core/ReplyState.qml, where it is pure
// QtQuick and tested headlessly (the A9 rule); this file is wiring and
// pixels.
//
// §06, and why it looks like this:
//   · `warn`, not `risk` and not ember. Nothing is broken — the ladder
//     worked, the brain answered, the machine is well — and ember means
//     Jarvis is DOING something. An incomplete answer is impaired, which
//     is the tier HealthPlate spends `warn` on, and the two plates read
//     as one family for that reason.
//   · TRUNCATIONS only, like ActionPlate's failures only. A reply that
//     finished draws nothing, because the reply itself is the report
//     that it finished.
//   · `length`, the schema's own word, in the quiet tier — the same call
//     ActionPlate makes for `execution_failed`. It is vocabulary out of a
//     frozen enum, so it is the string a reader can go and look up in
//     schemas/brain.response.json; a friendlier paraphrase would not be.
//   · NOT ONE WORD OF THE REPLY. The text is jv-brain's answer to
//     something the user said out loud, and the HUD has a place for what
//     you were heard saying (HeardPlate) and none for what Jarvis said
//     back. This plate says that an answer was cut off; hearing it again
//     is what asking again is for.
//   · nothing counts down and nothing pulses. The only motion is the
//     plate arriving and leaving through `Ease`, which carries the
//     reduced-motion switch with it (A7).
//
// It is a READOUT, like every other plate: the surface takes no keyboard
// and has an empty input region (invariant 10), so there is no "continue"
// button here and there never will be — asking again is what your voice
// and `jv` are for.
import QtQuick
import "."
import "core"

Item {
  id: root

  // How the last reply ended. `Bus` is the read-only link (A5): the HUD
  // subscribes and can do nothing else.
  readonly property ReplyState reply: ReplyState {
    bus: Bus
  }

  // Which plate this is, in one word (A53). The stack collects these so
  // that "something arrived in the corner" can become "THIS plate
  // arrived" — see `litNames` in core/PlateStack.qml.
  readonly property string plateName: "reply"

  // On screen exactly while the last reply is one that was cut off.
  readonly property bool shown: root.reply.truncated

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
      // Half the plate rhythm: the label and the schema's word are one
      // reading, not two stacked plates.
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
          color: Theme.warn
        }

        Text {
          // Past tense, and about the answer rather than about Jarvis:
          // this is a thing that has finished happening.
          text: "REPLY CUT OFF"
          color: Theme.text2
          font.family: Theme.familyMono
          font.pixelSize: Theme.labelPx
          font.letterSpacing: Theme.labelPx * Theme.labelTrackingEm
        }
      }

      Text {
        // The schema's own finish_reason. One word out of a frozen enum,
        // so it is the thing to grep for rather than a description.
        text: root.reply.reason
        visible: root.reply.reason.length > 0
        color: Theme.text3
        font.family: Theme.familyMono
        font.pixelSize: Theme.labelPx
      }
    }
  }
}
