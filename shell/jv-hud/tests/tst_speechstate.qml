// SpeechState — "what is Jarvis doing?", under test (PLAN A3).
//
// This is the HUD's first element backed by real sensor topics, so it is
// also the first place invariant 10 can be broken by arithmetic rather
// than by intent. The rules these tests defend:
//
//   · with no link, or no frame, the answer is "unknown" — never "idle".
//     Silence and calm are different things and only one of them is a
//     state we observed.
//   · "listening" is a claim about the microphone. It must end when the
//     bus says it ended (Jarvis answered, or the utterance closed), and
//     it must expire on its own when nothing says anything at all.
//   · a frame we cannot trust — wrong schema version, a wake that missed
//     its own threshold, a state topic hedging its confidence — changes
//     nothing. Under-claiming is the safe error; over-claiming is a lie.
//
// Everything runs headless (see tst_busmodel.qml): SpeechState is pure
// QtQuick and reads the bus through core/BusModel, which the test drives
// by hand with the same JSON lines the bridge writes.
import QtQuick
import QtTest
import "../core"

TestCase {
  id: suite
  name: "SpeechState"

  // A stand-in for CLOCK_MONOTONIC that the test drives. Frames are sent
  // with ts = fakeNow + 100, so the model pins an offset of exactly 100
  // and a frame is zero seconds old the moment it lands; winding fakeNow
  // forward is how a frame gets older.
  property real fakeNow: 0

  Component {
    id: busModel
    BusModel {}
  }

  Component {
    id: speechState
    SpeechState {}
  }

  // `createObject` hands back a bare QObject as far as qmllint can tell,
  // and every member read on one is then an unresolvable property. Routing
  // instantiation through an untyped function is how tst_busmodel stays
  // lint-clean too: the linter stops guessing, and the engine does not care.
  function spawn(component) {
    const o = component.createObject(suite);
    verify(o, "failed to instantiate a test object");
    return o;
  }

  // opts: { clock: false } to withhold the monotonic clock,
  //       { down: true } to leave the bridge link down,
  //       { windowS: n } for a shorter wake window.
  function makeVoice(opts) {
    const o = opts || {};
    suite.fakeNow = 0;
    const bus = spawn(busModel);
    if (o.clock !== false)
      bus.monotonic = () => suite.fakeNow;
    const voice = spawn(speechState);
    if (o.windowS !== undefined)
      voice.wakeWindowS = o.windowS;
    voice.bus = bus;
    if (o.down !== true)
      bus.ingest('{"t":"link","up":true}');
    return voice;
  }

  function send(voice, topic, body, over) {
    let env = {
      "topic": topic,
      "ts": suite.fakeNow + 100,
      "seq": suite.seq++,
      "src": "test",
      "conf": 1.0,
      "v": 1,
      "body": body
    };
    for (const k in over || {})
      env[k] = over[k];
    voice.bus.ingest(JSON.stringify({
      "t": "frame",
      "frame": env
    }));
  }

  property int seq: 1

  function speech(voice, state, over) {
    send(voice, "speech.state", {
      "state": state
    }, over);
  }

  function wake(voice, body, over) {
    let b = {
      "model": "hey_jarvis",
      "score": 0.91,
      "threshold": 0.5
    };
    for (const k in body || {})
      b[k] = body[k];
    send(voice, "audio.wake", b, over);
  }

  function vad(voice, event, over) {
    send(voice, "audio.vad", {
      "event": event,
      "utterance_id": "u1"
    }, over);
  }

  // --- silence is not calm -------------------------------------------

  function test_without_a_bus_nothing_is_known() {
    const voice = spawn(speechState);
    compare(voice.state, "unknown");
    verify(!voice.known);
    verify(!voice.active);
    verify(!voice.idle);
  }

  function test_a_down_link_shows_nothing_even_with_a_frame_in_hand() {
    // BusModel caches whatever it is fed; the element must still refuse to
    // render it while the bridge says it holds no live subscription.
    const voice = makeVoice({
      down: true
    });
    speech(voice, "speaking");
    compare(voice.state, "unknown");
  }

  function test_a_live_but_silent_bus_is_unknown_not_idle() {
    const voice = makeVoice();
    compare(voice.state, "unknown", "never heard from jv-voice is not the same as idle");
    verify(!voice.known);
  }

  function test_a_dropped_link_forgets_what_jarvis_was_doing() {
    const voice = makeVoice();
    speech(voice, "speaking");
    compare(voice.state, "speaking");
    voice.bus.ingest('{"t":"link","up":false,"err":"bridge stopped"}');
    compare(voice.state, "unknown", "a dead bus must not keep Jarvis talking");
  }

  // --- speech.state maps straight through -----------------------------

  function test_speech_state_is_reported_as_published_data() {
    return [
      {
        tag: "idle",
        state: "idle"
      },
      {
        tag: "speaking",
        state: "speaking"
      },
      {
        tag: "interrupted",
        state: "interrupted"
      }
    ];
  }

  function test_speech_state_is_reported_as_published(data) {
    const voice = makeVoice();
    speech(voice, data.state);
    compare(voice.state, data.state);
    verify(voice.known);
  }

  function test_a_state_word_we_do_not_know_reads_as_unknown() {
    // A later schema version may add states. Rendering one we were not
    // written against as the nearest thing we do know would be inventing.
    const voice = makeVoice();
    speech(voice, "thinking");
    compare(voice.state, "unknown");
  }

  function test_active_is_only_true_while_jarvis_is_doing_something_data() {
    return [
      {
        tag: "idle",
        state: "idle",
        active: false
      },
      {
        tag: "speaking",
        state: "speaking",
        active: true
      },
      {
        tag: "interrupted",
        state: "interrupted",
        active: false
      }
    ];
  }

  function test_active_is_only_true_while_jarvis_is_doing_something(data) {
    const voice = makeVoice();
    speech(voice, data.state);
    compare(voice.active, data.active);
    compare(voice.idle, data.state === "idle");
  }

  // --- listening: the claim that costs the most if it is wrong --------

  function test_a_wake_word_means_listening() {
    const voice = makeVoice();
    speech(voice, "idle");
    wake(voice);
    compare(voice.state, "listening");
    verify(voice.active);
  }

  function test_a_wake_is_listening_even_before_jv_voice_has_spoken() {
    // The wake is a fact on its own; it does not need jv-voice's opinion.
    const voice = makeVoice();
    wake(voice);
    compare(voice.state, "listening");
  }

  function test_a_wake_that_cannot_be_aged_is_never_listening() {
    // No clock means no age, which means no way to know the window has not
    // already closed. The honest answer is the state we last observed.
    const voice = makeVoice({
      clock: false
    });
    speech(voice, "idle");
    wake(voice);
    compare(voice.state, "idle");
  }

  function test_a_wake_that_arrives_already_stale_is_not_listening() {
    // Frames queued behind a slow consumer arrive late. One older than the
    // window describes a moment that has passed.
    const voice = makeVoice();
    speech(voice, "idle");
    wake(voice, {}, {
      "ts": suite.fakeNow + 100 - 20
    });
    compare(voice.state, "idle");
  }

  function test_listening_expires_when_nothing_else_ever_arrives() {
    // jv-ears disarms after wake_timeout_s with no speech, and publishes
    // nothing when it does. The HUD must let go on its own or it lies for
    // as long as the machine stays quiet.
    const voice = makeVoice({
      windowS: 0.05
    });
    speech(voice, "idle");
    wake(voice);
    compare(voice.state, "listening");
    tryCompare(voice, "state", "idle", 3000, "a wake window must close by itself");
  }

  function test_a_wake_delivered_late_gets_only_what_is_left_of_its_window() {
    // A frame that spent 0.45 s in flight is 0.45 s into its own window,
    // not at the start of one. Arming the whole window on arrival would
    // hold "listening" open past the moment ears gave up.
    const voice = makeVoice({
      windowS: 0.5
    });
    speech(voice, "idle");
    wake(voice, {}, {
      "ts": suite.fakeNow + 100 - 0.45
    });
    compare(voice.state, "listening");
    tryCompare(voice, "state", "idle", 250, "the window closes when it was opened, not when we heard");
  }

  function test_shortening_the_window_closes_an_open_one() {
    const voice = makeVoice();
    wake(voice);
    compare(voice.state, "listening");
    voice.wakeWindowS = 0.05;
    tryCompare(voice, "state", "unknown", 3000);
  }

  function test_a_second_wake_reopens_a_window_that_had_closed() {
    const voice = makeVoice({
      windowS: 0.05
    });
    speech(voice, "idle");
    wake(voice);
    tryCompare(voice, "state", "idle", 3000);
    suite.fakeNow += 1;
    wake(voice);
    compare(voice.state, "listening");
  }

  // --- listening ends on evidence, not only on a timer ----------------

  function test_jarvis_answering_ends_listening() {
    const voice = makeVoice();
    wake(voice);
    compare(voice.state, "listening");
    suite.fakeNow += 1;
    speech(voice, "speaking");
    compare(voice.state, "speaking", "Jarvis answering means it heard you");
  }

  function test_a_wake_during_speech_is_barge_in_and_reads_as_listening() {
    // Wake detection stays live while jv-voice talks (that is barge-in).
    // The speaking frame is older than the wake, so it is not an answer to
    // it, and the user's word has already landed.
    const voice = makeVoice();
    speech(voice, "speaking");
    suite.fakeNow += 1;
    wake(voice);
    compare(voice.state, "listening");
  }

  function test_being_interrupted_does_not_end_listening() {
    // jv-voice publishes interrupted BECAUSE of the wake. Reading that as
    // the end of the listening window would blank the HUD at the exact
    // moment the user is talking.
    const voice = makeVoice();
    speech(voice, "speaking");
    suite.fakeNow += 1;
    wake(voice);
    suite.fakeNow += 0.2;
    speech(voice, "interrupted");
    compare(voice.state, "listening");
  }

  function test_the_end_of_the_utterance_ends_listening() {
    // jv-ears disarms at speech_end for a wake-gated utterance: it is
    // transcribing now, not listening for more.
    const voice = makeVoice();
    speech(voice, "idle");
    wake(voice);
    suite.fakeNow += 0.3;
    vad(voice, "speech_start");
    compare(voice.state, "listening", "the user talking is the window being used");
    suite.fakeNow += 2;
    vad(voice, "speech_end");
    compare(voice.state, "idle");
  }

  function test_an_older_utterance_end_does_not_end_a_newer_wake() {
    const voice = makeVoice();
    speech(voice, "idle");
    vad(voice, "speech_end");
    suite.fakeNow += 1;
    wake(voice);
    compare(voice.state, "listening");
  }

  function test_a_frame_with_no_usable_timestamp_is_not_a_state() {
    // Ordering a wake against a speech transition is the whole of the
    // listening rule, and ordering needs a comparable ts. A frame without
    // one is dropped rather than guessed at — and dropping the newest
    // frame on a topic means the topic goes back to unknown, because the
    // one before it is no longer what the bus is saying.
    const voice = makeVoice();
    speech(voice, "idle");
    compare(voice.state, "idle");
    speech(voice, "speaking", {
      "ts": "soon"
    });
    compare(voice.state, "unknown", "a frame we cannot order is a frame we cannot use");
  }

  // --- frames we refuse to believe ------------------------------------

  function test_a_wake_below_its_own_threshold_is_ignored() {
    const voice = makeVoice();
    speech(voice, "idle");
    wake(voice, {
      "score": 0.4,
      "threshold": 0.5
    }, {
      "conf": 0.4
    });
    compare(voice.state, "idle", "a detection that missed its bar is not a detection");
  }

  function test_a_wake_whose_confidence_contradicts_its_score_is_ignored() {
    // conf mirrors score (schemas/audio.wake.json). A frame that disagrees
    // with itself is one the HUD cannot reason about (invariant 4).
    const voice = makeVoice();
    speech(voice, "idle");
    wake(voice, {}, {
      "conf": 0.1
    });
    compare(voice.state, "idle");
  }

  function test_frames_from_an_unknown_schema_version_are_not_rendered_data() {
    return [
      {
        tag: "speech.state v2",
        topic: "speech.state"
      },
      {
        tag: "audio.wake v2",
        topic: "audio.wake"
      }
    ];
  }

  function test_frames_from_an_unknown_schema_version_are_not_rendered(data) {
    const voice = makeVoice();
    speech(voice, "idle");
    if (data.topic === "speech.state") {
      speech(voice, "speaking", {
        "v": 2
      });
      compare(voice.state, "unknown", "v2 bodies are not v1 bodies");
    } else {
      wake(voice, {}, {
        "v": 2
      });
      compare(voice.state, "idle");
    }
  }

  function test_a_state_frame_that_hedges_its_confidence_is_not_a_state() {
    // speech.state is a state topic: the envelope schema fixes its conf at
    // 1.0. Something less than certain is not something to render.
    const voice = makeVoice();
    speech(voice, "speaking", {
      "conf": 0.5
    });
    compare(voice.state, "unknown");
  }

  function test_a_malformed_body_changes_nothing_data() {
    return [
      {
        tag: "state is not a string",
        body: {
          "state": 3
        }
      },
      {
        tag: "no state at all",
        body: {
          "reason": "completed"
        }
      }
    ];
  }

  function test_a_malformed_body_changes_nothing(data) {
    const voice = makeVoice();
    send(voice, "speech.state", data.body);
    compare(voice.state, "unknown");
  }
}
