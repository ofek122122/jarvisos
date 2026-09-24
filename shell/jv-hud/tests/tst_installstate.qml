// InstallState — "the app that did not get installed", under test
// (PLAN A52).
//
// This is the second element to read jv-compat's half of invariant 8 (the
// first was GuardState, which reads the screener), and the first to read a
// LIFECYCLE rather than a verdict: six events on one topic, of which
// exactly one is news. So the failures worth writing tests around are
// mostly about which of the other five is silence and which is an
// all-clear:
//
//   · reporting progress. `fingerprinted`, `screened` and `prefix_created`
//     are an install running, which is the thing this element deliberately
//     does not draw (A52 leaves the progress question to a human) — and
//     they must also CLEAR a held failure, because the last install
//     attempted is now a different one.
//   · reporting `blocked` as a failure of its own. GuardPlate already
//     draws that refusal from the screener's own frame; two plates for one
//     event is the HUD saying the same thing twice. It must not create a
//     plate and must not clear one either.
//   · drawing the installer's own stdout. `error` on a failed frame is 500
//     bytes written by an untrusted Windows binary; a test here asserts
//     the element does not even offer it.
//   · believing a slug that is not one. The schema calls `app` a prefix
//     directory name, and a "directory name" with a newline or a slash in
//     it would be drawn as whatever the publisher sent.
//
// Headless, like the rest of core/: InstallState is pure QtQuick and reads
// the bus through core/BusModel, driven with the same JSON lines
// jv-hud-bridge writes.
import QtQuick
import QtTest
import "../core"

TestCase {
  id: suite
  name: "InstallState"

  // The stand-in for CLOCK_MONOTONIC. Every frame is delivered at its own
  // `ts` so it lands zero seconds old; winding this forward is how the
  // backstop is made to fire without waiting for it.
  property real fakeNow: 0

  // A real sha256 shape: 64 lowercase hex. Long enough that the 12-digit
  // prefix this element shows is a prefix of something.
  readonly property string sha: "9f2c4b7a1e08d3c65a4fbe2170d9c8815b3e6a04f7d2c9b81e5a30f64c7b92d1"

  // A second installer, for the tests about one install replacing another.
  readonly property string otherSha: "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

  Component {
    id: busModel
    BusModel {}
  }

  Component {
    id: installState
    InstallState {}
  }

  // createObject() is typed QObject, so every member read on the result
  // would be `missing-property` to qmllint. Going through an untyped
  // helper keeps the file lint-clean at -W 0 (see tst_speechstate).
  function spawn(component) {
    const o = component.createObject(suite);
    verify(o, "failed to instantiate a test object");
    return o;
  }

  // An InstallState on a live, subscribed link, with a clock we drive.
  // opts: { holdS: n } for a different backstop,
  //       { down: true } to leave the link down,
  //       { bus: obj } to hand it something other than a BusModel.
  function makeInstall(opts) {
    const o = opts || {};
    suite.fakeNow = 0;
    const s = spawn(installState);
    if (o.holdS !== undefined)
      s.holdS = o.holdS;
    s.bus = o.bus !== undefined ? o.bus : spawn(busModel);
    if (o.bus === undefined && o.down !== true) {
      s.bus.monotonic = () => suite.fakeNow;
      s.bus.ingest('{"t":"link","up":true}');
    }
    return s;
  }

  // --- building the frames the bridge would write ----------------------

  property int nextSeq: 0

  function envelope(topic, ts, conf, body, extra) {
    const e = extra || {};
    return {
      "topic": topic,
      "ts": ts,
      "seq": e.seq !== undefined ? e.seq : suite.nextSeq++,
      "src": e.src !== undefined ? e.src : "jv-compat",
      "conf": conf,
      "v": e.v !== undefined ? e.v : 1,
      "body": body
    };
  }

  function deliver(s, env) {
    if (typeof env.ts === "number")
      suite.fakeNow = Math.max(suite.fakeNow, env.ts);
    s.bus.ingest(JSON.stringify({
      "t": "frame",
      "frame": env
    }));
  }

  // jv-compat saying where an install has got to. opts: { app, sha256,
  // error, path, recipe, ts, conf, v, seq, noTs, drop: [fields],
  // noApp: true }.
  function stage(s, event, opts) {
    const o = opts || {};
    let body = {
      "event": event,
      "sha256": o.sha256 !== undefined ? o.sha256 : suite.sha
    };
    if (o.noApp !== true)
      body.app = o.app !== undefined ? o.app : "notepad-plus-plus";
    if (o.error !== undefined)
      body.error = o.error;
    if (o.path !== undefined)
      body.path = o.path;
    if (o.recipe !== undefined)
      body.recipe = o.recipe;
    if (o.drop !== undefined)
      for (let i = 0; i < o.drop.length; i++)
        delete body[o.drop[i]];
    const env = suite.envelope("compat.install", o.ts !== undefined ? o.ts : suite.fakeNow, o.conf !== undefined ? o.conf : 1, body, o);
    if (o.noTs === true)
      delete env.ts;
    deliver(s, env);
    return env;
  }

  // --- the ordinary failure ---------------------------------------------

  function test_nothing_is_shown_before_anything_has_been_installed() {
    const s = makeInstall();
    compare(s.failed, false, "an empty corner is what a machine nobody installs anything on looks like");
    compare(s.app, "");
    compare(s.fingerprint, "");
  }

  function test_a_failed_install_names_the_app_and_carries_the_hash() {
    const s = makeInstall();
    stage(s, "failed", {
      "error": "wine: Unhandled page fault on read access"
    });
    compare(s.failed, true);
    compare(s.app, "notepad-plus-plus", "the prefix directory name, which is also what you would type to try again");
    compare(s.fingerprint, "9f2c4b7a1e08", "the first 12 hex, the identity jv-guard logs");
  }

  function test_the_newest_failure_replaces_the_one_before_it() {
    const s = makeInstall();
    stage(s, "failed");
    suite.fakeNow = 3;
    stage(s, "failed", {
      "app": "irfanview",
      "sha256": suite.otherSha
    });
    compare(s.failed, true);
    compare(s.app, "irfanview");
    compare(s.fingerprint, "0123456789ab");
  }

  // --- the five events that are not news ---------------------------------

  function test_an_install_that_is_merely_running_draws_nothing() {
    // §06's earned emptiness, and A52's open question left open: an
    // install takes MINUTES, "what is jv-compat doing right now" may well
    // deserve a progress indicator, and that is a shape for a human to
    // decide on rather than one to arrive at by accident.
    const s = makeInstall();
    const running = ["fingerprinted", "screened", "prefix_created"];
    for (let i = 0; i < running.length; i++) {
      suite.fakeNow = i;
      stage(s, running[i]);
      compare(s.failed, false, running[i] + " put a plate on screen");
      compare(s.app, "");
    }
  }

  function test_an_install_that_worked_draws_nothing() {
    // The app being on the machine is the report that it installed —
    // ActionPlate's argument (A37) applied to jv-compat.
    const s = makeInstall();
    stage(s, "installed");
    compare(s.failed, false);
  }

  function test_a_later_install_starting_takes_an_earlier_failure_off_the_screen() {
    // This element reports the LAST install attempted. A `fingerprinted`
    // is the user handing jv-compat a different binary, so the failure
    // being held is no longer what this machine is doing.
    const s = makeInstall();
    stage(s, "failed");
    compare(s.failed, true);
    suite.fakeNow = 60;
    stage(s, "fingerprinted", {
      "app": "irfanview",
      "sha256": suite.otherSha,
      "path": "/home/ofek/Downloads/iview.exe"
    });
    compare(s.failed, false, "a newer install under way is newer news");
    compare(s.app, "");
  }

  function test_a_retry_that_worked_takes_the_failure_off_the_screen() {
    // The same rule ActionState applies to a tool: holding a failure under
    // a retry that succeeded describes a machine that is not the one in
    // front of you.
    const s = makeInstall();
    stage(s, "failed");
    suite.fakeNow = 120;
    stage(s, "installed");
    compare(s.failed, false);
  }

  // --- the refusal is somebody else's plate -------------------------------

  function test_a_blocked_install_is_not_this_elements_news() {
    // GuardPlate (A51) draws the refusal from jv-guard's own
    // `guard.verdict`, joined to this lifecycle by the same sha256. Two
    // plates for one refusal would be the HUD saying the same thing twice
    // in two vocabularies.
    const s = makeInstall();
    stage(s, "blocked", {
      "error": "matched ClamAV signature Win.Trojan.Agent"
    });
    compare(s.failed, false);
    compare(s.app, "");
  }

  function test_a_blocked_install_does_not_clear_a_real_failure_either() {
    // ActionState's rule for the confirmation outcomes it declines: an
    // event this element passes over is NO NEWS, never an all-clear.
    const s = makeInstall();
    stage(s, "failed");
    compare(s.failed, true);
    suite.fakeNow = 30;
    stage(s, "blocked", {
      "app": "irfanview",
      "sha256": suite.otherSha,
      "error": "screening unavailable — refusing to install (fail closed)"
    });
    compare(s.failed, true, "a refusal took a real failure off the screen");
    compare(s.app, "notepad-plus-plus", "and it changed the app while it was at it");
  }

  // --- the installer's own words are not ours to draw ---------------------

  function test_the_element_does_not_even_offer_the_installers_output() {
    // `compat.install.error` on a failed frame is the last 500 bytes of a
    // confined Windows installer's stdout — free text written by the one
    // thing invariant 8 says outright is untrusted, and likely carrying
    // paths out of this filesystem. A plate cannot draw what its element
    // does not expose, so this is the gate, not a rule about pixels
    // somewhere else.
    const s = makeInstall();
    stage(s, "failed", {
      "error": "C:\\users\\ofek\\AppData: access denied",
      "path": "/home/ofek/Downloads/npp.8.6.Installer.x64.exe"
    });
    compare(s.failed, true);
    compare(typeof s.error, "undefined", "the installer's stdout is exposed to the HUD");
    compare(typeof s.detail, "undefined", "the installer's stdout is exposed to the HUD");
    compare(typeof s.path, "undefined", "the user's filesystem is exposed to the HUD");
  }

  // --- the slug, believed only if it looks like one -----------------------

  function test_a_slug_with_a_separator_in_it_is_not_a_directory_name() {
    // jv-compat builds this out of a file name chosen by whoever built the
    // installer. Its own sieve would never emit this; a frame is what it
    // is, and the HUD trusts no publisher's sanitising.
    const s = makeInstall();
    stage(s, "failed", {
      "app": "../../etc/notepad"
    });
    compare(s.failed, true, "the install still failed and must still be reported");
    compare(s.app, "", "a path was drawn as an app name");
    compare(s.fingerprint, "9f2c4b7a1e08", "and it fell back to the hash");
  }

  function test_a_newline_in_a_slug_cannot_make_the_plate_taller() {
    const s = makeInstall();
    stage(s, "failed", {
      "app": "notepad\nplus"
    });
    compare(s.app, "");
    compare(s.fingerprint, "9f2c4b7a1e08");
  }

  function test_a_bidirectional_override_is_not_part_of_an_app_name() {
    // The trick GuardState sanitises a FILE name against: a name that
    // renders as something other than what it is. Here it is refused
    // outright rather than scrubbed — see the next test.
    const s = makeInstall();
    stage(s, "failed", {
      "app": "setup\u202Eexe.bat"
    });
    compare(s.app, "");
  }

  function test_a_slug_that_had_to_be_repaired_is_not_drawn_at_all() {
    // The difference from GuardState, and the reason this element sieves
    // rather than sanitises: a file NAME is a thing to look at, so
    // stripping the invisible characters out of one still leaves the name
    // its author typed. A slug is an IDENTIFIER — the prefix directory,
    // the thing you would type to try again — and a repaired identifier is
    // another app's name. The hash is the honest substitute.
    const s = makeInstall();
    stage(s, "failed", {
      "app": "note pad"
    });
    compare(s.app, "", "a slug with a space in it was drawn as one");
    compare(s.fingerprint, "9f2c4b7a1e08");
  }

  function test_an_absurdly_long_slug_is_refused_rather_than_truncated() {
    // Half a slug is another app's name. The plate elides on WIDTH as
    // well — that is what a reader sees — but what the element is willing
    // to BELIEVE is a directory name is capped here.
    const s = makeInstall();
    let long = "";
    for (let i = 0; i < 12; i++)
      long += "notepad-";
    stage(s, "failed", {
      "app": long
    });
    compare(s.app, "");
    compare(s.fingerprint, "9f2c4b7a1e08");
  }

  function test_a_slug_exactly_at_the_cap_is_kept_whole() {
    const s = makeInstall();
    let name = "";
    for (let i = 0; i < 40; i++)
      name += "a";
    stage(s, "failed", {
      "app": name
    });
    compare(s.app, name, "a slug at the cap was refused for being at it");
  }

  function test_the_shapes_a_package_name_is_really_made_of_are_kept() {
    // Deliberately wider than jv-compat's own `[a-z0-9-]`: this element is
    // written against the schema (a prefix directory name), not against
    // one publisher's regex, and a recipe naming `python3.11_x64` must not
    // be reported as a hash.
    const s = makeInstall();
    const names = ["notepad-plus-plus", "python3.11", "vc_redist.x64", "7zip", "foo+bar"];
    for (let i = 0; i < names.length; i++) {
      suite.fakeNow = i;
      stage(s, "failed", {
        "app": names[i]
      });
      compare(s.app, names[i]);
    }
  }

  function test_a_failure_with_no_app_at_all_is_still_reported() {
    // `app` is required by the schema, so this is a frame that should not
    // exist — but an install that failed is news whether or not the HUD
    // can name it, which is ActionState's rule for an outcome it cannot
    // attribute to a tool.
    const s = makeInstall();
    stage(s, "failed", {
      "noApp": true
    });
    compare(s.failed, true);
    compare(s.app, "");
    compare(s.fingerprint, "9f2c4b7a1e08");
  }

  // --- the fingerprint ----------------------------------------------------

  function test_the_fingerprint_is_lowercased_so_two_reports_read_alike() {
    const s = makeInstall();
    stage(s, "failed", {
      "app": "no slug here",
      "sha256": suite.sha.toUpperCase()
    });
    compare(s.fingerprint, "9f2c4b7a1e08");
  }

  function test_a_hash_that_is_not_hex_is_not_shortened_into_something_it_is_not() {
    // A truncated something-else looks exactly like a sha256 prefix, and
    // would be the one identity on this plate that cannot be looked up.
    const s = makeInstall();
    stage(s, "failed", {
      "app": "no slug here",
      "sha256": "not-a-hash-at-all-but-long-enough-to-slice"
    });
    compare(s.failed, true, "the install still failed");
    compare(s.fingerprint, "");
  }

  // --- frames we refuse to read ------------------------------------------

  function test_an_install_frame_from_a_newer_schema_is_refused() {
    // Invariant 2: a v2 body is not a v1 body, and guessing at one is how
    // a HUD reports fields that have moved.
    const s = makeInstall();
    stage(s, "failed", {
      "v": 2
    });
    compare(s.failed, false);
  }

  function test_a_hedged_install_frame_is_refused() {
    // schemas/compat.install.json fixes conf at 1.0: an installer either
    // exited non-zero or it did not (invariant 4).
    const s = makeInstall();
    stage(s, "failed", {
      "conf": 0.6
    });
    compare(s.failed, false);
  }

  function test_an_install_frame_with_no_timestamp_is_refused() {
    // Without a `ts` there is no age, so there is no backstop — and a line
    // the HUD cannot time is one it would hold forever.
    const s = makeInstall();
    stage(s, "failed", {
      "noTs": true
    });
    compare(s.failed, false);
  }

  function test_an_install_frame_with_no_hash_is_refused() {
    // The hash is required by the schema and is the installer's identity.
    // A frame without one could not be attributed to anything.
    const s = makeInstall();
    stage(s, "failed", {
      "drop": ["sha256"]
    });
    compare(s.failed, false);
  }

  function test_a_frame_that_does_not_say_which_stage_it_is_is_refused() {
    // Honest about what this proves: `event` is required by the schema and
    // is checked with the hash, in the envelope floor — but deleting that
    // half of the check does NOT fail this test, because `apply()` acts on
    // an allow-list and a missing event matches nothing in it. The
    // OUTCOME is pinned here; the check itself is belt to that braces, and
    // the same reasoning is why there is no "is that a word I know" gate
    // at all (see core/InstallState.qml).
    const s = makeInstall();
    stage(s, "failed", {
      "drop": ["event"]
    });
    compare(s.failed, false);
  }

  function test_an_event_outside_the_enum_is_neither_a_failure_nor_progress() {
    // A publisher inventing `rolled_back` must not put a word on screen
    // that nobody can look up — and must not read as progress either,
    // which would silently clear a real failure.
    const s = makeInstall();
    stage(s, "failed");
    compare(s.failed, true);
    suite.fakeNow = 2;
    stage(s, "rolled_back", {
      "app": "irfanview",
      "sha256": suite.otherSha
    });
    compare(s.failed, true, "an unreadable frame took a real failure off the screen");
    compare(s.app, "notepad-plus-plus", "and it changed the app while it was at it");
  }

  function test_an_unreadable_frame_is_not_progress_on_its_own() {
    const s = makeInstall();
    stage(s, "failed");
    suite.fakeNow = 2;
    stage(s, "installed", {
      "v": 2
    });
    compare(s.failed, true, "refusing to read a frame is not being told the install worked");
  }

  // --- a bus the HUD cannot see -------------------------------------------

  function test_nothing_is_shown_while_the_link_is_down() {
    const s = makeInstall({
      "down": true
    });
    stage(s, "failed");
    compare(s.failed, false);
  }

  function test_the_link_dropping_forgets_the_failure() {
    const s = makeInstall();
    stage(s, "failed");
    compare(s.failed, true);
    s.bus.ingest('{"t":"link","up":false}');
    compare(s.failed, false);
    compare(s.app, "");
  }

  function test_a_reconnect_does_not_put_back_a_failure_nobody_republished() {
    // The difference between forgetting and merely not reporting: while
    // the link is down `failed` is false either way, and only a
    // RECONNECT can tell the two apart. A failure that comes back when
    // the pipe does is a claim about a machine nothing has re-examined.
    const s = makeInstall();
    stage(s, "failed");
    s.bus.ingest('{"t":"link","up":false}');
    s.bus.ingest('{"t":"link","up":true}');
    compare(s.failed, false, "a reconnect resurrected a failure nothing republished");
    compare(s.app, "");
  }

  function test_a_bus_that_is_not_a_bus_is_simply_quiet() {
    const s = makeInstall({
      "bus": {}
    });
    compare(s.failed, false);
    compare(s.app, "");
  }

  // --- the backstop --------------------------------------------------------

  function test_a_failure_leaves_on_its_own_after_the_hold() {
    // Nothing else ends an install: the trigger is a terminal command, so
    // there is no spoken explanation coming and no newer event unless
    // somebody installs something else. Without this the line would sit in
    // the corner until the next reboot.
    const s = makeInstall({
      "holdS": 30
    });
    stage(s, "failed");
    compare(s.failed, true);
    wait(0);
    compare(s.hold.running, true, "nothing is timing the line");
    compare(s.hold.interval, 30000, "the whole window, for a frame that arrived fresh");
  }

  function test_a_failure_that_spent_its_window_in_flight_arrives_expired() {
    // `ageOf` is what is LEFT of the window, not the whole of it. The
    // on-time frame first is not decoration: BusModel learns the offset
    // between envelope `ts` and its own clock from the frames themselves,
    // converging from below, so until something has arrived promptly
    // everything looks fresh. It is also the honest shape of the real
    // case — this HUD sees the early stages of an install arrive on time
    // and one late `failed`.
    const s = makeInstall({
      "holdS": 5
    });
    stage(s, "fingerprinted", {
      "ts": 0
    });
    suite.fakeNow = 20;
    stage(s, "failed", {
      "ts": 0
    });
    compare(s.failed, false, "a line older than its own window went on screen");
  }

  function test_the_backstop_is_rearmed_by_each_new_failure() {
    const s = makeInstall({
      "holdS": 8
    });
    stage(s, "failed");
    suite.fakeNow = 4;
    stage(s, "failed", {
      "app": "irfanview",
      "sha256": suite.otherSha
    });
    wait(0);
    compare(s.hold.interval, 8000, "the second failure inherited what was left of the first one's window");
  }

  function test_no_timer_runs_while_there_is_nothing_to_show() {
    // §06: 0 fps when nothing is happening. An armed timer here would be a
    // wakeup per interval on every machine that installs nothing, which is
    // this machine on almost every day.
    const s = makeInstall();
    wait(0);
    compare(s.hold.running, false);
    stage(s, "failed");
    wait(0);
    compare(s.hold.running, true);
    suite.fakeNow = 3;
    stage(s, "installed");
    wait(0);
    compare(s.hold.running, false, "the timer outlived the line it was timing");
  }

  function test_the_hold_can_be_shortened_and_the_line_really_goes() {
    // The one test that lets a real timer fire, so the exit is proven by
    // the clock rather than by reading `hold.interval`.
    const s = makeInstall({
      "holdS": 0.05
    });
    stage(s, "failed");
    compare(s.failed, true);
    tryCompare(s, "failed", false, 2000, "the failure never left the screen");
    compare(s.app, "");
    compare(s.fingerprint, "");
  }
}
