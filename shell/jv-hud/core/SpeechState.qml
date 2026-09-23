// SpeechState — what Jarvis is doing, as the bus actually reported it (A3).
//
// The HUD's first element backed by real sensor topics, and therefore the
// first one that can break invariant 10 by arithmetic. It answers exactly
// one question — idle / listening / speaking / interrupted / unknown —
// from three topics, and it is the `core/` half on purpose: this is the
// logic, so it is pure QtQuick and tested headlessly (A9's rule).
// StatePlate.qml next door is the wiring and the pixels.
//
// Where each answer comes from:
//
//   speech.state  (jv-voice)  idle / speaking / interrupted, verbatim.
//   audio.wake    (jv-ears)   the wake word fired -> "listening".
//   audio.vad     (jv-ears)   speech_end closes a listening window.
//
// "listening" is the claim that costs the most if it is wrong, because it
// is a claim about the microphone. jv-ears publishes when a window OPENS
// (audio.wake) but nothing when it closes, so closing has to be inferred,
// and every rule below is chosen to under-claim rather than over-claim:
//
//   · Jarvis answering (speech.state -> speaking, newer than the wake)
//     means it already heard you: the window is done.
//   · audio.vad speech_end newer than the wake means the utterance closed
//     — jv-ears disarms there for a wake-gated utterance and transcribes.
//     (If that segment was NOT gated, ears stays armed and we stop saying
//     "listening" a little early. Early is the safe direction.)
//   · otherwise the window expires on its own after `wakeWindowS`, which
//     mirrors jv-ears' `wake_timeout_s`. It is a fallback, not the primary
//     rule, and it is a HUD-side constant because nothing publishes ears'
//     configuration — so keep it AT OR BELOW the value ears is tuned to.
//
// The three topics arrive on one bus with one clock (CLOCK_MONOTONIC `ts`),
// so ordering them is just comparing `ts`. A frame without a numeric one
// cannot be ordered and is therefore not used at all.
//
// Nothing here ever shows a state it did not observe: with no link, no
// frame, or no trustworthy frame, the answer is "unknown" — which the view
// draws as nothing. Silence and calm are different things.
import QtQuick

QtObject {
  id: root

  // Anything offering `linkUp`, `latest(topic)` and `ageOf(envelope)`:
  // the `Bus` singleton in production, a BusModel the tests drive by hand.
  // Consumer-only by construction — there is nothing to publish with.
  property var bus: null

  // How long a wake word keeps meaning "listening" when nothing else has
  // said otherwise. jv-ears' `wake_timeout_s` default is 8 s; see above.
  property real wakeWindowS: 8.0

  // The one output: "unknown" | "idle" | "listening" | "speaking" | "interrupted".
  readonly property string state: {
    if (root.listening)
      return "listening";
    const s = root.speech;
    if (s === null)
      return "unknown";
    const named = s.body.state;
    // A body from a schema version we know, carrying a state we do not,
    // is still not something to draw. Later versions may add states; the
    // nearest thing we recognise would be an invention, not a reading.
    return named === "idle" || named === "speaking" || named === "interrupted" ? named : "unknown";
  }

  // Did we observe anything at all? False means the view draws nothing.
  readonly property bool known: root.state !== "unknown"
  readonly property bool idle: root.state === "idle"
  // Jarvis (or the room) is genuinely doing something — this, and only
  // this, is what earns the ember/teal accent (§06: scarcity is the point).
  readonly property bool active: root.state === "listening" || root.state === "speaking"

  // --- the frames we are willing to believe ---------------------------

  // The latest speech.state we can read, or null.
  readonly property var speech: {
    const env = root.frameOn("speech.state");
    return root.wellFormed(env) && env.conf >= 1 && typeof env.body.state === "string" ? env : null;
  }

  // The latest audio.wake that met its own bar, or null. A detection that
  // scored below the threshold it declares — or whose envelope confidence
  // contradicts that score — is a frame that disagrees with itself, and
  // invariant 4 says a consumer handles that rather than rendering it.
  readonly property var wake: {
    const env = root.frameOn("audio.wake");
    if (!root.wellFormed(env))
      return null;
    const b = env.body;
    if (typeof b.score !== "number" || typeof b.threshold !== "number")
      return null;
    return b.score >= b.threshold && env.conf >= b.threshold ? env : null;
  }

  // The latest audio.vad boundary, or null.
  readonly property var vad: {
    const env = root.frameOn("audio.vad");
    return root.wellFormed(env) && env.conf >= 1 && typeof env.body.event === "string" ? env : null;
  }

  // --- is the microphone open for us? ---------------------------------

  readonly property bool listening: root.wakeFresh && !root.wakeConsumed

  // Young enough to still describe now. `ageOf` is Infinity when the age
  // is not knowable (no clock yet, no ts), which fails this — an age we
  // cannot compute is not an age we may assume is zero.
  readonly property bool wakeFresh: root.wake !== null && !root.wakeTimedOut && root.ageOf(root.wake) <= root.wakeWindowS

  // Something newer than the wake says the window is over.
  readonly property bool wakeConsumed: root.answered || root.utteranceEnded

  // Jarvis started speaking after the wake: it heard you and is replying.
  // (A `speaking` frame OLDER than the wake is barge-in, not an answer —
  // wake detection stays live while jv-voice talks — so the user's word
  // has landed and "listening" is the true thing to show.)
  readonly property bool answered: root.wake !== null && root.speech !== null && root.speech.body.state === "speaking" && root.speech.ts >= root.wake.ts

  // The utterance closed after the wake: ears is transcribing, not taking
  // more. `interrupted` deliberately does NOT count — jv-voice publishes
  // it BECAUSE of the wake, and blanking the HUD there would blank it at
  // the exact moment the user is talking.
  readonly property bool utteranceEnded: root.wake !== null && root.vad !== null && root.vad.body.event === "speech_end" && root.vad.ts >= root.wake.ts

  // --- the fallback timeout -------------------------------------------

  // Set by the timer below; cleared whenever a new wake arrives. A plain
  // property rather than a computed one because time passing is not a
  // property change: no binding re-evaluates just because a clock moved.
  property bool wakeTimedOut: false

  // Identity of the current wake: a new detection always has a new `seq`
  // (per-publisher, strictly increasing). Watching this rather than the
  // frame object means the window re-arms exactly once per detection.
  readonly property string wakeKey: root.wake === null ? "" : root.wake.seq + "@" + root.wake.ts

  onWakeKeyChanged: root.armWakeExpiry()
  onWakeWindowSChanged: root.armWakeExpiry()

  // One shot, armed only while a wake is actually open, so an idle HUD
  // runs no timer at all (§06: 0 fps when nothing is happening).
  readonly property Timer expiry: Timer {
    repeat: false
    onTriggered: root.wakeTimedOut = true
  }

  function armWakeExpiry(): void {
    root.wakeTimedOut = false;
    // Whatever is LEFT of the window, not the whole of it: a frame that
    // spent time in flight is already partway through its own window.
    const left = root.wakeWindowS - root.ageOf(root.wake);
    if (root.wake === null || !(left > 0)) {
      root.expiry.running = false;
      return;
    }
    root.expiry.interval = Math.max(1, Math.ceil(left * 1000));
    root.expiry.restart();
  }

  // --- reading the bus, defensively -----------------------------------

  // The last frame on `topic`, but only while the bridge holds a live
  // subscription. A cached frame from a link that has since dropped
  // describes a machine we can no longer see.
  function frameOn(topic: string): var {
    if (!root.bus || !root.bus.linkUp)
      return null;
    return root.bus.latest(topic);
  }

  function ageOf(envelope: var): real {
    return root.bus && typeof root.bus.ageOf === "function" ? root.bus.ageOf(envelope) : Infinity;
  }

  // The envelope floor for every topic here: the schema version we were
  // written against (invariant 2 — a v2 body is not a v1 body), a numeric
  // `conf` (invariant 4), a body, and a numeric `ts`. The last one is not
  // pedantry: ordering a wake against a speech transition is the whole of
  // the listening rule, and an unorderable frame would have to be guessed
  // at.
  function wellFormed(envelope: var): bool {
    return !!envelope && envelope.v === 1 && typeof envelope.ts === "number" && typeof envelope.conf === "number" && !!envelope.body;
  }
}
