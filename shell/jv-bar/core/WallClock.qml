// WallClock — a time, as the two glyphs a bar shows (PLAN D1).
//
// The pure-QtQuick half of the clock, so the one thing on this surface that
// is always true is also the one thing a headless test can read. The
// Quickshell half is in `Clock.qml`'s source: Quickshell's `SystemClock` at
// Minutes precision, which wakes on the minute and not on the second —
// §06's "0 fps when idle" applied to the element with the best excuse for
// breaking it.
//
// `hours`/`minutes` are `real` and start at -1 rather than `int` at 0,
// because the element has to be able to say it does not know. Midnight is a
// real time; a bar that maps before its clock source starts would otherwise
// show it, confidently, as the answer.
import QtQuick

QtObject {
  id: root

  // The hour and minute the machine's clock reads, 0-23 and 0-59. Anything
  // else — including the -1 they start at — is not a time.
  property real hours: -1
  property real minutes: -1

  // "HH:mm", 24-hour and zero-padded, or "" when there is nothing to show.
  // Never seconds: see tst_wallclock.qml.
  readonly property string text: root.known ? root.pad(root.hours) + ":" + root.pad(root.minutes) : ""

  readonly property bool known: root.whole(root.hours, 23) && root.whole(root.minutes, 59)

  function whole(value: real, top: int): bool {
    return Number.isInteger(value) && value >= 0 && value <= top;
  }

  function pad(value: real): string {
    return (value < 10 ? "0" : "") + String(value);
  }
}
