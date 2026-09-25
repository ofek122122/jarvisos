// GuardState — "this machine refused to run a program", under test
// (PLAN A51).
//
// This is the first element that reads jv-guard, and the first one whose
// text was written by somebody hostile: invariant 8 says a Windows binary
// is untrusted by default, and the file NAME is part of the binary. So the
// failures worth writing tests around are a different set from the rest of
// core/:
//
//   · drawing a name as the installer's author typed it. A Linux file name
//     may carry newlines (a plate three lines tall, over every window), a
//     bidirectional override (a name that renders as `setup.bat` and is
//     not), or four kilobytes of nothing. `plainName()` is the whole
//     answer and it is the most-tested function in this file.
//   · reporting a clean file. Every screening would light the corner, and
//     a corner that is busy is one nobody reads on the day it matters.
//   · holding a refusal after a later screening said something else, or
//     dropping one because a frame was odd in a way that has nothing to do
//     with the verdict.
//   · putting a scanner's `reasons` on screen. The schema says those are
//     "spoken on request"; a test here asserts this element does not even
//     offer them.
//
// Headless, like the rest of core/: GuardState is pure QtQuick and reads
// the bus through core/BusModel, driven with the same JSON lines
// jv-hud-bridge writes.
import QtQuick
import QtTest
import "../core"

TestCase {
  id: suite
  name: "GuardState"

  // The stand-in for CLOCK_MONOTONIC. Every frame is delivered at its own
  // `ts` so it lands zero seconds old; winding this forward is how the
  // backstop is made to fire without waiting for it.
  property real fakeNow: 0

  // A real sha256 shape: 64 lowercase hex. Long enough that the 12-digit
  // prefix this element shows is a prefix of something.
  readonly property string sha: "9f2c4b7a1e08d3c65a4fbe2170d9c8815b3e6a04f7d2c9b81e5a30f64c7b92d1"

  Component {
    id: busModel
    BusModel {}
  }

  Component {
    id: guardState
    GuardState {}
  }

  // createObject() is typed QObject, so every member read on the result
  // would be `missing-property` to qmllint. Going through an untyped
  // helper keeps the file lint-clean at -W 0 (see tst_speechstate).
  function spawn(component) {
    const o = component.createObject(suite);
    verify(o, "failed to instantiate a test object");
    return o;
  }

  // A GuardState on a live, subscribed link, with a clock we drive.
  // opts: { holdS: n } for a different backstop,
  //       { down: true } to leave the link down,
  //       { bus: obj } to hand it something other than a BusModel.
  function makeGuard(opts) {
    const o = opts || {};
    suite.fakeNow = 0;
    const g = spawn(guardState);
    if (o.holdS !== undefined)
      g.holdS = o.holdS;
    g.bus = o.bus !== undefined ? o.bus : spawn(busModel);
    if (o.bus === undefined && o.down !== true) {
      g.bus.monotonic = () => suite.fakeNow;
      g.bus.ingest('{"t":"link","up":true}');
    }
    return g;
  }

  // --- building the frames the bridge would write ----------------------

  property int nextSeq: 0

  function envelope(topic, ts, conf, body, extra) {
    const e = extra || {};
    return {
      "topic": topic,
      "ts": ts,
      "seq": e.seq !== undefined ? e.seq : suite.nextSeq++,
      "src": e.src !== undefined ? e.src : "jv-guard",
      "conf": conf,
      "v": e.v !== undefined ? e.v : 1,
      "body": body
    };
  }

  function deliver(g, env) {
    if (typeof env.ts === "number")
      suite.fakeNow = Math.max(suite.fakeNow, env.ts);
    g.bus.ingest(JSON.stringify({
      "t": "frame",
      "frame": env
    }));
  }

  // jv-guard saying what it made of a binary. opts: { path, sha256,
  // reasons, scanned_by, ts, conf, v, seq, noTs, noPath, drop: [fields] }.
  function screened(g, verdict, opts) {
    const o = opts || {};
    let body = {
      "sha256": o.sha256 !== undefined ? o.sha256 : suite.sha,
      "verdict": verdict,
      "reasons": o.reasons !== undefined ? o.reasons : [],
      "scanned_by": ["clamav"]
    };
    if (o.noPath !== true)
      body.path = o.path !== undefined ? o.path : "/home/ofek/Downloads/setup.exe";
    if (o.drop !== undefined)
      for (let i = 0; i < o.drop.length; i++)
        delete body[o.drop[i]];
    const env = suite.envelope("guard.verdict", o.ts !== undefined ? o.ts : suite.fakeNow, o.conf !== undefined ? o.conf : 1, body, o);
    if (o.noTs === true)
      delete env.ts;
    deliver(g, env);
    return env;
  }

  // --- the ordinary refusal --------------------------------------------

  function test_nothing_is_shown_before_anything_has_been_screened() {
    const g = makeGuard();
    compare(g.refused, false, "an empty corner is what a machine nobody hands binaries to looks like");
    compare(g.verdict, "");
    compare(g.file, "");
    compare(g.fingerprint, "");
  }

  function test_a_blocked_binary_names_the_verdict_the_file_and_the_hash() {
    const g = makeGuard();
    screened(g, "blocked", {
      "reasons": ["matched ClamAV signature Win.Trojan.Agent"]
    });
    compare(g.refused, true);
    compare(g.verdict, "blocked", "the screener's own word out of the frozen enum");
    compare(g.file, "setup.exe", "the file's own name, without the directory");
    compare(g.fingerprint, "9f2c4b7a1e08", "the first 12 hex, the identity jv-guard logs");
  }

  function test_a_suspicious_binary_is_shown_too_and_says_which_it_is() {
    // `suspicious` may be overridden through the confirmation flow and
    // `blocked` may not, so the two are different news and the plate must
    // be able to tell them apart.
    const g = makeGuard();
    screened(g, "suspicious", {
      "reasons": ["packer entropy anomaly"]
    });
    compare(g.refused, true);
    compare(g.verdict, "suspicious");
  }

  function test_a_clean_binary_is_not_news() {
    // §06's earned emptiness. jv-compat going on to build a prefix is the
    // report that the file passed; a plate per screening is a corner that
    // lights up for every install and is unread on the day one is refused.
    const g = makeGuard();
    screened(g, "clean");
    compare(g.refused, false);
    compare(g.verdict, "");
    compare(g.file, "");
  }

  function test_a_later_clean_screening_takes_an_earlier_refusal_off_the_screen() {
    // This element reports the LAST binary screened. Holding a refusal
    // under a later screening would describe a machine that is not the one
    // in front of you — ActionState's rule about a retry that worked.
    const g = makeGuard();
    screened(g, "blocked");
    compare(g.refused, true);
    suite.fakeNow = 5;
    screened(g, "clean", {
      "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
      "path": "/home/ofek/Downloads/other.exe"
    });
    compare(g.refused, false, "a newer screening is newer news");
  }

  function test_the_newest_refusal_replaces_the_one_before_it() {
    const g = makeGuard();
    screened(g, "suspicious");
    suite.fakeNow = 3;
    screened(g, "blocked", {
      "sha256": "aaaabbbbcccc0011223344556677889900112233445566778899aabbccddeeff",
      "path": "/tmp/dropper.exe"
    });
    compare(g.refused, true);
    compare(g.verdict, "blocked");
    compare(g.file, "dropper.exe");
    compare(g.fingerprint, "aaaabbbbcccc");
  }

  function test_the_hash_changing_under_the_screener_is_a_refusal_like_any_other() {
    // jv-guard's own dropper case: the file changed between fingerprint
    // and screening, which it publishes as `blocked` with no engine having
    // run. The HUD must show it — this is the most alarming verdict the
    // topic carries — and it is a frame with an empty `scanned_by`.
    const g = makeGuard();
    const env = suite.envelope("guard.verdict", suite.fakeNow, 1, {
      "sha256": suite.sha,
      "verdict": "blocked",
      "reasons": ["file hash changed between fingerprint and screening"],
      "scanned_by": [],
      "path": "/home/ofek/Downloads/setup.exe"
    });
    deliver(g, env);
    compare(g.refused, true);
    compare(g.verdict, "blocked");
    compare(g.file, "setup.exe");
  }

  // --- the reasons are not ours to draw --------------------------------

  function test_the_element_does_not_even_offer_the_scanners_reasons() {
    // schemas/guard.verdict.json says the reasons are "spoken on request",
    // and they are the one field on this topic whose text comes from a
    // scanner rather than from a frozen enum. A plate cannot draw what its
    // element does not expose, so this is the gate — not a rule about
    // pixels somewhere else.
    const g = makeGuard();
    screened(g, "blocked", {
      "reasons": ["matched ClamAV signature Win.Trojan.Agent", "packer entropy anomaly"]
    });
    compare(g.refused, true);
    compare(typeof g.reasons, "undefined", "the scanner's text is exposed to the HUD");
    compare(typeof g.reason, "undefined", "the scanner's text is exposed to the HUD");
  }

  // --- the name, made safe to draw -------------------------------------

  function test_only_the_file_name_is_kept_never_the_directory() {
    const g = makeGuard();
    screened(g, "blocked", {
      "path": "/mnt/share/games/Setup Deluxe Edition.exe"
    });
    compare(g.file, "Setup Deluxe Edition.exe", "spaces inside a name are part of the name");
  }

  function test_a_path_with_no_slash_is_already_a_name() {
    const g = makeGuard();
    screened(g, "blocked", {
      "path": "setup.exe"
    });
    compare(g.file, "setup.exe");
  }

  function test_a_newline_in_a_name_cannot_make_the_plate_taller() {
    // A newline is a legal character in a Linux file name and this plate
    // is sized for one line, on a surface that is on top of every window.
    const g = makeGuard();
    screened(g, "blocked", {
      "path": "/tmp/setup\n\nEXTRA LINE.exe"
    });
    compare(g.file, "setup EXTRA LINE.exe", "every run of whitespace collapses to one space");
    compare(g.file.indexOf("\n"), -1);
  }

  function test_a_tab_is_whitespace_like_any_other() {
    const g = makeGuard();
    screened(g, "blocked", {
      "path": "/tmp/setup\t\tfinal.exe"
    });
    compare(g.file, "setup final.exe");
  }

  function test_a_bidirectional_override_cannot_disguise_what_the_file_is() {
    // U+202E flips the rendering of everything after it, which is how
    // `setup<U+202E>exe.bat` appears on screen as `setup.bat` while being a
    // .exe. It exists for no other purpose here.
    const g = makeGuard();
    screened(g, "blocked", {
      "path": "/tmp/setup\u202Eexe.bat"
    });
    compare(g.file, "setupexe.bat", "the override survived into the drawn name");
    compare(g.file.charCodeAt(5), "e".charCodeAt(0));
  }

  function test_zero_width_characters_are_not_part_of_a_name() {
    const g = makeGuard();
    screened(g, "blocked", {
      "path": "/tmp/se\u200Btup\u2060.exe"
    });
    compare(g.file, "setup.exe");
  }

  function test_a_control_character_never_reaches_a_text_item() {
    const g = makeGuard();
    screened(g, "blocked", {
      "path": "/tmp/setup\u0007\u001B[31m.exe"
    });
    compare(g.file, "setup[31m.exe", "the bell and the escape are gone, the printable rest is not");
  }

  function test_a_name_made_entirely_of_invisible_characters_is_no_name() {
    // Nothing is left to draw, so this falls back to the hash rather than
    // to an empty bright line that looks like a rendering bug.
    const g = makeGuard();
    screened(g, "blocked", {
      "path": "/tmp/\u200B\u200B\u0001"
    });
    compare(g.file, "");
    compare(g.fingerprint, "9f2c4b7a1e08", "with no name, the hash is the identity");
  }

  function test_a_path_that_is_a_directory_leaves_no_name() {
    const g = makeGuard();
    screened(g, "blocked", {
      "path": "/home/ofek/Downloads/"
    });
    compare(g.file, "");
    compare(g.refused, true, "the refusal itself is still news");
  }

  function test_an_absurdly_long_name_is_capped_by_the_element_not_by_the_plate() {
    // Eliding is about what a reader sees; this is about what the element
    // is willing to carry at all, so a megabyte of name is not a megabyte
    // of string being measured on every frame.
    const g = makeGuard();
    let name = "";
    for (let i = 0; i < 400; i++)
      name += "a";
    screened(g, "blocked", {
      "path": "/tmp/" + name + ".exe"
    });
    compare(g.file.length, 64);
    compare(g.file, name.slice(0, 64));
  }

  function test_a_name_exactly_at_the_cap_is_kept_whole() {
    const g = makeGuard();
    let name = "";
    for (let i = 0; i < 64; i++)
      name += "b";
    screened(g, "blocked", {
      "path": "/tmp/" + name
    });
    compare(g.file, name);
  }

  // --- the fingerprint --------------------------------------------------

  function test_a_frame_with_no_path_is_still_reported_by_its_hash() {
    // `path` is optional in the schema. A refusal with no name is still a
    // refusal, and the hash is the one substitute a reader can look up.
    const g = makeGuard();
    screened(g, "blocked", {
      "noPath": true
    });
    compare(g.refused, true);
    compare(g.file, "");
    compare(g.fingerprint, "9f2c4b7a1e08");
  }

  function test_the_fingerprint_is_lowercased_so_two_reports_read_alike() {
    const g = makeGuard();
    screened(g, "blocked", {
      "sha256": "9F2C4B7A1E08D3C65A4FBE2170D9C8815B3E6A04F7D2C9B81E5A30F64C7B92D1"
    });
    compare(g.fingerprint, "9f2c4b7a1e08");
  }

  function test_a_hash_that_is_not_hex_is_not_shortened_into_something_it_is_not() {
    // A truncated something-else looks exactly like a sha256 prefix, and
    // would be the one identity on this plate nobody can go and check.
    const g = makeGuard();
    screened(g, "blocked", {
      "sha256": "not-a-hash-at-all",
      "noPath": true
    });
    compare(g.refused, true, "the refusal is still news without an identity");
    compare(g.fingerprint, "");
  }

  function test_a_hash_too_short_to_shorten_is_left_alone() {
    const g = makeGuard();
    screened(g, "blocked", {
      "sha256": "9f2c4b7a",
      "noPath": true
    });
    compare(g.fingerprint, "");
  }

  // --- frames we refuse to read ----------------------------------------

  function test_a_verdict_from_a_newer_schema_is_refused() {
    // Invariant 2: a v2 body is not a v1 body, and guessing at one is how
    // a HUD reports fields that have moved.
    const g = makeGuard();
    screened(g, "blocked", {
      "v": 2
    });
    compare(g.refused, false);
  }

  function test_a_hedged_verdict_is_refused() {
    // schemas/guard.verdict.json fixes conf at 1.0: a scanner either
    // matched or it did not, and a verdict that is unsure of itself is not
    // one jv-guard publishes (invariant 4).
    const g = makeGuard();
    screened(g, "blocked", {
      "conf": 0.7
    });
    compare(g.refused, false);
  }

  function test_a_verdict_with_no_timestamp_is_refused() {
    // Without a `ts` there is no age, so there is no backstop — and a line
    // the HUD cannot time is one it would hold forever.
    const g = makeGuard();
    screened(g, "blocked", {
      "noTs": true
    });
    compare(g.refused, false);
  }

  function test_a_verdict_with_no_hash_is_refused() {
    // The hash is required by the schema and is the file's identity. A
    // frame without one could not be attributed to anything.
    const g = makeGuard();
    screened(g, "blocked", {
      "drop": ["sha256"]
    });
    compare(g.refused, false);
  }

  function test_a_frame_that_does_not_say_what_it_decided_is_refused() {
    const g = makeGuard();
    screened(g, "blocked", {
      "drop": ["verdict"]
    });
    compare(g.refused, false);
  }

  function test_a_word_outside_the_enum_is_neither_a_refusal_nor_an_all_clear() {
    // A publisher inventing `quarantined` must not put a word on screen
    // that nobody can look up — and must not read as "clean" either,
    // which would silently clear a real refusal.
    const g = makeGuard();
    screened(g, "blocked");
    compare(g.refused, true);
    suite.fakeNow = 2;
    screened(g, "quarantined", {
      "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    });
    compare(g.refused, true, "an unreadable frame took a real refusal off the screen");
    compare(g.verdict, "blocked", "and it changed the word while it was at it");
  }

  function test_an_unreadable_frame_is_not_an_all_clear_on_its_own() {
    const g = makeGuard();
    screened(g, "suspicious");
    suite.fakeNow = 2;
    screened(g, "clean", {
      "v": 2
    });
    compare(g.refused, true, "refusing to read a frame is not being told the file was fine");
  }

  // --- a bus the HUD cannot see ----------------------------------------

  function test_nothing_is_shown_while_the_link_is_down() {
    const g = makeGuard({
      "down": true
    });
    compare(g.refused, false);
  }

  function test_the_link_dropping_forgets_the_refusal() {
    // Every element in this HUD drops what it cached on a dropped link: a
    // line latched off a bus we can no longer see describes a machine we
    // can no longer see (invariant 10).
    const g = makeGuard();
    screened(g, "blocked");
    compare(g.refused, true);
    g.bus.ingest('{"t":"link","up":false,"err":"connect: No such file or directory"}');
    compare(g.refused, false);
    compare(g.verdict, "");
    compare(g.file, "");
  }

  function test_a_reconnect_does_not_put_back_a_refusal_nobody_republished() {
    // The half of the dropped link that `refused` alone cannot show: it is
    // already false while the link is down, so an element that merely
    // stopped REPORTING the refusal would look identical here — until the
    // bridge reconnects, BusModel comes back with an empty cache, and the
    // latch that was never let go of puts a verdict back on screen that
    // nothing on the bus is saying any more.
    const g = makeGuard();
    screened(g, "blocked");
    compare(g.refused, true);
    g.bus.ingest('{"t":"link","up":false,"err":"connect: No such file or directory"}');
    compare(g.refused, false);
    g.bus.ingest('{"t":"link","up":true}');
    compare(g.refused, false, "the bus came back and the HUD re-asserted a verdict nobody republished");
    compare(g.verdict, "");
    compare(g.file, "");
  }

  function test_a_bus_that_is_not_a_bus_is_simply_quiet() {
    // Bus.qml forwards a handful of functions; a stand-in that forwards
    // none must make this element quiet rather than make it throw inside a
    // binding, where the symptom is a warning nobody reads.
    const g = makeGuard({
      "bus": {
        "linkUp": true
      }
    });
    compare(g.refused, false);
    compare(g.file, "");
  }

  // --- the backstop ----------------------------------------------------

  function test_a_refusal_leaves_on_its_own_after_the_hold() {
    // Nothing else ends a screening: the trigger is a terminal command, so
    // there is no spoken explanation coming and no newer verdict unless
    // somebody installs something else. Without this the line would sit in
    // the corner until the next reboot.
    const g = makeGuard({
      "holdS": 30
    });
    screened(g, "blocked");
    compare(g.refused, true);
    wait(0);
    compare(g.hold.running, true, "nothing is timing the line");
    compare(g.hold.interval, 30000, "the whole window, for a frame that arrived fresh");
  }

  function test_a_refusal_that_spent_its_window_in_flight_arrives_expired() {
    // `ageOf` is what is LEFT of the window, not the whole of it: a frame
    // that took longer than the hold to reach the HUD is news about a
    // screening that is already over.
    //
    // The clean screening first is not decoration. BusModel learns the
    // difference between envelope `ts` and its own clock from the frames
    // themselves, converging from below, so until SOME frame has arrived
    // promptly there is no age to compute and everything looks fresh —
    // its documented behaviour, and the reason a test about lateness needs
    // something on time in front of it. It is also the honest shape of the
    // real case: this HUD sees jv-guard's clean verdicts all day and one
    // late refusal.
    const g = makeGuard({
      "holdS": 5
    });
    screened(g, "clean", {
      "ts": 0
    });
    suite.fakeNow = 20;
    screened(g, "blocked", {
      "ts": 0,
      "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    });
    compare(g.refused, false, "a line older than its own window went on screen");
  }

  function test_the_backstop_is_rearmed_by_each_new_refusal() {
    const g = makeGuard({
      "holdS": 8
    });
    screened(g, "suspicious");
    suite.fakeNow = 4;
    screened(g, "blocked", {
      "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    });
    wait(0);
    compare(g.hold.interval, 8000, "the second refusal inherited what was left of the first one's window");
  }

  function test_no_timer_runs_while_there_is_nothing_to_show() {
    // §06: 0 fps when nothing is happening. This is the rarest plate in
    // the stack — it needs somebody to hand Jarvis a Windows binary AND a
    // scanner to object to it — so an armed timer here would be a wakeup
    // per interval on a machine that installs nothing.
    const g = makeGuard();
    wait(0);
    compare(g.hold.running, false);
    screened(g, "blocked");
    wait(0);
    compare(g.hold.running, true);
    suite.fakeNow = 3;
    screened(g, "clean", {
      "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    });
    wait(0);
    compare(g.hold.running, false, "the timer outlived the line it was timing");
  }

  function test_the_hold_can_be_shortened_and_the_line_really_goes() {
    // The one test that lets a real timer fire, so the exit is proven by
    // the clock rather than by reading `hold.interval`.
    const g = makeGuard({
      "holdS": 0.05
    });
    screened(g, "blocked");
    compare(g.refused, true);
    tryCompare(g, "refused", false, 2000, "the refusal never left the screen");
    compare(g.verdict, "");
    compare(g.file, "");
    compare(g.fingerprint, "");
  }
}
