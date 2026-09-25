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

  // --- the process behind the heartbeat (A78) -------------------------
  //
  // Every unit in modules/jarvis-services.nix is `Restart=on-failure`, so
  // the interesting failure is not a service reporting trouble — it is a
  // service that has died four times in a minute and whose newest
  // heartbeat, written by the process that replaced it, says `ok`. Before
  // this section that machine drew an EMPTY corner, which §06 has taught
  // the reader to trust.
  //
  // The two ways the claim could be worse than that silence:
  //
  //   · inventing a death. `uptime_s` is a number off the wire and the
  //     claim is a COMPARISON, so a string, a NaN, or the first heartbeat
  //     the HUD ever hears are all ways to manufacture a restart out of a
  //     service that has been up for a week.
  //   · keeping the news after it is news. A count that stays on screen
  //     for the life of the process is the all-day gauge this plate
  //     exists not to be, and one that spans a link loss is a tally over
  //     a stretch the HUD could not see.

  function test_a_first_heartbeat_claims_no_restart() {
    // The honest shape of not knowing, and the ordinary shape of a boot: a
    // small `uptime_s` is what EVERY service looks like on the first frame
    // the HUD hears, and with nothing remembered there is no direction for
    // the number to have moved in.
    const health = makeHealth();
    beat(health, "jv-ears", "ok", {
      "uptime_s": 3
    });
    compare(suite.entry(health, "jv-ears").state, "ok");
    compare(suite.entry(health, "jv-ears").restarts, 0);
    compare(health.findingCount, 0);
    verify(!health.reporting, "an empty corner, which is the truth here");
  }

  function test_a_rising_uptime_claims_no_restart() {
    const health = makeHealth();
    beat(health, "jv-ears", "ok", {
      "uptime_s": 30
    });
    beat(health, "jv-ears", "ok", {
      "uptime_s": 35
    });
    compare(suite.entry(health, "jv-ears").state, "ok");
    compare(suite.entry(health, "jv-ears").restarts, 0);
  }

  function test_a_repeated_uptime_is_not_a_restart() {
    // Two heartbeats carrying the same number is a service whose clock
    // resolution is coarser than this test, not a process that died in
    // between. Strictly backwards, or nothing.
    //
    // Both inside the freshness window on purpose: at 30 s the window has
    // already closed, so a version of this file that DID call a repeat a
    // death would report nothing and the test would pass having proved
    // only that 30 is more than two periods.
    const health = makeHealth();
    beat(health, "jv-ears", "ok", {
      "uptime_s": 4
    });
    beat(health, "jv-ears", "ok", {
      "uptime_s": 4
    });
    compare(suite.entry(health, "jv-ears").state, "ok");
    compare(suite.entry(health, "jv-ears").restarts, 0);
  }

  function test_an_uptime_that_went_backwards_is_a_restart() {
    // The whole point: the service says `ok`, and it is not fine.
    const health = makeHealth();
    beat(health, "jv-ears", "ok", {
      "uptime_s": 900
    });
    compare(health.findingCount, 0, "a service that has been up 15 minutes");
    beat(health, "jv-ears", "ok", {
      "uptime_s": 4
    });
    compare(suite.entry(health, "jv-ears").state, "restarted");
    compare(suite.entry(health, "jv-ears").restarts, 1);
    compare(health.findingCount, 1);
    verify(health.reporting);
  }

  function test_a_restart_to_zero_is_still_a_restart() {
    // The schema's minimum, and the one a heartbeat published in the first
    // moments of a process really carries.
    const health = makeHealth();
    beat(health, "jv-ears", "ok", {
      "uptime_s": 30
    });
    beat(health, "jv-ears", "ok", {
      "uptime_s": 0
    });
    compare(suite.entry(health, "jv-ears").state, "restarted");
  }

  function test_the_count_climbs_with_every_death() {
    const health = makeHealth();
    beat(health, "jv-ears", "ok", {
      "uptime_s": 900
    });
    beat(health, "jv-ears", "ok", {
      "uptime_s": 4
    });
    // Alive for a moment, then gone again — which is what a crash loop
    // looks like from the bus.
    beat(health, "jv-ears", "ok", {
      "uptime_s": 9
    });
    compare(suite.entry(health, "jv-ears").restarts, 1, "still one death, one process");
    beat(health, "jv-ears", "ok", {
      "uptime_s": 2
    });
    compare(suite.entry(health, "jv-ears").restarts, 2);
    compare(suite.entry(health, "jv-ears").state, "restarted");
  }

  function test_one_service_restarting_says_nothing_about_another() {
    const health = makeHealth();
    beat(health, "jv-ears", "ok", {
      "uptime_s": 900
    });
    beat(health, "jv-voice", "ok", {
      "uptime_s": 900
    });
    beat(health, "jv-ears", "ok", {
      "uptime_s": 1
    });
    compare(suite.entry(health, "jv-ears").state, "restarted");
    compare(suite.entry(health, "jv-voice").state, "ok");
    compare(suite.entry(health, "jv-voice").restarts, 0);
    compare(health.findingCount, 1);
  }

  // --- how long a restart is news -------------------------------------

  function test_the_restart_leaves_when_the_new_process_is_no_longer_new() {
    // `period_s * 2` — the same span this file already grants one
    // heartbeat, read off the frame's own body, which is why no timer is
    // involved: the beat that carries too large an uptime is the one that
    // takes the row off.
    const health = makeHealth();
    beat(health, "jv-ears", "ok", {
      "uptime_s": 900,
      "period_s": 5
    });
    beat(health, "jv-ears", "ok", {
      "uptime_s": 4,
      "period_s": 5
    });
    compare(suite.entry(health, "jv-ears").state, "restarted");
    beat(health, "jv-ears", "ok", {
      "uptime_s": 9.9,
      "period_s": 5
    });
    compare(suite.entry(health, "jv-ears").state, "restarted", "still inside the window");
    beat(health, "jv-ears", "ok", {
      "uptime_s": 10,
      "period_s": 5
    });
    compare(suite.entry(health, "jv-ears").state, "ok");
    compare(suite.entry(health, "jv-ears").restarts, 0);
    compare(health.findingCount, 0, "one crash an hour ago is not a standing fault");
  }

  function test_the_window_is_the_services_own_period_and_not_a_constant() {
    // A service that beats every 30 s gets 60 s of being new. Nothing here
    // is tuned in seconds; it is the schema's own number, per service.
    const health = makeHealth();
    beat(health, "jv-voice", "ok", {
      "uptime_s": 900,
      "period_s": 30
    });
    beat(health, "jv-voice", "ok", {
      "uptime_s": 45,
      "period_s": 30
    });
    compare(suite.entry(health, "jv-voice").state, "restarted");
  }

  function test_the_count_survives_the_window_it_stopped_being_news_in() {
    // The row leaves and the memory does not: the second death is the
    // second death, and a count that reset every time the row went quiet
    // could never say a service had been doing this all afternoon.
    const health = makeHealth();
    beat(health, "jv-ears", "ok", {
      "uptime_s": 900
    });
    beat(health, "jv-ears", "ok", {
      "uptime_s": 1
    });
    beat(health, "jv-ears", "ok", {
      "uptime_s": 400
    });
    compare(suite.entry(health, "jv-ears").restarts, 0, "nothing to say right now");
    beat(health, "jv-ears", "ok", {
      "uptime_s": 1
    });
    compare(suite.entry(health, "jv-ears").restarts, 2);
  }

  function test_a_restart_only_noticed_late_is_counted_and_not_announced() {
    // The drop is real — a different process wrote the second frame — but
    // by the time the HUD saw one, the replacement had been up longer than
    // its own heartbeat is believed for. Counted, silent, and the count is
    // there the next time it happens.
    const health = makeHealth();
    beat(health, "jv-ears", "ok", {
      "uptime_s": 900,
      "period_s": 5
    });
    beat(health, "jv-ears", "ok", {
      "uptime_s": 40,
      "period_s": 5
    });
    compare(suite.entry(health, "jv-ears").state, "ok");
    compare(suite.entry(health, "jv-ears").restarts, 0);
    beat(health, "jv-ears", "ok", {
      "uptime_s": 2,
      "period_s": 5
    });
    compare(suite.entry(health, "jv-ears").restarts, 2);
  }

  // --- whose word wins ------------------------------------------------

  function test_a_service_with_something_worse_to_say_keeps_its_own_word() {
    // `degraded` and `restarted` tie, and the tie goes to the service: it
    // is reporting on itself, where this file inferred a death from a
    // number. The count stays on the entry regardless.
    const health = makeHealth();
    beat(health, "jv-voice", "ok", {
      "uptime_s": 900
    });
    beat(health, "jv-voice", "degraded", {
      "uptime_s": 2,
      "notes": "piper fell behind"
    });
    compare(suite.entry(health, "jv-voice").state, "degraded");
    compare(suite.entry(health, "jv-voice").notes, "piper fell behind");
    compare(suite.entry(health, "jv-voice").restarts, 1,
            "the count is the truth about the process either way");
  }

  function test_an_error_outranks_a_restart() {
    const health = makeHealth();
    beat(health, "jv-act", "ok", {
      "uptime_s": 900
    });
    beat(health, "jv-act", "error", {
      "uptime_s": 1
    });
    compare(suite.entry(health, "jv-act").state, "error");
    compare(health.findings[0].severity, 5);
  }

  function test_a_service_still_starting_after_a_death_says_so() {
    // The worst crash loop there is: a service that dies during startup
    // never reaches `ok`, so `starting` would be the only word it ever
    // published. `starting` is not trouble on its own — every service says
    // it once — and a restart outranks it for exactly that reason.
    const health = makeHealth();
    beat(health, "jv-ears", "ok", {
      "uptime_s": 900
    });
    beat(health, "jv-ears", "starting", {
      "uptime_s": 0.2
    });
    compare(suite.entry(health, "jv-ears").state, "restarted");
  }

  function test_a_restart_ranks_with_a_degraded_service_and_not_above_it() {
    // The list is three lines deep. A completed death ranking above a live
    // impairment would push a jv-voice that cannot reach the speakers off
    // the plate for a jv-ears that crashed once at boot.
    const health = makeHealth();
    beat(health, "jv-brain", "degraded", {
      "uptime_s": 900
    });
    beat(health, "jv-voice", "ok", {
      "uptime_s": 900
    });
    beat(health, "jv-voice", "ok", {
      "uptime_s": 1
    });
    compare(health.findingCount, 2);
    compare(health.findings[0].severity, health.findings[1].severity);
    compare(health.findings[0].service, "jv-brain", "the tie is broken by name, as ever");
  }

  function test_the_word_is_never_taken_off_the_wire() {
    // `restarted` is this file's own word, like `lost` and `unknown`. A
    // service publishing it is publishing a state outside the frozen enum,
    // and a HUD that passed it through would let any process claim a death
    // it never had.
    const health = makeHealth();
    beat(health, "jv-ears", "restarted");
    compare(suite.entry(health, "jv-ears").state, "unknown");
    compare(suite.entry(health, "jv-ears").restarts, 0);
  }

  // --- the numbers this file will not compare -------------------------

  function test_an_unreadable_uptime_claims_nothing_and_forgets_nothing() {
    // `"4" < 900` is true in JavaScript. A service publishing its uptime
    // in quotes would otherwise be reported dead — and the last GOOD
    // reading has to survive, or the comparison after it is against a
    // number this file never read.
    const health = makeHealth();
    beat(health, "jv-ears", "ok", {
      "uptime_s": 900
    });
    beat(health, "jv-ears", "ok", {
      "uptime_s": "4"
    });
    compare(suite.entry(health, "jv-ears").state, "ok");
    compare(suite.entry(health, "jv-ears").restarts, 0);
    beat(health, "jv-ears", "ok", {
      "uptime_s": 4
    });
    compare(suite.entry(health, "jv-ears").restarts, 1,
            "measured against the 900, which is the last thing that was read");
  }

  function test_an_infinite_uptime_is_not_a_reading() {
    // An infinity compares greater than everything, so it would become a
    // high-water mark no later heartbeat could rise above — and the next
    // honest number would read as a death, for the rest of the session.
    //
    // Through a hand-built bus, because JSON cannot carry it: core/
    // BusModel.qml refuses a line containing `1e999` WHOLE (there is a
    // test for that next door, in tst_earsbudgets.qml), so the bridge can
    // never deliver one. This element's contract is any bus offering
    // `latest`/`ageOf`, and the schema's type for this field is `number`,
    // of which an infinity is one — so the check is written rather than
    // inherited from whoever happens to be parsing today.
    //
    // A 1000 s heartbeat, which the schema allows and nothing on this
    // machine uses, because it is the only arrangement in which the damage
    // is VISIBLE: the number that follows the infinity has to be larger
    // than the one before it (or the restart is real) and still inside the
    // window a restart is news in (or the row says nothing either way).
    const bus = spawn(stubBus);
    const health = spawn(healthState);
    health.bus = bus;
    bus.order = ["jv-ears"];
    bus.beats = ({
      "jv-ears": suite.stubBeat("jv-ears", 900, 1000)
    });
    bus.beats = ({
      "jv-ears": suite.stubBeat("jv-ears", Infinity, 1000)
    });
    bus.beats = ({
      "jv-ears": suite.stubBeat("jv-ears", 950, 1000)
    });
    compare(suite.entry(health, "jv-ears").state, "ok");
    compare(suite.entry(health, "jv-ears").restarts, 0);
  }

  function test_a_negative_uptime_is_not_a_reading() {
    // Below the schema's own minimum. A process is not up for -1 seconds,
    // and a number that low would be a restart against every real one.
    const health = makeHealth();
    beat(health, "jv-ears", "ok", {
      "uptime_s": 900
    });
    beat(health, "jv-ears", "ok", {
      "uptime_s": -1
    });
    compare(suite.entry(health, "jv-ears").state, "ok");
    compare(suite.entry(health, "jv-ears").restarts, 0);
  }

  function test_a_missing_uptime_is_not_a_reading() {
    // Required by the schema, which is not the same as present on the
    // wire. `undefined < 900` is false, so an absent field would not have
    // manufactured a restart — but it would have been remembered as one.
    const health = makeHealth();
    beat(health, "jv-ears", "ok", {
      "uptime_s": 900
    });
    beat(health, "jv-ears", "ok", {
      "uptime_s": undefined
    });
    beat(health, "jv-ears", "ok", {
      "uptime_s": 3
    });
    compare(suite.entry(health, "jv-ears").restarts, 1,
            "3 is below the 900, and the frame between them said nothing");
  }

  function test_an_unreadable_frame_between_two_rising_uptimes_changes_nothing() {
    // The other way the skip can go wrong, and it is not the same test as
    // the one above: a version that RECORDED the refusal would write a
    // sentinel as the high-water mark AND count the drop to it as a death.
    // The second mistake hides the first — the next honest number is above
    // the sentinel, so no further death is counted, and the tally is right
    // by one wrong step in each direction. Only a rising uptime after the
    // gap can tell them apart, which again wants a window wide enough to
    // still call 950 new.
    const health = makeHealth();
    beat(health, "jv-ears", "ok", {
      "uptime_s": 900,
      "period_s": 1000
    });
    beat(health, "jv-ears", "ok", {
      "uptime_s": "4",
      "period_s": 1000
    });
    beat(health, "jv-ears", "ok", {
      "uptime_s": 950,
      "period_s": 1000
    });
    compare(suite.entry(health, "jv-ears").state, "ok");
    compare(suite.entry(health, "jv-ears").restarts, 0);
  }

  function test_a_count_is_not_shown_beside_an_age_this_file_cannot_read() {
    // The restart is remembered and the CURRENT frame is what says whether
    // it is still news. A heartbeat whose `uptime_s` is unreadable cannot
    // say how old the process it came from is, so the count goes quiet
    // rather than standing on an age nobody measured.
    const health = makeHealth();
    beat(health, "jv-ears", "ok", {
      "uptime_s": 900
    });
    beat(health, "jv-ears", "ok", {
      "uptime_s": 2
    });
    compare(suite.entry(health, "jv-ears").state, "restarted");
    beat(health, "jv-ears", "ok", {
      "uptime_s": "2"
    });
    compare(suite.entry(health, "jv-ears").state, "ok");
    compare(suite.entry(health, "jv-ears").restarts, 0);
  }

  function test_a_period_that_is_not_a_number_is_not_a_heartbeat() {
    // `"5" > 0` is true, so a string period used to be believed and then
    // multiplied — by the expiry, by the timer's interval, and now by the
    // window a restart is news inside. Refused outright: `unknown` is a
    // finding, which is what an uninterpretable heartbeat deserves.
    const health = makeHealth();
    beat(health, "jv-ears", "ok", {
      "period_s": "5"
    });
    compare(suite.entry(health, "jv-ears").state, "unknown");
    compare(health.findingCount, 1);
  }

  function test_an_untrusted_heartbeat_neither_claims_a_restart_nor_loses_one() {
    // A frame this file may not read leaves the memory exactly as it was:
    // a hedged heartbeat is not evidence of a death, and it is not
    // evidence against the one that came before it either.
    const health = makeHealth();
    beat(health, "jv-ears", "ok", {
      "uptime_s": 900
    });
    beat(health, "jv-ears", "ok", {
      "uptime_s": 1
    }, {
      "conf": 0.6
    });
    compare(suite.entry(health, "jv-ears").state, "unknown", "the hedged frame is the newest");
    beat(health, "jv-ears", "ok", {
      "uptime_s": 1
    });
    compare(suite.entry(health, "jv-ears").restarts, 1, "one death, counted once");
  }

  // --- the memory does not span a blindness ----------------------------

  function test_losing_the_link_forgets_how_many_processes_there_have_been() {
    // A HUD that could not see the bus does not know how many came and
    // went while it was blind, and a count that silently spans a gap of
    // unknown length means something other than what it says. Coming back
    // is a first sighting, which claims nothing.
    const health = makeHealth();
    beat(health, "jv-ears", "ok", {
      "uptime_s": 900
    });
    beat(health, "jv-ears", "ok", {
      "uptime_s": 2
    });
    compare(suite.entry(health, "jv-ears").restarts, 1);
    health.bus.ingest('{"t":"link","up":false,"err":"bridge died"}');
    compare(health.roster.length, 0);
    health.bus.ingest('{"t":"link","up":true}');
    beat(health, "jv-ears", "ok", {
      "uptime_s": 3
    });
    compare(suite.entry(health, "jv-ears").state, "ok");
    compare(suite.entry(health, "jv-ears").restarts, 0);
  }

  function test_a_bus_that_keeps_its_frames_through_a_drop_still_forgets() {
    // The other half of the forgetting, and the reason there are two. A
    // `BusModel` empties its caches on a drop and lowers `linkUp`
    // afterwards, so the pass that a drop triggers runs while the link
    // still looks up — this bus never empties anything, which is the only
    // way to drive the case where the flag is all there is to go on.
    const bus = spawn(stubBus);
    const health = spawn(healthState);
    health.bus = bus;
    bus.order = ["jv-ears"];
    bus.beats = ({
      "jv-ears": suite.stubBeat("jv-ears", 900)
    });
    bus.beats = ({
      "jv-ears": suite.stubBeat("jv-ears", 2)
    });
    compare(suite.entry(health, "jv-ears").state, "restarted");
    bus.linkUp = false;
    bus.linkUp = true;
    bus.beats = ({
      "jv-ears": suite.stubBeat("jv-ears", 3)
    });
    compare(suite.entry(health, "jv-ears").state, "ok");
    compare(suite.entry(health, "jv-ears").restarts, 0);
  }

  // One heartbeat as the stub bus hands them over: no ingest, no clock, so
  // `ageOf` is the stub's own 0 and nothing here can expire — and no
  // JSON, which is the only way a value JSON cannot carry reaches the
  // element.
  function stubBeat(service, uptime, period) {
    return {
      "topic": "sys.health",
      "ts": 100,
      "seq": suite.seq++,
      "src": service,
      "conf": 1.0,
      "v": 1,
      "body": {
        "service": service,
        "state": "ok",
        "uptime_s": uptime,
        "period_s": period === undefined ? 5 : period
      }
    };
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
