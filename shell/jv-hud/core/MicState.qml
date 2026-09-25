// MicState — is the microphone open, right now? (A4)
//
// The privacy indicator. Invariant 10 says the mic light is not optional
// and not fakeable, which cuts both ways: it must never claim an open
// microphone that is closed, and it must never go dark while one is open.
// Those two errors are not symmetric — a dark indicator over a live mic is
// the one that costs trust — so where this cannot tell, it says so.
//
// This is a DIFFERENT question from SpeechState's "listening", and it must
// never be derived from it: jv-ears runs its VAD continuously whether or
// not a wake window is open. "listening" answers *is Jarvis attending to
// me*; this answers *is audio being captured at all*.
//
// Where the answer comes from. jv-ears is the only process that can see
// the device, so it is the only one that can answer, and it reports on its
// sys.health heartbeat (free-form `metrics`, no schema change):
//
//   mic_open       1 for a real microphone, 0 for a --wav run.
//   capture_age_s  seconds since the device last delivered audio.
//                  ABSENT means it never has.
//   captured_s     total audio delivered, for the log.
//   capture_stall_s  how long ears itself lets a device go quiet before
//                  calling its own heartbeat degraded. A budget, not a
//                  measurement: MicPlate feeds it in as `stallS` (A14).
//   capture_loss_age_s  seconds since a chunk of the room was discarded —
//                  by ears' own queue, or by the device before ears ran.
//                  ABSENT means none ever was.
//   capture_loss_window_s  how long a discard keeps meaning "this
//                  microphone is losing audio". The other budget, fed in
//                  as `lossWindowS` the same way (A84).
//
// Which is why the process being alive is not the test. The 2026-09-15
// field bug was exactly that: PortAudio opened nothing, jv-ears stayed up
// and cheerful, and the stream delivered silence forever. A heartbeat is
// evidence about jv-ears; only the counters are evidence about the mic.
//
// Everything here is either read off a frame or refused. There is no path
// that turns "I cannot see the bus" into "the microphone is off".
import QtQuick

QtObject {
  id: root

  // Anything offering `linkUp`, `latestFrom(topic, src)` and `ageOf()`:
  // the `Bus` singleton in production, a BusModel the tests drive.
  property var bus: null

  // The service that owns the microphone. `sys.health` carries every
  // service's heartbeat, so asking by name is the whole point of
  // `latestFrom` — "the newest heartbeat" is somebody else's answer.
  property string service: "jv-ears"

  // How long the device may deliver nothing before we stop calling it
  // live. MicPlate binds this to what jv-ears reports on its own
  // heartbeat (core/EarsBudgets.qml, A14); the value here is the fallback
  // for a jv-ears that has not said, and a tools test fails the build if
  // it drifts from `CaptureMeter.STALL_S`. Stays a plain property, not a
  // binding: this element decides one thing and takes its inputs.
  property real stallS: 1.0

  // How long a discarded chunk keeps meaning "losing audio". Same shape,
  // same source, same pinned fallback (`CaptureMeter.LOSS_S`) — and a
  // deliberately separate number from the one above, because they bound
  // different things: that one is how long silence is still a slow
  // stream, this one is how long a hole in the recording is still news.
  property real lossWindowS: 1.0

  // "unknown" — nothing trustworthy to say (no link, no heartbeat, a
  //             heartbeat too old to describe now, or a jv-ears that does
  //             not report the gauges at all).
  // "off"     — jv-ears is here and has no microphone open (a --wav run).
  // "live"    — the device is open, delivering, and losing nothing.
  // "losing"  — the device is open and delivering, and chunks of the room
  //             are going missing anyway: ears' hand-off queue overflowed,
  //             or the device discarded input before ears ran. Every gauge
  //             `live` is built on stays fresh through this, which is why
  //             it needed a word of its own — without one the indicator
  //             reads "fine" over a recording with holes in it, and that
  //             is the not-fakeable half of invariant 10 over-claiming.
  // "stalled" — the device is open and has gone quiet: still recording as
  //             far as the OS is concerned, but Jarvis is deaf.
  //
  // The last two are both degraded and only one can be on screen, so the
  // order is a decision, and it is jv-ears' own: a stall outranks a loss,
  // because "no audio at all" is the bigger fact. Drawing the other order
  // would put the plate and the heartbeat it came from in disagreement.
  readonly property string state: {
    const m = root.metrics;
    if (m === null)
      return "unknown";
    if (m.mic_open !== 1)
      return "off";
    if (!(typeof m.capture_age_s === "number" && m.capture_age_s <= root.stallS))
      return "stalled";
    return root.recentLoss(m) ? "losing" : "live";
  }

  readonly property bool known: root.state !== "unknown"
  // The one claim that matters: audio is being captured in this room. A
  // microphone losing chunks is still recording the ones it keeps, so the
  // privacy light stays on — the hole is a second fact, not a reprieve.
  readonly property bool capturing: root.state === "live" || root.state === "losing"
  // Open but silent. Worth saying — it is the failure that hid for a day.
  readonly property bool stalled: root.state === "stalled"
  // Open, delivering, and dropping some of it on the floor.
  readonly property bool losing: root.state === "losing"

  // Is there a hole in the recording recent enough to still be news?
  //
  // jv-ears publishes the age only once something HAS been discarded, so
  // the absence of the gauge is the answer "nothing was lost" and not a
  // jv-ears that forgot to say. Which is also why an age that is present
  // but unreadable comes out true: the presence is the evidence, the
  // value only dates it, and a loss we cannot date is not a loss we may
  // call old. `<=` matches CaptureMeter.health() — including a negative
  // age, which is a stamp taken on PortAudio's thread and subtracted on
  // the asyncio loop, not a loss from the future.
  function recentLoss(m: var): bool {
    const age = m.capture_loss_age_s;
    if (age === undefined)
      return false;
    return typeof age !== "number" || age <= root.lossWindowS;
  }

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

  // The gauges, or null if this heartbeat carries none. Null is NOT "off":
  // a jv-ears too old to report the microphone is a jv-ears we cannot read
  // one from, and guessing "off" there is the lie that matters.
  readonly property var metrics: {
    const env = root.health;
    if (env === null || root.healthStale)
      return null;
    const m = env.body.metrics;
    return m && typeof m.mic_open === "number" ? m : null;
  }

  // --- how long a heartbeat describes the present ----------------------

  // schemas/sys.health.json: "Missing 2 consecutive periods = presumed
  // dead". So a heartbeat speaks for two of its own periods and no longer;
  // after that jv-ears may have died with the microphone open and we would
  // have no way to know. `ageOf` is Infinity when the age is not knowable
  // (no clock, no ts), which fails this — an age we cannot compute is not
  // an age we may assume is zero.
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
  // with no jv-ears on the bus runs no timer at all (§06: 0 fps when
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
