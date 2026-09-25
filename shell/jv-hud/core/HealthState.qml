// HealthState — is anything wrong with Jarvis right now? (A6)
//
// Every service heartbeats on `sys.health` (schemas/sys.health.json): a
// state word, how long it has been up, and how often it promises to speak
// again. This turns that stream into the one thing a glance needs — a
// short list of what is NOT well — and into the llm rung, which is the
// single number that explains why Jarvis got slow.
//
// Four rules hold it to the truth:
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
//   · **A service that keeps dying does not get to say it is fine** (A78).
//     Every unit in `modules/jarvis-services.nix` is `Restart=on-failure`,
//     so a service that crashes is replaced by a new process that
//     heartbeats `starting`, then `ok` — and until this rule the corner
//     over a jv-ears dying every eight seconds was EMPTY. `uptime_s` is
//     the field that gives it away: it counts from one process's own
//     start, so it only ever rises while that process lives, and a
//     heartbeat carrying LESS of it than the last one from the same
//     service was written by a different process. That is observed here
//     and nowhere else on the bus — nothing publishes "I was restarted",
//     and a service that could would be the one least able to, having
//     just lost the memory.
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

  // The link went down: forget how many processes there have been (A78).
  //
  // Here and not in `observe()` below, which is the pass every frame
  // drives: core/BusModel.qml's `applyLink` empties its caches BEFORE it
  // lowers `linkUp`, so the pass a drop triggers still sees a live link
  // with nothing on it, and the flag falls afterwards with no frame left
  // to notice it. The falling edge of the link is the event, so it is what
  // this listens to — and a bus that keeps its frames through a drop
  // (which a `BusModel` never does, and a test therefore has to be written
  // by hand) is forgotten by the same line.
  onKnownChanged: {
    if (!root.known)
      root.lives = ({});
  }

  // Every service heard from, sorted by name:
  //   { service, state, severity, notes, restarts }
  // `state` is one of the schema's five words, plus `lost` (heartbeats
  // stopped), `unknown` (heard, unreadable) and `restarted` (its uptime
  // went backwards). Never a word off the wire that the schema does not
  // define — including those three: a heartbeat that SAYS `restarted` is
  // outside the frozen enum and comes out `unknown`, like any other word
  // this file did not derive itself.
  //
  // `restarts` is how many times this service's uptime has been seen to go
  // backwards since the link came up, and it is carried whether or not the
  // word is `restarted`: a service with something worse to say keeps its
  // own word (below), and the count is still the truth about its process.
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
      // A process that died and came back is not `ok`, whatever its newest
      // heartbeat says — that heartbeat was written by the replacement. It
      // overrides only the words that are not themselves trouble (`ok`,
      // `starting`, `stopping`), and the tie with `degraded` goes to the
      // SERVICE: a service reporting on itself knows something this file
      // inferred from a number, and `restarts` stays on the entry either
      // way for whoever wants both.
      const restarts = root.restartsOf(service, env);
      if (restarts > 0 && root.rank(state) < root.rank("restarted"))
        state = "restarted";
      out.push({
        "service": service,
        "state": state,
        "severity": root.rank(state),
        "notes": notes,
        "restarts": restarts
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
    if (env.body.service !== service)
      return null;
    // A NUMBER, and not merely something that compares greater than zero:
    // `"5" > 0` is true in JavaScript, so a period arriving as a string used
    // to be believed and then multiplied — by `lost`, by `rearm`'s timer
    // interval, and now by the freshness window `restartsOf` reads. It was
    // harmless while every use was multiplication of a coercible string;
    // it is not the kind of thing to leave standing once one of the uses is
    // a window inside which the HUD calls a service unwell. (core/
    // DropState.qml writes the same test, and said so about this one.)
    if (typeof env.body.period_s !== "number" || !isFinite(env.body.period_s) || env.body.period_s <= 0)
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
  //
  // `restarted` ties with `degraded` rather than outranking it, and the tie
  // is the claim: the service is running and answering — it is alive and
  // impaired, which is the bracket `degraded` names. Ranking a completed
  // death above a live impairment would also put it above every degraded
  // service in a list only three lines deep, so one crash at boot would
  // push a jv-voice that cannot reach the speakers off the plate.
  function rank(state: string): int {
    switch (state) {
    case "error":
      return 5;
    case "lost":
      return 4;
    case "unknown":
      return 3;
    case "restarted":
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

  // --- the process behind the heartbeat (A78) --------------------------

  // service -> { uptime, restarts }: the last `uptime_s` this file read for
  // that service, and how many times it has been seen to go BACKWARDS.
  //
  // A plain property, written by `observe()` below, because this is a
  // MEMORY and not a reading: `bus.latestFrom` keeps one frame per
  // publisher, so the beat that would prove a restart is gone by the time
  // the next one lands. Nothing else in this file remembers anything, and
  // that is the point — it is why a restart is the one fact here that
  // cannot be recomputed from what is currently on the bus.
  //
  // Forgotten the moment the link drops, and not kept across it. A HUD that
  // could not see the bus does not know how many processes came and went
  // while it was blind, and a count that silently spans a gap of unknown
  // length is a number that means something different from what it says.
  // Coming back it is a first sighting again, which claims nothing.
  property var lives: ({})

  // How many restarts are worth SAYING about this service right now: the
  // remembered count, but only while the process that is heartbeating is
  // still young enough for its own arrival to be the news.
  //
  // Young enough is `period_s * 2` — the same span this file already grants
  // one heartbeat, and deliberately not a new constant. It reads off the
  // frame's own body, so nothing here needs a clock or a timer: every
  // heartbeat carries a larger `uptime_s` than the last, and the row leaves
  // on the beat that carries one too large. A service crash-looping inside
  // that window never stops reporting, which is the case this exists for;
  // a service that restarted once an hour ago says nothing until it does it
  // again, and then says 2.
  function restartsOf(service: string, env: var): int {
    const life = root.lives[service];
    if (life === undefined || !(life.restarts > 0) || env === null)
      return 0;
    const up = root.uptimeOf(env);
    return up >= 0 && up < env.body.period_s * 2 ? life.restarts : 0;
  }

  // `uptime_s` as a number, or NEGATIVE when this file may not read it.
  // Required by the schema and still checked, because the whole claim is a
  // comparison: `"5" < 120` is true in JavaScript, so a string uptime would
  // manufacture a restart out of a service that had merely published its
  // number in quotes.
  //
  // The schema's own minimum is 0, and a reading below it is refused by the
  // SAME `< 0` its callers recognise a refusal by — one comparison rather
  // than two that could come to disagree about whether -5 is a reading.
  // Hence "negative" and not "-1": a negative on the wire arrives as its
  // own refusal.
  //
  // An unreadable one refuses the restart claim ONLY — not the heartbeat.
  // `trust()` rejects the fields this file needs in order to interpret a
  // frame at all; a broken `uptime_s` leaves the service's own state word
  // perfectly readable, and turning a jv-voice that is shouting `error`
  // into `unknown` over a field about its age would lose the louder fact.
  function uptimeOf(env: var): real {
    if (env === null)
      return -1;
    const up = env.body.uptime_s;
    return typeof up === "number" && isFinite(up) ? up : -1;
  }

  // Take note of every uptime currently on the bus, and of every one that
  // went backwards since the last look. Called from `onBeatKeyChanged`, so
  // it runs exactly once per frame and once more whenever a service joins
  // or the link moves.
  //
  // Nothing here needs to ask whether the link is up: `beats` is empty
  // while it is down, so this pass has nothing to read, and the forgetting
  // is `onKnownChanged`'s (above).
  //
  // A service whose newest frame is unreadable is SKIPPED rather than
  // forgotten: the next good frame is then compared against the last good
  // one, which is the comparison that means something. Being skipped is
  // also why a first sighting claims nothing — with nothing remembered
  // there is no direction for the number to have moved in, and a small
  // `uptime_s` on the first beat the HUD ever hears is what every service
  // looks like on a machine that just booted.
  function observe(): void {
    const beats = root.beats;
    let out = ({});
    for (const service in root.lives)
      out[service] = root.lives[service];
    for (const service in beats) {
      const up = root.uptimeOf(beats[service]);
      if (up < 0)
        continue;
      const seen = out[service];
      out[service] = ({
        "uptime": up,
        "restarts": seen === undefined ? 0 : (up < seen.uptime ? seen.restarts + 1 : seen.restarts)
      });
    }
    root.lives = out;
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

  onBeatKeyChanged: {
    // Before `reassess`, and the order is not arbitrary: `observe` reads
    // the uptimes off the frames, and `reassess` is about the timer that
    // decides which of them are still believed. Neither reads the other's
    // output, and running them in the other order would work — but the
    // memory is written from the frame that just arrived, so it belongs
    // first, next to the arrival.
    root.observe();
    root.reassess();
  }

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
