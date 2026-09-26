// How wide a plate's text may be drawn on the surface it is actually on
// (PLAN D66).
//
// Six plates in this HUD cap their own text at `maxTextPx: 240`, and all six
// carry the same comment for the number: "the surface is 300 px and the plate
// sits inside its inset". That sentence is true of the corner this machine's
// three monitors give it, and it is the whole of what the plates knew — until
// this file the corner was DEAF to its own width. Measured, at thirteen
// widths from 300 px down to 32: the crowded corner laid its confirmation
// plate out 260 px wide at every one of them, including the 32 px surface,
// where 228 px of a question jv-act is waiting on an answer to was off the
// left edge of the screen.
//
// So the cap needs a second half: the room. This is the arithmetic of it, in
// numbers, with no font and no Text and no engine — the same shape
// `shell/jv-bar/core/RowFit.qml` is for the bar's row, and testable for the
// same reason.
//
// WHY THE TWO NEGATIVE ANSWERS ARE DIFFERENT, which is the whole reason this
// is a file rather than a `Math.min` in six plates. D35 landed exactly this
// bug next door: a room of ZERO — a surface that has measured itself and has
// nothing to give — and a room of NOBODY-SAID must not be spelled the same,
// because one of them means draw nothing and the other means draw everything.
// A `Math.min(cap, room - pad * 2)` answers both with a negative number, and
// a negative `Text.width` is not "no room", it is a layout the engine will
// argue with. Zero is answered here before anything else, and an unmeasured
// room leaves the declared cap standing — a plate that elided in the first
// frame of every session, before its surface had been configured, would be a
// plate that hid the news to protect a margin.
import QtQuick
import QtTest
import "../core"

Item {
  id: root

  PlateFit {
    id: fit
  }

  TestCase {
    name: "PlateFit"

    // The plates' own numbers, so the cases below are the corner's cases and
    // not arithmetic for its own sake: every capped plate declares
    // `maxTextPx: 240` and every one of them is padded by `Theme.padPx` on
    // both sides, which is 10.
    readonly property int cap: 240
    readonly property int pad: 10

    // --- nobody has said ------------------------------------------------

    // The surface has not been configured yet: `width` is 0 until the
    // compositor answers, so the room arrives negative. The declared cap
    // stands, and that direction is the safe one — the plate draws what it
    // has to say and finds out later that it had less room than it thought.
    function test_an_unmeasured_room_leaves_the_declared_cap_alone() {
      compare(fit.textPx(cap, -1, pad), cap);
      compare(fit.textPx(cap, -1000, pad), cap);
    }

    // --- the corner this machine really has -----------------------------

    // 300 px of surface, one 16 px inset at each edge: 268 px of room, 248 px
    // of it for text, and the declared cap is under that. Nothing changes on
    // any monitor ares has, which is the claim the contact sheet's thirteen
    // byte-identical pictures make in pixels and this one makes in numbers.
    function test_the_real_corner_is_wider_than_the_cap_so_the_cap_wins() {
      compare(fit.textPx(cap, 300 - 16 * 2, pad), cap);
    }

    // The boundary from the other side: room for exactly the cap and its
    // padding is not a narrow surface, it is an exact one.
    function test_room_for_exactly_the_cap_and_its_padding_yields_the_cap() {
      compare(fit.textPx(cap, cap + pad * 2, pad), cap);
    }

    // One pixel less than exact, and the cap gives up that one pixel. Not
    // the whole plate, and not nothing: the rule is elide to the room.
    function test_one_pixel_short_of_the_cap_costs_exactly_one_pixel() {
      compare(fit.textPx(cap, cap + pad * 2 - 1, pad), cap - 1);
    }

    // --- narrower than the corner ---------------------------------------

    // The room, minus the padding the plate draws inside. This is the case
    // the whole item is about: a 256 px output leaves 224 px of room, 204 px
    // of which is text.
    function test_a_narrow_surface_narrows_the_text_to_what_is_left() {
      compare(fit.textPx(cap, 256 - 16 * 2, pad), 256 - 16 * 2 - pad * 2);
      compare(fit.textPx(cap, 100, pad), 80);
    }

    // --- the two zeros --------------------------------------------------

    // Room for the padding and not one pixel more. The text is gone and the
    // answer is ZERO — never a negative, which is what a plain
    // `Math.min(cap, room - pad * 2)` would have returned here.
    function test_room_for_only_the_padding_is_no_room_for_text() {
      compare(fit.textPx(cap, pad * 2, pad), 0);
    }

    // Narrower than the plate's own padding. Still zero: the surface has
    // measured itself and has nothing to give, which is a different fact
    // from not having measured, and the two must not come out the same.
    function test_a_room_narrower_than_the_padding_is_still_zero_not_negative() {
      compare(fit.textPx(cap, pad, pad), 0);
      compare(fit.textPx(cap, 1, pad), 0);
      compare(fit.textPx(cap, 0, pad), 0);
    }

    // And the pair, side by side, because this is the distinction the file
    // exists for: 0 px of room hides the text, and -1 px of room means
    // nobody has said and hides nothing.
    function test_no_room_and_no_answer_are_not_the_same_room() {
      compare(fit.textPx(cap, 0, pad), 0);
      compare(fit.textPx(cap, -1, pad), cap);
    }

    // --- what it never returns ------------------------------------------

    // The sweep. A `Text.width` is the one output of this file, and there is
    // no width a layout can be handed that is below zero or above the cap —
    // at any room, including every room between the two answers above.
    function test_no_room_yields_a_width_outside_zero_and_the_cap() {
      for (let room = -40; room <= 400; room++) {
        const px = fit.textPx(cap, room, pad);
        verify(px >= 0, "room " + room + " gave " + px + " px of text");
        verify(px <= cap, "room " + room + " gave " + px + " px past a " + cap + " px cap");
      }
    }

    // Monotone over the room, which is the property that makes this a fit
    // rule rather than a formula: a wider surface never draws LESS of what
    // the plate has to say. Checked from zero up, because below zero the
    // answer is deliberately the opposite (the cap, not nothing) and the
    // step across that boundary is the subject of the check above.
    function test_a_wider_room_never_draws_less() {
      let last = fit.textPx(cap, 0, pad);
      for (let room = 1; room <= 400; room++) {
        const px = fit.textPx(cap, room, pad);
        verify(px >= last, "room " + room + " drew " + px + " px where " + (room - 1)
               + " px of room drew " + last);
        last = px;
      }
    }

    // --- a plate with no padding ----------------------------------------

    // The padding is the caller's, not this file's: every plate in this HUD
    // shares `Theme.padPx` today, and a rule that had 10 baked into it would
    // be a rule that is right about the corner and wrong about the next
    // surface that reads it.
    function test_the_padding_is_the_callers() {
      compare(fit.textPx(cap, 100, 0), 100);
      compare(fit.textPx(cap, 100, 25), 50);
      compare(fit.textPx(cap, 100, 50), 0);
    }
  }
}
