// InstallState — the Windows app jv-compat could not finish installing
// (PLAN A52).
//
// A51 gave the HUD half of invariant 8: jv-guard's refusal, the one moment
// JarvisOS says NO to something its user asked for. The other half is what
// happens to the binaries it lets through — jv-compat builds a confined
// prefix and runs the installer inside it, silently, minutes at a time,
// and when that goes wrong the only report is an exit code in whatever
// terminal started it. `jv-compat install` is a fire-and-forget command;
// the user is somewhere else by then, and the HUD — which is on top of
// every window — showed the same empty corner it shows for a machine
// nobody has asked to install anything.
//
// It answers ONE question, and the wording is exactly what one frame can
// prove: **did the last install jv-compat attempted FAIL, and which app
// was it.** One topic, one frame:
//
//   compat.install  (jv-compat)  event, app slug, and the installer hash.
//
// Four decisions shape it:
//
// FAILURES ONLY, AND THEREFORE NO PROGRESS INDICATOR. `compat.install`
// carries the whole lifecycle — fingerprinted, screened, prefix_created,
// installed — and an install is the one thing on this bus that takes
// MINUTES, so "what is jv-compat doing right now" is a real question and
// a progress indicator is a shape §06 does not have yet. That is a
// deliberate call for a human to make (A52), not a side effect of this
// element, so nothing here anticipates it: the happy path draws NOTHING,
// the way an action that worked draws nothing (A37) and a service that is
// well draws nothing (A6). An install that finishes is reported by the app
// being on the machine.
//
// NOT `blocked`. That event is how the SCREENING ended, and GuardPlate
// (A51) already draws it from jv-guard's own `guard.verdict`, joined to
// this lifecycle by the same sha256. Two plates for one refusal would be
// the HUD saying the same thing twice in two vocabularies, and the one
// that reads the screener directly is the better witness. Passed over as
// NO NEWS, ActionState's rule for the confirmation outcomes it declines:
// a refusal landing after a real failure must not silently take it off
// the screen.
//
// NOT THE ERROR TEXT. `compat.install.error` on a `failed` frame is the
// last 500 bytes of the confined installer's own stdout — free text
// written by a Windows binary invariant 8 says outright is untrusted,
// likely carrying paths out of this filesystem. It is for the log and the
// spoken answer. This is the same line ActionPlate draws at
// `action.result.detail` and GuardPlate at the scanner's `reasons`, and
// here it is drawn harder: the element does not expose the field at all,
// so no plate can render what it never received.
//
// THE SLUG MUST LOOK LIKE ONE. `app` is required by the schema and is the
// prefix DIRECTORY name — jv-compat builds it out of the installer's file
// name through a lowercase-and-hyphens sieve, so what arrives is already
// an identifier rather than an attacker's string. This element does not
// take that on faith (a frame is what it is, and the HUD trusts no
// publisher's sanitising): a slug is drawn only if it still has the shape
// jv-compat claims for it — one line, no spaces, no separators, short
// enough to be a directory name. Anything else is REFUSED rather than
// repaired, because a truncated or scrubbed slug is a different app's
// name, and the frame's sha256 prefix is shown instead — the identity
// jv-guard's log uses and the only thing about a file that may ever leave
// this machine (invariant 7).
//
// The latch is let go of in three ways:
//
//   · a newer lifecycle event that is not itself a failure. The question
//     is about the LAST install attempted, so a `fingerprinted` means the
//     user has moved on to another binary and an `installed` means the
//     next one worked — GuardState's rule (the last binary SCREENED) and
//     ActionState's (a retry that worked is newer news about the same
//     machine).
//   · the link dropping. A cached failure from a bus we can no longer see
//     is a claim about a machine we can no longer watch.
//   · `holdS`, the backstop — and, as in GuardState, the ORDINARY exit
//     here rather than a last resort. There is deliberately no "Jarvis
//     started explaining" exit: an install is not part of a voice turn
//     (the trigger is `jv-compat install` at a terminal), so a `speaking`
//     frame that lands after one is almost certainly about something
//     else, and treating it as the explanation would take the failure off
//     the screen for an unrelated sentence.
//
// On confidence (invariant 4): schemas/compat.install.json fixes envelope
// `conf` at 1.0. An installer either exited non-zero or it did not; a
// hedged lifecycle event is not a thing jv-compat publishes, so an
// unhedged `conf` is part of the envelope floor here rather than
// something displayed.
import QtQuick

QtObject {
  id: root

  // Anything offering `linkUp`, `latest(topic)` and `ageOf(envelope)`:
  // the `Bus` singleton in production, a BusModel the tests drive by hand.
  // Consumer-only by construction — there is nothing to publish with.
  property var bus: null

  // How long a failed install stays readable. The same 30 s ActionState,
  // HeardState and GuardState use, and deliberately not pinned to any of
  // them: this one is "nobody is coming back to tell you about this", and
  // whoever looks at the screen on ares is free to answer it differently.
  property real holdS: 30.0

  // The events that mean the failure being held is no longer the last
  // thing jv-compat attempted: a new install starting, or one finishing.
  // An ALLOW-LIST out of the frozen enum in schemas/compat.install.json,
  // and the reason this element needs no "is that a word I know" gate
  // above it: the only other thing `apply()` acts on is the exact string
  // `failed`, so a word jv-compat invents tomorrow does nothing at all —
  // it cannot put an unlookuppable label on screen and cannot clear a
  // real failure either. That is a property of these two lists rather
  // than of a check somewhere else, which is the point: a guard no test
  // can tell the presence of is a guard nothing is holding up.
  // `blocked` is deliberately in neither list — see the header.
  readonly property var clearingEvents: ["fingerprinted", "screened", "prefix_created", "installed"]

  // How long a prefix directory name may be before this element stops
  // believing it is one. Refused, never truncated: half a slug is another
  // app's name.
  readonly property int maxSlugChars: 40

  // What a prefix directory name looks like: one line, starting with a
  // character you can see, and made only of the pieces a package name is
  // made of. Deliberately wider than jv-compat's own `[a-z0-9-]` sieve
  // (this element is written against the schema, not against one
  // publisher's regex) and far narrower than "a string": a slug with a
  // slash, a space, a newline or a bidirectional override in it is not a
  // directory name, whoever published it.
  readonly property var slugShape: /^[A-Za-z0-9][A-Za-z0-9._+-]*$/

  // --- the outputs ----------------------------------------------------

  // Is there a failed install to show? The plate draws nothing whenever
  // this is false, which is the state of every machine that has not been
  // handed a Windows installer — that is to say, almost every machine,
  // almost always.
  readonly property bool failed: root.linked && root.failure !== null && !root.expired

  // The app's slug — `notepad-plus-plus` — or "" when the frame carried
  // nothing with the shape of one.
  readonly property string app: root.failed ? root.failureApp : ""

  // The first 12 hex of the installer's sha256, which is what the plate
  // shows when there is no usable slug. "" when the frame's hash is not
  // hex we can shorten honestly.
  readonly property string fingerprint: root.failed ? root.failureSha : ""

  // --- the failure we are holding --------------------------------------

  // The latched compat.install envelope, or null. Plain properties: they
  // are a memory, not a reading, and every path that sets them is below.
  // Both strings are resolved ONCE, at the moment the failure is accepted,
  // so what is on screen cannot change under a reader while the same
  // failure is being shown.
  property var failure: null
  property string failureApp: ""
  property string failureSha: ""

  // True only while the bridge holds a live subscription. Separate from
  // `frame` on purpose — a link that drops must forget the failure, while
  // a frame we merely cannot parse must not.
  readonly property bool linked: !!root.bus && root.bus.linkUp === true

  onLinkedChanged: {
    if (!root.linked)
      root.forget();
  }

  // The newest compat.install we are willing to read, or null. Null covers
  // three things — nothing there, a frame from a schema version we were
  // not written against, and one missing a field the schema requires (the
  // hash that identifies the installer, or the event that says what
  // happened to it) — and `apply()` treats all of them as no news.
  // Refusing to read a frame is never the same as being told an install is
  // going fine.
  readonly property var frame: {
    if (!root.linked || typeof root.bus.latest !== "function")
      return null;
    const env = root.bus.latest("compat.install");
    if (!root.wellFormed(env))
      return null;
    const b = env.body;
    if (typeof b.sha256 !== "string" || b.sha256.length === 0)
      return null;
    if (typeof b.event !== "string" || b.event.length === 0)
      return null;
    return env;
  }

  onFrameChanged: root.apply()

  function apply(): void {
    const env = root.frame;
    if (env === null)
      return; // a frame we cannot read is not an install
    const b = env.body;
    if (b.event !== "failed") {
      if (root.clearingEvents.indexOf(b.event) >= 0)
        root.forget(); // a newer install is under way, or one finished
      // Everything else is NO NEWS: `blocked`, which is GuardPlate's
      // story, and any word a later jv-compat invents, which this element
      // was not written against. Never an all-clear — that would silently
      // take a real failure off the screen.
      return;
    }
    root.failure = env;
    root.failureApp = root.plainSlug(b.app);
    root.failureSha = root.shortSha(b.sha256);
  }

  function forget(): void {
    root.failure = null;
    root.failureApp = "";
    root.failureSha = "";
  }

  // --- the slug, believed only if it looks like one ---------------------

  // The prefix directory name, or "" if what arrived is not one. Nothing
  // here repairs a bad slug (see the header): a name is an identity, and
  // an identity that had to be edited before it could be drawn is not the
  // identity of anything. The caller falls back to the hash.
  function plainSlug(app: var): string {
    if (typeof app !== "string" || app.length === 0 || app.length > root.maxSlugChars)
      return "";
    return root.slugShape.test(app) ? app : "";
  }

  // The first 12 hex digits of the installer's hash, lowercased so two
  // reports of the same file read the same. A hash that is not at least
  // that much hex is not one this element will shorten: a truncated
  // something-else looks exactly like a sha256 prefix and would be the one
  // identity on this plate that cannot be looked up.
  function shortSha(sha: string): string {
    return /^[0-9a-fA-F]{12}/.test(sha) ? sha.slice(0, 12).toLowerCase() : "";
  }

  // --- the backstop ----------------------------------------------------

  // Set by the timer below, cleared whenever a new failure arrives. A
  // plain property rather than a computed one because time passing is not
  // a property change: no binding re-evaluates just because a clock moved.
  property bool expired: false

  // Identity of the failure being held: `seq` is per-publisher and
  // strictly increasing, so this changes exactly once per failed frame.
  readonly property string failureKey: root.failure === null ? "" : root.failure.seq + "@" + root.failure.ts

  onFailureKeyChanged: root.armHold()
  onHoldSChanged: root.armHold()

  // One shot, armed only while a failure is actually held, so a HUD on a
  // machine that installs nothing runs no timer at all (§06: 0 fps when
  // nothing is happening). Like GuardPlate's, this is one of the rarest
  // plates in the stack: it needs somebody to hand Jarvis a Windows
  // installer AND that installer to fail inside its prefix.
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
