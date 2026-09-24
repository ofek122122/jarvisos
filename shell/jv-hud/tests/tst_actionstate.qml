// ActionState — "Jarvis changed your machine, and it did not work", under
// test (PLAN A37).
//
// This is the first element that reads jv-act's own outcomes, and the
// failures worth writing tests around are the ones that would make it
// worse than the empty corner it replaces:
//
//   · labelling a failure with a tool it cannot prove it belongs to.
//     `action.result` carries a request_id and NOT a tool name, so the
//     name has to come from the `intent.action` that asked for it — and
//     a HUD that names the wrong tool has told you a lie about what
//     touched your machine, which is worse than saying nothing.
//   · reporting a success. Every action that worked would put a plate on
//     screen for no reason, and a corner that is busy all day is one
//     nobody reads on the day it matters (the HealthPlate argument).
//   · answering A22's open question by accident. `denied` and
//     `confirm_timeout` are how a CONFIRMATION ended, and how a
//     confirmation ends on screen is a human's call, not this element's.
//   · keeping the line up forever, or dropping it because a frame was odd
//     in some way that has nothing to do with the outcome.
//
// Headless, like the rest of core/: ActionState is pure QtQuick and reads
// the bus through core/BusModel, driven with the same JSON lines
// jv-hud-bridge writes.
import QtQuick
import QtTest
import "../core"

TestCase {
  id: suite
  name: "ActionState"

  // The stand-in for CLOCK_MONOTONIC. Every frame is delivered at its own
  // `ts` so it lands zero seconds old; winding this forward is how the
  // backstop is made to fire without waiting for it.
  property real fakeNow: 0

  Component {
    id: busModel
    BusModel {}
  }

  Component {
    id: actionState
    ActionState {}
  }

  // createObject() is typed QObject, so every member read on the result
  // would be `missing-property` to qmllint. Going through an untyped
  // helper keeps the file lint-clean at -W 0 (see tst_speechstate).
  function spawn(component) {
    const o = component.createObject(suite);
    verify(o, "failed to instantiate a test object");
    return o;
  }

  // An ActionState on a live, subscribed link, with a clock we drive.
  // opts: { holdS: n } for a different backstop,
  //       { down: true } to leave the link down,
  //       { bus: obj } to hand it something other than a BusModel.
  function makeAction(opts) {
    const o = opts || {};
    suite.fakeNow = 0;
    const act = spawn(actionState);
    if (o.holdS !== undefined)
      act.holdS = o.holdS;
    act.bus = o.bus !== undefined ? o.bus : spawn(busModel);
    if (o.bus === undefined && o.down !== true) {
      act.bus.monotonic = () => suite.fakeNow;
      act.bus.ingest('{"t":"link","up":true}');
    }
    return act;
  }

  // --- building the frames the bridge would write ----------------------

  property int nextSeq: 0

  function envelope(topic, ts, conf, body, extra) {
    const e = extra || {};
    return {
      "topic": topic,
      "ts": ts,
      "seq": e.seq !== undefined ? e.seq : suite.nextSeq++,
      "src": e.src !== undefined ? e.src : "jv-act",
      "conf": conf,
      "v": e.v !== undefined ? e.v : 1,
      "body": body
    };
  }

  function deliver(act, env) {
    if (typeof env.ts === "number")
      suite.fakeNow = Math.max(suite.fakeNow, env.ts);
    act.bus.ingest(JSON.stringify({
      "t": "frame",
      "frame": env
    }));
  }

  // The brain asking jv-act to run a tool. opts: { ts, conf, v, seq,
  // capability, drop: [fields] }.
  function intent(act, requestId, tool, opts) {
    const o = opts || {};
    let body = {
      "request_id": requestId,
      "tool": tool,
      "args": {
        "name": "firefox"
      },
      "capability": o.capability !== undefined ? o.capability : "benign"
    };
    if (o.drop !== undefined)
      for (let i = 0; i < o.drop.length; i++)
        delete body[o.drop[i]];
    const env = suite.envelope("intent.action", o.ts !== undefined ? o.ts : suite.fakeNow, o.conf !== undefined ? o.conf : 1, body, {
      "src": o.src !== undefined ? o.src : "jv-brain",
      "seq": o.seq,
      "v": o.v
    });
    deliver(act, env);
    return env;
  }

  // jv-act saying how it went. opts: { error, ok, ts, conf, v, seq,
  // output, noTs, drop: [fields] }.
  function result(act, requestId, opts) {
    const o = opts || {};
    let body = {
      "request_id": requestId,
      "ok": o.ok !== undefined ? o.ok : false,
      "duration_ms": 12
    };
    if (o.error !== undefined)
      body.error = o.error;
    if (o.output !== undefined)
      body.output = o.output;
    if (o.drop !== undefined)
      for (let i = 0; i < o.drop.length; i++)
        delete body[o.drop[i]];
    const env = suite.envelope("action.result", o.ts !== undefined ? o.ts : suite.fakeNow, o.conf !== undefined ? o.conf : 1, body, o);
    if (o.noTs === true)
      delete env.ts;
    deliver(act, env);
    return env;
  }

  function speech(act, state, ts) {
    deliver(act, suite.envelope("speech.state", ts !== undefined ? ts : suite.fakeNow, 1, {
      "state": state
    }, {
      "src": "jv-voice"
    }));
  }

  // A whole failed action: the brain asks, jv-act refuses or breaks.
  function failedAction(act, tool, error) {
    intent(act, "req-1", tool);
    result(act, "req-1", {
      "error": error
    });
  }

  // --- the ordinary failure --------------------------------------------

  function test_nothing_is_shown_before_jarvis_has_touched_anything() {
    const act = makeAction();
    compare(act.failed, false, "an empty corner is what a machine nobody has acted on looks like");
    compare(act.tool, "");
    compare(act.reason, "");
  }

  function test_a_failed_action_names_the_tool_and_the_schemas_own_reason() {
    const act = makeAction();
    failedAction(act, "app.launch", "execution_failed");
    compare(act.failed, true);
    compare(act.tool, "app.launch", "the tool comes from the intent this result answers");
    compare(act.reason, "execution_failed", "the schema's word, not a friendlier paraphrase");
  }

  function test_an_action_that_worked_is_not_news() {
    // §06's earned emptiness. The machine visibly doing the thing is the
    // report that it was done; a plate per success is a corner that is
    // busy all day and unread on the day it matters.
    const act = makeAction();
    intent(act, "req-1", "app.launch");
    result(act, "req-1", {
      "ok": true,
      "output": "Firefox launched"
    });
    compare(act.failed, false);
    compare(act.tool, "");
  }

  function test_a_later_success_takes_an_earlier_failure_off_the_screen() {
    // The brain retries with another tool and it works. Holding the first
    // failure under a newer success would report a machine that is not
    // the one in front of you.
    const act = makeAction();
    failedAction(act, "app.launch", "execution_failed");
    compare(act.failed, true);
    intent(act, "req-2", "app.focus");
    result(act, "req-2", {
      "ok": true
    });
    compare(act.failed, false, "a newer outcome is newer news");
  }

  function test_the_newest_failure_replaces_the_one_before_it() {
    const act = makeAction();
    failedAction(act, "app.launch", "execution_failed");
    failedAction2(act, "files.move", "invalid_args");
    compare(act.failed, true);
    compare(act.tool, "files.move");
    compare(act.reason, "invalid_args");
  }

  // The second failure of a turn, with its own request id.
  function failedAction2(act, tool, error) {
    intent(act, "req-2", tool);
    result(act, "req-2", {
      "error": error
    });
  }

  // --- never name a tool we cannot prove -------------------------------

  function test_a_result_with_no_matching_intent_is_reported_without_a_tool() {
    // The HUD may have missed the intent frame entirely — it subscribed
    // late, or the bridge dropped frames as a slow consumer (the gaps show
    // up as jumps in `seq`). The failure is still real and still worth
    // saying; the tool name is not, so it is not said.
    const act = makeAction();
    result(act, "req-1", {
      "error": "execution_failed"
    });
    compare(act.failed, true, "a failure the HUD cannot name is still a failure");
    compare(act.tool, "", "a tool name nobody can prove is a lie about what touched your machine");
    compare(act.reason, "execution_failed");
  }

  function test_an_intent_for_a_different_request_never_lends_its_name() {
    // `bus.latest()` holds ONE frame per topic, so the intent sitting
    // there may belong to a completely different request — and a tool name
    // taken on faith is the one mistake this element cannot make.
    const act = makeAction();
    intent(act, "req-OTHER", "system.shutdown");
    result(act, "req-1", {
      "error": "execution_failed"
    });
    compare(act.failed, true);
    compare(act.tool, "", "the name belonged to another request");
  }

  function test_an_intent_arriving_after_the_failure_does_not_rename_it() {
    // The pair is latched together at the moment the failure is accepted.
    // A later intent on the same topic is the NEXT thing Jarvis is trying,
    // and binding the displayed name to `latest()` would relabel a failure
    // that has not changed.
    const act = makeAction();
    failedAction(act, "app.launch", "execution_failed");
    intent(act, "req-2", "system.shutdown");
    compare(act.failed, true);
    compare(act.tool, "app.launch", "the line was relabelled with a tool that has not failed");
  }

  function test_an_intent_with_no_tool_name_is_not_a_name() {
    const act = makeAction();
    intent(act, "req-1", "", {
      "drop": ["tool"]
    });
    result(act, "req-1", {
      "error": "execution_failed"
    });
    compare(act.failed, true);
    compare(act.tool, "");
  }

  // --- the confirmation flow is not ours to report (A22) ---------------

  function test_a_denied_action_says_nothing() {
    // You answered no. You know. And `denied`/`confirm_timeout` are how a
    // CONFIRMATION ended — A22 reserves that question for a human, and
    // this element must not answer it as a side effect.
    const act = makeAction();
    failedAction(act, "files.delete", "denied");
    compare(act.failed, false);
  }

  function test_a_confirmation_that_timed_out_says_nothing_here() {
    const act = makeAction();
    failedAction(act, "files.delete", "confirm_timeout");
    compare(act.failed, false, "how a confirmation ends on screen is A22's open question");
  }

  function test_a_confirmation_outcome_does_not_take_an_older_failure_down() {
    // It is not news this element reports, so it is not news this element
    // acts on either: a denial landing after a real failure must not clear
    // the line the user has not read yet.
    const act = makeAction();
    failedAction(act, "app.launch", "execution_failed");
    failedAction2(act, "files.delete", "denied");
    compare(act.failed, true);
    compare(act.tool, "app.launch");
  }

  // --- reasons ---------------------------------------------------------

  function test_a_failure_with_no_reason_is_still_reported() {
    // `error` is required by the schema only when ok=false, and a jv-act
    // that omitted it has still told us the action did not happen. The
    // failure is the news; the reason is the detail.
    const act = makeAction();
    intent(act, "req-1", "app.launch");
    result(act, "req-1", {});
    compare(act.failed, true);
    compare(act.tool, "app.launch");
    compare(act.reason, "");
  }

  function test_a_reason_the_schema_does_not_define_is_not_put_on_screen() {
    // HealthState's rule, for the same reason: a word invented by a
    // publisher is not a word the reader can look up. The failure still
    // shows; the unknown word does not.
    const act = makeAction();
    intent(act, "req-1", "app.launch");
    result(act, "req-1", {
      "error": "kaboom"
    });
    compare(act.failed, true);
    compare(act.reason, "", "a reason nobody can look up is not a reason");
  }

  function test_every_reason_the_schema_defines_reaches_the_screen() {
    // The five that are not the confirmation flow's own outcomes.
    const reasons = ["unknown_tool", "invalid_args", "capability_mismatch", "execution_failed", "timeout"];
    for (let i = 0; i < reasons.length; i++) {
      const act = makeAction();
      failedAction(act, "app.launch", reasons[i]);
      compare(act.failed, true, reasons[i] + " never reached the screen");
      compare(act.reason, reasons[i]);
    }
  }

  // --- the exit --------------------------------------------------------

  function test_the_line_leaves_when_jarvis_starts_explaining() {
    // The ordinary exit, and the reason this plate needs no display timer:
    // jv-brain is handed every action.result and phrases it, so once you
    // can hear the explanation, the explanation is the better report.
    const act = makeAction();
    failedAction(act, "app.launch", "execution_failed");
    compare(act.failed, true);
    speech(act, "speaking");
    compare(act.failed, false);
    compare(act.tool, "", "the tool goes with the plate");
    compare(act.reason, "");
  }

  function test_the_answer_starting_is_remembered_after_jarvis_falls_silent() {
    // `bus.latest()` keeps one frame per topic, so the `speaking` frame is
    // GONE the moment jv-voice publishes the idle that follows it.
    // Derived rather than latched, the line would come back on screen for
    // the rest of the reply.
    const act = makeAction();
    failedAction(act, "app.launch", "execution_failed");
    speech(act, "speaking");
    speech(act, "idle");
    compare(act.failed, false, "an explained failure came back from the dead");
  }

  function test_speech_from_before_the_failure_is_not_an_explanation_of_it() {
    // Jarvis narrates ("let me try that") and THEN calls the tool, so
    // there is very often a `speaking` frame already sitting on the topic
    // when the failure lands. It is about the sentence before the attempt.
    const act = makeAction();
    speech(act, "speaking", 1);
    suite.fakeNow = 2;
    failedAction(act, "app.launch", "execution_failed");
    compare(act.failed, true, "the plate was silenced by a sentence spoken before the tool ran");
  }

  function test_an_interrupted_reply_also_ends_the_line() {
    // jv-voice only ever publishes `interrupted` out of `speaking`, so one
    // stamped after the failure means the explanation began and was cut
    // off by the user. It began either way.
    const act = makeAction();
    failedAction(act, "app.launch", "execution_failed");
    speech(act, "interrupted");
    compare(act.failed, false);
  }

  function test_jarvis_going_quiet_is_not_jarvis_explaining() {
    // `idle` landing between the failure and the first spoken word — an
    // errored say, a turn that produced no sentences — is not an answer,
    // and the failure has still not been reported to anyone.
    const act = makeAction();
    failedAction(act, "app.launch", "execution_failed");
    speech(act, "idle");
    compare(act.failed, true);
  }

  function test_a_new_failure_stops_being_explained_by_the_old_answer() {
    const act = makeAction();
    failedAction(act, "app.launch", "execution_failed");
    speech(act, "speaking");
    compare(act.failed, false);
    suite.fakeNow = 10;
    failedAction2(act, "files.move", "timeout");
    compare(act.failed, true, "a second failure was hidden by the answer to the first");
    compare(act.tool, "files.move");
  }

  // --- the backstop ----------------------------------------------------

  function test_a_failure_nobody_ever_explains_leaves_on_its_own() {
    // The brain died between the tool and the sentence, or the action came
    // from `jv` with nothing to speak. Without this the line would sit in
    // the corner until the next reboot.
    const act = makeAction({
      "holdS": 30
    });
    failedAction(act, "app.launch", "execution_failed");
    compare(act.failed, true);
    wait(0);
    compare(act.hold.running, true, "nothing is timing the line");
    compare(act.hold.interval, 30000, "the whole window, for a frame that arrived fresh");
  }

  function test_a_failure_that_spent_its_window_in_flight_arrives_expired() {
    // `ageOf` is what is LEFT of the window, not the whole of it. A frame
    // that took longer than the hold to reach the HUD is news about a turn
    // that is already over.
    const act = makeAction({
      "holdS": 5
    });
    intent(act, "req-1", "app.launch", {
      "ts": 0
    });
    suite.fakeNow = 20;
    result(act, "req-1", {
      "error": "execution_failed",
      "ts": 0
    });
    compare(act.failed, false, "a line older than its own window went on screen");
  }

  function test_the_backstop_is_rearmed_by_each_new_failure() {
    const act = makeAction({
      "holdS": 8
    });
    failedAction(act, "app.launch", "execution_failed");
    suite.fakeNow = 4;
    failedAction2(act, "files.move", "timeout");
    wait(0);
    compare(act.hold.interval, 8000, "the second failure inherited what was left of the first one's window");
  }

  function test_no_timer_runs_while_there_is_nothing_to_show() {
    // §06: 0 fps when nothing is happening. Actions are rare and failures
    // rarer, so this element is idle almost always — and an armed timer on
    // an idle machine is a wakeup per interval for nothing.
    const act = makeAction();
    wait(0);
    compare(act.hold.running, false);
    failedAction(act, "app.launch", "execution_failed");
    wait(0);
    compare(act.hold.running, true);
    speech(act, "speaking");
    wait(0);
    compare(act.hold.running, false, "the timer outlived the line it was timing");
  }

  // --- a bus the HUD cannot see ----------------------------------------

  function test_nothing_is_shown_while_the_link_is_down() {
    const act = makeAction({
      "down": true
    });
    compare(act.failed, false);
  }

  function test_the_link_dropping_forgets_the_failure() {
    // Every element in this HUD drops what it cached on a dropped link: a
    // line latched off a bus we can no longer see describes a machine we
    // can no longer see (invariant 10).
    const act = makeAction();
    failedAction(act, "app.launch", "execution_failed");
    compare(act.failed, true);
    act.bus.ingest('{"t":"link","up":false,"err":"connect: No such file or directory"}');
    compare(act.failed, false);
  }

  function test_a_bus_that_is_not_a_bus_is_simply_quiet() {
    // Bus.qml forwards a handful of functions; a stand-in that forwards
    // none must make this element quiet rather than make it throw inside a
    // binding, where the symptom is a warning nobody reads.
    const act = makeAction({
      "bus": {
        "linkUp": true
      }
    });
    compare(act.failed, false);
    compare(act.tool, "");
  }

  // --- frames we refuse to read ----------------------------------------

  function test_a_result_from_a_newer_schema_is_refused() {
    // Invariant 2: a v2 body is not a v1 body, and guessing at one is how
    // a HUD reports fields that have moved.
    const act = makeAction();
    intent(act, "req-1", "app.launch");
    result(act, "req-1", {
      "error": "execution_failed",
      "v": 2
    });
    compare(act.failed, false);
  }

  function test_a_hedged_result_is_refused() {
    // schemas/action.result.json fixes conf at 1.0: jv-act either did the
    // thing or it did not, and a result that is unsure of itself is not
    // one (invariant 4).
    const act = makeAction();
    intent(act, "req-1", "app.launch");
    result(act, "req-1", {
      "error": "execution_failed",
      "conf": 0.6
    });
    compare(act.failed, false);
  }

  function test_a_result_with_no_timestamp_is_refused() {
    // Without a `ts` there is no age, so there is no backstop — and a line
    // the HUD cannot time is one it would hold forever.
    const act = makeAction();
    intent(act, "req-1", "app.launch");
    result(act, "req-1", {
      "error": "execution_failed",
      "noTs": true
    });
    compare(act.failed, false);
  }

  function test_a_result_with_no_request_id_is_refused() {
    // The id is the only thread between an intent and its outcome. One
    // without it could never be attributed to anything.
    const act = makeAction();
    intent(act, "req-1", "app.launch");
    result(act, "req-1", {
      "error": "execution_failed",
      "drop": ["request_id"]
    });
    compare(act.failed, false);
  }

  function test_a_result_that_does_not_say_whether_it_worked_is_refused() {
    // `ok` is required and boolean. A missing one read as falsy would
    // report every unreadable frame as a failed action.
    const act = makeAction();
    intent(act, "req-1", "app.launch");
    result(act, "req-1", {
      "error": "execution_failed",
      "drop": ["ok"]
    });
    compare(act.failed, false);
  }

  function test_refusing_a_frame_is_not_the_same_as_being_answered() {
    // A held line survives frames this element cannot read. Refusal is the
    // absence of news, never news of a success.
    const act = makeAction();
    failedAction(act, "app.launch", "execution_failed");
    result(act, "req-2", {
      "ok": true,
      "v": 2
    });
    compare(act.failed, true, "an unreadable frame took a real failure off the screen");
    compare(act.tool, "app.launch");
  }

  function test_an_unreadable_speech_frame_does_not_end_the_line() {
    const act = makeAction();
    failedAction(act, "app.launch", "execution_failed");
    deliver(act, suite.envelope("speech.state", suite.fakeNow, 1, {
      "state": 7
    }, {
      "src": "jv-voice"
    }));
    compare(act.failed, true);
  }
}
