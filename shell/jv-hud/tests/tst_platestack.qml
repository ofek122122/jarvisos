// PlateStack — "does the HUD have anything on screen?", under test (A15).
//
// This one property decides whether the surface is mapped at all, which
// makes both of its failures invisible by construction:
//
//   · false when something IS drawing — the plate that was trying to tell
//     you the microphone died never appears, and nothing anywhere fails.
//     That is the bug A15 exists to kill: the old hand-written OR in
//     shell.qml grew a term per element, and the next element to forget
//     itself would have landed here.
//   · true when nothing is drawing — an empty surface stays mapped, which
//     is §06's "0 fps when idle" quietly broken.
//
// So the tests are mostly about the ways a stack can be asked the question
// and answer it wrongly: a plate that is not the first one, a plate added
// after the stack was built, a plate that answered yes and has since gone
// quiet while another still has something to say, and — the one that would
// rot without anybody noticing — `anyLit` being a value computed once at
// startup rather than a live binding an element can watch.
//
// Headless, like the rest of core/: a PlateStack is a Column, and the fake
// plates below are Items with the two properties a real plate declares.
import QtQuick
import QtTest
import "../core"

TestCase {
  id: suite
  name: "PlateStack"

  // A stand-in for a real plate: the two questions the stack asks, plus
  // the self-visibility every plate in shell.qml declares, so the layout
  // test below is exercising the real arrangement.
  Component {
    id: plate

    Item {
      property bool shown: false
      property bool lit: false
      // Every real plate declares one (A53); the default here is what a
      // plate that forgot to would look like.
      property string plateName: ""

      implicitWidth: 40
      implicitHeight: 10
      visible: shown || lit
    }
  }

  // A child that answers NEITHER question — the shape of a future element
  // that forgets the contract, or of something that is not a plate at all.
  Component {
    id: mute

    Item {
      implicitWidth: 40
      implicitHeight: 10
    }
  }

  // A child that answers only one of the two. It CAN be asked, so the
  // fail-safe below must not fire for it.
  Component {
    id: halfPlate

    Item {
      property bool lit: false

      implicitWidth: 40
      implicitHeight: 10
      visible: lit
    }
  }

  Component {
    id: plateStack

    PlateStack {}
  }

  // createObject() is typed QObject, so every member read on the result
  // would be `missing-property` to qmllint. Going through an untyped
  // helper keeps the file lint-clean (see tst_speechstate).
  function spawn(component, parent, props) {
    const o = component.createObject(parent, props || {});
    verify(o, "failed to instantiate a test object");
    return o;
  }

  function makeStack() {
    return spawn(plateStack, suite, {});
  }

  // What an element actually does with this property: bind to it. A binding
  // re-evaluates only if what it read is a real notifying property, so this
  // is what catches an `anyLit` that got computed once and frozen. -1 means
  // nothing is attached, so a test that forgets to wire it up reads as
  // broken rather than as "nothing on screen".
  QtObject {
    id: watcher

    property var source: null
    readonly property int mapped: watcher.source ? (watcher.source.anyLit ? 1 : 0) : -1
    // The same question asked of `litNames` (A53). "null" rather than -1
    // because a list has no out-of-band value of its own.
    readonly property string named: watcher.source ? watcher.source.litNames.join(",") : "null"
  }

  // --- the default: a stack with nothing in it shows nothing -------------

  function test_an_empty_stack_is_not_lit() {
    const stack = makeStack();
    compare(stack.anyLit, false, "nothing in the stack means nothing on screen");
  }

  function test_silent_plates_leave_the_surface_unmapped() {
    const stack = makeStack();
    spawn(plate, stack, {});
    spawn(plate, stack, {});
    compare(stack.anyLit, false, "plates with nothing to say draw nothing");
  }

  // --- the two ways a plate is on screen --------------------------------

  function test_a_plate_with_something_to_say_maps_the_surface() {
    const stack = makeStack();
    spawn(plate, stack, { shown: true });
    // `shown` alone, with `lit` still false: this is the instant a frame
    // lands, BEFORE the fade has moved any opacity. If the surface waited
    // for `lit` here it would never map at all — an unmapped window has no
    // animation driver, so the fade that would have lit it never runs.
    compare(stack.anyLit, true, "a plate with something to say must map the surface");
  }

  function test_a_plate_still_fading_out_keeps_the_surface_mapped() {
    const stack = makeStack();
    spawn(plate, stack, { shown: false, lit: true });
    // The exit: the plate has nothing left to say and is evaporating. Drop
    // the surface now and the last frame is the window vanishing out from
    // under an element mid-fade.
    compare(stack.anyLit, true, "a plate must be allowed to finish leaving");
  }

  // --- it asks ALL of them ----------------------------------------------

  function test_a_plate_that_is_not_the_first_one_still_counts() {
    const stack = makeStack();
    spawn(plate, stack, {});
    spawn(plate, stack, {});
    const third = spawn(plate, stack, {});
    compare(stack.anyLit, false);
    third.shown = true;
    compare(stack.anyLit, true, "the last plate in the stack is as real as the first");
  }

  function test_a_plate_added_after_the_stack_was_built_counts() {
    const stack = makeStack();
    compare(stack.anyLit, false);
    // The old OR was written once, at the top of shell.qml, against the
    // elements that existed that day. A stack that only counts the children
    // it was born with has the same bug with extra steps.
    spawn(plate, stack, { shown: true });
    compare(stack.anyLit, true, "a plate added later is still a plate");
  }

  function test_the_plate_that_said_yes_going_quiet_does_not_hide_the_others() {
    const stack = makeStack();
    const first = spawn(plate, stack, { shown: true });
    const second = spawn(plate, stack, { shown: true });
    compare(stack.anyLit, true);
    // The answer stops at the first yes, so `second` was never read while
    // `first` was speaking. If that shortcut were a cache rather than a
    // re-evaluated binding, the surface would unmap here with a plate still
    // on it.
    first.shown = false;
    compare(stack.anyLit, true, "the second plate still has something to say");
    second.shown = false;
    compare(stack.anyLit, false, "and now nothing does");
  }

  // --- the fail-safe direction ------------------------------------------

  function test_a_child_that_cannot_answer_is_assumed_to_be_drawing() {
    const stack = makeStack();
    spawn(mute, stack, {});
    // Of the two ways to be wrong about an unaskable child, this is the one
    // that costs idle frames instead of losing a plate. A tools test keeps
    // this branch unreachable in the real shell by checking every plate
    // declares both properties.
    compare(stack.anyLit, true, "a plate we cannot ask might be drawing");
  }

  function test_a_half_answering_child_is_taken_at_its_word() {
    const stack = makeStack();
    // `lit` present, `shown` absent: it CAN answer, so the fail-safe does
    // not apply and a plain "no" is a no.
    const half = spawn(halfPlate, stack, {});
    compare(stack.anyLit, false, "it answered, and the answer was no");
    half.lit = true;
    compare(stack.anyLit, true);
  }

  // --- it is a live binding, not a startup value -------------------------

  function test_anylit_is_a_property_an_element_can_bind_to() {
    const stack = makeStack();
    const p = spawn(plate, stack, {});
    watcher.source = stack;
    compare(watcher.mapped, 0, "the watcher must see an empty stack as unmapped");
    p.shown = true;
    compare(watcher.mapped, 1, "anyLit must notify, or the surface never maps");
    p.shown = false;
    p.lit = true;
    compare(watcher.mapped, 1, "still on screen while it fades");
    p.lit = false;
    compare(watcher.mapped, 0, "and the surface goes away when it does");
    watcher.source = null;
  }


  // --- A53: WHICH plates, not just whether any --------------------------

  // `anyLit` is what maps the surface, so everything watching this HUD from
  // outside could only ever measure that SOMETHING was drawn. Five checks
  // in the two shot harnesses say "the corner got taller"; none of them
  // could say which plate made it taller, and two plates in this stack draw
  // the same two lines in the same colour. `litNames` is the answer, and
  // these are the ways a list of names can be wrong where a boolean could
  // not be: right count and wrong order, right plates and a stale one still
  // in it, a name that came from the harness rather than from the plate.

  function test_an_empty_stack_names_nobody() {
    const stack = makeStack();
    compare(stack.litNames.length, 0, "nothing in the stack means nobody to name");
  }

  function test_silent_plates_are_not_named() {
    const stack = makeStack();
    spawn(plate, stack, { plateName: "mic" });
    spawn(plate, stack, { plateName: "health" });
    compare(stack.litNames.join(","), "", "a plate with nothing to say is not on screen");
  }

  function test_only_the_plates_on_screen_are_named() {
    const stack = makeStack();
    spawn(plate, stack, { plateName: "link" });
    spawn(plate, stack, { plateName: "state", shown: true });
    spawn(plate, stack, { plateName: "mic" });
    spawn(plate, stack, { plateName: "health", shown: true });
    compare(stack.litNames.join(","), "state,health",
            "the list is the plates that are drawing, and only those");
  }

  function test_the_names_come_in_stack_order_not_in_arrival_order() {
    const stack = makeStack();
    const first = spawn(plate, stack, { plateName: "state" });
    const second = spawn(plate, stack, { plateName: "mic" });
    // The second plate lights FIRST. Reading order is what a human sees in
    // the corner and what the sheet is a picture of, so the list is the
    // stack's order and never the order the frames happened to land in.
    second.shown = true;
    first.shown = true;
    compare(stack.litNames.join(","), "state,mic", "top of the stack first");
  }

  function test_a_plate_still_fading_out_is_still_named() {
    const stack = makeStack();
    spawn(plate, stack, { plateName: "guard", shown: false, lit: true });
    compare(stack.litNames.join(","), "guard",
            "it is on screen until the fade ends, so it is in the list until then");
  }

  function test_a_plate_that_went_quiet_leaves_the_list() {
    const stack = makeStack();
    const p = spawn(plate, stack, { plateName: "confirm", shown: true });
    compare(stack.litNames.join(","), "confirm");
    p.shown = false;
    compare(stack.litNames.join(","), "",
            "a name left behind would be a plate the sheet swears is on screen");
  }

  // --- the fail-safe, and why it is a name rather than a silence ---------

  function test_a_child_that_cannot_answer_is_named_as_unknown() {
    const stack = makeStack();
    spawn(mute, stack, {});
    // `anyLit` counts it as drawing, so the list must too — a list that
    // skipped it would say "nothing is on screen" about a mapped surface,
    // which is the one disagreement between the two that must never happen.
    compare(stack.litNames.join(","), "?", "something is there and it will not say what");
  }

  function test_a_plate_with_no_name_is_named_as_unknown() {
    const stack = makeStack();
    // It answers `shown`, so it is genuinely on screen; it just never said
    // who it is. Nothing may be invented on its behalf — a tools test keeps
    // this unreachable in the real shell by pinning every plate's name to
    // its file name.
    spawn(plate, stack, { shown: true });
    compare(stack.litNames.join(","), "?", "an unnamed plate is not an absent plate");
  }

  // --- the two answers must never disagree ------------------------------

  // `anyLit` is a separate, cheaper implementation of "is anything on
  // screen" and it is the one that maps the surface. Two implementations of
  // one fact drift; this is what stops them.
  function test_anylit_and_litnames_always_agree() {
    const stack = makeStack();
    const a = spawn(plate, stack, { plateName: "state" });
    const b = spawn(plate, stack, { plateName: "mic" });
    const cases = [
      { shownA: false, litA: false, shownB: false, litB: false },
      { shownA: true, litA: false, shownB: false, litB: false },
      { shownA: false, litA: true, shownB: false, litB: false },
      { shownA: false, litA: false, shownB: true, litB: false },
      { shownA: false, litA: false, shownB: false, litB: true },
      { shownA: true, litA: true, shownB: true, litB: true }
    ];
    for (let i = 0; i < cases.length; i++) {
      const c = cases[i];
      a.shown = c.shownA;
      a.lit = c.litA;
      b.shown = c.shownB;
      b.lit = c.litB;
      compare(stack.litNames.length > 0, stack.anyLit,
              "case " + i + ": the surface is mapped iff the list has a name in it");
    }
    // And the unaskable child, where the fail-safe is the whole point.
    spawn(mute, stack, {});
    compare(stack.litNames.length > 0, stack.anyLit, "the unaskable child");
    compare(stack.anyLit, true);
  }

  // --- it is a live binding, not a startup value -------------------------

  function test_litnames_is_a_property_an_element_can_bind_to() {
    const stack = makeStack();
    const p = spawn(plate, stack, { plateName: "heard" });
    watcher.source = stack;
    compare(watcher.named, "", "the watcher must see an empty stack as naming nobody");
    p.shown = true;
    compare(watcher.named, "heard", "litNames must notify, or nothing can watch it");
    p.shown = false;
    p.lit = true;
    compare(watcher.named, "heard", "still on screen while it fades");
    p.lit = false;
    compare(watcher.named, "", "and gone when it is");
    watcher.source = null;
  }

  function test_a_plate_added_after_the_stack_was_built_is_named_too() {
    const stack = makeStack();
    watcher.source = stack;
    compare(watcher.named, "");
    spawn(plate, stack, { plateName: "output", shown: true });
    compare(watcher.named, "output", "a plate added later is still a plate");
    watcher.source = null;
  }

  // --- the layout contract the HUD leans on -----------------------------

  // A PlateStack is a positioner, not a bare Item — the plates have to
  // stack, and nothing in shell.qml gives them a y of their own. Change the
  // base type and three plates land on top of each other.
  //
  // What is NOT asserted here, deliberately: that the plates below a
  // silenced one close up over its gap. A Column repositions on polish, and
  // an offscreen window that is never exposed has no polish cycle, so the
  // engine these tests run in cannot answer that question at all. It is
  // Qt's behaviour rather than ours; what makes it FIRE is that every plate
  // declares its own `visible`, and that is checked in tools/tests where it
  // can be.
  function test_the_plates_stack_instead_of_landing_on_each_other() {
    const stack = makeStack();
    stack.spacing = 4;
    const first = spawn(plate, stack, { shown: true });
    const middle = spawn(plate, stack, { shown: true });
    const last = spawn(plate, stack, { shown: true });
    tryCompare(first, "y", 0);
    tryCompare(middle, "y", 14);
    tryCompare(last, "y", 28);
  }
}
