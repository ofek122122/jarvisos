// HeardState — the words Jarvis is about to act on (A26).
//
// The HUD could already say that the microphone was open (A4), that a wake
// word fired and that Jarvis was thinking (A3/A12). What it could never say
// is the one thing that decides whether any of that was worth anything:
// WHAT it heard. So the most common failure of a voice assistant — it
// heard something else — was invisible until it came back as a wrong
// answer, and by then "it misheard me", "it ignored me" and "the brain is
// slow" all looked identical from the chair.
//
// This element is the readable copy of the transcript, and nothing more.
// It answers one question — is there a line to show, and what is it —
// from one topic:
//
//   audio.transcript  (jv-ears)  ASR output, partial and final.
//
// and it reads one more only to know WHEN the turn it belongs to began:
//
//   audio.vad  (jv-ears)  speech_end — the end of the utterance being
//                         transcribed. Never rendered, never a reason to
//                         show or hide the line; see the backstop below.
//
// FINALS ONLY, and that is the whole editorial policy. The schema says it
// in its own words: "Partials are provisional and may be rewritten; only
// finals are acted on." A partial that gets rewritten a breath later would
// have shown the user a sentence Jarvis never acted on, which is a more
// expensive kind of wrong than showing nothing. It is also why the line
// has to be LATCHED rather than derived: partials ride the same topic, so
// `bus.latest()` replaces the final with the next utterance's first
// partial, and a derived reading would blank itself the instant the user
// started speaking again. What is remembered here is an observation the
// bus no longer carries — the same reason ConfirmState latches a question.
//
// Why showing this is a reasonable thing to do at all: jv-ears transcribes
// ONLY wake-gated utterances (the first line of its pipeline). Everything
// on this topic was addressed to Jarvis after a wake word; the VAD runs
// continuously and the room's ordinary conversation never reaches an ASR,
// let alone a screen. `speech-no-wake` is the recording that says so, and
// tst_sessionreplay replays it through this element for exactly that
// reason. If ears ever transcribes ungated speech, this plate becomes a
// live transcript of the room and this paragraph is where to start.
//
// A latch has to be let go of, and there are three ways:
//
//   · Jarvis starts answering. The user is now hearing the reply, and the
//     reply is a better answer to "did it hear me?" than the transcript
//     is. This is the ordinary exit and it is a real signal, not a timer —
//     which is what keeps the line out of the "on screen for a fixed
//     duration" territory nothing in this HUD has entered yet (A22).
//   · the link dropping. A line latched off a bus we can no longer see
//     describes a turn we can no longer see.
//   · `holdS`, the backstop for a brain that died before it said anything
//     at all. It is the same window SpeechState is willing to say
//     "thinking" for, because it is the same claim — a question is in
//     flight — and a tools gate fails the build if the two ever drift.
//
// Equal lengths were not enough, and A57 is why. SpeechState times its
// "thinking" window off the utterance's `audio.vad speech_end` — the frame
// that says a question is in flight — while this element only ever saw the
// transcript, which lands however long faster-whisper took AFTER that
// boundary. Two equal windows measured from different instants are not one
// window: the state plate let go first and the words sat on screen alone
// for the length of the ASR, a transcript with nothing above it saying why
// it was still there. So the hold is anchored to the boundary of the
// utterance these words belong to — `utterance_id` is minted at
// speech_start and threaded through both topics, which is what makes the
// two frames matchable at all — and falls back to the transcript's own
// `ts` when that boundary is not something we saw. The fallback is the old
// behaviour and errs the way it always did: too long rather than too
// short. Nothing about this decides WHETHER the line is shown; a missing,
// mismatched or unreadable boundary costs the reader nothing.
//
// None of the committed recordings COULD show this, and that is why it
// survived five suites: the fixture generator stamped each final at the
// same `ts` as the speech_end before it, so in every replay the ASR was
// instantaneous and both anchors were the same number. A58 closed that —
// the generator now stamps a final at the sample clock plus the ASR
// measured on ares, so the three recordings that contain one put 2.2 s
// between the boundary and the words, and tst_sessionreplay reads the
// anchor off a real recording. A live recording of a real utterance
// (A28) would still be better; this is the part that needed no human at
// the machine.
//
// On confidence (invariant 4). A numeric envelope `conf` is required and
// nothing else is done with it, which is a decision and not an oversight.
// The three real finals in harness/fixtures/sessions/ carry 0.886 (quiet
// room), 0.863 (mid-sentence pause) and 0.739 (music bed) — and all three
// transcribe their sentence correctly. So every bar inside that spread
// would mark a word-perfect transcript as doubtful, and every bar below it
// would never fire: exp(avg_logprob) is measuring the room, not whether
// the words are right. A doubt marker that fires on correct transcripts is
// one the user learns to ignore, which is the LinkPlate cry-wolf failure
// with better manners. tst_sessionreplay pins this against the recordings
// so that changing the decision means arguing with real data.
//
// `lang` is the exception, and only because there is a known gap behind
// it: the pinned ASR is English-only (faster-distil-small.en), so a frame
// claiming anything else is a frame disagreeing with the model that
// produced it. That is worth a quiet word on screen rather than a silent
// pass-through.
import QtQuick

QtObject {
  id: root

  // Anything offering `linkUp`, `latest(topic)` and `ageOf(envelope)`:
  // the `Bus` singleton in production, a BusModel the tests drive by hand.
  // Consumer-only by construction — there is nothing to publish with.
  property var bus: null

  // How long a transcript keeps meaning "Jarvis is working on this" when
  // nothing ever answers it, measured from the end of the utterance rather
  // than from the moment the words reached us (see the note above).
  // Mirrors no service's configuration: like SpeechState's `thinkWindowS`,
  // it is a policy about how long the HUD is willing to assert a question
  // whose end it may have missed. The two are the same claim about the same
  // turn and are pinned equal by a tools test — a line that outlived the
  // "THINKING" beside it would be words with nothing left saying they are
  // still in flight.
  property real holdS: 30.0

  // The language this machine expects to be spoken to in (the locked
  // decision: English voice in, English voice out). Named here rather than
  // compared against a literal so that the day it changes, it changes in
  // one place that says what it is.
  property string expectedLang: "en"

  // --- the outputs ----------------------------------------------------

  // Is there a line to show? The plate draws nothing whenever this is
  // false, which is the ordinary state of a machine nobody is talking to.
  readonly property bool heard: root.linked && root.transcript !== null && !root.answering && !root.expired

  // What jv-ears transcribed, in its own words. Whitespace is collapsed
  // and nothing else is touched: a stray newline would reshape the plate
  // rather than the sentence, and no word is changed by flattening one.
  // A paraphrase here would be the HUD claiming Jarvis heard something it
  // did not.
  readonly property string text: root.heard ? root.flatten(root.stringOf(root.transcript, "text")) : ""

  // The language jv-ears detected, as a BCP-47 primary tag, or "".
  readonly property string lang: root.heard ? root.stringOf(root.transcript, "lang") : ""

  // A transcript the English-only ASR says is not English. Not an alarm —
  // it is a fact about a frame that disagrees with the model behind it,
  // and the reader deserves to know before wondering why the answer made
  // no sense.
  readonly property bool foreignLang: root.lang.length > 0 && root.lang !== root.expectedLang

  // The utterance these words belong to, for anyone correlating this with
  // the rest of the turn. Empty whenever there is nothing to show.
  readonly property string utteranceId: root.heard ? root.stringOf(root.transcript, "utterance_id") : ""

  // --- the line we are holding -----------------------------------------

  // The latched final envelope, or null. A plain property: it is a memory,
  // not a reading, and every path that sets it is below.
  property var transcript: null

  // True only while the bridge holds a live subscription. Separate from
  // `frame` on purpose — a link that drops must forget the line, while a
  // frame we merely cannot parse must not.
  readonly property bool linked: !!root.bus && root.bus.linkUp === true

  onLinkedChanged: {
    if (!root.linked) {
      root.transcript = null;
      root.boundary = null;
    }
  }

  // The newest audio.transcript we are willing to read, or null. Null
  // covers three different things — nothing there, a partial, and
  // something unreadable — and `apply()` treats all of them the same way:
  // as no news. Refusing to read a frame is never the same as being
  // answered.
  readonly property var frame: {
    if (!root.linked || typeof root.bus.latest !== "function")
      return null;
    const env = root.bus.latest("audio.transcript");
    if (!root.wellFormed(env))
      return null;
    const b = env.body;
    if (b.kind !== "final")
      return null;
    // The three fields the schema requires of every transcript. An
    // utterance_id is what ties these words to the rest of the turn; text
    // that flattens to nothing is a final jv-ears would never have
    // published, and a blank plate is not a reading.
    if (typeof b.utterance_id !== "string" || b.utterance_id.length === 0)
      return null;
    if (typeof b.lang !== "string" || b.lang.length === 0)
      return null;
    return typeof b.text === "string" && root.flatten(b.text).length > 0 ? env : null;
  }

  onFrameChanged: {
    // Newest wins: a second final is a second thing the user said, and the
    // first one is no longer what Jarvis is working on.
    if (root.frame !== null)
      root.transcript = root.frame;
  }

  // --- has the answer started? -----------------------------------------

  // The latest speech.state we can read, or null. A state topic, so its
  // envelope conf is fixed at 1.0 by its schema.
  readonly property var speech: {
    const env = root.frameOn("speech.state");
    return root.wellFormed(env) && env.conf >= 1 && typeof env.body.state === "string" ? env : null;
  }

  // Jarvis began saying something after these words landed. Latched for
  // the reason SpeechState latches `heardAnswer`: `bus.latest()` holds one
  // frame per topic, so the `speaking` frame is gone the instant jv-voice
  // publishes the idle that follows it, and a derived reading would put
  // the line back on screen for the rest of the reply.
  property bool answering: false

  // `interrupted` counts, and must: jv-voice only ever publishes it out of
  // `speaking`, so one stamped after these words means the answer to THEM
  // began and was cut off — by the next thing the user said, whose own
  // final is already on its way here. An `interrupted` stamped BEFORE them
  // is the barge-in that produced this utterance in the first place, which
  // is why the comparison is against the transcript's `ts` and not against
  // the frame merely existing.
  onSpeechChanged: root.noteAnswerStarted()

  function noteAnswerStarted(): void {
    if (root.transcript === null || root.speech === null)
      return;
    if (root.speech.ts < root.transcript.ts)
      return;
    const named = root.speech.body.state;
    if (named === "speaking" || named === "interrupted")
      root.answering = true;
  }

  // --- the backstop ----------------------------------------------------

  // The newest utterance boundary jv-ears has published, or null. Only
  // `speech_end`: a `speech_start` is the beginning of the NEXT thing being
  // said and has no bearing on words already held. `conf` is fixed at 1.0
  // by the schema for this topic, so a frame claiming less is one that
  // disagrees with itself. Nothing here checks for an `utterance_id` —
  // `anchor` below has to COMPARE ids anyway, and a boundary carrying none
  // fails that comparison, so a guard here would be a second mechanism for
  // one rule and no test could tell it from the first.
  readonly property var boundaryFrame: {
    const env = root.frameOn("audio.vad");
    if (!root.wellFormed(env) || env.conf < 1)
      return null;
    return env.body.event === "speech_end" ? env : null;
  }

  // Latched, for the reason everything else in this file is latched: the
  // boundary arrives BEFORE the transcript that follows it, and
  // `bus.latest()` holds one frame per topic — ears' VAD runs continuously
  // (A4), so the next sound in the room replaces it. Derived, the anchor
  // would vanish the moment anybody spoke again.
  property var boundary: null

  onBoundaryFrameChanged: {
    if (root.boundaryFrame !== null)
      root.boundary = root.boundaryFrame;
  }

  // The frame whose age the hold is measured from: the end of the utterance
  // these words belong to, when we saw it, and the words themselves
  // otherwise. Never a boundary stamped AFTER the final it supposedly
  // preceded — such a pair cannot be ordered, and anchoring to the later of
  // the two would LENGTHEN the hold, which is the one direction this window
  // may not err in.
  readonly property var anchor: {
    if (root.transcript === null)
      return null;
    const b = root.boundary;
    if (b === null || b.ts > root.transcript.ts)
      return root.transcript;
    return root.stringOf(b, "utterance_id") === root.stringOf(root.transcript, "utterance_id") ? b : root.transcript;
  }

  // Set by the timer below, cleared whenever a new line arrives. A plain
  // property rather than a computed one because time passing is not a
  // property change: no binding re-evaluates just because a clock moved.
  property bool expired: false

  // Identity of the line being held: `seq` is per-publisher and strictly
  // increasing, so this changes exactly once per final frame.
  readonly property string transcriptKey: root.transcript === null ? "" : root.transcript.seq + "@" + root.transcript.ts

  onTranscriptKeyChanged: {
    // A different sentence: whatever we saw answering was answering the
    // last one. Re-checked immediately, because this line may already have
    // been overtaken by a frame that arrived before it did.
    root.answering = false;
    root.noteAnswerStarted();
    root.armHold();
  }
  onHoldSChanged: root.armHold()
  // A boundary that arrives out of order, after the transcript it precedes,
  // still gets to shorten the hold: by the rule above it can only ever be
  // older than the words, so re-arming here cannot extend anything and
  // cannot bring an expired line back (`armHold` recomputes what is left
  // and expires on the spot when that is nothing).
  onAnchorChanged: root.armHold()

  // One shot, armed only while a line is actually held, so a HUD nobody is
  // talking to runs no timer at all (§06: 0 fps when nothing is
  // happening).
  readonly property Timer hold: Timer {
    repeat: false
    onTriggered: root.expired = true
  }

  function armHold(): void {
    root.expired = false;
    if (root.transcript === null) {
      root.hold.running = false;
      return;
    }
    // Whatever is LEFT of the window, not the whole of it: a turn that
    // spent time in the ASR is already partway through its own. `ageOf` is
    // Infinity when the age is not knowable (no clock, no ts), which lands
    // here as "already over" — a line the HUD cannot time is one it must
    // not hold open forever.
    const left = root.holdS - root.ageOf(root.anchor);
    if (!(left > 0)) {
      root.hold.running = false;
      root.expired = true;
      return;
    }
    root.hold.interval = Math.max(1, Math.ceil(left * 1000));
    root.hold.restart();
  }

  // --- reading the bus, defensively ------------------------------------

  // The last frame on `topic`, but only while the bridge holds a live
  // subscription. A cached frame from a link that has since dropped
  // describes a machine we can no longer see.
  function frameOn(topic: string): var {
    if (!root.bus || !root.bus.linkUp || typeof root.bus.latest !== "function")
      return null;
    return root.bus.latest(topic);
  }

  function ageOf(envelope: var): real {
    return root.bus && typeof root.bus.ageOf === "function" ? root.bus.ageOf(envelope) : Infinity;
  }

  // A string field of the held line, or "". Read by TYPE rather than by
  // truthiness: a number is truthy and has no `.replace`, and a guard that
  // only checked for emptiness would throw inside a binding — where the
  // symptom is a warning nobody reads and a plate quietly missing a line.
  function stringOf(envelope: var, field: string): string {
    const v = envelope === null || !envelope.body ? null : envelope.body[field];
    return typeof v === "string" ? v : "";
  }

  // One paragraph. The plate wraps on its own width and elides when there
  // is more than a glance of it; what it must never do is have its layout
  // decided by a newline or a tab inside the sentence.
  function flatten(text: string): string {
    return text.replace(/\s+/g, " ").trim();
  }

  // The envelope floor: the schema version we were written against
  // (invariant 2 — a v2 body is not a v1 body), a numeric `ts` (without
  // one there is no age and so no backstop), a numeric `conf` (invariant
  // 4 — see the note at the top about why nothing else is done with it),
  // and a body.
  function wellFormed(envelope: var): bool {
    return !!envelope && envelope.v === 1 && typeof envelope.ts === "number" && typeof envelope.conf === "number" && !!envelope.body;
  }
}
