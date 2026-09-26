// The top bar, photographed — because it is the one surface on this machine
// that is ALWAYS on screen, and the last one with no picture of itself
// (PLAN D13).
//
// The HUD earned a sheet by being the thing that speaks; the notification
// corner earned one by holding strings this repo did not write. The bar earns
// one differently: it is 31 px tall, it spans every monitor, and it is up from
// the moment the session starts until it ends. Nothing else on the desktop is
// looked at as often or as briefly — which means every one of its decisions is
// a decision about a glance, and a glance is exactly what no headless test can
// take. Until this file the strip, the workspaces row and the clock were
// reached by no QML gate at all: `nix build .#jv-bar` runs qmllint over them
// and `tools/tests/test_dependents.py` wrote the gap down so it would not
// become invisible.
//
// WHAT IT ASSERTS, beyond being pictures. Per shot: the row's own account of
// what it drew — `<label>:<reading>` per workspace, from `Workspaces.drew`,
// which names the reading in the same expression that chooses the colour — the
// clock as drawn, and TWO NUMBERS that are the bar's side of a promise nothing
// else in this repo can check:
//
//   · `hudOverflowPx`, how far the workspaces row reaches into the corner
//     shell.qml reserves for the HUD. The HUD is another process on another
//     layer; it draws OVER this strip and neither surface can see the other,
//     so two things in one corner is the one arrangement nothing on this
//     machine can report. It must be zero on every shot.
//   · `clockOverlapPx`, how far the row reaches past the clock — which is
//     centred on the SCREEN and so cannot move out of the way.
//
// Both are questions only a laid-out surface answers, and both are about a
// string the user chose the length of: niri lets a workspace be NAMED, and a
// named workspace puts an arbitrary word in a row that has no width of its own
// — the same shape as the app-name row that painted 656 px past its plate the
// first time the notification sheet was taken.
//
// Honest about what it is NOT:
//   · not the compositor. Layer-shell, the empty input mask, the exclusive
//     zone that tiles windows below the strip, `WlrKeyboardFocus.None` and the
//     one-surface-per-monitor `Variants` are shell.qml's, and a human at ares
//     is the only thing that can confirm them.
//   · not niri. There is no compositor here: the lines go in through the
//     stand-in next door, out of `Desk.qml` — which is where this directory
//     keeps its one copy of the recording, since the settle driver needs the
//     same desk to start from (PLAN D34). Where the desk is ares' own it is
//     `harness/fixtures/niri/ares-desk.jsonl` byte for byte, the line niri
//     really wrote. The two shots that need a desk ares does not have (named
//     workspaces, a crowded row) are COMPOSED, in the recording's own shape,
//     and docs/bar/README.md says which is which.
import QtQuick
import QtTest
import ".."

Item {
  id: root

  // The monitor this shot is taken on, in pixels, set per shot. The bar spans
  // the output (`anchors { left: true; right: true }`), so the width IS the
  // screen's and there is no box for the harness to choose — which is why the
  // clock's `fits` binding can only be answered at a real width.
  property int screenPx: 2560

  width: root.screenPx
  // Derived exactly as shell.qml derives it, from the same two tokens: one
  // label's worth of type with §06's padding above and below. A sheet whose
  // strip was a height somebody picked would be a picture of the harness.
  height: strip.implicitHeight

  Strip {
    id: strip

    width: root.width
    height: root.height
  }

  // The lines niri wrote, shared with the other driver in this directory
  // (PLAN D34) so that the copy of the recording exists once.
  Desk {
    id: desk
  }

  TestCase {
    id: suite

    name: "BarShots"
    when: windowShown

    // --- shots ----------------------------------------------------------

    // ares' primary monitor, exactly as niri described it. Two workspaces: the
    // one your keyboard is in, in teal, and the one beside it in the quietest
    // grey the palette has. This is the bar as it is for most of a day.
    function shot_primary() {
      Niri.ingest(desk.recorded);
    }

    // The same instant, one monitor over. DP-1's only workspace is ACTIVE —
    // it is what that screen is showing — and not focused, because the
    // keyboard is on HDMI-A-1. `text_2` rather than `text_3` is the whole of
    // that distinction, and it is the reason there are two quiet greys here
    // instead of one: "on screen somewhere" and "not on screen" are different
    // facts about a workspace.
    function shot_side() {
      Niri.ingest(desk.recorded);
    }

    // Your keyboard moving, which is the one thing this strip exists to say.
    // The teal leaves workspace 1 and arrives on workspace 2 — the only
    // property on this surface that eases rather than snapping (§06: a value
    // moves toward its target), because the move IS the signal.
    function shot_focus_moved() {
      Niri.ingest(desk.recorded);
      Niri.ingest(desk.activated(4, true));
    }

    // A window on the workspace you are not looking at wants you. `warn`, and
    // deliberately NOT the ember: ember means Jarvis is doing something, and
    // any window on the machine can raise this.
    function shot_urgent() {
      Niri.ingest(desk.recorded);
      Niri.ingest(desk.urgency(4, true));
    }

    // The first seconds of a session: the bar is mapped, niri has not
    // described the desk, and nothing has said the time. §06's earned
    // emptiness at its most literal — a surface that is genuinely empty rather
    // than full of placeholders. A bar that drew "00:00" here, or three grey
    // pips for workspaces it had not been told about, would be lying in the
    // first frame the user ever sees.
    function shot_starting() {
      // Nothing. `Niri.reset()` in the loop below is the whole shot.
    }

    // And the same emptiness arriving from the other direction: niri had
    // described the desk, and then the event stream ended (the compositor
    // exited, or the session was replaced). The workspaces go, because the
    // last snapshot is a photograph of a desk that has since been rearranged —
    // and the clock stays, which is what the bar still has a right to say and
    // the reason the strip earns its place before anything else is alive.
    function shot_lost() {
      Niri.ingest(desk.recorded);
      Niri.drop("niri event stream stopped");
    }

    // COMPOSED: a desk whose workspaces are named. niri sends the name in the
    // same field it sends `null` in, and `NiriModel` prefers it to the index —
    // "the label is whichever one the user would say out loud". The point of
    // photographing it is that the name is the first string on this surface
    // that a person chose the LENGTH of.
    function shot_named() {
      Niri.ingest(desk.snapshot([
        { "id": 1, "idx": 1, "output": "HDMI-A-1", "name": "web", "active": true, "focused": true },
        { "id": 4, "idx": 2, "output": "HDMI-A-1", "name": "code" },
        { "id": 7, "idx": 3, "output": "HDMI-A-1", "name": "chat" }
      ]));
    }

    // COMPOSED, and the question this sheet exists to ask: a full desk of
    // long-named workspaces on the narrower of ares' two monitor sizes. The
    // row has no width of its own — it is a `Row`, which takes its width from
    // its children — so this is where it either stays inside the space the
    // surface has for it or paints across the clock and into the HUD's corner.
    // The two numbers in the caption are the answer.
    function shot_crowded() {
      Niri.ingest(desk.snapshot([
        { "id": 1, "idx": 1, "output": "DP-1", "name": "documentation", "active": true, "focused": true },
        { "id": 2, "idx": 2, "output": "DP-1", "name": "compositor" },
        { "id": 3, "idx": 3, "output": "DP-1", "name": "video-editing" },
        { "id": 4, "idx": 4, "output": "DP-1", "name": "correspondence" },
        { "id": 5, "idx": 5, "output": "DP-1", "name": "nixos-rebuild", "urgent": true },
        { "id": 6, "idx": 6, "output": "DP-1", "name": "measurements" }
      ]));
    }

    // COMPOSED, and the shot D32 was raised to take: a desk with more names on
    // it than the strip has room for. The rule is `core/RowFit.qml`'s — as many
    // WHOLE labels as fit, then a `+N` where the row was cut — and here the
    // keyboard is on the FIRST workspace, so the run simply stops and the
    // number is the last thing on the row. Nothing is elided and nothing is
    // clipped: every name on screen is a name, and the ones that are not there
    // are counted rather than quietly missing.
    function shot_collapsed() {
      Niri.ingest(desk.snapshot(suite.crowd(1)));
    }

    // The same desk and the same monitor, with the keyboard on the LAST
    // workspace — which is the half of the rule that is not arithmetic. The
    // one you are on is reserved before the run is filled and drawn after the
    // marker, so the row reads "these, then some, then you". One of the
    // workspaces you cannot see is asking for you, and that is why the `+N` is
    // in `warn` rather than the quietest grey: a row that hid a window's call
    // for attention and said nothing would be doing the thing the marker
    // exists to prevent.
    function shot_collapsed_focus_last() {
      const rows = suite.crowd(10);
      rows[7].urgent = true;
      Niri.ingest(desk.snapshot(rows));
    }

    // A monitor narrow enough that the centre of the screen falls inside the
    // HUD's corner. The clock hides itself rather than be drawn under another
    // process's plates — `fits` in shell.qml — and the workspaces stay,
    // because the left end of the strip is nobody else's. ares has no such
    // output; a 640 px one is what a projector or a capture device gives you,
    // and shell.qml says this "should fail visibly on the fourth" monitor.
    // This is what visibly looks like.
    function shot_narrow() {
      Niri.ingest(desk.recorded);
    }

    // COMPOSED, and narrower still: an output narrower than the corner this
    // strip reserves for the HUD (PLAN D35). 320 px against a 316 px reserve
    // leaves the row a budget of 320 - 316 - inset - gap = -20 px, and the
    // shot is here because a NEGATIVE budget is spelled the same way as
    // "nobody has said how wide this monitor is" — which draws everything.
    // Everything, on this output, is one label inside another process's
    // corner, and the only surface that could have reported it is this one.
    //
    // ares has no such output and neither does anything else: 320 px is a
    // capture device or a virtual sink, and the reason to photograph a
    // monitor nobody has is that the strip's own arithmetic decides what
    // happens at widths nobody chose. The same desk as 09 on the same output,
    // so the ONLY thing that differs between the two pictures is the width.
    function shot_no_room() {
      Niri.ingest(desk.recorded);
    }

    // A desk of ten named workspaces on one output, with the keyboard on the
    // `focus`th of them. More names than a 1920 px strip has room for, which
    // is the whole point of it — and every one of them is the kind of word
    // somebody really calls a workspace, because a desk of `aaaaaaaaaaaa`
    // would photograph the arithmetic rather than the bar.
    function crowd(focus: int): var {
      const names = ["documentation", "compositor", "video-editing", "correspondence", "nixos-rebuild", "measurements", "screenshots", "references", "long-running-builds", "scratch"];
      const out = [];
      for (let i = 0; i < names.length; i++)
        out.push({
          "id": i + 1,
          "idx": i + 1,
          "output": "DP-1",
          "name": names[i],
          "active": i + 1 === focus,
          "focused": i + 1 === focus
        });
      return out;
    }

    // --- the sheet --------------------------------------------------------

    // name -> what it is, in reading order. The file names carry the order so
    // a directory listing is the sheet.
    //
    // `desk` is the CAPTION, asserted: one entry per label on screen, in
    // layout order, each `<label>:<reading>` as the row itself reports it.
    // `clock` is the clock as drawn ("" when it is not there). `overlap` is
    // how far the row paints past the clock — a number rather than a flag
    // because "they touch" and "they cross by 300 px" are different bugs.
    readonly property var sheet: [
      { "file": "01-primary.png", "build": suite.shot_primary, "screen": 2560, "output": "HDMI-A-1", "desk": ["1:focused", "2:idle"], "clock": "09:41", "overlap": 0 },
      { "file": "02-side.png", "build": suite.shot_side, "screen": 1920, "output": "DP-1", "desk": ["1:active"], "clock": "09:41", "overlap": 0 },
      { "file": "03-focus-moved.png", "build": suite.shot_focus_moved, "screen": 2560, "output": "HDMI-A-1", "desk": ["1:idle", "2:focused"], "clock": "09:41", "overlap": 0 },
      { "file": "04-urgent.png", "build": suite.shot_urgent, "screen": 2560, "output": "HDMI-A-1", "desk": ["1:focused", "2:urgent"], "clock": "09:41", "overlap": 0 },
      // No desk and no time: both unknown, so both draw nothing.
      { "file": "05-starting.png", "build": suite.shot_starting, "screen": 2560, "output": "HDMI-A-1", "desk": [], "clock": "", "overlap": 0 },
      { "file": "06-lost.png", "build": suite.shot_lost, "screen": 2560, "output": "HDMI-A-1", "desk": [], "clock": "09:41", "overlap": 0 },
      { "file": "07-named.png", "build": suite.shot_named, "screen": 2560, "output": "HDMI-A-1", "desk": ["web:focused", "code:idle", "chat:idle"], "clock": "09:41", "overlap": 0 },
      { "file": "08-crowded.png", "build": suite.shot_crowded, "screen": 1920, "output": "DP-1", "desk": ["documentation:focused", "compositor:idle", "video-editing:idle", "correspondence:idle", "nixos-rebuild:urgent", "measurements:idle"], "clock": "09:41", "overlap": 0 },
      // The clock is gone, and that is the shot.
      { "file": "09-narrow.png", "build": suite.shot_narrow, "screen": 640, "output": "DP-2", "desk": ["1:active"], "clock": "", "overlap": 0 },
      // More names than the strip has room for, which is what the two numbers
      // in every caption above were counting down to (PLAN D32).
      { "file": "10-collapsed.png", "build": suite.shot_collapsed, "screen": 1920, "output": "DP-1", "desk": ["documentation:focused", "compositor:idle", "video-editing:idle", "correspondence:idle", "nixos-rebuild:idle", "measurements:idle", "screenshots:idle", "references:idle", "+2:idle"], "clock": "09:41", "overlap": 0 },
      { "file": "11-collapsed-focus-last.png", "build": suite.shot_collapsed_focus_last, "screen": 1920, "output": "DP-1", "desk": ["documentation:idle", "compositor:idle", "video-editing:idle", "correspondence:idle", "nixos-rebuild:idle", "measurements:idle", "screenshots:idle", "+2:urgent", "scratch:focused"], "clock": "09:41", "overlap": 0 },
      // Narrower than the corner the HUD reserves: the row has no pixels it
      // is allowed to paint in, so it paints none. An empty strip, and the
      // only empty strip on this sheet that is empty because there is no
      // room rather than because there is nothing to say (PLAN D35).
      { "file": "12-no-room.png", "build": suite.shot_no_room, "screen": 320, "output": "DP-2", "desk": [], "clock": "", "overlap": 0 }
    ]

    function test_the_sheet() {
      for (let i = 0; i < suite.sheet.length; i++) {
        const shot = suite.sheet[i];

        Niri.reset();
        root.screenPx = shot.screen;
        strip.screenName = shot.output;
        // 09:41, on every shot that knows the time. Fixed, because a sheet
        // rendered against the wall clock would be a different picture every
        // minute and could never be compared with the one committed at HEAD.
        strip.hours = shot.clock.length > 0 ? 9 : -1;
        strip.minutes = shot.clock.length > 0 ? 41 : -1;
        shot.build();

        // Past the one animation in this shell — the label colour settling
        // when your keyboard arrives on another workspace — so the grab lands
        // on a finished colour rather than inside the ease. Nothing else here
        // moves at all.
        wait(Theme.fadeInMs + Theme.easeMs);

        // WHAT IS ON SCREEN, as the row itself reports it. Two shots of this
        // surface look almost identical — the entire vocabulary is a few
        // characters in one of four greys — so without this line a harness
        // that sent a snapshot the model refused would photograph a plausible
        // bar and assert nothing.
        compare(strip.desk.join(" "), shot.desk.join(" "), shot.file + ": the workspaces on screen");
        compare(strip.clockText, shot.clock, shot.file + ": the clock");

        // AND NOTHING IS LAID OUT IN THE HUD'S CORNER. shell.qml promises it
        // in prose — "nothing may be laid out inside it" — to a process that
        // cannot hear the promise and draws there regardless. This is the only
        // thing in the repository that checks it.
        compare(strip.hudOverflowPx, 0, shot.file + ": the row paints "
                + strip.hudOverflowPx + " px into the HUD's corner");
        compare(strip.clockOverlapPx, shot.overlap, shot.file + ": the row paints "
                + strip.clockOverlapPx + " px past the clock");

        // The margin, said out loud. `clockOverlapPx` above is the promise and
        // it is asserted at zero; this is how much room is LEFT before that
        // assertion starts failing, and it is printed rather than pinned
        // because it is arithmetic over glyph widths — a number that would
        // make this suite fail on a font update without anything being wrong.
        // Printing it is what keeps "how many more workspaces fit" a fact
        // somebody has seen rather than a thing nobody measured (PLAN D32).
        console.log(shot.file + ": " + strip.clockClearPx
                    + " px between the workspaces and the clock");

        const img = grabImage(root);
        compare(img.width, root.width, shot.file + ": width");
        compare(img.height, root.height, shot.file + ": height");
        // Relative to the process's working directory — ops/ralph/barshots.sh
        // runs the runner from the output directory, which is how a QML test
        // with no way to read an environment variable is told where to put its
        // files.
        img.save(shot.file);
      }
    }
  }
}
