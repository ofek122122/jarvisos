// LinkState — "can the HUD still see the bus?", under test (PLAN A23).
//
// Every other element in this HUD is written to refuse: MicState will not
// say "off" when it cannot tell, SpeechState will not say "idle" from a bus
// it cannot see, ConfirmState drops a latched question the moment the link
// goes. All of those refusals reach the screen the same way — the plate
// draws NOTHING — and an empty corner is also what a quiet, healthy machine
// looks like. So the refusals are currently invisible, and the HUD's silence
// says two opposite things with the same pixels.
//
// This element is the difference between them, and the failures worth
// writing tests around are exactly the two ways it could be worse than
// nothing:
//
//   · a HUD that went blind and never said so — the mic could be open, the
//     whole point of the recording light, and the corner stays dark.
//   · a plate that cries wolf. The bridge respawns two seconds after a
//     crash, and reconnects half a second after jarvisd restarts; a warning
//     that blinks on every ordinary reconnect is one that gets ignored the
//     day it is true.
//
// Headless, like the rest of core/: LinkState is pure QtQuick and reads the
// link through core/BusModel, driven with the same JSON lines the bridge
// writes.
import QtQuick
import QtTest
import "../core"

TestCase {
  id: suite
  name: "LinkState"

  // Short enough that a test can outwait it, long enough that the timer is
  // genuinely armed and fires on its own rather than being read as expired.
  readonly property real graceS: 0.025

  Component {
    id: busModel
    BusModel {}
  }

  Component {
    id: linkState
    LinkState {}
  }

  // createObject() is typed QObject, so every member read on the result
  // would be `missing-property` to qmllint. Going through an untyped
  // helper keeps the file lint-clean at -W 0 (see tst_speechstate).
  function spawn(component) {
    const o = component.createObject(suite);
    verify(o, "failed to instantiate a test object");
    return o;
  }

  // opts: { up: true } to start from a live, subscribed link,
  //       { graceS: n } for a different wait,
  //       { bus: obj } to hand it something other than a BusModel.
  function makeLink(opts) {
    const o = opts || {};
    const link = spawn(linkState);
    link.graceS = o.graceS !== undefined ? o.graceS : suite.graceS;
    link.bus = o.bus !== undefined ? o.bus : spawn(busModel);
    if (o.up === true)
      suite.up(link);
    return link;
  }

  // The bridge saying it holds a live subscription.
  function up(link) {
    link.bus.ingest('{"t":"link","up":true}');
  }

  // ... and saying it does not, in its own words.
  function down(link, why) {
    link.bus.ingest(JSON.stringify({
      "t": "link",
      "up": false,
      "err": why === undefined ? "bridge stopped" : why
    }));
  }

  // --- the reason this element exists ----------------------------------

  function test_a_link_that_never_came_up_is_reported() {
    // The startup case, and the one that matters most: jarvisd is not
    // running, the bridge cannot connect, and every plate in this HUD is
    // silent because none of them knows anything. Silence there is not
    // "nothing is happening" — it is "I cannot see".
    const link = makeLink();
    verify(!link.blind, "a link gets its grace before anything is said");
    tryCompare(link, "blind", true, 1000, "a bus that never appeared must be reported");
  }

  function test_a_link_that_drops_after_working_is_reported() {
    const link = makeLink({
      "up": true
    });
    compare(link.blind, false);
    suite.down(link);
    tryCompare(link, "blind", true, 1000);
  }

  function test_a_missing_bus_is_blindness_not_an_exception() {
    // An element wired to nothing can see nothing. This should read as the
    // HUD's own failure, on screen, rather than as a quiet corner.
    const link = makeLink({
      "bus": null
    });
    tryCompare(link, "blind", true, 1000);
  }

  function test_a_bus_that_does_not_answer_linkup_is_not_taken_as_up() {
    // `linkUp === true`, never truthiness: a stand-in without the property
    // answers `undefined`, and "I did not say" must not read as "yes".
    const link = makeLink({
      "bus": ({
          "linkError": "no link property at all"
        })
    });
    tryCompare(link, "blind", true, 1000);
  }

  // --- the reason it waits ---------------------------------------------

  function test_an_ordinary_reconnect_never_reaches_the_screen() {
    // jv-hud-bridge retries 0.5 s after a link that worked drops, and
    // Bus.qml respawns the process itself two seconds after it dies. Both
    // are shorter than the grace on purpose: a warning that blinks every
    // time jarvisd restarts is a warning nobody reads.
    const link = makeLink({
      "up": true,
      "graceS": 0.4
    });
    suite.down(link);
    wait(60);
    compare(link.blind, false, "still inside the grace");
    suite.up(link);
    wait(600); // twice what was left of the grace
    compare(link.blind, false, "the link came back; nothing was ever wrong");
  }

  function test_a_recovered_link_stops_being_reported_at_once() {
    // A stale warning is the same lie as a stale sensor: the link is back,
    // the plates below can speak for themselves again, and this one has
    // nothing left to say.
    const link = makeLink();
    tryCompare(link, "blind", true, 1000);
    suite.up(link);
    compare(link.blind, false, "recovery is immediate, not on the next tick");
  }

  function test_the_drop_after_a_reported_outage_waits_its_own_grace() {
    // The wait is a property of THIS outage, not a latch that stays armed
    // once it has fired. jarvisd goes down for a minute and comes back;
    // the next ordinary blip must not inherit that verdict, or the plate
    // blinks on every restart from then on — the cry-wolf failure arriving
    // one outage later, which is when nobody is looking for it.
    const link = makeLink({
      "graceS": 0.3
    });
    tryCompare(link, "blind", true, 1000, "the first outage is reported");
    suite.up(link);
    compare(link.blind, false);
    suite.down(link);
    wait(100);
    compare(link.blind, false, "a fresh outage gets the whole grace again");
    tryCompare(link, "blind", true, 1000);
  }

  function test_a_bridge_retrying_in_a_loop_does_not_postpone_the_report() {
    // jv-hud-bridge does not say "down" once. It says it again on every
    // failed retry, with a fresh explanation each time and a backoff that
    // climbs to 8 s — so an element that restarted its wait whenever it
    // heard "down" would push the report past the outage that caused it
    // and, for the first few seconds, past its own grace forever.
    const link = makeLink({
      "graceS": 0.3
    });
    suite.down(link, "connect: attempt one");
    wait(250);
    compare(link.blind, false, "still inside the grace");
    suite.down(link, "connect: attempt two");
    wait(200); // 0.45 s since the outage began, 0.25 s since the last line
    compare(link.blind, true, "the wait belongs to the outage, not to the last line about it");
    compare(link.reason, "connect: attempt two", "and the newest explanation is the one shown");
  }

  function test_a_flapping_link_is_judged_on_its_current_outage() {
    const link = makeLink({
      "graceS": 0.4
    });
    for (let i = 0; i < 3; i++) {
      suite.up(link);
      suite.down(link);
      wait(60);
    }
    compare(link.blind, false, "no outage lasted the grace");
    suite.up(link);
    compare(link.blind, false);
  }

  function test_an_element_asked_nothing_is_already_timing_its_outage() {
    // What production builds: `LinkState { bus: Bus }` and not one property
    // more. `linked` is false from the first instant and STAYS false while
    // a bridge fails to connect, so no change signal ever fires for the
    // outage the HUD boots into — a machine where nothing is running at
    // all. Nothing else would notice: the element would sit there, correct
    // about everything it was asked, and never say the one thing it exists
    // to say.
    const link = spawn(linkState);
    compare(link.grace.running, true, "the wait starts when the element does");
    compare(link.grace.interval, Math.ceil(link.graceS * 1000));
  }

  // --- 0 fps when nothing is happening (§06) ----------------------------

  function test_a_live_link_runs_no_timer() {
    const link = makeLink({
      "up": true
    });
    compare(link.grace.running, false, "nothing to wait for while the link is up");
  }

  function test_a_reported_outage_runs_no_timer() {
    const link = makeLink();
    tryCompare(link, "blind", true, 1000);
    compare(link.grace.running, false, "the wait is over; there is nothing left to time");
  }

  function test_a_grace_that_cannot_be_waited_reports_immediately_data() {
    return [
      {
        "tag": "zero",
        "graceS": 0
      },
      {
        "tag": "negative",
        "graceS": -1
      }
    ];
  }

  function test_a_grace_that_cannot_be_waited_reports_immediately(data) {
    // Not a configuration anything ships with — it is the boundary the
    // arming code has to survive. `restart()` on a zero interval fires a
    // frame later and reads as a missed outage; a negative one is a wait
    // that can never elapse, which is the same as never reporting.
    const link = makeLink({
      "graceS": data.graceS
    });
    compare(link.blind, true);
    compare(link.grace.running, false);
  }

  // --- what it is allowed to say ----------------------------------------

  function test_nothing_is_said_about_a_link_that_is_merely_young() {
    // BusModel starts with linkError "starting". That is true and it is
    // not news; a plate must have nothing to draw until the outage has
    // earned the screen.
    const link = makeLink();
    compare(link.blind, false);
    compare(link.reason, "", "no reason before there is a report to reason about");
  }

  function test_the_reason_is_the_bridges_own_words() {
    // The bridge says why in the same line that says it is down —
    // "connect: ..." when jarvisd is not there, "bus closed the
    // connection" when it went away. That distinction is the whole value
    // of the second line, so it is passed through rather than summarised.
    const link = makeLink();
    suite.down(link, "connect: [Errno 2] No such file or directory");
    tryCompare(link, "blind", true, 1000);
    compare(link.reason, "connect: [Errno 2] No such file or directory");
  }

  function test_the_reason_carries_no_line_breaks_of_its_own() {
    // The label wraps on its own width. A newline from the bridge would
    // break the plate's layout instead of the sentence, and a tab would
    // open a hole in the middle of it.
    const link = makeLink();
    suite.down(link, "  link: connection\n  reset by peer\t ");
    tryCompare(link, "blind", true, 1000);
    compare(link.reason, "link: connection reset by peer");
  }

  function test_a_long_reason_is_clipped_and_says_so() {
    const link = makeLink();
    suite.down(link, "bus rejected us: " + "x".repeat(200));
    tryCompare(link, "blind", true, 1000);
    compare(link.reason.length, link.maxReasonChars);
    compare(link.reason.endsWith("…"), true, "a clipped reason must not read as a whole one");
    compare(link.reason.startsWith("bus rejected us: "), true);
  }

  function test_a_bus_with_no_reason_to_give_is_still_reported() {
    // The fact is the headline; the reason is the footnote. A bridge that
    // died without a word must not cost us the report.
    const link = makeLink({
      "bus": ({
          "linkUp": false
        })
    });
    tryCompare(link, "blind", true, 1000);
    compare(link.reason, "");
  }

  function test_a_non_string_reason_is_refused_rather_than_rendered() {
    // Refused by TYPE, not by truthiness: a number is truthy and has no
    // `.replace`, so a guard that merely checked for emptiness would throw
    // inside the binding — where the only symptom is a warning nobody
    // reads and a plate that quietly loses its second line.
    failOnWarning(/TypeError/);
    const link = makeLink({
      "bus": ({
          "linkUp": false,
          "linkError": 42
        })
    });
    tryCompare(link, "blind", true, 1000);
    compare(link.reason, "");
  }
}
