// KeyedRows — a list a Repeater can keep its delegates across (PLAN D34).
//
// THE PROBLEM THIS EXISTS FOR, because it is invisible and cost this shell its
// only animation. `NiriModel` publishes the desk as a JS array and REPLACES it
// wholesale on every delta — it must: a list mutated in place is a list no
// binding hears about, and that rule is written into the model in those words.
// A `Repeater` handed a new array does not diff it. It destroys every delegate
// and builds new ones, and a `Behavior` does not animate an initial
// assignment. So `Ease on color` on a label in that Repeater is attached to
// nothing: the teal never moved, it was simply drawn on a Text that had always
// been teal. Nothing could tell the two apart, because a still picture of a
// finished colour looks the same either way (tools/barshots/scene/
// tst_settle.qml is what tells them apart now).
//
// THE FIX IS IDENTITY. A row on screen is not "the label at position 2", it is
// "workspace 7" — and workspace 7 is still workspace 7 after the desk beside
// it changes. So this is a `ListModel` synced by a `key` the caller chooses:
// a row whose key is already on screen keeps its delegate (moved, and its
// roles reassigned, which is a binding re-evaluation and therefore something
// an `Ease` can move THROUGH), a row whose key is new gets a new delegate, and
// a key that has gone takes its delegate with it.
//
// WHY NOT BY POSITION, which is the sync everyone writes first. Then a desk
// that grew at the left would hand each surviving delegate its NEIGHBOUR's
// workspace, and every label on the strip would cross-fade to the colour of
// the workspace next to it — a 200 ms lie about a change that is
// instantaneous. Workspaces do not slide into existence; niri either has one
// or does not. Keying by identity is what makes "the colour eases, the desk
// snaps" one rule instead of two.
//
// It is a ListModel and not an array because this is exactly the seam QML
// gives for saying "these rows are the same rows": `insert`/`move`/`remove`
// reach the Repeater as changes rather than as a reset, and `set` is a role
// assignment on a delegate that already exists. Nothing here is about the bar
// — a key, some rows, one function — which is why it is in `core/`, where
// `qmltestrunner` can drive it with no Quickshell under it.
import QtQuick

ListModel {
  id: root

  // Make `rows` what is on screen, keeping every delegate whose `key` is
  // still here.
  //
  //   rows — the rows to show, in layout order. Each is an object with a
  //          `key` that identifies the THING it draws (not its position) and
  //          whatever roles the delegate reads. Every row must carry the same
  //          keys as the first one ever synced: a ListModel's roles are fixed
  //          by the first insert, and one that appears later is one the
  //          delegate never sees.
  //
  // O(n²) in the length of the row, deliberately: a bar holds a handful of
  // labels, and the alternative — an index built per sync — costs more than
  // the scan it saves at this size and is one more thing to be wrong.
  function sync(rows: var): void {
    for (let i = 0; i < rows.length; i++) {
      // Where this key is now, looking only at the rows not yet placed: a key
      // BEFORE `i` has already been claimed by an earlier row this pass, and
      // a duplicate key must not steal it.
      let at = i;
      while (at < root.count && root.get(at).key !== rows[i].key)
        at++;
      if (at >= root.count) {
        // New. A delegate is built for it, and whatever the delegate's
        // bindings evaluate to is an initial assignment — so it SNAPS, which
        // is the honest reading of a thing that has just come into existence.
        root.insert(i, rows[i]);
        continue;
      }
      if (at !== i)
        root.move(at, i, 1);
      // Same row, possibly saying something new: the delegate survives and
      // its bindings re-evaluate, which is a value moving toward a target and
      // is the one thing an `Ease` can act on.
      root.set(i, rows[i]);
    }
    // Whatever is left is gone from the row. Removed from the end, in one
    // call, so the delegates that stay are not touched.
    if (root.count > rows.length)
      root.remove(rows.length, root.count - rows.length);
  }
}
