// DictateState — is push-to-talk dictation recording, right now? (F5c)
//
// jv-dictate (F5b) is the second process that opens the microphone: unlike
// jv-ears' always-on VAD, it captures only while the push-to-talk key is
// held. That is still audio leaving the room, so invariant 10 applies here
// exactly as it does to MicState — the indicator must never claim a
// recording that is not happening, and must never go dark while one is.
//
// The two elements deliberately do not share code. jv-ears reports a rich
// set of gauges (mic_open, capture_age_s, loss counters) because a single
// continuously-open device can fail in several ways; jv-dictate reports one
// number, `metrics.recording` (services/jv-dictate/jv_dictate/service.py),
// because there is nothing to distinguish — the key is either held or it is
// not, and PushToTalk's own hard cap (MAX_RECORDING_S) is what stops a stuck
// key from becoming an open mic, not something this element has to detect.
//
// Everything here is either read off a frame or refused, the same rule
// MicState follows: there is no path that turns "I cannot see the bus" into
// "not recording".
import QtQuick

QtObject {
  id: root

  // Anything offering `linkUp`, `latestFrom(topic, src)` and `ageOf()`:
  // the `Bus` singleton in production, a BusModel the tests drive.
  property var bus: null

  // The service that owns push-to-talk dictation.
  property string service: "jv-dictate"

  // "unknown"   — nothing trustworthy to say (no link, no heartbeat, a
  //               heartbeat too old to describe now, or a jv-dictate that
  //               does not report the gauge at all).
  // "idle"      — jv-dictate is here and the key is not held.
  // "recording" — the key is held and audio is being captured.
  readonly property string state: {
    const m = root.metrics;
    if (m === null)
      return "unknown";
    return m.recording === 1 ? "recording" : "idle";
  }

  readonly property bool known: root.state !== "unknown"
  readonly property bool recording: root.state === "recording"

  // --- the heartbeat we are willing to believe -------------------------

  // The last sys.health from `service`, or null. Rejected outright: a body
  // from a schema version we were not written against (invariant 2), a
  // frame with no orderable `ts`, a heartbeat hedging its confidence
  // (state topics publish conf 1.0 — anything less disagrees with itself),
  // a body naming a DIFFERENT service than the envelope said published it,
  // and one with no usable `period_s`, which is how long we may believe it.
  readonly property var health: {
    if (!root.bus || !root.bus.linkUp || typeof root.bus.latestFrom !== "function")
      return null;
    const env = root.bus.latestFrom("sys.health", root.service);
    if (!env || env.v !== 1 || typeof env.ts !== "number" || env.conf !== 1 || !env.body)
      return null;
    if (env.body.service !== root.service || !(env.body.period_s > 0))
      return null;
    return env;
  }

  // The gauge, or null if this heartbeat carries none. Null is NOT "idle":
  // a jv-dictate too old to report recording is one we cannot read a
  // reading from, and guessing "idle" there is the lie that matters.
  readonly property var metrics: {
    const env = root.health;
    if (env === null || root.healthStale)
      return null;
    const m = env.body.metrics;
    return m && typeof m.recording === "number" ? m : null;
  }

  // --- how long a heartbeat describes the present ----------------------

  // schemas/sys.health.json: "Missing 2 consecutive periods = presumed
  // dead". So a heartbeat speaks for two of its own periods and no longer;
  // after that jv-dictate may have died mid-recording and we would have no
  // way to know. `ageOf` is Infinity when the age is not knowable (no
  // clock, no ts), which fails this — an age we cannot compute is not an
  // age we may assume is zero.
  readonly property bool healthStale: root.health === null || root.expired || root.ageOf(root.health) > root.health.body.period_s * 2

  // Set by the timer below, cleared by every fresh heartbeat. A plain
  // property, not a computed one: no binding re-evaluates because a clock
  // moved, and this element's whole job is to stop claiming things.
  property bool expired: false

  // Identity of the heartbeat currently believed: `seq` is per-publisher
  // and strictly increasing, so this changes exactly once per frame.
  readonly property string healthKey: root.health === null ? "" : root.health.seq + "@" + root.health.ts

  onHealthKeyChanged: root.armExpiry()

  // One shot, armed only while there is a heartbeat to expire — a HUD
  // with no jv-dictate on the bus runs no timer at all (§06: 0 fps when
  // nothing is happening).
  readonly property Timer expiry: Timer {
    repeat: false
    onTriggered: root.expired = true
  }

  function armExpiry(): void {
    root.expired = false;
    if (root.health === null) {
      root.expiry.running = false;
      return;
    }
    // Whatever is LEFT of the two periods: a frame that spent time in
    // flight is already partway through its own life.
    const left = root.health.body.period_s * 2 - root.ageOf(root.health);
    if (!(left > 0)) {
      root.expiry.running = false;
      root.expired = true;
      return;
    }
    root.expiry.interval = Math.max(1, Math.ceil(left * 1000));
    root.expiry.restart();
  }

  function ageOf(envelope: var): real {
    return root.bus && typeof root.bus.ageOf === "function" ? root.bus.ageOf(envelope) : Infinity;
  }
}
