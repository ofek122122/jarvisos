// The corner, over a whole real turn — which plates the HUD puts up, in
// what order, at which second (PLAN A54).
//
// Everything that has ever checked this stack checked ONE SETTLED INSTANT.
// The contact sheet next door photographs ten of them and, since A53,
// asserts which plates each picture is of; the headless suites in
// shell/jv-hud/tests drive one state element at a time and assert what it
// decided. Between those two there is a gap exactly the shape of the bug
// this corner can actually have: a plate that arrives one frame too late,
// leaves one frame too early, blinks in the middle of an utterance, or
// appears in the wrong ORDER relative to the plate it is supposed to
// qualify. None of those is a state — every one of them is a SEQUENCE, and
// a still picture of the settled end of a turn cannot see any of them.
//
// So this file replays the committed recordings (B3 — what jv-ears really
// published, with real openWakeWord, real Silero VAD and real
// faster-whisper behind it) through the REAL plates, and asserts the
// corner's whole trajectory: every change to `litNames` with the `ts` of
// the frame that caused it. `trajectory()` in
// shell/jv-hud/tests/tst_sessionreplay.qml does exactly this for one state
// machine's word; this does it for what the user sees.
//
// WHY MOTION IS OFF HERE. A plate's `lit` is `opacity > 0`, and its
// opacity crosses zero through `Ease` — so with motion allowed, "when did
// this plate arrive" is a question about a 140 ms fade running on the
// render thread, and the answer would depend on how long the test happened
// to block. `Motion.policy.envOverride = "1"` is the reduced-motion path
// the real HUD honours (JV_HUD_REDUCED_MOTION=1, parsed in
// core/MotionPolicy.qml), and under it `Ease` is disabled outright and
// every opacity is ASSIGNED: a plate is on screen in the same frame the
// bus gave it something to say, and gone in the same frame that stopped
// being true. That is the sequence this file is about. The fades
// themselves are watched standing still by the shots (A43/A48/A49), which
// is where a duration can be looked at rather than raced.
//
// Honest about what it is NOT: not the compositor, not a live machine, and
// not a claim about the SECONDS between plates on ares — the recordings'
// `ts` is a sample clock (zero at the first sample of the WAV), so the
// numbers below are positions in the recording, not wall-clock latency.
// jv-ears' own processing delays are not in them. Latency of the last hop
// is B15's open question and needs a real bus.
import QtQuick
import QtTest
import ".."

Item {
  id: root

  // The real surface box, so the plates lay out as they do on screen. This
  // file never grabs an image — the layout matters only so that a plate
  // that is too wide for the surface would still be too wide here.
  width: 300
  height: 688

  // The same corner shell.qml composes, in the same order: one file, two
  // harnesses (tools/tests/test_hudshots.py pins it to shell.qml).
  Corner {
    id: stack

    anchors.top: parent.top
    anchors.right: parent.right
    anchors.topMargin: Theme.insetPx
    anchors.rightMargin: Theme.insetPx
  }

  // The recordings, compiled to QML by tools/gen_sessions_qml.py.
  Sessions {
    id: recordings
  }

  TestCase {
    id: suite

    name: "HudSequence"

    // How a corner with nothing in it reads in a trajectory. On a real
    // machine this is not an empty plate but an unmapped surface — the
    // desktop, with no HUD on it at all (§06's earned emptiness).
    readonly property string dark: "(dark)"

    // Every plate the shell can put up, as the plates name themselves.
    // Anything outside this set is a plate that invented a name, which is
    // the one way `litNames` could lie without any test noticing.
    readonly property var everyPlate: ["link", "confirm", "state", "output", "heard", "action", "guard", "install", "mic", "health"]

    function initTestCase() {
      // See the header: the trajectories below are about frames, not fades.
      Motion.policy.envOverride = "1";
    }

    function cleanupTestCase() {
      // The singleton is the engine's, and the sheet next door renders its
      // fades for real. Leaving motion switched off here would be this
      // file quietly changing what that one photographs.
      Motion.policy.envOverride = "";
    }

    // A HUD that has never seen anything, then a live link: the state
    // every recording starts from.
    //
    // The link goes up BEFORE the corner is checked, and that order is not
    // cosmetic. `Bus.reset()` hands the plates a model that has never been
    // connected, and the plates are not rebuilt between tests — so a
    // LinkState that already sat through an outage in an earlier test (the
    // last one here does exactly that) is entitled to call this HUD blind
    // the moment it sees another one. That is correct behaviour and it
    // would make "the corner starts dark" a claim about test ordering. A
    // live link is what these recordings were made on.
    function init() {
      Bus.reset();
      verify(!Motion.animate,
             "motion is on, so this file would be timing fades rather than frames");
      compare(Motion.suppressedBy, "reduced-motion");
      Bus.ingest('{"t":"link","up":true}');
      compare(suite.names(), "", "a HUD that has seen nothing has something on screen");
    }

    // The declared policy, back on every plate, after every test.
    //
    // One test below shortens two windows to watch them close, and the
    // plates are not rebuilt between tests — so restoring them at the end
    // of that function meant a `compare` in the middle of it restored
    // nothing, and four later tests then ran against a HUD with a 200 ms
    // memory and failed for a reason that was not theirs. A `cleanup()`
    // runs whether or not the test got there. (The sheet next door
    // photographs these same plates, which is the other half of why this
    // cannot be left to a happy path.)
    function cleanup() {
      const voice = suite.plateNamed("state");
      const words = suite.plateNamed("heard");
      if (voice)
        voice.voice.thinkWindowS = 30.0;
      if (words)
        words.heard.holdS = 30.0;
    }

    // The plate that calls itself `name`, or null. By its own name (A53)
    // rather than by its position in the stack, so this survives the next
    // plate being inserted above it.
    function plateNamed(name) {
      const kids = stack.children;
      for (let i = 0; i < kids.length; i++)
        if (kids[i].plateName === name)
          return kids[i];
      return null;
    }

    // What is on screen, in reading order, in the plates' own words (A53).
    function names() {
      return stack.litNames.join(" ");
    }

    // Replay `name` and return the corner's whole trajectory: what was on
    // screen before anything arrived, then every CHANGE with the `ts` of
    // the frame that caused it. A plate that blinks shows up as two extra
    // entries, one that arrives late shows up as a later `ts`, and one that
    // arrives out of order shows up as a different line — the reading order
    // is the stack's, not this file's.
    function corner(name) {
      const rec = recordings.byName[name];
      verify(rec, "no recording named " + name);
      let out = [suite.dark];
      let last = "";
      for (let i = 0; i < rec.frames.length; i++) {
        const env = JSON.parse(rec.frames[i]);
        Bus.deliver(env);
        const now = suite.names();
        if (now !== last) {
          last = now;
          out.push((now === "" ? suite.dark : now) + "@" + env.ts.toFixed(2));
        }
      }
      return out.join(" -> ");
    }

    // --- the corner this file is actually driving -------------------------

    function test_the_stack_under_test_is_the_whole_corner() {
      // Without this the file could be asserting a two-plate trajectory
      // over a stack that only has two plates in it, and the claim "and
      // nothing else lit" below would be empty. Corner.qml is pinned to
      // shell.qml by tools/tests/test_hudshots.py; this is the count
      // reaching the engine.
      compare(stack.children.length, suite.everyPlate.length,
              "the corner does not hold every plate the shell stacks");
    }

    function test_a_plate_arrives_in_the_same_frame_the_bus_speaks() {
      // The assumption every trajectory here rests on, made a test: with
      // motion suppressed there is no fade to wait for, so one frame in is
      // one plate up — synchronously, with no `wait()` anywhere. If this
      // ever fails, every sequence below silently becomes a measurement of
      // how long this process blocked rather than of what the HUD did.
      const rec = recordings.byName["hey-jarvis-clean"];
      Bus.deliver(JSON.parse(rec.frames[1])); // the real wake, at 1.44 s
      compare(suite.names(), "state", "the plate did not arrive with the frame");
      compare(stack.anyLit, true);
    }

    // --- a real turn, from the first frame to the last --------------------

    function test_a_real_question_puts_up_two_plates_and_nothing_else() {
      // hey-jarvis-clean: "Hey Jarvis, what time is it?" in a quiet room.
      // The VAD opens at 0.80 s and the corner stays DARK — speech in the
      // room is not speech to Jarvis, and there is nothing truthful to
      // show about it. The wake at 1.44 s puts the state plate up. The
      // utterance closes at 3.76 s, where ears transcribes and the words
      // join the state that now says THINKING — under it, never above it.
      //
      // Two plates, three entries, in that order. Everything a picture of
      // this turn could say is in `03-heard.png`; everything it cannot say
      // is the two numbers and the order.
      compare(suite.corner("hey-jarvis-clean"),
              "(dark) -> state@1.44 -> state heard@5.96");
    }

    function test_the_same_question_over_music_reads_the_same_shape() {
      // hey-jarvis-music is the same turn with a music bed behind it: the
      // wake scores 0.963 instead of 0.990 and every transcript confidence
      // drops. That must move the timing and NOTHING ELSE — no extra
      // plate, no different order. A HUD that treated a noisier room as a
      // doubtful claim would show up here as a corner that reads
      // differently, which is A26's "no confidence bar" decision holding
      // at the level of what the user sees.
      compare(suite.corner("hey-jarvis-music"),
              "(dark) -> state@1.44 -> state heard@6.36");
    }

    function test_a_pause_mid_sentence_never_takes_the_corner_down_and_up() {
      // hey-jarvis-pause holds 1.2 s of real silence inside one sentence,
      // and rewrites itself seven times across it — "Hey Jarvis remind me
      // to", then "Hey Jarvis, remind me too.", then back again. Every one
      // of those was on the bus. If any provisional sentence reached the
      // screen, or if the pause split the utterance, this corner would
      // flicker: extra entries, in both directions, in the middle of
      // somebody talking. Two entries is the whole claim.
      compare(suite.corner("hey-jarvis-pause"),
              "(dark) -> state@1.36 -> state heard@8.84");
    }

    function test_a_room_talking_never_puts_anything_in_the_corner() {
      // speech-no-wake is a real utterance nobody addressed to Jarvis:
      // ears' VAD opens a segment at 0.80 s, closes it at 4.40 s and
      // transcribes nothing. The corner must be dark for every frame of
      // it — invariant 10 as a sequence rather than as a photograph. A
      // single entry here would be the HUD claiming the microphone is
      // open for us, or claiming to have heard something, over a room that
      // was simply talking.
      compare(suite.corner("speech-no-wake"), "(dark)");
      compare(stack.anyLit, false, "the surface would have been mapped over a room talking");
    }

    // --- what the recordings can NEVER light -----------------------------

    function test_no_recording_lights_a_plate_no_service_in_it_reported() {
      // These recordings are jv-ears alone: no sys.health, no
      // action.confirm, no action.result, no guard.verdict, no
      // context.system, and a link that never drops. Seven of the nine
      // plates therefore have nothing to say in any of them, and a plate
      // that lights anyway is reading frames that are not about it — a
      // MicPlate that took audio.vad for a capture counter would be a
      // recording light lit by the room rather than by the device, which
      // is invariant 10 broken in the worst direction.
      const allowed = ["state", "heard"];
      for (let i = 0; i < recordings.names.length; i++) {
        const name = recordings.names[i];
        suite.init();
        const seen = {};
        const rec = recordings.byName[name];
        for (let f = 0; f < rec.frames.length; f++) {
          Bus.deliver(JSON.parse(rec.frames[f]));
          const up = stack.litNames;
          for (let p = 0; p < up.length; p++)
            seen[up[p]] = true;
        }
        const lit = Object.keys(seen).sort();
        for (let l = 0; l < lit.length; l++) {
          verify(suite.everyPlate.indexOf(lit[l]) >= 0,
                 name + " lit a plate that is not in the shell's corner: " + lit[l]);
          verify(allowed.indexOf(lit[l]) >= 0,
                 name + " lit `" + lit[l] + "`, and nothing in that recording reports it");
        }
      }
    }

    function test_the_words_are_never_up_without_the_state_above_them() {
      // The one ORDERING claim that is about meaning rather than layout:
      // shell.qml puts the transcript under the state plate because the
      // two are one reading — that one says Jarvis is thinking, this one
      // says what about. A transcript on screen with no state above it
      // would be words with no explanation of why they are still there,
      // and it is a sequence bug: it needs the state plate to leave first.
      for (let i = 0; i < recordings.names.length; i++) {
        const name = recordings.names[i];
        suite.init();
        const rec = recordings.byName[name];
        for (let f = 0; f < rec.frames.length; f++) {
          Bus.deliver(JSON.parse(rec.frames[f]));
          const up = stack.litNames;
          const heard = up.indexOf("heard");
          if (heard < 0)
            continue;
          const state = up.indexOf("state");
          verify(state >= 0, name + ": the words are up with no state plate above them");
          verify(state < heard, name + ": the words are above the state plate");
        }
      }
    }

    // --- the turn has to end ---------------------------------------------

    function test_an_unanswered_turn_empties_the_corner_on_its_own() {
      // Nothing in these recordings ever publishes the brain.response or
      // the speech.state that ends a turn — jv-voice is not in them
      // (B10/A28). So both plates that go up are up on a WINDOW:
      // SpeechState's `thinkWindowS` and HeardState's `holdS`, 30 s each
      // and pinned equal by a tools test. Past those the HUD no longer
      // knows whether anyone is still working, so it must stop saying so.
      // A plate that never leaves is a stale claim outliving its evidence,
      // and no still picture can catch it: every shot is taken while
      // something is true.
      //
      // The two budgets are shortened and nothing else is staged: both
      // windows then close the way they close on ares, on their own
      // one-shot timers, in real time. Winding the injected clock instead
      // would prove less — SpeechState reads a frame's AGE and would
      // expire, while HeardState keeps its own time and would not, so the
      // corner would empty for a reason the machine does not have.
      //
      // 3 s, and the number is no longer arbitrary (A58). Both windows
      // start at the utterance's boundary and the words arrive 2.2 s
      // later — the ASR, which these recordings now carry — so a budget
      // under that expires the line before it is ever shown, and this
      // test would go green over a corner the reader never saw. It used
      // to be 200 ms, which was only ever legal while the recordings said
      // the ASR was free.
      const voice = suite.plateNamed("state");
      const words = suite.plateNamed("heard");
      verify(voice && words, "the corner is missing a plate this test drives");
      voice.voice.thinkWindowS = 3.0;
      words.heard.holdS = 3.0;

      compare(suite.corner("hey-jarvis-clean"),
              "(dark) -> state@1.44 -> state heard@5.96");
      tryVerify(function () {
        return suite.names() === "";
      }, 6000, "the corner never emptied after a question nobody answered");
      compare(stack.anyLit, false, "the surface would have stayed mapped for nothing");
    }

    function test_losing_the_bus_mid_turn_takes_every_plate_down_first() {
      // A23, as a sequence. Every plate under the link plate gates on the
      // same bus the link plate is reporting the loss of, so the instant
      // the bridge goes the corner has to go with it — the words and the
      // state are claims about a machine the HUD can no longer see.
      //
      // The in-between is the part no picture can hold: LinkState waits
      // `graceS` (5 s) before it will call the HUD blind, because a
      // reconnecting bridge is not a lost machine. So the corner is DARK
      // for those five seconds — not "state heard", and not yet "link".
      // `07-no-bus.png` settles past the grace and can only ever show the
      // end of that, which is why this is checked here instead.
      compare(suite.corner("hey-jarvis-clean"),
              "(dark) -> state@1.44 -> state heard@5.96");
      Bus.ingest('{"t":"link","up":false,"err":"connect /run/jarvis/bus.sock: No such file or directory"}');
      compare(suite.names(), "",
              "a plate stayed up over a bus the HUD can no longer see");
      // The grace runs on a real Timer (it is a duration the HUD decides,
      // not a frame age), so this is the one place the file waits — and it
      // waits for the corner rather than for a number of milliseconds.
      tryVerify(function () {
        return suite.names() === "link";
      }, 8000, "the HUD never admitted it was blind");
      compare(suite.names(), "link", "something else came back with the link plate");
    }
  }
}
