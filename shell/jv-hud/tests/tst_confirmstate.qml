// ConfirmState — "is Jarvis waiting on a yes or no?", under test (PLAN A20).
//
// This one guards a different thing from the other elements. StatePlate and
// MicPlate are about not LYING; this is about not going dark at the one
// moment the machine is asking permission to do something irreversible.
// jv-act speaks the question and gives you a window (15 s today, and it
// says so in the frame); if you did not hear it, silence is the answer and
// the answer is no. So the failures worth writing tests around are:
//
//   · a live question that never reached the screen — the whole reason
//     this element exists.
//   · a question still on screen after it was answered — the user says
//     "yes" into a closed window and nothing happens.
//   · a question drawn from a bus the HUD can no longer see.
//
// The awkward part, and the reason this needs a latch rather than a
// binding: `bus.latest()` holds exactly one frame per topic, and the ANSWER
// arrives on the same topic as the request. The moment jv-act (or the jv
// CLI) answers, the request is gone from the bus — so a derived "is
// anything pending" would be blind to the question for its entire life
// except the instant it landed. What is remembered here is an observation
// the bus no longer carries, which is what a latch is for.
//
// Headless, like the rest of core/: ConfirmState is pure QtQuick and reads
// the bus through core/BusModel, driven with the same JSON lines the bridge
// writes.
import QtQuick
import QtTest
import "../core"

TestCase {
  id: suite
  name: "ConfirmState"

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
    id: confirmState
    ConfirmState {}
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
  //       { fallbackS: n } for a different ceiling on an undeclared window.
  function makeConfirm(opts) {
    const o = opts || {};
    suite.fakeNow = 0;
    const bus = spawn(busModel);
    if (o.clock !== false)
      bus.monotonic = () => suite.fakeNow;
    const confirm = spawn(confirmState);
    if (o.fallbackS !== undefined)
      confirm.windowFallbackS = o.fallbackS;
    confirm.bus = bus;
    if (o.down !== true)
      bus.ingest('{"t":"link","up":true}');
    return confirm;
  }

  // One frame on any topic, with the envelope the bridge would forward.
  function send(confirm, topic, src, body, env) {
    let e = {
      "topic": topic,
      "ts": suite.fakeNow + 100,
      "seq": suite.seq++,
      "src": src,
      "conf": 1.0,
      "v": 1,
      "body": body
    };
    for (const k in env || {})
      e[k] = env[k];
    confirm.bus.ingest(JSON.stringify({
      "t": "frame",
      "frame": e
    }));
  }

  // jv-act asking. `body` overrides the defaults; pass null for a field to
  // leave it out entirely, which is what an older jv-act would do (the
  // schema requires only `kind` and `request_id`).
  function ask(confirm, body, env) {
    let b = {
      "kind": "request",
      "request_id": "req-1",
      "tool": "trash.empty",
      "summary": "empty the trash — yes or no?",
      "window_s": 15.0
    };
    for (const k in body || {}) {
      if (body[k] === null)
        delete b[k];
      else
        b[k] = body[k];
    }
    send(confirm, "action.confirm", "jv-act", b, env);
  }

  // Whoever heard the user: jv-act itself from its scoped transcript
  // window, or the `jv confirm` CLI — which is why this element reads the
  // topic rather than one publisher on it.
  function reply(confirm, body, env, src) {
    let b = {
      "kind": "answer",
      "request_id": "req-1",
      "granted": true,
      "answered_by": "voice"
    };
    for (const k in body || {}) {
      if (body[k] === null)
        delete b[k];
      else
        b[k] = body[k];
    }
    send(confirm, "action.confirm", src || "jv-act", b, env);
  }

  // --- nothing known is never a question ------------------------------

  function test_without_a_bus_nothing_is_pending() {
    const confirm = spawn(confirmState);
    verify(!confirm.pending);
    compare(confirm.summary, "");
    compare(confirm.tool, "");
    compare(confirm.requestId, "");
  }

  function test_a_link_that_is_down_knows_nothing() {
    const confirm = makeConfirm({
      down: true
    });
    ask(confirm);
    verify(!confirm.pending);
  }

  function test_a_live_bus_with_no_confirm_shows_nothing() {
    verify(!makeConfirm().pending);
  }

  // --- the question itself --------------------------------------------

  function test_a_request_is_pending_and_says_what_it_says() {
    const confirm = makeConfirm();
    ask(confirm);
    verify(confirm.pending);
    compare(confirm.requestId, "req-1");
    compare(confirm.tool, "trash.empty");
    // Verbatim. jv-act wrote the question the user is HEARING; a HUD that
    // paraphrased it would be asking a second, different question.
    compare(confirm.summary, "empty the trash — yes or no?");
  }

  function test_a_request_without_words_is_still_a_question() {
    // `summary` and `tool` are optional in the schema. The fact that
    // something destructive is waiting on you is the signal; the words are
    // detail, and dropping the frame would take the signal with them.
    const confirm = makeConfirm();
    ask(confirm, {
      "summary": null,
      "tool": null
    });
    verify(confirm.pending);
    compare(confirm.summary, "");
    compare(confirm.tool, "");
  }

  function test_a_summary_that_is_not_a_string_is_not_words() {
    const confirm = makeConfirm();
    ask(confirm, {
      "summary": 7
    });
    verify(confirm.pending);
    compare(confirm.summary, "");
  }

  // --- the question ending --------------------------------------------

  function test_an_answer_ends_the_question() {
    const confirm = makeConfirm();
    ask(confirm);
    verify(confirm.pending);
    reply(confirm);
    verify(!confirm.pending, "it was answered; there is nothing to ask");
    compare(confirm.requestId, "");
  }

  function test_a_denial_ends_the_question_too() {
    const confirm = makeConfirm();
    ask(confirm);
    reply(confirm, {
      "granted": false,
      "answered_by": "voice"
    });
    verify(!confirm.pending);
  }

  function test_the_timeout_answer_ends_the_question() {
    // jv-act publishes an answer even when nobody spoke: window closed,
    // answered_by=timeout, denied. That frame is the end of the question
    // and the HUD must not outlive it waiting for its own clock.
    const confirm = makeConfirm();
    ask(confirm);
    reply(confirm, {
      "granted": false,
      "answered_by": "timeout"
    });
    verify(!confirm.pending);
  }

  function test_an_answer_from_the_cli_ends_it_as_well() {
    // `jv confirm` publishes the answer itself, so the frame that ends a
    // question does not always come from the service that asked it. This
    // element reads the TOPIC for that reason.
    const confirm = makeConfirm();
    ask(confirm);
    reply(confirm, {
      "answered_by": "cli"
    }, {}, "jv");
    verify(!confirm.pending);
  }

  function test_an_answer_to_a_different_request_leaves_this_one_open() {
    // Two questions cannot be outstanding at once today — jv-act reserves
    // a single slot — but the HUD is not the thing that enforces that, and
    // clearing on somebody else's answer would blank a live question.
    const confirm = makeConfirm();
    ask(confirm);
    reply(confirm, {
      "request_id": "req-other"
    });
    verify(confirm.pending);
    compare(confirm.requestId, "req-1");
  }

  function test_an_answer_with_no_request_id_ends_nothing() {
    const confirm = makeConfirm();
    ask(confirm);
    reply(confirm, {
      "request_id": null
    });
    verify(confirm.pending);
  }

  function test_a_second_request_replaces_the_first() {
    const confirm = makeConfirm();
    ask(confirm);
    ask(confirm, {
      "request_id": "req-2",
      "tool": "file.delete",
      "summary": "delete the file — yes or no?"
    });
    verify(confirm.pending);
    compare(confirm.requestId, "req-2", "the newest question is the live one");
    compare(confirm.tool, "file.delete");
  }

  function test_an_answer_to_the_replaced_question_does_not_close_the_live_one() {
    const confirm = makeConfirm();
    ask(confirm);
    ask(confirm, {
      "request_id": "req-2"
    });
    reply(confirm, {
      "request_id": "req-1"
    });
    verify(confirm.pending);
    compare(confirm.requestId, "req-2");
  }

  // --- a bus we cannot see -------------------------------------------

  function test_losing_the_link_forgets_the_question() {
    // A question latched from a bus that has since died describes a
    // machine we can no longer see — and the window may well have closed
    // while we were not looking.
    const confirm = makeConfirm();
    ask(confirm);
    verify(confirm.pending);
    confirm.bus.ingest('{"t":"link","up":false,"err":"bridge died"}');
    verify(!confirm.pending);
  }

  function test_a_link_that_comes_back_does_not_resurrect_the_question() {
    const confirm = makeConfirm();
    ask(confirm);
    confirm.bus.ingest('{"t":"link","up":false,"err":"bridge died"}');
    confirm.bus.ingest('{"t":"link","up":true}');
    verify(!confirm.pending, "nothing on the bus says that question is still open");
  }

  // --- frames that disagree with themselves ---------------------------

  function test_a_body_from_a_schema_version_we_do_not_know_is_refused() {
    const confirm = makeConfirm();
    ask(confirm, {}, {
      "v": 2
    });
    verify(!confirm.pending);
  }

  function test_a_hedged_confidence_is_refused() {
    // schemas/action.confirm.json: envelope conf = 1.0. A confirmation
    // handshake that is only 60% sure of itself is not one.
    const confirm = makeConfirm();
    ask(confirm, {}, {
      "conf": 0.6
    });
    verify(!confirm.pending);
  }

  function test_a_frame_with_no_orderable_ts_is_refused() {
    // Without a `ts` there is no age, and without an age there is no
    // window — the question would sit on screen forever.
    const confirm = makeConfirm();
    ask(confirm, {}, {
      "ts": "soon"
    });
    verify(!confirm.pending);
  }

  function test_a_request_with_no_request_id_is_refused() {
    // The id is how the answer will find it. One without an id is a
    // question that can never be closed.
    const confirm = makeConfirm();
    ask(confirm, {
      "request_id": null
    });
    verify(!confirm.pending);
  }

  function test_a_kind_we_do_not_recognise_neither_asks_nor_answers() {
    const confirm = makeConfirm();
    ask(confirm);
    ask(confirm, {
      "kind": "cancelled"
    });
    verify(confirm.pending, "a word we do not know is not an answer");
    compare(confirm.requestId, "req-1");
  }

  function test_a_frame_we_cannot_read_does_not_close_a_live_question() {
    // The B5 rule, and here it is the difference between a question the
    // user can read and a blank corner: refusing to UNDERSTAND a frame is
    // never the same as being told the question is over.
    const confirm = makeConfirm();
    ask(confirm);
    ask(confirm, {}, {
      "v": 2
    });
    verify(confirm.pending);
    compare(confirm.requestId, "req-1");
  }

  function test_another_topic_says_nothing_about_a_confirmation() {
    const confirm = makeConfirm();
    ask(confirm);
    send(confirm, "speech.state", "jv-voice", {
      "state": "speaking"
    });
    verify(confirm.pending);
  }

  // --- the window ------------------------------------------------------

  function test_the_window_is_the_one_jv_act_declared() {
    // A14's rule: the service that enforces a budget states it, and the
    // HUD reads it rather than remembering a copy. jv-act puts its own
    // confirm window in every request.
    const confirm = makeConfirm();
    ask(confirm, {
      "window_s": 12.0
    });
    compare(confirm.windowS, 12.0);
  }

  function test_a_request_that_declares_no_window_gets_the_huds_own_ceiling() {
    const confirm = makeConfirm({
      fallbackS: 30.0
    });
    ask(confirm, {
      "window_s": null
    });
    verify(confirm.pending);
    compare(confirm.windowS, 30.0);
  }

  function test_a_window_that_is_not_a_positive_number_gets_the_ceiling_too() {
    const confirm = makeConfirm({
      fallbackS: 30.0
    });
    ask(confirm, {
      "window_s": -4
    });
    compare(confirm.windowS, 30.0);
  }

  function test_the_question_closes_when_its_window_runs_out() {
    // jv-act may have died mid-window, and then the answer frame that
    // normally ends this never comes. The HUD lets go on its own or it
    // asks forever.
    const confirm = makeConfirm();
    ask(confirm, {
      "window_s": 0.05
    });
    verify(confirm.pending);
    tryCompare(confirm, "pending", false, 3000, "a confirm window must close by itself");
  }

  function test_when_the_window_closes_the_words_go_with_it() {
    // The question is latched and the latch outlives the window — it has
    // to, or a second request could not tell whether it replaced one. So
    // everything READABLE has to be gated on the question still being
    // open, not on the latch still being held: words that outlive their
    // window are a question the user can still read and can no longer
    // answer. (Found by mutation; the plate's own visibility hid it.)
    const confirm = makeConfirm();
    ask(confirm, {
      "window_s": 0.05
    });
    tryCompare(confirm, "pending", false, 3000);
    compare(confirm.summary, "", "an expired question has nothing left to say");
    compare(confirm.tool, "");
    compare(confirm.requestId, "");
  }

  function test_a_request_delivered_late_gets_only_what_is_left_of_its_window() {
    // A frame that spent 0.45 s in flight is 0.45 s into its own window.
    // Arming the whole window on arrival would keep asking after jv-act
    // had already timed out and denied it.
    //
    // The clock has to be pinned by a PROMPT frame first: BusModel learns
    // the offset from the frames it sees, so a late frame arriving first
    // would teach it a late clock and then read as zero seconds old.
    const confirm = makeConfirm();
    send(confirm, "speech.state", "jv-voice", {
      "state": "idle"
    });
    ask(confirm, {
      "window_s": 0.5
    }, {
      "ts": suite.fakeNow + 100 - 0.45
    });
    verify(confirm.pending);
    tryCompare(confirm, "pending", false, 250, "the window closes when it opened, not when we heard");
  }

  function test_a_request_older_than_its_own_window_was_never_open() {
    const confirm = makeConfirm();
    // Pin the clock with a fresh frame first, then send one from the past.
    send(confirm, "speech.state", "jv-voice", {
      "state": "idle"
    });
    ask(confirm, {
      "window_s": 1.0
    }, {
      "ts": suite.fakeNow + 100 - 5
    });
    verify(!confirm.pending);
  }

  function test_a_second_question_reopens_after_one_expired() {
    const confirm = makeConfirm();
    ask(confirm, {
      "window_s": 0.05
    });
    tryCompare(confirm, "pending", false, 3000);
    suite.fakeNow += 1;
    ask(confirm, {
      "request_id": "req-2",
      "window_s": 15.0
    });
    verify(confirm.pending);
    compare(confirm.requestId, "req-2");
  }

  function test_with_no_clock_there_is_no_window_and_so_no_question() {
    // The house rule, and it points the same way here as everywhere else:
    // an age we cannot compute is not an age of zero. A HUD that cannot
    // tell time cannot tell when the window shuts, and a question that
    // never expires is the one failure worse than a missed one.
    const confirm = makeConfirm({
      clock: false
    });
    ask(confirm);
    verify(!confirm.pending);
  }
}
