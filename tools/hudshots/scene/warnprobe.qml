// The HUD's corner, loaded under an engine that prints what QtTest drops
// (PLAN D38). Lowercase on purpose: this is a document `qml` is pointed at,
// never a type anything names, and qmltestrunner — which is given this same
// directory — only runs `tst_*.qml`.
//
// The stack is the one Corner.qml declares, which is the one shell.qml
// composes and the one the contact sheet photographs. No inset, no backdrop
// and no surface box: nothing here is rendered for a human, so the only
// thing that would come of stating a box is a fourth copy of it (PLAN D33).
//
// Bus is the stub, and nothing feeds it. That is the point — this is the HUD
// as it exists in the first frame of a session, before a single frame has
// arrived, which is the state no shot on the sheet is a picture of.
import QtQuick

Probe {
  subject: stack

  Corner {
    id: stack
  }
}
