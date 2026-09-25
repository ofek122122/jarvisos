// RowFit — which labels fit, and what the rest collapse to (PLAN D32).
//
// The bar's workspaces row has no width of its own. It is a `Row`, which
// takes its width from its children, and its children are strings the USER
// chose the length of: niri lets a workspace be NAMED, and nothing stops six
// of them being called `documentation`. D13 photographed that desk and
// printed what was left — 274 px on a 1920 px monitor, about three more
// names — because a margin is not a promise. This file is what happens to
// the name after those three.
//
// THE RULE, in one line: as many whole labels as fit, then a `+N` standing
// where the row was cut, and the workspace this output is SHOWING is never
// among the dropped.
//
// Why each half of that is the way it is — the alternatives are all worse in
// a specific way, and tst_rowfit.qml names them:
//
//   · whole labels, never elided. Half a word is a surface that looks broken
//     rather than one that has less to say, and a row of `documen…` `compos…`
//     `video-…` says nothing at all while spending every pixel it has.
//   · a marker, never silence. Dropping labels quietly is the failure the
//     notifier's `+N EARLIER` line exists to prevent: a surface that has
//     hidden something from you has to say that it has, and it has to say
//     how much. `+3` is three characters and is the whole difference between
//     "that is the desk" and "that is some of the desk".
//   · the one you are on survives. This strip exists to say which workspace
//     your keyboard is in; a rule that could drop THAT label to make room
//     for three you are not looking at has inverted its own reason to exist.
//     So it is reserved first and drawn last, after the marker.
//
// WHERE THE MARKER SITS, and the one thing it does not claim. It goes
// between the run and the label that was held back — where the row was cut.
// In the ordinary cases that is exactly where the hidden workspaces are: the
// keyboard is either on one of the first few (marker last, everything after
// it hidden) or on the far end (marker in the middle, standing for the ones
// it stands in front of). It is possible to be on a workspace with more
// beyond it, and then some of the counted ones are to the RIGHT of the label
// the marker is drawn to the left of. The COUNT is exact in every case; the
// POSITION says "the row was cut here" and not "they were all here".
//
// It is pure arithmetic over numbers, which is what makes it the bar's, and
// testable: no font, no Text, no engine. The pixels come from the labels
// themselves — Workspaces.qml measures its own type and hands the widths in
// — because a row that computed glyph widths from character counts would be
// a row that is right about JetBrains Mono and wrong about the first name
// with an emoji in it.
import QtQuick

QtObject {
  id: root

  // Which labels a row draws, given what they measure.
  //
  //   widths    — the labels in layout order, in pixels, as they were laid
  //               out. Empty means an empty row, which is a desk this bar
  //               really has (an unknown one, and a lost one).
  //   gapPx     — the space between two labels; the marker is a label for
  //               this purpose and pays for a gap of its own.
  //   roomPx    — how much room the row has. NEGATIVE means nobody has said,
  //               and then nothing is dropped: a row that hid labels because
  //               it had not yet been told how wide its surface is would hide
  //               them in the first frame of every session.
  //   keepIndex — the label that is never dropped (-1 for none). The caller's
  //               choice, and in this shell it is the workspace the output is
  //               showing, which is the focused one when the keyboard is
  //               here and the active one when it is not.
  //   markerPx  — what the widest `+N` this row could draw measures. Reserved
  //               before the count is known, because the count depends on how
  //               much room the marker leaves: measuring the widest breaks
  //               that circle for at most one glyph of over-reservation.
  //
  // Returns { run, marker, tail, dropped, elidePx }: the first `run` labels
  // are drawn, then the `+dropped` marker if `marker`, then the label at
  // `tail` if it is not -1. `elidePx` is 0 except in the one case below.
  function plan(widths: var, gapPx: int, roomPx: int, keepIndex: int, markerPx: int): var {
    const n = widths.length;
    const whole = {
      "run": n,
      "marker": false,
      "tail": -1,
      "dropped": 0,
      "elidePx": 0
    };
    if (n === 0 || roomPx < 0)
      return whole;

    // Everything, with nothing spent on a marker nothing was dropped into.
    if (root.span(widths, n, gapPx, -1, 0) <= roomPx)
      return whole;

    const keep = keepIndex >= 0 && keepIndex < n ? keepIndex : -1;

    // The longest run from the left that still leaves room for the marker
    // and for the label being held back. Descending, and the first fit wins:
    // removing a label never makes a row wider, so the first k that fits is
    // the largest one that does. n labels was the case above, so this starts
    // at n - 1 — every k here draws a marker.
    for (let k = n - 1; k >= 0; k--) {
      // The held-back label is a TAIL only while it is outside the run;
      // inside it, it is already drawn in its own place and appending it
      // again would put the focused workspace on screen twice.
      const tail = keep >= k ? keep : -1;
      if (root.span(widths, k, gapPx, tail, markerPx) <= roomPx)
        return {
          "run": k,
          "marker": true,
          "tail": tail,
          "dropped": n - k - (tail >= 0 ? 1 : 0),
          "elidePx": 0
        };
    }

    // Not even the marker and one label. What is left is the label you are
    // on, alone — the COUNT is what gives way here and not the name, because
    // a workspace you can read beats a number about workspaces you cannot
    // see. A row with nothing to hold back draws nothing at all, which is
    // what a monitor narrower than the corner the HUD reserves would get.
    if (keep < 0)
      return {
        "run": 0,
        "marker": false,
        "tail": -1,
        "dropped": n,
        "elidePx": 0
      };
    return {
      "run": 0,
      "marker": false,
      "tail": keep,
      "dropped": n - 1,
      // The one place this rule cuts a word: a single label wider than the
      // whole row. Every other case draws whole names or does not draw them.
      "elidePx": widths[keep] > roomPx ? roomPx : 0
    };
  }

  // What a row of `count` labels from the left measures, plus the marker
  // (0 for none) and plus `tail` (-1 for none), with a gap between each pair.
  function span(widths: var, count: int, gapPx: int, tail: int, markerPx: int): real {
    let px = markerPx;
    let items = markerPx > 0 ? 1 : 0;
    for (let i = 0; i < count; i++) {
      px += widths[i];
      items += 1;
    }
    if (tail >= 0) {
      px += widths[tail];
      items += 1;
    }
    return items > 0 ? px + gapPx * (items - 1) : 0;
  }
}
