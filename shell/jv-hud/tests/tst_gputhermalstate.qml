// GpuThermalState — "is the card running hot?", under test (G5).
//
// Mirrors tst_dictatestate.qml's shape: a service-named `sys.health` gauge
// bag, read with the same rejection rules (schema version, hedged conf,
// wrong-service body, staleness after two periods). What is new here is the
// earned-emptiness gate on top: `known` is not the same as `reporting`,
// because a temperature is only worth a HealthPlate line once it crosses
// `hotThresholdC` — a cold, perfectly healthy card must stay silent.
//
// Headless, like DictateState: pure QtQuick, reading the bus through
// core/BusModel, which the test drives with the same JSON lines the bridge
// writes.
import QtQuick
import QtTest
import "../core"

TestCase {
  id: suite
  name: "GpuThermalState"

  property real fakeNow: 0
  property int seq: 1

  Component {
    id: busModel
    BusModel {}
  }

  Component {
    id: thermalState
    GpuThermalState {}
  }

  // createObject() is typed QObject, so every member read on the result
  // would be `missing-property` to qmllint. Going through an untyped
  // helper keeps the file lint-clean at -W 0 (see tst_dictatestate).
  function spawn(component) {
    const o = component.createObject(suite);
    verify(o, "failed to instantiate a test object");
    return o;
  }

  // opts: { clock: false } to withhold the monotonic clock,
  //       { down: true } to leave the bridge link down,
  //       { threshold: N } to override hotThresholdC.
  function makeThermal(opts) {
    const o = opts || {};
    suite.fakeNow = 0;
    const bus = spawn(busModel);
    if (o.clock !== false)
      bus.monotonic = () => suite.fakeNow;
    const thermal = spawn(thermalState);
    thermal.bus = bus;
    if (o.threshold !== undefined)
      thermal.hotThresholdC = o.threshold;
    if (o.down !== true)
      bus.ingest('{"t":"link","up":true}');
    return thermal;
  }

  // One jv-context heartbeat. `metrics` null means a heartbeat carrying
  // none at all; `body` and `env` override the rest.
  function beat(thermal, metrics, body, env) {
    let b = {
      "service": "jv-context",
      "state": "ok",
      "uptime_s": 30,
      "period_s": 5
    };
    if (metrics !== null)
      b.metrics = metrics;
    for (const k in body || {})
      b[k] = body[k];
    let e = {
      "topic": "sys.health",
      "ts": suite.fakeNow + 100,
      "seq": suite.seq++,
      "src": "jv-context",
      "conf": 1.0,
      "v": 1,
      "body": b
    };
    for (const k in env || {})
      e[k] = env[k];
    thermal.bus.ingest(JSON.stringify({
      "t": "frame",
      "frame": e
    }));
  }

  function reading(thermal, tempC, fanPct, body, env) {
    const m = {
      "gpu_temp_c": tempC
    };
    if (fanPct !== undefined)
      m.gpu_fan_pct = fanPct;
    beat(thermal, m, body, env);
  }

  // Give the model a promptly-delivered frame so it learns what "now" is.
  // BusModel pins its clock offset from the frames it sees, so the FIRST
  // frame is always zero seconds old by construction.
  function pinClock(thermal) {
    thermal.bus.ingest(JSON.stringify({
      "t": "frame",
      "frame": {
        "topic": "speech.state",
        "ts": suite.fakeNow + 100,
        "seq": suite.seq++,
        "src": "jv-voice",
        "conf": 1.0,
        "v": 1,
        "body": {
          "state": "idle"
        }
      }
    }));
  }

  // --- nothing known is never "reporting" ---------------------------------

  function test_without_a_bus_nothing_is_known() {
    const thermal = spawn(thermalState);
    verify(!thermal.known);
    verify(!thermal.reporting);
    compare(thermal.line, "");
  }

  function test_a_link_that_is_down_knows_nothing() {
    const thermal = makeThermal({
      down: true
    });
    verify(!thermal.known);
  }

  function test_a_live_bus_with_no_heartbeat_knows_nothing() {
    verify(!makeThermal().known);
  }

  function test_losing_the_link_forgets_a_hot_card() {
    const thermal = makeThermal();
    reading(thermal, 85, 70);
    verify(thermal.reporting);
    thermal.bus.ingest('{"t":"link","up":false,"err":"bridge died"}');
    verify(!thermal.known);
    verify(!thermal.reporting);
  }

  function test_another_services_heartbeat_says_nothing_about_the_card() {
    const thermal = makeThermal();
    beat(thermal, {
      "gpu_temp_c": 85
    }, {
      "service": "jv-brain"
    }, {
      "src": "jv-brain"
    });
    verify(!thermal.known, "jv-brain cannot see the GPU probe");
  }

  function test_a_body_naming_a_different_service_than_published_it_is_refused() {
    const thermal = makeThermal();
    reading(thermal, 85, 70, {
      "service": "jv-brain"
    });
    verify(!thermal.known);
  }

  // --- the reading itself --------------------------------------------------

  function test_a_cold_card_is_known_but_silent() {
    const thermal = makeThermal();
    reading(thermal, 42, 30);
    verify(thermal.known, "42°C is a reading, not nothing");
    compare(thermal.tempC, 42);
    verify(!thermal.reporting, "a card idling in the 40s is not news");
    compare(thermal.line, "");
  }

  function test_a_hot_card_is_reported() {
    const thermal = makeThermal();
    reading(thermal, 82, 64);
    verify(thermal.reporting);
    compare(thermal.line, "GPU 82°C");
    verify(thermal.fanReporting);
    compare(thermal.fanLine, "FAN 64%");
  }

  function test_exactly_the_threshold_is_hot() {
    const thermal = makeThermal({
      threshold: 80
    });
    reading(thermal, 80, 50);
    verify(thermal.reporting, "the threshold itself counts as hot");
  }

  function test_the_fan_line_never_appears_without_the_temperature() {
    // reporting is gated on temperature alone; a heartbeat with no fan
    // number at all must still show the temperature, just no second line.
    const thermal = makeThermal();
    reading(thermal, 82, undefined);
    verify(thermal.reporting);
    compare(thermal.line, "GPU 82°C");
    verify(!thermal.fanReporting);
    compare(thermal.fanLine, "");
  }

  function test_a_newer_heartbeat_replaces_what_the_last_one_said() {
    const thermal = makeThermal();
    reading(thermal, 85, 70);
    verify(thermal.reporting);
    reading(thermal, 40, 20);
    verify(!thermal.reporting, "the card cooled down and the line said so");
  }

  // --- a heartbeat we cannot read is not an answer --------------------------

  function test_a_heartbeat_without_the_gauge_is_unknown_not_cold() {
    const thermal = makeThermal();
    beat(thermal, null);
    verify(!thermal.known);
  }

  function test_a_gauge_that_is_not_a_number_is_not_a_gauge() {
    const thermal = makeThermal();
    beat(thermal, {
      "gpu_temp_c": "hot"
    });
    verify(!thermal.known);
  }

  function test_a_body_from_a_schema_version_we_do_not_know_is_refused() {
    const thermal = makeThermal();
    reading(thermal, 85, 70, {}, {
      "v": 2
    });
    verify(!thermal.known, "a v2 body is not a v1 body (invariant 2)");
  }

  function test_a_heartbeat_hedging_its_confidence_is_refused() {
    const thermal = makeThermal();
    reading(thermal, 85, 70, {}, {
      "conf": 0.9
    });
    verify(!thermal.known);
  }

  function test_a_heartbeat_with_no_ts_cannot_be_aged_and_is_refused() {
    const thermal = makeThermal();
    reading(thermal, 85, 70, {}, {
      "ts": "soon"
    });
    verify(!thermal.known);
  }

  function test_a_heartbeat_without_a_period_cannot_be_trusted_for_long() {
    const thermal = makeThermal();
    reading(thermal, 85, 70, {
      "period_s": 0
    });
    verify(!thermal.known);
  }

  function test_with_no_clock_there_is_no_age_and_therefore_no_claim() {
    const thermal = makeThermal({
      clock: false
    });
    reading(thermal, 85, 70);
    verify(!thermal.known);
  }

  // --- heartbeats stop describing the present -------------------------------

  function test_a_heartbeat_older_than_two_periods_is_not_a_reading() {
    const thermal = makeThermal();
    suite.pinClock(thermal);
    reading(thermal, 85, 70, {
      "period_s": 5
    }, {
      "ts": suite.fakeNow + 100 - 11
    });
    verify(!thermal.known);
  }

  function test_a_claim_expires_on_its_own_when_the_heartbeats_stop() {
    const thermal = makeThermal();
    reading(thermal, 85, 70, {
      "period_s": 0.025
    });
    verify(thermal.reporting);
    tryCompare(thermal, "known", false, 3000, "a heartbeat must expire on its own");
  }

  function test_the_next_heartbeat_revives_a_claim_that_had_expired() {
    const thermal = makeThermal();
    reading(thermal, 85, 70, {
      "period_s": 0.025
    });
    tryCompare(thermal, "known", false, 3000);
    suite.fakeNow += 1;
    reading(thermal, 85, 70);
    verify(thermal.reporting);
  }
}
