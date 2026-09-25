// SpeechState — what Jarvis is doing, as the bus actually reported it (A3).
//
// The HUD's first element backed by real sensor topics, and therefore the
// first one that can break invariant 10 by arithmetic. It answers exactly
// one question — idle / listening / speaking / interrupted / preempted /
// unknown — from three topics, and it is the `core/` half on purpose: this
// is the logic, so it is pure QtQuick and tested headlessly (A9's rule).
// StatePlate.qml next door is the wiring and the pixels.
//
// Where each answer comes from:
//
//   speech.state   (jv-voice)  idle / speaking / interrupted, verbatim —
//                              and `reason`, which says which of the two
//                              of you stopped the sentence (B91, below).
//   audio.wake     (jv-ears)   the wake word fired -> "listening"; one
//                              arriving mid-question also ends it, since
//                              the user abandoned that question.
//   audio.vad      (jv-ears)   speech_end closes a listening window, and
//                              opens a thinking one.
//   brain.request  (jv CLI,    a typed/replayed question -> "thinking".
//                   harness)
//   brain.response (jv-brain)  the answer landed -> thinking is over.
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
//     is ears' own `wake_timeout_s`, read off its heartbeat (A14). It is
//     a fallback, not the primary rule. This used to be a constant typed
//     in here because nothing published ears' configuration; ears now
//     states the budgets it enforces, so the HUD reads them instead of
//     being asked to remember them.
//
// "thinking" (A12) is the other half of the same honesty problem. Between
// the moment Jarvis has your words and the moment you hear anything back
// it is working — prefill, generation, maybe a tool round-trip — and this
// element used to call that `idle`, which the view draws as nothing at
// all. So the HUD went dark at the exact moment the user was waiting and
// wanted to know something was happening.
//
// Nothing on the bus says "the brain accepted this", so the prompt has to
// be recognised, and only two things are recognisable as one:
//
//   · a wake-gated utterance ENDING (the `utteranceEnded` rule above).
//     jv-ears disarms there and transcribes, and jv-brain answers every
//     transcript final — so that boundary is a question in flight. A
//     speech_end with no wake behind it is just speech in the room (ears'
//     VAD runs continuously, see A4) and means nothing here.
//   · a `brain.request`, which is how the non-voice frontends ask.
//
// and four things end it: `brain.response` (the only thing that can, for
// a silent CLI query or a reply that errored and was never spoken), the
// first `speaking` frame after it (the user is now hearing the answer —
// the brain may still be generating, but saying so would flip the word
// once per streamed sentence), a WAKE newer than the prompt (A17 — the
// user gave up on that question and jv-brain has already cancelled it,
// publishing no response at all), and `thinkWindowS` as the floor under a
// brain that died mid-turn.
//
// Whatever jv-voice says is audible RIGHT NOW outranks it: `speaking` and
// `interrupted` are observations, "thinking" is an inference, and the
// inference must never talk over the observation.
//
// All of these topics arrive on one bus with one clock (CLOCK_MONOTONIC
// `ts`), so ordering them is just comparing `ts`. A frame without a
// numeric one cannot be ordered and is therefore not used at all.
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
  // said otherwise. StatePlate binds this to what jv-ears reports on its
  // own heartbeat (core/EarsBudgets.qml, A14); the value here is the
  // fallback for a jv-ears that has not said, and a tools test fails the
  // build if it drifts from ears' `wake_timeout_s` default.
  property real wakeWindowS: 8.0

  // How long an unanswered prompt keeps meaning "thinking". Unlike
  // `wakeWindowS` this mirrors no service's configuration: it is a policy
  // about how long the HUD is willing to assert work it cannot see. An
  // answer can legitimately take this long on the CPU rung (invariant 6),
  // and past it we no longer know whether anyone is still working — so we
  // stop saying so and fall back to jv-voice, which under-claims. That is
  // the direction this file always errs in, and the CPU rung that explains
  // a slow answer is on screen anyway (HealthPlate, A6).
  property real thinkWindowS: 30.0

  // The one output: "unknown" | "idle" | "listening" | "thinking" |
  // "speaking" | "interrupted" | "preempted".
  readonly property string state: {
    // The microphone claim first: it is the one that costs the most.
    if (root.listening)
      return "listening";
    // A body from a schema version we know, carrying a state we do not, is
    // still not something to draw. Later versions may add states; the
    // nearest thing we recognise would be an invention, not a reading.
    const named = root.speech === null ? "" : root.speech.body.state;
    // What is audible right now beats what we infer about the brain.
    if (named === "speaking")
      return named;
    if (named === "interrupted")
      return root.selfInterrupted ? "preempted" : "interrupted";
    if (root.promptOpen)
      return "thinking";
    return named === "idle" ? "idle" : "unknown";
  }

  // Did we observe anything at all? False means the view draws nothing.
  readonly property bool known: root.state !== "unknown"
  readonly property bool idle: root.state === "idle"
  // Jarvis (or the room) is genuinely doing something — this, and only
  // this, is what earns the ember/teal accent (§06: scarcity is the point).
  readonly property bool active: root.state === "listening" || root.state === "speaking"

  // --- which of the two of you stopped the sentence (B91) -------------

  // An utterance can stop for two quite different reasons and until now
  // both reached the screen as INTERRUPTED: the user talked over Jarvis
  // (`wake`), or Jarvis cut its own sentence short because something more
  // urgent arrived (`preempted` — jv-voice drops the rest of that turn and
  // speaks the urgent one instead). Only the second is worth its own word,
  // because only the second is a thing the user did not do and would
  // otherwise have no way to tell from the one they did.
  //
  // Everything else is `interrupted`, which stays true of all of them: a
  // `wake`, a frame with no `reason` at all, a reason that is not a
  // string, and a word a later schema version adds. That is the same
  // direction this whole file errs in — an utterance we watched stop is a
  // fact, and naming who stopped it on a field we could not read would be
  // an invention. The reason rides other transitions too (`completed` and
  // `error` land on the `idle` that follows), and they are not read here:
  // `idle` draws nothing, and a reply that failed is HealthPlate's
  // sentence (A6), not a word on this plate.
  readonly property bool selfInterrupted: root.speech !== null && root.speech.body.reason === "preempted"

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

  // The latest brain.request we can read, or null. A command topic, so its
  // envelope conf is fixed at 1.0; a body that misses its own schema
  // (empty text, no source) is not a question we can claim to have.
  readonly property var request: {
    const env = root.frameOn("brain.request");
    if (!root.wellFormed(env) || env.conf < 1)
      return null;
    const b = env.body;
    return typeof b.text === "string" && b.text.length > 0 && typeof b.source === "string" ? env : null;
  }

  // The latest brain.response we can read, or null. `finish_reason` is
  // what makes it a reply rather than a fragment — including the `error`
  // one, which is the reply nobody ever hears.
  readonly property var response: {
    const env = root.frameOn("brain.response");
    return root.wellFormed(env) && env.conf >= 1 && typeof env.body.finish_reason === "string" ? env : null;
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

  // --- is the brain working on something of ours? ----------------------

  readonly property bool promptOpen: root.promptFresh && !root.answered_ && !root.abandoned

  // The newest thing we can recognise as a question in flight. Newest
  // rather than first: a typed question during a spoken turn is the live
  // one, and running the window off the older prompt would close it early.
  readonly property var prompt: {
    const spoken = root.utteranceEnded ? root.vad : null;
    if (spoken === null)
      return root.request;
    if (root.request === null)
      return spoken;
    return root.request.ts >= spoken.ts ? root.request : spoken;
  }

  // Young enough to still describe now — same rule as `wakeFresh`, and
  // the same reason: an age we cannot compute is not an age of zero.
  readonly property bool promptFresh: root.prompt !== null && !root.thinkTimedOut && root.ageOf(root.prompt) <= root.thinkWindowS

  // Trailing underscore because `answered` above is about the wake window;
  // this one is about the prompt, and conflating them would be a bug
  // waiting to happen.
  readonly property bool answered_: root.heardAnswer || root.repliedOnBus

  // The user has heard this answer START. Latched, not derived, and the
  // difference matters: `bus.latest()` holds only the newest frame per
  // topic, so the `speaking` frame is GONE the moment jv-voice publishes
  // the idle that follows it. Derived, this would forget mid-reply — and
  // since jv-brain speaks one speech.say per sentence, it would forget
  // between every pair of sentences and flip the word back to "thinking"
  // each time. What is remembered here is an observation the bus no
  // longer carries, which is exactly what a latch is for.
  property bool heardAnswer: false

  // The reply exists on the bus. For a silent query, or one that errored
  // before a word was synthesised, this is the ONLY thing that ever says
  // the work is over. Safe to derive: nothing replaces a brain.response
  // except a newer one, which answers the same prompt or a later one.
  readonly property bool repliedOnBus: root.prompt !== null && root.response !== null && root.response.ts >= root.prompt.ts

  // Checked on both edges that can make it true — a speech frame arriving,
  // and the prompt changing under an already-speaking Jarvis — rather than
  // on a `repliedAloud` binding, which would depend on which of the two
  // re-evaluates first and would never fire at all in the second case.
  onSpeechChanged: root.noteSpokenAnswer()

  function noteSpokenAnswer(): void {
    if (root.prompt !== null && root.speech !== null && root.speech.body.state === "speaking" && root.speech.ts >= root.prompt.ts)
      root.heardAnswer = true;
  }

  // --- the question the user gave up on (A17) --------------------------

  // A wake NEWER than the open prompt: the user started talking to Jarvis
  // again before it answered, so that answer is not coming. jv-brain
  // cancels the turn in flight when it sees the same frame (B6), and an
  // interrupted turn publishes no `brain.response` — the frozen
  // `finish_reason` enum has no word for "the user stopped me" (proposal
  // R3). So the one thing that could have closed this window stopped
  // arriving, and without this the plate would keep claiming a working
  // brain until `thinkWindowS` ran out.
  //
  // Latched for the same reason `heardAnswer` is: `bus.latest()` holds one
  // frame per topic, so the wake that ended the window is gone the moment
  // the next detection lands — and a detection we refuse to believe leaves
  // nothing to compare against at all. Derived, an abandoned question
  // would come back to life.
  property bool abandoned: false

  // Checked on the WAKE edge only, unlike `heardAnswer`. A prompt that
  // arrives after a wake is a NEW question, not an abandoned one: jv-brain
  // saw the wake first, had nothing to cancel, and is now working on this.
  // `onPromptKeyChanged` clears the latch for exactly that reason.
  onWakeChanged: root.noteAbandonedPrompt()

  function noteAbandonedPrompt(): void {
    if (root.wake !== null && root.prompt !== null && root.spokenPrompt(root.prompt) && root.wake.ts >= root.prompt.ts)
      root.abandoned = true;
  }

  // Would the answer to this prompt be SPOKEN? Only a spoken turn is
  // cancellable — jv-brain's rule, and the honest one: a wake says the
  // user is talking to Jarvis, not that the CLI or the HUD stopped wanting
  // the reply it asked for, and a silent reply is not being talked over.
  // Claiming that question was abandoned would be the same lie in the
  // other direction.
  //
  // One field answers it for both prompt topics. `brain.request.speak`
  // defaults to true in the schema and in jv-brain, which is exactly what
  // `!== false` says; and the voice prompt is an audio.vad boundary, whose
  // frozen body has no such field and whose answer is spoken by
  // definition. A topic check in front of this would read like protection
  // and never change an answer.
  function spokenPrompt(envelope: var): bool {
    return envelope.body.speak !== false;
  }

  // --- the fallback timeouts ------------------------------------------

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

  // The same three pieces for the thinking window. Identity includes the
  // topic and publisher because a prompt can come from either of two
  // topics, and `seq` only counts per publisher.
  property bool thinkTimedOut: false

  readonly property string promptKey: root.prompt === null ? "" : root.prompt.topic + "/" + root.prompt.src + "#" + root.prompt.seq + "@" + root.prompt.ts

  onPromptKeyChanged: {
    // A different question: whatever we heard was the answer to the last
    // one. Re-checked immediately, because this prompt may already have
    // been answered by a frame that arrived before it did.
    root.heardAnswer = false;
    root.abandoned = false;
    root.noteSpokenAnswer();
    root.armThinkExpiry();
  }
  onThinkWindowSChanged: root.armThinkExpiry()

  readonly property Timer thinkExpiry: Timer {
    repeat: false
    onTriggered: root.thinkTimedOut = true
  }

  function armThinkExpiry(): void {
    root.thinkTimedOut = false;
    const left = root.thinkWindowS - root.ageOf(root.prompt);
    if (root.prompt === null || !(left > 0)) {
      root.thinkExpiry.running = false;
      return;
    }
    root.thinkExpiry.interval = Math.max(1, Math.ceil(left * 1000));
    root.thinkExpiry.restart();
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
