// The wallpaper, loaded under an engine that prints what QtTest drops (PLAN
// D38). Lowercase on purpose: a document `qml` is pointed at, never a type, and
// qmltestrunner — given this same directory — only runs `tst_*.qml`.
//
// The field is the one Field.qml declares, which is the one shell.qml composes.
// It is stated at ares' primary geometry because this surface has no size of its
// own — the real one is anchored to all four edges of an output — and every
// piece of arithmetic in it (the instrument's centre, the ring's radius, which
// of pkgs/jarvis-wallpaper's renders this output resolves) is a function of that
// size. A field at 0x0 would evaluate every binding against zero and throw
// nothing.
//
// `wallDir` is left EMPTY, and that is the state being probed: the wallpaper as
// it is when `JV_WALL_DIR` is unset, which is every way this shell can be
// started other than through the wrapper in pkgs/jv-wall. The Image fails, the
// fallback fires, that fails too, and the surface is the transparent nothing
// this file is here to prove it becomes without a single binding throwing on the
// way. No shot on the sheet is a picture of it.
import QtQuick

Probe {
  subject: field

  Field {
    id: field

    width: 2560
    height: 1440
  }
}
