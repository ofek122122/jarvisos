// Workspaces — niri's workspaces for ONE output (PLAN D1, D32).
//
// A row of labels and nothing else: no boxes, no separators, no pill behind
// the active one. §06's earned emptiness applies hardest here, because a
// workspace strip is the element every other desktop uses to decorate.
// What each one is doing is said in colour, and the colours are chosen from
// what the tokens MEAN rather than from what would stand out:
//
//   · teal for the workspace your keyboard is in. theme.toml: "Teal is the
//     second, cooler voice: your own state, not Jarvis's." Which workspace
//     you are on is the definition of your own state, and it is the one
//     thing this strip exists to say.
//   · NOT ember. Ember means Jarvis is doing something and nothing else;
//     spending it on the ordinary act of switching workspaces would make
//     the HUD's accent a theme colour, which is the one way §06 says the
//     look dies.
//   · `warn` for urgent — a window on that workspace asked for you — which
//     is the one reading here that is about something that happened rather
//     than about where you are.
//   · `text_2` for a workspace that is active on another monitor, `text_3`
//     for the rest. Two quiets, because "on screen somewhere" and "not on
//     screen" are genuinely different facts about a workspace.
//
// The data arrives as a property rather than being read off the `Niri`
// singleton, so this file names nothing of the compositor: QtQuick, the
// generated Theme, the generated Ease, and `core/RowFit`. That is exactly the
// shape of a HUD plate — and Ease reaches `Motion`, which is a Quickshell
// singleton, so the render harness for the bar (PLAN D13) stages a stub over
// it the way `tools/hudshots` already does for the HUD. One stub, not a
// compositor. That harness is `ops/ralph/barshots.sh`, and `docs/bar/` is
// what it wrote.
//
// WHAT EACH LABEL IS DOING IS NAMED ONCE. `reading()` says it in a word and
// `tint()` turns that word into a colour, so the strip's own account of what
// it drew (`drew`, which the shot harness photographs beside the picture) and
// the pixels it actually painted cannot disagree. A caption that could say
// `focused` over a label painted `text_3` would be a caption worth nothing,
// which is the same argument `Toast.urgencyName` makes one shell over.
//
// THE ROW HAS NO WIDTH OF ITS OWN, AND ITS CONTENT IS SOMEBODY ELSE'S STRING
// (PLAN D32). It is a `Row` — it is as wide as its children — and niri lets a
// workspace be NAMED, so six of them called `documentation` is a desk a user
// can really have. D13 photographed that and printed what was left before the
// row reached the clock: 274 px on a 1920 px monitor, about three more names.
// What happens to the fourth is decided in `core/RowFit.qml`, in numbers, and
// the rule is: as many WHOLE labels as fit, then a `+N` where the row was
// cut, and the workspace this output is showing is never among the dropped.
// The reasoning — and what is wrong with clipping, with eliding everything,
// and with dropping labels silently — is written there and tested in
// `tests/tst_rowfit.qml`.
//
// THE PIXELS ARE MEASURED, NOT COMPUTED. `bench` below is one invisible copy
// of each label, in this row's own type, whose only job is to report what the
// word measures; `RowFit` is handed those numbers. A row that multiplied
// character counts by an advance width would be right about JetBrains Mono
// and wrong about the first workspace someone names with an emoji in it — and
// it would be wrong in the direction that paints into another process's
// corner. Nothing here draws a label it has not measured: until every width
// is in, `roomPx` is withheld and the row draws everything, which is what it
// did before this rule existed and is the right thing to do in the first
// frame of a session.
//
// The ONE thing that moves here is the colour, and it moves the way §06 says
// a value moves: eased toward the target rather than snapped to it, through
// the shared `Ease` — so the whole of "may this bar animate at all" is the
// same decision the HUD and the notifier ask (PLAN D18), and
// JV_REDUCED_MOTION=1 stills this strip with the rest of the desktop. It
// earns the frames because the colour IS the signal: your keyboard moving to
// another workspace is a fact about you, and a 200 ms settle is what makes it
// read as a move rather than as a repaint. Nothing else animates — a
// workspace appearing or vanishing still snaps, which is honest (there is no
// intermediate state between "niri has this workspace" and "it does not")
// and is 0 fps while the desk is unchanged, which is what §06 asks of an
// idle surface.
// `root` below is an id in THIS component, read from inside the delegate the
// Repeater builds — and by default a delegate resolves an outer id
// dynamically, at whatever the name happens to mean when the binding runs.
// Bound makes that lookup lexical and checkable, which is what lets qmllint
// see the reference at all: without it the colour binding is an `unqualified`
// warning, and -W 0 in pkgs/jv-bar means a warning is a failed build. It is
// the same line, for the same reason, that shell.qml opens with.
pragma ComponentBehavior: Bound

import QtQuick
import "."
import "core"

Row {
  id: root

  // The workspaces on this output, in layout order: exactly what
  // `Niri.workspacesOn(<output>)` returns. Empty means the bar has nothing
  // true to say about this monitor — because niri has not described the
  // desk, or because the stream is gone — and an empty Row draws nothing.
  required property var workspaces

  // How much room this row has before it reaches something it must not
  // touch. The surface's own arithmetic, because only it knows how wide the
  // monitor is, where the clock is centred and how much of the right end the
  // HUD draws over. NEGATIVE means nobody has said — the default, and the
  // only honest answer before a surface has a width: a row that hid labels
  // because it had not been told its size would hide them in the first frame
  // of every session.
  property int roomPx: -1

  // This row's own account of what it drew: one `<label>:<reading>` per thing
  // on screen, in layout order, INCLUDING the `+N` when the row was cut. Read
  // by the shot harness (tools/barshots/scene/Strip.qml) so that a picture of
  // two grey labels is a picture OF something — the whole vocabulary here is
  // a few characters in one of four colours, and two shots of different desks
  // look almost alike.
  readonly property var drew: root.shown.map(e => e.label + ":" + e.reading)

  // --- what is on screen, and what was left off -------------------------

  // The label that is never dropped: the workspace this output is SHOWING.
  // That is the focused one when your keyboard is here and the active one
  // when it is not — one property, because `NiriModel` will not let a
  // workspace be focused without being active. -1 when niri has activated
  // nothing on this output, which is not this row's business to fix.
  readonly property int keepIndex: root.workspaces.findIndex(w => w.active)

  // Each label's width as the label itself reports it, in layout order, with
  // -1 for one the bench has not weighed yet.
  readonly property var widths: root.sized(root.labelPx, root.workspaces.length)
  readonly property bool weighed: root.widths.indexOf(-1) < 0

  // Which of them fit. `roomPx` is withheld until every label has been
  // measured, and an unmeasured row draws all of them.
  readonly property var plan: fitter.plan(root.widths, Theme.gapPx, root.weighed ? root.roomPx : -1, root.keepIndex, widest.implicitWidth)

  // …and that plan as the things to draw, in layout order: the run, then the
  // marker standing where the row was cut, then the label held back.
  readonly property var shown: root.compose(root.plan)

  // The raw measurements, written by the bench as each label lays itself out.
  // Not read directly — `widths` above is the one that is the right length.
  property var labelPx: []

  // --- the decisions, one function each ---------------------------------

  // What one workspace is doing, in a word. The one place that decision is
  // made: `tint` below turns the word into a colour and `drew` above puts the
  // same word in the caption.
  function reading(w: var): string {
    return w.urgent ? "urgent" : w.focused ? "focused" : w.active ? "active" : "idle";
  }

  // …and the word as a §06 token. See the paragraph above the imports for why
  // each of the four is the one it is.
  function tint(reading: string): color {
    if (reading === "urgent")
      return Theme.warn;
    if (reading === "focused")
      return Theme.teal;
    if (reading === "active")
      return Theme.text2;
    return Theme.text3;
  }

  // One thing to draw: a label, the word for what it is doing, and the width
  // it must elide to (0 — the ordinary case — meaning it is drawn whole).
  function entry(w: var, elidePx: int): var {
    return {
      "label": w.label,
      "reading": root.reading(w),
      "elidePx": elidePx
    };
  }

  // What the workspaces behind the marker amount to, in the same vocabulary
  // the labels use. `urgent` when one of the ones you cannot see is asking
  // for you — a row that hid a window's call for attention and said nothing
  // would be doing the thing the marker exists to prevent — and the quietest
  // grey otherwise, because a count of ordinary workspaces is the least
  // urgent thing on this strip.
  function hidden(plan: var): string {
    for (let i = 0; i < root.workspaces.length; i++) {
      if (i < plan.run || i === plan.tail)
        continue;
      if (root.workspaces[i].urgent)
        return "urgent";
    }
    return "idle";
  }

  function compose(plan: var): var {
    const out = [];
    for (let i = 0; i < plan.run; i++)
      out.push(root.entry(root.workspaces[i], 0));
    if (plan.marker)
      out.push({
        "label": "+" + plan.dropped,
        "reading": root.hidden(plan),
        "elidePx": 0
      });
    if (plan.tail >= 0)
      out.push(root.entry(root.workspaces[plan.tail], plan.elidePx));
    return out;
  }

  // The measurements, as exactly as many as there are workspaces: a desk that
  // shrank leaves widths behind it, and a desk that grew arrives before the
  // bench has weighed the new one. -1 is "not weighed", and one of those is
  // what makes `weighed` false.
  function sized(px: var, count: int): var {
    const out = [];
    for (let i = 0; i < count; i++)
      out.push(i < px.length ? px[i] : -1);
    return out;
  }

  function measured(index: int, px: real): void {
    const next = root.labelPx.slice(0);
    while (next.length <= index)
      next.push(-1);
    next[index] = px;
    root.labelPx = next;
  }

  spacing: Theme.gapPx

  // The row's type, in one place, because it is worn by two things that are
  // not the same kind of object: the labels on screen and the invisible
  // copies that measure them. A bench in a different font would be a bench
  // measuring a row that does not exist.
  component Label: Text {
    font.family: Theme.familyMono
    font.pixelSize: Theme.labelPx
    font.letterSpacing: Theme.labelPx * Theme.labelTrackingEm
  }

  RowFit {
    id: fitter
  }

  // The widest `+N` this row could draw, measured before the count is known —
  // which is the circle `RowFit` has to be handed a way out of, since how
  // many labels are dropped depends on how much room the number reporting it
  // takes. The widest costs at most one glyph of over-reservation and can
  // never under-reserve.
  Label {
    id: widest

    visible: false
    text: "+" + root.workspaces.length
  }

  // The bench: every label, in the row's own type, laid out and never drawn.
  // Invisible children are not positioned, so this occupies no space in the
  // Row — it exists so that `RowFit` is given what the words MEASURE rather
  // than what an arithmetic over character counts thinks they measure.
  Item {
    id: bench

    visible: false

    Repeater {
      model: root.workspaces

      Label {
        required property var modelData
        required property int index

        text: modelData.label

        onImplicitWidthChanged: root.measured(index, implicitWidth)
        Component.onCompleted: root.measured(index, implicitWidth)
      }
    }
  }

  Repeater {
    model: root.shown

    Label {
      required property var modelData

      text: modelData.label
      color: root.tint(modelData.reading)
      // Whole words, except for the one case `RowFit` elides: a single label
      // wider than the entire row. Everywhere else this is the label's own
      // width and `elide` is off, so nothing here can cut a name that fits.
      width: modelData.elidePx > 0 ? modelData.elidePx : implicitWidth
      elide: modelData.elidePx > 0 ? Text.ElideRight : Text.ElideNone

      // §06's one gated Behavior. `enabled` is false whenever motion is
      // suppressed, so with the preference set the colour is assigned
      // straight through and this strip renders no frame at all.
      Ease on color {}
    }
  }
}
