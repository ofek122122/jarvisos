// The HUD, photographed — so that looking at it stops requiring a seat at
// ares (PLAN A29).
//
// Every element in shell/jv-hud has been built, linted and tested without
// anyone ever seeing it: the sandbox this loop runs in has no compositor,
// so "the surface maps" has always been verified by construction. The
// standing ask — go and look at it — has gone unanswered for twenty-six
// iterations, and five open plan items (A13, A21, A22, A25, A27) are
// blocked on a human eye rather than on any code.
//
// This is not a test in the usual sense. It builds the real plates, over
// the real Theme, driven through the real core/BusModel, and writes what
// they draw to PNG. It asserts almost nothing: an assertion about pixels
// is a thing that breaks when a font ships a new version, and the point
// here is a picture a person can look at, not a comparison a machine can
// make. What it DOES assert is that every shot drew something (except the
// one whose whole subject is drawing nothing) — because a contact sheet of
// seven empty rectangles would look like a HUD with earned emptiness and
// would actually be a broken harness.
//
// Honest about what it is NOT:
//   · not the compositor. Layer-shell, the empty input mask, the zero
//     exclusive zone and the three real monitors are shell.qml's, and
//     nothing here exercises them. This is the CONTENT of one surface.
//   · not a live machine. Some shots replay real recordings from
//     harness/fixtures/sessions (B3) and some are frames written by hand,
//     because nothing in the repo has ever recorded jv-voice speaking
//     (B10/A28) or jv-act asking. docs/hud/README.md says which is which,
//     per shot, and that line is the whole value of the sheet.
import QtQuick
import QtTest
import ".."
import "../core"

Item {
  id: root

  // shell.qml's surface box, to the pixel: the shot is the whole area the
  // HUD may ever paint, not a crop around whatever happens to be lit. The
  // empty two-thirds is the point — §06's earned emptiness is a thing you
  // have to SEE to have an opinion about.
  width: 300
  height: 560

  // NOT the HUD. The real surface is `color: "transparent"` and floats
  // over whatever Niri has on screen; a PNG has to put something behind
  // the plates or the translucency (`plate_opacity = 0.86`) is invisible
  // and the sheet renders on whatever background a browser feels like.
  // A flat neutral grey, deliberately not a theme token — a colour that
  // appeared in personality/theme.toml would be a colour a reader could
  // mistake for Jarvis's. tools/tests/test_hudshots.py holds that line.
  readonly property color backdrop: "#31353B"

  Rectangle {
    anchors.fill: parent
    color: root.backdrop
  }

  // The corner stack, as shell.qml composes it: same order, same anchors,
  // same margins. It is a copy, and a copy is a thing that drifts, so
  // tools/tests/test_hudshots.py reads the plate list out of both files
  // and fails if they stop matching — a new plate that never appears in
  // the sheet would be a new plate nobody ever looked at.
  PlateStack {
    id: stack

    anchors.top: parent.top
    anchors.right: parent.right
    anchors.topMargin: Theme.insetPx
    anchors.rightMargin: Theme.insetPx
    spacing: Theme.gapPx

    LinkPlate {
      anchors.right: parent.right
    }

    ConfirmPlate {
      anchors.right: parent.right
    }

    StatePlate {
      anchors.right: parent.right
    }

    HeardPlate {
      anchors.right: parent.right
    }

    MicPlate {
      anchors.right: parent.right
    }

    HealthPlate {
      anchors.right: parent.right
    }
  }

  // The recorded sessions, compiled to QML by tools/gen_sessions_qml.py
  // and staged in next door. Same file the HUD's own replay test reads.
  Sessions {
    id: recordings
  }

  TestCase {
    id: suite

    name: "HudShots"
    when: windowShown

    property int seq: 0

    // --- frames -------------------------------------------------------

    // One envelope, in the bridge's shape. `ts` defaults to now, which is
    // what a frame that just arrived looks like.
    function send(topic, src, body, conf, ts) {
      Bus.deliver({
        "topic": topic,
        "ts": ts === undefined ? Bus.now : ts,
        "seq": suite.seq++,
        "src": src,
        "conf": conf === undefined ? 1.0 : conf,
        "v": 1,
        "body": body
      });
    }

    // A sys.health heartbeat. `metrics` is the free-form field A14 gave
    // jv-ears for its capture counters and jv-brain for its llm rung.
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

    // The microphone as jv-ears reports it while a real device is open.
    function micOpen() {
      suite.beat("jv-ears", "ok", {
        "mic_open": 1,
        "capture_age_s": 0.02,
        "captured_s": 1846.4,
        "capture_stall_s": 2.0
      });
    }

    // Replay a recording up to and including `untilTs` (undefined = all of
    // it). The frames are the committed lines, unmodified.
    function replay(name, untilTs) {
      const lines = recordings.byName[name].frames;
      for (let i = 0; i < lines.length; i++) {
        const env = JSON.parse(lines[i]);
        if (untilTs !== undefined && env.ts > untilTs)
          return;
        Bus.deliver(env);
      }
    }

    // --- shots --------------------------------------------------------

    // A HUD that can see the bus and has nothing to say. Every plate is
    // refusing to invent something, which on a well machine is also what
    // "all quiet" looks like — the shell leaves the surface unmapped and
    // the screen is the desktop. This is the ordinary state.
    function shot_quiet() {
      Bus.ingest('{"t":"link","up":true}');
    }

    // Real recording (hey-jarvis-clean), replayed to the wake word at
    // 1.44 s: the microphone window jv-ears opened, teal because the open
    // mic is yours. The heartbeat under it is composed — no recorded
    // session carries sys.health at all (B10).
    function shot_listening() {
      Bus.ingest('{"t":"link","up":true}');
      suite.replay("hey-jarvis-clean", 1.44);
      suite.micOpen();
    }

    // The same recording, all of it: the words jv-ears took down, under
    // the state that says Jarvis has them and has not answered yet.
    function shot_heard() {
      Bus.ingest('{"t":"link","up":true}');
      suite.replay("hey-jarvis-clean");
      suite.micOpen();
      suite.send("brain.request", "jv-brain", {
        "text": "Hey Jarvis, what time is it?",
        "source": "voice"
      });
    }

    // COMPOSED. Nothing committed has ever recorded jv-voice speaking, so
    // the one frame that ends a turn is written here by hand — which is
    // precisely the gap B10/A28 asks a human to close with one real
    // utterance at the machine.
    function shot_speaking() {
      Bus.ingest('{"t":"link","up":true}');
      suite.replay("hey-jarvis-clean");
      suite.micOpen();
      suite.send("speech.state", "jv-voice", {
        "state": "speaking",
        "utterance_id": "5ab8fecf-13d0-4f86-aa5d-0b2cc23b4d5d"
      });
    }

    // COMPOSED. jv-act stopping in front of a destructive tool, in its own
    // words, with the 15 s window running. This is the one thing the HUD
    // shows that is waiting on YOU — and until A20 it was only ever spoken.
    function shot_confirm() {
      Bus.ingest('{"t":"link","up":true}');
      suite.micOpen();
      suite.send("action.confirm", "jv-act", {
        "kind": "request",
        "request_id": "req-4f21",
        "tool": "fs.trash",
        "summary": "move 14 files in ~/Downloads to the trash — yes or no?",
        "window_s": 15.0
      });
    }

    // COMPOSED. What the machine looks like when it is not well: the short
    // list, worst first, and the llm rung read off jv-brain's own
    // heartbeat because that is the number that explains the slowness.
    function shot_health() {
      Bus.ingest('{"t":"link","up":true}');
      suite.micOpen();
      suite.beat("jv-brain", "degraded", {
        "llm_rung": 4,
        "llm_gpu": 0
      }, "VRAM pressure: fell back to CPU");
      suite.beat("jv-voice", "ok");
      suite.beat("jv-compat", "degraded", undefined, "wine prefix rebuild pending");
    }

    // The HUD admitting it cannot see the machine at all (A23). Every
    // plate below refuses to guess, and a refusal draws the same nothing a
    // calm machine draws — so without this line a dark recording light
    // over a microphone the HUD simply cannot see would read as "off".
    function shot_nobus() {
      Bus.ingest('{"t":"link","up":true}');
      suite.micOpen();
      Bus.ingest('{"t":"link","up":false,"err":"connect /run/jarvis/bus.sock: No such file or directory"}');
    }

    // --- the sheet ----------------------------------------------------

    // name -> builder, in reading order. The file names carry the order so
    // a directory listing is the sheet.
    readonly property var sheet: [
      { "file": "01-quiet.png", "build": suite.shot_quiet, "lit": false },
      { "file": "02-listening.png", "build": suite.shot_listening, "lit": true },
      { "file": "03-heard.png", "build": suite.shot_heard, "lit": true },
      { "file": "04-speaking.png", "build": suite.shot_speaking, "lit": true },
      { "file": "05-confirm.png", "build": suite.shot_confirm, "lit": true },
      { "file": "06-health.png", "build": suite.shot_health, "lit": true },
      // LinkState holds a 5 s grace before it will call the HUD blind — a
      // reconnecting bridge is not a lost machine — so this one settles
      // past that rather than photographing the silence in between.
      { "file": "07-no-bus.png", "build": suite.shot_nobus, "lit": true, "settleMs": 6500 }
    ]

    function test_the_sheet() {
      for (let i = 0; i < suite.sheet.length; i++) {
        const shot = suite.sheet[i];

        Bus.reset();
        suite.seq = 0;
        shot.build();

        // Past the longest §06 duration, so the grab lands on the settled
        // frame rather than somewhere inside a fade — or past whatever
        // longer window this particular shot is waiting on. The waits are
        // the only reason this file takes a visible moment to run.
        wait(shot.settleMs === undefined ? Theme.pulseMs + Theme.easeMs : shot.settleMs);

        // A surface with nothing lit is unmapped on a real machine, so a
        // plate stack that lit nothing is either the quiet shot or a
        // harness that fed the plates something they refused. Both look
        // identical in a PNG; only this line tells them apart.
        compare(stack.anyLit, shot.lit, shot.file + ": stack.anyLit");

        const img = grabImage(root);
        compare(img.width, root.width, shot.file + ": width");
        compare(img.height, root.height, shot.file + ": height");
        // Relative to the process's working directory — ops/ralph/hudshots.sh
        // runs the runner from the output directory, which is how a QML
        // test with no way to read an environment variable is told where
        // to put its files.
        img.save(shot.file);
      }
    }
  }
}
