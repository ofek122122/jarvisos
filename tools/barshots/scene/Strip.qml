// Strip — the top bar's surface, staged for the harness that drives the real
// elements without a compositor and without niri (PLAN D13).
//
// shell.qml composes this inside a PanelWindow, and it has to: the surface IS
// the layer-shell window, and that file is the Quickshell half no other engine
// can load. So anything that wants to exercise the REAL strip headlessly needs
// a copy of it — and it is here, once, rather than inside the driver, so that
// "the harness draws what the shell draws" is a single claim.
// tools/tests/test_barshots.py reads the composition out of this file and out
// of shell.qml and fails if the two differ: a strip that dropped the hairline,
// or centred the clock on the space left over instead of on the screen, would
// photograph and assert a bar the user never sees.
//
// Same three children, same order, same anchors, same ground as shell.qml. The
// two things handed in rather than bound are the two that come from Quickshell
// there: which output this surface is on (`Variants` gives shell.qml a screen;
// there are no screens here) and the time (a `SystemClock`, which needs the
// quickshell binary). Everything else — the workspaces row, the clock face,
// the hairline, the reserved corner — is the shell's own file.
//
// WHAT IT IS NOT. Not the compositor: layer-shell, `WlrKeyboardFocus.None`,
// the empty input mask, the exclusive zone that makes windows tile below the
// strip, and the one-surface-per-monitor `Variants` are shell.qml's, and a
// human at the machine is still the only thing that can confirm them. This is
// the CONTENT of one surface, at the width a real monitor gives it.
import QtQuick
import ".."

Rectangle {
  id: root

  // --- what the shell gets from Quickshell and the harness hands in ----

  // The output this strip is on, as Wayland names it — `Variants` gives
  // shell.qml a screen and the workspaces are looked up by its name. The join
  // is the whole reason the bar can be per-monitor, so the harness makes it
  // explicit rather than drawing every workspace on the machine.
  property string screenName: ""

  // The machine's clock as `SystemClock` reports it, and -1 for "nothing has
  // said the time yet" — which is a state this surface really is in for the
  // first moments of a session, and one of the shots.
  property real hours: -1
  property real minutes: -1

  // --- what the harness reads back -------------------------------------

  // The workspaces row's own account of what it drew: `<label>:<reading>` per
  // workspace, in layout order. From `Workspaces.drew`, which names each
  // reading in the same place the colour is chosen — so the caption under a
  // shot cannot claim a focus the pixels do not have.
  readonly property var desk: row.drew

  // The clock as drawn, or "" when it is not on screen at all. The string and
  // not the numbers: an unknown time and a monitor too narrow to hold the
  // clock clear of the HUD's corner both end in nothing being drawn, and that
  // is the fact worth photographing.
  readonly property string clockText: face.visible ? face.text : ""

  // How far the workspaces row reaches INTO the corner shell.qml reserves for
  // the HUD. Must be zero: the HUD is a different process on a different
  // layer, it draws over this strip, and neither surface can detect the other
  // — so two things in one corner is the one arrangement nothing on this
  // machine can report. This number is the whole of the bar's side of that
  // promise.
  readonly property int hudOverflowPx: Math.max(0, Math.ceil(row.x + row.width - (root.width - root.hudReservePx)))

  // …and how far it reaches past the left edge of the clock, which is centred
  // on the SCREEN and therefore cannot move out of the way. Zero when the
  // clock is not drawn, because then there is nothing to run into.
  readonly property int clockOverlapPx: face.visible ? Math.max(0, Math.ceil(row.x + row.width - face.x)) : 0

  // The room left between the two, which is the same measurement from the
  // other side and is the one the driver PRINTS rather than asserts. -1 when
  // the clock is not drawn. A margin is not a promise — it is a number that
  // shrinks by one workspace at a time, and the only way anyone finds out how
  // many are left is if a run says so out loud (PLAN D32).
  readonly property int clockClearPx: face.visible ? Math.floor(face.x - (row.x + row.width)) : -1

  // --- shell.qml's surface, verbatim -----------------------------------

  readonly property int hudReservePx: 300 + Theme.insetPx

  implicitHeight: Theme.labelPx + Theme.padPx * 2
  color: Theme.groundDeep

  Rectangle {
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.bottom: parent.bottom
    height: Theme.hairlinePx
    color: Theme.lineSoft
  }

  Workspaces {
    id: row

    anchors.left: parent.left
    anchors.leftMargin: Theme.insetPx
    anchors.verticalCenter: parent.verticalCenter

    workspaces: Niri.workspacesOn(root.screenName)
  }

  Clock {
    id: face

    anchors.horizontalCenter: parent.horizontalCenter
    anchors.verticalCenter: parent.verticalCenter

    hours: root.hours
    minutes: root.minutes
    fits: root.width / 2 + face.width / 2 < root.width - root.hudReservePx
  }
}
