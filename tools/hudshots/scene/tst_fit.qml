// The CROWDED corner — every plate that can be up at once, each drawing the
// widest thing it will ever draw, measured against the surface it has to fit
// inside (PLAN A63).
//
// shell.qml's box is 300x807, and until this file every digit of that number
// came out of an ARGUMENT about co-occurrence: LinkPlate "can never share the
// surface, but a box sized by an argument about how other elements behave is
// a box that clips"; ConfirmPlate and HeardPlate each wrap to three lines;
// GuardPlate and InstallPlate "can genuinely share the surface with
// everything under it". Four arguments, written in a comment, checked by
// nothing. The only fit check that existed ran over the contact sheet, whose
// tallest picture lights THREE plates and clears the box by more than 500 px
// — so the case the box is actually sized for has never been measured at all.
//
// What a failure here would be, on a real machine: a layer-shell panel
// floating over every window, with a plate cut in half at the bottom edge.
// Nothing errors, nothing logs, and the half-plate is as likely to be the
// HUD saying an action failed as it is to be the microphone indicator.
//
// WHAT THIS FILE IS NOT. Not a picture. A63's other half — a composed SHOT
// of a crowded corner — is deliberately not taken here, because a photograph
// of eight unrelated plates stacked 8 px apart is a picture of exactly the
// confusion A62 raises (does the reader assume one story?), and that is a
// human's design question, not an assertion's. This file answers the half
// that is arithmetic: does what the box is sized for fit in the box.
//
// WHY THE STRINGS ARE OVER-LONG. Every text plate caps its own width
// (`maxTextPx`) and some cap their own characters (GuardState.maxNameChars),
// so the widest a plate can EVER be is its cap, not any sentence a service
// really sends. The probes below are deliberately past every cap: what is
// being measured is the cap, and a plate whose cap stopped working would
// measure wider than the surface here rather than eliding quietly on ares.
// That is the opposite of the contact sheet's rule next door, where every
// field is held to the producer that really emits it — because that file
// photographs what the machine says and this one measures what the plate
// will not exceed.
//
// FOUR PLATES ARE NOT AT THEIR LONGEST WORD, and it does not matter.
// `StatePlate`, `OutputPlate`, `MicPlate` and `ReplyPlate` draw one word out
// of a fixed vocabulary, so their widest is INTERRUPTED rather than SPEAKING
// and there is no cap to sit at. None of them can be the binding constraint
// either way: the widest of the four is 132 px against a 260 px capped plate,
// and their HEIGHT — the only thing the box is short of — is fixed regardless
// of the word (one row, or the reply plate's two). `state` is held at
// `speaking` here because that is what makes `output` truthful, and a crowd
// that traded one for the other would be a smaller crowd.
//
// WHY MOTION IS OFF. Same reason as tst_sequence.qml: a plate's `lit` is
// `opacity > 0` through `Ease`, so with fades running, WHICH plates are in
// the crowd is a question about a 140 ms animation on the render thread.
// Under the real reduced-motion path every opacity is assigned, so the crowd
// is whole in the frame the bus spoke and the only thing left to wait for is
// the layout.
import QtQuick
import QtTest
import ".."

Item {
  id: root

  // shell.qml's surface box, to the pixel. tools/tests/test_hudshots.py pins
  // this to the shell's own `implicitWidth`/`implicitHeight` — a box that
  // grew there and not here would leave this check asserting yesterday's
  // edge, which is the failure mode that makes a check worse than none.
  width: 300
  height: 807

  // The same corner shell.qml composes, in the same order, from the one file
  // both other drivers use.
  Corner {
    id: stack

    anchors.top: parent.top
    anchors.right: parent.right
    anchors.topMargin: Theme.insetPx
    anchors.rightMargin: Theme.insetPx
  }

  TestCase {
    id: suite

    name: "HudFit"
    when: windowShown

    property int seq: 0

    // Every plate the shell can put up, in stack order.
    readonly property var everyPlate: ["link", "confirm", "state", "output", "heard", "reply", "action", "guard", "install", "mic", "health"]

    // The one plate that excludes every other: each of the ten below gates
    // on `Bus.linkUp`, so a HUD that cannot see the bus draws this and
    // nothing else. The crowd is therefore the other ten, and `test_the_
    // two_crowds_are_the_only_two` holds that split rather than assuming it.
    readonly property string blindPlate: "link"

    // The services on this machine, by directory name under services/ minus
    // the library. A roster this long is not a prediction — it is the worst
    // case the health plate has to survive, and every name in it is real.
    readonly property var roster: ["jarvisd", "jv-act", "jv-brain", "jv-compat", "jv-context", "jv-ears", "jv-guard", "jv-hud-bridge", "jv-voice"]

    function initTestCase() {
      Motion.policy.envOverride = "1";
    }

    function cleanupTestCase() {
      // The singleton belongs to the engine, and the sheet next door renders
      // its fades for real.
      Motion.policy.envOverride = "";
    }

    function init() {
      Bus.reset();
      suite.seq = 0;
    }

    // --- frames ---------------------------------------------------------

    function send(topic, src, body, ts) {
      Bus.deliver({
        "topic": topic,
        "ts": ts === undefined ? Bus.now : ts,
        "seq": suite.seq++,
        "src": src,
        "conf": 1.0,
        "v": 1,
        "body": body
      });
    }

    function beat(service, state, metrics, notes) {
      let b = {
        "service": service,
        "state": state,
        "uptime_s": 1847,
        "period_s": 5
      };
      if (metrics !== undefined)
        b.metrics = metrics;
      if (notes !== undefined)
        b.notes = notes;
      suite.send("sys.health", service, b);
    }

    // A string past every cap in this HUD, in the alphabet the plates
    // actually render: `n` characters of mono text is wider than any
    // `maxTextPx` long before it is long enough to be a sentence.
    function overlong(n) {
      let s = "";
      while (s.length < n)
        s += "Wm0";
      return s.slice(0, n);
    }

    // --- the crowd ------------------------------------------------------

    // Every plate but `link`, each at its own widest.
    //
    // It is one moment, and it is a moment this machine can reach: Jarvis is
    // part-way through an answer into a sink somebody muted (state + output),
    // the user has talked over it and jv-ears has the new words down (heard —
    // the `speaking` frame is OLDER than the transcript, which is exactly the
    // barge-in core/HeardState.qml is written around), jv-act is holding a
    // confirmation open and has separately failed a different call (confirm +
    // action), the answer being read out ran out of context (reply),
    // jv-guard has refused a binary and jv-compat has failed an install
    // (guard + install), the microphone is live (mic), and the services are
    // complaining (health). Nobody will see this HUD. The box is
    // sized for it anyway, which is the only reason there is a height in
    // shell.qml at all.
    function crowd() {
      Bus.ingest('{"t":"link","up":true}');

      // jv-voice, mid-utterance, into the default sink…
      suite.send("sys.health", "jv-voice", {
        "service": "jv-voice",
        "state": "degraded",
        "uptime_s": 1847,
        "period_s": 5,
        "notes": "piper fell behind",
        "metrics": {
          "output_device_pinned": 0
        }
      });
      suite.send("speech.state", "jv-voice", {
        "state": "speaking",
        "utterance_id": "5ab8fecf-13d0-4f86-aa5d-0b2cc23b4d5d"
      });
      // …reading out an answer that jv-brain had already run out of room
      // for. brain.response is published when the STREAM closes, so a
      // truncated reply and a jv-voice still working through its sentences
      // are the ordinary pair rather than a contrived one.
      suite.send("brain.response", "jv-brain", {
        "text": "The meeting is at three, and the one after it is",
        "finish_reason": "length",
        "conversation_id": "5ab8fecf-13d0-4f86-aa5d-0b2cc23b4d5d",
        "backend": "cpu",
        "latency_ms": 8412
      });
      // …which jv-context says is muted.
      suite.send("context.system", "jv-context", {
        "net_online": true,
        "load1": 6.1,
        "mem_used_pct": 71.8,
        "audio_volume": 0.62,
        "audio_muted": true,
        "gpu_vram_free_mb": 943
      });

      // The user talking over it. Stamped AFTER the `speaking` above, so
      // HeardState reads it as a barge-in rather than as an answered turn.
      suite.send("audio.transcript", "jv-ears", {
        "kind": "final",
        "text": suite.overlong(240),
        "lang": "en",
        "utterance_id": "6b1c0d94-3a72-4f51-8e2d-97f4a05c1b83"
      }, Bus.now + 0.2);

      // jv-act, holding a question open and reporting a different failure.
      suite.send("action.confirm", "jv-act", {
        "kind": "request",
        "request_id": "4f21a6c8-2b7d-4e15-9a03-6c5d8e1b47f0",
        "tool": "window.move_workspace",
        "summary": suite.overlong(240),
        "window_s": 15.0
      });
      suite.send("intent.action", "jv-brain", {
        "request_id": "9c07b3e1-5f84-42da-8b6e-01c7a9d25384",
        "tool": suite.overlong(64),
        "args": {
          "app": "obsidian"
        },
        "capability": "benign",
        "needs_confirmation": false
      });
      suite.send("action.result", "jv-act", {
        "request_id": "9c07b3e1-5f84-42da-8b6e-01c7a9d25384",
        "ok": false,
        "duration_ms": 214,
        "error": "capability_mismatch"
      });

      // jv-guard refusing a binary, jv-compat failing an install.
      suite.send("guard.verdict", "jv-guard", {
        "sha256": "9f2c4b7a1e08d3c65a4fbe2170d9c8815b3e6a04f7d2c9b81e5a30f64c7b92d1",
        "verdict": "blocked",
        "reasons": ["clamav signature: Win.Trojan.Agent-9823041"],
        "path": "/home/ofek/Downloads/" + suite.overlong(96) + ".exe",
        "scanned_by": ["clamav"]
      });
      // Not `overlong()`: `InstallState.plainSlug` REFUSES a slug past
      // `maxSlugChars` or outside the slug alphabet rather than truncating
      // it, so an over-long probe here draws an EMPTY app name — the plate
      // at its narrowest, on a check about its widest. 40 characters of
      // real slug is the cap, exactly.
      suite.send("compat.install", "jv-compat", {
        "event": "failed",
        "app": "notepad-plus-plus-portable-x64-installer",
        "sha256": "4d0d5d4bb6f8d63a0f0a08dd9e8d2f15b1d9c3a7e6b40f2c8a17d35e9b0c6a21",
        "error": "wine: could not load kernel32.dll, status c0000135"
      });

      // The microphone, live, off jv-ears' own capture counters — on a
      // heartbeat that also says jv-ears is impaired, which is a real pair:
      // `degraded` means alive, and a service dropping partials is still
      // capturing.
      suite.beat("jv-ears", "degraded", {
        "mic_open": 1,
        "capture_age_s": 0.02,
        "captured_s": 1846.4,
        "capture_stall_s": 2.0
      }, "partials behind");

      // And everybody else complaining. jv-brain on the CPU floor adds the
      // two rows under the list: the rung, and the VRAM that explains it.
      suite.beat("jv-brain", "degraded", {
        "llm_rung": 4,
        "llm_gpu": 0,
        "llm_gpu_floor_mb": 5424
      }, "VRAM pressure: fell back to CPU");
      for (let i = 0; i < suite.roster.length; i++) {
        const service = suite.roster[i];
        if (service === "jv-ears" || service === "jv-brain" || service === "jv-voice")
          continue;
        suite.beat(service, "degraded", undefined, "impaired");
      }

      // And let the scene lay out. Every check below reads a SIZE, and a
      // size is the one thing in this harness that is not ready in the
      // frame the bus spoke: motion is off, so the plates' opacity is
      // assigned, but `Column` positions its children and `Text` measures
      // its wrap on the next polish. Without this a check reads the sizes the
      // items were BUILT with — every plate 35 px tall, the health plate
      // 20x20, a 240-character question 90 px wide — and passes enormously.
      // That is not hypothetical: it is what the first version of this file
      // did in whichever check ran first, and the only reason the fit check
      // was not one of them is that a check ahead of it had already spun the
      // event loop.
      //
      // `waitForRendering` and not a `wait(ms)`: the stub clock only moves
      // when a frame is delivered, but every state element's backstop is a
      // real Timer, and a plain wait spends real milliseconds against
      // windows the fake clock says have not started. Blocking on the next
      // rendered frame settles the layout and spends none.
      verify(waitForRendering(root), "the scene never rendered");
    }

    // --- the checks -----------------------------------------------------

    // The control. Everything below measures a stack, and a stack that
    // quietly lit five plates instead of nine would measure comfortably and
    // prove nothing — which is how a fit check goes vacuous.
    function test_the_crowd_really_is_every_plate_but_the_blind_one() {
      suite.crowd();
      const expected = suite.everyPlate.filter(name => name !== suite.blindPlate);
      compare(stack.litNames.join(" "), expected.join(" "),
              "the crowd is not the crowd");
    }

    // The two crowds are the only two: `link` alone, or the other ten. Every
    // plate below LinkPlate gates on the same link it reports on, so a HUD
    // that cannot see the bus has exactly one thing to say — and if that ever
    // stops being true, the box has a taller case than the one measured here
    // and this file would not have noticed.
    function test_the_two_crowds_are_the_only_two() {
      suite.crowd();
      Bus.ingest('{"t":"link","up":false,"error":"bus.sock: connection refused"}');
      wait(6000); // LinkState.graceS + a settle: the HUD waits before saying it is blind
      compare(stack.litNames.join(" "), suite.blindPlate,
              "a blind HUD is not showing the blind plate alone");
    }

    // The height. This is A63, and the first time it was run the corner was
    // 713 px in a 688 px box: 41 px over, with `HealthPlate` — the plate that
    // says what is wrong — as the thing being cut in half.
    //
    // The rule is TWO insets, not one. §06 gives the corner an `insetPx` gap
    // at the top and at the right; the bottom edge got none, so a stack that
    // exactly filled the box would end flush against the edge of a panel
    // floating over every window, which reads as a crop whether or not it is
    // one. The box is now 2 x insetPx + this measurement, so this passes with
    // nothing to spare — which is the point. Any pixel a plate grows, this
    // says so.
    function test_the_crowded_corner_fits_the_surface() {
      suite.crowd();
      verify(Theme.insetPx * 2 + stack.height <= root.height,
             "the crowded corner is " + stack.height + " px tall between two "
             + Theme.insetPx + " px insets on a " + root.height + " px surface — "
             + (Theme.insetPx * 2 + stack.height - root.height) + " px over");
    }

    // The control for the WIDEST half of the claim, and it is the one that
    // caught the only real mistake in this file: `InstallState.plainSlug`
    // REFUSES a slug past its cap instead of truncating it, so the probe
    // that made every other plate draw its widest made that one draw its
    // narrowest — an empty app name on a check about crowding. Nothing
    // failed. The corner measured 3 px short of the truth.
    //
    // So every plate that declares a text cap has to BE at it. A plate that
    // quietly refused what it was handed measures a plate nobody is
    // crowding, which is the way this whole file goes vacuous.
    function test_every_capped_plate_is_drawing_at_its_cap() {
      suite.crowd();
      const kids = stack.children;
      let capped = 0;
      for (let i = 0; i < kids.length; i++) {
        const kid = kids[i];
        if (!(kid.shown || kid.lit) || kid.maxTextPx === undefined)
          continue;
        capped++;
        compare(kid.width, kid.maxTextPx + Theme.padPx * 2,
                kid.plateName + " caps its text at " + kid.maxTextPx
                + " px and is drawing " + kid.width + " px wide — it refused "
                + "the probe rather than eliding it");
      }
      verify(capped >= 5, "only " + capped + " plates in the crowd declare a text cap");
    }

    // The width, which is the half A63 gained from shot 13: a corner is not
    // only a stack that might not fit downwards, it is several near-full-width
    // plates. Each plate is measured on its own so a failure names the plate.
    function test_no_plate_is_wider_than_the_surface() {
      suite.crowd();
      const kids = stack.children;
      for (let i = 0; i < kids.length; i++) {
        const kid = kids[i];
        if (!(kid.shown || kid.lit))
          continue;
        verify(kid.width + Theme.insetPx <= root.width,
               kid.plateName + " is " + kid.width + " px wide, "
               + Theme.insetPx + " px in from a " + root.width + " px surface");
      }
    }
  }
}
