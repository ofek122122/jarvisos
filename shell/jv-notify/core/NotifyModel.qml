// NotifyModel — what is in the notification corner, and until when (PLAN D2).
//
// This is the half of the notification daemon that is pure QtQuick, so every
// decision it makes is testable without a compositor or a D-Bus session
// (`ops/ralph/notifytest.sh`). `Notifications.qml` next door is the other
// half: the org.freedesktop.Notifications server, the real monotonic clock,
// and nothing else. Logic that lands up there is logic no test can reach.
//
// The decisions, and why each one is a decision rather than a default:
//
//   · HOW MANY ARE ON SCREEN. Three. A notification corner that grows
//     without limit is a corner that eventually covers the window you were
//     reading, and the surface this feeds takes no input — so there would
//     be no way to push it off. The ones past the cap are not dropped and
//     not hidden either: `earlier` counts them, and the surface says so.
//
//   · HOW LONG ONE STAYS. `dwellMsFor` below, and the interesting case is
//     the one freedesktop leaves open: expire_timeout = 0 means "never
//     expire". Honoured literally, that is a D-Bus method any process on
//     this machine can call to pin a plate over your work forever. So a
//     non-critical notification that asks for forever gets `maxDwellMs`
//     instead, and the only thing that stays until it is withdrawn is
//     `Critical` — where losing it is the worse failure.
//
//   · WHAT HAPPENS WITH NO CLOCK. Nothing expires. `monotonic` is injected
//     (the tests drive one; the shell hands over Quickshell's ElapsedTimer),
//     and with no clock there is no answer to "how long has this been up",
//     so every deadline is 0 — never. A corner that cannot time itself
//     keeps what it was given rather than guessing when to drop it.
//
//   · WHAT A REPLACEMENT IS. freedesktop lets a sender reuse an id to
//     update a notification it already sent — a download at 40%, then 80%.
//     That is ONE story, so it updates in place and keeps its position in
//     the stack instead of jumping to the front; only its dwell is re-armed,
//     because the news is fresh even though the plate is not new.
//
// `handle` on a record is the sender-facing object, held opaquely: this file
// calls `expire()` on it when a dwell runs out and never reads a property of
// it. That is what lets the model own the lifecycle without importing
// Quickshell — and what lets a test pass a fake and assert it was called.
import QtQuick

QtObject {
  id: root

  // The monotonic clock, injected: a callable returning SECONDS since some
  // fixed origin. `Notifications.qml` supplies Quickshell's ElapsedTimer;
  // the tests supply one they can wind. Null means no clock (see above).
  property var monotonic: null

  // How many plates the corner may show at once. The rest are counted, not
  // forgotten.
  //
  // AND THIS CAP IS THE FLOOR (PLAN D77) — the reason this shell declares no
  // minimum screen height and warns about no screen, where `jv-hud` does both.
  //
  //   · The HUD asks the compositor for a FIXED 300x826 box, so a screen
  //     shorter than that crops it. D74 settled that as a declared floor and a
  //     warn rather than a clamp, because the choice there is WHICH crop and
  //     not whether to have one.
  //   · This surface is derived instead (`stack.implicitHeight + inset*2` in
  //     shell.qml), so the question is not whether it fits but how tall the
  //     stack can get — and the answer is bounded HERE. A plate's own height
  //     is bounded too: `Toast` gives the summary two lines and the body
  //     three, then elides. So the tallest corner anything can produce is this
  //     many plates at their own maximum, under the `+N EARLIER` line.
  //   · MEASURED, not reasoned: `docs/notify/11-tallest.png` is that corner,
  //     and it is 470 px tall, against a shortest loaded screen of 768 px
  //     (`tools/shellload/shells.py`). `tools/tests/test_notifyshots.py`
  //     holds those two numbers together, so a theme with a bigger body size,
  //     a fourth line of body, or a raised cap all turn red here instead of
  //     cropping a corner on somebody's screen. At today's rhythm this cap
  //     could go to five and still fit; six is where it stops.
  //
  // So a warn in this shell would be a warn that cannot fire. If one is ever
  // wanted, note that the crop it would report is the HUD's argument sharpened
  // rather than repeated: this column grows UPWARD out of the bottom corner,
  // so the first thing cut off is the topmost element — the `+N EARLIER` line,
  // whose entire job is to say that something is being hidden.
  property int maxVisible: 3

  // The dwell a notification gets when it did not ask for one, by urgency.
  // Low is something you may read; Normal is something you should. Neither
  // is a number anything else on this machine depends on, which is why they
  // are properties here rather than tokens in personality/theme.toml: they
  // are this element's policy, not the look.
  property real lowDwellMs: 4000
  property real normalDwellMs: 6000

  // The floor and the ceiling on a dwell a sender DID ask for. The floor
  // exists because a toast that is gone before it is read is a toast that
  // wasted the corner; the ceiling, because the corner is not a sender's to
  // keep. Both apply to `Normal` and `Low` only.
  property real minDwellMs: 1500
  property real maxDwellMs: 20000

  // The urgency values, as freedesktop numbers them on the wire (and as
  // Quickshell's NotificationUrgency enum happens to, because it is the same
  // table). Named here because core/ cannot import the enum, and a bare 2 in
  // a comparison is a number nobody can check.
  readonly property int urgencyLow: 0
  readonly property int urgencyNormal: 1
  readonly property int urgencyCritical: 2

  // Everything being tracked, OLDEST FIRST. Replaced wholesale rather than
  // mutated, so bindings on it actually re-evaluate.
  //
  // A record is: { key, appName, summary, body, urgency, deadline, handle }.
  // `deadline` is in the clock's own seconds, and 0 means "never".
  property var entries: []

  // What the surface draws: the NEWEST `maxVisible`, still oldest-first, so
  // a bottom-anchored column puts the newest nearest the corner.
  readonly property var toasts: root.entries.slice(Math.max(0, root.entries.length - root.maxVisible))

  // THE SAME LIST, BY IDENTITY — what the surface actually repeats over, and
  // the reason the corner stopped blinking (PLAN D37).
  //
  // `toasts` above is a fresh JS array every time anything is sent, replaced,
  // withdrawn or expired; it has to be, because a list mutated in place is a
  // list no binding hears about. A `Repeater` handed a fresh array does not
  // diff it — it destroys every delegate and builds new ones — and a rebuilt
  // `Toast` is one that starts at `arrived` false and fades up from zero
  // AGAIN. So every plate in the corner announced itself as new whenever any
  // other notification arrived, and a download updating its own progress made
  // all three of them blink. `core/KeyedRows.qml` syncs by the notification's
  // own key, so a plate that is still up keeps its delegate and stays exactly
  // where it was.
  //
  // Only the fields a plate DRAWS go in, and every one of them is a
  // primitive: a ListModel's roles are values, not objects, so `handle` (the
  // sender-facing object this file calls `expire()` on) and `deadline` (the
  // lifecycle's, never the plate's) stay here where they belong. `key` is
  // carried because it is what makes a row the same row.
  readonly property KeyedRows onScreen: KeyedRows {}

  onToastsChanged: root.onScreen.sync(root.toasts.map(e => ({
    "key": e.key,
    "appName": e.appName,
    "summary": e.summary,
    "body": e.body,
    "urgency": e.urgency
  })))

  // How many are being tracked and NOT shown. They are older than everything
  // on screen, which is the word the surface uses for them.
  readonly property int earlier: Math.max(0, root.entries.length - root.maxVisible)

  // Is there anything at all? The surface is unmapped when there is not
  // (§06: earned emptiness, and 0 fps for a corner with nothing in it).
  readonly property bool anyLit: root.entries.length > 0

  // --- taking one in ----------------------------------------------------

  // Add or replace a notification. `record` is what the server half read off
  // the wire: { key, appName, summary, body, urgency, timeoutMs, handle }.
  // Everything is optional except `key`, because everything except `key` is
  // something a sender chose and may have left out.
  function push(record: var): void {
    if (record === null || record === undefined || record.key === undefined)
      return; // nothing we could ever find again, or close
    const key = "" + record.key;
    const urgency = root.normalUrgency(record.urgency);
    const entry = {
      "key": key,
      // The sender's own words, whitespace-collapsed (see `oneLine`).
      "appName": root.oneLine(record.appName),
      "summary": root.oneLine(record.summary),
      "body": root.oneLine(record.body),
      "urgency": urgency,
      "deadline": root.deadlineFor(urgency, record.timeoutMs),
      "handle": record.handle === undefined ? null : record.handle
    };

    const next = root.entries.slice();
    const at = root.indexOf(key);
    if (at < 0)
      next.push(entry);
    else
      next[at] = entry; // one story, same place in the stack
    root.entries = next;
    root.arm();
  }

  // Forget one, without closing it: this is what the server half calls when
  // the notification is ALREADY closed (expired, withdrawn by its sender, or
  // dismissed), so the handle must not be touched. Unknown keys are a no-op —
  // a close can arrive for something this model never showed.
  function drop(key: string): void {
    const next = root.entries.filter(e => e.key !== key);
    if (next.length === root.entries.length)
      return;
    root.entries = next;
    root.arm();
  }

  // Forget all of them, still without closing anything. For a link that went
  // away rather than a notification that ended.
  function clear(): void {
    root.entries = [];
    root.arm();
  }

  function indexOf(key: string): int {
    for (let i = 0; i < root.entries.length; i++) {
      if (root.entries[i].key === key)
        return i;
    }
    return -1;
  }

  // --- how long it stays ------------------------------------------------

  // The dwell for one notification, in milliseconds. 0 means it never
  // expires on its own and waits for its sender to withdraw it.
  function dwellMsFor(urgency: int, timeoutMs: var): real {
    if (root.normalUrgency(urgency) === root.urgencyCritical)
      return 0; // the one thing allowed to stay: losing it is worse
    const fallback = root.normalUrgency(urgency) === root.urgencyLow ? root.lowDwellMs : root.normalDwellMs;
    const asked = typeof timeoutMs === "number" && isFinite(timeoutMs) ? timeoutMs : NaN;
    if (!isFinite(asked) || asked < 0)
      return fallback; // -1, or nothing readable: the server decides
    if (asked === 0)
      return root.maxDwellMs; // "forever" is not a sender's to ask for
    return Math.min(Math.max(asked, root.minDwellMs), root.maxDwellMs);
  }

  // When one should go, on the injected clock. 0 for "never" — which is what
  // a critical notification gets, and what EVERYTHING gets while there is no
  // clock to measure a dwell against.
  function deadlineFor(urgency: int, timeoutMs: var): real {
    const dwell = root.dwellMsFor(urgency, timeoutMs);
    const now = root.nowS();
    return dwell > 0 && isFinite(now) ? now + dwell / 1000 : 0;
  }

  // Seconds on the injected clock, or NaN when there is none.
  function nowS(): real {
    return typeof root.monotonic === "function" ? root.monotonic() : NaN;
  }

  // --- the one timer ----------------------------------------------------

  // One shot, armed for the SOONEST deadline and re-armed after every sweep.
  // Not one timer per plate and not a ticker: a corner with nothing in it
  // runs no timer at all, and a corner with three runs one.
  readonly property Timer expiry: Timer {
    repeat: false
    onTriggered: root.sweep()
  }

  // Drop everything whose deadline has passed, and tell each one's sender it
  // expired. The list is replaced BEFORE any handle is touched, because
  // `expire()` is what makes the server emit `closed`, which comes straight
  // back here as `drop()` — so the sweep must already be over by then.
  function sweep(): void {
    const now = root.nowS();
    if (!isFinite(now))
      return; // no clock, no deadline, nothing to sweep
    const done = [];
    const keep = [];
    for (let i = 0; i < root.entries.length; i++) {
      const e = root.entries[i];
      if (e.deadline > 0 && e.deadline <= now)
        done.push(e);
      else
        keep.push(e);
    }
    if (done.length > 0)
      root.entries = keep;
    root.arm();
    for (let i = 0; i < done.length; i++) {
      const h = done[i].handle;
      if (h !== null && h !== undefined && typeof h.expire === "function")
        h.expire();
    }
  }

  function arm(): void {
    const now = root.nowS();
    let soonest = 0;
    for (let i = 0; i < root.entries.length; i++) {
      const d = root.entries[i].deadline;
      if (d > 0 && (soonest === 0 || d < soonest))
        soonest = d;
    }
    if (soonest === 0 || !isFinite(now)) {
      root.expiry.running = false;
      return;
    }
    // At least 1 ms: a deadline already in the past still goes through the
    // timer rather than recursing into `sweep` from inside itself.
    root.expiry.interval = Math.max(1, Math.ceil((soonest - now) * 1000));
    root.expiry.restart();
  }

  // --- reading what a sender sent, defensively --------------------------

  // Anything that is not one of the three urgencies is Normal. A sender can
  // put any byte in that field, and the two readings that must not happen
  // are "unknown urgency, so nothing is shown" and "unknown urgency, so it
  // is treated as critical".
  function normalUrgency(urgency: var): int {
    if (urgency === root.urgencyLow || urgency === root.urgencyCritical)
      return urgency;
    return root.urgencyNormal;
  }

  // One line of text, as a plate can show it: every run of whitespace
  // becomes a single space, and the ends are trimmed. A notification body
  // arrives as whatever the sender formatted for a dialog — tabs, newlines,
  // a trailing blank line — and a glance-sized plate that honoured those
  // would show two words and a lot of air. It is collapsed rather than
  // truncated: nothing is dropped here, and how much of it fits is the
  // surface's business.
  function oneLine(text: var): string {
    if (typeof text !== "string")
      return "";
    return text.replace(/\s+/g, " ").trim();
  }
}
