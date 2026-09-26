// The top bar, loaded under an engine that prints what QtTest drops (PLAN
// D38). Lowercase on purpose: a document `qml` is pointed at, never a type,
// and qmltestrunner — given this same directory — only runs `tst_*.qml`.
//
// The strip is the one Strip.qml declares, which is the one shell.qml
// composes. Unlike the other two shells it has no width of its own — the
// real surface is anchored to both edges of an output — and half of its
// arithmetic (the room the row is given, the overflow into the HUD's corner,
// the clock's `fits`) can only be evaluated at a real one. So this states a
// width, and states ares' primary, which is the width every bar shot and the
// settle driver start from.
//
// `Niri` is the stub and nothing has been recorded into it: this is the bar
// in the first frame of a session, before the compositor's event stream has
// said anything, and a state no shot on the sheet is a picture of.
import QtQuick

Probe {
  subject: strip

  Strip {
    id: strip

    width: 2560
    height: strip.implicitHeight
  }
}
