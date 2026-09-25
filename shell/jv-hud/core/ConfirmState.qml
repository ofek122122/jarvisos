// ConfirmState — is Jarvis waiting on a yes or no? (A20)
//
// Invariant 3: only jv-act mutates the machine, and every destructive tool
// stops and asks first. jv-act speaks that question through jv-voice and
// opens a window (15 s, and it says so in the frame); the answer comes back
// from whoever heard the user, and silence is a no. Until now the screen
// said nothing at all during that window — so a question you did not hear,
// or heard half of over music, was answered by a timeout you never knew was
// running. This element is the readable copy of the question, and nothing
// more than that.
//
// It is a CONSUMER, structurally and deliberately. It cannot answer, and
// neither can the plate that draws it: the HUD surface has an empty input
// region and takes no keyboard (invariant 10), so there is no path from
// these pixels to an authorization. The answer is spoken, or typed into
// `jv confirm`. A HUD that could grant a destructive action would be a
// second actuator, which invariant 3 does not have a word for.
//
// Where it comes from — one topic, both directions:
//
//   action.confirm kind=request  (jv-act)  a question is on the table.
//   action.confirm kind=answer   (jv-act   it has been answered, by voice,
//                                 or `jv`)  by the CLI, or by the window
//                                          closing (answered_by=timeout).
//
// Which is why this reads the topic rather than one publisher on it: the
// frame that ENDS a question does not always come from the service that
// asked it.
//
// The request has to be LATCHED rather than derived, and that is forced by
// the bus: `bus.latest()` keeps exactly one frame per topic, and the answer
// lands on the same topic as the request. The instant anything answers, the
// question is gone from the bus — so a derived "something is pending" would
// see the question only in the moment it arrived and be blind to it for the
// rest of its life. What is remembered here is an observation the bus no
// longer carries, which is exactly what a latch is for (the same reason
// SpeechState latches `heardAnswer`).
//
// A latch has to be let go of, and there are three ways:
//
//   · an answer naming THIS request_id. Not any answer — jv-act keeps a
//     single outstanding slot today, but the HUD is not the thing that
//     enforces that, and closing on somebody else's answer would blank a
//     live question.
//   · the link dropping. A question latched from a bus we can no longer
//     see describes a machine we can no longer see, and the window has
//     very likely closed while we were not looking.
//   · the window running out, which is the backstop for a jv-act that died
//     mid-question and will never publish the answer that normally ends
//     this. The window is the one jv-act DECLARED in the request (A14's
//     rule: the service that enforces a budget states it and the HUD reads
//     it, rather than keeping a copy that can drift). `windowFallbackS` is
//     for a request that declares none — a ceiling on how long the HUD is
//     willing to assert a question whose end it may have missed, and it
//     mirrors no service's constant on purpose.
//
// Everything else is refused rather than guessed at, and refusing is never
// the same as being answered: a frame this cannot read leaves a pending
// question exactly where it was.
//
// Of those three, exactly one is NEWS — an answer frame says what the
// machine decided about a destructive tool, and until A79 that was thrown
// away with the question (`granted` was the one body field of the frozen
// schema nothing here read). So the ending is latched too, beside the
// question: what was decided, by which route, and about which tool. The
// reading half only — what a HUD should DRAW when a question ends, and for
// how long, is a §06 decision and a human's (A22).
import QtQuick

QtObject {
  id: root

  // Anything offering `linkUp`, `latest(topic)` and `ageOf(envelope)`:
  // the `Bus` singleton in production, a BusModel the tests drive by hand.
  // Consumer-only by construction — there is nothing to publish with.
  property var bus: null

  // How long the HUD keeps asking a question that declared no window of
  // its own. Unlike the declared one this mirrors nothing: it is a policy
  // about how long we assert a window we cannot see the end of. jv-act's
  // real window is well under it, and jv-act's answer frame — which it
  // publishes even on timeout — normally ends the question long before.
  property real windowFallbackS: 30.0

  // --- the outputs ----------------------------------------------------

  // Is there a question on the table right now? The plate draws nothing
  // whenever this is false, which is the ordinary state of the machine.
  readonly property bool pending: root.linked && root.request !== null && !root.expired

  // The intent.action awaiting an answer, for the log and for anyone
  // correlating this with `jv act-log`.
  readonly property string requestId: root.textOf("request_id")

  // jv-act's own words, verbatim — the question the user is HEARING. A
  // paraphrase would be a second, different question, and the one thing
  // this element must not do is disagree with the voice. Empty when the
  // request carried none: `summary` is optional in the frozen schema, and
  // the fact that something destructive is waiting on you survives the
  // loss of the words.
  readonly property string summary: root.textOf("summary")

  // The tool that will run if the answer is yes, in the name jv-act
  // registers it under. Optional in the schema, so possibly empty.
  readonly property string tool: root.textOf("tool")

  // How long the answer window is, as this request declared it — or the
  // HUD's own ceiling when it declared nothing usable.
  readonly property real windowS: root.windowOf(root.request)

  // --- how the last question ENDED (A79) ------------------------------
  //
  // `pending` going false is three different endings wearing one face: the
  // user said yes, the user said no (or said nothing and jv-act denied it
  // for them), or we stopped being able to tell. The most consequential
  // thing this topic carries is which of those it was, and it used to
  // leave the screen with the question.
  //
  // What this will and will not say:
  //
  //   · only about a question this element was HOLDING. An answer whose
  //     request_id we never saw asked is a verdict out of nowhere; the
  //     rule that keeps a stranger's answer from blanking a live question
  //     keeps it from writing an ending for one.
  //   · only from an answer FRAME. A window that ran out on our side ends
  //     the asking and settles nothing — `expired` is the HUD's own
  //     backstop for a jv-act that died mid-question, not news from the
  //     machine. An answer that lands after we let go is still an ending,
  //     and is taken: it is what really happened to a question the user
  //     was shown.
  //   · `granted` decides, and nothing else does. See `outcome`.
  //
  // It is forgotten when a new question arrives (the live one is the news,
  // and a verdict readable beside an unanswered question would be attached
  // to the wrong one) and when the link drops (a decision latched off a
  // bus we can no longer see). Nothing else forgets it, because "how long
  // does an ending stay up" is precisely what A22 is for.

  // "" until something is answered; then "granted", "denied", or
  // "unknown" for an answer whose verdict we could not read.
  //
  // `granted` is optional in the frozen schema, and an answer without a
  // usable one is `unknown` even when `answered_by` is "timeout" — the
  // schema's prose does say a timeout is a denial, and jv-act publishes
  // `granted: false` when it times out, which is exactly why reading the
  // denial off the ROUTE here would be a second copy of a rule the frame
  // already states (A14). Two copies are what drift is made of, and this
  // one would be guessing at the outcome of a destructive tool.
  readonly property string outcome: {
    if (root.answer === null)
      return "";
    const g = root.answer.env.body.granted;
    if (typeof g !== "boolean")
      return "unknown";
    return g ? "granted" : "denied";
  }

  // Which route the answer came in by: "voice", "cli", "timeout", or ""
  // for an answer naming a route the frozen schema does not have. A
  // different question from `outcome` — "you said no" and "you were not
  // there" are both denials and a reader wants them apart — and losing a
  // word we do not recognise must not lose the verdict with it.
  readonly property string answeredBy: {
    if (root.answer === null)
      return "";
    const by = root.answer.env.body.answered_by;
    return by === "voice" || by === "cli" || by === "timeout" ? by : "";
  }

  // The question that ended. Kept rather than read back off `request`,
  // because by now there is no pending question and everything readable
  // through `textOf` is gated on there being one — and an ending nobody
  // can attach to a tool is not worth drawing.
  readonly property string answeredRequestId: root.answer === null ? "" : root.answer.env.body.request_id
  readonly property string answeredTool: root.askedTextOf("tool")
  readonly property string answeredSummary: root.askedTextOf("summary")

  // --- the question we are holding ------------------------------------

  // The latched request envelope, or null. A plain property: it is a
  // memory, not a reading, and every path that sets it is below.
  property var request: null

  // The latched ending: `{ env, request }` — the answer frame and the
  // question it closed — or null. A plain property for the same reason
  // `request` is one, and holding both halves because the answer frame
  // carries neither `tool` nor `summary` (request-only in the schema).
  property var answer: null

  // True only while the bridge holds a live subscription. Separate from
  // `frame` on purpose — a link that drops must forget the question, while
  // a frame we merely cannot parse must not.
  readonly property bool linked: !!root.bus && root.bus.linkUp === true

  onLinkedChanged: {
    if (!root.linked) {
      root.request = null;
      root.answer = null;
    }
  }

  // The newest action.confirm we are willing to read, or null. Null covers
  // two different things — nothing there, and something unreadable — and
  // `apply()` treats both the same way: as no news.
  readonly property var frame: {
    if (!root.linked || typeof root.bus.latest !== "function")
      return null;
    const env = root.bus.latest("action.confirm");
    if (!root.wellFormed(env))
      return null;
    const b = env.body;
    // The id is how an answer will find this question; one without an id
    // is a question that could never be closed.
    if (typeof b.request_id !== "string" || b.request_id.length === 0)
      return null;
    return b.kind === "request" || b.kind === "answer" ? env : null;
  }

  onFrameChanged: root.apply()

  function apply(): void {
    const env = root.frame;
    if (env === null)
      return; // a frame we cannot read is not an answer
    if (env.body.kind === "request") {
      // Newest wins: a second question is the live one, and how the last
      // one ended stops being the news the moment there is another.
      root.request = env;
      root.answer = null;
      return;
    }
    if (root.request !== null && root.request.body.request_id === env.body.request_id) {
      root.answer = {
        "env": env,
        "request": root.request
      };
      root.request = null;
    }
  }

  // --- the window ------------------------------------------------------

  // Set by the timer below, cleared whenever a question arrives. A plain
  // property rather than a computed one because time passing is not a
  // property change: no binding re-evaluates just because a clock moved.
  property bool expired: false

  // Identity of the question being held: `seq` is per-publisher and
  // strictly increasing, so this changes exactly once per request frame.
  readonly property string requestKey: root.request === null ? "" : root.request.seq + "@" + root.request.ts

  onRequestKeyChanged: root.armExpiry()
  onWindowFallbackSChanged: root.armExpiry()

  // One shot, armed only while a question is actually open, so a HUD with
  // nothing to ask runs no timer at all (§06: 0 fps when nothing is
  // happening). Confirmations are rare; this is idle almost always.
  readonly property Timer expiry: Timer {
    repeat: false
    onTriggered: root.expired = true
  }

  function armExpiry(): void {
    root.expired = false;
    if (root.request === null) {
      root.expiry.running = false;
      return;
    }
    // Whatever is LEFT of the window, not the whole of it: a frame that
    // spent time in flight is already partway through its own window, and
    // arming the full one would keep asking after jv-act had timed out.
    // `ageOf` is Infinity when the age is not knowable (no clock, no ts),
    // which lands here as "already over" — a question the HUD cannot time
    // is one it must not hold open forever.
    const left = root.windowOf(root.request) - root.ageOf(root.request);
    if (!(left > 0)) {
      root.expiry.running = false;
      root.expired = true;
      return;
    }
    root.expiry.interval = Math.max(1, Math.ceil(left * 1000));
    root.expiry.restart();
  }

  // The window this request declared, or the HUD's ceiling. Read through a
  // function rather than off the `windowS` binding so that arming never
  // depends on which of two bindings re-evaluated first.
  function windowOf(envelope: var): real {
    const w = envelope === null || !envelope.body ? NaN : envelope.body.window_s;
    return typeof w === "number" && isFinite(w) && w > 0 ? w : root.windowFallbackS;
  }

  // --- reading the frame, defensively ----------------------------------

  // A string field of the pending question, or "". Gated on `pending` so
  // that nothing is ever drawn from a question that has been answered, has
  // expired, or came off a bus we have since lost.
  function textOf(field: string): string {
    if (!root.pending)
      return "";
    const v = root.request.body[field];
    return typeof v === "string" ? v : "";
  }

  // A string field of the QUESTION that ended, or "". `tool` and `summary`
  // are request-only in the frozen schema, so this reads the request half
  // of the latch; the answer frame carries neither.
  function askedTextOf(field: string): string {
    if (root.answer === null)
      return "";
    const v = root.answer.request.body[field];
    return typeof v === "string" ? v : "";
  }

  function ageOf(envelope: var): real {
    return root.bus && typeof root.bus.ageOf === "function" ? root.bus.ageOf(envelope) : Infinity;
  }

  // The envelope floor: the schema version we were written against
  // (invariant 2), a numeric `ts` — without one there is no age and so no
  // window — a body, and an unhedged `conf`. schemas/action.confirm.json
  // fixes conf at 1.0: a confirmation handshake that is unsure of itself
  // is not one (invariant 4).
  function wellFormed(envelope: var): bool {
    return !!envelope && envelope.v === 1 && typeof envelope.ts === "number" && envelope.conf >= 1 && !!envelope.body;
  }
}
