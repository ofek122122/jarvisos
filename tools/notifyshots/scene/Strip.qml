// Strip — the notification corner's stack, staged for the harness that drives
// the real toasts without a compositor or a D-Bus session (PLAN D20).
//
// shell.qml composes this stack inline, and it has to: the stack lives inside
// a PanelWindow, and that file is the Quickshell half no other engine can
// load. So anything that wants to exercise the REAL plates headlessly needs a
// copy of it — and it is here, once, rather than inside the driver, so that
// "the harness stacks what the shell stacks" is a single claim.
// tools/tests/test_notifyshots.py reads the composition out of this file and
// out of shell.qml and fails if the two differ: a strip that stacked the
// plates NEWEST first, or dropped the `+N EARLIER` line, would photograph and
// assert a corner the user never sees.
//
// Same order, same spacing, same `+N EARLIER` line as shell.qml. The position
// on the surface is the consumer's — shell.qml anchors this bottom-right
// inside the inset and the driver does the same, because a shot is a picture
// of the surface and not of the stack floating in the middle of one.
//
// Each Toast reaches for nothing: the record is handed in from
// `Notifications.toasts`, which in this stage is
// tools/notifyshots/stub/Notifications.qml — the real NotifyModel with a
// wound clock instead of a D-Bus server.
import QtQuick
import ".."

Column {
  id: root

  // --- what the harness reads back ------------------------------------

  // How many plates are on screen. Not `Notifications.toasts.length`: that is
  // what the model OFFERED, and this is what the Repeater built.
  readonly property int shown: plates.count

  // The `+N EARLIER` line as drawn, or "" when it is not there. The string and
  // not the count, because the one thing a capped stack owes its reader is
  // that sentence, and a sheet that asserted a number would pass over a line
  // that said "+0 EARLIER" or nothing at all.
  readonly property string earlierText: counted.visible ? counted.text : ""

  // Each plate's own account of what it drew, nearest-the-corner LAST (the
  // order they are stacked in). A function rather than a property: the
  // delegates do not exist until the Repeater has built them, and a binding
  // over `itemAt` would be evaluated once, before there was anything to read.
  //
  // `as Toast` on every `itemAt`, because the Repeater hands back a bare
  // QQuickItem and qmllint is right to refuse a member it cannot find on one —
  // a harness reading a property that does not exist would see `undefined` and
  // assert a caption of nothing.
  function captions(): var {
    const out = [];
    for (let i = 0; i < plates.count; i++) {
      const plate = plates.itemAt(i) as Toast;
      out.push(plate ? plate.drew : "?");
    }
    return out;
  }

  // The dot colours, in the same order, as `#rrggbb`. The dot is the only
  // channel urgency gets, so this is the whole of what the sheet can claim
  // about a sender's severity reaching the screen.
  function dots(): var {
    const out = [];
    for (let i = 0; i < plates.count; i++) {
      const plate = plates.itemAt(i) as Toast;
      out.push(plate ? "" + plate.dotColor : "?");
    }
    return out;
  }

  // Each plate's opacity AS PAINTED, in the same order. The one read-back on
  // this strip that is about a moment rather than about a layout: a shot waits
  // past `fadeInMs` before it grabs, so every PNG on the sheet holds a settled
  // plate and none of them can see a plate that blinked on the way there.
  // `tst_settle.qml` samples this while a second notification lands (PLAN
  // D37).
  function opacities(): var {
    const out = [];
    for (let i = 0; i < plates.count; i++) {
      const plate = plates.itemAt(i) as Toast;
      out.push(plate ? plate.paintedOpacity : -1);
    }
    return out;
  }

  // How far each plate paints past its own border, in the same order. Must be
  // zeroes: this surface has no input region, so paint outside a plate is paint
  // on the desktop that nothing can move.
  function overflows(): var {
    const out = [];
    for (let i = 0; i < plates.count; i++) {
      const plate = plates.itemAt(i) as Toast;
      out.push(plate ? plate.overflowPx : -1);
    }
    return out;
  }

  // --- shell.qml's stack, verbatim ------------------------------------

  spacing: Theme.gapPx

  Text {
    id: counted

    text: "+" + Notifications.earlier + " EARLIER"
    visible: Notifications.earlier > 0
    color: Theme.text3
    font.family: Theme.familyMono
    font.pixelSize: Theme.labelPx
    font.letterSpacing: Theme.labelPx * Theme.labelTrackingEm
    textFormat: Text.PlainText
  }

  // Keyed by the notification's id, never by position (PLAN D37).
  // `Notifications.onScreen` is a ListModel `NotifyModel` keeps in step
  // with `toasts`, so a plate that is still up keeps its delegate — and
  // a delegate that survives keeps `arrived` true and does not fade in
  // again. Repeating over the array instead meant every plate in the
  // corner was destroyed and rebuilt whenever ANY notification arrived,
  // was replaced or went away, so all three blinked and the fade stopped
  // meaning "this one is new".
  //
  // The record is rebuilt from the roles because a ListModel holds
  // values, not objects: `Toast` takes one record, which is what lets it
  // import nothing but QtQuick and the generated Theme.
  Repeater {
    id: plates

    model: Notifications.onScreen

    Toast {
      required property string appName
      required property string summary
      required property string body
      required property int urgency

      toast: ({
          "appName": appName,
          "summary": summary,
          "body": body,
          "urgency": urgency
        })
    }
  }
}
