// The HUD, driven by perception's real output (PLAN B9).
//
// Every other test in this directory hands the bus frames someone typed —
// which means the input and the expectation have the same author, and a
// misunderstanding about what jv-ears actually publishes would be written
// into both. `harness/fixtures/sessions/` fixed the supply side (B3): four
// recordings of what jv-ears REALLY published while listening to the
// fixture WAVs, with real openWakeWord, real Silero VAD and real
// faster-whisper behind them. This file is the HUD reading them.
//
// What that buys, concretely:
//
//   · the state trajectory is asserted against real seconds. "listening
//     starts at 1.44 s and ends at 3.76 s" is a fact about the recording,
//     not a number chosen to make a test pass.
//   · the mid-sentence pause (hey-jarvis-pause) is 1.2 s of real silence
//     inside one utterance. Nothing hand-written would have caught a HUD
//     that flickered there; this does, because the flicker would show up
//     as extra transitions.
//   · speech-no-wake is a real room with real speech and no wake word. If
//     the HUD ever claims the microphone is open for us there, invariant
//     10 is broken and a recording — not an argument — says so.
//   · the wake frames carry the detector's real `score` and `conf`, so
//     SpeechState's "a frame that disagrees with itself is not a
//     detection" bar is checked against numbers openWakeWord produced.
//
// The replay is what jv-hud-bridge does: one envelope per line, in order,
// wrapped as `{"t":"frame","frame":...}`. Two honest differences from a
// live HUD, both in the safe direction:
//
//   · the bridge forwards a whitelist, and as of A26 `audio.transcript` is
//     on it — so these recordings are now replayed in FULL, exactly as the
//     HUD would see them. What used to be asserted about the bridge is
//     therefore asserted about the elements instead: the transcripts reach
//     `HeardState` and move nothing else, `SpeechState` least of all.
//   · `ts` here is the pipeline's sample clock (zero at the first sample of
//     the WAV), so the replay drives the injected monotonic clock to each
//     frame's own `ts`: every frame lands zero seconds old, as it would on
//     a machine keeping up. Ageing is then real — winding past the end is
//     how the windows time out — but jv-ears' own wall-clock delays are not
//     reproduced, because a sample clock does not record them.
import QtQuick
import QtTest
import "../core"

TestCase {
  id: suite
  name: "SessionReplay"

  // The committed recordings, compiled into QML by tools/gen_sessions_qml.py
  // (a QML engine cannot read a file out of the repo). The jv-hud build runs
  // that generator with --check, so these lines are the ones on disk.
  Sessions {
    id: recordings
  }

  // The stand-in for CLOCK_MONOTONIC, driven to each frame's `ts`.
  property real fakeNow: 0

  Component {
    id: busModel
    BusModel {}
  }

  Component {
    id: speechState
    SpeechState {}
  }

  Component {
    id: heardState
    HeardState {}
  }

  // Same reason as tst_speechstate.qml: the linter reads `createObject` as
  // returning a bare QObject, so instantiation goes through an untyped
  // function and it stops guessing.
  function spawn(component) {
    const o = component.createObject(suite);
    verify(o, "failed to instantiate a test object");
    return o;
  }

  function makeVoice() {
    suite.fakeNow = 0;
    const bus = spawn(busModel);
    bus.monotonic = () => suite.fakeNow;
    const voice = spawn(speechState);
    voice.bus = bus;
    bus.ingest('{"t":"link","up":true}');
    return voice;
  }

  // The same, for the element that renders the words (A26). It shares no
  // helper with `makeVoice` on purpose: these tests are about what reaches
  // the plate, not about what the two elements agree on.
  function makeHeard() {
    suite.fakeNow = 0;
    const bus = spawn(busModel);
    bus.monotonic = () => suite.fakeNow;
    const heard = spawn(heardState);
    heard.bus = bus;
    bus.ingest('{"t":"link","up":true}');
    return heard;
  }

  // Replay every frame of `name` into whichever element `holder` wraps.
  function replay(holder, name) {
    const frames = envelopes(name);
    for (let i = 0; i < frames.length; i++)
      deliver(holder, frames[i]);
  }

  // The one final transcript in a recording, or null. jv-ears publishes
  // exactly one per utterance and these recordings hold one utterance.
  function finalOn(name) {
    const frames = envelopes(name);
    for (let i = 0; i < frames.length; i++)
      if (frames[i].topic === "audio.transcript" && frames[i].body.kind === "final")
        return frames[i];
    return null;
  }

  // --- reading a recording --------------------------------------------

  function recording(name) {
    const rec = recordings.byName[name];
    verify(rec, "no recording named " + name);
    return rec;
  }

  function envelopes(name) {
    const lines = recording(name).frames;
    let out = [];
    for (let i = 0; i < lines.length; i++)
      out.push(JSON.parse(lines[i]));
    return out;
  }

  // One frame onto the bus, at its own moment in the recording.
  function deliver(voice, env) {
    suite.fakeNow = Math.max(suite.fakeNow, env.ts);
    voice.bus.ingest(JSON.stringify({
      "t": "frame",
      "frame": env
    }));
  }

  // Replay `name` and return the state trajectory as one readable string:
  // the state before anything arrived, then every CHANGE with the `ts` of
  // the frame that caused it. A flicker cannot hide in this — it is an
  // extra transition — and a failure message reads like the recording.
  //
  // opts: { skipTopics: [...] } to leave a topic out of the replay,
  //       { upto: n } to stop after n frames.
  function trajectory(voice, name, opts) {
    const o = opts || {};
    const frames = envelopes(name);
    let out = [voice.state];
    let last = voice.state;
    for (let i = 0; i < frames.length; i++) {
      if (o.upto !== undefined && i >= o.upto)
        break;
      if (o.skipTopics !== undefined && o.skipTopics.indexOf(frames[i].topic) >= 0)
        continue;
      deliver(voice, frames[i]);
      if (voice.state !== last) {
        last = voice.state;
        out.push(last + "@" + frames[i].ts.toFixed(2));
      }
    }
    return out.join(" -> ");
  }

  // The first frame on `topic`, or null. Used to state a fact about the
  // recording in the test that depends on it.
  function firstOn(name, topic, event) {
    const frames = envelopes(name);
    for (let i = 0; i < frames.length; i++)
      if (frames[i].topic === topic && (event === undefined || frames[i].body.event === event))
        return frames[i];
    return null;
  }

  // --- the recordings are actually here -------------------------------

  function test_every_committed_recording_is_compiled_in() {
    // Without this, a generator that emitted an empty object would leave
    // every test below asserting nothing at all, in green.
    compare(recordings.names.length, 4, "four recordings are committed (B3)");
    for (let i = 0; i < recordings.names.length; i++) {
      const name = recordings.names[i];
      const rec = recording(name);
      verify(rec.frames.length > 0, name + " has no frames");
      const header = JSON.parse(rec.header);
      // The trajectories below quote sample-clock seconds. A live-bus
      // recording's `ts` would be some boot's CLOCK_MONOTONIC and every
      // number in this file would be meaningless.
      compare(header.boot_id, "sample-clock", name + " is not a sample-clock session");
    }
  }

  // --- the voice path, as recorded ------------------------------------

  function test_a_real_wake_walks_the_hud_from_unknown_to_listening_to_thinking() {
    // hey-jarvis-clean: "Hey Jarvis, what time is it?" in a quiet room.
    // The VAD opens at 0.80 s and the HUD says NOTHING — speech in the room
    // is not speech to Jarvis. The wake lands at 1.44 s, and the utterance
    // closes at 3.76 s, where ears disarms and transcribes: from there the
    // question is in flight and the HUD owes the user "thinking".
    const voice = makeVoice();
    compare(trajectory(voice, "hey-jarvis-clean"), "unknown -> listening@1.44 -> thinking@3.76");
    compare(voice.state, "thinking");
    verify(!voice.active, "thinking is work we infer, not the ember");
  }

  function test_the_same_question_over_a_music_bed_reads_the_same() {
    // hey-jarvis-music is the same shape with music behind it: the wake
    // scores 0.963 instead of 0.990 and every transcript confidence drops,
    // which must change the timing and nothing else. A HUD that treated a
    // noisier room as a quieter claim would show up right here.
    const voice = makeVoice();
    compare(trajectory(voice, "hey-jarvis-music"), "unknown -> listening@1.44 -> thinking@4.16");
  }

  function test_a_pause_mid_sentence_does_not_break_the_listening_window() {
    // hey-jarvis-pause holds 1.2 s of real silence inside one sentence —
    // the fixture exists because that pause must not split the utterance.
    // Downstream of that, the HUD must not blink either: one entry into
    // "listening" at the wake, one exit at the real boundary 5.28 s later,
    // and nothing in between. Every flicker would be two more transitions.
    const voice = makeVoice();
    compare(trajectory(voice, "hey-jarvis-pause"), "unknown -> listening@1.36 -> thinking@6.64");
  }

  function test_the_longest_recorded_utterance_still_fits_the_wake_window() {
    // The one real coupling between jv-ears' tuning and the HUD's biggest
    // claim. `wakeWindowS` is ears' own `wake_timeout_s` (A14): if it were
    // ever set below the longest thing a person actually says, the HUD
    // would drop "listening" mid-sentence while ears was still recording.
    // The recordings are the only evidence available about how long that
    // is, so they are what this is checked against — 5.28 s of real speech
    // against an 8 s window today.
    const voice = makeVoice();
    let longest = 0;
    for (let i = 0; i < recordings.names.length; i++) {
      const name = recordings.names[i];
      const wake = firstOn(name, "audio.wake");
      const ended = firstOn(name, "audio.vad", "speech_end");
      if (wake === null || ended === null)
        continue;
      longest = Math.max(longest, ended.ts - wake.ts);
    }
    verify(longest > 0, "no recording has a wake followed by a boundary");
    verify(longest < voice.wakeWindowS,
           "the longest recorded utterance (" + longest.toFixed(2) +
           " s) does not fit in the wake window (" + voice.wakeWindowS +
           " s): the HUD would stop saying listening while ears still is");
  }

  function test_the_recorded_wakes_meet_the_huds_own_trust_bar() {
    // SpeechState refuses a detection whose envelope `conf` contradicts the
    // `score` in its body (invariant 4: a frame that disagrees with itself
    // is handled, not rendered). These are the numbers openWakeWord really
    // produced, so this is the check that the bar is set where real
    // detections pass it rather than somewhere only test data does.
    let wakes = 0;
    for (let i = 0; i < recordings.names.length; i++) {
      const name = recordings.names[i];
      const wake = firstOn(name, "audio.wake");
      if (wake === null)
        continue;
      const voice = makeVoice();
      deliver(voice, wake);
      verify(voice.wake !== null, name + "'s real wake frame was not believed");
      compare(voice.state, "listening", name + "'s real wake did not open a window");
      wakes += 1;
    }
    compare(wakes, 3, "three of the four recordings contain a wake word");
  }

  // --- the room talking is not the user talking to Jarvis ---------------

  function test_speech_with_no_wake_never_claims_the_microphone() {
    // speech-no-wake is a real utterance nobody addressed to Jarvis: ears'
    // VAD runs continuously (A4), so it opens and closes a segment and
    // transcribes nothing. The HUD must stay dark through all of it — not
    // "listening" (a lie about the microphone) and not "thinking" (a lie
    // about the brain, since no question was ever asked).
    const voice = makeVoice();
    compare(trajectory(voice, "speech-no-wake"), "unknown");
    verify(!voice.listening);
    verify(!voice.known, "unknown draws nothing, which is the truth here");
    compare(voice.prompt, null, "a segment ears never gated is not a question");
  }

  // --- the two differences from a live HUD, made explicit --------------

  function test_the_transcripts_move_nothing_but_the_plate_that_reads_them() {
    // The bridge forwards audio.transcript as of A26, so SpeechState now
    // sees frames it has no business acting on. What it says must be
    // decided by the wake and the VAD boundary and nothing else — a state
    // machine that started taking its cue from the ASR would answer a
    // slower question and claim the microphone for longer.
    const withText = makeVoice();
    const full = trajectory(withText, "hey-jarvis-clean");
    const withoutText = makeVoice();
    const bridged = trajectory(withoutText, "hey-jarvis-clean", {
      skipTopics: ["audio.transcript"]
    });
    compare(bridged, full, "the transcripts moved the speech state, which they must not");
  }

  // --- the words, as jv-ears really transcribed them (A26) --------------

  function test_a_real_question_reaches_the_plate_verbatim() {
    // The whole point of the plate: after the utterance closes, the user
    // can read what Jarvis took down. Asserted against the recording's own
    // body rather than a sentence typed here, so this stays true if the
    // fixtures are ever re-recorded and says something if the element
    // starts editing them.
    const heard = makeHeard();
    replay(heard, "hey-jarvis-clean");
    const final = finalOn("hey-jarvis-clean");
    verify(final !== null, "the recording has no final transcript");
    compare(heard.heard, true, "a real question left the plate empty");
    compare(heard.text, final.body.text);
    compare(heard.lang, "en");
    compare(heard.foreignLang, false);
    compare(heard.utteranceId, final.body.utterance_id);
    verify(heard.text.length > 0);
  }

  function test_the_partials_that_precede_it_are_never_what_is_shown() {
    // hey-jarvis-pause rewrites itself seven times before it settles —
    // "Hey Jarvis remind me to", then "Hey Jarvis, remind me too.", then
    // back again. Every one of those was on the bus, and none of them is
    // what Jarvis acted on.
    const heard = makeHeard();
    const frames = envelopes("hey-jarvis-pause");
    let partials = 0;
    for (let i = 0; i < frames.length; i++) {
      deliver(heard, frames[i]);
      if (frames[i].topic === "audio.transcript" && frames[i].body.kind === "partial") {
        partials += 1;
        compare(heard.heard, false, "a provisional sentence reached the plate");
      }
    }
    verify(partials >= 7, "the recording no longer rewrites itself, so this proves nothing");
    compare(heard.text, finalOn("hey-jarvis-pause").body.text);
  }

  function test_speech_nobody_addressed_to_jarvis_never_reaches_the_plate() {
    // This is the recording that makes showing transcripts at all a
    // defensible thing to do. speech-no-wake is a real utterance in a real
    // room with no wake word: ears' VAD opens and closes a segment and no
    // ASR ever runs, so there is nothing to put on a screen. If jv-ears
    // ever transcribes ungated speech, this plate becomes a live
    // transcript of the room — and this test is what says so first.
    const heard = makeHeard();
    replay(heard, "speech-no-wake");
    compare(heard.heard, false);
    compare(heard.text, "");
    const frames = envelopes("speech-no-wake");
    let transcripts = 0;
    for (let i = 0; i < frames.length; i++)
      if (frames[i].topic === "audio.transcript")
        transcripts += 1;
    compare(transcripts, 0, "ears transcribed an utterance nobody addressed to it");
  }

  function test_every_real_transcript_clears_the_plate_however_noisy_the_room() {
    // HeardState deliberately has no confidence bar, and these are the
    // numbers that decided it. The three recorded finals carry 0.886 (a
    // quiet room), 0.863 (a mid-sentence pause) and 0.739 (a music bed) —
    // and all three transcribe their sentence correctly. So a bar anywhere
    // in that spread would mark a word-perfect transcript as doubtful, and
    // one below it would never fire: exp(avg_logprob) is measuring the
    // room, not whether the words are right. A doubt marker that fires on
    // correct transcripts is one the user learns to ignore, which is
    // LinkPlate's cry-wolf failure with better manners.
    //
    // Add a bar above the quietest of these and this test fails, which is
    // the point: the decision should cost an argument with real data.
    let lowest = 1;
    let highest = 0;
    let shown = 0;
    for (let i = 0; i < recordings.names.length; i++) {
      const name = recordings.names[i];
      const final = finalOn(name);
      if (final === null)
        continue;
      lowest = Math.min(lowest, final.conf);
      highest = Math.max(highest, final.conf);
      const heard = makeHeard();
      deliver(heard, final);
      verify(heard.heard, name + "'s real transcript was refused by the HUD");
      compare(heard.text, final.body.text);
      shown += 1;
    }
    compare(shown, 3, "three of the four recordings contain a transcript");
    verify(highest - lowest > 0.1,
           "the recorded confidences (" + lowest.toFixed(3) + "-" + highest.toFixed(3) +
           ") no longer spread far enough to say anything about a bar");
    verify(lowest < 0.8, "the noisy room no longer scores low, so this proves nothing");
  }

  function test_the_words_leave_when_the_link_does() {
    const heard = makeHeard();
    replay(heard, "hey-jarvis-clean");
    compare(heard.heard, true);
    heard.bus.ingest('{"t":"link","up":false,"err":"bridge stopped"}');
    compare(heard.heard, false, "a sentence from a bus we can no longer see");
  }

  function test_the_thinking_window_closes_when_the_brain_never_answers() {
    // These recordings are jv-ears alone: nothing ever publishes the
    // brain.response that would end the window. Past `thinkWindowS` the HUD
    // no longer knows whether anyone is still working, so it must stop
    // saying so — the direction this element always errs in.
    const voice = makeVoice();
    trajectory(voice, "hey-jarvis-clean");
    compare(voice.state, "thinking");
    suite.fakeNow += voice.thinkWindowS + 1;
    compare(voice.state, "unknown", "an unanswered question cannot stay 'thinking' forever");
  }

  function test_the_link_dropping_mid_utterance_forgets_the_open_window() {
    // Replay only as far as the real wake, then lose the bridge. A HUD that
    // kept drawing "listening" from a bus it can no longer see would be
    // making a claim about a microphone it is not watching.
    const voice = makeVoice();
    compare(trajectory(voice, "hey-jarvis-clean", {
      upto: 2
    }), "unknown -> listening@1.44");
    voice.bus.ingest('{"t":"link","up":false,"err":"bridge stopped"}');
    compare(voice.state, "unknown");
    voice.bus.ingest('{"t":"link","up":true}');
    compare(voice.state, "unknown", "the link came back; the recording did not");
  }

  // --- the bus bookkeeping, on real traffic ----------------------------

  function test_the_recording_arrives_as_frames_from_one_real_publisher() {
    // BusModel's roster is "who has spoken" (A6), and on a real perception
    // recording that is exactly one service. Checked here because every
    // other test of it uses a hand-written `src`.
    const voice = makeVoice();
    trajectory(voice, "hey-jarvis-clean");
    compare(voice.bus.received, recording("hey-jarvis-clean").frames.length);
    compare(voice.bus.publishersOf("audio.wake"), ["jv-ears"]);
    compare(voice.bus.publishersOf("audio.vad"), ["jv-ears"]);
    compare(voice.bus.publishersOf("speech.state"), [], "jv-voice is not in these recordings");
  }
}
