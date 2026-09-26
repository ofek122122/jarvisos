// ConfirmPlate — the question Jarvis is waiting on an answer to (A20).
//
// The one plate in this HUD that appears because the machine needs
// something FROM you. jv-act stops in front of every destructive tool and
// asks (invariant 3); jv-voice speaks the question; a window opens and
// closes, and silence inside it is a no. Everything about that handshake
// was audible and nothing about it was visible, which made it fragile in
// the ordinary way: music playing, headphones off, a sentence half heard.
// This is the readable copy — the same words, on screen, for exactly as
// long as the window is open.
//
// It cannot answer, and that is structural rather than a decision made
// here. The surface has an empty input region and takes no keyboard
// (invariant 10, pinned by a tools test), so there is no path from these
// pixels to an authorization at all. Answering stays where invariant 3 put
// it: your voice, or `jv confirm`. A clickable YES here would make the HUD
// a second actuator, which invariant 3 has no word for.
//
// §06, and why it looks like this:
//   · ember. The accent means Jarvis is doing something, and §06 names
//     confirmations as one of the three places it belongs. This is the
//     scarcest thing on the screen and it should read that way.
//   · the summary VERBATIM, in jv-act's own words. The user is hearing
//     this sentence; a HUD that paraphrased it would be asking a second,
//     subtly different question, and the one thing this must never do is
//     disagree with the voice.
//   · the tool id underneath, quiet, in the name it is registered under —
//     the precise thing that will run, for a reader who wants more than
//     prose. Absent when the frame carried none.
//   · nothing pulses and nothing counts down. A ticking number would
//     spend a frame a second saying what the spoken question already said,
//     and §06 asks for 0 fps when nothing is happening. The only motion is
//     the plate arriving and leaving, through `Ease`, which carries the
//     reduced-motion switch (A7).
//   · it disappears the moment the question is answered — including by the
//     window closing. A question on screen that can no longer be answered
//     invites you to say yes into a closed window.
import QtQuick
import "."
import "core"

Item {
  id: root

  // What jv-act has asked, if anything. `Bus` is the read-only link (A5):
  // the HUD subscribes and can do nothing else.
  readonly property ConfirmState confirm: ConfirmState {
    bus: Bus
  }

  // How wide the question may be before it wraps. The surface is 300 px
  // and the plate sits inside its inset, so this is the widest line that
  // fits without the plate reaching the far edge of the screen.
  property int maxTextPx: 240

  // The room this plate really HAS, and -1 for as long as nothing has said
  // (PLAN D66). The cap above is a choice about how much of the corner a
  // sentence may take, made for the 300 px surface ares' monitors give it; on
  // an output narrower than that corner the cap alone lays this text out past
  // the left edge of the screen, which is where it cannot be read. Both files
  // that compose the stack hand this down — `shell.qml` from the surface the
  // compositor configured, `tools/hudshots/scene/Corner.qml` from the box its
  // driver renders into — and `tools/tests/test_hudshots.py` fails if a plate
  // that declares a cap is left out of either one.
  property int roomPx: -1

  // The cap, narrowed to that room. The rule is `core/PlateFit.qml` and not a
  // `Math.min` here for one reason `tests/tst_platefit.qml` spells out: an
  // unmeasured room has to leave the cap standing and a room of ZERO has to
  // not, and the naive arithmetic answers both with the same negative number.
  readonly property int textPx: root.fit.textPx(root.maxTextPx, root.roomPx, Theme.padPx)

  // The rule itself, which owns no state and holds no reading.
  readonly property PlateFit fit: PlateFit {}

  // How many lines of the question are shown before it elides. Three is a
  // sentence a person reads in a glance; past that the spoken question is
  // the better copy anyway, and the ellipsis says there is more.
  property int maxLines: 3

  // Which plate this is, in one word (A53). The stack collects these
  // so that "something arrived in the corner" can become "THIS plate
  // arrived" — see `litNames` in core/PlateStack.qml.
  readonly property string plateName: "confirm"

  // On screen exactly while an answer is owed.
  readonly property bool shown: root.confirm.pending

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
    // The one plate with an ember edge. Every other plate reports on the
    // machine; this one is Jarvis addressing you, and the border is what
    // makes it findable in the corner of your eye without moving.
    border.color: Theme.ember
    border.width: Theme.hairlinePx

    opacity: root.shown ? Theme.plateOpacity : 0
    visible: plate.opacity > 0

    Ease on opacity {
      base: root.shown ? Theme.fadeInMs : Theme.fadeOutMs
    }

    Column {
      id: rows

      anchors.centerIn: parent
      // Half the plate rhythm: the label, the question and the tool are
      // one reading, not three stacked plates.
      spacing: Theme.gapPx / 2

      Row {
        spacing: Theme.gapPx

        Rectangle {
          // The same 6 px dot every other plate uses: one HUD, one
          // vocabulary. Ember, because this is Jarvis asking.
          width: 6
          height: 6
          radius: width / 2
          anchors.verticalCenter: parent.verticalCenter
          color: Theme.ember
        }

        Text {
          // One word, and it is the imperative the situation actually is:
          // something is waiting on you to say yes or no out loud.
          text: "CONFIRM"
          color: Theme.ember
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

        font: question.font
        text: question.text
      }

      Text {
        id: question

        // jv-act's sentence, unedited. Empty when the request carried no
        // summary — the plate is still right to be here, because
        // something destructive is still waiting on an answer.
        text: root.confirm.summary
        visible: question.text.length > 0
        width: Math.min(metrics.width, root.textPx)
        wrapMode: Text.Wrap
        maximumLineCount: root.maxLines
        // Truncation that does not say it truncated reads as a complete
        // question — and this is the one plate where a half-read sentence
        // could authorize the wrong thing.
        elide: Text.ElideRight
        color: Theme.text
        font.family: Theme.familyMono
        font.pixelSize: Theme.bodyPx
      }

      Text {
        // The tool that runs if the answer is yes, in the name jv-act
        // registers it under and `jv act-log` prints — this line should be
        // copyable into the next thing you type.
        text: root.confirm.tool
        visible: text.length > 0
        color: Theme.text3
        font.family: Theme.familyMono
        font.pixelSize: Theme.labelPx
        font.letterSpacing: Theme.labelPx * Theme.labelTrackingEm
      }
    }
  }
}
