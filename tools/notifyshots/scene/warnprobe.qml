// The notification corner, loaded under an engine that prints what QtTest
// drops (PLAN D38). Lowercase on purpose: a document `qml` is pointed at,
// never a type, and qmltestrunner — given this same directory — only runs
// `tst_*.qml`.
//
// The strip is the one Strip.qml declares, which is the one shell.qml
// composes. It sizes itself off its plates (it is a Column), so there is no
// box to state: with nothing notified there are no plates, and an empty
// corner is exactly the state this probe is for. `Notifications` is the stub
// and nothing has been sent to it — which is every session before the first
// notification arrives, and a state no shot on the sheet is a picture of.
import QtQuick

Probe {
  subject: strip

  Strip {
    id: strip
  }
}
