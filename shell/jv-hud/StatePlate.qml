// StatePlate — the HUD's first real element: what Jarvis is doing (A3).
//
// A small docked plate that exists ONLY while there is something true to
// say. The mapping from bus frames to a state lives next door in
// core/SpeechState.qml, where it is pure QtQuick and tested headlessly;
// this file is wiring and pixels, which is the A9 rule.
//
// §06, and why it looks like this:
//   · earned emptiness — `idle` and `unknown` both draw NOTHING. A badge
//     sitting there saying "idle" is chrome that never earned its place,
//     and one saying it while the bus is down would be a lie. The plate
//     no longer vanishes while Jarvis is answering, though: that gap used
//     to report `idle` and now reports `thinking` (A12), which is both
//     truer and the one moment the user is actually waiting on it.
//   · one ember accent, spent only on Jarvis genuinely doing something.
//     Listening is teal: theme.toml reserves the cooler voice for YOUR
//     state, and the open microphone is yours, not Jarvis's.
//   · the dot carries the colour and the word carries the meaning. Ember
//     never decorates the text — scarcity is what makes it read as a
//     voice.
//   · the only things that move are the plate's opacity and the dot's
//     colour, both through `Ease`, so the reduced-motion switch turns
//     them off without this file having to remember it (A7). With motion
//     suppressed the plate simply appears — it still says the same thing.
//
// Truthfulness is structural, not stylistic: every state drawn here came
// off the bus, and there is no path in this file that can invent one.
import QtQuick
import "."
import "core"

Item {
  id: root

  // What the bus says, as a state. `Bus` is the read-only link (A5): it
  // subscribes and nothing more, so nothing in the HUD can act.
  readonly property SpeechState voice: SpeechState {
    bus: Bus
  }

  // Is there something to show? Unknown means we cannot see, idle means
  // nothing is happening — both draw nothing at all.
  readonly property bool shown: root.voice.known && !root.voice.idle

  // True while any of this is still on screen, INCLUDING the fade out.
  // shell.qml keeps the surface mapped until this goes false, so the
  // plate's exit is not a surface disappearing out from under it.
  readonly property bool lit: plate.opacity > 0

  // Ember is Jarvis; teal is you. Anything else is quiet by design —
  // `interrupted` is a fact worth reading, not an alarm worth colouring,
  // and `thinking` (A12) is Jarvis working with nothing to perceive and
  // nothing to say yet: a word, not a third accent.
  readonly property color dotColor: root.voice.state === "speaking" ? Theme.ember : root.voice.state === "listening" ? Theme.teal : Theme.text3

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

    implicitWidth: row.implicitWidth + Theme.padPx * 2
    implicitHeight: row.implicitHeight + Theme.padPx * 2
    radius: Theme.radiusPx
    color: Theme.groundDeep
    border.color: Theme.lineSoft
    border.width: Theme.hairlinePx

    // Summon and evaporate (§06). Gone means opacity 0 AND not rendered:
    // an invisible item costs no frames.
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
        // The one lit pixel. 6 px is the smallest dot that still reads as
        // deliberate at 1x on the 1440p panel; it is a shape, not a token.
        width: 6
        height: 6
        radius: width / 2
        anchors.verticalCenter: parent.verticalCenter
        color: root.dotColor

        // The colour moves only because the state moved.
        Ease on color {}
      }

      Text {
        // The state word itself, never a friendlier paraphrase of it.
        text: root.voice.state.toUpperCase()
        color: Theme.text2
        font.family: Theme.familyMono
        font.pixelSize: Theme.labelPx
        font.letterSpacing: Theme.labelPx * Theme.labelTrackingEm
      }
    }
  }
}
