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
// they draw to PNG. It asserts nothing about PIXELS: that is a thing that
// breaks when a font ships a new version, and the point here is a picture
// a person can look at, not a comparison a machine can make.
//
// What it DOES assert is the caption — which plates are on screen in each
// shot, in reading order, as the plates themselves report it (A53). That
// used to be one bit per shot (`anyLit`: something is drawn), which nine
// of the ten shots answered identically, so a harness that fed a plate
// something it refused and photographed a DIFFERENT plate instead would
// have gone green with a sheet that misnames its own contents. Two plates
// in this stack draw the same two lines, in the same severity colour, in
// the same corner; a picture is the only thing that has ever told them
// apart, and a picture needs a human.
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

Item {
  id: root

  // shell.qml's surface box, to the pixel: the shot is the whole area the
  // HUD may ever paint, not a crop around whatever happens to be lit. The
  // empty two-thirds is the point — §06's earned emptiness is a thing you
  // have to SEE to have an opinion about.
  width: 300
  height: 745

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

  // The corner stack, as shell.qml composes it: same plates, same order,
  // same self-anchoring. It lives in Corner.qml next door because the
  // sequence replay (A54) drives the same stack, and two harnesses with
  // two copies of it would be two things to keep matching shell.qml.
  // tools/tests/test_hudshots.py reads the plate list out of Corner.qml and
  // out of shell.qml and fails if they stop matching — a new plate that
  // never appears in the sheet would be a new plate nobody ever looked at.
  //
  // The inset is here rather than in Corner: the shot is the whole surface
  // box, so the plates have to sit where they sit on it, and the replay
  // next door has no box at all.
  Corner {
    id: stack

    anchors.top: parent.top
    anchors.right: parent.right
    anchors.topMargin: Theme.insetPx
    anchors.rightMargin: Theme.insetPx
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
    //
    // ITS OWN WORDS, LITERALLY (A67). jv-act does not compose a sentence
    // about the invocation. It sends
    // `format!("{} — yes or no?", spec.description)` — the REGISTRY
    // description of the tool and a fixed tail — so the question it asks
    // is generic by construction, and the older frame here ("move 14
    // files in ~/Downloads to the trash") was a picture of a machine that
    // says what it is about to touch. It does not, and A21's reader
    // deserves to be judging the question that will really be on screen.
    // The window and `kind` are jv-act's too; tools/tests/test_hudshots.py
    // reads all three out of services/jv-act/src/service.rs.
    //
    // ONE THING IN IT IS NOT JV-ACT'S OWN, the same thing A49 wrote down
    // for the other sheet: `fs.trash` is not in jv-act's registry.
    // services/jv-act/tools.toml is v0 — "observe + benign only" — so it
    // holds no destructive tool at all, and the confirmation rule is
    // structural: ONLY destructive and privileged tools are ever
    // confirmed. Asked for `fs.trash` today the real jv-act would answer
    // `unknown_tool` and ask nobody anything. The machinery being
    // photographed is built and reviewed; the tool it is holding is one
    // the registry has not been granted yet, and the description below is
    // therefore the one composed string in the frame — written in the
    // registry's own voice ("Launch an application", "Close a window").
    //
    // The request id is jv-brain's uuid4 (service.py mints it and jv-act
    // echoes it back); it reaches no pixel and is here because a frame
    // with `req-4f21` in it is a frame nothing on this machine produces.
    function shot_confirm() {
      Bus.ingest('{"t":"link","up":true}');
      suite.micOpen();
      suite.send("action.confirm", "jv-act", {
        "kind": "request",
        "request_id": "4f21a6c8-2b7d-4e15-9a03-6c5d8e1b47f0",
        "tool": "fs.trash",
        "summary": "Move files to the trash — yes or no?",
        "window_s": 15.0
      });
    }

    // COMPOSED. What the machine looks like when it is not well: the short
    // list, worst first, and the llm rung read off jv-brain's own
    // heartbeat because that is the number that explains the slowness.
    function shot_health() {
      Bus.ingest('{"t":"link","up":true}');
      suite.micOpen();
      // The floor is jv-brain's own arithmetic over its own ladder
      // (`launcher.gpu_floor_mb`, B45), published only while something is
      // waiting on it — which a brain on rung 4 with a card present is.
      // tools/tests/test_hudshots.py recomputes it off that ladder, so
      // this figure is checked rather than chosen.
      suite.beat("jv-brain", "degraded", {
        "llm_rung": 4,
        "llm_gpu": 0,
        "llm_gpu_floor_mb": 5424
      }, "VRAM pressure: fell back to CPU");
      suite.beat("jv-voice", "ok");
      suite.beat("jv-compat", "degraded", undefined, "wine prefix rebuild pending");
      // And WHY the brain is on the floor (B40), from jv-context's 1 Hz
      // snapshot of the card. 943 MiB is not a stand-in: it is what ares
      // measured, twice in one week, with a healthy 6 GB GTX 1660 SUPER
      // whose VRAM the desktop and a browser had already spent. Without
      // this frame the rung line above reads as a fault; with it, it reads
      // as the ladder in invariant 6 doing its job.
      suite.send("context.system", "jv-context", {
        "net_online": true,
        "load1": 2.4,
        "mem_used_pct": 41.8,
        "audio_volume": 0.62,
        "audio_muted": false,
        "gpu_vram_free_mb": 943
      });
    }

    // COMPOSED. jv-act reaching into the machine and getting nowhere. The
    // pair is what the plate needs and what the bus really carries: the
    // intent names the tool, the result says only that request_id failed,
    // and core/ActionState.qml will not put the name on screen unless the
    // two ids match. `denied` and `confirm_timeout` are deliberately NOT
    // photographed here — they are how a confirmation ended, which is
    // A22's open question and not this plate's to answer.
    //
    // Every field here that is vocabulary rather than prose is now held
    // to its producer (A67), and three of them were wrong before anyone
    // looked: the intent passed `args.name` where the registry declares
    // `app` (jv-act would have answered `invalid_args`), it omitted the
    // `needs_confirmation` jv-brain always derives from the capability,
    // and the ids were short stand-ins where jv-brain mints uuid4s.
    //
    // The detail was the interesting one. `exec: "obsidian": executable
    // file not found in $PATH` is a Go runtime's sentence about execing a
    // binary directly, and jv-act is Rust and does not exec the
    // application at all: `app.launch` plans `gtk-launch -- <app>`, and a
    // failure's detail is THAT program's stderr. The line below is
    // gtk-launch's own message for a desktop id it cannot find. It is
    // still composed — no gtk-launch has ever run in this sandbox — so
    // what the gate pins is the program it names, which is the part that
    // was a lie about how this machine launches things.
    //
    // Neither `args` nor `detail` reaches a pixel, and a tools gate keeps
    // it that way (invariant 7). They are in the frame because the bridge
    // forwards whole envelopes and the sheet should show what the HUD is
    // really handed.
    function shot_action() {
      Bus.ingest('{"t":"link","up":true}');
      suite.micOpen();
      suite.send("intent.action", "jv-brain", {
        "request_id": "9c07b3e1-5f84-42da-8b6e-01c7a9d25384",
        "tool": "app.launch",
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
        "error": "execution_failed",
        "detail": "gtk-launch: no such application obsidian"
      });
    }

    // COMPOSED. Jarvis answering into a sink nobody can hear (A40). The
    // pair is what the plate needs and what the bus really carries: jv-voice
    // saying an utterance is in flight, and jv-context's 1 Hz snapshot of
    // the default sink saying it is muted. Every service in this picture is
    // `ok`, which is the whole point — this is the one failure where
    // nothing is broken and the room is silent anyway.
    function shot_muted() {
      Bus.ingest('{"t":"link","up":true}');
      suite.micOpen();
      // A41: the plate will not speak about the default sink until
      // jv-voice has said that is where it plays. 0 = `sd.play()` with no
      // device argument, which is jv-voice's ordinary configuration.
      suite.send("sys.health", "jv-voice", {
        "service": "jv-voice",
        "state": "ok",
        "uptime_s": 1847,
        "period_s": 5,
        "metrics": {
          "output_device_pinned": 0
        }
      });
      suite.send("speech.state", "jv-voice", {
        "state": "speaking",
        "utterance_id": "5ab8fecf-13d0-4f86-aa5d-0b2cc23b4d5d"
      });
      suite.send("context.system", "jv-context", {
        "net_online": true,
        "load1": 2.4,
        "mem_used_pct": 41.8,
        "audio_volume": 0.62,
        "audio_muted": true
      });
    }

    // COMPOSED. jv-guard refusing a Windows binary (A51). One frame, from
    // a service that only ever speaks when somebody runs `jv-compat
    // install` — so unlike every other shot here there is no second topic
    // to join and nothing to time it against. The `reasons` are in the
    // frame and deliberately not on the plate: the schema says they are
    // spoken on request, and this picture is what a glance gets you.
    // The name is ordinary on purpose. The interesting names — the one
    // with a newline in it, the one with a bidirectional override — are
    // exercised in shell/jv-hud/tests/tst_guardstate.qml, where the result
    // can be compared rather than looked at; a sheet is for judging what
    // the ordinary case reads like.
    function shot_guard() {
      Bus.ingest('{"t":"link","up":true}');
      suite.micOpen();
      suite.send("guard.verdict", "jv-guard", {
        "sha256": "9f2c4b7a1e08d3c65a4fbe2170d9c8815b3e6a04f7d2c9b81e5a30f64c7b92d1",
        "verdict": "blocked",
        "reasons": ["clamav signature: Win.Trojan.Agent-9823041"],
        "scanned_by": ["clamav"],
        "path": "/home/ofek/Downloads/rct3-setup.exe"
      });
    }

    // COMPOSED. jv-compat failing to install a Windows app (A52). The
    // other half of the pair above it: that shot is a binary that never
    // got to run, this one is a binary that ran inside its prefix and did
    // not work. Two frames, because the interesting thing about this
    // element is which of the six lifecycle events it draws — the
    // `prefix_created` says the install was under way and is deliberately
    // invisible, and only the `failed` puts anything on screen. The
    // installer's own stdout is in the frame and on no pixel: the schema
    // calls it "failed/blocked detail", and it is 500 bytes written by the
    // one thing invariant 8 calls untrusted outright.
    function shot_install() {
      Bus.ingest('{"t":"link","up":true}');
      suite.micOpen();
      suite.send("compat.install", "jv-compat", {
        "event": "prefix_created",
        "app": "notepad-plus-plus",
        "sha256": "4d0d5d4bb6f8d63a0f0a08dd9e8d2f15b1d9c3a7e6b40f2c8a17d35e9b0c6a21",
        "recipe": "notepad-plus-plus"
      });
      suite.send("compat.install", "jv-compat", {
        "event": "failed",
        "app": "notepad-plus-plus",
        "sha256": "4d0d5d4bb6f8d63a0f0a08dd9e8d2f15b1d9c3a7e6b40f2c8a17d35e9b0c6a21",
        "error": "wine: could not load kernel32.dll, status c0000135"
      });
    }

    // COMPOSED, and the only shot here with TWO stories in it (A61). The
    // two plates above are the two halves of invariant 8 — a binary
    // refused, an install that failed — and no picture has ever shown them
    // together, though the surface box was grown 624 -> 688 px on the
    // argument that they co-occur. An argument no shot demonstrates is an
    // argument nobody can check, so here is the case, and it is not the
    // one A61 guessed at. (The argument is checked outright now — see
    // tst_fit.qml, which stacks every plate that can co-occur and found
    // the box 41 px short of them; A63.)
    //
    // A61 described a refusal followed by a RETRY: jv-guard blocks an
    // installer, the user fetches a different build, that one fails. That
    // sequence cannot produce this picture, and writing it out is how the
    // reason surfaced — jv-guard screens the second build too, a `clean`
    // verdict is newer news from the same screener, and
    // `core/GuardState.qml` lets the refusal go the moment it lands. The
    // refusal and the failure have to be about DIFFERENT binaries, and the
    // refusal has to be the newer of the two screenings.
    //
    // Which is exactly what two overlapping installs look like, because an
    // install takes minutes and a user does not sit and watch it:
    //
    //   t=0      `jv-compat install flstudio_win64_21.2.exe` — fingerprinted,
    //            screened clean, prefix built, and then minutes of silence
    //            while the installer runs inside bubblewrap.
    //   t=200    the user, waiting, grabs something else off a download
    //            site and installs that too. jv-guard matches a signature
    //            in it; jv-compat refuses it and builds no prefix.
    //   t=214    the FIRST install, still going, dies inside its prefix.
    //
    // Every frame here is one services/jv-compat/jv_compat/install.py and
    // services/jv-guard really publish, in the order they publish them —
    // including the `blocked` on `compat.install`, which is the one
    // lifecycle event `core/InstallState.qml` reads as no news at all, and
    // which lands here in the middle of another app's install where a
    // clearing event would have wiped the failure that follows it.
    //
    // What the picture is FOR, beyond the fit: the corner is showing two
    // different binaries at once and says nothing about that anywhere. The
    // refused file and the failed app are two identities stacked 8 px
    // apart, and a reader who assumes one story is reading the wrong one
    // (PLAN A62).
    function shot_guard_install() {
      Bus.ingest('{"t":"link","up":true}');

      // The long install. `nsis`, `x64` and the path ride the frame and
      // reach no pixel — jv-compat publishes them, and the only element
      // that reads this topic reads three fields of it.
      const fl = "7c1e5a0b93d84f26ab705c3e1d9f8460b2a4c7d1e03f9658ba2d4c7e1f60539a";
      suite.send("compat.install", "jv-compat", {
        "event": "fingerprinted",
        "app": "fl-studio",
        "sha256": fl,
        "path": "/home/ofek/Downloads/flstudio_win64_21.2.exe",
        "installer": "nsis",
        "arch": "x64"
      }, undefined, 0.0);
      // A clean screening draws nothing — the install proceeding IS the
      // report that the binary passed. It matters anyway: it is the
      // verdict the refusal below has to be NEWER than.
      suite.send("guard.verdict", "jv-guard", {
        "sha256": fl,
        "verdict": "clean",
        "reasons": [],
        "scanned_by": ["clamav"],
        "path": "/home/ofek/Downloads/flstudio_win64_21.2.exe"
      }, undefined, 0.9);
      suite.send("compat.install", "jv-compat", {
        "event": "screened",
        "app": "fl-studio",
        "sha256": fl
      }, undefined, 0.9);
      suite.send("compat.install", "jv-compat", {
        "event": "prefix_created",
        "app": "fl-studio",
        "sha256": fl,
        "recipe": "fl-studio"
      }, undefined, 1.2);

      // Two minutes later, with that installer still running: a second
      // binary, screened and refused. Its `fingerprinted` clears the
      // install latch, which is holding nothing yet — the failure has not
      // happened.
      const pack = "b03f4d8c6e21a95704fd3b8e1c6a02975d4e8b13fa06c92d7e5b418a0c36f2d7";
      suite.send("compat.install", "jv-compat", {
        "event": "fingerprinted",
        "app": "codec-pack",
        "sha256": pack,
        "path": "/home/ofek/Downloads/codec_pack_setup.exe",
        "installer": "inno",
        "arch": "x86"
      }, undefined, 200.0);
      suite.send("guard.verdict", "jv-guard", {
        "sha256": pack,
        "verdict": "blocked",
        "reasons": ["clamav signature: Win.Adware.Bundler-7719234"],
        "scanned_by": ["clamav"],
        "path": "/home/ofek/Downloads/codec_pack_setup.exe"
      }, undefined, 200.4);
      // jv-compat's own word for the same refusal, on its own topic, in
      // the frame it really publishes (install.py: blocked, never a
      // prefix). InstallState passes it over: `blocked` is GuardPlate's
      // story, and treating it as news would take the failure below off
      // the screen.
      suite.send("compat.install", "jv-compat", {
        "event": "blocked",
        "app": "codec-pack",
        "sha256": pack,
        "error": "clamav signature: Win.Adware.Bundler-7719234"
      }, undefined, 200.4);

      // And the first install, fourteen seconds later, gets nowhere.
      suite.send("compat.install", "jv-compat", {
        "event": "failed",
        "app": "fl-studio",
        "sha256": fl,
        "error": "0009:err:mscoree:CLRRuntimeInfo_GetRuntimeHost Wine Mono is not installed"
      }, undefined, 214.0);

      // The heartbeat LAST, so the open microphone is as fresh as the
      // failure above it. Every other shot here lives at one instant; this
      // one spans three and a half minutes, and a heartbeat stamped at the
      // start of it would be 214 s stale by the end — which is a picture of
      // a jv-ears that stopped, not of a mic that is open.
      suite.micOpen();
    }

    // COMPOSED, and the first picture of the middle rung (A66). Until
    // jv-guard grew a shape engine (A64), `decide()` could only ever
    // return `clean` or `blocked` — so `GuardPlate`'s `warn` branch was a
    // colour with no producer, and a shot of it would have been a picture
    // of an intention rather than of anything this machine does.
    //
    // It has a producer now, and this is what it looks like: not malware.
    // A decade-old widescreen patch for a game, which its author ran UPX
    // over to make it one small download, in which ClamAV recognises
    // nothing at all — and which is shaped, byte for byte, exactly like
    // something hiding. That is the case the middle rung is FOR, and it is
    // also why the rung has to be a rung: `blocked` would be a lie about
    // this file and `clean` would be a promise nothing here can make.
    //
    // Every string in this frame is one services/jv-guard really produces
    // for a binary of this shape. tools/tests/test_hudshots.py builds a
    // UPX-shaped PE, runs the real `PEHeuristicScanner` and the real
    // `decide()` over it, and compares the verdict, the three reasons and
    // `scanned_by` to this literal — so the sentences photographed here
    // cannot drift away from the sentences jv-guard says.
    //
    // Those reasons reach NO pixel, and that is this plate's rule rather
    // than this shot's omission: `core/GuardState.qml` never reads
    // `reasons`, because schemas/guard.verdict.json says they are spoken
    // on request. What differs between this picture and 10-guard.png is
    // one word and one colour — `SUSPICIOUS` in `warn` where that one says
    // `BLOCKED` in `risk` — and what the colour is carrying is whether
    // anything can still be done about it. Today: not from here and not
    // from anywhere. The override goes through a confirmation flow nobody
    // has wired to this verdict yet (A65), so what you are looking at is
    // an install that stopped in front of a door with no handle on it.
    function shot_suspicious() {
      Bus.ingest('{"t":"link","up":true}');
      suite.micOpen();
      suite.send("guard.verdict", "jv-guard", {
        "sha256": "3ac10e7f5d92b48061c3fa2e7b5d0498f16a2c7d3e8b90154fa6c2d71e08b93f",
        "verdict": "suspicious",
        "reasons": [
          "pe-shape: executable section 'UPX0' has no bytes in the file but claims 512 KiB at run time (unpacks itself)",
          "pe-shape: executable section 'UPX1' is also writable (W+X: it can rewrite the code it runs)",
          "pe-shape: executable section 'UPX1' looks packed or encrypted: entropy 7.98 of a possible 8.00 over all of it"
        ],
        "scanned_by": ["clamav", "pe-shape"],
        "path": "/home/ofek/Downloads/nfs2se-widescreen-patch.exe"
      });
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
    //
    // `plates` is the CAPTION, asserted (A53). Until it existed the only
    // check here was `stack.anyLit` — something is on screen — and every
    // shot but the first one says `true`, so nine of the ten shots were
    // checked by exactly the same claim. Two plates in this stack draw the
    // same two lines in the same severity colour in the same corner, so a
    // wiring mistake that photographed the wrong one would have produced a
    // green run and a sheet whose README lies in a way only a person
    // looking at the picture could catch. These lists are read off the
    // plates themselves, in stack order, so the sheet now proves what it
    // is a picture OF and not merely that it is a picture of something.
    readonly property var sheet: [
      { "file": "01-quiet.png", "build": suite.shot_quiet, "plates": [] },
      { "file": "02-listening.png", "build": suite.shot_listening, "plates": ["state", "mic"] },
      { "file": "03-heard.png", "build": suite.shot_heard, "plates": ["state", "heard", "mic"] },
      { "file": "04-speaking.png", "build": suite.shot_speaking, "plates": ["state", "mic"] },
      { "file": "05-confirm.png", "build": suite.shot_confirm, "plates": ["confirm", "mic"] },
      { "file": "06-health.png", "build": suite.shot_health, "plates": ["mic", "health"] },
      // LinkState holds a 5 s grace before it will call the HUD blind — a
      // reconnecting bridge is not a lost machine — so this one settles
      // past that rather than photographing the silence in between.
      // `link` ALONE: every plate under it gates on the same bus it is
      // reporting the loss of, so the open microphone from a moment ago is
      // gone from the corner rather than left there as a stale claim about
      // the room. That is the whole argument of A23, and it was never
      // checked — only looked at.
      { "file": "07-no-bus.png", "build": suite.shot_nobus, "plates": ["link"], "settleMs": 6500 },
      { "file": "08-action.png", "build": suite.shot_action, "plates": ["action", "mic"] },
      { "file": "09-muted.png", "build": suite.shot_muted, "plates": ["state", "output", "mic"] },
      { "file": "10-guard.png", "build": suite.shot_guard, "plates": ["guard", "mic"] },
      // TWO frames, one plate: the `prefix_created` that precedes the
      // failure is an install RUNNING, which this stack deliberately does
      // not draw (A52 leaves the progress question to a human), so a
      // caption reading `install mic` and not `install install mic` is the
      // assertion that the happy path stayed invisible.
      { "file": "11-install.png", "build": suite.shot_install, "plates": ["install", "mic"] },
      // TWO stories, three plates (A61): the refused binary and the failed
      // install that the box grew to hold at the same time. Both halves of
      // invariant 8, in one corner, from the frames two services really
      // publish when two installs overlap.
      { "file": "12-guard-install.png", "build": suite.shot_guard_install, "plates": ["guard", "install", "mic"] },
      // The middle rung, photographed for the first time (A66): the same
      // element as 10-guard.png, one word and one colour apart, and
      // unreachable code until jv-guard grew something that could say
      // `suspicious` out loud.
      { "file": "13-suspicious.png", "build": suite.shot_suspicious, "plates": ["guard", "mic"] }
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

        // WHICH plates are in this picture, in reading order, as the
        // plates themselves report it (A53). A surface with nothing lit is
        // unmapped on a real machine, so a stack that lit nothing is
        // either the quiet shot or a harness that fed the plates something
        // they refused — and a stack that lit the WRONG plate looks, in a
        // PNG, almost exactly like one that lit the right one. Only this
        // line tells any of them apart.
        compare(stack.litNames.join(" "), shot.plates.join(" "),
                shot.file + ": the plates on screen");
        // And the property that actually maps the surface, which is a
        // second, cheaper implementation of the same fact. They agree here
        // or one of them is wrong.
        compare(stack.anyLit, shot.plates.length > 0, shot.file + ": stack.anyLit");

        // And it FITS. A stack taller than the surface is not a smaller
        // sheet — it is a plate the compositor cuts in half on a panel
        // floating over every window, and the only thing that had ever
        // checked it was a person looking at a PNG and seeing nothing
        // obviously wrong.
        //
        // This is the WEAK half of that check and always was: no shot here
        // lights more than three plates, so it clears the box by hundreds
        // of pixels and would pass on a HUD that crops the moment a fourth
        // arrives. tst_fit.qml next door is the strong half — every plate
        // that can be up at once, at its widest — and it found the box 41
        // px short (A63). What this line is for is the shots themselves:
        // each picture proves its own contents are whole.
        //
        // Same rule as tst_fit: an inset at the top AND at the bottom, the
        // edge gap §06 gives every side of this corner.
        verify(Theme.insetPx * 2 + stack.height <= root.height,
               shot.file + ": the corner is " + stack.height + " px tall, "
               + Theme.insetPx + " px down a " + root.height + " px surface");

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
