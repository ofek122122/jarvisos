// HeardPlate — what Jarvis heard you say (A26).
//
// The HUD could say the microphone was open, that a wake word fired, and
// that Jarvis was working. It could never say what it HEARD — so the most
// common way a voice assistant fails you was the one thing the screen had
// no word for, and "it misheard me", "it never heard me" and "it is just
// slow" were the same dark corner. This plate is that word, on screen for
// exactly as long as the question is still in flight.
//
// The mapping lives next door in core/HeardState.qml, where it is pure
// QtQuick and tested headlessly (the A9 rule); this file is wiring and
// pixels.
//
// §06, and why it looks like this:
//   · teal, not ember. theme.toml reserves the cooler voice for YOUR
//     state — the open microphone is yours (A4) and so are these words.
//     Ember means Jarvis is doing something, and nothing here is Jarvis
//     doing anything; it is Jarvis repeating you.
//   · the transcript VERBATIM, in jv-ears' own words, punctuation and
//     all. The whole value of this plate is that it shows what was heard
//     rather than a tidied version of it — the misheard word IS the
//     signal, and a HUD that cleaned it up would hide the one thing the
//     user came here to see.
//   · three lines and then an ellipsis. Longer than a glance is a
//     paragraph nobody reads standing up, and truncation that does not
//     say it truncated reads as a whole sentence.
//   · a quiet language tag, and only when the frame claims a language
//     this machine does not expect. The pinned ASR is English-only, so
//     "he" on that line means the model is hallucinating English words
//     out of Hebrew audio — a fact worth reading, not an alarm worth
//     colouring.
//   · nothing counts down and nothing pulses. The line leaves when Jarvis
//     starts answering, which is a real signal rather than a timer, and
//     the only motion is the plate arriving and leaving through `Ease`,
//     which carries the reduced-motion switch with it (A7).
//
// It is a READOUT, like every other plate: the surface takes no keyboard
// and has an empty input region (invariant 10), so there is no path from
// these pixels to a correction. Getting a misheard sentence fixed is still
// a matter of saying it again — this plate is only what tells you to.
import QtQuick
import "."
import "core"

Item {
  id: root

  // What jv-ears transcribed, if anything. `Bus` is the read-only link
  // (A5): the HUD subscribes and can do nothing else.
  readonly property HeardState heard: HeardState {
    bus: Bus
  }

  // How wide the sentence may be before it wraps. The surface is 300 px
  // and the plate sits inside its inset, so this is the widest line that
  // fits without the plate reaching for the middle of the screen. Same
  // number as ConfirmPlate, because they are the same box.
  property int maxTextPx: 240

  // How many lines are shown before it elides. Three is what a person
  // reads without stopping; past that, the sentence they just said is the
  // better copy anyway.
  property int maxLines: 3

  // On screen exactly while the words are still the live question.
  readonly property bool shown: root.heard.heard

  // True while anything is still drawn, including the fade out, so
  // shell.qml can keep the surface mapped until the plate is really gone.
  readonly property bool lit: plate.opacity > 0

  implicitWidth: plate.implicitWidth
  implicitHeight: plate.implicitHeight

  // A plate answers for itself: it takes room in the stack exactly while it
  // is on screen, so a silenced plate leaves no gap and the ones below it
  // close up. `shown || lit` and not just `lit`, so the plate is in the
  // layout from the first frame of its fade rather than appearing into it.
  // PlateStack reads the same two properties to decide whether the surface
  // is mapped at all (A15) — nothing upstream keeps a list of us.
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
      // Half the plate rhythm: the label and the sentence are one reading,
      // not two stacked plates.
      spacing: Theme.gapPx / 2

      Row {
        spacing: Theme.gapPx

        Rectangle {
          // The same 6 px dot every sensor plate uses: one HUD, one
          // vocabulary. Teal, because these are your words.
          width: 6
          height: 6
          radius: width / 2
          anchors.verticalCenter: parent.verticalCenter
          color: Theme.teal
        }

        Text {
          // One word, past tense on purpose: this is what was taken down,
          // not what is being taken down. The recording light (A4) is the
          // plate that speaks in the present.
          text: "HEARD"
          color: Theme.text2
          font.family: Theme.familyMono
          font.pixelSize: Theme.labelPx
          font.letterSpacing: Theme.labelPx * Theme.labelTrackingEm
        }
      }

      // Measured, not guessed: a wrapped Text reports an implicitWidth
      // that depends on its width, and binding one to the other is how a
      // layout starts oscillating. TextMetrics asks the same font the same
      // question without being part of the layout at all.
      TextMetrics {
        id: metrics

        font: sentence.font
        text: sentence.text
      }

      Text {
        id: sentence

        // jv-ears' transcript, unedited. The brightest tier in the HUD,
        // because on the rare occasion this plate is up it is the thing
        // the user is here to read.
        text: root.heard.text
        width: Math.min(metrics.width, root.maxTextPx)
        wrapMode: Text.Wrap
        maximumLineCount: root.maxLines
        elide: Text.ElideRight
        color: Theme.text
        font.family: Theme.familyMono
        font.pixelSize: Theme.bodyPx
      }

      Text {
        // The detected language, and only when it is not the one this
        // machine speaks. Whisper is pinned to an English-only model, so
        // this line appearing at all means the words above are a guess
        // made out of audio the model could not represent.
        text: root.heard.lang.toUpperCase()
        visible: root.heard.foreignLang
        color: Theme.text3
        font.family: Theme.familyMono
        font.pixelSize: Theme.labelPx
        font.letterSpacing: Theme.labelPx * Theme.labelTrackingEm
      }
    }
  }
}
