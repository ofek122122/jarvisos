// LinkPlate — the HUD saying it cannot see the machine (A23).
//
// The one plate that is about this panel rather than about the room, and it
// exists because the other four have no way to say "I don't know". They are
// all built to refuse — MicState will not call a mic it cannot see "off",
// SpeechState will not call an invisible bus "idle", BusModel empties its
// cache the moment the link drops — and every one of those refusals draws
// NOTHING. An empty corner is also the ordinary state of a well, quiet
// machine (§06: earned emptiness), so the same blank pixels mean both "all
// is calm" and "this screen has been blind for a minute and the microphone
// may be open". Invariant 10 asks the HUD to show sensor state truthfully;
// a silence you cannot tell from a reading is not a truthful answer.
//
// §06, and why it looks like this:
//   · no dot and no accent. Ember means Jarvis is doing something and teal
//     means you are; this is neither, it is the pipe describing itself, and
//     dressing it as a sensor row is exactly the confusion to avoid. The
//     self-test marker next door already states that rule for "bus up /
//     bus down"; this is the same fact in the place a user will see it.
//   · the brightest text tier, on the quietest plate. Legibility, not
//     alarm: you should be able to read it the moment you look, and it
//     should not compete with a confirmation that needs an answer.
//   · the consequence is spelled out. "NO BUS" is the fact, but the thing
//     worth knowing is that everything below it has stopped meaning
//     anything — including the recording light.
//   · nothing pulses, nothing counts. The only motion is the plate arriving
//     and leaving, through `Ease`, which carries the reduced-motion switch
//     (A7). A blinking warning is a warning you stop seeing.
//   · it waits before it appears (core/LinkState.qml). Bridges respawn and
//     jarvisd restarts; a plate that blinked every time would be ignored on
//     the day it was true.
import QtQuick
import "."
import "core"

Item {
  id: root

  // Can this HUD see the bus? `Bus` is the read-only link (A5) and also,
  // here, the subject: this is the one element whose input is the state of
  // its own input.
  readonly property LinkState link: LinkState {
    bus: Bus
  }

  // How wide the bridge's explanation may run before it wraps — the same
  // budget ConfirmPlate's question uses, so the two longest things this
  // HUD can draw agree about the edge of the surface.
  property int maxTextPx: 240

  // Two lines of explanation. Past that it is a log entry, not a glance.
  property int maxLines: 2

  // On screen exactly while the HUD cannot vouch for anything below it.
  readonly property bool shown: root.link.blind

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
      // Half the plate rhythm: the fact, what it costs you, and why are one
      // reading rather than three stacked plates.
      spacing: Theme.gapPx / 2

      Text {
        // The fact, in the words the bridge's own protocol uses.
        text: "NO BUS"
        color: Theme.text
        font.family: Theme.familyMono
        font.pixelSize: Theme.labelPx
        font.letterSpacing: Theme.labelPx * Theme.labelTrackingEm
      }

      Text {
        // The consequence, which is the part worth reading: every other
        // plate on this surface has gone quiet because it knows nothing,
        // not because there is nothing to know.
        text: "SENSOR STATE UNKNOWN"
        color: Theme.text2
        font.family: Theme.familyMono
        font.pixelSize: Theme.labelPx
        font.letterSpacing: Theme.labelPx * Theme.labelTrackingEm
      }

      // Measured, not guessed: a wrapped Text reports an implicitWidth that
      // depends on its width, and binding one to the other is how a layout
      // starts oscillating. TextMetrics asks the same font the same
      // question without being part of the layout at all.
      TextMetrics {
        id: metrics

        font: why.font
        text: why.text
      }

      Text {
        id: why

        // The bridge's own explanation — "connect: ..." when jarvisd is not
        // running, "bus closed the connection" when it went away. Clipped
        // to a glance by LinkState; the elide here is the layout's
        // backstop, for a font wider than that budget assumed. Absent when
        // the link died without a word, which costs nothing: the headline
        // is the report and this is the footnote.
        text: root.link.reason
        visible: why.text.length > 0
        width: Math.min(metrics.width, root.maxTextPx)
        wrapMode: Text.Wrap
        maximumLineCount: root.maxLines
        elide: Text.ElideRight
        color: Theme.text3
        font.family: Theme.familyMono
        font.pixelSize: Theme.labelPx
      }
    }
  }
}
