// Clock — the time, in the middle of the bar (PLAN D1).
//
// The only element on this surface that does not depend on anything being
// alive, which is why it is the one that earns the bar its place before
// niri has said a word: a bar with no workspaces and a clock is still
// telling the truth about something.
//
// The reading itself is decided in `core/WallClock.qml`, where a headless
// test can read it. What is left here is the type and the colour: mono,
// because it is a measurement and §06 puts every measurement in mono, and
// `text_2`, because the time is the most-glanced-at and least-urgent thing
// on the machine — it never competes with a workspace that is asking for
// you two hundred pixels to the left.
//
// Its source is Quickshell's `SystemClock` at Minutes precision, bound in
// shell.qml: it wakes the surface once a minute, on the minute, and never
// on the second. A ticking seconds digit would be sixty repaints a minute
// of a pixel nobody reads, which is precisely the ambient cost §06 caps.
import QtQuick
import "."
import "core"

Text {
  id: root

  // The machine's clock, as two numbers. -1 means nothing has said the
  // time yet, and the face below draws nothing rather than midnight.
  required property real hours
  required property real minutes

  // Whether there is room for it where it wants to be — the bar's own
  // question, because only the surface knows how wide the monitor is and
  // where the HUD's corner starts. Default true: an element that hid
  // itself by default would be an element nobody noticed was missing.
  property bool fits: true

  text: face.text
  // The surface is mapped for the workspaces' sake as well, so an unknown
  // time — or a monitor too narrow to hold the clock clear of the HUD —
  // leaves this element out rather than the bar.
  visible: face.text.length > 0 && root.fits
  color: Theme.text2
  font.family: Theme.familyMono
  font.pixelSize: Theme.labelPx
  font.letterSpacing: Theme.labelPx * Theme.labelTrackingEm

  WallClock {
    id: face

    hours: root.hours
    minutes: root.minutes
  }
}
