// Workspaces — niri's workspaces for ONE output (PLAN D1).
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
// generated Theme, and the generated Ease. That is exactly the shape of a
// HUD plate — and Ease reaches `Motion`, which is a Quickshell singleton, so
// a render harness for the bar (PLAN D13) stages a stub over it the way
// `tools/hudshots` already does for the HUD. One stub, not a compositor.
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
import QtQuick
import "."

Row {
  id: root

  // The workspaces on this output, in layout order: exactly what
  // `Niri.workspacesOn(<output>)` returns. Empty means the bar has nothing
  // true to say about this monitor — because niri has not described the
  // desk, or because the stream is gone — and an empty Row draws nothing.
  required property var workspaces

  spacing: Theme.gapPx

  Repeater {
    model: root.workspaces

    Text {
      required property var modelData

      // The workspace's own name when it has one, its index when it does
      // not. niri sends both; the label is whichever one the user would
      // say out loud.
      text: modelData.label
      color: modelData.urgent ? Theme.warn : modelData.focused ? Theme.teal : modelData.active ? Theme.text2 : Theme.text3
      font.family: Theme.familyMono
      font.pixelSize: Theme.labelPx
      font.letterSpacing: Theme.labelPx * Theme.labelTrackingEm

      // §06's one gated Behavior. `enabled` is false whenever motion is
      // suppressed, so with the preference set the colour is assigned
      // straight through and this strip renders no frame at all.
      Ease on color {}
    }
  }
}
