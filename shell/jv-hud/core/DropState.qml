// DropState — did the bus throw frames away, and how many (A75).
//
// `schemas/sys.health.json` has carried `drops` since v1: "frames dropped
// since the last heartbeat, keyed by topic. Published by jarvisd per slow
// subscriber; empty/absent = none." The broker really fills it —
// `broker.rs` counts an out-queue overflow against the topic it threw
// away, a broadcast lag against `_lagged`, a lost control frame against
// `_ctl`, sums every connection's tally into one map and drains it into
// each heartbeat — and `jv health` really prints it. Until this element,
// nothing in `shell/jv-hud` read the field at all: `seq` appears in eleven
// files under `core/` and in every one of them it is an identity
// component, never a gap check.
//
// Which left invariant 5's one failure visible to a human at a terminal
// and invisible on screen. That matters more here than it would anywhere
// else, because it is a fact ABOUT the other plates: every line in this
// corner is drawn from the frames that arrived, and a drop is the machine
// saying that some did not. A HUD that cannot say so is a HUD whose
// silence means two different things.
//
// Five rules hold it to the truth:
//
// NOT A GAUGE. A healthy machine publishes no map at all, and a row
// reading "0 DROPPED" all day is the readout nobody reads on the day it
// matters (§06's earned emptiness, and `HealthPlate`'s whole design). So
// zero is silence — which is where this element parts company with
// `VramState` (B40) on purpose: 0 MiB free is the most informative reading
// that field can carry, and 0 frames dropped is the machine being well.
//
// AN AGGREGATE NAMES NOBODY. The broker sums every subscriber connection's
// drops before publishing, so the HUD may not be the reader that lost
// anything — one slow consumer three processes away produces this frame.
// The row therefore says the BUS dropped something and stops there. It
// does not name a topic (which would invite "audio.vad is broken" when the
// fault is elsewhere, and would not fit the 300 px box anyway) and it
// never claims whose frames were lost. The map itself is one `jv health`
// away, which is the same standing answer B23 gives for `jv sub`.
//
// ONE PERIOD, NOT TWO. The count describes the stretch that just ended,
// and the next heartbeat is due in `period_s`. Two periods is the schema's
// rule for presuming a SERVICE dead — `HealthState` uses it for exactly
// that — and borrowing it here would leave an interval's news on screen
// for twice the interval it happened in. If the broker then goes quiet,
// `HealthState` reports jarvisd `lost` on its own account and this row
// simply is not there.
//
// ONLY THE BROKER SAYS THIS. A slow subscriber is a thing only jarvisd can
// see. `drops` on jv-ears' heartbeat would be a perception service
// claiming a fact from the far side of invariant 1's wall, and it is read
// off the broker by NAME rather than off whoever published `drops` last.
// The name is an input (like `HealthState.brain`) so that nothing here
// hardcodes a roster it cannot see.
//
// A TOTAL THAT CANNOT BE TOTALLED IS NOT A TOTAL. One value that is not a
// whole non-negative count makes the sum wrong by an unknown amount, and
// the sum is the only thing this row says. So a single unreadable value
// refuses the whole frame rather than being skipped: a partial total
// presented as a total is worse than saying nothing, and saying nothing
// claims nothing.
//
// The state word is deliberately NOT read. jarvisd hardcodes `ok` in the
// same body that carries the map (A76), and whether the broker should ever
// call itself impaired is a decision with a human in it; either way the
// count is the news.
import QtQuick

QtObject {
  id: root

  // Anything offering `linkUp`, `latestFrom(topic, src)` and
  // `ageOf(envelope)`: the `Bus` singleton in production, a BusModel the
  // tests drive by hand. Consumer-only by construction — there is nothing
  // to publish with.
  property var bus: null

  // Who the broker is. An input for the same reason `HealthState.brain` is
  // one: this file reads a field only one process on the machine can fill,
  // and it says which process rather than trusting the newest frame.
  property string broker: "jarvisd"

  // --- the outputs ------------------------------------------------------

  // Frames the bus threw away in the interval this heartbeat describes, or
  // -1 when there is no readable count. Never 0 for unknown: 0 is a real
  // reading here (the interval dropped nothing) and it is the reading that
  // takes the row off.
  readonly property real dropped: root.reading

  // Is this worth putting on a screen? Only a count that is both readable
  // and non-zero, off a heartbeat still inside the period it describes.
  readonly property bool reporting: root.dropped > 0 && !root.expired && root.withinPeriod

  // The line, as `HealthPlate` draws it — "12 DROPPED" — or "" whenever
  // there is nothing to say. Named `line` and not `detail` because
  // `detail` in core/ can only mean `action.result.detail`, the free text
  // for logs that no element may render (invariant 7) — and a test in
  // tools/tests/test_gen_theme_qml.py holds every file here to that.
  readonly property string line: root.reporting ? root.render(root.dropped) : ""

  // The count, in at most five characters. Not cosmetic: the HUD surface
  // is a fixed 300 px box (shell.qml) sized to the longest line any plate
  // may ever draw, which is `jv-compat DEGRADED`, and an unbounded count
  // is the one thing on this row that could grow. Both branches are
  // bounded — `9999 DROPPED` and `9999+ DROPPED` — and the capped branch
  // says it is capped, because a truncation that does not admit it reads
  // as a complete number. Past four digits the exact figure has stopped
  // being the point anyway; `jv health` has it to the frame.
  function render(n: real): string {
    return (n > 9999 ? "9999+" : String(n)) + " DROPPED";
  }

  // --- reading the frame -------------------------------------------------

  // True only while the bridge holds a live subscription. A cached count
  // from a link that has since dropped describes a broker the HUD can no
  // longer see.
  readonly property bool linked: !!root.bus && root.bus.linkUp === true

  // The broker's newest heartbeat, or null. Null covers: nothing there, a
  // body from a schema version this file was not written against
  // (invariant 2), a frame with no orderable `ts` (without one there is no
  // age, and so no expiry), a hedged `conf` (sys.health fixes it at 1.0,
  // and less than that disagrees with itself), a body naming a DIFFERENT
  // service than the envelope said published it, and no usable `period_s`,
  // which is how long the count may speak for.
  readonly property var beat: {
    if (!root.linked || typeof root.bus.latestFrom !== "function")
      return null;
    const env = root.bus.latestFrom("sys.health", root.broker);
    if (!env || env.v !== 1 || typeof env.ts !== "number" || env.conf !== 1 || !env.body)
      return null;
    // `period_s` must be a NUMBER and not merely something that compares
    // greater than zero: `"5" > 0` is true in JavaScript, and a period
    // arriving as a string is a body this file could only interpret by
    // coercion. (`HealthState.trust` writes the same test without the
    // `typeof`, where it is harmless — it only ever multiplies the value —
    // but here the period is arithmetic on a timer's interval.)
    if (env.body.service !== root.broker)
      return null;
    if (typeof env.body.period_s !== "number" || !isFinite(env.body.period_s) || env.body.period_s <= 0)
      return null;
    return env;
  }

  // The total off the frame above, unqualified by freshness, or -1 when
  // there is no total to be had. An absent map is -1 and not 0: the schema
  // says absent means none, but "none" is what a broker that is not
  // reporting looks like too, and only a map the broker actually wrote can
  // say the interval was clean. Both come out as silence, so the
  // distinction costs nothing on screen and keeps `dropped` honest.
  readonly property real reading: {
    const env = root.beat;
    if (env === null)
      return -1;
    const map = env.body.drops;
    // `typeof null` is "object" and an Array is one too, and neither is the
    // keyed map the schema describes.
    if (!map || typeof map !== "object" || Array.isArray(map))
      return -1;
    let total = 0;
    for (const key in map) {
      const n = map[key];
      // The schema's own type is a non-negative integer. A fraction, a
      // negative, a string, or the Infinity that `1e999` on the wire
      // parses to is a value this element cannot add up — and one of them
      // makes the whole sum wrong by an unknown amount.
      if (typeof n !== "number" || !isFinite(n) || n < 0 || Math.floor(n) !== n)
        return -1;
      total += n;
    }
    return total;
  }

  // --- how long an interval's news is news -------------------------------

  // Is the heartbeat still inside the period it promised to speak again
  // in? `ageOf` is Infinity when the age is not knowable (no clock, no
  // ts), which fails this — an age we cannot compute is not an age we may
  // assume is zero.
  //
  // STRICTLY inside, unlike `HealthState.lost`'s two-period window, and
  // the strictness is load-bearing rather than fussy: `armExpiry` below
  // arms a timer for the time remaining, so a period that had exactly run
  // out would be a frame with nothing left to wait for and no deadline to
  // take it off. One comparison answers both, which is the only way they
  // cannot come to disagree.
  readonly property bool withinPeriod: {
    const env = root.beat;
    if (env === null || !root.bus || typeof root.bus.ageOf !== "function")
      return false;
    return root.bus.ageOf(env) < env.body.period_s;
  }

  // Set by the timer below, cleared by every frame that moves the
  // deadline. A plain property, not a computed one: no binding
  // re-evaluates because a clock moved, and nothing publishes "the bus has
  // stopped dropping frames" — letting go on a timer is the only way this
  // row ever leaves while nothing arrives.
  property bool expired: false

  // Identity of the heartbeat currently believed — `seq` is per-publisher
  // and strictly increasing, so this changes exactly once per frame.
  readonly property string beatKey: root.beat === null ? "" : root.beat.seq + "@" + root.beat.ts

  onBeatKeyChanged: root.armExpiry()

  // One shot, armed only while there is a count to expire — a HUD on a
  // machine whose broker is quiet, or whose broker is not dropping
  // anything, runs no timer at all (§06: 0 fps when nothing is happening).
  readonly property Timer lifespan: Timer {
    repeat: false
    onTriggered: root.expired = true
  }

  function armExpiry(): void {
    // Cleared first, and it is not housekeeping: the bus dropping frames
    // in two intervals running is the ordinary shape of this failure, and
    // an `expired` left set by the first would keep the row off for the
    // second and for every one after it.
    root.expired = false;
    root.lifespan.stop();
    const env = root.beat;
    // Nothing to let go of unless there is a count worth drawing AND a
    // period still to run. Both are asked through the properties that
    // decide what is on screen, rather than re-derived here: a second copy
    // of "is this still fresh" is a second thing that can disagree with
    // the first, and `withinPeriod` being true is exactly what makes the
    // subtraction below positive.
    if (env === null || !(root.reading > 0) || !root.withinPeriod)
      return;
    root.lifespan.interval = (env.body.period_s - root.bus.ageOf(env)) * 1000;
    root.lifespan.start();
  }
}
