// HealthState — "is anything wrong with Jarvis?", under test (PLAN A6).
//
// The glance is a REPORT, and a report that is wrong is worse than no
// report at all. The two ways it can lie:
//
//   · inventing trouble — a service reported as dead because the HUD
//     could not read its heartbeat. Cry wolf twice and nobody looks at
//     the corner again.
//   · staying quiet over real trouble — a service that stopped
//     heartbeating three minutes ago still shown as `ok`, or simply
//     omitted, because the HUD kept the last frame it liked.
//
// Both come out of the same rule: the HUD reports on services it has
// HEARD, it stops believing a heartbeat after the two periods the schema
// gives it, and anything it cannot read is `unknown` rather than fine.
// Nothing here ever invents a roster — there is no list anywhere of which
// services are supposed to be running, so a service that never started is
// absent, and absence is not a claim.
//
// Headless, like the rest of core/: HealthState is pure QtQuick and reads
// the bus through core/BusModel, driven with the same JSON lines the
// bridge writes.
import QtQuick
import QtTest
import "../core"

TestCase {
  id: suite
  name: "HealthState"

  // A stand-in for CLOCK_MONOTONIC the test drives. Frames are sent with
  // ts = fakeNow + 100, so the model pins an offset of exactly 100 and a
  // frame lands zero seconds old.
  property real fakeNow: 0
  property int seq: 1

  Component {
    id: busModel
    BusModel {}
  }

  Component {
    id: healthState
    HealthState {}
  }

  // createObject() is typed QObject, so every member read on the result
  // would be `missing-property` to qmllint. Going through an untyped
  // helper keeps the file lint-clean (see tst_speechstate).
  function spawn(component) {
    const o = component.createObject(suite);
    verify(o, "failed to instantiate a test object");
    return o;
  }

  // opts: { clock: false } to withhold the monotonic clock,
  //       { down: true } to leave the bridge link down.
  function makeHealth(opts) {
    const o = opts || {};
    suite.fakeNow = 0;
    const bus = spawn(busModel);
    if (o.clock !== false)
      bus.monotonic = () => suite.fakeNow;
    const health = spawn(healthState);
    health.bus = bus;
    if (o.down !== true)
      bus.ingest('{"t":"link","up":true}');
    return health;
  }

  // One heartbeat from `service`. `body` and `env` override the defaults,
  // so a test can say exactly which field it is breaking.
  function beat(health, service, state, body, env) {
    let b = {
      "service": service,
      "state": state,
      "uptime_s": 30,
      "period_s": 5
    };
    for (const k in body || {})
      b[k] = body[k];
    let e = {
      "topic": "sys.health",
      "ts": suite.fakeNow + 100,
      "seq": suite.seq++,
      "src": service,
      "conf": 1.0,
      "v": 1,
      "body": b
    };
    for (const k in env || {})
      e[k] = env[k];
    health.bus.ingest(JSON.stringify({
      "t": "frame",
      "frame": e
    }));
  }

  // The roster entry for one service, or null. The roster is small and
  // this keeps the assertions about the reading rather than the index.
  function entry(health, service) {
    for (const e of health.roster)
      if (e.service === service)
        return e;
    return null;
  }

  // A bus that answers in whatever order and link state the test asks
  // for. Driving HealthState through a real BusModel can never prove
  // HealthState sorts its roster or refuses a dead link, because BusModel
  // already sorts its publishers and empties itself when the link drops —
  // and "something upstream happens to do it" is a coincidence, not a
  // guarantee. This is the same API, minus the good manners.
  Component {
    id: stubBus

    QtObject {
      id: stub

      property bool linkUp: true
      // service -> its heartbeat, and the order publishersOf reports the
      // services in, verbatim.
      property var beats: ({})
      property var order: []

      function publishersOf(topic) {
        return topic === "sys.health" ? stub.order : [];
      }

      function latestFrom(topic, src) {
        const env = stub.beats[src];
        return topic === "sys.health" && env !== undefined ? env : null;
      }

      function ageOf(envelope) {
        return envelope ? 0 : Infinity;
      }
    }
  }

  // Every named service, degraded, handed over in exactly the order given.
  function makeStubbed(services, linkUp) {
    const bus = spawn(stubBus);
    let beats = ({});
    for (const service of services)
      beats[service] = {
        "topic": "sys.health",
        "ts": 100,
        "seq": 1,
        "src": service,
        "conf": 1.0,
        "v": 1,
        "body": {
          "service": service,
          "state": "degraded",
          "uptime_s": 5,
          "period_s": 5
        }
      };
    bus.beats = beats;
    bus.order = services;
    bus.linkUp = linkUp !== false;
    const health = spawn(healthState);
    health.bus = bus;
    return health;
  }

  // --- nothing heard is never "everything is fine" --------------------

  function test_without_a_bus_nothing_is_known() {
    const health = spawn(healthState);
    compare(health.roster.length, 0);
    compare(health.findingCount, 0);
    verify(!health.known);
    verify(!health.reporting);
  }

  function test_a_link_that_is_down_knows_nothing() {
    const health = makeHealth({
      down: true
    });
    compare(health.roster.length, 0);
    verify(!health.known);
  }

  function test_a_live_bus_with_no_heartbeats_reports_on_nobody() {
    // Not "all clear": the HUD has heard from no service, so it has
    // nothing to say about any. Absence is not a claim in either
    // direction.
    const health = makeHealth();
    compare(health.roster.length, 0);
    compare(health.findingCount, 0);
    verify(health.known, "the bus itself is visible, which is a different question");
  }

  function test_losing_the_link_forgets_every_service() {
    const health = makeHealth();
    beat(health, "jv-ears", "degraded");
    compare(health.findingCount, 1);
    health.bus.ingest('{"t":"link","up":false,"err":"bridge died"}');
    compare(health.roster.length, 0, "a bus we cannot see has no services on it");
    compare(health.findingCount, 0);
    verify(!health.known);
  }

  // --- the reading itself ---------------------------------------------

  function test_a_healthy_service_is_on_the_roster_and_is_not_a_finding() {
    const health = makeHealth();
    beat(health, "jv-ears", "ok");
    compare(health.roster.length, 1);
    compare(suite.entry(health, "jv-ears").state, "ok");
    compare(suite.entry(health, "jv-ears").severity, 0);
    compare(health.findingCount, 0, "§06: a well machine earns an empty corner");
    verify(!health.reporting);
  }

  function test_a_degraded_service_is_a_finding_and_keeps_its_note() {
    // `notes` is the schema's human-readable detail for exactly this
    // case, and it is the difference between "something is wrong" and
    // "the brain fell back to the CPU".
    const health = makeHealth();
    beat(health, "jv-brain", "degraded", {
      "notes": "llm error: connection refused"
    });
    compare(health.findingCount, 1);
    compare(health.findings[0].service, "jv-brain");
    compare(health.findings[0].state, "degraded");
    compare(health.findings[0].notes, "llm error: connection refused");
    verify(health.reporting);
  }

  function test_an_error_outranks_a_degradation() {
    const health = makeHealth();
    beat(health, "jv-voice", "degraded");
    beat(health, "jv-ears", "error");
    compare(health.findingCount, 2);
    compare(health.findings[0].service, "jv-ears", "the worst thing is read first");
    verify(health.findings[0].severity > health.findings[1].severity);
  }

  function test_starting_and_stopping_are_reported_but_rank_lowest() {
    // Transient, and worth showing — a service that has been `starting`
    // for a minute is a finding whether or not it ever says so itself.
    const health = makeHealth();
    beat(health, "jv-context", "starting");
    beat(health, "jv-guard", "stopping");
    beat(health, "jv-brain", "degraded");
    compare(health.findingCount, 3);
    compare(health.findings[0].service, "jv-brain");
    compare(health.findings[1].service, "jv-context", "equal rank sorts by name");
    compare(health.findings[2].service, "jv-guard");
  }

  function test_only_the_unwell_services_are_findings() {
    const health = makeHealth();
    for (const s of ["jv-voice", "jv-ears", "jv-guard"])
      beat(health, s, "ok");
    beat(health, "jv-brain", "error");
    compare(health.roster.length, 4);
    compare(health.findingCount, 1);
    compare(health.findings[0].service, "jv-brain");
  }

  function test_the_roster_is_sorted_by_service_name() {
    const health = makeHealth();
    for (const s of ["jv-voice", "jv-act", "jv-ears"])
      beat(health, s, "ok");
    compare(health.roster[0].service, "jv-act");
    compare(health.roster[1].service, "jv-ears");
    compare(health.roster[2].service, "jv-voice");
  }

  function test_a_newer_heartbeat_replaces_what_the_last_one_said() {
    const health = makeHealth();
    beat(health, "jv-brain", "degraded");
    compare(health.findingCount, 1);
    beat(health, "jv-brain", "ok");
    compare(health.findingCount, 0, "it recovered and said so");
    compare(suite.entry(health, "jv-brain").state, "ok");
  }

  // --- a heartbeat we cannot read is not an all-clear ------------------

  function test_a_frame_from_an_unknown_schema_version_is_unknown_not_ok() {
    // Invariant 2: the body of a v2 sys.health is not a shape this file
    // was written against, so it is not a shape this file may interpret.
    const health = makeHealth();
    beat(health, "jv-ears", "ok", {}, {
      "v": 2
    });
    compare(suite.entry(health, "jv-ears").state, "unknown");
    compare(health.findingCount, 1, "a service we cannot read is a finding");
  }

  function test_a_hedged_heartbeat_is_refused() {
    // sys.health is published at conf 1.0 by contract. Anything less is a
    // frame disagreeing with itself.
    const health = makeHealth();
    beat(health, "jv-ears", "ok", {}, {
      "conf": 0.6
    });
    compare(suite.entry(health, "jv-ears").state, "unknown");
  }

  function test_a_body_naming_a_different_service_than_published_it_is_refused() {
    // schemas/sys.health.json: `service` matches the envelope `src`.
    const health = makeHealth();
    beat(health, "jv-ears", "ok", {
      "service": "jv-brain"
    });
    compare(suite.entry(health, "jv-ears").state, "unknown");
  }

  function test_a_heartbeat_without_a_period_cannot_be_trusted_for_long() {
    // period_s is how long a frame speaks for. Without it there is no
    // expiry, and a heartbeat with no expiry never stops claiming health.
    const health = makeHealth();
    beat(health, "jv-ears", "ok", {
      "period_s": 0
    });
    compare(suite.entry(health, "jv-ears").state, "unknown");
  }

  function test_a_heartbeat_with_no_ts_cannot_be_aged_and_is_refused() {
    const health = makeHealth();
    beat(health, "jv-ears", "ok", {}, {
      "ts": "soon"
    });
    compare(suite.entry(health, "jv-ears").state, "unknown");
  }

  function test_a_state_word_the_schema_does_not_define_is_never_rendered() {
    // The enum is frozen. A word outside it is a service we do not
    // understand, and the HUD must not put an unvetted string on screen.
    const health = makeHealth();
    beat(health, "jv-ears", "vibing");
    compare(suite.entry(health, "jv-ears").state, "unknown");
  }

  function test_with_no_clock_no_heartbeat_can_be_aged_and_none_is_believed() {
    const health = makeHealth({
      clock: false
    });
    beat(health, "jv-ears", "ok");
    compare(suite.entry(health, "jv-ears").state, "lost");
  }

  // --- heartbeats stop describing the present -------------------------

  function test_a_heartbeat_older_than_two_periods_is_lost() {
    // schemas/sys.health.json: missing 2 consecutive periods = presumed
    // dead. Nothing publishes "jv-ears died", so this is the only way the
    // HUD ever learns it.
    const health = makeHealth();
    beat(health, "jv-voice", "ok");
    beat(health, "jv-ears", "ok", {
      "period_s": 5
    }, {
      "ts": suite.fakeNow + 100 - 11
    });
    compare(suite.entry(health, "jv-ears").state, "lost");
    compare(suite.entry(health, "jv-voice").state, "ok", "one silence is not everyone's");
    compare(health.findingCount, 1);
  }

  function test_a_lost_service_outranks_a_merely_degraded_one() {
    const health = makeHealth();
    beat(health, "jv-brain", "degraded");
    beat(health, "jv-ears", "ok", {
      "period_s": 1
    }, {
      "ts": suite.fakeNow + 100 - 9
    });
    compare(health.findings[0].service, "jv-ears");
    compare(health.findings[0].state, "lost");
  }

  function test_a_service_goes_lost_on_its_own_when_the_heartbeats_stop() {
    const health = makeHealth();
    beat(health, "jv-ears", "ok", {
      "period_s": 0.025
    });
    compare(health.findingCount, 0);
    tryCompare(health, "findingCount", 1, 3000, "a heartbeat must expire on its own");
    compare(suite.entry(health, "jv-ears").state, "lost");
  }

  function test_the_next_heartbeat_revives_a_service_that_had_gone_quiet() {
    const health = makeHealth();
    beat(health, "jv-ears", "ok", {
      "period_s": 0.025
    });
    tryCompare(health, "findingCount", 1, 3000);
    suite.fakeNow += 1;
    beat(health, "jv-ears", "ok");
    compare(health.findingCount, 0);
    compare(suite.entry(health, "jv-ears").state, "ok");
  }

  function test_services_expire_on_their_own_schedules() {
    // One timer serves the whole roster, so the short-lived heartbeat
    // must not drag the long-lived one down with it — or take its own
    // deadline from somebody else's period.
    const health = makeHealth();
    beat(health, "jv-ears", "ok", {
      "period_s": 0.025
    });
    beat(health, "jv-voice", "ok", {
      "period_s": 30
    });
    tryCompare(health, "findingCount", 1, 3000);
    compare(suite.entry(health, "jv-ears").state, "lost");
    compare(suite.entry(health, "jv-voice").state, "ok");
  }

  function test_a_late_heartbeat_gets_only_what_is_left_of_its_life() {
    const health = makeHealth();
    beat(health, "jv-voice", "ok");
    beat(health, "jv-ears", "ok", {
      "period_s": 0.25
    }, {
      "ts": suite.fakeNow + 100 - 0.45
    });
    compare(health.findingCount, 0);
    tryCompare(health, "findingCount", 1, 150, "0.05 s of the 0.5 s was left, not 0.5 s");
  }

  // --- the llm rung ----------------------------------------------------

  function test_the_rung_is_read_from_the_brains_own_heartbeat() {
    const health = makeHealth();
    beat(health, "jv-brain", "ok", {
      "metrics": {
        "llm_rung": 0.0,
        "llm_gpu": 1.0
      }
    });
    compare(health.llmRung, 0);
    compare(health.llmBackend, "gpu");
    verify(!health.llmOnCpu);
    verify(!health.reporting, "a brain on the GPU is the ordinary case and says nothing");
  }

  function test_a_brain_on_the_cpu_is_worth_saying_out_loud() {
    // Invariant 6: rung 4 is the CPU floor — alive, and seconds per
    // token. Nothing else on screen would explain why Jarvis got slow.
    const health = makeHealth();
    beat(health, "jv-brain", "ok", {
      "metrics": {
        "llm_rung": 4.0,
        "llm_gpu": 0.0
      }
    });
    compare(health.llmRung, 4);
    compare(health.llmBackend, "cpu");
    verify(health.llmOnCpu);
    verify(health.reporting, "it is not a fault, but it is not nothing either");
    compare(health.findingCount, 0, "the brain itself said it was ok");
  }

  function test_a_brain_that_reports_no_rung_is_not_a_brain_on_the_gpu() {
    const health = makeHealth();
    beat(health, "jv-brain", "ok");
    compare(health.llmRung, -1);
    compare(health.llmBackend, "unknown");
    verify(!health.llmOnCpu);
  }

  function test_another_services_metrics_are_not_the_brains() {
    const health = makeHealth();
    beat(health, "jv-ears", "ok", {
      "metrics": {
        "llm_rung": 4.0,
        "llm_gpu": 0.0
      }
    });
    compare(health.llmRung, -1);
    compare(health.llmBackend, "unknown", "jv-ears cannot see the model");
  }

  function test_a_stale_brain_heartbeat_is_not_a_rung_reading() {
    const health = makeHealth();
    beat(health, "jv-voice", "ok");
    beat(health, "jv-brain", "ok", {
      "period_s": 5,
      "metrics": {
        "llm_rung": 4.0,
        "llm_gpu": 0.0
      }
    }, {
      "ts": suite.fakeNow + 100 - 11
    });
    compare(health.llmBackend, "unknown", "the brain may not even be running");
    compare(health.llmRung, -1);
    compare(suite.entry(health, "jv-brain").state, "lost");
  }

  // --- what the card would have to give back (B46) ---------------------

  function test_the_floor_is_read_from_the_brains_own_heartbeat() {
    // jv-brain publishes it only while something is waiting on it: a
    // brain on the CPU, on a machine that HAS a card. 5424 MiB is ares'
    // own ladder — the cheapest GPU rung, of a 6144 MiB card.
    const health = makeHealth();
    beat(health, "jv-brain", "ok", {
      "metrics": {
        "llm_rung": 4.0,
        "llm_gpu": 0.0,
        "llm_gpu_floor_mb": 5424.0
      }
    });
    compare(health.llmGpuFloorMb, 5424);
  }

  function test_a_brain_that_names_no_floor_is_not_a_brain_that_needs_nothing() {
    // The ordinary case for a brain already on the GPU, and for a machine
    // with no card at all: jv-brain withholds the gauge, and the HUD may
    // not fill the gap with a ladder it cannot read (invariant 1).
    const health = makeHealth();
    beat(health, "jv-brain", "ok", {
      "metrics": {
        "llm_rung": 4.0,
        "llm_gpu": 0.0
      }
    });
    verify(health.llmOnCpu);
    compare(health.llmGpuFloorMb, -1);
  }

  function test_another_services_floor_is_not_the_brains() {
    const health = makeHealth();
    beat(health, "jv-ears", "ok", {
      "metrics": {
        "llm_rung": 4.0,
        "llm_gpu": 0.0,
        "llm_gpu_floor_mb": 5424.0
      }
    });
    compare(health.llmGpuFloorMb, -1, "jv-ears does not own the ladder");
  }

  function test_a_stale_brain_heartbeat_is_not_a_floor() {
    const health = makeHealth();
    beat(health, "jv-voice", "ok");
    beat(health, "jv-brain", "ok", {
      "period_s": 5,
      "metrics": {
        "llm_rung": 4.0,
        "llm_gpu": 0.0,
        "llm_gpu_floor_mb": 5424.0
      }
    }, {
      "ts": suite.fakeNow + 100 - 11
    });
    compare(health.llmGpuFloorMb, -1, "a requirement off a dead brain describes nothing");
  }

  // `metrics` is free-form by schema, so anything at all can arrive under
  // this name from a service that meant something else by it — and every
  // one of these would render as a requirement if it were let through. 0
  // is on the list because it is not a floor: it is a ladder that asks
  // for nothing, which no rung on jv-brain's does.
  function test_a_floor_that_is_not_a_quantity_is_not_a_floor() {
    for (const bad of ["5424", true, null, 0.0, -1.0]) {
      const health = makeHealth();
      beat(health, "jv-brain", "ok", {
        "metrics": {
          "llm_rung": 4.0,
          "llm_gpu": 0.0,
          "llm_gpu_floor_mb": bad
        }
      });
      compare(health.llmGpuFloorMb, -1, String(bad) + " is not a VRAM requirement");
    }
  }

  // The two that cannot arrive as a bridge line — QML's JSON parser
  // refuses a `1e999` or a NaN whole, and core/BusModel drops the line —
  // but `bus` is duck-typed, and the shot harness already hands these
  // elements bodies built in QML rather than parsed from a line. So the
  // guard is reachable by the path a stub takes, and it is tested by that
  // path: `NEEDS Infinity MiB` is not a thing to put on a screen.
  function test_a_floor_that_is_not_a_number_of_mebibytes_is_not_a_floor() {
    for (const bad of [Infinity, -Infinity, NaN]) {
      const health = suite.makeStubbed(["jv-brain"]);
      let env = health.bus.beats["jv-brain"];
      env.body.metrics = {
        "llm_rung": 4.0,
        "llm_gpu": 0.0,
        "llm_gpu_floor_mb": bad
      };
      // Reassigned whole rather than mutated in place: `beats` is a var
      // property, and a binding does not re-run because an object it
      // already holds grew a field.
      health.bus.beats = ({ "jv-brain": env });
      verify(health.llmOnCpu, "the stub really is a brain on the CPU floor");
      compare(health.llmGpuFloorMb, -1, bad + " is not a number of mebibytes");
    }
  }

  function test_a_degraded_brain_still_reports_which_rung_it_is_on() {
    // Both facts at once, and they are different facts: the service is
    // impaired AND the model is on the CPU floor.
    const health = makeHealth();
    beat(health, "jv-brain", "degraded", {
      "notes": "llm fell back to CPU",
      "metrics": {
        "llm_rung": 4.0,
        "llm_gpu": 0.0
      }
    });
    compare(health.findingCount, 1);
    compare(health.findings[0].state, "degraded");
    verify(health.llmOnCpu);
    compare(health.llmRung, 4);
  }

  // --- the guarantees this file makes on its own ----------------------

  function test_the_roster_is_sorted_here_not_upstream() {
    const health = suite.makeStubbed(["jv-voice", "jv-ears", "jv-act"]);
    compare(health.roster.length, 3);
    compare(health.roster[0].service, "jv-act");
    compare(health.roster[1].service, "jv-ears");
    compare(health.roster[2].service, "jv-voice");
  }

  function test_equally_bad_findings_are_tied_by_name_here_not_upstream() {
    // Three services, one severity between them. Without a tiebreak of
    // its own the list would inherit whatever order the bus offered, and
    // reshuffle under the reader's eye whenever that order changed.
    const health = suite.makeStubbed(["jv-voice", "jv-ears", "jv-act"]);
    compare(health.findingCount, 3);
    compare(health.findings[0].service, "jv-act");
    compare(health.findings[1].service, "jv-ears");
    compare(health.findings[2].service, "jv-voice");
  }

  function test_a_bus_that_says_the_link_is_down_is_not_read_at_all() {
    // Invariant 10: not one pixel comes from a cache the link no longer
    // backs. BusModel empties itself on a drop as well; this element does
    // not get to rely on that.
    const health = suite.makeStubbed(["jv-ears", "jv-brain"], false);
    compare(health.roster.length, 0);
    compare(health.findingCount, 0);
    verify(!health.known);
  }
}
