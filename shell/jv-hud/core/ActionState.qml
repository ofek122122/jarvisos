// ActionState — Jarvis reached into the machine and it did not work (A37).
//
// Invariant 3 gives exactly one process the right to change this computer,
// and until now the HUD could show the QUESTION jv-act asks before a
// destructive tool (A20) and never what came of it. So the one category of
// event the user has the most right to see — something acted on my machine
// on my behalf, and it failed — was the same dark corner as a calm,
// idle desktop. The spoken reply does eventually say so, in a sentence
// composed by a language model out of `output`; this says which tool and
// which error, in the words jv-act and the schema use, so the thing you
// read on screen is the thing you can grep for in the audit log.
//
// It answers one question — did the last thing Jarvis tried to do fail,
// and what was it — from three topics:
//
//   intent.action  (jv-brain)  the request: this is where the TOOL NAME is.
//   action.result  (jv-act)    the outcome: ok, and an error word if not.
//   speech.state   (jv-voice)  Jarvis starting to explain it — the exit.
//
// Three decisions shape the whole element:
//
// FAILURES ONLY. An action that worked needs no plate: the machine
// visibly doing the thing is the report that it was done, and a corner
// that lights up for every volume change is one nobody reads on the day
// it matters. That is HealthPlate's argument (A6) applied to actions
// instead of services, and it is what keeps §06's earned emptiness real.
//
// NEVER A TOOL WE CANNOT PROVE. `action.result` carries a `request_id`
// and no tool name — the name lives in the `intent.action` that asked —
// so the two have to be paired by id, and `bus.latest()` holds exactly
// one frame per topic, which may well belong to a different request by
// the time an outcome lands. A HUD that takes the name on faith would
// eventually tell you a lie about what touched your machine, which is
// strictly worse than the empty line it replaced. Unpaired failures are
// still reported; they are just reported without a name.
//
// NOT THE CONFIRMATION FLOW'S OUTCOMES. `denied` and `confirm_timeout`
// are how a confirmation ENDED, and A22 is an open question for a human:
// today ConfirmPlate vanishes identically whether you said no, said
// nothing, or ran out of time, and deciding what the screen should do
// about that is a deliberate call, not a side effect of this element.
// Both are passed over here — and passed over as NO NEWS, so a denial
// arriving after a real failure cannot silently take it off the screen.
//
// The latch is let go of in three ways, the same three HeardState uses
// (A26), because it is the same kind of claim — a fact about a turn that
// the bus no longer carries:
//
//   · Jarvis starts explaining. jv-brain is handed every action.result
//     and phrases it, so once you can hear the explanation the
//     explanation is the better report. A real signal, not a timer, which
//     is what keeps this out of the "on screen for a fixed duration"
//     territory A22 flagged as needing a human.
//   · a newer outcome. The next action is newer news about the same
//     machine — including a SUCCESS, because holding a failure under a
//     retry that worked describes a machine that is not the one in front
//     of you.
//   · the link dropping, and `holdS` as the backstop for a failure nobody
//     ever explains: a `jv act` run with nothing to speak, or a brain that
//     died between the tool and the sentence.
//
// On confidence (invariant 4): schemas/action.result.json and
// schemas/intent.action.json both fix envelope `conf` at 1.0. jv-act
// either did the thing or it did not, and a hedged outcome is not one —
// so an unhedged conf is part of the envelope floor here rather than
// something displayed.
//
// On privacy (invariant 7): `intent.action.args` carries whatever the
// tool was asked to operate on — a path, a search string, a window title
// — and `action.result.detail` is free text for logs. Neither is read by
// this element and neither reaches a screen; a tools gate keeps it that
// way. What is drawn is a registry tool name and one word out of a frozen
// enum, both of which are vocabulary rather than content.
import QtQuick

QtObject {
  id: root

  // Anything offering `linkUp`, `latest(topic)` and `ageOf(envelope)`:
  // the `Bus` singleton in production, a BusModel the tests drive by hand.
  // Consumer-only by construction — there is nothing to publish with.
  property var bus: null

  // How long a failure nobody explained stays readable. The same 30 s
  // HeardState holds a question for, and deliberately NOT pinned to it:
  // that one is "a turn may still be in flight", this one is "nobody is
  // coming back to tell you about this", and the two are free to be
  // answered differently by whoever looks at the screen. It is a backstop,
  // never the ordinary exit.
  property real holdS: 30.0

  // The error words this element is willing to put on screen: the frozen
  // enum of schemas/action.result.json, minus the confirmation flow's own
  // two (see the header). A word outside this list is one the reader
  // cannot look up, so the failure is reported without it rather than with
  // something a publisher invented.
  readonly property var reportableReasons: ["unknown_tool", "invalid_args", "capability_mismatch", "execution_failed", "timeout"]

  // How a confirmation ended. Not ours to report (A22) and not ours to
  // act on either — see `apply()`.
  readonly property var confirmOutcomes: ["denied", "confirm_timeout"]

  // --- the outputs ----------------------------------------------------

  // Is there a failure to show? The plate draws nothing whenever this is
  // false, which is the ordinary state of a machine whose last action
  // worked — and of one nobody has asked to do anything at all.
  readonly property bool failed: root.linked && root.failure !== null && !root.expired

  // The registry tool that failed — `app.launch` — verbatim, or "" when
  // the HUD never saw the intent that names it.
  readonly property string tool: root.failed ? root.failureTool : ""

  // Why, in schemas/action.result.json's own word, or "" when jv-act sent
  // none or sent one this element does not recognise.
  readonly property string reason: root.failed ? root.failureReason : ""

  // --- the failure we are holding --------------------------------------

  // The latched action.result envelope, or null. Plain properties: they
  // are a memory, not a reading, and every path that sets them is below.
  // The tool and the reason are resolved ONCE, at the moment the failure
  // is accepted, because both of their sources keep moving afterwards.
  property var failure: null
  property string failureTool: ""
  property string failureReason: ""

  // True only while the bridge holds a live subscription. Separate from
  // `frame` on purpose — a link that drops must forget the failure, while
  // a frame we merely cannot parse must not.
  readonly property bool linked: !!root.bus && root.bus.linkUp === true

  onLinkedChanged: {
    if (!root.linked)
      root.forget();
  }

  // The newest action.result we are willing to read, or null. Null covers
  // three different things — nothing there, a frame from a schema we were
  // not written against, and one missing a field the schema requires — and
  // `apply()` treats all of them the same way: as no news. Refusing to
  // read a frame is never the same as being told the machine is fine.
  readonly property var frame: {
    if (!root.linked || typeof root.bus.latest !== "function")
      return null;
    const env = root.bus.latest("action.result");
    if (!root.wellFormed(env))
      return null;
    const b = env.body;
    // The id is the only thread between an intent and its outcome; one
    // without it could never be attributed to anything. `ok` is what the
    // whole element turns on, and a missing one read as falsy would report
    // every unreadable frame as a failed action.
    if (typeof b.request_id !== "string" || b.request_id.length === 0)
      return null;
    return typeof b.ok === "boolean" ? env : null;
  }

  onFrameChanged: root.apply()

  function apply(): void {
    const env = root.frame;
    if (env === null)
      return; // a frame we cannot read is not an outcome
    const b = env.body;
    if (b.ok === true) {
      root.forget(); // the newest thing Jarvis did worked
      return;
    }
    if (typeof b.error === "string" && root.confirmOutcomes.indexOf(b.error) >= 0)
      return; // A22's question, not this element's — and not news either
    root.failure = env;
    root.failureTool = root.toolFor(b.request_id);
    root.failureReason = typeof b.error === "string" && root.reportableReasons.indexOf(b.error) >= 0 ? b.error : "";
    root.noteExplained();
  }

  function forget(): void {
    root.failure = null;
    root.failureTool = "";
    root.failureReason = "";
  }

  // The tool name the brain asked for, but ONLY if the intent still on the
  // bus is the one this outcome answers. `bus.latest()` holds one frame
  // per topic, and by the time a result lands that frame may belong to the
  // next request entirely — so the ids must match or there is no name.
  function toolFor(requestId: string): string {
    const env = root.frameOn("intent.action");
    if (!root.wellFormed(env))
      return "";
    const b = env.body;
    if (typeof b.request_id !== "string" || b.request_id !== requestId)
      return "";
    return typeof b.tool === "string" ? b.tool.trim() : "";
  }

  // --- has the explanation started? ------------------------------------

  // The latest speech.state we can read, or null. A state topic, so its
  // envelope conf is fixed at 1.0 by its schema.
  readonly property var speech: {
    const env = root.frameOn("speech.state");
    return root.wellFormed(env) && typeof env.body.state === "string" ? env : null;
  }

  onSpeechChanged: root.noteExplained()

  // Jarvis began saying something AFTER this failure landed. The
  // comparison is against the failure's own `ts` and not against a frame
  // merely existing, because a tool call in the middle of a streamed reply
  // leaves a `speaking` frame on the topic that is about the sentence
  // before the attempt. `interrupted` counts too: jv-voice only ever
  // publishes it out of `speaking`, so one stamped after the failure means
  // the explanation began and the user cut it off — it began either way.
  function noteExplained(): void {
    if (root.failure === null || root.speech === null)
      return;
    if (root.speech.ts < root.failure.ts)
      return;
    const named = root.speech.body.state;
    if (named === "speaking" || named === "interrupted")
      root.forget();
  }

  // --- the backstop ----------------------------------------------------

  // Set by the timer below, cleared whenever a new failure arrives. A
  // plain property rather than a computed one because time passing is not
  // a property change: no binding re-evaluates just because a clock moved.
  property bool expired: false

  // Identity of the failure being held: `seq` is per-publisher and
  // strictly increasing, so this changes exactly once per result frame.
  readonly property string failureKey: root.failure === null ? "" : root.failure.seq + "@" + root.failure.ts

  onFailureKeyChanged: root.armHold()
  onHoldSChanged: root.armHold()

  // One shot, armed only while a failure is actually held, so a HUD on a
  // machine nobody is acting on runs no timer at all (§06: 0 fps when
  // nothing is happening). Actions are rare and failures rarer; this is
  // idle almost always.
  readonly property Timer hold: Timer {
    repeat: false
    onTriggered: root.expired = true
  }

  function armHold(): void {
    root.expired = false;
    if (root.failure === null) {
      root.hold.running = false;
      return;
    }
    // Whatever is LEFT of the window, not the whole of it: a frame that
    // spent time in flight is already partway through its own. `ageOf` is
    // Infinity when the age is not knowable (no clock, no ts), which lands
    // here as "already over" — a line the HUD cannot time is one it must
    // not hold open forever.
    const left = root.holdS - root.ageOf(root.failure);
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
