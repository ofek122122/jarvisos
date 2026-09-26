// The one animation in this shell, measured — because until this file nothing
// in the repository could tell it from a snap (PLAN D34).
//
// `Workspaces.qml` puts `Ease on color` on its labels and says why in a
// paragraph: your keyboard moving to another workspace is a fact about you,
// and a 200 ms settle is what makes the teal read as a MOVE rather than as a
// repaint. The contact sheet next door has a shot named for it —
// `03-focus-moved.png` — and that shot waits `fadeInMs + easeMs` before it
// grabs, on purpose, so that what lands in the PNG is a finished colour.
// Which means the sheet looks exactly the same whether the ease ran or the
// colour arrived in one frame. Every gate this shell had was in that position:
// the headless suites in shell/jv-bar/tests are pure arithmetic with no engine
// under them, and `nix build .#jv-bar` is a linter. An animation that never
// ran would have passed all of them.
//
// It did not run. The Repeater's model was a JS array that `NiriModel`
// REPLACES wholesale on every delta — it must; a list mutated in place is a
// list no binding hears about — and a Repeater handed a new array destroys its
// delegates and builds new ones. A `Behavior` does not animate an initial
// assignment, so every label was a NEW Text that had always been teal, with
// the ease attached to nothing. `core/KeyedRows.qml` is the fix: the row is
// synced into a ListModel BY WORKSPACE ID, so the label you are looking at
// survives its own desk changing and its colour has somewhere to move from.
//
// WHAT THIS FILE ASSERTS, and why each half needs the other:
//
//   · the teal ARRIVES OVER TIME. The colour on the glyph is sampled while the
//     move is happening and has to be somewhere that is neither where it
//     started nor where it is going. That is the only observation that can
//     separate a 200 ms ease from an assignment, and it is why this driver
//     exists instead of one more still picture.
//   · a workspace APPEARING still snaps, and does not recolour the labels
//     already on screen. This is the half that fails if the row is keyed by
//     POSITION rather than by id: a desk that grows at the left would hand
//     each surviving delegate its neighbour's workspace, and the strip would
//     cross-fade between two unrelated workspaces — a 200 ms lie about a
//     change that is instantaneous ("there is no intermediate state between
//     niri having a workspace and not having it").
//
// Honest about what it is NOT. Not the compositor and not niri: the desk comes
// out of `Desk.qml`, which is the recording. Not a claim about FRAMES either —
// §06's 2 ms/frame budget and the 0 fps idle are measured by the HUD's probe,
// not here. This is one question: does the colour move.
import QtQuick
import QtTest
import ".."

Item {
  id: root

  // ares' primary monitor, so the row has more room than it can use and
  // nothing here is about the collapse rule (that is `tst_rowfit.qml`'s, at
  // round numbers, and the two collapsed shots').
  width: 2560
  height: strip.implicitHeight

  Strip {
    id: strip

    width: root.width
    height: root.height
    screenName: "HDMI-A-1"
    // 09:41, the sheet's own fixed time — the clock is not what this file is
    // about, but a strip with no clock budgets its row differently, and the
    // row should be laid out the way the pictures show it.
    hours: 9
    minutes: 41
  }

  // The lines niri wrote, shared with the sheet next door.
  Desk {
    id: desk
  }

  TestCase {
    id: suite

    name: "BarSettle"
    when: windowShown

    function init() {
      Niri.reset();
    }

    // A colour as this file compares them. `color` is four floats and the
    // ease walks through values no token names, so what is compared is the
    // string a QML colour prints as — the same form `Theme.teal` prints in.
    function hex(c: color): string {
      return c.toString();
    }

    // The desk the recording describes, drawn and finished moving.
    function settled() {
      Niri.ingest(desk.recorded);
      suite.wait(Theme.fadeInMs + Theme.easeMs);
    }

    // The teal leaves the workspace you were on and arrives on the one you
    // went to, and it takes the §06 ease to do it. The sheet's
    // `03-focus-moved.png` is the two ends of this move; this is the middle,
    // which no picture can hold.
    function test_the_teal_moves_rather_than_appearing() {
      verify(Motion.animate, "motion is suppressed in this stage, so there is "
             + "nothing here to measure (" + Motion.suppressedBy + ")");

      suite.settled();
      compare(strip.desk.join(" "), "1:focused 2:idle", "the desk the recording describes");
      compare(suite.hex(strip.painted(0)), suite.hex(Theme.teal), "the workspace the keyboard is on");
      compare(suite.hex(strip.painted(1)), suite.hex(Theme.text3), "the one it is not");

      // The keyboard moves to workspace 2. The PLAN changes in this frame —
      // `drew` is what the row MEANT to draw and it is arithmetic, not a
      // value that settles.
      Niri.ingest(desk.activated(4, true));
      compare(strip.desk.join(" "), "1:idle 2:focused", "what the row now means to draw");

      // …and the PIXELS do not. Sampled across the settle: at least one
      // observation of each label has to be a colour that is neither the one
      // it left nor the one it is going to, which is the whole difference
      // between an ease and an assignment. Several samples rather than one
      // because where in the curve a sample lands depends on how long the
      // event loop happened to block, and the claim is about the move, not
      // about a particular millisecond of it.
      let moving = [0, 0];
      const trail = [];
      for (let i = 0; i < 6; i++) {
        suite.wait(Math.round(Theme.easeMs / 8));
        const now = [suite.hex(strip.painted(0)), suite.hex(strip.painted(1))];
        trail.push(now.join("/"));
        if (now[0] !== suite.hex(Theme.teal) && now[0] !== suite.hex(Theme.text3))
          moving[0] += 1;
        if (now[1] !== suite.hex(Theme.teal) && now[1] !== suite.hex(Theme.text3))
          moving[1] += 1;
      }
      console.log("the settle, sampled: " + trail.join(" "));
      verify(moving[0] > 0, "the label the keyboard LEFT went straight to "
             + suite.hex(strip.painted(0)) + " — the ease is attached to nothing");
      verify(moving[1] > 0, "the label the keyboard ARRIVED on went straight to "
             + suite.hex(strip.painted(1)) + " — the ease is attached to nothing");

      // And it finishes where the caption says it does.
      suite.wait(Theme.easeMs * 2);
      compare(suite.hex(strip.painted(0)), suite.hex(Theme.text3), "where the teal left");
      compare(suite.hex(strip.painted(1)), suite.hex(Theme.teal), "where it arrived");
    }

    // A workspace being created is not a value moving toward a target: niri
    // either has it or does not. So a new label is drawn in its colour, in the
    // frame it appears, and — the part that a positional sync would get wrong
    // — the labels ALREADY on screen keep the colours they had, even though
    // every one of them is now at a different index.
    function test_a_workspace_arriving_snaps_and_recolours_nothing() {
      suite.settled();

      // The same two workspaces with a new one in front of them: niri renumbers
      // `idx`, which is what the row lays out by, so every label moves right.
      Niri.ingest(desk.snapshot([
        { "id": 9, "idx": 1, "output": "HDMI-A-1" },
        { "id": 1, "idx": 2, "output": "HDMI-A-1", "active": true, "focused": true },
        { "id": 4, "idx": 3, "output": "HDMI-A-1" }
      ]));
      compare(strip.desk.join(" "), "1:idle 2:focused 3:idle", "the desk that grew at the left");

      // In THIS frame, with nothing waited for.
      compare(suite.hex(strip.painted(0)), suite.hex(Theme.text3), "the workspace that just appeared");
      compare(suite.hex(strip.painted(1)), suite.hex(Theme.teal),
              "the workspace the keyboard never left — it moved one place right, and a "
              + "row keyed by position would be fading it to its neighbour's colour");
      compare(suite.hex(strip.painted(2)), suite.hex(Theme.text3), "the one that was already quiet");
    }

    // The desk going away and coming back, which is the sequence that found
    // the OTHER half of D34. Keeping the list on screen in step with `shown`
    // means reading `shown` the moment it changes, and a row that derived it
    // through a chain of properties could be handed the previous desk's plan
    // over this desk's workspaces — a ten-label run composed over an empty
    // array. `Workspaces.qml` now derives the whole thing in one binding over
    // one argument, and this drives the transition that exposed it: a full
    // strip, then the stream ending, then a full strip again.
    //
    // What it can assert is the outcome. The fault itself was a TypeError on
    // the console, in a binding that recovered in the same turn, and nothing
    // in any of these harnesses fails on a console warning (PLAN D36).
    function test_the_desk_can_empty_and_come_back() {
      const names = ["documentation", "compositor", "video-editing", "correspondence", "nixos-rebuild"];
      const rows = names.map((name, i) => ({
        "id": i + 1,
        "idx": i + 1,
        "output": "HDMI-A-1",
        "name": name,
        "active": i === 0,
        "focused": i === 0
      }));

      Niri.ingest(desk.snapshot(rows));
      compare(strip.desk.length, names.length, "the desk niri described");

      // The compositor exits: the last snapshot is a photograph of a desk
      // that has since been rearranged, so the row empties.
      Niri.drop("niri event stream stopped");
      compare(strip.desk.join(" "), "", "a row with nothing true to say");
      compare(suite.hex(strip.painted(0)), "#00000000", "and nothing painted");

      // …and the session is replaced by one with the same desk on it.
      Niri.ingest(desk.snapshot(rows));
      compare(strip.desk.length, names.length, "the desk, back");
      compare(suite.hex(strip.painted(0)), suite.hex(Theme.teal), "the one the keyboard is on");
    }
  }
}
