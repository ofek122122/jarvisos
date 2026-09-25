// Toast — one notification, as a plate (PLAN D2).
//
// Deliberately the HUD's plate and not a new invention: same ground, same
// hairline, same radius, same 6 px dot, same label-over-body rhythm. A
// notification is another program's news and the HUD's plates are Jarvis's
// own, but they are one machine's chrome and a second visual language would
// make the desktop read as two desktops.
//
// §06, and why it looks like this:
//
//   · NOT EMBER, ever. Ember means Jarvis is doing something. Every process
//     with a D-Bus session can send a notification and can put any string in
//     `app_name` — including "Jarvis" — so a corner that spent the accent
//     here would let any program on this machine dress up as the assistant.
//     The accent stays in the HUD, where the only publisher is the bus.
//
//   · urgency is ONE channel: the dot. `risk` for Critical — the sender is
//     saying something is wrong, which is exactly what that token is for —
//     `text_2` for Normal, `text_3` for Low. Three readings, one place to
//     look, no boxes and no icons.
//
//   · the app's name above its own message, quiet and in mono: it is a label,
//     and §06 labels are wide and quiet. Which program is talking to you is
//     the first thing to know and the last thing to shout.
//
//   · PLAIN TEXT, always. `Text.PlainText` is not a default here, it is the
//     other half of `bodyMarkupSupported: false` in Notifications.qml: a
//     daemon that told senders it does not do markup and then interpreted
//     `<img>` anyway would be rendering markup from strangers on a surface
//     that floats over every window.
//
//   · two lines of summary, three of body, then an ellipsis. Longer than a
//     glance is a paragraph nobody reads standing up — and an elide is what
//     makes a truncated message look truncated instead of finished.
//
// The data is a record from `core/NotifyModel.qml`, passed in as a property
// rather than read off the `Notifications` singleton, so this file imports
// nothing but QtQuick and the generated Theme. That is the same split the
// HUD's plates keep, and it is what would make a render harness for this
// shell possible without a D-Bus session (PLAN D20).
import QtQuick
import "."

Item {
  id: root

  // One entry as the model holds it: { key, appName, summary, body, urgency,
  // deadline, handle }. Required, because a toast with nothing to say is not
  // a toast that should have been built.
  required property var toast

  // How wide the plate is. Fixed rather than fitted to the text: a column of
  // plates that each ended where their own sentence did would read as a
  // ragged pile rather than as a stack.
  property int plateWidthPx: 320

  // How many lines each field may take before it elides. The summary is the
  // sentence the sender wrote to be read at a glance; the body is the detail
  // under it, and gets more room because that is where a path or a reason
  // lands.
  property int maxSummaryLines: 2
  property int maxBodyLines: 3

  // The urgency numbers, as freedesktop puts them on the wire. The model
  // guarantees the field is one of the three, so this is a lookup and not a
  // guess — but it is spelled out rather than compared against a bare 2.
  readonly property int urgencyCritical: 2
  readonly property int urgencyLow: 0

  // Arrival. The plate is built at zero and fades up to its tint on the frame
  // after it exists, so something appearing in a corner you were not looking
  // at reads as an arrival rather than as a repaint. LEAVING IS INSTANT, on
  // purpose: the delegate is destroyed the moment the model stops holding the
  // notification, and a plate that lingered through a fade-out would be a
  // plate showing a notification that no longer exists — which is the one
  // thing invariant 10 does not let a surface do. The HUD can fade out
  // because its plates outlive their own signal by design; a toast's whole
  // content is the fact that it is still there.
  property bool arrived: false

  Component.onCompleted: root.arrived = true

  implicitWidth: plate.width
  implicitHeight: plate.height

  Rectangle {
    id: plate

    width: root.plateWidthPx
    height: rows.implicitHeight + Theme.padPx * 2
    radius: Theme.radiusPx
    color: Theme.groundDeep
    border.color: Theme.lineSoft
    border.width: Theme.hairlinePx

    opacity: root.arrived ? Theme.plateOpacity : 0

    Fade on opacity {
      base: Theme.fadeInMs
    }

    Column {
      id: rows

      anchors.left: parent.left
      anchors.right: parent.right
      anchors.top: parent.top
      anchors.margins: Theme.padPx
      // Half the plate rhythm: a name, a sentence and its detail are one
      // reading rather than three stacked plates.
      spacing: Theme.gapPx / 2

      Row {
        spacing: Theme.gapPx

        Rectangle {
          // The same 6 px dot every HUD plate uses: one machine, one
          // vocabulary. Its colour is the only thing on this plate that says
          // how urgent the sender thinks it is.
          width: 6
          height: 6
          radius: width / 2
          anchors.verticalCenter: parent.verticalCenter
          color: root.toast.urgency === root.urgencyCritical ? Theme.risk : root.toast.urgency === root.urgencyLow ? Theme.text3 : Theme.text2
        }

        Text {
          // Who is talking. Upper case because §06 labels are, and because it
          // separates the program's name from the program's words without
          // spending a second type size on it. Hidden outright when a sender
          // left `app_name` empty — an anonymous notification says so by
          // having no name, not by showing the word "unknown".
          text: root.toast.appName.toUpperCase()
          visible: root.toast.appName.length > 0
          color: Theme.text3
          font.family: Theme.familyMono
          font.pixelSize: Theme.labelPx
          font.letterSpacing: Theme.labelPx * Theme.labelTrackingEm
          textFormat: Text.PlainText
        }
      }

      Text {
        // The sender's own summary, in the brightest tier: on the rare
        // occasion this plate is up, this is the line the user is here to
        // read.
        text: root.toast.summary
        visible: root.toast.summary.length > 0
        width: rows.width
        wrapMode: Text.Wrap
        maximumLineCount: root.maxSummaryLines
        elide: Text.ElideRight
        color: Theme.text
        font.family: Theme.familyMono
        font.pixelSize: Theme.bodyPx
        textFormat: Text.PlainText
      }

      Text {
        // The detail under it, quieter. Absent rather than empty when the
        // sender sent no body, so a one-line notification is a one-line
        // plate.
        text: root.toast.body
        visible: root.toast.body.length > 0
        width: rows.width
        wrapMode: Text.Wrap
        maximumLineCount: root.maxBodyLines
        elide: Text.ElideRight
        color: Theme.text2
        font.family: Theme.familyMono
        font.pixelSize: Theme.bodyPx
        textFormat: Text.PlainText
      }
    }
  }
}
