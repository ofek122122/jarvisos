// ReplyState — "the answer you heard was not the whole answer", under test
// (PLAN A71).
//
// `brain.response.finish_reason` has had three words since v1 and the HUD
// has never read any of them for their meaning. The failures worth writing
// tests around are the ones that would make this element worse than the
// empty corner it replaces:
//
//   · saying a reply was cut off when it finished. Every completed turn
//     would put a plate on screen, which is the corner nobody reads on the
//     day it matters (the HealthPlate argument, A6).
//   · reporting `error` here as well as through jv-brain's own `degraded`
//     heartbeat. One event, two plates, two colours, one corner — which is
//     A62's confusion built on purpose.
//   · holding the news past the turn it is about. `bus.latest()` keeps one
//     frame per topic, so a derived answer would leave the plate up from
//     one truncated reply until the next one, which on a quiet machine is
//     forever.
//   · dropping it for the wrong reason — a `speaking` frame that is the
//     truncated reply STILL BEING READ OUT, or a frame this element merely
//     could not parse.
//
// Headless, like the rest of core/: ReplyState is pure QtQuick and reads
// the bus through core/BusModel, driven with the same JSON lines
// jv-hud-bridge writes.
import QtQuick
import QtTest
import "../core"

TestCase {
  id: suite
  name: "ReplyState"

  // The stand-in for CLOCK_MONOTONIC. Every frame is delivered at its own
  // `ts` so it lands zero seconds old; winding this forward is how the
  // backstop is made to fire without waiting for it.
  property real fakeNow: 0

  Component {
    id: busModel
    BusModel {}
  }

  Component {
    id: replyState
    ReplyState {}
  }

  // createObject() is typed QObject, so every member read on the result
  // would be `missing-property` to qmllint. Going through an untyped
  // helper keeps the file lint-clean at -W 0 (see tst_speechstate).
  function spawn(component) {
    const o = component.createObject(suite);
    verify(o, "failed to instantiate a test object");
    return o;
  }

  // A ReplyState on a live, subscribed link, with a clock we drive.
  // opts: { holdS: n } for a different backstop,
  //       { down: true } to leave the link down,
  //       { bus: obj } to hand it something other than a BusModel.
  function makeReply(opts) {
    const o = opts || {};
    suite.fakeNow = 0;
    const rep = spawn(replyState);
    if (o.holdS !== undefined)
      rep.holdS = o.holdS;
    rep.bus = o.bus !== undefined ? o.bus : spawn(busModel);
    if (o.bus === undefined && o.down !== true) {
      rep.bus.monotonic = () => suite.fakeNow;
      rep.bus.ingest('{"t":"link","up":true}');
    }
    return rep;
  }

  // --- building the frames the bridge would write ----------------------

  property int nextSeq: 0

  function envelope(topic, ts, conf, body, extra) {
    const e = extra || {};
    return {
      "topic": topic,
      "ts": ts,
      "seq": e.seq !== undefined ? e.seq : suite.nextSeq++,
      "src": e.src !== undefined ? e.src : "jv-brain",
      "conf": conf,
      "v": e.v !== undefined ? e.v : 1,
      "body": body
    };
  }

  function deliver(rep, env) {
    if (typeof env.ts === "number")
      suite.fakeNow = Math.max(suite.fakeNow, env.ts);
    rep.bus.ingest(JSON.stringify({
      "t": "frame",
      "frame": env
    }));
  }

  // jv-brain ending a turn. opts: { finish, text, ts, conf, v, seq, noTs,
  // drop: [fields] }. The defaults are the case this element exists for:
  // a reply that the context limit stopped mid-sentence.
  function response(rep, opts) {
    const o = opts || {};
    let body = {
      "text": o.text !== undefined ? o.text : "The meeting is at three, and the one after it is",
      "finish_reason": o.finish !== undefined ? o.finish : "length",
      "conversation_id": "5ab8fecf-13d0-4f86-aa5d-0b2cc23b4d5d",
      "backend": "cpu",
      "latency_ms": 8412
    };
    if (o.drop !== undefined)
      for (let i = 0; i < o.drop.length; i++)
        delete body[o.drop[i]];
    const env = suite.envelope("brain.response", o.ts !== undefined ? o.ts : suite.fakeNow, o.conf !== undefined ? o.conf : 1, body, o);
    if (o.noTs === true)
      delete env.ts;
    deliver(rep, env);
    return env;
  }

  // The wake word firing: the user starting again.
  function wake(rep, ts, extra) {
    const e = extra || {};
    deliver(rep, suite.envelope("audio.wake", ts !== undefined ? ts : suite.fakeNow, e.conf !== undefined ? e.conf : 1, {
      "phrase": "hey_jarvis",
      "score": 0.91
    }, {
      "src": "jv-ears",
      "v": e.v
    }));
  }

  // Something asking jv-brain a question in words — `jv ask`, onboarding.
  function request(rep, ts) {
    deliver(rep, suite.envelope("brain.request", ts !== undefined ? ts : suite.fakeNow, 1, {
      "text": "and what about tomorrow?",
      "source": "cli"
    }));
  }

  function speech(rep, state, ts) {
    deliver(rep, suite.envelope("speech.state", ts !== undefined ? ts : suite.fakeNow, 1, {
      "state": state
    }, {
      "src": "jv-voice"
    }));
  }

  // --- the ordinary truncation -----------------------------------------

  function test_nothing_is_shown_before_jarvis_has_answered_anything() {
    const rep = makeReply();
    compare(rep.truncated, false, "an empty corner is what a machine nobody has asked anything looks like");
    compare(rep.reason, "");
  }

  function test_a_truncated_reply_is_reported_in_the_schemas_own_word() {
    const rep = makeReply();
    response(rep);
    compare(rep.truncated, true);
    compare(rep.reason, "length", "the schema's word, not a friendlier paraphrase");
  }

  function test_a_reply_that_finished_is_not_news() {
    // §06's earned emptiness. The reply itself is the report that the
    // reply arrived; a plate per turn is a corner that is busy all day.
    const rep = makeReply();
    response(rep, {
      "finish": "stop"
    });
    compare(rep.truncated, false);
    compare(rep.reason, "");
  }

  function test_a_brain_that_could_not_answer_at_all_is_not_this_plates_news() {
    // `error` reaches the screen already: the same `except` block in
    // jv-brain publishes a `degraded` sys.health one await later, and
    // HealthPlate draws it. Two plates about one event is A62's confusion
    // built deliberately.
    const rep = makeReply();
    response(rep, {
      "finish": "error",
      "text": ""
    });
    compare(rep.truncated, false);
  }

  function test_the_reply_itself_never_reaches_an_output() {
    // Invariant 7. The element reads `text` for one thing — whether there
    // was anything to cut off — and exposes a frozen enum word and a bool.
    const rep = makeReply();
    response(rep, {
      "text": "the private half of a conversation"
    });
    compare(rep.truncated, true);
    compare(rep.reason, "length", "the only string this element offers is the schema's own word");
  }

  // --- letting go of it ------------------------------------------------

  function test_a_later_complete_reply_takes_the_truncation_off_the_screen() {
    // The user asked again and got a whole answer. Holding "your answer
    // was cut off" over it describes a conversation that is not the one
    // being had.
    const rep = makeReply();
    response(rep);
    compare(rep.truncated, true);
    response(rep, {
      "finish": "stop",
      "ts": suite.fakeNow + 20
    });
    compare(rep.truncated, false);
  }

  function test_a_later_errored_turn_also_takes_it_off_the_screen() {
    // Not drawn here and still a NEWER TURN. Passing it over as no news
    // would leave the last truncation on screen describing the turn
    // before the one that just failed.
    const rep = makeReply();
    response(rep);
    response(rep, {
      "finish": "error",
      "text": "",
      "ts": suite.fakeNow + 20
    });
    compare(rep.truncated, false);
  }

  function test_a_truncation_with_nothing_in_it_is_refused() {
    // The schema allows an empty `text` only with `error`. A `length`
    // with no text cut nothing off, and the plate would be a claim about
    // words the user never heard.
    const rep = makeReply();
    response(rep, {
      "text": ""
    });
    compare(rep.truncated, false);
  }

  function test_asking_again_out_loud_takes_it_off_the_screen() {
    const rep = makeReply();
    response(rep);
    wake(rep, suite.fakeNow + 4);
    compare(rep.truncated, false, "a wake after the truncation is the user replacing it");
  }

  function test_the_wake_that_started_the_turn_does_not_end_it() {
    // Every voice turn begins with one, and it is always older than the
    // reply it led to. An element that compared existence rather than
    // time would never show anything at all.
    const rep = makeReply();
    wake(rep, 1);
    response(rep, {
      "ts": 9
    });
    compare(rep.truncated, true);
  }

  function test_a_wake_already_newer_than_the_reply_ends_it_on_arrival() {
    // jv-voice is usually still speaking the sentences jv-brain streamed
    // when brain.response lands, so a barge-in can be stamped AFTER the
    // frame that closed the turn — and it reaches this element first.
    const rep = makeReply();
    wake(rep, 30);
    response(rep, {
      "ts": 22
    });
    compare(rep.truncated, false, "a truncation the user had already moved past arrived on screen");
  }

  function test_a_typed_question_takes_it_off_the_screen_too() {
    const rep = makeReply();
    response(rep);
    request(rep, suite.fakeNow + 3);
    compare(rep.truncated, false);
  }

  function test_the_request_that_asked_for_this_reply_does_not_end_it() {
    const rep = makeReply();
    request(rep, 1);
    response(rep, {
      "ts": 9
    });
    compare(rep.truncated, true);
  }

  function test_jarvis_still_reading_the_cut_off_reply_does_not_end_it() {
    // The one exit ActionState has and this element deliberately does not.
    // brain.response is published when the STREAM closes; jv-voice is
    // still working through the sentences it was handed, so a `speaking`
    // stamped after the truncation is the truncated reply being read out.
    // Leaving on it would take the plate down while the user is still
    // listening to the thing it is about.
    const rep = makeReply();
    response(rep);
    speech(rep, "speaking", suite.fakeNow + 1);
    speech(rep, "idle", suite.fakeNow + 6);
    compare(rep.truncated, true);
  }

  // --- the link --------------------------------------------------------

  function test_a_hud_that_never_saw_the_bus_claims_nothing() {
    const rep = makeReply({
      "down": true
    });
    compare(rep.truncated, false);
    compare(rep.reason, "");
  }

  function test_losing_the_bus_forgets_the_truncation() {
    // A cached frame from a link that has since dropped describes a
    // machine the HUD can no longer see.
    const rep = makeReply();
    response(rep);
    compare(rep.truncated, true);
    rep.bus.ingest('{"t":"link","up":false,"err":"bus.sock: connection refused"}');
    compare(rep.truncated, false);
    rep.bus.ingest('{"t":"link","up":true}');
    compare(rep.truncated, false, "a reconnect brought a forgotten truncation back to life");
  }

  function test_a_bus_with_no_frames_at_all_says_nothing() {
    const rep = makeReply({
      "bus": ({
          "linkUp": true
        })
    });
    compare(rep.truncated, false);
  }

  // --- the backstop ----------------------------------------------------

  function test_the_truncation_expires_on_its_own() {
    // Nobody is coming to explain this one: jv-brain does not say its
    // reply was cut off in any way a later frame carries. For a user who
    // asks one question and walks away, the timer IS the exit.
    const rep = makeReply({
      "holdS": 0.12
    });
    response(rep);
    compare(rep.truncated, true);
    tryCompare(rep, "truncated", false, 2000);
  }

  function test_a_reply_that_arrives_already_old_is_never_shown() {
    // Whatever is LEFT of the window, not the whole of it. The clock has
    // to be pinned by a frame this element does not read before the stale
    // one lands: BusModel estimates the offset between `ts` and its own
    // clock FROM the frames, and a lone frame is always zero seconds old
    // by construction.
    const rep = makeReply({
      "holdS": 5
    });
    speech(rep, "idle", 60);
    response(rep, {
      "ts": 10
    });
    compare(rep.truncated, false);
  }

  function test_a_newer_truncation_starts_the_window_again() {
    const rep = makeReply({
      "holdS": 0.2
    });
    response(rep, {
      "ts": 1
    });
    tryCompare(rep, "truncated", false, 2000);
    response(rep, {
      "ts": 2
    });
    compare(rep.truncated, true, "a second cut-off reply is its own news");
  }

  function test_a_reply_with_no_timestamp_is_refused() {
    // Without a `ts` there is no age, so there is no backstop — and a
    // line the HUD cannot time is one it would hold forever.
    const rep = makeReply();
    response(rep, {
      "noTs": true
    });
    compare(rep.truncated, false);
  }

  // --- frames this element will not read -------------------------------

  function test_a_reply_from_a_schema_we_were_not_written_against_is_refused() {
    const rep = makeReply();
    response(rep, {
      "v": 2
    });
    compare(rep.truncated, false);
  }

  function test_a_hedged_reply_is_refused() {
    // schemas/brain.response.json fixes envelope conf at 1.0 in v0. A
    // hedged one is not a frame this element was written against.
    const rep = makeReply();
    response(rep, {
      "conf": 0.6
    });
    compare(rep.truncated, false);
  }

  function test_a_reply_that_does_not_say_how_it_ended_is_refused() {
    const rep = makeReply();
    response(rep, {
      "drop": ["finish_reason"]
    });
    compare(rep.truncated, false);
  }

  function test_a_reply_with_no_text_field_at_all_is_refused() {
    const rep = makeReply();
    response(rep, {
      "drop": ["text"]
    });
    compare(rep.truncated, false);
  }

  function test_a_word_outside_the_frozen_enum_is_not_a_truncation() {
    const rep = makeReply();
    response(rep, {
      "finish": "truncated"
    });
    compare(rep.truncated, false, "only the schema's own words decide this");
  }

  function test_refusing_a_frame_is_not_the_same_as_being_answered() {
    // A held line survives frames this element cannot read. Refusal is the
    // absence of news, never news of a reply that arrived whole.
    const rep = makeReply();
    response(rep);
    response(rep, {
      "finish": "stop",
      "v": 2,
      "ts": suite.fakeNow + 5
    });
    compare(rep.truncated, true, "an unreadable frame took a real truncation off the screen");
    compare(rep.reason, "length");
  }

  function test_an_unreadable_wake_does_not_end_the_line() {
    const rep = makeReply();
    response(rep);
    wake(rep, suite.fakeNow + 4, {
      "v": 2
    });
    compare(rep.truncated, true);
  }
}
