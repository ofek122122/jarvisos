// KeyedRows — the list a Repeater keeps its delegates across, under test
// (PLAN D34).
//
// This is the half of the fix that is a rule rather than a picture. The bar's
// one animation — the teal arriving on the workspace your keyboard moved to —
// ran on nothing for as long as the row existed, because the Repeater was
// handed a fresh JS array on every niri delta and a Repeater handed a fresh
// array destroys every delegate it has. A `Behavior` does not animate an
// initial assignment, so each label was a new Text that had always been teal.
//
// `core/KeyedRows.qml` syncs the rows into a `ListModel` BY KEY, so a row that
// is still there keeps its delegate. Two things have to be true for that to be
// worth anything, and both are checked here with a real Repeater under them:
//
//   · the list ends up saying exactly what it was asked to say — the rows, in
//     order, with nothing left over from the desk before. A sync that quietly
//     kept a stale row would put a workspace on the strip that niri has
//     destroyed, which is the failure `NiriModel` refuses in its own words.
//   · the delegates that SURVIVE are the ones whose key survived — by
//     identity, the same objects — and a delegate that survives is one whose
//     `Behavior` can move. The delegates below carry an `Ease`-shaped
//     Behavior on colour, and the test watches a colour arrive over time
//     rather than in one frame, which is the only observation that can tell
//     an animation from an assignment.
//
// The keys here are numbers and the rows say nothing about workspaces: this
// file is about the list. That the BAR is keyed by niri's workspace id, and
// that the teal really moves on the real strip, is
// tools/barshots/scene/tst_settle.qml's — it needs the theme, the fonts and
// the Quickshell stand-ins, which is exactly what this directory does not have.
//
// Bound for the same reason every file in these shells is: the delegate below
// reads `root`, an id in THIS component, and a delegate resolves an outer id
// dynamically unless told not to. `nix build .#jv-bar` lints this directory at
// -W 0, where that is a failed build rather than a warning.
pragma ComponentBehavior: Bound

import QtQuick
import QtTest
import "../core"

Item {
  id: root

  width: 400
  height: 40

  // Two colours that are deliberately NOT §06 tokens. This directory cannot
  // reach the generated `Theme` (it is next to `Motion`, which imports
  // Quickshell), and it should not want to: the file is about a list keeping
  // its delegates, and a palette colour in it would read as a claim about how
  // the bar looks. What matters is only that the two are distinguishable and
  // that the values between them are neither.
  readonly property color quiet: "steelblue"
  readonly property color loud: "orange"

  KeyedRows {
    id: rows
  }

  Row {
    id: strip

    Repeater {
      id: labels

      model: rows

      Text {
        required property string label
        required property bool lit

        text: label
        color: lit ? root.loud : root.quiet

        // The shape `Ease` has in the shells, written out: this directory
        // cannot import the generated one (it reaches `Motion`, which is a
        // Quickshell singleton), and the duration is this file's own so the
        // settle can be sampled without a theme under it.
        Behavior on color {
          PropertyAnimation {
            duration: 200
            easing.type: Easing.OutCubic
          }
        }
      }
    }
  }

  TestCase {
    id: suite

    name: "KeyedRows"
    when: windowShown

    function init() {
      rows.clear();
    }

    // A row, as this file writes them: a key, a word, and whether it is lit.
    function row(key: int, label: string, lit: bool): var {
      return {
        "key": key,
        "label": label,
        "lit": lit === true
      };
    }

    function labelsOn(): string {
      const out = [];
      for (let i = 0; i < labels.count; i++)
        out.push((labels.itemAt(i) as Text).text);
      return out.join(" ");
    }

    function test_the_list_says_what_it_was_asked_to_say_data(): var {
      return [
        { tag: "from nothing", first: [], then: [1, 2, 3] },
        { tag: "unchanged", first: [1, 2, 3], then: [1, 2, 3] },
        { tag: "one arrives at the end", first: [1, 2], then: [1, 2, 3] },
        { tag: "one arrives at the front", first: [1, 2], then: [3, 1, 2] },
        { tag: "one arrives in the middle", first: [1, 3], then: [1, 2, 3] },
        { tag: "one leaves", first: [1, 2, 3], then: [1, 3] },
        { tag: "the last ones leave", first: [1, 2, 3], then: [1] },
        { tag: "reordered", first: [1, 2, 3], then: [3, 1, 2] },
        { tag: "replaced whole", first: [1, 2], then: [8, 9] },
        { tag: "emptied", first: [1, 2, 3], then: [] }
      ];
    }

    function test_the_list_says_what_it_was_asked_to_say(data) {
      rows.sync(data.first.map(k => suite.row(k, "w" + k, false)));
      compare(suite.labelsOn(), data.first.map(k => "w" + k).join(" "), "the desk it started on");

      rows.sync(data.then.map(k => suite.row(k, "w" + k, false)));
      compare(rows.count, data.then.length, "how many rows");
      compare(suite.labelsOn(), data.then.map(k => "w" + k).join(" "), "the desk it ended on");
      for (let i = 0; i < data.then.length; i++)
        compare(rows.get(i).key, data.then[i], "the key at " + i);
    }

    // The point of all of it: a row that is still there is the SAME OBJECT,
    // wherever it has moved to, and a row that is new is a new one.
    function test_a_row_that_stayed_keeps_its_delegate() {
      rows.sync([suite.row(1, "a", false), suite.row(2, "b", false)]);
      const a = labels.itemAt(0);
      const b = labels.itemAt(1);

      rows.sync([suite.row(9, "z", false), suite.row(1, "a", false), suite.row(2, "b", false)]);
      compare(labels.itemAt(1), a, "the row that was first and is now second");
      compare(labels.itemAt(2), b, "the row behind it");
      verify(labels.itemAt(0) !== a && labels.itemAt(0) !== b, "the row that is new is new");

      rows.sync([suite.row(2, "b", false), suite.row(1, "a", false)]);
      compare(labels.itemAt(0), b, "b, after the two swapped places");
      compare(labels.itemAt(1), a, "and a");
    }

    // TWO ROWS WITH ONE KEY, which is what the search window is for. A key is
    // an identity and nothing here can promise the caller's are unique — niri
    // can describe a desk carrying one id twice — so the scan for a surviving
    // row starts at `i` rather than at 0. Everything before `i` was claimed by
    // an earlier row THIS PASS, and the second row with a repeated key has to
    // take the next one instead of stealing back the first: a scan from 0
    // would move the claimed row down, leave the other in its place unset,
    // and draw the same word twice off two delegates that had swapped.
    function test_two_rows_with_one_key_each_keep_their_own_delegate() {
      rows.sync([suite.row(7, "a", false), suite.row(7, "b", false)]);
      compare(suite.labelsOn(), "a b");
      const first = labels.itemAt(0);
      const second = labels.itemAt(1);

      rows.sync([suite.row(7, "a", false), suite.row(7, "b", false)]);
      compare(suite.labelsOn(), "a b", "neither row was claimed by the other");
      compare(labels.itemAt(0), first, "the first row kept its delegate");
      compare(labels.itemAt(1), second, "and so did the one behind it");
    }

    // …and the only reason it matters: a delegate that survives is one whose
    // Behavior has somewhere to move from. A rebuilt one has always been the
    // colour it is drawn in.
    function test_a_surviving_delegate_eases_and_a_new_one_snaps() {
      rows.sync([suite.row(1, "a", false)]);
      wait(400);
      compare((labels.itemAt(0) as Text).color.toString(), root.quiet.toString(), "where it starts");

      rows.sync([suite.row(1, "a", true)]);
      let moving = 0;
      for (let i = 0; i < 6; i++) {
        wait(25);
        const now = (labels.itemAt(0) as Text).color.toString();
        if (now !== root.quiet.toString() && now !== root.loud.toString())
          moving += 1;
      }
      verify(moving > 0, "the colour went straight to "
             + (labels.itemAt(0) as Text).color + " — the delegate was rebuilt");
      wait(400);
      compare((labels.itemAt(0) as Text).color.toString(), root.loud.toString(), "where it arrives");

      // A row that has just come into existence is drawn lit, in the frame it
      // appears. There is no state between not being on the list and being on
      // it, so there is nothing for a Behavior to cross.
      rows.sync([suite.row(1, "a", true), suite.row(5, "e", true)]);
      compare((labels.itemAt(1) as Text).color.toString(), root.loud.toString(), "the new row");
    }
  }
}
