// BusModel — what the HUD believes the bus has said, and nothing else.
//
// This is the half of the bus link (PLAN A5) that is pure QtQuick: parse a
// line, update state, answer questions about it. Bus.qml wraps it with the
// Quickshell half — the child bridge process, the respawn timer, the real
// monotonic clock — which cannot be loaded outside the quickshell binary.
// Splitting them is what makes this testable headlessly (PLAN A9); the
// rules below are the ones invariant 10 rides on, so they are worth tests:
//
//   · `linkUp` is false until the bridge says it is subscribed. Until then
//     the honest answer about every topic is "I don't know".
//   · when the link drops, `frames` is emptied. A HUD still drawing
//     "listening" from a bus that died three minutes ago is lying, and a
//     stale indicator is worse than no indicator.
//   · `latest()` returns null for anything unheard, so an element that
//     forgets to handle "no signal" fails loudly instead of inventing one.
//   · a line we cannot parse changes nothing at all.
import QtQuick

QtObject {
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
  // this is how an element added later knows the HUD has been awake. It
  // survives a link drop — the cache goes stale, the past does not.
  property int received: 0

  // The monotonic clock, injected: a callable returning seconds since a
  // fixed arbitrary origin, on the same CLOCK_MONOTONIC the bus stamps
  // `ts` with. Bus.qml supplies Quickshell's ElapsedTimer; the tests
  // supply one they can drive. Null means no clock, and with no clock
  // there is no age — `ageOf` says Infinity rather than guessing.
  property var monotonic: null

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
  // Envelope `ts` and the injected clock both read CLOCK_MONOTONIC, so
  // they differ by exactly one constant: when this process started. Every
  // frame gives an estimate of it (ts minus the reading taken as the frame
  // lands), biased low by however long the frame spent in flight — so we
  // keep the LARGEST estimate seen, which converges on the truth from
  // below as soon as one frame arrives promptly. Before the first frame
  // there is no estimate and therefore no age, which is the honest answer.
  function ageOf(envelope: var): real {
    if (!envelope || typeof envelope.ts !== "number" || !root.clockPinned)
      return Infinity;
    return root.elapsed() + root.clockOffset - envelope.ts;
  }

  property bool clockPinned: false
  property real clockOffset: 0

  // NaN when no clock was injected — every comparison against it is false,
  // so the offset never pins and `ageOf` stays Infinity.
  function elapsed(): real {
    return typeof root.monotonic === "function" ? root.monotonic() : NaN;
  }

  // One line from the bridge: `{"t":"frame",...}` or `{"t":"link",...}`.
  // Anything else is dropped on the floor, silently and completely.
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
    const now = root.elapsed();
    // isNaN, not a truthiness test: with no clock `elapsed()` is NaN, and
    // pinning an offset of NaN would make every age NaN — which compares
    // false against every staleness threshold, i.e. reads as "fresh".
    // Unknown age must stay Infinity.
    if (typeof env.ts === "number" && !isNaN(now)) {
      const estimate = env.ts - now;
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
}
