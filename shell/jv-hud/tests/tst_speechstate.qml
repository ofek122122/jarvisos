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
//   · "thinking" (A12) is the gap between Jarvis hearing you and you
//     hearing anything back. It may only be shown while a prompt the
//     brain is actually going to answer is outstanding, it must yield to
//     whatever jv-voice says is audible right now, and it must end — on
//     the reply, on the first spoken word, or on its own.
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
  //       { windowS: n } for a shorter wake window,
  //       { thinkS: n } for a shorter thinking window.
  function makeVoice(opts) {
    const o = opts || {};
    suite.fakeNow = 0;
    const bus = spawn(busModel);
    if (o.clock !== false)
      bus.monotonic = () => suite.fakeNow;
    const voice = spawn(speechState);
    if (o.windowS !== undefined)
      voice.wakeWindowS = o.windowS;
    if (o.thinkS !== undefined)
      voice.thinkWindowS = o.thinkS;
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

  function ask(voice, body, over) {
    let b = {
      "text": "what is the time",
      "source": "cli"
    };
    for (const k in body || {})
      b[k] = body[k];
    send(voice, "brain.request", b, over);
  }

  function reply(voice, body, over) {
    let b = {
      "text": "Nine o'clock.",
      "finish_reason": "stop"
    };
    for (const k in body || {})
      b[k] = body[k];
    send(voice, "brain.response", b, over);
  }

  // One complete thing said to Jarvis through the voice path: the wake
  // word, then two seconds of speech, then the boundary jv-ears disarms
  // on. Nothing publishes "the brain accepted this" — the gated utterance
  // ending IS the evidence, which is what makes it worth a helper.
  function utterance(voice) {
    wake(voice);
    suite.fakeNow += 2;
    vad(voice, "speech_end");
  }

  // The same thing, but it finished `agoS` seconds ago: BOTH frames are
  // backdated, the wake a hair earlier so the boundary still closes a
  // window that was genuinely open. Backdating only the vad would leave
  // the wake fresh, and "listening" outranks everything.
  function utteranceEndedAgo(voice, agoS) {
    wake(voice, {}, {
      "ts": suite.fakeNow + 100 - agoS - 0.01
    });
    vad(voice, "speech_end", {
      "ts": suite.fakeNow + 100 - agoS
    });
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
    // transcribing now, not listening for more. The microphone claim ends
    // there; what replaces it is A12's business, tested below.
    const voice = makeVoice();
    speech(voice, "idle");
    wake(voice);
    suite.fakeNow += 0.3;
    vad(voice, "speech_start");
    compare(voice.state, "listening", "the user talking is the window being used");
    suite.fakeNow += 2;
    vad(voice, "speech_end");
    verify(!voice.listening, "the window must close whatever is drawn next");
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

  // --- thinking: the gap between hearing and answering (A12) ----------

  function test_a_wake_gated_utterance_ending_means_thinking() {
    // The whole point of A12: this moment used to read "idle", and idle
    // draws nothing at all. Jarvis has the utterance and is working on it.
    const voice = makeVoice();
    speech(voice, "idle");
    utterance(voice);
    compare(voice.state, "thinking");
    verify(voice.known);
    verify(!voice.idle);
  }

  function test_thinking_is_not_an_accent() {
    // §06 spends the accents on perceiving and speaking. Working is not
    // a third thing worth colouring; it is a word.
    const voice = makeVoice();
    utterance(voice);
    compare(voice.state, "thinking");
    verify(!voice.active, "thinking must not light the ember or the teal");
  }

  function test_ungated_speech_in_the_room_is_not_thinking() {
    // jv-ears' VAD runs continuously whether or not a wake window is open
    // (A4). Speech Jarvis was never addressed with must not put it to work
    // on screen.
    const voice = makeVoice();
    speech(voice, "idle");
    vad(voice, "speech_start");
    suite.fakeNow += 2;
    vad(voice, "speech_end");
    compare(voice.state, "idle", "nobody said its name");
  }

  function test_a_brain_request_means_thinking_with_no_voice_path_at_all() {
    // The non-voice frontends (jv ask, the replay harness) publish
    // brain.request instead, and jv-brain answers those the same way.
    const voice = makeVoice();
    ask(voice);
    compare(voice.state, "thinking");
  }

  function test_a_silent_request_still_ends_when_the_reply_lands() {
    // speak:false never reaches jv-voice, so the ONLY thing that can close
    // this window is brain.response. Without it the HUD would sit on a
    // claim about work that finished.
    const voice = makeVoice();
    ask(voice, {
      "speak": false
    });
    compare(voice.state, "thinking");
    suite.fakeNow += 1;
    reply(voice);
    compare(voice.state, "unknown", "jv-voice never spoke, so there is nothing else to say");
  }

  function test_the_first_spoken_word_ends_thinking() {
    const voice = makeVoice();
    speech(voice, "idle");
    utterance(voice);
    compare(voice.state, "thinking");
    suite.fakeNow += 1;
    speech(voice, "speaking");
    compare(voice.state, "speaking");
  }

  function test_the_gaps_between_a_streamed_reply_sentences_are_not_thinking() {
    // jv-brain speaks one speech.say per sentence, so jv-voice publishes
    // idle between them while the brain is still generating. Technically
    // still thinking; drawing it would flip the word once per sentence,
    // which is churn, not information. Hearing the answer begin is what
    // closes the window.
    const voice = makeVoice();
    speech(voice, "idle");
    utterance(voice);
    suite.fakeNow += 1;
    speech(voice, "speaking");
    suite.fakeNow += 1;
    speech(voice, "idle", {
      "reason": "completed"
    });
    compare(voice.state, "idle", "the answer already started; do not go back to thinking");
  }

  function test_an_error_reply_ends_thinking_even_though_nothing_was_said() {
    // finish_reason=error with empty text: the brain gave up and jv-voice
    // will never speak. The window has to close on the reply itself.
    const voice = makeVoice();
    speech(voice, "idle");
    utterance(voice);
    suite.fakeNow += 1;
    reply(voice, {
      "text": "",
      "finish_reason": "error"
    });
    compare(voice.state, "idle");
  }

  function test_a_reply_older_than_the_prompt_does_not_answer_it() {
    // The previous turn's reply says nothing about this turn.
    const voice = makeVoice();
    speech(voice, "idle");
    reply(voice);
    suite.fakeNow += 1;
    utterance(voice);
    compare(voice.state, "thinking");
  }

  function test_a_reply_we_cannot_read_does_not_close_the_window() {
    const voice = makeVoice();
    speech(voice, "idle");
    utterance(voice);
    suite.fakeNow += 1;
    reply(voice, {
      "finish_reason": 7
    });
    compare(voice.state, "thinking", "an unreadable reply is not a reply");
  }

  function test_jarvis_still_finishing_a_previous_reply_reads_as_speaking() {
    // Audible output is the more concrete claim, and it is what the user is
    // experiencing. A speaking frame OLDER than the prompt is not an answer
    // to it, so the window stays open underneath.
    const voice = makeVoice();
    speech(voice, "speaking");
    suite.fakeNow += 0.2;
    utterance(voice);
    compare(voice.state, "speaking");
    suite.fakeNow += 1;
    speech(voice, "idle", {
      "reason": "completed"
    });
    compare(voice.state, "thinking", "the prompt was never answered, so it is still open");
  }

  function test_an_answer_that_arrives_before_its_own_question_still_answers_it() {
    // Frames queue behind a slow consumer, so arrival order is not event
    // order: the speaking frame can land before the gated boundary that
    // opened the window it closes. By `ts` it is still the answer, and the
    // latch has to notice that on the prompt's edge as well as its own —
    // otherwise the idle that follows reads as "thinking" forever.
    const voice = makeVoice();
    speech(voice, "speaking");
    suite.fakeNow += 1;
    utteranceEndedAgo(voice, 1.5);
    compare(voice.state, "speaking");
    suite.fakeNow += 0.5;
    speech(voice, "idle", {
      "reason": "completed"
    });
    compare(voice.state, "idle", "it was answered; the arrival order does not change that");
  }

  function test_being_interrupted_outranks_thinking_and_then_gives_way() {
    // jv-voice always follows interrupted with idle, so this is a moment,
    // not a resting state — and the moment belongs to jv-voice.
    const voice = makeVoice();
    speech(voice, "speaking");
    suite.fakeNow += 0.2;
    utterance(voice);
    suite.fakeNow += 0.2;
    speech(voice, "interrupted");
    compare(voice.state, "interrupted");
    suite.fakeNow += 0.1;
    speech(voice, "idle");
    compare(voice.state, "thinking");
  }

  function test_a_wake_during_thinking_is_listening_again() {
    // Re-asking mid-answer: the microphone claim outranks everything, as
    // it does everywhere else in this file.
    const voice = makeVoice();
    speech(voice, "idle");
    utterance(voice);
    compare(voice.state, "thinking");
    suite.fakeNow += 0.5;
    wake(voice);
    compare(voice.state, "listening");
  }

  function test_a_state_word_we_cannot_read_still_reports_thinking() {
    // The brain working is a fact about the brain. jv-voice publishing
    // something we were not written against does not unmake it.
    const voice = makeVoice();
    utterance(voice);
    speech(voice, "humming");
    compare(voice.state, "thinking");
  }

  function test_a_dropped_link_forgets_that_jarvis_was_thinking() {
    const voice = makeVoice();
    utterance(voice);
    compare(voice.state, "thinking");
    voice.bus.ingest('{"t":"link","up":false,"err":"bridge stopped"}');
    compare(voice.state, "unknown");
  }

  function test_a_prompt_that_cannot_be_aged_is_never_thinking() {
    const voice = makeVoice({
      clock: false
    });
    speech(voice, "idle");
    utterance(voice);
    compare(voice.state, "idle", "an age we cannot compute is not an age of zero");
  }

  function test_a_prompt_that_arrives_already_stale_is_not_thinking() {
    // Frames queued behind a slow consumer arrive late. A question that
    // was asked and abandoned long ago is not work happening now.
    const voice = makeVoice({
      thinkS: 1
    });
    speech(voice, "idle");
    utteranceEndedAgo(voice, 20);
    compare(voice.state, "idle");
  }

  function test_thinking_expires_when_nothing_ever_answers() {
    // jv-brain dying mid-turn publishes nothing. A HUD that keeps saying
    // "thinking" is describing a process that may not exist.
    const voice = makeVoice({
      thinkS: 0.05
    });
    speech(voice, "idle");
    utterance(voice);
    compare(voice.state, "thinking");
    tryCompare(voice, "state", "idle", 3000, "a thinking window must close by itself");
  }

  function test_an_expired_window_stays_expired() {
    // The wall clock passing IS the evidence; re-deriving the age when the
    // timer fires would let a frozen clock un-expire the claim and re-arm
    // at the millisecond floor, which is a spin, not a HUD.
    const voice = makeVoice({
      thinkS: 0.05
    });
    speech(voice, "idle");
    utterance(voice);
    tryCompare(voice, "state", "idle", 3000);
    wait(120);
    compare(voice.state, "idle");
  }

  function test_a_prompt_delivered_late_gets_only_what_is_left_of_its_window() {
    // 0.45 s in flight means 0.45 s into its own window, not at the start
    // of one — same rule as the wake window, same reason.
    const voice = makeVoice({
      thinkS: 0.5
    });
    speech(voice, "idle");
    utteranceEndedAgo(voice, 0.45);
    compare(voice.state, "thinking");
    tryCompare(voice, "state", "idle", 250, "the window closes when it opened, not when we heard");
  }

  function test_shortening_the_thinking_window_closes_an_open_one() {
    const voice = makeVoice();
    speech(voice, "idle");
    utterance(voice);
    compare(voice.state, "thinking");
    voice.thinkWindowS = 0.05;
    tryCompare(voice, "state", "idle", 3000);
  }

  function test_the_next_turn_is_thinking_again() {
    // The ordinary case of two questions in a row: the answer that closed
    // the last window must not still be closing this one.
    const voice = makeVoice();
    speech(voice, "idle");
    utterance(voice);
    suite.fakeNow += 1;
    speech(voice, "speaking");
    suite.fakeNow += 1;
    speech(voice, "idle", {
      "reason": "completed"
    });
    suite.fakeNow += 1;
    reply(voice);
    compare(voice.state, "idle");
    suite.fakeNow += 1;
    utterance(voice);
    compare(voice.state, "thinking", "a new question has not been answered yet");
  }

  function test_a_second_prompt_reopens_a_window_that_had_closed() {
    const voice = makeVoice({
      thinkS: 0.05
    });
    speech(voice, "idle");
    utterance(voice);
    tryCompare(voice, "state", "idle", 3000);
    suite.fakeNow += 1;
    ask(voice);
    compare(voice.state, "thinking");
  }

  function test_the_newer_of_two_prompts_owns_the_window() {
    // A typed question during a spoken turn: the window must run from the
    // newer prompt, or the older one's timeout would close it early.
    const voice = makeVoice({
      thinkS: 1
    });
    speech(voice, "idle");
    utterance(voice);
    suite.fakeNow += 0.9;
    ask(voice);
    compare(voice.state, "thinking");
    wait(300);
    compare(voice.state, "thinking", "the older prompt's clock must not close the newer one");
  }

  function test_a_request_we_refuse_to_believe_is_not_a_prompt_data() {
    return [
      {
        tag: "empty text",
        body: {
          "text": ""
        },
        over: {}
      },
      {
        tag: "text is not a string",
        body: {
          "text": 3
        },
        over: {}
      },
      {
        tag: "no source",
        body: {
          "source": undefined
        },
        over: {}
      },
      {
        tag: "v2 body",
        body: {},
        over: {
          "v": 2
        }
      },
      {
        tag: "hedged conf",
        body: {},
        over: {
          "conf": 0.5
        }
      },
      {
        tag: "unorderable ts",
        body: {},
        over: {
          "ts": "soon"
        }
      }
    ];
  }

  function test_a_request_we_refuse_to_believe_is_not_a_prompt(data) {
    // brain.request is a command topic: conf is fixed at 1.0, and a body
    // that does not meet its own schema is not something to render from.
    const voice = makeVoice();
    speech(voice, "idle");
    ask(voice, data.body, data.over);
    compare(voice.state, "idle");
  }

  // --- the question the user gave up on (A17) -------------------------
  //
  // B6 made a wake cancel the answer in flight, and an interrupted turn
  // publishes NO brain.response — the frozen `finish_reason` enum has no
  // word for "the user stopped me". So the one thing that could close a
  // thinking window for a prompt nobody will ever answer stopped coming,
  // and the plate could claim work was in progress for the whole 30 s
  // floor. The rule that replaces it: a wake NEWER than the open prompt
  // means the user abandoned it.

  function test_a_wake_abandons_the_spoken_question_it_interrupts() {
    // Ask, then interrupt before a word comes back, then say nothing.
    // Once the microphone claim expires there is nothing left in flight,
    // and the plate must say so rather than keep claiming a busy brain.
    const voice = makeVoice({
      windowS: 0.05
    });
    speech(voice, "idle");
    utterance(voice);
    compare(voice.state, "thinking");
    suite.fakeNow += 0.5;
    wake(voice);
    tryCompare(voice, "state", "idle", 3000, "the brain was cancelled; nothing is thinking");
  }

  function test_a_wake_abandons_a_request_whose_answer_would_be_spoken() {
    // The same thing through the non-voice frontends. jv-brain speaks a
    // brain.request reply unless the request says otherwise, and a spoken
    // turn is exactly the turn a wake cancels.
    const voice = makeVoice({
      windowS: 0.05
    });
    speech(voice, "idle");
    ask(voice);
    compare(voice.state, "thinking");
    suite.fakeNow += 0.5;
    wake(voice);
    tryCompare(voice, "state", "idle", 3000, "a spoken reply is cancelled by a wake");
  }

  function test_a_wake_does_not_abandon_a_silent_request() {
    // jv-brain refuses to cancel a silent turn: a wake says the user is
    // talking to Jarvis, not that the CLI stopped wanting the answer it
    // asked for. That answer is still being written, and saying otherwise
    // would be the same lie in the other direction.
    const voice = makeVoice({
      windowS: 0.05
    });
    speech(voice, "idle");
    ask(voice, {
      "speak": false
    });
    suite.fakeNow += 0.5;
    wake(voice);
    tryCompare(voice, "state", "thinking", 3000, "nothing cancelled this one");
  }

  function test_the_wake_that_asked_the_question_does_not_abandon_it() {
    // The ordinary flow puts a wake BEFORE every spoken prompt. If the
    // comparison ran the wrong way round, voice would never think at all.
    const voice = makeVoice({
      windowS: 0.05,
      thinkS: 5
    });
    speech(voice, "idle");
    utterance(voice);
    compare(voice.state, "thinking");
    wait(200);
    compare(voice.state, "thinking", "the wake that opened this turn is not a barge-in");
  }

  function test_the_question_after_an_abandoned_one_is_thinking_again() {
    // Giving up on one question says nothing about the next.
    const voice = makeVoice({
      windowS: 0.05
    });
    speech(voice, "idle");
    ask(voice);
    suite.fakeNow += 0.5;
    wake(voice);
    tryCompare(voice, "state", "idle", 3000);
    suite.fakeNow += 1;
    ask(voice, {
      "text": "and the date"
    });
    compare(voice.state, "thinking");
  }

  function test_a_later_wake_we_cannot_read_does_not_bring_back_an_abandoned_question() {
    // Why this is a latch and not a comparison evaluated every frame:
    // `bus.latest()` holds one frame per topic, so the wake that ended the
    // window is replaced by the next detection — and a detection we refuse
    // to believe leaves nothing to compare against. Derived, the abandoned
    // question would come back to life for the rest of its 30 s.
    const voice = makeVoice({
      windowS: 0.05
    });
    speech(voice, "idle");
    ask(voice);
    suite.fakeNow += 0.5;
    wake(voice);
    tryCompare(voice, "state", "idle", 3000);
    suite.fakeNow += 1;
    wake(voice, {
      "score": 0.1
    });
    compare(voice.state, "idle", "an unreadable wake is not evidence that the brain resumed");
  }

  function test_a_wake_in_the_same_instant_as_the_question_abandons_it() {
    // Two frames stamped identically cannot be ordered, so this is a
    // tie-break, not a reading — and it is the same one the rest of this
    // file makes (`answered`, `utteranceEnded`, `repliedOnBus` all treat
    // "same instant" as "after"). Ending the window is also the
    // under-claiming direction: "thinking" is the assertion, so dropping
    // it says less, not more. Pinned so the comparison cannot drift.
    const voice = makeVoice({
      windowS: 0.05
    });
    speech(voice, "idle");
    ask(voice);
    wake(voice);
    tryCompare(voice, "state", "idle", 3000);
  }

  function test_a_wake_that_refutes_itself_abandons_nothing() {
    // The same bar the listening claim holds a wake to. A frame that
    // scored below the threshold it declares is not a detection, and must
    // not be allowed to throw away a question that is genuinely in flight.
    const voice = makeVoice();
    speech(voice, "idle");
    ask(voice);
    suite.fakeNow += 0.5;
    wake(voice, {
      "score": 0.1
    });
    compare(voice.state, "thinking");
  }

  function test_a_wake_that_stops_being_readable_reaches_through_nothing() {
    // The one path where the wake goes from a frame to NOTHING while a
    // question is still open and unabandoned — so it is the only place a
    // latch that forgot its null check would reach through it. A TypeError
    // in a signal handler is a warning, not a failure, so this test says
    // out loud that a warning is a failure: without that line the guard
    // could be deleted and every assertion here would still pass.
    failOnWarning(/TypeError/);
    const voice = makeVoice({
      windowS: 0.05
    });
    speech(voice, "idle");
    wake(voice);
    tryCompare(voice, "state", "idle", 3000);
    suite.fakeNow += 1;
    ask(voice);
    compare(voice.state, "thinking");
    suite.fakeNow += 0.5;
    wake(voice, {
      "score": 0.1
    });
    compare(voice.state, "thinking", "an unreadable wake neither abandons a question nor throws");
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
