// HeardState — "what did Jarvis hear you say?", under test (PLAN A26).
//
// This is the first element that renders the USER's words, so the failures
// worth writing tests around are the ones that would make it worse than
// the empty corner it replaces:
//
//   · showing a PARTIAL. Whisper rewrites the growing utterance every
//     0.7 s; a sentence that was on screen and then was never acted on is
//     a more expensive lie than saying nothing, and the schema draws the
//     same line ("only finals are acted on").
//   · showing words from a bus the HUD can no longer see. Every other
//     element drops what it cached on a dropped link; a stale transcript
//     is the same failure with a sentence attached.
//   · keeping the line up forever. Its exit is meant to be a real signal
//     — Jarvis starting to answer — with a backstop for the turn nobody
//     ever answers.
//   · dropping a line because the frame was odd in some way that has
//     nothing to do with the words. Refusing to read a frame is not the
//     same as being answered.
//
// Headless, like the rest of core/: HeardState is pure QtQuick and reads
// the bus through core/BusModel, driven with the same JSON lines
// jv-hud-bridge writes.
import QtQuick
import QtTest
import "../core"

TestCase {
  id: suite
  name: "HeardState"

  // The stand-in for CLOCK_MONOTONIC. Every frame is delivered at its own
  // `ts` so it lands zero seconds old; winding this forward is how the
  // backstop is made to fire without waiting for it.
  property real fakeNow: 0

  Component {
    id: busModel
    BusModel {}
  }

  Component {
    id: heardState
    HeardState {}
  }

  // createObject() is typed QObject, so every member read on the result
  // would be `missing-property` to qmllint. Going through an untyped
  // helper keeps the file lint-clean at -W 0 (see tst_speechstate).
  function spawn(component) {
    const o = component.createObject(suite);
    verify(o, "failed to instantiate a test object");
    return o;
  }

  // A HeardState on a live, subscribed link, with a clock we drive.
  // opts: { holdS: n } for a different backstop,
  //       { down: true } to leave the link down,
  //       { bus: obj } to hand it something other than a BusModel.
  function makeHeard(opts) {
    const o = opts || {};
    suite.fakeNow = 0;
    const heard = spawn(heardState);
    if (o.holdS !== undefined)
      heard.holdS = o.holdS;
    heard.bus = o.bus !== undefined ? o.bus : spawn(busModel);
    if (o.bus === undefined && o.down !== true)
      heard.bus.monotonic = () => suite.fakeNow;
    if (o.bus === undefined && o.down !== true)
      heard.bus.ingest('{"t":"link","up":true}');
    return heard;
  }

  // --- building the frames the bridge would write ----------------------

  property int nextSeq: 0

  function envelope(topic, ts, conf, body, extra) {
    const e = extra || {};
    return {
      "topic": topic,
      "ts": ts,
      "seq": e.seq !== undefined ? e.seq : suite.nextSeq++,
      "src": e.src !== undefined ? e.src : "jv-ears",
      "conf": conf,
      "v": e.v !== undefined ? e.v : 1,
      "body": body
    };
  }

  function deliver(heard, env) {
    if (typeof env.ts === "number")
      suite.fakeNow = Math.max(suite.fakeNow, env.ts);
    heard.bus.ingest(JSON.stringify({
      "t": "frame",
      "frame": env
    }));
  }

  // opts: { kind, utterance_id, lang, conf, ts, v, drop: [fields] }
  function transcript(heard, text, opts) {
    const o = opts || {};
    let body = {
      "kind": o.kind !== undefined ? o.kind : "final",
      "utterance_id": o.utterance_id !== undefined ? o.utterance_id : "utt-1",
      "text": text,
      "lang": o.lang !== undefined ? o.lang : "en",
      "t0": 0,
      "t1": 2
    };
    if (o.drop !== undefined)
      for (let i = 0; i < o.drop.length; i++)
        delete body[o.drop[i]];
    const env = suite.envelope("audio.transcript", o.ts !== undefined ? o.ts : suite.fakeNow, o.conf !== undefined ? o.conf : 0.88, body, o);
    deliver(heard, env);
    return env;
  }

  function speech(heard, state, ts) {
    deliver(heard, suite.envelope("speech.state", ts !== undefined ? ts : suite.fakeNow, 1, {
      "state": state
    }, {
      "src": "jv-voice"
    }));
  }

  // --- the ordinary turn ----------------------------------------------

  function test_nothing_is_shown_before_anyone_has_said_anything() {
    const heard = makeHeard();
    compare(heard.heard, false, "an empty corner is what a machine nobody is talking to looks like");
    compare(heard.text, "");
    compare(heard.lang, "");
    compare(heard.utteranceId, "");
  }

  function test_a_final_transcript_reaches_the_screen_verbatim() {
    const heard = makeHeard();
    transcript(heard, "Hey Jarvis, what time is it?");
    compare(heard.heard, true);
    compare(heard.text, "Hey Jarvis, what time is it?", "the words are shown, not a tidied version of them");
    compare(heard.lang, "en");
    compare(heard.utteranceId, "utt-1");
    compare(heard.foreignLang, false);
  }

  function test_the_line_leaves_when_jarvis_starts_answering() {
    // The ordinary exit, and the reason this plate needs no display timer:
    // once you can hear the reply, the reply is the better report on
    // whether you were heard.
    const heard = makeHeard();
    transcript(heard, "turn the volume down");
    compare(heard.heard, true);
    speech(heard, "speaking");
    compare(heard.heard, false);
    compare(heard.text, "", "the words go with the plate");
  }

  function test_the_answer_starting_is_remembered_after_jarvis_falls_silent() {
    // `bus.latest()` keeps one frame per topic, so the `speaking` frame is
    // GONE the moment jv-voice publishes the idle that follows it. Derived
    // rather than latched, the line would come back on screen for the rest
    // of the turn — and jv-voice returning to idle is the most ordinary
    // thing that happens next.
    const heard = makeHeard();
    transcript(heard, "what time is it");
    speech(heard, "speaking");
    speech(heard, "idle");
    compare(heard.heard, false, "an answered question came back from the dead");
  }

  function test_jarvis_going_quiet_is_not_jarvis_answering() {
    // Only `speaking` and `interrupted` mean the reply began. jv-voice
    // publishes on every transition, and an `idle` landing between the
    // transcript and the first spoken word — an errored say, a turn
    // somebody cancelled — is the answer NOT starting. Reading any state
    // at all as an answer would take the words away at exactly the moment
    // the user is still waiting for one.
    const heard = makeHeard();
    transcript(heard, "what time is it");
    speech(heard, "idle");
    compare(heard.heard, true, "a silent jv-voice was read as a reply");
    compare(heard.text, "what time is it");
  }

  function test_an_interruption_after_the_words_also_ends_them() {
    // jv-voice only ever publishes `interrupted` out of `speaking`, so one
    // stamped after these words means the answer to THEM began and was cut
    // off — by the next thing the user said, whose own final is on its way.
    const heard = makeHeard();
    transcript(heard, "read me the news");
    speech(heard, "interrupted");
    compare(heard.heard, false);
  }

  function test_jarvis_speaking_BEFORE_the_words_is_the_barge_in_that_caused_them() {
    // Wake detection stays live while jv-voice talks (A4), so the frame
    // sequence of a barge-in is: speaking, then the user's utterance, then
    // its transcript. A HUD that read the older `speaking` as "the answer
    // started" would blank the plate for exactly the utterance that
    // interrupted it — the one the user most wants to check.
    const heard = makeHeard();
    speech(heard, "speaking", 10);
    suite.fakeNow = 12;
    transcript(heard, "no, stop", {
      "ts": 12
    });
    compare(heard.heard, true);
    compare(heard.text, "no, stop");
  }

  function test_a_second_question_replaces_the_first() {
    const heard = makeHeard();
    transcript(heard, "what time is it", {
      "utterance_id": "utt-1"
    });
    transcript(heard, "what day is it", {
      "utterance_id": "utt-2"
    });
    compare(heard.text, "what day is it", "the newest thing the user said is the live one");
    compare(heard.utteranceId, "utt-2");
  }

  function test_a_new_question_re_opens_a_line_an_answer_had_closed() {
    // The `answering` latch belongs to the sentence it closed. Left
    // standing, the next thing the user says would never be shown at all.
    const heard = makeHeard();
    transcript(heard, "what time is it");
    speech(heard, "speaking");
    compare(heard.heard, false);
    suite.fakeNow += 5;
    transcript(heard, "and the date");
    compare(heard.heard, true);
    compare(heard.text, "and the date");
  }

  // --- partials are not what Jarvis acts on ----------------------------

  function test_a_partial_is_never_shown() {
    const heard = makeHeard();
    transcript(heard, "Hey Jarvis turn to", {
      "kind": "partial"
    });
    compare(heard.heard, false, "a provisional sentence must not read as the one Jarvis has");
  }

  function test_partials_do_not_disturb_the_final_they_precede() {
    const heard = makeHeard();
    transcript(heard, "Hey Jarvis turn to", {
      "kind": "partial"
    });
    transcript(heard, "Hey Jarvis, turn the volume down.", {
      "kind": "final"
    });
    compare(heard.text, "Hey Jarvis, turn the volume down.");
  }

  function test_the_next_utterances_partials_do_not_wipe_the_held_line() {
    // Partials ride the same topic, so `bus.latest()` replaces the final
    // with the next utterance's first partial. Derived instead of latched,
    // the plate would blank itself the instant the user started speaking
    // again — which is to say, at the busiest moment of a conversation.
    const heard = makeHeard();
    transcript(heard, "what time is it", {
      "utterance_id": "utt-1"
    });
    transcript(heard, "and the", {
      "kind": "partial",
      "utterance_id": "utt-2"
    });
    compare(heard.heard, true);
    compare(heard.text, "what time is it");
  }

  // --- the link ---------------------------------------------------------

  function test_a_bus_that_was_never_up_says_nothing() {
    const heard = makeHeard({
      "down": true
    });
    compare(heard.heard, false);
  }

  function test_the_link_dropping_forgets_the_words() {
    const heard = makeHeard();
    transcript(heard, "delete the backups");
    compare(heard.heard, true);
    heard.bus.ingest('{"t":"link","up":false,"err":"bridge stopped"}');
    compare(heard.heard, false);
    heard.bus.ingest('{"t":"link","up":true}');
    compare(heard.heard, false, "the link came back; the sentence did not");
  }

  function test_a_null_bus_is_blindness_and_not_an_exception() {
    failOnWarning(/TypeError/);
    const heard = spawn(heardState);
    compare(heard.heard, false);
    compare(heard.text, "");
  }

  function test_a_bus_that_cannot_be_asked_is_read_as_silence() {
    // A stand-in that says the link is up and offers no `latest` must not
    // throw inside a binding, where the only symptom is a warning nobody
    // reads and a plate that quietly never appears.
    failOnWarning(/TypeError/);
    const heard = makeHeard({
      "bus": ({
          "linkUp": true
        })
    });
    compare(heard.heard, false);
  }

  // --- the backstop -----------------------------------------------------

  function test_a_question_nobody_ever_answers_stops_being_asserted() {
    // A real timer on a short window, not a wound-forward clock: the
    // backstop is a Timer, and a test that moved only the fake clock would
    // pass whether or not one was ever armed.
    const heard = makeHeard({
      "holdS": 0.05
    });
    transcript(heard, "what is the weather");
    compare(heard.heard, true);
    tryCompare(heard, "heard", false, 1000, "a line nobody answered cannot stay up forever");
  }

  function test_the_backstop_times_the_words_and_not_their_arrival() {
    // A frame that spent time in flight is already partway through its own
    // window; arming the whole of it would hold a sentence past the point
    // the HUD can still say anything about it. The speech frame is here to
    // pin BusModel's clock offset first — the very first frame the HUD
    // ever sees necessarily lands at age zero, since it is the only
    // evidence there is about where the clock sits.
    const heard = makeHeard();
    suite.fakeNow = 100;
    speech(heard, "idle", 100);
    suite.fakeNow = 100 + heard.holdS + 5;
    transcript(heard, "an old sentence", {
      "ts": 100
    });
    compare(heard.heard, false, "a stale final was held as if it had just landed");
  }

  function test_the_backstop_is_re_armed_by_a_newer_question() {
    const heard = makeHeard({
      "holdS": 0.05
    });
    transcript(heard, "first");
    tryCompare(heard, "heard", false, 1000);
    suite.fakeNow += 1;
    transcript(heard, "second");
    compare(heard.heard, true, "a fresh sentence inherited the last one's expiry");
  }

  function test_an_untimeable_frame_is_not_held_open_forever() {
    // No clock means no age, which `ageOf` reports as Infinity. A line the
    // HUD cannot time is one it must not assert — the same direction every
    // other element errs in.
    const heard = spawn(heardState);
    heard.bus = spawn(busModel);
    heard.bus.ingest('{"t":"link","up":true}');
    transcript(heard, "a sentence with no clock behind it");
    compare(heard.heard, false);
  }

  // --- frames we will not read -----------------------------------------

  function test_a_future_schema_version_is_refused() {
    const heard = makeHeard();
    transcript(heard, "from a bus we do not speak", {
      "v": 2
    });
    compare(heard.heard, false, "a v2 body is not a v1 body (invariant 2)");
  }

  function test_a_frame_with_no_numeric_confidence_is_refused() {
    // Invariant 4: every producer publishes `conf`. Nothing further is done
    // with the value here — see the note at the top of HeardState — but a
    // frame that carries none is not one this element knows how to read.
    const heard = makeHeard();
    transcript(heard, "how confident are you", {
      "conf": "high"
    });
    compare(heard.heard, false);
  }

  function test_a_quiet_confidence_is_still_shown() {
    // The lowest confidence in the committed recordings is 0.739, on a
    // transcript whose words are exactly right. A bar above it would hide
    // the sentence the user most needs to read, on the day the room is
    // noisiest. tst_sessionreplay pins this against the real numbers.
    const heard = makeHeard();
    transcript(heard, "turn the volume down", {
      "conf": 0.42
    });
    compare(heard.heard, true);
    compare(heard.text, "turn the volume down");
  }

  function test_a_final_with_no_utterance_id_is_refused() {
    const heard = makeHeard();
    transcript(heard, "whose words are these", {
      "drop": ["utterance_id"]
    });
    compare(heard.heard, false);
  }

  function test_a_final_with_no_language_is_refused() {
    const heard = makeHeard();
    transcript(heard, "in what tongue", {
      "drop": ["lang"]
    });
    compare(heard.heard, false);
  }

  function test_text_that_is_not_a_string_is_refused_by_type() {
    failOnWarning(/TypeError/);
    const heard = makeHeard();
    transcript(heard, 42);
    compare(heard.heard, false);
  }

  function test_a_final_that_says_nothing_is_not_a_reading() {
    const heard = makeHeard();
    transcript(heard, "   \n  ");
    compare(heard.heard, false, "a blank plate is not a transcript");
  }

  function test_a_final_with_no_timestamp_cannot_displace_a_good_one() {
    // Without a `ts` there is no age, so there is no backstop — the line
    // would be held for as long as the HUD ran. Refusing it at the door is
    // what keeps that from also COSTING the sentence already on screen:
    // an unreadable frame is no news, not a replacement.
    const heard = makeHeard();
    transcript(heard, "the sentence that matters");
    let env = suite.envelope("audio.transcript", 0, 0.88, {
      "kind": "final",
      "utterance_id": "utt-2",
      "text": "a frame nobody can place in time",
      "lang": "en"
    });
    delete env.ts;
    deliver(heard, env);
    compare(heard.heard, true);
    compare(heard.text, "the sentence that matters");
  }

  function test_an_unreadable_frame_leaves_the_held_line_where_it_was() {
    // Refusing to read a frame is never the same as being answered.
    const heard = makeHeard();
    transcript(heard, "the sentence that matters");
    transcript(heard, "from the future", {
      "v": 2
    });
    compare(heard.heard, true);
    compare(heard.text, "the sentence that matters");
  }

  // --- how the sentence is carried -------------------------------------

  function test_line_breaks_inside_a_sentence_do_not_reshape_the_plate() {
    const heard = makeHeard();
    transcript(heard, "remind me\nto call\tmy sister");
    compare(heard.text, "remind me to call my sister");
  }

  function test_surrounding_whitespace_is_not_part_of_what_was_said() {
    const heard = makeHeard();
    transcript(heard, "  hello  ");
    compare(heard.text, "hello");
  }

  function test_nothing_in_the_sentence_itself_is_edited() {
    // Punctuation, capitals and all: the misheard word IS the signal, and
    // a HUD that cleaned the transcript up would hide the one thing the
    // user came to this plate to see.
    const heard = makeHeard();
    transcript(heard, "Hey Jarvis, remind me to. Call my sister tomorrow morning.");
    compare(heard.text, "Hey Jarvis, remind me to. Call my sister tomorrow morning.");
  }

  // --- the language the machine does not expect -------------------------

  function test_a_language_the_asr_cannot_actually_speak_is_flagged() {
    // faster-distil-small.en is English-only, so a frame claiming Hebrew
    // means the model is making English words out of audio it cannot
    // represent. The words are still shown — they are what Jarvis will act
    // on — with the tag saying where they came from.
    const heard = makeHeard();
    transcript(heard, "shalom what time is it", {
      "lang": "he"
    });
    compare(heard.heard, true);
    compare(heard.lang, "he");
    compare(heard.foreignLang, true);
  }

  function test_the_expected_language_is_named_once_and_not_hard_coded() {
    const heard = makeHeard();
    heard.expectedLang = "he";
    transcript(heard, "what time is it", {
      "lang": "he"
    });
    compare(heard.foreignLang, false);
  }
}
