// DictateState — "is push-to-talk dictation recording?", under test (F5c).
//
// jv-dictate reports one gauge, `metrics.recording` (services/jv-dictate/
// jv_dictate/service.py), so this element decides between three words and
// not MicState's five: there is nothing here that can be open-but-silent or
// open-but-losing-chunks the way a continuously-running device can be — the
// push-to-talk key is either held or it is not. What survives from
// MicState's own tests is the shape of the two lies invariant 10 forbids:
// claiming a recording that is not happening, and going dark while one is.
//
// Headless, like MicState: pure QtQuick, reading the bus through
// core/BusModel, which the test drives with the same JSON lines the bridge
// writes.
import QtQuick
import QtTest
import "../core"

TestCase {
  id: suite
  name: "DictateState"

  property real fakeNow: 0
  property int seq: 1

  Component {
    id: busModel
    BusModel {}
  }

  Component {
    id: dictateState
    DictateState {}
  }

  // createObject() is typed QObject, so every member read on the result
  // would be `missing-property` to qmllint. Going through an untyped
  // helper keeps the file lint-clean at -W 0 (see tst_micstate).
  function spawn(component) {
    const o = component.createObject(suite);
    verify(o, "failed to instantiate a test object");
    return o;
  }

  // opts: { clock: false } to withhold the monotonic clock,
  //       { down: true } to leave the bridge link down.
  function makeDictate(opts) {
    const o = opts || {};
    suite.fakeNow = 0;
    const bus = spawn(busModel);
    if (o.clock !== false)
      bus.monotonic = () => suite.fakeNow;
    const dictate = spawn(dictateState);
    dictate.bus = bus;
    if (o.down !== true)
      bus.ingest('{"t":"link","up":true}');
    return dictate;
  }

  // One jv-dictate heartbeat. `metrics` null means a heartbeat carrying
  // none at all; `body` and `env` override the rest.
  function beat(dictate, metrics, body, env) {
    let b = {
      "service": "jv-dictate",
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
      "src": "jv-dictate",
      "conf": 1.0,
      "v": 1,
      "body": b
    };
    for (const k in env || {})
      e[k] = env[k];
    dictate.bus.ingest(JSON.stringify({
      "t": "frame",
      "frame": e
    }));
  }

  function recording(dictate, body, env) {
    beat(dictate, {
      "recording": 1.0
    }, body, env);
  }

  // Give the model a promptly-delivered frame so it learns what "now" is.
  // BusModel pins its clock offset from the frames it sees, so the FIRST
  // frame is always zero seconds old by construction — a test about an old
  // frame has to send a fresh one first or it is testing nothing.
  function pinClock(dictate) {
    dictate.bus.ingest(JSON.stringify({
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

  function idle(dictate, body, env) {
    beat(dictate, {
      "recording": 0.0
    }, body, env);
  }

  // --- nothing known is never "idle" ------------------------------------

  function test_without_a_bus_nothing_is_known() {
    const dictate = spawn(dictateState);
    compare(dictate.state, "unknown");
    verify(!dictate.known);
    verify(!dictate.recording);
  }

  function test_a_link_that_is_down_knows_nothing() {
    const dictate = makeDictate({
      down: true
    });
    compare(dictate.state, "unknown");
  }

  function test_a_live_bus_with_no_heartbeat_knows_nothing() {
    compare(makeDictate().state, "unknown");
  }

  function test_losing_the_link_forgets_a_held_key() {
    // A cached heartbeat from a bus that died describes a machine we can no
    // longer see. The indicator must not keep drawing it.
    const dictate = makeDictate();
    recording(dictate);
    compare(dictate.state, "recording");
    dictate.bus.ingest('{"t":"link","up":false,"err":"bridge died"}');
    compare(dictate.state, "unknown");
  }

  function test_another_services_heartbeat_says_nothing_about_dictation() {
    const dictate = makeDictate();
    beat(dictate, {
      "recording": 1.0
    }, {
      "service": "jv-ears"
    }, {
      "src": "jv-ears"
    });
    compare(dictate.state, "unknown", "jv-ears cannot see the push-to-talk key");
  }

  function test_a_body_naming_a_different_service_than_published_it_is_refused() {
    const dictate = makeDictate();
    recording(dictate, {
      "service": "jv-ears"
    });
    compare(dictate.state, "unknown");
  }

  // --- the reading itself -------------------------------------------------

  function test_a_held_key_is_recording() {
    const dictate = makeDictate();
    recording(dictate);
    compare(dictate.state, "recording");
    verify(dictate.known);
    verify(dictate.recording);
  }

  function test_a_released_key_is_idle() {
    const dictate = makeDictate();
    idle(dictate);
    compare(dictate.state, "idle");
    verify(dictate.known, "a released key is a thing we know, not a thing we cannot see");
    verify(!dictate.recording);
  }

  function test_a_newer_heartbeat_replaces_what_the_last_one_said() {
    const dictate = makeDictate();
    recording(dictate);
    compare(dictate.state, "recording");
    idle(dictate);
    compare(dictate.state, "idle", "the key was released and said so");
  }

  // --- a heartbeat we cannot read is not an answer -------------------------

  function test_a_heartbeat_without_the_gauge_is_unknown_not_idle() {
    // An older jv-dictate that never learned to report the key, or a body
    // that omits `metrics` entirely. It tells us nothing about the key, and
    // "idle" would be an invention.
    const dictate = makeDictate();
    beat(dictate, null);
    compare(dictate.state, "unknown");
  }

  function test_a_gauge_that_is_not_a_number_is_not_a_gauge() {
    const dictate = makeDictate();
    beat(dictate, {
      "recording": "yes"
    });
    compare(dictate.state, "unknown");
  }

  function test_a_body_from_a_schema_version_we_do_not_know_is_refused() {
    const dictate = makeDictate();
    recording(dictate, {}, {
      "v": 2
    });
    compare(dictate.state, "unknown", "a v2 body is not a v1 body (invariant 2)");
  }

  function test_a_heartbeat_hedging_its_confidence_is_refused() {
    // State topics publish conf 1.0. Anything less disagrees with itself.
    const dictate = makeDictate();
    recording(dictate, {}, {
      "conf": 0.9
    });
    compare(dictate.state, "unknown");
  }

  function test_a_heartbeat_with_no_ts_cannot_be_aged_and_is_refused() {
    const dictate = makeDictate();
    recording(dictate, {}, {
      "ts": "soon"
    });
    compare(dictate.state, "unknown");
  }

  function test_a_heartbeat_without_a_period_cannot_be_trusted_for_long() {
    const dictate = makeDictate();
    recording(dictate, {
      "period_s": 0
    });
    compare(dictate.state, "unknown");
  }

  function test_with_no_clock_there_is_no_age_and_therefore_no_claim() {
    const dictate = makeDictate({
      clock: false
    });
    recording(dictate);
    compare(dictate.state, "unknown");
  }

  // --- heartbeats stop describing the present -----------------------------

  function test_a_heartbeat_older_than_two_periods_is_not_a_reading() {
    // schemas/sys.health.json: missing 2 consecutive periods = presumed
    // dead. jv-dictate may have died with the key held, so the honest
    // answer is "I cannot see", never "idle".
    const dictate = makeDictate();
    suite.pinClock(dictate);
    recording(dictate, {
      "period_s": 5
    }, {
      "ts": suite.fakeNow + 100 - 11
    });
    compare(dictate.state, "unknown");
  }

  function test_a_claim_expires_on_its_own_when_the_heartbeats_stop() {
    const dictate = makeDictate();
    recording(dictate, {
      "period_s": 0.025
    });
    compare(dictate.state, "recording");
    tryCompare(dictate, "state", "unknown", 3000, "a heartbeat must expire on its own");
  }

  function test_the_next_heartbeat_revives_a_claim_that_had_expired() {
    const dictate = makeDictate();
    recording(dictate, {
      "period_s": 0.025
    });
    tryCompare(dictate, "state", "unknown", 3000);
    suite.fakeNow += 1;
    recording(dictate);
    compare(dictate.state, "recording");
  }
}
