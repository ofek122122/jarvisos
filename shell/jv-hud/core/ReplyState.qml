// ReplyState — the answer you heard was not the whole answer (A71).
//
// `schemas/brain.response.json` has carried a three-word enum since v1 —
// `stop`, `length`, `error` — and until now the HUD read the frame only
// to learn that a turn had ENDED (SpeechState closes its THINKING window
// on it, A12) and never how. Two of those three words describe a turn
// that did not deliver what was asked for, and exactly one of them has no
// other route to a screen:
//
//   stop   the ordinary case. Nothing to say, and §06's earned emptiness
//          means nothing is what gets said.
//   error  jv-brain could not answer at all. Already visible: the same
//          `except` block that publishes this frame publishes a
//          `sys.health` `degraded` with the failure in its notes, one
//          `await` later, and HealthPlate draws it. Reporting it a second
//          time, in a second colour, in the same corner, about one event,
//          is A62's confusion manufactured on purpose — so this element
//          passes over it. Not as no-news, though: see `apply()`.
//   length the context or token limit was hit and THE TEXT IS TRUNCATED,
//          in the schema's own words. Nothing anywhere says so. jv-brain
//          speaks the reply sentence-by-sentence as it streams, so the
//          user has already heard it stop mid-thought; no service calls
//          it a fault, so no heartbeat changes; and the reply that
//          arrives is a well-formed frame on a healthy machine. The one
//          outcome of a turn that is invisible, and on ares the LIKELY
//          one — the brain runs on a CPU rung with a 2048-token context
//          (invariant 6's ladder, B39/B41) against a conversation budget
//          sized for rung 0 (docs/optimization-backlog.md §4).
//
// So this element answers one question — was the last reply cut off — and
// says nothing at any other time.
//
// A CLAIM ABOUT A TURN, NOT A READING. `bus.latest()` holds one frame per
// topic, so a derived answer would keep the plate up from the moment a
// truncated reply landed until the NEXT one did, which on a machine
// nobody talks to is forever. It is latched on the frame's edge and let
// go of the way HeardState and ActionState let go of theirs — on real
// signals, plus a backstop:
//
//   · a newer brain.response that is not `length`. The next turn is newer
//     news about the same brain, including a complete one: holding "your
//     answer was cut off" over a reply that arrived whole describes a
//     conversation that is not the one you are having. `error` clears it
//     for the same reason — it is a NEWER TURN, even though this element
//     will not draw it.
//   · the user starting again — a wake, or a `brain.request` — stamped
//     after the truncated reply. At that point the cut-off answer is the
//     thing being replaced rather than the thing being read.
//   · the link dropping, and `holdS` as the backstop.
//
// The backstop is more load-bearing here than it is next door, and that
// is worth saying plainly rather than inheriting quietly: ActionState's
// exit is Jarvis explaining the failure out loud, and nobody is ever
// coming to explain this one. jv-brain does not know its reply was
// truncated in any way it says out loud, and the frozen enum is the only
// place the fact exists. So for a user who asks one question and walks
// away, the timer IS the exit — which is A22's "on screen for a fixed
// duration" question, and the reason this element holds for the same
// 30 s HeardState holds a question for rather than inventing a number.
//
// WHAT IS DELIBERATELY NOT AN EXIT: `speech.state`. ActionState leaves
// when jv-voice starts speaking, because jv-brain is handed every
// action.result and phrases it. Nothing phrases this. Worse, the frame
// would be actively misleading — brain.response is published AFTER the
// stream closes, while jv-voice is very often still working through the
// sentences it was handed, so a `speaking` stamped after the truncation
// is the truncated reply still being read out. Leaving on it would take
// the plate down while the user is still listening to the thing it is
// about.
//
// On confidence (invariant 4): schemas/brain.response.json fixes envelope
// `conf` at 1.0 in v0 ("no self-assessment yet"), so an unhedged conf is
// part of the envelope floor here rather than something displayed.
//
// On privacy (invariant 7): the reply TEXT never reaches a pixel. It is
// read for exactly one thing — the schema says an empty string is allowed
// "only with finish_reason=error", so a `length` with no text is a frame
// contradicting its own schema, and this element refuses it rather than
// announcing that something which was never said got cut off. What is
// drawn is one word out of a frozen enum.
import QtQuick

QtObject {
  id: root

  // Anything offering `linkUp`, `latest(topic)` and `ageOf(envelope)`:
  // the `Bus` singleton in production, a BusModel the tests drive by hand.
  // Consumer-only by construction — there is nothing to publish with.
  property var bus: null

  // How long a truncation nobody replaces stays readable. The same 30 s
  // HeardState holds a question for, and deliberately not pinned to it:
  // see the header on why this one is the ordinary exit rather than a
  // backstop, and on why that is A22's question and not this element's.
  property real holdS: 30.0

  // The one `finish_reason` this element draws. A list of one, written as
  // a list because the argument in the header is about which of the three
  // frozen words reach a screen, and the next reader deserves to see the
  // set rather than an `=== "length"` with a paragraph above it.
  readonly property var reportableReasons: ["length"]

  // --- the outputs ----------------------------------------------------

  // Was the last reply cut off? The plate draws nothing whenever this is
  // false, which is the state of every machine whose brain finished its
  // sentence — and of every machine nobody has asked anything.
  readonly property bool truncated: root.linked && root.cut !== null && !root.expired

  // Why, in schemas/brain.response.json's own word, or "" when there is
  // nothing to say. Always `length` today; read off the latched frame
  // rather than written as a constant, so a second reportable word would
  // arrive on screen instead of arriving as this one.
  readonly property string reason: root.truncated ? root.cutReason : ""

  // --- the truncation we are holding -----------------------------------

  // The latched brain.response envelope, or null. Plain properties: they
  // are a memory, not a reading, and every path that sets them is below.
  property var cut: null
  property string cutReason: ""

  // True only while the bridge holds a live subscription. Separate from
  // `frame` on purpose — a link that drops must forget the truncation,
  // while a frame we merely cannot parse must not.
  readonly property bool linked: !!root.bus && root.bus.linkUp === true

  onLinkedChanged: {
    if (!root.linked)
      root.forget();
  }

  // The newest brain.response we are willing to read, or null. Null covers
  // three different things — nothing there, a frame from a schema we were
  // not written against, and one missing a field the schema requires — and
  // `apply()` treats all of them as NO NEWS. Refusing to read a frame is
  // never the same as being told the reply arrived whole.
  readonly property var frame: {
    if (!root.linked || typeof root.bus.latest !== "function")
      return null;
    const env = root.bus.latest("brain.response");
    if (!root.wellFormed(env))
      return null;
    const b = env.body;
    // Both fields are `required` in the frozen schema. `finish_reason` is
    // what the whole element turns on; `text` is what makes a truncation
    // a truncation (see the header).
    if (typeof b.finish_reason !== "string" || typeof b.text !== "string")
      return null;
    return env;
  }

  onFrameChanged: root.apply()

  function apply(): void {
    const env = root.frame;
    if (env === null)
      return; // a frame we cannot read is not a reply
    const b = env.body;
    if (root.reportableReasons.indexOf(b.finish_reason) < 0) {
      root.forget(); // a newer turn, however it ended
      return;
    }
    if (b.text.length === 0) {
      // The schema allows an empty reply only with `error`. A `length`
      // with nothing in it did not cut anything off, and a plate saying
      // so would be a claim about words the user never heard.
      root.forget();
      return;
    }
    root.cut = env;
    root.cutReason = b.finish_reason;
    // The wake or the request may already be newer than the reply they
    // are being compared against: jv-voice is usually still working
    // through the sentences jv-brain streamed, so a barge-in lands after
    // the frame that closed the turn. Checked here as well as on their
    // own edges, or a truncation the user had already moved past would
    // arrive on screen and sit there for the whole backstop.
    root.noteAsked();
  }

  function forget(): void {
    root.cut = null;
    root.cutReason = "";
  }

  // --- has the user moved on? ------------------------------------------

  // The user starting again: the wake word firing, or a `brain.request`
  // arriving from whatever asked (`jv ask`, onboarding). Either one,
  // stamped after the truncated reply, means the cut-off answer is being
  // replaced rather than read.
  readonly property var wake: root.frameOn("audio.wake")
  readonly property var request: root.frameOn("brain.request")

  onWakeChanged: root.noteAsked()
  onRequestChanged: root.noteAsked()

  function noteAsked(): void {
    if (root.cut === null)
      return;
    if (root.startedAfter(root.wake) || root.startedAfter(root.request))
      root.forget();
  }

  // A frame that is readable AND newer than the truncation. The envelope
  // floor is the same one the reply goes through: a frame this element
  // would refuse to read is not a frame it may act on either.
  function startedAfter(envelope: var): bool {
    return root.wellFormed(envelope) && envelope.ts >= root.cut.ts;
  }

  // --- the backstop ----------------------------------------------------

  // Set by the timer below, cleared whenever a new truncation arrives. A
  // plain property rather than a computed one because time passing is not
  // a property change: no binding re-evaluates just because a clock moved.
  property bool expired: false

  // Identity of the reply being held: `seq` is per-publisher and strictly
  // increasing, so this changes exactly once per response frame.
  readonly property string cutKey: root.cut === null ? "" : root.cut.seq + "@" + root.cut.ts

  onCutKeyChanged: root.armHold()
  onHoldSChanged: root.armHold()

  // One shot, armed only while a truncation is actually held, so a HUD on
  // a machine whose replies all finish runs no timer at all (§06: 0 fps
  // when nothing is happening).
  readonly property Timer hold: Timer {
    repeat: false
    onTriggered: root.expired = true
  }

  function armHold(): void {
    root.expired = false;
    if (root.cut === null) {
      root.hold.running = false;
      return;
    }
    // Whatever is LEFT of the window, not the whole of it: a frame that
    // spent time in flight is already partway through its own. `ageOf` is
    // Infinity when the age is not knowable (no clock, no ts), which lands
    // here as "already over" — a line the HUD cannot time is one it must
    // not hold open forever.
    const left = root.holdS - root.ageOf(root.cut);
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

  // The envelope floor: the schema version we were written against
  // (invariant 2 — a v2 body is not a v1 body), a numeric `ts` (without
  // one there is no age and so no backstop), an unhedged `conf` (see the
  // header), and a body.
  function wellFormed(envelope: var): bool {
    return !!envelope && envelope.v === 1 && typeof envelope.ts === "number" && envelope.conf >= 1 && !!envelope.body;
  }
}
