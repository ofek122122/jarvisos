// MicState — "is the microphone open?", under test (PLAN A4).
//
// This is the HUD's privacy indicator, so the tests are written around the
// two ways it can lie, which are not equally bad:
//
//   · claiming a microphone that is not open — embarrassing, and it makes
//     the indicator noise.
//   · going dark while one IS open — the failure that costs trust, and
//     the reason invariant 10 says the indicator is not fakeable.
//
// So "I cannot tell" must never collapse into "off": no link, no
// heartbeat, a heartbeat too old to describe the present, or a jv-ears
// that reports no gauges all have to come out as `unknown`. And a live
// microphone that has stopped delivering audio has to come out as
// something other than `live` — that is the 2026-09-15 field bug, where
// PortAudio opened nothing and every other signal stayed cheerful.
//
// Headless, like the rest of core/: MicState is pure QtQuick and reads the
// bus through core/BusModel, which the test drives with the same JSON
// lines the bridge writes.
import QtQuick
import QtTest
import "../core"

TestCase {
  id: suite
  name: "MicState"

  // A stand-in for CLOCK_MONOTONIC the test drives. Frames are sent with
  // ts = fakeNow + 100, so the model pins an offset of exactly 100 and a
  // frame lands zero seconds old; winding fakeNow forward ages it.
  property real fakeNow: 0
  property int seq: 1

  Component {
    id: busModel
    BusModel {}
  }

  Component {
    id: micState
    MicState {}
  }

  // createObject() is typed QObject, so every member read on the result
  // would be `missing-property` to qmllint. Going through an untyped
  // helper keeps the file lint-clean at -W 0 (see tst_speechstate).
  function spawn(component) {
    const o = component.createObject(suite);
    verify(o, "failed to instantiate a test object");
    return o;
  }

  // opts: { clock: false } to withhold the monotonic clock,
  //       { down: true } to leave the bridge link down,
  //       { stallS: n } for a different stall budget.
  function makeMic(opts) {
    const o = opts || {};
    suite.fakeNow = 0;
    const bus = spawn(busModel);
    if (o.clock !== false)
      bus.monotonic = () => suite.fakeNow;
    const mic = spawn(micState);
    if (o.stallS !== undefined)
      mic.stallS = o.stallS;
    mic.bus = bus;
    if (o.down !== true)
      bus.ingest('{"t":"link","up":true}');
    return mic;
  }

  // One jv-ears heartbeat. `metrics` null means a heartbeat carrying none
  // at all (an older jv-ears); `body` and `env` override the rest.
  function beat(mic, metrics, body, env) {
    let b = {
      "service": "jv-ears",
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
      "src": "jv-ears",
      "conf": 1.0,
      "v": 1,
      "body": b
    };
    for (const k in env || {})
      e[k] = env[k];
    mic.bus.ingest(JSON.stringify({
      "t": "frame",
      "frame": e
    }));
  }

  // Give the model a promptly-delivered frame so it learns what "now" is.
  // BusModel pins its clock offset from the frames it sees, so the FIRST
  // frame is always zero seconds old by construction — a test about an
  // old frame has to send a fresh one first or it is testing nothing.
  function pinClock(mic) {
    mic.bus.ingest(JSON.stringify({
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

  // A microphone that is open and delivering.
  function live(mic, ageS, body, env) {
    beat(mic, {
      "mic_open": 1.0,
      "captured_s": 12.5,
      "capture_age_s": ageS === undefined ? 0.08 : ageS
    }, body, env);
  }

  // The same microphone, with a hole in the recording `lossAgeS` seconds
  // ago. jv-ears publishes `capture_loss_age_s` only once something has
  // been discarded, so its ABSENCE above is the "nothing has been lost"
  // case and not a jv-ears that forgot to say.
  function lossy(mic, lossAgeS, ageS) {
    beat(mic, {
      "mic_open": 1.0,
      "captured_s": 12.5,
      "capture_age_s": ageS === undefined ? 0.08 : ageS,
      "capture_loss_age_s": lossAgeS
    });
  }

  // --- nothing known is never "off" -----------------------------------

  function test_without_a_bus_nothing_is_known() {
    const mic = spawn(micState);
    compare(mic.state, "unknown");
    verify(!mic.known);
    verify(!mic.capturing);
  }

  function test_a_link_that_is_down_knows_nothing() {
    const mic = makeMic({
      down: true
    });
    compare(mic.state, "unknown");
  }

  function test_a_live_bus_with_no_heartbeat_knows_nothing() {
    compare(makeMic().state, "unknown");
  }

  function test_losing_the_link_forgets_an_open_microphone() {
    // A cached heartbeat from a bus that died describes a machine we can
    // no longer see. The indicator must not keep drawing it.
    const mic = makeMic();
    live(mic);
    compare(mic.state, "live");
    mic.bus.ingest('{"t":"link","up":false,"err":"bridge died"}');
    compare(mic.state, "unknown");
  }

  function test_another_services_heartbeat_says_nothing_about_the_microphone() {
    const mic = makeMic();
    beat(mic, {
      "mic_open": 1.0,
      "capture_age_s": 0
    }, {
      "service": "jv-brain"
    }, {
      "src": "jv-brain"
    });
    compare(mic.state, "unknown", "jv-brain cannot see the microphone");
  }

  function test_a_body_naming_a_different_service_than_published_it_is_refused() {
    // schemas/sys.health.json: `service` matches the envelope `src`. A
    // frame that disagrees with itself is not a frame to render.
    const mic = makeMic();
    live(mic, 0, {
      "service": "jv-brain"
    });
    compare(mic.state, "unknown");
  }

  // --- the reading itself ---------------------------------------------

  function test_an_open_and_flowing_microphone_is_live() {
    const mic = makeMic();
    live(mic);
    compare(mic.state, "live");
    verify(mic.known);
    verify(mic.capturing);
    verify(!mic.stalled);
  }

  function test_no_microphone_open_is_off() {
    // jv-ears running --wav: the process is up, the device is not.
    const mic = makeMic();
    beat(mic, {
      "mic_open": 0.0,
      "captured_s": 3.0,
      "capture_age_s": 0.01
    });
    compare(mic.state, "off");
    verify(mic.known, "a closed microphone is a thing we know, not a thing we cannot see");
    verify(!mic.capturing);
  }

  function test_an_open_microphone_delivering_nothing_is_stalled_not_live() {
    // The 2026-09-15 bug, as the HUD would see it today.
    const mic = makeMic();
    live(mic, 4.0);
    compare(mic.state, "stalled");
    verify(mic.stalled);
    verify(!mic.capturing, "a deaf microphone is not a capturing one");
    verify(mic.known, "it is still open — that is worth saying");
  }

  function test_a_microphone_that_has_never_delivered_is_stalled() {
    // capture_age_s is ABSENT until the first chunk: never is not an age,
    // and jv-ears will not publish it as one (json has no Infinity).
    const mic = makeMic();
    beat(mic, {
      "mic_open": 1.0,
      "captured_s": 0.0
    });
    compare(mic.state, "stalled");
  }

  function test_the_stall_budget_is_inclusive_at_its_edge() {
    const mic = makeMic({
      stallS: 1.0
    });
    live(mic, 1.0);
    compare(mic.state, "live");
    live(mic, 1.001);
    compare(mic.state, "stalled");
  }

  // --- open, delivering, and losing chunks anyway (A84) ----------------
  //
  // The fourth word. A device whose queue overflows delivers audio the
  // whole time, so every gauge `live` is built on stays fresh while the
  // room goes into a hole — which made `live` the indicator over-claiming
  // in exactly the direction invariant 10 says it may not.

  function test_a_microphone_losing_chunks_is_not_simply_live() {
    const mic = makeMic();
    lossy(mic, 0.2);
    compare(mic.state, "losing");
    verify(mic.losing);
    verify(!mic.stalled, "it is delivering — that is a different fault");
    verify(mic.capturing, "the room IS being recorded, holes and all");
    verify(mic.known);
  }

  function test_an_ears_that_lost_nothing_is_live() {
    // No discard has happened, so there is no age to publish. The absence
    // is the answer, and it must not read as a loss we cannot date.
    const mic = makeMic();
    live(mic);
    compare(mic.state, "live");
    verify(!mic.losing);
  }

  function test_a_loss_older_than_the_window_stops_being_news() {
    // The hole stays in jv-ears' totals forever. What ends is the claim
    // that it is happening NOW, which is the only claim on screen.
    const mic = makeMic();
    lossy(mic, 4.0);
    compare(mic.state, "live");
  }

  function test_the_loss_window_is_inclusive_at_its_edge() {
    // `<=`, matching CaptureMeter.health() exactly. The service and the
    // HUD drawing different sides of one boundary is how a plate comes to
    // contradict the heartbeat it was drawn from.
    const mic = makeMic();
    mic.lossWindowS = 1.0;
    lossy(mic, 1.0);
    compare(mic.state, "losing");
    lossy(mic, 1.001);
    compare(mic.state, "live");
  }

  function test_a_loss_age_from_the_future_is_still_a_loss() {
    // jv-ears stamps the discard on PortAudio's thread and subtracts on
    // the asyncio loop; a negative age must not fall through the window
    // check as "long ago". Its own health() has the same guard.
    const mic = makeMic();
    lossy(mic, -0.5);
    compare(mic.state, "losing");
  }

  function test_an_age_we_cannot_read_is_a_loss_we_cannot_date() {
    // The gauge is published only when something was discarded, so its
    // presence is the evidence and its value only says how stale that is.
    // An unreadable value therefore leaves a known loss we cannot call
    // old — the same way an unreadable `capture_age_s` above leaves a
    // device we cannot call live.
    const mic = makeMic();
    lossy(mic, "recently");
    compare(mic.state, "losing");
  }

  function test_a_stalled_microphone_says_so_even_while_it_is_losing_audio() {
    // Both are degraded and only one word fits on the plate. "No audio at
    // all" is the bigger fact — the same order jv-ears puts them in.
    const mic = makeMic();
    lossy(mic, 0.1, 4.0);
    compare(mic.state, "stalled");
    verify(!mic.losing);
  }

  function test_a_closed_microphone_cannot_be_losing_audio() {
    const mic = makeMic();
    beat(mic, {
      "mic_open": 0.0,
      "captured_s": 3.0,
      "capture_age_s": 0.01,
      "capture_loss_age_s": 0.1
    });
    compare(mic.state, "off");
    verify(!mic.losing);
  }

  // --- a heartbeat we cannot read is not an answer ---------------------

  function test_a_heartbeat_without_gauges_is_unknown_not_off() {
    // An older jv-ears that never learned to report the microphone. It
    // tells us nothing about the device, and "off" would be an invention.
    const mic = makeMic();
    beat(mic, null);
    compare(mic.state, "unknown");
  }

  function test_a_gauge_that_is_not_a_number_is_not_a_gauge() {
    const mic = makeMic();
    beat(mic, {
      "mic_open": "yes"
    });
    compare(mic.state, "unknown");
  }

  function test_a_body_from_a_schema_version_we_do_not_know_is_refused() {
    const mic = makeMic();
    live(mic, 0, {}, {
      "v": 2
    });
    compare(mic.state, "unknown", "a v2 body is not a v1 body (invariant 2)");
  }

  function test_a_heartbeat_hedging_its_confidence_is_refused() {
    // State topics publish conf 1.0. Anything less disagrees with itself.
    const mic = makeMic();
    live(mic, 0, {}, {
      "conf": 0.9
    });
    compare(mic.state, "unknown");
  }

  function test_a_heartbeat_with_no_ts_cannot_be_aged_and_is_refused() {
    const mic = makeMic();
    live(mic, 0, {}, {
      "ts": "soon"
    });
    compare(mic.state, "unknown");
  }

  function test_a_heartbeat_without_a_period_cannot_be_trusted_for_long() {
    // period_s is how long the frame speaks for. Without it there is no
    // expiry, and a heartbeat with no expiry is one that never stops
    // claiming an open microphone.
    const mic = makeMic();
    live(mic, 0, {
      "period_s": 0
    });
    compare(mic.state, "unknown");
  }

  function test_with_no_clock_there_is_no_age_and_therefore_no_claim() {
    const mic = makeMic({
      clock: false
    });
    live(mic);
    compare(mic.state, "unknown");
  }

  // --- heartbeats stop describing the present -------------------------

  function test_a_heartbeat_older_than_two_periods_is_not_a_reading() {
    // schemas/sys.health.json: missing 2 consecutive periods = presumed
    // dead. jv-ears may have died with the device open, so the honest
    // answer is "I cannot see", never "off".
    const mic = makeMic();
    pinClock(mic);
    live(mic, 0, {
      "period_s": 5
    }, {
      "ts": suite.fakeNow + 100 - 11
    });
    compare(mic.state, "unknown");
  }

  function test_a_claim_expires_on_its_own_when_the_heartbeats_stop() {
    // Nothing publishes "jv-ears died". The HUD has to let go by itself
    // or it draws a microphone state from a service that is gone.
    const mic = makeMic();
    live(mic, 0, {
      "period_s": 0.025
    });
    compare(mic.state, "live");
    tryCompare(mic, "state", "unknown", 3000, "a heartbeat must expire on its own");
  }

  function test_a_late_heartbeat_gets_only_what_is_left_of_its_life() {
    const mic = makeMic();
    pinClock(mic);
    live(mic, 0, {
      "period_s": 0.25
    }, {
      "ts": suite.fakeNow + 100 - 0.45
    });
    compare(mic.state, "live");
    tryCompare(mic, "state", "unknown", 150, "0.05 s of the 0.5 s was left, not 0.5 s");
  }

  function test_the_next_heartbeat_revives_a_claim_that_had_expired() {
    const mic = makeMic();
    live(mic, 0, {
      "period_s": 0.025
    });
    tryCompare(mic, "state", "unknown", 3000);
    suite.fakeNow += 1;
    live(mic);
    compare(mic.state, "live");
  }

  function test_a_newer_heartbeat_replaces_what_the_last_one_said() {
    const mic = makeMic();
    live(mic);
    compare(mic.state, "live");
    beat(mic, {
      "mic_open": 0.0,
      "captured_s": 99.0
    });
    compare(mic.state, "off", "the microphone closed and said so");
  }

  // --- it is not SpeechState -------------------------------------------

  function test_the_microphone_is_not_derived_from_anything_jarvis_says() {
    // jv-ears runs VAD continuously; the mic is open whether or not a
    // wake window is. Wiring this to speech.state would make the privacy
    // indicator go dark exactly when nobody is talking to Jarvis.
    const mic = makeMic();
    live(mic);
    mic.bus.ingest(JSON.stringify({
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
    compare(mic.state, "live");
  }
}
