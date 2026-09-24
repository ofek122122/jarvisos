// Bus — the HUD's read-only view of the JarvisOS bus (PLAN A5).
//
// QML cannot open a Unix socket or unpack MessagePack, and the HUD is
// forbidden from importing another service (invariant 1). So this
// singleton runs ONE child process — `jv-hud-bridge`, pinned into the
// wrapper by pkgs/jv-hud — and feeds the JSON lines it writes to a
// BusModel. Frames come in; nothing ever goes out. There is no publish
// here and no way to add one: the bridge is handed a read-only bus object
// on its side too.
//
// The state machine those lines drive lives next door in core/BusModel.qml,
// which imports nothing but QtQuick so it can be tested headlessly (A9).
// What is left here is exactly the part that CANNOT be: the child process,
// the respawn timer, and the monotonic clock. Keep it that way — logic that
// lands in this file is logic no test can reach.
//
// Everything an element uses — `linkUp`, `frames`, `latest()`,
// `latestFrom()`, `ageOf()`, `frameReceived` — is forwarded below, so
// consumers still see one `Bus`. A tools test fails the build if this file
// ever forgets one: an unforwarded function is invisible to every element,
// and invisible quietly.
pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import "core"

Singleton {
  id: root

  // True only while the bridge holds a live, subscribed bus connection.
  // Every element must gate its content on this.
  readonly property alias linkUp: model.linkUp
  // Why the link is down, for the log and for a future diagnostics panel.
  // Never rendered as a sensor state — it describes the pipe, not the room.
  readonly property alias linkError: model.linkError
  // topic -> the last envelope seen on it, emptied whenever the link drops.
  readonly property alias frames: model.frames
  readonly property alias received: model.received

  // Emitted for every well-formed frame, after `frames` is updated.
  signal frameReceived(string topic, var envelope)

  // The last envelope on `topic`, or null if the bus has never said
  // anything about it (or the link is down and the cache was cleared).
  function latest(topic: string): var {
    return model.latest(topic);
  }

  // The last envelope `src` published on `topic`, or null. Most topics
  // have exactly one publisher and `latest()` is enough; `sys.health` has
  // one per service, and "the newest heartbeat" is somebody else's answer.
  function latestFrom(topic: string, src: string): var {
    return model.latestFrom(topic, src);
  }

  // Every `src` heard on `topic`, sorted, or an empty list. The HUD's
  // only roster: nothing on the bus announces which services are meant to
  // be running, so "who has spoken" is the whole of what can be known.
  function publishersOf(topic: string): var {
    return model.publishersOf(topic);
  }

  // Seconds since a frame was captured, or Infinity when that is not
  // knowable yet — before the first frame, or for a frame with no `ts`.
  function ageOf(envelope: var): real {
    return model.ageOf(envelope);
  }

  BusModel {
    id: model

    // Quickshell's ElapsedTimer reads CLOCK_MONOTONIC in seconds, which is
    // the clock the bus stamps `ts` with. This is the only reason the model
    // needs an injected one: the tests have no ElapsedTimer to give it.
    monotonic: () => sinceStart.elapsed()

    onFrameReceived: (topic, envelope) => root.frameReceived(topic, envelope)
  }

  ElapsedTimer {
    id: sinceStart
  }

  Process {
    id: bridge

    // Pinned by the wrapper; the PATH fallback only matters when someone
    // runs the QML straight out of a checkout.
    command: [Quickshell.env("JV_HUD_BRIDGE") || "jv-hud-bridge"]
    running: true

    stdout: SplitParser {
      splitMarker: "\n"
      onRead: data => model.ingest(data)
    }

    // The bridge reconnects to the bus by itself; it only stops if it
    // crashed or was never there. Either way the link is down and the HUD
    // says so, then we try again on a slow, fixed cadence.
    //
    // This watches `running` rather than the `exited` signal: `exited`
    // carries a QProcess::ExitStatus, a type QML cannot resolve, and the
    // linter is a build gate here. The bool is all we act on anyway.
    onRunningChanged: {
      if (!bridge.running) {
        model.applyLink(false, "bridge stopped");
        respawn.start();
      }
    }
  }

  Timer {
    id: respawn
    interval: 2000
    repeat: false
    onTriggered: bridge.running = true
  }
}
