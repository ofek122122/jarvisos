// Bus — the shot harness's stand-in for the HUD's real bus singleton.
//
// STAGED OVER shell/jv-hud/Bus.qml, never committed next to it: the real
// one runs the `jv-hud-bridge` child process through Quickshell.Io, and
// quickshell links its QML plugin into its own binary, so no other QML
// engine can import it (the same wall that put every tested element in
// core/). What is left once that is gone is exactly what the plates use —
// a BusModel and a monotonic clock — and this file is that, with the clock
// handed to it instead of read off CLOCK_MONOTONIC.
//
// It is a STAND-IN FOR THE PIPE, not for the machine: every frame the
// plates see still goes in as a JSON line in the bridge's own wire format
// and through core/BusModel.qml, the same state machine the running HUD
// uses. Nothing here decides what a plate says.
//
// The forwarded surface is Bus.qml's, member for member —
// tools/tests/test_hudshots.py fails if the two ever drift, because a
// missing member here would not error: a plate reading `Bus.somethingElse`
// would quietly see `undefined` and draw a picture of nothing.
pragma Singleton

import QtQuick
import "core"

Item {
  id: root

  // The clock the model ages frames against, in seconds. The driver sets
  // it to each frame's own `ts` on the way in, so a delivered frame lands
  // zero seconds old, exactly as it would on a machine keeping up.
  property real now: 0

  // --- Bus.qml's surface ----------------------------------------------

  readonly property bool linkUp: root.model ? root.model.linkUp : false
  readonly property string linkError: root.model ? root.model.linkError : ""
  readonly property var frames: root.model ? root.model.frames : ({})
  readonly property int received: root.model ? root.model.received : 0

  signal frameReceived(string topic, var envelope)

  function latest(topic: string): var {
    return root.model ? root.model.latest(topic) : null;
  }

  function latestFrom(topic: string, src: string): var {
    return root.model ? root.model.latestFrom(topic, src) : null;
  }

  function publishersOf(topic: string): var {
    return root.model ? root.model.publishersOf(topic) : [];
  }

  function ageOf(envelope: var): real {
    return root.model ? root.model.ageOf(envelope) : Infinity;
  }

  // --- the harness half -----------------------------------------------

  // A whole new model per shot rather than a link drop: every shot must
  // start from a HUD that has never seen anything, and "clear the cache"
  // is the model's answer to a dropped link, not a factory reset.
  function reset(): void {
    if (root.model)
      root.model.destroy();
    root.now = 0;
    root.model = root.modelComponent.createObject(root, {
      monotonic: () => root.now
    });
    root.model.frameReceived.connect(root.frameReceived);
  }

  // One line in the bridge's wire format, verbatim.
  function ingest(line: string): void {
    root.model.ingest(line);
  }

  // One envelope, delivered at its own moment.
  function deliver(envelope: var): void {
    root.now = Math.max(root.now, typeof envelope.ts === "number" ? envelope.ts : root.now);
    root.ingest(JSON.stringify({
      "t": "frame",
      "frame": envelope
    }));
  }

  property BusModel model: null

  readonly property Component modelComponent: Component {
    BusModel {}
  }

  Component.onCompleted: root.reset()
}
