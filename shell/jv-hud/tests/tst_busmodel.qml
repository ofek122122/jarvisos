// BusModel — the HUD's bus-frame state machine, under test (PLAN A9).
//
// Everything here runs headless: `qmltestrunner -platform offscreen`, no
// compositor, no bus, no bridge process. That is possible only because
// BusModel is pure QtQuick — the Quickshell half (the child process, the
// respawn timer, the monotonic clock) lives in Bus.qml, which cannot be
// loaded outside the quickshell binary (its plugin is linked into it) —
// which is also why `core/` may never grow a Quickshell import.
//
// The line these tests defend is invariant 10: the HUD shows what the bus
// actually said, or it shows nothing. A frame the HUD cannot parse must
// change no state; a dropped link must empty the cache; an unheard topic
// must answer null rather than a plausible-looking default.
import QtQuick
import QtTest
import "../core"

TestCase {
  id: suite
  name: "BusModel"

  // A stand-in for CLOCK_MONOTONIC that the test drives by hand. The real
  // one is Quickshell's ElapsedTimer; the arithmetic under test is the
  // same either way, and here it is reproducible.
  property real fakeNow: 0

  function makeModel(withClock) {
    const model = busModel.createObject(suite);
    verify(model, "BusModel failed to instantiate");
    if (withClock)
      model.monotonic = () => suite.fakeNow;
    return model;
  }

  function frameLine(topic, extra) {
    let env = {
      "topic": topic,
      "ts": 100,
      "seq": 1,
      "src": "test",
      "conf": 1.0,
      "v": 1,
      "body": {}
    };
    for (const k in extra || {})
      env[k] = extra[k];
    return JSON.stringify({
      "t": "frame",
      "frame": env
    });
  }

  Component {
    id: busModel
    BusModel {}
  }

  // A binding on `frames`, which is the thing elements will actually do.
  // It re-evaluates only if the property is REPLACED; mutating the object
  // in place would leave this stuck at its first value. -1 means "no model
  // attached", so a test that forgets to attach one cannot read as zero.
  QtObject {
    id: watcher

    property var source: null
    readonly property int topicCount: watcher.source ? Object.keys(watcher.source.frames).length : -1
  }

  // --- the honest defaults -------------------------------------------

  function test_starts_down_and_knows_nothing() {
    const m = makeModel(true);
    verify(!m.linkUp, "the link is down until the bridge says otherwise");
    compare(m.received, 0);
    compare(m.latest("speech.state"), null);
    compare(Object.keys(m.frames).length, 0);
  }

  function test_latest_is_null_for_an_unheard_topic() {
    const m = makeModel(true);
    m.ingest(frameLine("speech.state"));
    compare(m.latest("audio.wake"), null, "silence must not read as a value");
    verify(m.latest("speech.state") !== null);
  }

  // --- parsing: a line we cannot trust changes nothing ----------------

  function test_ingest_records_a_well_formed_frame() {
    const m = makeModel(true);
    const seen = [];
    m.frameReceived.connect((topic, env) => seen.push([topic, env.seq]));

    m.ingest(frameLine("speech.state", {
      "seq": 7
    }));

    compare(m.received, 1);
    compare(m.latest("speech.state").seq, 7);
    compare(m.latest("speech.state").src, "test");
    compare(seen.length, 1);
    compare(seen[0][0], "speech.state");
    compare(seen[0][1], 7);
  }

  function test_junk_lines_are_dropped_without_touching_state_data() {
    return [
      {
        tag: "empty",
        line: ""
      },
      {
        tag: "not json",
        line: "{ this is not json",
        warn: true
      },
      {
        tag: "json scalar",
        line: "42"
      },
      {
        tag: "json null",
        line: "null"
      },
      {
        tag: "unknown kind",
        line: '{"t":"weather","frame":{"topic":"a"}}'
      },
      {
        tag: "frame without a frame",
        line: '{"t":"frame"}'
      },
      {
        tag: "frame without a topic",
        line: '{"t":"frame","frame":{"ts":1}}'
      },
      {
        tag: "topic is not a string",
        line: '{"t":"frame","frame":{"topic":3}}'
      }
    ];
  }

  function test_junk_lines_are_dropped_without_touching_state(data) {
    const m = makeModel(true);
    if (data.warn)
      ignoreWarning(/unparseable bridge line dropped/);
    m.ingest(data.line);
    compare(m.received, 0, data.tag + " must not count as a frame");
    compare(Object.keys(m.frames).length, 0);
    verify(!m.linkUp);
  }

  // --- the link: down means the HUD forgets --------------------------

  function test_link_up_then_down_empties_the_cache() {
    const m = makeModel(true);
    m.ingest('{"t":"link","up":true}');
    verify(m.linkUp);
    compare(m.linkError, "");

    m.ingest(frameLine("speech.state"));
    compare(Object.keys(m.frames).length, 1);

    m.ingest('{"t":"link","up":false,"err":"bridge stopped"}');
    verify(!m.linkUp);
    compare(m.linkError, "bridge stopped");
    compare(Object.keys(m.frames).length, 0, "a dead bus must show nothing");
    compare(m.latest("speech.state"), null);
  }

  function test_link_down_with_no_frames_is_harmless() {
    const m = makeModel(true);
    m.ingest('{"t":"link","up":false}');
    verify(!m.linkUp);
    compare(m.linkError, "");
    compare(Object.keys(m.frames).length, 0);
  }

  function test_coming_back_up_clears_the_reason_it_was_down() {
    // linkError describes the pipe RIGHT NOW. Left behind after a
    // reconnect it is a diagnostic that lies about a healthy link.
    const m = makeModel(true);
    m.ingest('{"t":"link","up":false,"err":"bridge stopped"}');
    compare(m.linkError, "bridge stopped");
    m.ingest('{"t":"link","up":true}');
    verify(m.linkUp);
    compare(m.linkError, "");

    // The contract is on the state, not on the wire: up means no error,
    // whatever anyone passes alongside it.
    m.applyLink(true, "nonsense");
    compare(m.linkError, "");
  }

  function test_received_survives_a_link_drop() {
    // The cache is what goes stale, not the fact that we have been awake.
    const m = makeModel(true);
    m.ingest(frameLine("speech.state"));
    m.ingest('{"t":"link","up":false,"err":"x"}');
    compare(m.received, 1);
  }

  // --- frames is replaced, never mutated -----------------------------

  function test_a_binding_on_frames_re_evaluates() {
    const m = makeModel(true);
    watcher.source = m;
    compare(watcher.topicCount, 0);
    m.ingest(frameLine("speech.state"));
    compare(watcher.topicCount, 1, "frames must be replaced so bindings fire");
    m.ingest(frameLine("audio.wake"));
    compare(watcher.topicCount, 2);
    m.ingest('{"t":"link","up":false}');
    compare(watcher.topicCount, 0, "a dropped link must un-draw what it drew");
    watcher.source = null;
  }

  function test_a_second_frame_on_a_topic_replaces_the_first() {
    const m = makeModel(true);
    m.ingest(frameLine("speech.state", {
      "seq": 1
    }));
    m.ingest(frameLine("speech.state", {
      "seq": 2
    }));
    compare(Object.keys(m.frames).length, 1);
    compare(m.latest("speech.state").seq, 2);
    compare(m.received, 2);
  }

  // --- age: only when it is actually knowable ------------------------

  function test_age_is_infinite_when_nothing_can_be_known_data() {
    return [
      {
        tag: "null envelope",
        env: null
      },
      {
        tag: "no ts",
        env: {
          "topic": "a"
        }
      },
      {
        tag: "ts is not a number",
        env: {
          "topic": "a",
          "ts": "soon"
        }
      }
    ];
  }

  function test_age_is_infinite_when_nothing_can_be_known(data) {
    const m = makeModel(true);
    m.ingest(frameLine("speech.state"));
    compare(m.ageOf(data.env), Infinity);
  }

  function test_age_is_infinite_before_the_first_frame() {
    const m = makeModel(true);
    compare(m.ageOf({
      "topic": "a",
      "ts": 100
    }), Infinity, "with no frame seen there is no offset, so no honest age");
  }

  function test_age_is_infinite_without_a_clock() {
    const m = makeModel(false);
    m.ingest(frameLine("speech.state"));
    compare(m.ageOf(m.latest("speech.state")), Infinity);
  }

  function test_age_counts_up_from_the_frame_that_pinned_the_clock() {
    const m = makeModel(true);
    suite.fakeNow = 4; // process has been up 4s; the bus says ts=100
    m.ingest(frameLine("speech.state", {
      "ts": 100
    }));
    fuzzyCompare(m.ageOf(m.latest("speech.state")), 0, 1e-9);
    suite.fakeNow = 6.5;
    fuzzyCompare(m.ageOf(m.latest("speech.state")), 2.5, 1e-9);
  }

  function test_the_offset_estimate_only_ever_improves() {
    // Each frame estimates (ts - elapsed); one delayed in flight estimates
    // LOW, which would make every frame look younger than it is. Keeping
    // the largest estimate converges on the truth from below.
    const m = makeModel(true);
    suite.fakeNow = 10;
    m.ingest(frameLine("late", {
      "ts": 100
    })); // spent 3s in flight -> offset 90
    suite.fakeNow = 13;
    m.ingest(frameLine("prompt", {
      "ts": 106
    })); // arrived promptly -> offset 93

    suite.fakeNow = 13;
    fuzzyCompare(m.ageOf(m.latest("prompt")), 0, 1e-9);
    fuzzyCompare(m.ageOf(m.latest("late")), 6, 1e-9);

    suite.fakeNow = 20;
    m.ingest(frameLine("later", {
      "ts": 107
    })); // 6s in flight -> estimate 87, worse: ignored
    fuzzyCompare(m.ageOf(m.latest("prompt")), 7, 1e-9);
  }

  function test_a_frame_without_a_ts_does_not_move_the_clock() {
    const m = makeModel(true);
    suite.fakeNow = 5;
    m.ingest(frameLine("a", {
      "ts": 100
    }));
    m.ingest('{"t":"frame","frame":{"topic":"b","seq":2}}');
    compare(m.received, 2, "a ts-less frame is still a frame");
    suite.fakeNow = 6;
    fuzzyCompare(m.ageOf(m.latest("a")), 1, 1e-9);
    compare(m.ageOf(m.latest("b")), Infinity);
  }
}
