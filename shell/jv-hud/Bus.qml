// Bus — the HUD's read-only view of the JarvisOS bus (PLAN A5).
//
// QML cannot open a Unix socket or unpack MessagePack, and the HUD is
// forbidden from importing another service (invariant 1). So this
// singleton runs ONE child process — `jv-hud-bridge`, pinned into the
// wrapper by pkgs/jv-hud — and reads the JSON lines it writes. Frames
// come in; nothing ever goes out. There is no publish here and no way to
// add one: the bridge is handed a read-only bus object on its side too.
//
// Truthfulness is the whole design (invariant 10):
//   · `linkUp` is false until the bridge says it is subscribed. Until
//     then the honest answer about every topic is "I don't know".
//   · when the link drops, `frames` is emptied. A HUD still drawing
//     "listening" from a bus that died three minutes ago is lying, and a
//     stale indicator is worse than no indicator.
//   · `latest()` returns null for anything unheard, so an element that
//     forgets to handle "no signal" fails loudly instead of inventing one.
//
// This singleton is constructed lazily, on first use. Nothing references
// it while the HUD has nothing to show, so an idle machine runs no bridge
// process and holds no socket — earned emptiness costs nothing (§06).
pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
  id: root

  // True only while the bridge holds a live, subscribed bus connection.
  // Every element must gate its content on this.
  property bool linkUp: false
  // Why the link is down, for the log and for a future diagnostics panel.
  // Never rendered as a sensor state — it describes the pipe, not the room.
  property string linkError: "starting"
  // topic -> the last envelope seen on it. Replaced wholesale (never
  // mutated in place) so bindings actually re-evaluate.
  property var frames: ({})
  // Frames that arrived while nothing was listening still count as heard:
  // this is how an element added later knows the HUD has been awake.
  property int received: 0

  // Emitted for every well-formed frame, after `frames` is updated.
  signal frameReceived(string topic, var envelope)

  // The last envelope on `topic`, or null if the bus has never said
  // anything about it (or the link is down and the cache was cleared).
  function latest(topic: string): var {
    const env = root.frames[topic];
    return env === undefined ? null : env;
  }

  // Seconds since a frame was captured, or Infinity when that is not
  // knowable yet. An element uses this to stop showing input that went
  // stale instead of pretending it is current (invariant 4).
  //
  // Envelope `ts` and Qt's ElapsedTimer both read CLOCK_MONOTONIC, so they
  // differ by exactly one constant: when this process started. Every frame
  // gives an estimate of it (ts minus the reading taken as the frame
  // lands), biased low by however long the frame spent in flight — so we
  // keep the LARGEST estimate seen, which converges on the truth from
  // below as soon as one frame arrives promptly. Before the first frame
  // there is no estimate and therefore no age, which is the honest answer.
  function ageOf(envelope: var): real {
    if (!envelope || typeof envelope.ts !== "number" || !root.clockPinned)
      return Infinity;
    return sinceStart.elapsed() + root.clockOffset - envelope.ts;
  }

  property bool clockPinned: false
  property real clockOffset: 0

  ElapsedTimer {
    id: sinceStart
  }

  // ---------------------------------------------------------------- wire

  function ingest(line: string): void {
    if (line.length === 0)
      return;
    let msg = null;
    try {
      msg = JSON.parse(line);
    } catch (e) {
      // A line the HUD cannot parse is a line the HUD does not act on.
      console.warn("jv-hud: unparseable bridge line dropped");
      return;
    }
    if (!msg || typeof msg !== "object")
      return;

    if (msg.t === "link") {
      root.applyLink(msg.up === true, typeof msg.err === "string" ? msg.err : "");
      return;
    }
    if (msg.t !== "frame" || !msg.frame || typeof msg.frame.topic !== "string")
      return;

    const env = msg.frame;
    if (typeof env.ts === "number") {
      const estimate = env.ts - sinceStart.elapsed();
      if (!root.clockPinned || estimate > root.clockOffset) {
        root.clockOffset = estimate;
        root.clockPinned = true;
      }
    }
    let next = {};
    for (const key in root.frames)
      next[key] = root.frames[key];
    next[env.topic] = env;
    root.frames = next;
    root.received += 1;
    root.frameReceived(env.topic, env);
  }

  function applyLink(up: bool, err: string): void {
    if (!up && Object.keys(root.frames).length > 0)
      root.frames = ({}); // nothing observed means nothing shown
    root.linkUp = up;
    root.linkError = up ? "" : err;
  }

  Process {
    id: bridge

    // Pinned by the wrapper; the PATH fallback only matters when someone
    // runs the QML straight out of a checkout.
    command: [Quickshell.env("JV_HUD_BRIDGE") || "jv-hud-bridge"]
    running: true

    stdout: SplitParser {
      splitMarker: "\n"
      onRead: data => root.ingest(data)
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
        root.applyLink(false, "bridge stopped");
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
