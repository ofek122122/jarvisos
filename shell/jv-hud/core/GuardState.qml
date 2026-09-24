// GuardState — a program was handed to this machine and refused (A51).
//
// Invariant 8 says Windows binaries are untrusted by default and that
// `jv-guard` screens every one of them before `jv-compat` builds a prefix
// for it. That screening is the only place in JarvisOS where the machine
// says NO to something the user asked for, and until now it said so
// nowhere the user looks: jv-guard publishes `guard.verdict`, jv-compat
// fails closed on anything that is not clean, and the HUD — which is on
// top of every window — showed the same empty corner it shows for a
// machine nobody has asked to install anything.
//
// It answers ONE question, and the wording matters because it is exactly
// what can be proven from one frame: **was the last binary jv-guard
// screened refused, and which file was it.** Not "is anything on this disk
// dangerous" (jv-guard screens what it is handed, nothing more), and not
// "is that install still running" (that is jv-compat's lifecycle on
// another topic, and this element does not read it).
//
// One topic, one frame:
//
//   guard.verdict  (jv-guard)  sha256, verdict, and the path it screened.
//
// Four decisions shape it:
//
// REFUSALS ONLY. `clean` draws nothing. The install proceeding IS the
// report that the binary passed, and a corner that lights up for every
// screened file is one nobody reads on the day it matters — HealthPlate's
// argument (A6) and ActionPlate's (A37), applied to the screener.
//
// NOT THE REASONS. `guard.verdict.reasons` is where "matched ClamAV
// signature X" lives, and its own schema says those are "spoken on
// request". That is a deliberate editorial line and this element keeps
// it: the screen says a file was refused and names the file, and WHY is a
// question you ask out loud. It is also the one field on this topic whose
// text comes from a scanner rather than from a frozen enum — the same
// argument ActionPlate makes for reading `error` and never `detail`.
//
// THE NAME IS SANITISED, AND THAT IS NOT PARANOIA. Every other string
// this HUD draws was chosen by a service (a tool name, a state word, a
// service name) or by the user's own mouth (the transcript). This one was
// chosen by whoever built the installer, which invariant 8 says outright
// is untrusted — and a file name on Linux may legally contain newlines,
// control characters and bidirectional overrides. A raw name could
// therefore push a plate to three lines on a surface that floats over
// every window, or read as `setup.bat` while actually ending in `.exe`.
// `plainName()` keeps a name that survives being looked at: one line, no
// control or format characters, and a length cap — and a name with
// nothing left of it after that is reported as no name at all, which
// falls back to the hash.
//
// NAME OR FINGERPRINT, NEVER A GUESS. `path` is optional in the schema
// (jv-guard omits it for nothing today, but a frame is what it is), so
// when there is no usable name the plate gets the first 12 hex of the
// sha256 instead, clearly as a hash. That is the identity jv-guard's own
// log uses and the only thing about a file that is ever allowed to leave
// this machine (invariant 7) — so it is the one substitute a reader can
// actually go and look up.
//
// The latch is let go of in three ways:
//
//   · a newer verdict. The next screening is newer news from the same
//     screener, INCLUDING a clean one: this element reports the last
//     binary screened, and holding a refusal under a later screening
//     would describe a machine that is not the one in front of you.
//   · the link dropping. A cached verdict from a bus we can no longer
//     see is a claim about a machine we can no longer watch.
//   · `holdS`, the backstop. Unlike ActionState there is no "Jarvis
//     started explaining" exit here, and that is deliberate rather than
//     an omission: a verdict is not part of a voice turn — the trigger is
//     `jv-compat install` on a terminal — so a `speaking` frame that
//     lands after one is almost certainly about something else entirely,
//     and treating it as the explanation would take the refusal off the
//     screen for an unrelated sentence.
//
// On confidence (invariant 4): schemas/guard.verdict.json fixes envelope
// `conf` at 1.0. A scanner either matched or it did not; a hedged verdict
// is not a thing jv-guard publishes, so an unhedged `conf` is part of the
// envelope floor here rather than something displayed.
import QtQuick

QtObject {
  id: root

  // Anything offering `linkUp`, `latest(topic)` and `ageOf(envelope)`:
  // the `Bus` singleton in production, a BusModel the tests drive by hand.
  // Consumer-only by construction — there is nothing to publish with.
  property var bus: null

  // How long a refusal stays readable. The same 30 s ActionState and
  // HeardState use, and deliberately not pinned to either: this one is
  // "nobody is coming back to tell you about this", and whoever looks at
  // the screen on ares is free to answer it differently. Here it is the
  // ORDINARY exit rather than a backstop — nothing else ends a screening
  // except the next one — which is the one way this element leans on a
  // timer where its siblings lean on a signal.
  property real holdS: 30.0

  // The frozen enum of schemas/guard.verdict.json. A verdict outside this
  // list is a word the reader cannot look up and a frame this element was
  // not written against, so it is read as no news at all — never as
  // "clean" (which would silently clear a real refusal) and never as a
  // refusal of its own (which would put a word nobody can explain on
  // screen).
  readonly property var knownVerdicts: ["clean", "suspicious", "blocked"]

  // The two that are worth a plate. `blocked` is final; `suspicious` may
  // be overridden through the confirmation flow, which is ConfirmPlate's
  // job to show and not this element's to anticipate.
  readonly property var refusedVerdicts: ["suspicious", "blocked"]

  // How many characters of a file name may reach the screen. The plate
  // elides on WIDTH as well, which is what the reader actually sees; this
  // is the cap on what the element is willing to carry at all, so a
  // 4 kB name cannot become a 4 kB string being measured and elided on
  // every frame.
  readonly property int maxNameChars: 64

  // --- the outputs ----------------------------------------------------

  // Is there a refusal to show? The plate draws nothing whenever this is
  // false, which is the state of every machine that has not been handed a
  // Windows binary — that is to say, almost every machine, almost always.
  readonly property bool refused: root.linked && root.screening !== null && !root.expired

  // The screener's own word: "blocked" or "suspicious", or "" when there
  // is nothing to show.
  readonly property string verdict: root.refused ? root.screeningVerdict : ""

  // The file's own name, sanitised (see the header), or "" when the frame
  // carried no path or nothing survived being made safe to draw.
  readonly property string file: root.refused ? root.screeningFile : ""

  // The first 12 hex of the sha256 — the identity jv-guard logs and the
  // only thing about this file that may ever leave the machine. "" when
  // the frame's hash is not hex we can shorten honestly.
  readonly property string fingerprint: root.refused ? root.screeningSha : ""

  // --- the refusal we are holding --------------------------------------

  // The latched guard.verdict envelope, or null. Plain properties: they
  // are a memory, not a reading, and every path that sets them is below.
  // All three strings are resolved ONCE, at the moment the refusal is
  // accepted, so what is on screen cannot change under a reader while the
  // same refusal is being shown.
  property var screening: null
  property string screeningVerdict: ""
  property string screeningFile: ""
  property string screeningSha: ""

  // True only while the bridge holds a live subscription. Separate from
  // `frame` on purpose — a link that drops must forget the refusal, while
  // a frame we merely cannot parse must not.
  readonly property bool linked: !!root.bus && root.bus.linkUp === true

  onLinkedChanged: {
    if (!root.linked)
      root.forget();
  }

  // The newest guard.verdict we are willing to read, or null. Null covers
  // four things — nothing there, a frame from a schema version we were not
  // written against, one with no hash to identify the file by, and one
  // whose verdict is not a word in the enum — and `apply()` treats all of
  // them as no news. Refusing to read a frame is never the same as being
  // told a file was fine.
  readonly property var frame: {
    if (!root.linked || typeof root.bus.latest !== "function")
      return null;
    const env = root.bus.latest("guard.verdict");
    if (!root.wellFormed(env))
      return null;
    const b = env.body;
    if (typeof b.sha256 !== "string" || b.sha256.length === 0)
      return null;
    if (typeof b.verdict !== "string" || root.knownVerdicts.indexOf(b.verdict) < 0)
      return null;
    return env;
  }

  onFrameChanged: root.apply()

  function apply(): void {
    const env = root.frame;
    if (env === null)
      return; // a frame we cannot read is not a screening
    const b = env.body;
    if (root.refusedVerdicts.indexOf(b.verdict) < 0) {
      root.forget(); // the newest binary screened was clean
      return;
    }
    root.screening = env;
    root.screeningVerdict = b.verdict;
    root.screeningFile = root.plainName(b.path);
    root.screeningSha = root.shortSha(b.sha256);
  }

  function forget(): void {
    root.screening = null;
    root.screeningVerdict = "";
    root.screeningFile = "";
    root.screeningSha = "";
  }

  // --- the name, made safe to draw --------------------------------------

  // The file's own name out of a path chosen by whoever built the
  // installer. Everything here is about that one fact (see the header):
  //
  //   · the directory is dropped. `setup.exe` is the identity a reader
  //     needs at a glance, and the rest of the path is more of this
  //     filesystem than the question requires on a panel above every
  //     window.
  //   · control and format characters go. C0/C1, the zero-width marks and
  //     the bidirectional overrides — the last of which exist precisely to
  //     make a name render as something other than what it is.
  //   · every run of whitespace becomes one space, so a name with a
  //     newline in it stays one line in a plate that is sized for one.
  //     This happens BEFORE the strip, because a newline is both a
  //     control character and a word boundary: collapsing first turns
  //     `setup\ninstaller.exe` into `setup installer.exe`, while
  //     stripping first would join the two words its author separated.
  //   · and it is capped, because a name is an identifier here, not a
  //     document.
  //
  // A path that leaves nothing behind — "/", all control characters, only
  // spaces — returns "", which the plate reads as "no name" and answers
  // with the fingerprint instead.
  function plainName(path: var): string {
    if (typeof path !== "string" || path.length === 0)
      return "";
    const cut = path.lastIndexOf("/");
    const base = cut < 0 ? path : path.slice(cut + 1);
    const plain = base
      .replace(/\s+/g, " ")
      .replace(/[\u0000-\u001F\u007F-\u009F\u200B-\u200F\u202A-\u202E\u2060-\u2069]/g, "")
      .trim();
    return plain.length > root.maxNameChars ? plain.slice(0, root.maxNameChars) : plain;
  }

  // The first 12 hex digits of the hash, lowercased so two shots of the
  // same file read the same. A hash that is not at least that much hex is
  // not one this element will shorten: a truncated something-else looks
  // exactly like a sha256 prefix and would be the one identity on this
  // plate that cannot be looked up.
  function shortSha(sha: string): string {
    return /^[0-9a-fA-F]{12}/.test(sha) ? sha.slice(0, 12).toLowerCase() : "";
  }

  // --- the backstop ----------------------------------------------------

  // Set by the timer below, cleared whenever a new screening arrives. A
  // plain property rather than a computed one because time passing is not
  // a property change: no binding re-evaluates just because a clock moved.
  property bool expired: false

  // Identity of the refusal being held: `seq` is per-publisher and
  // strictly increasing, so this changes exactly once per verdict frame.
  readonly property string screeningKey: root.screening === null ? "" : root.screening.seq + "@" + root.screening.ts

  onScreeningKeyChanged: root.armHold()
  onHoldSChanged: root.armHold()

  // One shot, armed only while a refusal is actually held, so a HUD on a
  // machine that installs nothing runs no timer at all (§06: 0 fps when
  // nothing is happening). This is the rarest plate in the stack: it needs
  // someone to hand Jarvis a Windows binary AND a scanner to object to it.
  readonly property Timer hold: Timer {
    repeat: false
    onTriggered: root.expired = true
  }

  function armHold(): void {
    root.expired = false;
    if (root.screening === null) {
      root.hold.running = false;
      return;
    }
    // Whatever is LEFT of the window, not the whole of it: a frame that
    // spent time in flight is already partway through its own. `ageOf` is
    // Infinity when the age is not knowable (no clock, no ts), which lands
    // here as "already over" — a line the HUD cannot time is one it must
    // not hold open forever.
    const left = root.holdS - root.ageOf(root.screening);
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
