// Niri — the bar's read-only view of the compositor (PLAN D1).
//
// QML cannot open niri's Unix socket, so this singleton runs ONE child
// process — `niri msg --json event-stream`, pinned into the wrapper by
// pkgs/jv-bar — and feeds the JSON lines it writes to a NiriModel. Events
// come in; nothing ever goes out. There is no `niri msg action` here and no
// way to add one: this shell watches the compositor and never drives it,
// which is invariant 3's line (only jv-act changes the state of this
// machine) drawn where a bar would most easily cross it.
//
// The state machine those lines drive lives next door in
// `core/NiriModel.qml`, which imports nothing but QtQuick so it can be
// tested headlessly against the recorded stream in `harness/fixtures/niri`.
// What is left here is exactly the part that CANNOT be: the child process
// and the respawn timer. Keep it that way — logic that lands in this file
// is logic no test can reach.
//
// This is `shell/jv-hud/Bus.qml` with a different child, deliberately: the
// two shells watch different things and share no state, but "one read-only
// subprocess, a pure model beside it, a slow respawn" is the shape that
// survived the HUD's first year and there is no reason for the bar to
// invent a second one.
pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import "core"

Singleton {
  id: root

  // True only once niri has described the desk — not merely once the child
  // process is running. Every element must gate its content on this.
  readonly property alias linkUp: model.linkUp
  // Why the desk is unknown, for the log. Never rendered: it describes the
  // pipe, not the compositor.
  readonly property alias linkError: model.linkError
  readonly property alias workspaces: model.workspaces

  // The workspaces on one output, in layout order. The bar's surfaces are
  // per-monitor, so this is the only question any of them asks.
  function workspacesOn(output: string): var {
    return model.workspacesOn(output);
  }

  NiriModel {
    id: model
  }

  Process {
    id: stream

    // Pinned by the wrapper; the PATH fallback only matters when someone
    // runs the QML straight out of a checkout. `niri msg` finds the running
    // compositor through NIRI_SOCKET, which niri-session exports into the
    // user manager — so a bar started outside a niri session has no socket
    // to read and says so by showing no workspaces at all.
    command: [Quickshell.env("JV_BAR_NIRI") || "niri", "msg", "--json", "event-stream"]
    running: true

    stdout: SplitParser {
      splitMarker: "\n"
      onRead: data => model.ingest(data)
    }

    // The stream ends when niri exits, when the session is replaced, or
    // when there was no compositor to talk to in the first place. All three
    // mean the same thing to the bar — the desk is unknown — and all three
    // are worth retrying slowly, because the second one is what a `niri
    // --session` restart looks like from here.
    //
    // This watches `running` rather than the `exited` signal, for the same
    // reason Bus.qml does: `exited` carries a QProcess::ExitStatus, a type
    // QML cannot resolve, and the linter is a build gate here.
    onRunningChanged: {
      if (!stream.running) {
        model.applyLink(false, "niri event stream stopped");
        respawn.start();
      }
    }
  }

  Timer {
    id: respawn

    interval: 2000
    repeat: false
    onTriggered: stream.running = true
  }
}
