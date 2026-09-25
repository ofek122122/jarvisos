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
// singleton, so this file imports nothing but QtQuick and the generated
// Theme — the same split the HUD's plates keep, and what makes a future
// render harness for the bar possible without a compositor (PLAN D13).
//
// Nothing here moves. The bar has no `Ease`/`Motion` pair of its own yet,
// and a colour that eased in one element while three others snapped would
// be worse than a bar that is simply still — still is also 0 fps, which is
// what §06 asks of an idle surface. PLAN D14.
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
    }
  }
}
