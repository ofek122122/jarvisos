// PlateStack — the HUD's corner stack, and the one thing that knows whether
// the surface has anything to show (PLAN A15).
//
// The HUD's surface is unmapped by design: earned emptiness is the default
// state, and an unmapped layer-shell surface costs exactly 0 fps (§06).
// Something therefore has to decide "is anything on screen right now", and
// until A15 that something was a hand-written OR in shell.qml that grew a
// term per element — three plates, six terms. The failure mode is the worst
// kind: the next element that forgot to add itself would simply never
// appear, on a surface that is invisible on purpose, so nothing would fail
// and nothing would notice.
//
// So the stack answers for itself. It asks its own children, whoever they
// are, and there is nothing to keep in sync:
//   · `shown`  — this child has something true to say RIGHT NOW.
//   · `lit`    — this child is still on screen, INCLUDING its fade out.
// A child answering either is enough to keep the surface mapped; `shown` is
// what maps it in the first place (at that instant the fade has not started
// and `lit` is still false), and `lit` is what keeps it mapped while the
// last plate evaporates, so the exit is an element fading rather than the
// surface vanishing out from under it.
//
// A child that answers NEITHER is counted as on screen. That direction is
// deliberate: an unaskable plate might be drawing, and of the two ways to
// be wrong, "the surface maps with nothing on it" costs a few idle frames
// while "the plate that was trying to warn you never appeared" is the bug
// A15 exists to kill. A tools test keeps that path unreachable by checking
// every plate in the stack really does answer.
//
// This is a Column and nothing more exotic: children stack, and a child
// that makes itself invisible leaves no gap, so the survivors close up
// rather than leaving a hole where a signal used to be.
//
// Lives under core/ because that makes it testable (A9): pure QtQuick, no
// Quickshell, so `qmltestrunner` can build one and flip its children.
import QtQuick

Column {
  id: stack

  // Does this stack have anything on screen? shell.qml maps the surface
  // while this is true and unmaps it the instant it goes false.
  //
  // A JS block, not a chain of ORs, because QML tracks what a binding
  // READS: every `shown`/`lit` touched below becomes a dependency, so this
  // re-evaluates when a plate changes state and when the child list itself
  // changes. Returning early is safe for the same reason — if the child
  // that said yes stops saying it, the re-run reads the ones after it.
  readonly property bool anyLit: {
    const kids = stack.children;
    for (let i = 0; i < kids.length; i++) {
      const kid = kids[i];
      if (kid.shown === undefined && kid.lit === undefined)
        return true; // cannot ask; assume it may be drawing
      if (kid.shown || kid.lit)
        return true;
    }
    return false;
  }
}
