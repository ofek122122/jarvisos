// OutputState — Jarvis is talking and you cannot hear a word of it (A40).
//
// The HUD's `StatePlate` has said SPEAKING since A3, and that word is a
// claim about jv-voice rather than about the room: jv-voice accepted an
// utterance, synthesised it, and handed samples to the default output
// device. If that device is muted, every one of those steps succeeded and
// the user heard silence — so the HUD was, at that moment, showing a true
// frame that added up to a false impression. Of all the ways a voice
// assistant fails, "it answered and I heard nothing" is the one with the
// least evidence attached: no service is unwell, nothing errored, the
// audit log is clean, and the only thing wrong is a toggle somewhere else
// on the machine.
//
// This element says the missing half, out of two topics:
//
//   speech.state    (jv-voice)   an utterance is in flight RIGHT NOW.
//   context.system  (jv-context)  the default sink, at 1 Hz: audio_muted
//                                and audio_volume, both required fields
//                                of schemas/context.system.json.
//
// It is a LIVE READING and not a latch — unlike ActionState (A37) or
// HeardState (A26), which remember a thing the bus has stopped carrying.
// Both inputs here describe the present, so the line goes away the instant
// either stops being true: Jarvis finishes the sentence, or you unmute.
// There is nothing to forget and nothing to time out; the only clock in
// this file exists to stop BELIEVING a frame, never to hide one.
//
// Four decisions shape it:
//
// ONLY WHILE SPEAKING. A muted machine is not news — it is a choice you
// made, probably on purpose, and a HUD that nags about it all day is the
// opposite of §06's earned emptiness. It becomes news at exactly one
// moment: when Jarvis is spending its breath on you and none of it is
// arriving. That is also why this plate sits directly under `StatePlate`
// in the stack — the two are one reading, the way HeardPlate is one
// reading with the word THINKING above it.
//
// SILENCE, NOT QUIETNESS. `audio_muted` is silence by definition, and so
// is `audio_volume` at zero. A threshold on "too quiet to hear" would be a
// guess about your speakers and your room, and it would put a plate on
// screen for a machine you deliberately turned down. There is no such
// threshold here, and the failure that leaves — a reply at 3% volume in a
// loud room — is one the user can at least reason about.
//
// THE RAW jv-voice WORD, NOT `SpeechState`'s. SpeechState answers "what is
// Jarvis doing" and lets the microphone claim outrank the speaking one
// (a barge-in reads as `listening` while jv-voice is still finishing its
// sentence). That is the right answer to its question and the wrong input
// to this one: what matters here is whether an utterance is being played,
// which is `speech.state` verbatim.
//
// A `speaking` FRAME DOES NOT MEAN FOREVER. jv-voice publishes `idle` when
// it finishes, so in ordinary running this element is ended by a real
// signal. But a jv-voice that died mid-sentence leaves `speaking` on the
// topic with nobody to retract it, and a muted machine would then carry
// this plate until the next reboot — a permanently lit corner, which is
// the one thing §06 will not have. `sayWindowS` is the backstop: how long
// the HUD is willing to assert an utterance it cannot see the end of. It
// mirrors no service's configuration (B7) — it is this element's policy,
// the same kind of number as SpeechState's `thinkWindowS`.
//
// On confidence (invariant 4): schemas/context.system.json fixes envelope
// conf at 1.0, and so does speech.state. A hedged snapshot of a mixer is
// a frame that disagrees with itself, and this plate is not worth showing
// on a maybe.
//
// On what it assumes (and this is the one assumption in the file):
// jv-voice plays through `sd.play(audio, rate)` with no device argument
// (services/jv-voice/jv_voice/player.py), which is PortAudio's default
// output — the same default sink jv-context reads with
// `wpctl get-volume @DEFAULT_AUDIO_SINK@`. If jv-voice ever pins a device,
// this plate becomes a true statement about the wrong sink and must gain a
// source that names the one it means. The other direction is safe and
// stays unreported: PipeWire can mute jv-voice's STREAM while the sink is
// open, and that is silence this element cannot see — it under-claims,
// which is the direction every element in core/ errs in.
import QtQuick

QtObject {
  id: root

  // Anything offering `linkUp`, `latest(topic)` and `ageOf(envelope)`:
  // the `Bus` singleton in production, a BusModel the tests drive by hand.
  // Consumer-only by construction — there is nothing to publish with.
  property var bus: null

  // How long one 1 Hz snapshot describes the present. The rate is stated
  // by schemas/context.system.json itself ("1 Hz system snapshot"), so
  // this is read off the schema rather than copied out of jv-context's
  // configuration — it is not the hand-copied constant B7 warns about.
  // Three periods, not two: jv-context is a user-session Python process
  // competing with CPU Whisper and an 8B prefill, and the moment it is
  // late is exactly the moment this machine is busy. Two would make the
  // plate blink under load; three is the first number that is not a coin
  // flip about the scheduler.
  property real snapshotS: 3.0

  // How long a `speaking` frame keeps meaning an utterance is in flight.
  // The backstop for a jv-voice that died mid-sentence (see the header),
  // never the ordinary exit — which is jv-voice publishing `idle`.
  property real sayWindowS: 30.0

  // --- the outputs ----------------------------------------------------

  // Jarvis is speaking and this machine is making no sound. The plate
  // draws nothing whenever this is false, which is every moment of an
  // ordinary day.
  //
  // No `linked` term here, deliberately: both readers below already refuse
  // to hand back a frame off a dead link, and a third guard on top of them
  // would be unreachable — which means an edit that deleted one of THEIRS
  // would be invisible to every test. The gate belongs where the frame is
  // read, once.
  readonly property bool unheard: !root.stale && root.speaking && root.silence !== ""

  // Why you cannot hear it: "muted" or "zero", and "" whenever there is
  // nothing to say. Two different facts with two different fixes, so they
  // are two different words — a single "silent" would send the user to
  // the wrong control half the time.
  readonly property string reason: root.unheard ? root.silence : ""

  // --- reading the two frames ------------------------------------------

  // True only while the bridge holds a live subscription. A cached frame
  // from a link that has since dropped describes a machine we can no
  // longer see — including a mixer somebody may have unmuted since.
  readonly property bool linked: !!root.bus && root.bus.linkUp === true

  // The newest sink snapshot we are willing to read, or null. Null covers
  // nothing-there, a body from a schema version we were not written
  // against (invariant 2), a frame with no orderable `ts` (without one
  // there is no age and so no expiry), a hedged `conf`, and a body missing
  // either field this element turns on. All of them mean the same thing:
  // we do not know what the speakers are doing, so we say nothing.
  readonly property var snapshot: {
    if (!root.linked || typeof root.bus.latest !== "function")
      return null;
    const env = root.bus.latest("context.system");
    if (!root.wellFormed(env))
      return null;
    const b = env.body;
    if (typeof b.audio_muted !== "boolean")
      return null;
    return typeof b.audio_volume === "number" ? env : null;
  }

  // The newest speech.state we can read, or null.
  readonly property var speech: {
    if (!root.linked || typeof root.bus.latest !== "function")
      return null;
    const env = root.bus.latest("speech.state");
    return root.wellFormed(env) && typeof env.body.state === "string" ? env : null;
  }

  // Is an utterance being played right now? `interrupted` is deliberately
  // not counted: it is how a sentence ENDED, and a barge-in is the user
  // already having stopped whatever they could not hear.
  readonly property bool speaking: root.speech !== null && root.speech.body.state === "speaking"

  // What the mixer says, whether or not anyone is speaking: "muted",
  // "zero", or "" for a sink that would be audible. `muted` wins when both
  // are true — it is the toggle, and the one a user flips first.
  readonly property string silence: {
    const env = root.snapshot;
    if (env === null)
      return "";
    if (env.body.audio_muted === true)
      return "muted";
    return env.body.audio_volume <= 0 ? "zero" : "";
  }

  // --- how long either frame describes the present ---------------------

  // Either input too old to describe now. `ageOf` is Infinity when the age
  // is not knowable (no clock, no ts), which lands here as stale — an age
  // we cannot compute is not an age we may assume is zero. `expired` is
  // what makes this re-evaluate as time passes; the two ages are what make
  // it TRUE, because no binding re-runs just because a clock moved.
  readonly property bool stale: root.snapshot === null || root.speech === null || root.expired || root.ageOf(root.snapshot) > root.snapshotS || root.ageOf(root.speech) > root.sayWindowS

  // Set by the timer below, cleared by every frame that moves either
  // deadline. A plain property, not a computed one, for the reason above.
  property bool expired: false

  // Identity of the pair currently believed: `seq` is per-publisher and
  // strictly increasing, so this changes exactly once per frame on either
  // topic. One key for both, because one timer serves both — whichever
  // deadline comes first is the one that matters.
  readonly property string pairKey: root.keyOf(root.snapshot) + "|" + root.keyOf(root.speech)

  onPairKeyChanged: root.armExpiry()
  onSnapshotSChanged: root.armExpiry()
  onSayWindowSChanged: root.armExpiry()

  function keyOf(envelope: var): string {
    return envelope === null ? "" : envelope.seq + "@" + envelope.ts;
  }

  // One shot, armed only while there are two frames to expire — a HUD on a
  // machine with no jv-context, or one nobody has spoken to, runs no timer
  // at all (§06: 0 fps when nothing is happening). On a live machine it is
  // re-armed once a second by jv-context's own cadence, and only while
  // jv-voice is mid-utterance, which is the only window this element has
  // any opinion in.
  readonly property Timer expiry: Timer {
    repeat: false
    onTriggered: root.expired = true
  }

  function armExpiry(): void {
    root.expired = false;
    if (root.snapshot === null || root.speech === null) {
      root.expiry.running = false;
      return;
    }
    // Whatever is LEFT of each window, not the whole of it: a frame that
    // spent time in flight is already partway through its own life. The
    // earlier deadline governs — believing the pair is believing both.
    const left = Math.min(root.snapshotS - root.ageOf(root.snapshot), root.sayWindowS - root.ageOf(root.speech));
    if (!(left > 0)) {
      root.expiry.running = false;
      root.expired = true;
      return;
    }
    root.expiry.interval = Math.max(1, Math.ceil(left * 1000));
    root.expiry.restart();
  }

  // --- reading the bus, defensively ------------------------------------

  function ageOf(envelope: var): real {
    return root.bus && typeof root.bus.ageOf === "function" ? root.bus.ageOf(envelope) : Infinity;
  }

  // The envelope floor: the schema version we were written against
  // (invariant 2 — a v2 body is not a v1 body), a numeric `ts`, an
  // unhedged `conf` (see the header), and a body.
  function wellFormed(envelope: var): bool {
    return !!envelope && envelope.v === 1 && typeof envelope.ts === "number" && envelope.conf >= 1 && !!envelope.body;
  }
}
