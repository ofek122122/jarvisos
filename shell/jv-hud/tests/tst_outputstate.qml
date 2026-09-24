// OutputState — "Jarvis is talking and you cannot hear it", under test
// (PLAN A40).
//
// The HUD has said SPEAKING since A3 without ever knowing whether anything
// reached the room. This element joins that word to jv-context's view of
// the default sink, and the failures worth writing tests around are the
// ones that would make it worse than the empty corner it replaces:
//
//   · claiming silence on a stale snapshot. context.system is a 1 Hz
//     heartbeat of a mixer somebody is holding the controls of; a frame
//     from a jv-context that died five minutes ago is a claim about a
//     machine as it used to be, and this plate's whole value is that it
//     is about right now.
//   · nagging. A muted machine is a choice, not news, and a plate that is
//     up all day is one nobody reads at the moment it matters. It must be
//     on screen only while jv-voice is actually mid-utterance.
//   · getting stuck. Unlike every other latched element, both inputs here
//     are live — so the line has to leave the instant either one changes,
//     and a `speaking` frame nobody ever retracts must not pin it there
//     forever.
//   · inventing a threshold. "Too quiet to hear" is a guess about a room;
//     silence is a fact. Only muted and zero count.
//
// Headless, like the rest of core/: OutputState is pure QtQuick and reads
// the bus through core/BusModel, driven with the same JSON lines
// jv-hud-bridge writes.
import QtQuick
import QtTest
import "../core"

TestCase {
  id: suite
  name: "OutputState"

  // The stand-in for CLOCK_MONOTONIC. Every frame is delivered at its own
  // `ts` so it lands zero seconds old; winding this forward is how the
  // freshness windows are made to lapse without waiting for them.
  property real fakeNow: 0

  Component {
    id: busModel
    BusModel {}
  }

  Component {
    id: outputState
    OutputState {}
  }

  // createObject() is typed QObject, so every member read on the result
  // would be `missing-property` to qmllint. Going through an untyped
  // helper keeps the file lint-clean at -W 0 (see tst_speechstate).
  function spawn(component) {
    const o = component.createObject(suite);
    verify(o, "failed to instantiate a test object");
    return o;
  }

  // An OutputState on a live, subscribed link, with a clock we drive.
  // opts: { snapshotS, sayWindowS } for different windows,
  //       { down: true } to leave the link down,
  //       { bus: obj } to hand it something other than a BusModel,
  //       { health: false } to leave jv-voice silent about its device.
  //
  // The default is the ORDINARY machine: jv-voice heartbeating that it
  // took PortAudio's default output (A41), which is the only arrangement
  // in which the default sink jv-context reports is the one Jarvis speaks
  // into. Without that heartbeat this element says nothing at all, so
  // every test below that expects a line needs it.
  function makeOutput(opts) {
    const o = opts || {};
    suite.fakeNow = 0;
    const out = spawn(outputState);
    if (o.snapshotS !== undefined)
      out.snapshotS = o.snapshotS;
    if (o.sayWindowS !== undefined)
      out.sayWindowS = o.sayWindowS;
    out.bus = o.bus !== undefined ? o.bus : spawn(busModel);
    if (o.bus === undefined && o.down !== true) {
      out.bus.monotonic = () => suite.fakeNow;
      out.bus.ingest('{"t":"link","up":true}');
      if (o.health !== false)
        suite.health(out, {});
    }
    return out;
  }

  // --- building the frames the bridge would write ----------------------

  property int nextSeq: 0

  function envelope(topic, ts, conf, body, extra) {
    const e = extra || {};
    return {
      "topic": topic,
      "ts": ts,
      "seq": e.seq !== undefined ? e.seq : suite.nextSeq++,
      "src": e.src !== undefined ? e.src : "jv-context",
      "conf": conf,
      "v": e.v !== undefined ? e.v : 1,
      "body": body
    };
  }

  function deliver(out, env) {
    if (typeof env.ts === "number")
      suite.fakeNow = Math.max(suite.fakeNow, env.ts);
    out.bus.ingest(JSON.stringify({
      "t": "frame",
      "frame": env
    }));
  }

  // One jv-context snapshot. opts: { muted, volume, ts, conf, v, seq,
  // noTs, drop: [fields], set: {field: value} }.
  function snapshot(out, opts) {
    const o = opts || {};
    let body = {
      "net_online": true,
      "load1": 1.4,
      "mem_used_pct": 38.2,
      "audio_volume": o.volume !== undefined ? o.volume : 0.6,
      "audio_muted": o.muted !== undefined ? o.muted : false
    };
    if (o.drop !== undefined)
      for (let i = 0; i < o.drop.length; i++)
        delete body[o.drop[i]];
    if (o.set !== undefined)
      for (let k in o.set)
        body[k] = o.set[k];
    const env = suite.envelope("context.system", o.ts !== undefined ? o.ts : suite.fakeNow, o.conf !== undefined ? o.conf : 1, body, o);
    if (o.noTs === true)
      delete env.ts;
    deliver(out, env);
    return env;
  }

  // What jv-voice is doing. opts: { ts, conf, v, seq, drop }.
  function speech(out, state, opts) {
    const o = opts || {};
    let body = {
      "state": state,
      "utterance_id": "5ab8fecf-13d0-4f86-aa5d-0b2cc23b4d5d"
    };
    if (o.drop !== undefined)
      for (let i = 0; i < o.drop.length; i++)
        delete body[o.drop[i]];
    const env = suite.envelope("speech.state", o.ts !== undefined ? o.ts : suite.fakeNow, o.conf !== undefined ? o.conf : 1, body, {
      "src": "jv-voice",
      "seq": o.seq,
      "v": o.v
    });
    deliver(out, env);
    return env;
  }

  // jv-voice's heartbeat, and the one gauge this element reads out of it:
  // whether playback opened a device somebody pinned. opts: { pinned,
  // src, ts, conf, v, seq, metrics: false, set: {gauge: value} }.
  function health(out, opts) {
    const o = opts || {};
    let body = {
      "service": o.src !== undefined ? o.src : "jv-voice",
      "state": "ok",
      "uptime_s": 12.5,
      "period_s": 5
    };
    if (o.metrics !== false)
      body["metrics"] = {
        "output_device_pinned": o.pinned !== undefined ? o.pinned : 0
      };
    if (o.set !== undefined)
      body["metrics"] = o.set;
    const env = suite.envelope("sys.health", o.ts !== undefined ? o.ts : suite.fakeNow, o.conf !== undefined ? o.conf : 1, body, {
      "src": o.src !== undefined ? o.src : "jv-voice",
      "seq": o.seq,
      "v": o.v
    });
    deliver(out, env);
    return env;
  }

  // The whole situation this element exists for: the sink is muted and
  // Jarvis is answering into it.
  function mutedWhileSpeaking(out) {
    snapshot(out, {
      "muted": true
    });
    speech(out, "speaking");
  }

  // --- the thing itself -------------------------------------------------

  function test_nothing_is_shown_on_a_quiet_machine() {
    const out = makeOutput();
    compare(out.unheard, false, "an empty corner is what a machine nobody is talking to looks like");
    compare(out.reason, "");
  }

  function test_speaking_into_a_muted_sink_is_the_whole_point() {
    const out = makeOutput();
    mutedWhileSpeaking(out);
    compare(out.unheard, true);
    compare(out.reason, "muted");
  }

  function test_speaking_into_a_sink_at_zero_says_which_control_it_is() {
    // A slider at the bottom and a mute toggle are two different things
    // to go and fix, so they are two different words.
    const out = makeOutput();
    snapshot(out, {
      "volume": 0
    });
    speech(out, "speaking");
    compare(out.unheard, true);
    compare(out.reason, "zero");
  }

  function test_muted_outranks_zero_when_a_sink_is_both() {
    const out = makeOutput();
    snapshot(out, {
      "muted": true,
      "volume": 0
    });
    speech(out, "speaking");
    compare(out.reason, "muted", "mute is the toggle, and the one a user reaches for first");
  }

  function test_an_audible_sink_is_not_news() {
    const out = makeOutput();
    snapshot(out, {
      "volume": 0.6
    });
    speech(out, "speaking");
    compare(out.unheard, false);
    compare(out.reason, "");
  }

  function test_a_sink_turned_up_past_100_percent_is_audible() {
    // schemas/context.system.json: "1.0 = 100%, may exceed 1.0". A
    // comparison written the other way round would light the plate on a
    // machine somebody had turned UP.
    const out = makeOutput();
    snapshot(out, {
      "volume": 1.4
    });
    speech(out, "speaking");
    compare(out.unheard, false);
  }

  function test_a_very_quiet_sink_is_not_silence() {
    // No threshold on "too quiet to hear": that would be a guess about
    // your speakers and your room, and it would put a plate on screen for
    // a machine you deliberately turned down.
    const out = makeOutput();
    snapshot(out, {
      "volume": 0.03
    });
    speech(out, "speaking");
    compare(out.unheard, false, "the HUD invented a threshold for audibility");
  }

  // --- only while Jarvis is speaking ------------------------------------

  function test_a_muted_machine_nobody_is_talking_to_says_nothing() {
    // §06's earned emptiness. Muting your speakers is a choice, and a HUD
    // that nags about it all day is one nobody reads on the day it counts.
    const out = makeOutput();
    snapshot(out, {
      "muted": true
    });
    compare(out.unheard, false);
  }

  function test_an_idle_jv_voice_takes_the_line_off_the_screen() {
    const out = makeOutput();
    mutedWhileSpeaking(out);
    compare(out.unheard, true);
    speech(out, "idle");
    compare(out.unheard, false, "the sentence ended and the line stayed up");
    compare(out.reason, "");
  }

  function test_an_interrupted_reply_is_not_an_unheard_one() {
    // jv-voice publishes `interrupted` when the user barges in — which is
    // the user having already stopped whatever they could not hear.
    const out = makeOutput();
    snapshot(out, {
      "muted": true
    });
    speech(out, "interrupted");
    compare(out.unheard, false);
  }

  function test_a_state_this_hud_does_not_know_is_not_speaking() {
    // A later schema version may add states. The nearest thing we
    // recognise would be an invention, not a reading.
    const out = makeOutput();
    snapshot(out, {
      "muted": true
    });
    speech(out, "buffering");
    compare(out.unheard, false);
  }

  function test_unmuting_mid_sentence_clears_the_line_at_once() {
    // This element latches nothing: both inputs describe the present, so
    // the fix taking effect is the line leaving.
    const out = makeOutput();
    mutedWhileSpeaking(out);
    compare(out.unheard, true);
    suite.fakeNow = 1;
    snapshot(out, {
      "muted": false
    });
    compare(out.unheard, false);
  }

  function test_muting_mid_sentence_puts_the_line_up_at_once() {
    const out = makeOutput();
    snapshot(out);
    speech(out, "speaking");
    compare(out.unheard, false);
    suite.fakeNow = 1;
    snapshot(out, {
      "muted": true
    });
    compare(out.unheard, true, "the user muted mid-answer and the HUD did not notice");
  }

  // --- frames we will not read ------------------------------------------

  function test_a_snapshot_from_a_schema_we_do_not_know_is_not_read() {
    const out = makeOutput();
    speech(out, "speaking");
    snapshot(out, {
      "muted": true,
      "v": 2
    });
    compare(out.unheard, false, "a v2 body is not a v1 body (invariant 2)");
  }

  function test_a_hedged_snapshot_is_not_read() {
    // schemas/context.system.json fixes envelope conf at 1.0. A mixer
    // reading that hedges disagrees with itself.
    const out = makeOutput();
    speech(out, "speaking");
    snapshot(out, {
      "muted": true,
      "conf": 0.5
    });
    compare(out.unheard, false);
  }

  function test_a_snapshot_with_no_timestamp_is_not_read() {
    // Without a `ts` there is no age, and without an age there is no way
    // to stop believing it.
    const out = makeOutput();
    speech(out, "speaking");
    snapshot(out, {
      "muted": true,
      "noTs": true
    });
    compare(out.unheard, false);
  }

  function test_a_snapshot_missing_the_mute_field_is_not_read() {
    const out = makeOutput();
    speech(out, "speaking");
    snapshot(out, {
      "drop": ["audio_muted"]
    });
    compare(out.unheard, false, "a missing boolean read as falsy is a guess about the machine");
  }

  function test_a_mute_field_that_is_not_a_boolean_is_not_read() {
    // The claim is `=== true`, so a string would not light the plate even
    // if it got through the type check — which is exactly what makes that
    // check easy to delete without anything noticing. What it really buys
    // is that the frame is refused OUTRIGHT: an unreadable body is not
    // half a reading, so there is nothing to time either.
    const out = makeOutput();
    speech(out, "speaking");
    snapshot(out, {
      "set": {
        "audio_muted": "yes"
      }
    });
    compare(out.unheard, false);
    wait(0);
    compare(out.expiry.running, false, "the HUD armed a clock over a body it cannot read");
  }

  function test_a_snapshot_missing_the_volume_is_not_read() {
    // Even for a muted one: the pair is what the schema requires, and a
    // body missing a required field is a body from something we do not
    // understand.
    const out = makeOutput();
    speech(out, "speaking");
    snapshot(out, {
      "muted": true,
      "drop": ["audio_volume"]
    });
    compare(out.unheard, false);
  }

  function test_a_volume_that_is_not_a_number_is_not_read() {
    const out = makeOutput();
    speech(out, "speaking");
    snapshot(out, {
      "set": {
        "audio_volume": "0"
      }
    });
    compare(out.unheard, false);
  }

  function test_a_speech_frame_with_no_state_is_not_read() {
    const out = makeOutput();
    snapshot(out, {
      "muted": true
    });
    speech(out, "speaking", {
      "drop": ["state"]
    });
    compare(out.unheard, false);
  }

  function test_a_hedged_speech_frame_is_not_read() {
    const out = makeOutput();
    snapshot(out, {
      "muted": true
    });
    speech(out, "speaking", {
      "conf": 0.4
    });
    compare(out.unheard, false);
  }

  function test_an_unreadable_newer_snapshot_stops_the_claim() {
    // The newest frame is the only one this element has, and one it
    // cannot read is not evidence of a muted sink. Stopping is the
    // under-claiming direction, which is the one core/ always takes.
    const out = makeOutput();
    mutedWhileSpeaking(out);
    compare(out.unheard, true);
    suite.fakeNow = 1;
    snapshot(out, {
      "muted": true,
      "v": 7
    });
    compare(out.unheard, false);
  }

  // --- how long a frame describes the present ---------------------------

  function test_a_snapshot_older_than_its_window_is_no_longer_a_reading() {
    // jv-context died with the sink muted, and somebody has since unmuted
    // it. Three 1 Hz periods is as long as one snapshot speaks for.
    const out = makeOutput({
      "snapshotS": 3
    });
    mutedWhileSpeaking(out);
    compare(out.unheard, true);
    suite.fakeNow = 3.5;
    speech(out, "speaking"); // something else moves; the snapshot does not
    compare(out.unheard, false, "a four-second-old snapshot of a mixer is not a reading");
  }

  function test_a_fresh_snapshot_renews_the_claim() {
    const out = makeOutput({
      "snapshotS": 3
    });
    mutedWhileSpeaking(out);
    suite.fakeNow = 3.5;
    speech(out, "speaking");
    compare(out.unheard, false);
    snapshot(out, {
      "muted": true
    });
    compare(out.unheard, true, "jv-context came back and the HUD would not listen");
  }

  function test_a_speaking_frame_nobody_retracts_does_not_pin_the_line_forever() {
    // jv-voice died mid-sentence. Without this the plate would sit in the
    // corner of a muted machine until the next reboot — the one thing §06
    // will not have.
    const out = makeOutput({
      "sayWindowS": 30
    });
    speech(out, "speaking", {
      "ts": 0
    });
    suite.fakeNow = 40;
    snapshot(out, {
      "muted": true
    });
    compare(out.unheard, false, "a forty-second-old utterance is not one being played now");
  }

  function test_a_snapshot_that_spent_its_window_in_flight_arrives_stale() {
    // `ageOf` is what is LEFT of the window, not the whole of it.
    const out = makeOutput({
      "snapshotS": 3
    });
    speech(out, "speaking", {
      "ts": 0
    });
    suite.fakeNow = 10;
    snapshot(out, {
      "muted": true,
      "ts": 0
    });
    compare(out.unheard, false);
  }

  // --- the timer --------------------------------------------------------

  function test_the_earlier_of_the_two_deadlines_is_the_one_armed() {
    // One timer serves both windows: believing the pair is believing
    // both, so whichever lapses first is the one that matters.
    const out = makeOutput({
      "snapshotS": 3,
      "sayWindowS": 30
    });
    mutedWhileSpeaking(out);
    wait(0);
    compare(out.expiry.running, true, "nothing is timing the line");
    compare(out.expiry.interval, 3000, "the snapshot lapses first and the timer did not say so");
  }

  function test_the_timer_follows_the_utterance_when_that_is_the_nearer_end() {
    const out = makeOutput({
      "snapshotS": 30,
      "sayWindowS": 4
    });
    mutedWhileSpeaking(out);
    wait(0);
    compare(out.expiry.interval, 4000);
  }

  function test_the_timer_counts_what_is_left_of_a_frame_already_in_flight() {
    const out = makeOutput({
      "snapshotS": 10,
      "sayWindowS": 60
    });
    speech(out, "speaking", {
      "ts": 0
    });
    suite.fakeNow = 6;
    snapshot(out, {
      "muted": true,
      "ts": 2
    });
    wait(0);
    compare(out.expiry.interval, 6000, "the snapshot's own four seconds in flight were not counted");
  }

  function test_the_line_leaves_when_the_timer_fires() {
    // The only clock in this element, doing the only thing it is for:
    // making the HUD stop believing a frame when nothing new arrives.
    const out = makeOutput({
      "snapshotS": 0.05
    });
    mutedWhileSpeaking(out);
    compare(out.unheard, true);
    tryCompare(out, "unheard", false, 2000, "the HUD kept claiming a muted sink off a lapsed snapshot");
  }

  function test_no_timer_runs_while_there_is_nothing_to_time() {
    // §06: 0 fps when nothing is happening. This element is idle on every
    // ordinary machine, and an armed timer on an idle machine is a wakeup
    // per interval for nothing.
    const out = makeOutput();
    wait(0);
    compare(out.expiry.running, false);
    snapshot(out, {
      "muted": true
    });
    wait(0);
    compare(out.expiry.running, false, "one frame is not a pair, and half a reading times nothing");
    speech(out, "speaking");
    wait(0);
    compare(out.expiry.running, true);
  }

  // --- a bus the HUD cannot see -----------------------------------------

  function test_nothing_is_shown_while_the_link_is_down() {
    // A cached snapshot from a link that has since dropped describes a
    // mixer somebody may have unmuted since. LinkPlate says the HUD is
    // blind; this element does not guess underneath it.
    const out = makeOutput({
      "down": true
    });
    compare(out.unheard, false);
  }

  function test_a_dropped_link_takes_the_line_off_the_screen() {
    const out = makeOutput();
    mutedWhileSpeaking(out);
    compare(out.unheard, true);
    out.bus.ingest('{"t":"link","up":false,"err":"connect /run/jarvis/bus.sock: No such file or directory"}');
    compare(out.unheard, false);
  }

  function test_a_bus_still_handing_out_frames_on_a_dead_link_is_not_believed() {
    // core/BusModel throws its frames away when the link drops, so on the
    // real HUD the readers below would see nothing anyway. This pins the
    // guard rather than the consequence: the element refuses a cached
    // frame off a dead link on its own account, not because the model it
    // happens to be wired to was tidy. Both readers are pinned together —
    // deleting the guard from only one leaves the other one nulling the
    // pair, so there is no way to observe half of it.
    const frames = {
      "context.system": suite.envelope("context.system", 0, 1, {
        "net_online": true,
        "load1": 1.0,
        "mem_used_pct": 12,
        "audio_volume": 0.5,
        "audio_muted": true
      }),
      "speech.state": suite.envelope("speech.state", 0, 1, {
        "state": "speaking"
      }, {
        "src": "jv-voice"
      })
    };
    const beat = suite.envelope("sys.health", 0, 1, {
      "service": "jv-voice",
      "state": "ok",
      "uptime_s": 1,
      "period_s": 5,
      "metrics": {
        "output_device_pinned": 0
      }
    }, {
      "src": "jv-voice"
    });
    const out = makeOutput({
      "bus": {
        "linkUp": false,
        "latest": topic => frames[topic],
        "latestFrom": () => beat,
        "ageOf": () => 0
      }
    });
    compare(out.unheard, false, "the HUD read a mixer it had already lost sight of");
    // The third reader (A41) has to be pinned on its own account: `unheard`
    // is already false because the other two nulled the pair, so deleting
    // ITS guard changes nothing anyone can see from the outside. `ownSink`
    // is where it is observable.
    compare(out.ownSink, false, "the HUD read jv-voice's device off a link it had already lost");
  }

  function test_a_bus_that_offers_nothing_is_survived() {
    // Not a hypothetical: `Bus` forwards to a bridge that may not have
    // started yet. A TypeError here would take the whole shell down with
    // it, and the shell is the thing holding every other plate.
    failOnWarning(/TypeError/);
    const out = makeOutput({
      "bus": {
        "linkUp": true
      }
    });
    compare(out.unheard, false);
    compare(out.reason, "");
  }

  function test_no_bus_at_all_is_survived() {
    failOnWarning(/TypeError/);
    const out = makeOutput({
      "bus": null
    });
    compare(out.unheard, false);
  }

  // --- the sink this element is allowed to speak about (A41) ------------
  //
  // Everything above rests on one thing being true: that the default sink
  // jv-context reports is the device jv-voice plays into. It is true while
  // jv-voice calls `sd.play()` with no device argument and false the day
  // anybody pins one — and a HUD that is confidently wrong about why you
  // cannot hear Jarvis is worse than the empty corner it replaced. So the
  // assumption stopped being an assumption: jv-voice states it in its
  // heartbeat (`output_device_pinned`), and this element says nothing
  // until it has been told.

  function test_the_line_waits_until_jv_voice_has_said_how_it_opens_its_device() {
    // Not a hypothetical: the HUD can be started, or the link re-made,
    // between two five-second heartbeats. Quiet for those seconds is the
    // under-claiming direction, which is the one core/ always takes.
    const out = makeOutput({
      "health": false
    });
    mutedWhileSpeaking(out);
    compare(out.unheard, false, "the HUD claimed a sink it had not been told jv-voice uses");
    compare(out.reason, "");
  }

  function test_a_pinned_device_takes_the_line_off_the_screen() {
    // jv-voice was pointed at a device. The default sink is now somebody
    // else's business, and its mute switch says nothing about Jarvis.
    const out = makeOutput();
    health(out, {
      "pinned": 1
    });
    mutedWhileSpeaking(out);
    compare(out.unheard, false, "a true statement about the wrong sink is still wrong");
  }

  function test_pinning_mid_session_clears_a_line_already_up() {
    // A restarted jv-voice with a device in its config heartbeats within a
    // second of coming back, while the sentence it is now speaking is one
    // this HUD can still see.
    const out = makeOutput();
    mutedWhileSpeaking(out);
    compare(out.unheard, true);
    suite.fakeNow = 1;
    health(out, {
      "pinned": 1
    });
    compare(out.unheard, false);
  }

  function test_unpinning_puts_the_line_back() {
    const out = makeOutput({
      "health": false
    });
    health(out, {
      "pinned": 1
    });
    mutedWhileSpeaking(out);
    compare(out.unheard, false);
    suite.fakeNow = 1;
    health(out, {
      "pinned": 0
    });
    compare(out.unheard, true, "jv-voice went back to the default sink and the HUD would not follow");
  }

  function test_a_gauge_this_hud_cannot_read_is_not_a_promise() {
    // A heartbeat with no gauge is every jv-voice built before A41, and
    // every service that never had an opinion. Absent is unknown, and
    // unknown is not "took the default".
    const out = makeOutput({
      "health": false
    });
    health(out, {
      "metrics": false
    });
    mutedWhileSpeaking(out);
    compare(out.unheard, false);
  }

  function test_a_gauge_that_is_not_a_number_is_not_read() {
    const out = makeOutput({
      "health": false
    });
    health(out, {
      "set": {
        "output_device_pinned": "no"
      }
    });
    mutedWhileSpeaking(out);
    compare(out.unheard, false);
  }

  function test_a_gauge_value_this_hud_has_no_meaning_for_is_not_read() {
    // schemas/sys.health.json calls `metrics` free-form numbers, so 2 is a
    // legal frame. It is not a word this element knows, and the nearest
    // one would be an invention.
    const out = makeOutput({
      "health": false
    });
    health(out, {
      "pinned": 2
    });
    mutedWhileSpeaking(out);
    compare(out.unheard, false);
  }

  function test_the_gauge_is_read_from_jv_voice_and_not_from_whoever_spoke_last() {
    // `sys.health` has one publisher per service and they all share the
    // topic. Only the service that does the playing can answer this.
    const out = makeOutput();
    suite.fakeNow = 1;
    health(out, {
      "src": "jv-context",
      "pinned": 1
    });
    mutedWhileSpeaking(out);
    compare(out.unheard, true, "another service's gauge silenced the plate");
  }

  function test_a_hedged_heartbeat_is_not_read() {
    const out = makeOutput({
      "health": false
    });
    health(out, {
      "conf": 0.5
    });
    mutedWhileSpeaking(out);
    compare(out.unheard, false);
  }

  function test_a_heartbeat_from_a_schema_we_do_not_know_is_not_read() {
    const out = makeOutput({
      "health": false
    });
    health(out, {
      "v": 2
    });
    mutedWhileSpeaking(out);
    compare(out.unheard, false, "a v2 body is not a v1 body (invariant 2)");
  }

  function test_an_old_heartbeat_still_answers_for_the_device() {
    // The deliberate asymmetry: this gauge is jv-voice's CONFIGURATION,
    // not a reading of the world, and configuration does not go stale
    // sitting still — it changes when the process restarts, and a restart
    // heartbeats at once. Expiring it would put a second, shorter clock
    // on the plate and hand the dead-jv-voice case to the wrong one:
    // `sayWindowS` is the backstop built for that, and it is tested above.
    const out = makeOutput();
    suite.fakeNow = 600;
    mutedWhileSpeaking(out);
    compare(out.unheard, true, "a ten-minute-old fact about how jv-voice opens a device is still that fact");
  }

  function test_a_dropped_link_forgets_the_device_too() {
    // Everything this element reads goes through the same gate: a HUD
    // that cannot see the bus reports nothing, and reporting nothing is
    // not an all-clear.
    const out = makeOutput();
    mutedWhileSpeaking(out);
    compare(out.unheard, true);
    out.bus.ingest('{"t":"link","up":false}');
    compare(out.unheard, false);
  }
}
