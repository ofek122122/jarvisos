// PlateFit — how wide a plate's text may be drawn on the surface it is on
// (PLAN D66).
//
// Six plates in this HUD cap their own text (`maxTextPx: 240`), and all six
// carried the same comment for the number: "the surface is 300 px and the
// plate sits inside its inset". True of the corner ares' three monitors
// give it, and the whole of what the plates knew — the corner was DEAF to
// its own width. Measured at thirteen widths from 300 px down to 32: the
// crowded corner laid its confirmation plate out 260 px wide at every one of
// them, so on a 32 px surface 228 px of a question jv-act is waiting on an
// answer to sat off the left edge of the screen. Nothing errored and nothing
// logged, because nothing in the HUD had ever been told what it was on.
//
// It is the BAR's problem, one process over, with one difference that
// decides the rule. `core/RowFit.qml` may DROP a workspace name: the row's
// job is to say which desk your keyboard is in, and three names you are not
// looking at are worth less than the one you are. A plate has no such
// ranking — the plate that would be dropped is as likely to be the one
// saying an action failed as it is the recording light — and PlateStack
// exists precisely because "the plate that was trying to warn you never
// appeared" is the worst way this surface can be wrong. So nothing is ever
// hidden here. The text elides to the room, and the plate keeps its label:
// less of what it had to say, never none of it, and never a word laid out
// where the screen ends.
//
// WHY THE TWO NEGATIVES ARE DIFFERENT ANSWERS, which is the reason this is a
// file and not a `Math.min` in six plates. D35 shipped exactly this bug next
// door: a room of ZERO — a surface that has measured itself and has nothing
// to give — and a room of NOBODY-HAS-SAID must not be spelled the same, and
// `Math.min(cap, roomPx - padPx * 2)` spells both as a negative number. One
// of them means draw nothing; the other means draw everything, because a
// plate that elided in the first frame of every session — before the
// compositor had configured its surface — would be a plate that hid the news
// to protect a margin. Zero is answered before anything else and an
// unmeasured room leaves the cap alone. `tests/tst_platefit.qml` holds both,
// and holds the step between them.
//
// Pure arithmetic over numbers: no font, no Text, no engine. The pixels come
// from the caller — its own `maxTextPx`, its own `Theme.padPx`, and the room
// its surface measured — because a rule that knew this HUD's padding would be
// a rule that is right about the corner and wrong about the next surface.
import QtQuick

QtObject {
  id: root

  // How many pixels of text a plate may lay out.
  //
  //   declaredPx — the plate's own cap, the width it will not exceed however
  //                much room it has. A choice about how much of the corner a
  //                sentence may take, not a measurement.
  //   roomPx     — how much width the plate HAS, padding included: the
  //                surface it is on, less the insets it is anchored by.
  //                NEGATIVE means nobody has said, and then the declared cap
  //                stands untouched.
  //   padPx      — what the plate draws inside its own edge, one side. Text
  //                pays for it twice.
  //
  // Never below zero and never above the cap, at any room.
  function textPx(declaredPx: int, roomPx: int, padPx: int): int {
    // Nobody has measured this surface yet. Say everything.
    if (roomPx < 0)
      return declaredPx;
    // It has been measured, and what is left after the padding is nothing.
    // Answered here, first, because every arithmetic below it comes out
    // negative in this case and a negative `Text.width` is not "no room".
    const textRoom = roomPx - padPx * 2;
    if (textRoom <= 0)
      return 0;
    return Math.min(declaredPx, textRoom);
  }
}
