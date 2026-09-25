// VramState — how much of the card is left, at the one moment it explains
// something (B40).
//
// `schemas/context.system.json` has carried `gpu_vram_free_mb` since v1 and
// nothing has ever read it. jv-context started measuring it in B37, and
// what it measures on ares is the interesting case: **943 MiB free of
// 6144**, twice in one week, with a perfectly healthy GTX 1660 SUPER —
// the desktop, the compositor and a browser own the rest. That is why
// jv-brain launches onto the CPU rung (B39/B41) on a machine whose GPU
// works, and it is the number invariant 6 is named after.
//
// The HUD already says the first half of that sentence: `HealthPlate` has
// drawn `llm CPU RUNG 4` since A6, off jv-brain's own heartbeat. What it
// could never say is WHY, and without the why that line reads as a fault —
// a broken driver, a card that fell out, something to go and fix. It is
// none of those. It is the ladder in invariant 6 doing exactly its job on a
// 6 GB card that is already spoken for, and the one thing that turns the
// line from an accusation into an explanation is the number sitting under
// it.
//
// So this element answers one question — how much VRAM is free right NOW —
// and refuses to answer it out loud at any other moment:
//
// NOT A GAUGE. A readout that is on screen all day is a readout nobody
// reads (§06's earned emptiness, and the same argument `HealthPlate` is
// built on). Free VRAM is news only while something is being paid for it,
// and today exactly one thing is: a brain on the CPU floor. `brainOnCpu`
// is that gate, and it is an INPUT rather than something this file reads
// for itself — jv-brain's rung already has a reader in `HealthState`, which
// owns the heartbeat's expiry and its trust rules, and two files deciding
// the same fact off the same topic is how they come to disagree. This
// element never guesses it: unfed, it is false, and nothing is drawn.
//
// A LIVE READING, NEVER A MEMORY. Like `OutputState` (A40) and unlike
// `ActionState` (A37), there is nothing here worth latching: the whole
// value of the number is that it MOVES — a game starts, a browser closes —
// and a remembered VRAM figure is a claim about a machine as it used to be.
// `snapshotS` is how long one 1 Hz snapshot may speak for the present; past
// that this element knows nothing, which is drawn as nothing rather than as
// a stale figure that looks live.
//
// ZERO IS A READING; ABSENT IS NOT. `gpu_vram_free_mb` is optional in the
// schema, because a machine with no GPU has no such number — and that is
// also the machine where jv-brain reports `llm_gpu = 0` for a reason that
// has nothing to do with pressure (B39). Absent therefore has to stay
// absent: it cannot be defaulted to 0, which would put "0 MiB FREE" under
// the rung line on a card-less machine and invent a shortage to explain a
// CPU brain that never had an alternative. `known` is the boolean and
// `freeMb` is -1 when nothing is known, so a genuine 0 MiB — the most
// informative reading this field can carry — is never confused with it.
//
// THE NUMBER IS QUOTED, NEVER JUDGED. No threshold lives here. "Enough
// VRAM for the 8B Q4 brain" is a fact about the rung ladder in jv-brain's
// launcher, and a HUD deciding "the card is free now, restart the brain"
// would be guessing at another service's configuration through a wall
// invariant 1 put there on purpose.
//
// Which is why the second row (B46) is a QUOTE and not a verdict.
// jv-brain now publishes what its own ladder would need — `llm_gpu_floor_mb`,
// 5424 MiB of ares' 6144 MiB card — and this element puts that figure on
// the line below the reading, in the same units, and stops there. It
// never subtracts the two, never colours one against the other, and never
// says "restart jv-llm": the comparison a reader makes from two numbers
// standing next to each other is theirs, and the same two numbers are on
// the bus for anything that wants to make it properly. The floor is an
// INPUT here for the same reason `brainOnCpu` is — it arrives on
// `sys.health`, which `HealthState` owns.
//
// On confidence (invariant 4): `context.system` fixes envelope conf at 1.0.
// A hedged snapshot of a mixer or a card is a frame that disagrees with
// itself, and this line is not worth drawing on a maybe.
import QtQuick

QtObject {
  id: root

  // Anything offering `linkUp`, `latest(topic)` and `ageOf(envelope)`: the
  // `Bus` singleton in production, a BusModel the tests drive by hand.
  // Consumer-only by construction — there is nothing to publish with.
  property var bus: null

  // How long one 1 Hz snapshot describes the present. Read off
  // schemas/context.system.json's own rate ("1 Hz system snapshot") rather
  // than copied out of jv-context's configuration, and three periods not
  // two for the reason `OutputState` gives: jv-context is a user-session
  // Python process competing with CPU Whisper and an 8B prefill, so the
  // moment it runs late is the moment this machine is busy — which is the
  // moment a VRAM figure is being read.
  property real snapshotS: 3.0

  // Is the brain on the CPU floor? Fed from `HealthState.llmOnCpu`, which
  // reads it off jv-brain's own `sys.health` heartbeat. False by default:
  // an unfed VramState says nothing, which is the same nothing a HUD that
  // cannot see the bus says.
  property bool brainOnCpu: false

  // What the card would have to give back before jv-brain's ladder would
  // pick a GPU rung again, in whole MiB — or -1 for "the brain is not
  // saying". Fed from `HealthState.llmGpuFloorMb`, which reads it off
  // jv-brain's own heartbeat (B45), and never computed here: the ladder
  // and its VRAM requirements live in `jv_brain/config.py`, on the far
  // side of the wall invariant 1 put there, and a HUD that guessed at
  // them would be quoting another service's configuration back at its
  // user. Unfed, it is -1, and the row below never appears — which is
  // exactly what this plate drew before the gauge existed.
  property real gpuFloorMb: -1

  // --- the outputs ------------------------------------------------------

  // Is there a free-VRAM figure this element is willing to stand behind
  // right now? False on a card-less machine, a dead link, a snapshot too
  // old to describe the present, and any body this file may not read.
  readonly property bool known: root.snapshot !== null && !root.expired && root.ageOf(root.snapshot) <= root.snapshotS

  // Free VRAM in MiB, or -1 when nothing is known. Never 0 for unknown:
  // see the header — 0 MiB free is the reading that explains the most.
  readonly property real freeMb: root.known ? root.reading : -1

  // Is this worth putting on a screen? Only while something is being paid
  // for the shortage. A card nobody is waiting on is not news.
  readonly property bool reporting: root.known && root.brainOnCpu

  // The line, as `HealthPlate` draws it — "943 MiB FREE" — or "" whenever
  // there is nothing to say. Named `line` and not `detail` because `detail`
  // in core/ can only mean `action.result.detail`, the free text for logs
  // that no element may render (invariant 7) — and a test in
  // tools/tests/test_gen_theme_qml.py holds every file here to that.
  readonly property string line: root.reporting ? root.render(root.freeMb) : ""

  // --- and what it would take (B46) --------------------------------------

  // Is there a requirement to put UNDER the reading? Only ever under it.
  // `reporting` is in the condition and not merely nearby: a requirement
  // with no measurement beside it is a number a reader cannot check —
  // "the brain wants 5424 MiB" says nothing about whether this machine
  // has them — and jv-brain refuses the same line for the same reason
  // (its `notes` quote the floor only next to a reading it actually
  // took). So the two rows arrive and leave together, and a HUD that can
  // see jv-brain but not jv-context draws exactly what it drew before.
  readonly property bool needKnown: root.reporting && root.gpuFloorMb > 0 && isFinite(root.gpuFloorMb)

  // The second row, as `HealthPlate` draws it — "NEEDS 5424 MiB" — or "".
  // Two rows rather than one composed sentence, because the two figures
  // come from two different services: jv-context measured the first and
  // jv-brain computed the second, and a single string would be the HUD
  // synthesising a claim neither of them made. Side by side, the
  // comparison is a glance instead of something the reader has to know
  // this machine's ladder to make.
  readonly property string needLine: root.needKnown ? "NEEDS " + root.amount(root.gpuFloorMb, true) : ""

  // Whole MiB below five digits, then GiB — one decimal, and none at all
  // past 100 GiB. Not cosmetic: the HUD surface is a fixed 300 px box
  // (shell.qml) sized to the longest line any plate may ever draw, which is
  // `jv-compat DEGRADED`, and a figure in bare MiB grows with the card. The
  // three branches are picked so that every one of them is thirteen
  // characters at its widest — `9999 MiB FREE`, `99.9 GiB FREE`,
  // `1024 GiB FREE` — so no card that exists can push this row past the
  // line that box was measured against. Rounding to whole MiB for the
  // reason ares' own reading is a whole number: nothing here is decided by
  // a fraction of a mebibyte.
  function render(mb: real): string {
    return root.amount(mb, false) + " FREE";
  }

  // The quantity on its own, in at most eight characters — `9999 MiB`,
  // `99.9 GiB`, `1024 GiB` — so that neither row can widen past the box:
  // `vram ` + eight + ` FREE` is thirteen, and `NEEDS ` + eight is
  // fourteen under a three-letter name.
  //
  // `up` is which way a figure that does not divide evenly is allowed to
  // move, and it is not cosmetic. A free-VRAM reading rounds to nearest
  // (nothing here is decided by a fraction of a MiB, and ares' own
  // reading is a whole number); a REQUIREMENT rounds up, so the pair can
  // never draw a fit that the ladder would not actually take. jv-brain
  // already rounds its floor up for the same reason, which makes this
  // belt and braces — and belt and braces is the right amount of care for
  // a number whose whole job is to be compared against another one.
  function amount(mb: real, up: bool): string {
    if (mb < 10000)
      return (up ? Math.ceil(mb) : Math.round(mb)) + " MiB";
    const gib = mb / 1024;
    if (gib >= 100)
      return String(up ? Math.ceil(gib) : Math.round(gib)) + " GiB";
    return (up ? Math.ceil(gib * 10) / 10 : gib).toFixed(1) + " GiB";
  }

  // --- reading the frame -------------------------------------------------

  // True only while the bridge holds a live subscription. A cached
  // snapshot from a link that has since dropped describes a card we can no
  // longer see — including one a closed game has since handed back.
  readonly property bool linked: !!root.bus && root.bus.linkUp === true

  // The newest snapshot carrying a readable free-VRAM figure, or null.
  // Null covers: nothing there, a body from a schema version this file was
  // not written against (invariant 2), a frame with no orderable `ts`
  // (without one there is no age, and so no expiry), a hedged `conf`, a
  // machine with no such field at all, and a figure that is not a figure —
  // a string, a negative number (the schema's own minimum is 0), or the
  // Infinity that `1e999` on the wire parses to.
  readonly property var snapshot: {
    if (!root.linked || typeof root.bus.latest !== "function")
      return null;
    const env = root.bus.latest("context.system");
    if (!root.wellFormed(env))
      return null;
    const mb = env.body.gpu_vram_free_mb;
    return typeof mb === "number" && isFinite(mb) && mb >= 0 ? env : null;
  }

  // The figure off the frame above, unqualified by freshness. Everything
  // public goes through `known` first.
  readonly property real reading: root.snapshot === null ? -1 : root.snapshot.body.gpu_vram_free_mb

  // --- how long the figure describes the present -------------------------

  // Set by the timer below, cleared by every frame that moves the
  // deadline. A plain property, not a computed one: no binding
  // re-evaluates because a clock moved, and a VRAM figure that stops being
  // true while nothing arrives is exactly this element's problem.
  property bool expired: false

  // Identity of the frame currently believed — `seq` is per-publisher and
  // strictly increasing, so this changes exactly once per snapshot.
  readonly property string frameKey: root.snapshot === null ? "" : root.snapshot.seq + "@" + root.snapshot.ts

  onFrameKeyChanged: root.armExpiry()
  onSnapshotSChanged: root.armExpiry()

  // One shot, armed only while there is a frame to expire — a HUD on a
  // machine with no jv-context runs no timer at all (§06: 0 fps when
  // nothing is happening). On a live machine jv-context re-arms it once a
  // second.
  readonly property Timer expiry: Timer {
    repeat: false
    onTriggered: root.expired = true
  }

  function armExpiry(): void {
    root.expired = false;
    if (root.snapshot === null) {
      root.expiry.running = false;
      return;
    }
    // Whatever is LEFT of the window, not the whole of it: a frame that
    // spent time in flight is already partway through its own life.
    const left = root.snapshotS - root.ageOf(root.snapshot);
    if (!(left > 0)) {
      root.expiry.running = false;
      root.expired = true;
      return;
    }
    root.expiry.interval = Math.max(1, Math.ceil(left * 1000));
    root.expiry.restart();
  }

  // --- reading the bus, defensively --------------------------------------

  function ageOf(envelope: var): real {
    return root.bus && typeof root.bus.ageOf === "function" ? root.bus.ageOf(envelope) : Infinity;
  }

  // The envelope floor: the schema version this file was written against
  // (invariant 2 — a v2 body is not a v1 body), a numeric `ts`, an
  // unhedged `conf` (see the header), and a body.
  function wellFormed(envelope: var): bool {
    return !!envelope && envelope.v === 1 && typeof envelope.ts === "number" && envelope.conf >= 1 && !!envelope.body;
  }
}
