// HealthState — is anything wrong with Jarvis right now? (A6)
//
// Every service heartbeats on `sys.health` (schemas/sys.health.json): a
// state word, how long it has been up, and how often it promises to speak
// again. This turns that stream into the one thing a glance needs — a
// short list of what is NOT well — and into the llm rung, which is the
// single number that explains why Jarvis got slow.
//
// Three rules hold it to the truth:
//
//   · **The roster is who has spoken.** Nothing on the bus announces which
//     services are supposed to be running, and inventing that list here
//     would mean the HUD reporting on a machine it has not heard. So a
//     service that never started is absent, not dead. Absence claims
//     nothing; that is the honest shape of not knowing.
//   · **A heartbeat expires.** The schema says missing two consecutive
//     periods is presumed dead, so a frame speaks for two of its own
//     periods and no longer. Nothing publishes "jv-brain died" — letting
//     go on a timer is the only way the HUD ever learns it.
//   · **Unreadable is not fine.** A body from a schema version this file
//     was not written against, a hedged `conf`, a body naming a service
//     other than the one that published it, a state word outside the
//     frozen enum: all `unknown`, all reported. The failure that matters
//     is the quiet one — a green corner over a machine that is broken.
//
// §06 earns the empty corner the other way round: when every service
// heard from is `ok`, there are no findings and the plate draws nothing.
// A link that is down also draws nothing, for the opposite reason — see
// HealthPlate, where that asymmetry is the whole design.
import QtQuick

QtObject {
  id: root

  // Anything offering `linkUp`, `publishersOf(topic)`, `latestFrom()` and
  // `ageOf()`: the `Bus` singleton in production, a BusModel the tests
  // drive.
  property var bus: null

  // The service that owns the model. It is the only one that can see the
  // rung, so the metrics are read from its heartbeat by name rather than
  // from whoever published `llm_rung` last.
  property string brain: "jv-brain"

  // Can the HUD see the bus at all? Distinct from "is anything wrong" —
  // a blind HUD reports nothing, and reporting nothing is not an
  // all-clear.
  readonly property bool known: root.bus ? root.bus.linkUp === true : false

  // Every service heard from, sorted by name:
  //   { service, state, severity, notes }
  // `state` is one of the schema's five words, plus `lost` (heartbeats
  // stopped) and `unknown` (heard, unreadable). Never a word off the wire
  // that the schema does not define.
  readonly property var roster: {
    const beats = root.beats;
    let out = [];
    for (const service in beats) {
      const env = beats[service];
      let state = "unknown";
      let notes = "";
      if (env !== null) {
        if (root.lost(env, service)) {
          // The notes described a moment that has passed; the only true
          // thing left to say about this service is that it went quiet.
          state = "lost";
        } else {
          state = root.definedState(env.body.state) ? env.body.state : "unknown";
          if (typeof env.body.notes === "string")
            notes = env.body.notes;
        }
      }
      out.push({
        "service": service,
        "state": state,
        "severity": root.rank(state),
        "notes": notes
      });
    }
    out.sort((a, b) => root.byName(a.service, b.service));
    return out;
  }

  // What is wrong, worst first, ties broken by name so the list does not
  // reshuffle under the reader's eye between two equally bad findings.
  readonly property var findings: {
    let out = root.roster.filter(entry => entry.severity > 0);
    out.sort((a, b) => b.severity - a.severity || root.byName(a.service, b.service));
    return out;
  }

  readonly property int findingCount: root.findings.length

  // Is there anything at all to put on screen? A brain on the CPU is not
  // a fault — no service reports itself degraded for it — but it is the
  // difference between "Jarvis is thinking" and "Jarvis is thinking for
  // thirty seconds", so it counts.
  readonly property bool reporting: root.findingCount > 0 || root.llmOnCpu

  // --- the llm rung ----------------------------------------------------

  // The rung jv-brain picked at launch, or -1 when it cannot be known —
  // no brain on the bus, a heartbeat too old to describe now, or a brain
  // that reports no gauges. Invariant 6: 0 is the roomiest GPU shape, 4
  // is the CPU floor that always fits.
  readonly property int llmRung: root.brainMetrics === null || typeof root.brainMetrics.llm_rung !== "number" ? -1 : root.brainMetrics.llm_rung

  // "gpu", "cpu", or "unknown". Unknown is never rendered as "gpu": a
  // brain we cannot read is not a brain we may reassure anyone about.
  readonly property string llmBackend: {
    const m = root.brainMetrics;
    if (m === null || typeof m.llm_gpu !== "number")
      return "unknown";
    return m.llm_gpu === 1 ? "gpu" : "cpu";
  }

  readonly property bool llmOnCpu: root.llmBackend === "cpu"

  // The least free VRAM at which jv-brain's ladder would still land on the
  // card, in whole MiB — or -1 when the brain is not saying. jv-brain
  // computes it off its own ladder (`launcher.gpu_floor_mb`) and publishes
  // it only while something is waiting on it: never while the model is
  // already on the GPU, and never on a machine with no card, where a
  // floor would send a reader hunting VRAM that machine has never had.
  // So its mere PRESENCE is meaningful, and this reads it exactly as
  // published rather than deriving a floor for a brain that did not offer
  // one (invariant 1: the ladder is jv-brain's configuration, not the
  // HUD's to guess at).
  //
  // Refused: anything that is not a positive, finite number. `metrics` is
  // free-form by schema, so a string, a NaN, or the Infinity `1e999`
  // parses to would otherwise reach a screen as a requirement — and 0 is
  // not a floor either, it is a ladder that asks for nothing.
  readonly property real llmGpuFloorMb: {
    const m = root.brainMetrics;
    if (m === null)
      return -1;
    const mb = m.llm_gpu_floor_mb;
    return typeof mb === "number" && isFinite(mb) && mb > 0 ? mb : -1;
  }

  // jv-brain's free-form gauges, or null. Same expiry as everything else:
  // a rung read off a three-minute-old heartbeat describes a process that
  // may not be running.
  readonly property var brainMetrics: {
    const env = root.beats[root.brain];
    if (!env || root.lost(env, root.brain))
      return null;
    const m = env.body.metrics;
    if (!m)
      return null;
    return typeof m.llm_rung === "number" || typeof m.llm_gpu === "number" ? m : null;
  }

  // --- the heartbeats we are willing to believe ------------------------

  // service -> its last heartbeat, or null when the last frame from that
  // service is one we may not interpret. Null is a service on the roster
  // with nothing readable to say, which is a finding; a service missing
  // from this map has never spoken, which is not.
  readonly property var beats: {
    const bus = root.bus;
    let out = ({});
    if (!bus || !bus.linkUp || typeof bus.publishersOf !== "function" || typeof bus.latestFrom !== "function")
      return out;
    for (const service of bus.publishersOf("sys.health"))
      out[service] = root.trust(bus.latestFrom("sys.health", service), service);
    return out;
  }

  // The frame, or null if it is not one this file may read. Rejected:
  // a body from a schema version we were not written against (invariant
  // 2), no orderable `ts`, a heartbeat hedging its confidence (state
  // topics publish conf 1.0 — anything less disagrees with itself), a
  // body naming a DIFFERENT service than the envelope said published it,
  // and no usable `period_s`, which is how long we may believe it.
  function trust(env: var, service: string): var {
    if (!env || env.v !== 1 || typeof env.ts !== "number" || env.conf !== 1 || !env.body)
      return null;
    if (env.body.service !== service || !(env.body.period_s > 0))
      return null;
    return env;
  }

  // Has this heartbeat outlived the two periods the schema grants it?
  // `ageOf` is Infinity when the age is not knowable (no clock, no ts),
  // which fails this — an age we cannot compute is not an age we may
  // assume is zero. The timer below is the same test on a schedule, for
  // the case where no binding re-evaluates because nothing changed but
  // the time.
  function lost(env: var, service: string): bool {
    return root.expired[service] === true || root.ageOf(env) > env.body.period_s * 2;
  }

  function definedState(state: var): bool {
    return state === "starting" || state === "ok" || state === "degraded" || state === "error" || state === "stopping";
  }

  // How loudly a state deserves to be read. `ok` is 0 and is the only
  // state that is not a finding. `lost` and `unknown` rank above
  // `degraded` on purpose: a service that told us it is impaired is in
  // better shape than one we cannot hear at all.
  function rank(state: string): int {
    switch (state) {
    case "error":
      return 5;
    case "lost":
      return 4;
    case "unknown":
      return 3;
    case "degraded":
      return 2;
    case "starting":
    case "stopping":
      return 1;
    default:
      return 0;
    }
  }

  function byName(a: string, b: string): int {
    return a < b ? -1 : (a > b ? 1 : 0);
  }

  // --- letting go, on a schedule ---------------------------------------

  // Services whose last heartbeat has outlived it. Set by the timer
  // below and rebuilt on every frame. A plain property, not a computed
  // one: no binding re-evaluates because a clock moved, and that is
  // exactly the gap this closes.
  property var expired: ({})

  // Identity of the whole set of heartbeats currently believed — `seq` is
  // per-publisher and strictly increasing, so this changes exactly once
  // per frame, and once more whenever a service joins or leaves.
  readonly property string beatKey: {
    const beats = root.beats;
    let parts = [];
    for (const service of Object.keys(beats).sort())
      parts.push(service + ":" + (beats[service] === null ? "-" : beats[service].seq + "@" + beats[service].ts));
    return parts.join(",");
  }

  // The services the timer is currently counting down for — the ones
  // whose heartbeats run out soonest. When it fires, THEY are the ones
  // that have run out; nobody else has.
  property var dueNext: []

  onBeatKeyChanged: root.reassess()

  // ONE timer for the whole roster, armed for the SOONEST deadline among
  // the services still believed. Not one timer per service: the roster is
  // discovered at runtime, and a HUD with nothing on the bus should run no
  // timer at all (§06: 0 fps when nothing is happening). Every heartbeat
  // pushes its own deadline out, so on a healthy machine this is restarted
  // over and over and never actually fires.
  readonly property Timer lifespan: Timer {
    repeat: false
    onTriggered: root.expireDue()
  }

  // A frame arrived (or a service joined, or the link dropped): forget
  // every expiry and work the whole roster out again from the frames.
  // This is what revives a service that had gone quiet and came back.
  function reassess(): void {
    root.expired = ({});
    root.rearm();
  }

  // The timer ran out. What it was counting down for has outlived its
  // heartbeat — the wall clock waited those milliseconds, and that is the
  // evidence. Deliberately NOT a fresh age computation: re-asking the
  // clock here would mean a clock that has not moved un-expires a claim
  // and re-arms, over and over, which is a spin instead of a HUD.
  function expireDue(): void {
    let gone = ({});
    for (const service in root.expired)
      gone[service] = true;
    for (const service of root.dueNext)
      gone[service] = true;
    root.expired = gone;
    root.rearm();
  }

  // Arm for the soonest deadline among the services still believed. A
  // heartbeat that was already too old when it arrived needs no timer —
  // `lost()` can see that from its age alone.
  function rearm(): void {
    const beats = root.beats;
    let soonest = Infinity;
    let due = [];
    for (const service in beats) {
      const env = beats[service];
      if (env === null || root.expired[service] === true)
        continue;
      // Whatever is LEFT of the two periods: a frame that spent time in
      // flight is already partway through its own life.
      const left = env.body.period_s * 2 - root.ageOf(env);
      if (!(left > 0))
        continue;
      if (left < soonest) {
        soonest = left;
        due = [service];
      } else if (left === soonest) {
        due.push(service);
      }
    }
    root.dueNext = due;
    if (!(soonest < Infinity)) {
      root.lifespan.running = false;
      return;
    }
    root.lifespan.interval = Math.max(1, Math.ceil(soonest * 1000));
    root.lifespan.restart();
  }

  function ageOf(envelope: var): real {
    return root.bus && typeof root.bus.ageOf === "function" ? root.bus.ageOf(envelope) : Infinity;
  }
}
