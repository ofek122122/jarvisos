// RowFit — how a row of labels gives up, under test (PLAN D32).
//
// The bar's workspaces row is a `Row`: it takes its width from its children,
// and its children are strings the USER chose the length of. niri lets a
// workspace be named, and nothing stops six of them being called
// `documentation`. D13 photographed exactly that and printed the margin —
// 274 px left on a 1920 px monitor, about three more names — so the question
// this file answers is what happens to the fourth.
//
// The answers that were available, and why this is the one:
//
//   · draw them all and let the row run on. It runs into the clock, which is
//     centred on the SCREEN and so cannot move out of the way, and then into
//     the corner another PROCESS draws its plates over. Nothing on this
//     machine can see that happen; `hudOverflowPx` in the shot harness exists
//     because it is the one arrangement neither surface can report.
//   · clip the row. A glyph cut in half is the failure §06 is written
//     against — a surface that looks broken rather than one that has less to
//     say.
//   · elide every label to some share of the room. Then the workspace you are
//     ON is unreadable, which is the one thing this strip exists to say.
//   · drop the labels that do not fit, silently. That is the failure the
//     notifier's `+N EARLIER` line exists to prevent: a surface that has
//     hidden something from you must say that it has.
//
// So: as many WHOLE labels as fit, then a `+N` standing where the row was
// cut, and the one your keyboard is on is never among the dropped. This file
// is that decision in numbers, away from any font — the pixels come from the
// labels themselves in Workspaces.qml, and everything interesting about the
// rule is arithmetic that a headless test can read.
//
// The widths here are round numbers on purpose. A test that measured real
// glyphs would be a test of JetBrains Mono, and would go red on a font
// update with nothing about this rule having changed.
import QtQuick
import QtTest
import "../core"

TestCase {
  id: suite
  name: "RowFit"

  Component {
    id: rowFit
    RowFit {}
  }

  // Four labels, 100 px each, 10 px between them: 430 px of row, and the
  // `+N` that replaces the dropped ones is 30 px wide.
  readonly property var four: [100, 100, 100, 100]
  readonly property int gap: 10
  readonly property int marker: 30

  // Untyped on purpose, exactly as tst_wallclock.qml spawns its object:
  // `createObject` hands back a QObject, and qmllint would rather this file
  // did not call `plan()` on one. -W 0 in pkgs/jv-bar means that warning is a
  // failed build.
  function spawn(component) {
    const o = component.createObject(suite);
    verify(o, "failed to instantiate a test object");
    return o;
  }

  function fit(widths, roomPx, keepIndex) {
    return suite.spawn(rowFit).plan(widths, suite.gap, roomPx, keepIndex, suite.marker);
  }

  // What a plan draws, in one string, in layout order: the run, then the
  // marker if there is one, then the label that was held back. `w0` is the
  // workspace at index 0. It is written this way because the ORDER is half
  // the decision and a plan compared field by field would not check it.
  function drawn(plan) {
    const out = [];
    for (let i = 0; i < plan.run; i++)
      out.push("w" + i);
    if (plan.marker)
      out.push("+" + plan.dropped);
    if (plan.tail >= 0)
      out.push("w" + plan.tail);
    return out.join(" ");
  }

  function test_an_empty_row_has_nothing_to_give_up() {
    const plan = suite.fit([], 500, -1);
    compare(suite.drawn(plan), "");
    compare(plan.dropped, 0);
  }

  function test_a_row_nobody_has_measured_draws_everything() {
    // Negative room is not a narrow monitor, it is "nobody has said". A row
    // that hid labels because it had not been told how much space it had
    // would hide them in the first frame of every session.
    const plan = suite.fit(suite.four, -1, 0);
    compare(suite.drawn(plan), "w0 w1 w2 w3");
    compare(plan.dropped, 0);
    compare(plan.marker, false);
  }

  function test_everything_that_fits_is_drawn_whole() {
    // 4 * 100 + 3 * 10 = 430, and not a pixel of it is spent on a marker
    // nothing was dropped into.
    const plan = suite.fit(suite.four, 430, 0);
    compare(suite.drawn(plan), "w0 w1 w2 w3");
    compare(plan.marker, false);
    compare(plan.elidePx, 0);
  }

  function test_one_pixel_short_costs_a_whole_label() {
    // Whole labels or nothing: there is no 99-pixel `documentatio`.
    const plan = suite.fit(suite.four, 429, 0);
    compare(suite.drawn(plan), "w0 w1 w2 +1");
    compare(plan.dropped, 1);
  }

  function test_the_marker_pays_for_its_own_room() {
    // 3 * 100 + 30 + 3 * 10 = 360. A row that dropped a label and then drew
    // the `+1` in space it had not reserved would overflow by exactly the
    // width of the thing that says it did not.
    compare(suite.drawn(suite.fit(suite.four, 360, 0)), "w0 w1 w2 +1");
    compare(suite.drawn(suite.fit(suite.four, 359, 0)), "w0 w1 +2");
  }

  function test_the_one_you_are_on_is_never_dropped() {
    // The whole point. The keyboard is on the LAST workspace and only two
    // labels' worth of room is left — so the run is cut, the marker stands
    // where it was cut, and the workspace you are on is drawn after it.
    const plan = suite.fit(suite.four, 400, 3);
    compare(suite.drawn(plan), "w0 w1 +1 w3");
    compare(plan.dropped, 1);
    compare(plan.tail, 3);
  }

  function test_the_one_you_are_on_is_not_drawn_twice() {
    // …and when it is inside the run it stays there, in its own place, with
    // the marker at the end. A tail that was appended anyway would draw the
    // focused workspace once in order and once again at the far right.
    const plan = suite.fit(suite.four, 360, 1);
    compare(suite.drawn(plan), "w0 w1 w2 +1");
    compare(plan.tail, -1);
  }

  function test_a_row_with_no_workspace_of_its_own_still_collapses() {
    // niri has not activated anything on this output — possible, and not
    // this row's business. Nothing is held back, so the run is simply as
    // long as it fits.
    const plan = suite.fit(suite.four, 360, -1);
    compare(suite.drawn(plan), "w0 w1 w2 +1");
    compare(plan.tail, -1);
  }

  function test_the_marker_goes_before_the_label_you_are_reading_does() {
    // Down to one label's worth of room. `+3 w3` fits in 140 and does not in
    // 120 — and what gives way there is the COUNT, not the name: a label you
    // can read beats a number telling you about labels you cannot see.
    compare(suite.drawn(suite.fit(suite.four, 145, 3)), "+3 w3");
    const tight = suite.fit(suite.four, 120, 3);
    compare(suite.drawn(tight), "w3");
    compare(tight.marker, false);
    // Still counted, though: nothing about the plan pretends the other three
    // are not there, so a caller with somewhere to put the number has it.
    compare(tight.dropped, 3);
    compare(tight.elidePx, 0);
  }

  function test_a_label_wider_than_the_whole_row_is_the_one_thing_elided() {
    // The last resort, and the only place this rule cuts a word: ONE label —
    // the one you are on — in a row narrower than it. Every other case draws
    // whole words or does not draw them.
    const plan = suite.fit([400], 250, 0);
    compare(suite.drawn(plan), "w0");
    compare(plan.elidePx, 250);
  }

  function test_a_row_with_no_room_at_all_draws_nothing() {
    // A monitor narrower than the corner the HUD reserves. There is no such
    // output on this machine; what there is, is an arithmetic that must not
    // return a negative width to a Text.
    const plan = suite.fit(suite.four, 0, -1);
    compare(suite.drawn(plan), "");
    compare(plan.dropped, 4);
    compare(plan.elidePx, 0);
  }
}
