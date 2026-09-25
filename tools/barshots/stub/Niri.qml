// Niri — the shot harness's stand-in for the bar's real singleton (PLAN D13).
//
// STAGED OVER shell/jv-bar/Niri.qml, never committed next to it: the real one
// runs `niri msg --json event-stream` as a child process through Quickshell's
// `Process`/`SplitParser`, and quickshell links its QML plugin into its own
// binary, so no other QML engine can import it. That is the same wall that put
// every tested element of this shell in `core/`, and the reason `Workspaces`
// takes its row as a property instead of reading this singleton.
//
// What is left once the child process and the respawn timer are gone is
// exactly what the strip uses — a NiriModel and a way to put lines into it —
// and this file is that, with the lines handed in by the driver instead of
// read off a pipe.
//
// It is a STAND-IN FOR THE PIPE, not for the model's judgement: every line the
// strip's workspaces come from goes through the real
// `shell/jv-bar/core/NiriModel.qml`, so the per-output filter, the `idx` sort,
// the activation-across-outputs rule and the refusal to invent a workspace are
// all the running bar's. Nothing here decides what a label says. The lines the
// driver sends are `harness/fixtures/niri/ares-desk.jsonl` where the desk is
// the real one, which is the whole reason this sheet is worth taking.
//
// The forwarded surface is Niri.qml's, member for member —
// tools/tests/test_barshots.py fails if the two ever drift, because a missing
// member here would not error: a strip reading `Niri.somethingElse` would
// quietly see `undefined` and photograph a bar with no workspaces on it, which
// is a picture this shell is designed to be able to draw.
pragma Singleton

import QtQuick
import "core"

Item {
  id: root

  // --- Niri.qml's surface ----------------------------------------------

  readonly property bool linkUp: root.model ? root.model.linkUp : false
  readonly property string linkError: root.model ? root.model.linkError : "starting"
  readonly property var workspaces: root.model ? root.model.workspaces : []

  function workspacesOn(output: string): var {
    return root.model ? root.model.workspacesOn(output) : [];
  }

  // --- the harness half -------------------------------------------------

  // A whole new model per shot rather than replaying an empty snapshot: every
  // shot must start from a bar that has never been told anything, and
  // "starting" is a state the strip can be photographed in.
  function reset(): void {
    if (root.model)
      root.model.destroy();
    root.model = root.modelComponent.createObject(root);
  }

  // One line of `niri msg --json event-stream`, exactly as the SplitParser
  // hands it over: a string, one JSON object, no trailing newline.
  function ingest(line: string): void {
    root.model.ingest(line);
  }

  // The stream ending — niri exiting, the session being replaced, or there
  // never having been a compositor to talk to. The real singleton calls this
  // from `onRunningChanged`, and it is the one transition that empties the
  // desk, so it is the one a shot of an unknown desk has to go through rather
  // than around.
  function drop(reason: string): void {
    root.model.applyLink(false, reason);
  }

  property NiriModel model: null

  readonly property Component modelComponent: Component {
    NiriModel {}
  }

  Component.onCompleted: root.reset()
}
