// EarsBudgets — "how is jv-ears tuned?", under test (PLAN A14).
//
// The HUD makes two claims that are only true for as long as jv-ears is
// tuned to make them true: how long a wake word means "listening", and
// how long an open microphone may go quiet and still read as live. Both
// numbers were typed into QML by hand under comments asking a future
// reader to keep them in step with the Python. This element reads them
// off jv-ears' own heartbeat instead, and the tests are written around
// the ways that can go wrong:
//
//   · nothing to read (no bus, no link, no heartbeat, an older jv-ears
//     that reports no budgets) must land on ears' shipped defaults — the
//     same place the HUD stood before this existed, never on zero, which
//     would close every window instantly.
//   · a number we cannot act on — not a number, not finite, not positive,
//     or past a ceiling — is refused the same way, because arithmetic on
//     a bad budget is worse than arithmetic on a known-old one.
//   · a budget does NOT expire with its heartbeat, unlike the gauges in
//     MicState. That is the one deliberate asymmetry here and it is
//     pinned below, both directions.
//
// Headless, like the rest of core/: EarsBudgets is pure QtQuick and reads
// the bus through core/BusModel, which the test drives with the same JSON
// lines the bridge writes.
import QtQuick
import QtTest
import "../core"

TestCase {
  id: suite
  name: "EarsBudgets"

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
    id: earsBudgets
    EarsBudgets {}
  }

  // createObject() is typed QObject, so every member read on the result
  // would be `missing-property` to qmllint. Going through an untyped
  // helper keeps the file lint-clean at -W 0 (see tst_speechstate).
  function spawn(component) {
    const o = component.createObject(suite);
    verify(o, "failed to instantiate a test object");
    return o;
  }

  // opts: { down: true } to leave the bridge link down.
  function makeBudgets(opts) {
    const o = opts || {};
    suite.fakeNow = 0;
    const bus = spawn(busModel);
    bus.monotonic = () => suite.fakeNow;
    const ears = spawn(earsBudgets);
    ears.bus = bus;
    if (o.down !== true)
      bus.ingest('{"t":"link","up":true}');
    return ears;
  }

  // One jv-ears heartbeat. `metrics` null means a heartbeat carrying none
  // at all (a jv-ears older than A14); `body` and `env` override the rest.
  function beat(ears, metrics, body, env) {
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
    ears.bus.ingest(JSON.stringify({
      "t": "frame",
      "frame": e
    }));
  }

  // The heartbeat jv-ears actually publishes: the mic gauges and, since
  // A14, the budgets it enforces.
  function tuned(ears, wakeS, stallS) {
    beat(ears, {
      "mic_open": 1.0,
      "captured_s": 12.5,
      "capture_age_s": 0.08,
      "capture_stall_s": stallS,
      "wake_timeout_s": wakeS
    });
  }

  // A bus that hands back one heartbeat carrying `metrics`, for the cases
  // BusModel cannot be driven into: values JSON cannot express, and a
  // link reported down while a frame is still in hand. EarsBudgets asks a
  // `var` for `linkUp` and `latestFrom`, so a plain JS object is a bus as
  // far as it is concerned — which is also what lets the real one be a
  // Quickshell singleton the tests cannot load.
  function busReporting(metrics, up) {
    return {
      "linkUp": up !== false,
      "latestFrom": function (topic, src) {
        return {
          "topic": topic,
          "ts": 100,
          "seq": 1,
          "src": src,
          "conf": 1.0,
          "v": 1,
          "body": {
            "service": src,
            "state": "ok",
            "uptime_s": 30,
            "period_s": 5,
            "metrics": metrics
          }
        };
      }
    };
  }

  // --- with nothing to read, ears' shipped defaults --------------------

  function test_without_a_bus_the_defaults_stand() {
    const ears = spawn(earsBudgets);
    compare(ears.wakeWindowS, ears.wakeWindowDefaultS);
    compare(ears.stallS, ears.stallDefaultS);
    verify(!ears.wakeWindowReported);
    verify(!ears.stallReported);
  }

  function test_a_link_that_is_down_reads_no_budgets() {
    const ears = makeBudgets({
      down: true
    });
    compare(ears.wakeWindowS, ears.wakeWindowDefaultS);
    compare(ears.stallS, ears.stallDefaultS);
  }

  function test_a_live_bus_with_no_heartbeat_reads_no_budgets() {
    const ears = makeBudgets();
    compare(ears.wakeWindowS, ears.wakeWindowDefaultS);
    verify(!ears.wakeWindowReported);
  }

  function test_the_defaults_are_never_zero() {
    // The whole point of a fallback: a zero window would close the
    // listening claim on the frame it opened, and a zero stall budget
    // would call every live microphone deaf.
    const ears = spawn(earsBudgets);
    verify(ears.wakeWindowDefaultS > 0);
    verify(ears.stallDefaultS > 0);
  }

  // --- reading what jv-ears says --------------------------------------

  function test_a_heartbeat_carrying_budgets_replaces_the_defaults() {
    const ears = makeBudgets();
    tuned(ears, 12.0, 2.5);
    compare(ears.wakeWindowS, 12.0);
    compare(ears.stallS, 2.5);
    verify(ears.wakeWindowReported);
    verify(ears.stallReported);
  }

  function test_newer_tuning_wins() {
    // jv-ears restarted with a different config: it beats immediately on
    // start, so the HUD follows within one frame.
    const ears = makeBudgets();
    tuned(ears, 12.0, 2.5);
    tuned(ears, 4.0, 0.5);
    compare(ears.wakeWindowS, 4.0);
    compare(ears.stallS, 0.5);
  }

  function test_half_a_report_is_half_believed() {
    // A jv-ears that states one budget and not the other tells us exactly
    // one thing, and the other stays the default rather than becoming it.
    const ears = makeBudgets();
    beat(ears, {
      "mic_open": 1.0,
      "wake_timeout_s": 3.0
    });
    compare(ears.wakeWindowS, 3.0);
    verify(ears.wakeWindowReported);
    compare(ears.stallS, ears.stallDefaultS);
    verify(!ears.stallReported);
  }

  function test_a_heartbeat_without_metrics_leaves_the_defaults() {
    const ears = makeBudgets();
    beat(ears, null);
    compare(ears.wakeWindowS, ears.wakeWindowDefaultS);
    compare(ears.stallS, ears.stallDefaultS);
  }

  // --- whose heartbeat it is matters ----------------------------------

  function test_another_service_cannot_tune_the_ears() {
    const ears = makeBudgets();
    beat(ears, {
      "wake_timeout_s": 12.0
    }, {
      "service": "jv-brain"
    }, {
      "src": "jv-brain"
    });
    compare(ears.wakeWindowS, ears.wakeWindowDefaultS, "only jv-ears knows how jv-ears is tuned");
  }

  function test_a_body_naming_a_different_service_than_published_it_is_refused() {
    // schemas/sys.health.json: `service` matches the envelope `src`. A
    // frame that disagrees with itself is not a frame to act on.
    const ears = makeBudgets();
    beat(ears, {
      "wake_timeout_s": 12.0
    }, {
      "service": "jv-brain"
    });
    compare(ears.wakeWindowS, ears.wakeWindowDefaultS);
  }

  function test_losing_the_link_forgets_the_tuning() {
    // A cached heartbeat from a bus we can no longer see describes a
    // jv-ears we can no longer see. Back to the shipped defaults.
    const ears = makeBudgets();
    tuned(ears, 12.0, 2.5);
    compare(ears.wakeWindowS, 12.0);
    ears.bus.ingest('{"t":"link","up":false,"err":"bridge died"}');
    compare(ears.wakeWindowS, ears.wakeWindowDefaultS);
    compare(ears.stallS, ears.stallDefaultS);
  }

  function test_a_body_from_a_schema_version_we_do_not_know_is_refused() {
    const ears = makeBudgets();
    beat(ears, {
      "wake_timeout_s": 12.0
    }, {}, {
      "v": 2
    });
    compare(ears.wakeWindowS, ears.wakeWindowDefaultS);
  }

  function test_a_heartbeat_hedging_its_confidence_is_refused() {
    // sys.health is a state topic: conf is 1.0. Anything less is a frame
    // disagreeing with itself (invariant 4).
    const ears = makeBudgets();
    beat(ears, {
      "wake_timeout_s": 12.0
    }, {}, {
      "conf": 0.6
    });
    compare(ears.wakeWindowS, ears.wakeWindowDefaultS);
  }

  // --- a number we cannot act on is not a budget ------------------------

  function test_a_budget_that_is_not_a_number_is_not_a_budget() {
    const ears = makeBudgets();
    beat(ears, {
      "wake_timeout_s": "eight",
      "capture_stall_s": null
    });
    compare(ears.wakeWindowS, ears.wakeWindowDefaultS);
    compare(ears.stallS, ears.stallDefaultS);
  }

  function test_a_budget_of_zero_or_less_is_refused() {
    // Zero would close the window on the frame that opened it; negative
    // is nonsense. Either way the default is the honest thing to use.
    const ears = makeBudgets();
    tuned(ears, 0, -1);
    compare(ears.wakeWindowS, ears.wakeWindowDefaultS);
    compare(ears.stallS, ears.stallDefaultS);
  }

  function test_a_budget_past_its_ceiling_is_refused() {
    const ears = makeBudgets();
    tuned(ears, ears.wakeWindowCeilingS + 0.001, ears.stallCeilingS + 0.001);
    compare(ears.wakeWindowS, ears.wakeWindowDefaultS);
    compare(ears.stallS, ears.stallDefaultS);
    verify(!ears.wakeWindowReported);
    verify(!ears.stallReported);
  }

  function test_the_ceiling_itself_is_allowed() {
    const ears = makeBudgets();
    tuned(ears, ears.wakeWindowCeilingS, ears.stallCeilingS);
    compare(ears.wakeWindowS, ears.wakeWindowCeilingS);
    compare(ears.stallS, ears.stallCeilingS);
  }

  function test_a_numeric_string_is_not_a_number() {
    // `"12" > 0` is true in JavaScript and `"12" <= 60` is too, so a
    // budget that arrived as a string would sail through arithmetic and
    // land in a Timer interval. It is a jv-ears we do not understand.
    const ears = makeBudgets();
    beat(ears, {
      "mic_open": 1.0,
      "wake_timeout_s": "12",
      "capture_stall_s": "2"
    });
    compare(ears.wakeWindowS, ears.wakeWindowDefaultS);
    compare(ears.stallS, ears.stallDefaultS);
    verify(!ears.wakeWindowReported);
  }

  function test_a_bus_that_says_the_link_is_down_is_not_read() {
    // BusModel drops every frame when the bridge dies, so through it this
    // guard can never be reached. It is still the guard that matters: an
    // element must not read a bus that says it cannot see the machine,
    // whoever is holding the frames.
    const ears = makeBudgets();
    ears.bus = suite.busReporting({
      "mic_open": 1.0,
      "wake_timeout_s": 12.0
    }, false);
    compare(ears.wakeWindowS, ears.wakeWindowDefaultS);
    verify(!ears.wakeWindowReported);
  }

  function test_an_infinite_budget_is_refused() {
    // An infinite window never closes: "listening" would stay on screen
    // over a microphone that disarmed minutes ago. The ceiling is what
    // refuses it, which is why there is no separate finiteness check in
    // the element. JSON cannot carry Infinity (see the test below), so
    // this is pinned through a hand-built bus.
    const ears = makeBudgets();
    ears.bus = suite.busReporting({
      "mic_open": 1.0,
      "wake_timeout_s": Infinity,
      "capture_stall_s": -Infinity
    });
    compare(ears.wakeWindowS, ears.wakeWindowDefaultS);
    compare(ears.stallS, ears.stallDefaultS);
    verify(!ears.wakeWindowReported);
    verify(!ears.stallReported);
  }

  function test_a_bridge_line_that_would_parse_as_infinity_never_lands() {
    // `1e999` is valid JSON and out of range for a double. BusModel
    // refuses the line whole rather than acting on part of it, so the
    // heartbeat is LOST, not half-read — and the link is still up, so
    // the next good heartbeat tunes us as if nothing had happened.
    const ears = makeBudgets();
    ears.bus.ingest('{"t":"frame","frame":{"topic":"sys.health","ts":100,' + '"seq":9001,"src":"jv-ears","conf":1.0,"v":1,"body":{"service":"jv-ears",' + '"state":"ok","uptime_s":30,"period_s":5,"metrics":{"mic_open":1.0,' + '"wake_timeout_s":1e999}}}}');
    compare(ears.wakeWindowS, ears.wakeWindowDefaultS);
    verify(!ears.wakeWindowReported);
    tuned(ears, 12.0, 2.5);
    compare(ears.wakeWindowS, 12.0);
  }

  // --- configuration does not expire; measurements do ------------------

  function test_an_old_heartbeat_still_states_the_tuning() {
    // The deliberate asymmetry with MicState: its gauges stop describing
    // the present after two heartbeat periods, because a gauge is about a
    // moment. A budget is about how the service is CONFIGURED and stays
    // true until it says otherwise — and a jv-ears too dead to beat is a
    // jv-ears publishing no wakes for the window to bound anyway.
    const ears = makeBudgets();
    tuned(ears, 12.0, 2.5);
    suite.fakeNow += 3600;
    compare(ears.wakeWindowS, 12.0);
    compare(ears.stallS, 2.5);
    verify(ears.wakeWindowReported);
  }

  function test_a_heartbeat_with_no_timestamp_is_still_a_configuration() {
    // MicState refuses this frame outright: an unorderable frame cannot
    // be aged, and its gauges would be measurements of an unknown moment.
    // Nothing here is a measurement, so there is nothing to age.
    const ears = makeBudgets();
    beat(ears, {
      "mic_open": 1.0,
      "wake_timeout_s": 12.0
    }, {}, {
      "ts": "soon"
    });
    compare(ears.wakeWindowS, 12.0);
  }

  // --- and it drives no clock -----------------------------------------

  function test_reading_budgets_arms_no_timer() {
    // §06: 0 fps when nothing is happening. This element answers from the
    // frame in hand and never counts anything down — the elements that DO
    // (SpeechState, MicState) own their timers, and this one must not add
    // a second one behind them.
    const ears = makeBudgets();
    tuned(ears, 12.0, 2.5);
    const timers = [];
    for (const k in ears)
      if (ears[k] && typeof ears[k] === "object" && ears[k].hasOwnProperty("interval") && ears[k].hasOwnProperty("running"))
        timers.push(k);
    compare(timers, [], "EarsBudgets grew a timer: " + timers.join(", "));
  }
}
