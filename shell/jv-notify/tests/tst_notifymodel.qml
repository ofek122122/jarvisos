// NotifyModel — the notification corner's lifecycle, under test (PLAN D2).
//
// A notification daemon is the one surface on this machine that draws text a
// stranger chose. Every process with a D-Bus session can call Notify(), and
// none of them is trusted — so the failures worth writing tests around are
// not "does a toast appear" but the ways a sender could take the corner:
//
//   · expire_timeout = 0 means "never expire" in the freedesktop spec. Taken
//     literally it is a one-line way for any process to pin a plate over
//     your work for the rest of the session.
//   · a dwell of 5 ms, which flashes a plate nobody can read and leaves the
//     corner jittering.
//   · an unbounded number of notifications, which is a corner that grows
//     until it covers the screen — on a surface that takes no input, so
//     there is nothing a human could click to stop it.
//   · an urgency byte that is none of the three values, which must not read
//     as critical and must not blank the plate.
//   · a summary with three hundred newlines in it.
//
// And two that are the daemon's own mistake rather than a sender's: a plate
// that outlives the notification behind it (it was withdrawn and the corner
// still shows it), and a plate that never leaves because nothing armed a
// timer for it.
//
// Headless, like every core/ suite: NotifyModel is pure QtQuick and the clock
// is injected, so time is wound by hand and nothing here waits.
import QtQuick
import QtTest
import "../core"

TestCase {
  id: suite
  name: "NotifyModel"

  // A stand-in for CLOCK_MONOTONIC, in seconds, that the test drives.
  property real fakeNow: 0

  Component {
    id: notifyModel
    NotifyModel {}
  }

  // createObject() is typed QObject, so every member read on the result would
  // be `missing-property` to qmllint. Going through an untyped helper keeps
  // this file lint-clean at -W 0 (the same trick the HUD's suites use).
  function spawn(component) {
    const o = component.createObject(suite);
    verify(o, "failed to instantiate a test object");
    return o;
  }

  // opts: { clock: false } to withhold the monotonic clock entirely.
  function makeModel(opts) {
    const o = opts || {};
    suite.fakeNow = 0;
    const model = spawn(notifyModel);
    if (o.clock !== false)
      model.monotonic = () => suite.fakeNow;
    return model;
  }

  // A sender, as the server half hands one over. `fields` overrides anything.
  function sent(key, fields) {
    const f = fields || {};
    const record = {
      "key": key,
      "appName": f.appName === undefined ? "Thunar" : f.appName,
      "summary": f.summary === undefined ? "Copy finished" : f.summary,
      "body": f.body === undefined ? "" : f.body,
      "urgency": f.urgency === undefined ? 1 : f.urgency,
      "timeoutMs": f.timeoutMs === undefined ? -1 : f.timeoutMs,
      "handle": f.handle === undefined ? null : f.handle
    };
    return record;
  }

  // A stand-in for the Quickshell Notification object: the model may call
  // `expire()` on it and may read nothing else. The count goes through a
  // closure rather than `this`, because inside a QML method `this` is the
  // TestCase — so `this.expired` is a member of the wrong object, and the
  // linter says so at -W 0, which is a failed build.
  function fakeHandle() {
    const handle = {
      "expired": 0
    };
    handle.expire = () => {
      handle.expired++;
    };
    return handle;
  }

  // --- nothing at all ---------------------------------------------------

  function test_an_empty_corner_is_unmapped_and_runs_no_timer() {
    const model = makeModel();
    compare(model.anyLit, false);
    compare(model.toasts.length, 0);
    compare(model.earlier, 0);
    compare(model.expiry.running, false, "a corner with nothing in it must run no timer");
  }

  function test_a_record_with_no_key_is_not_a_notification() {
    const model = makeModel();
    model.push(null);
    model.push(undefined);
    model.push({
      "summary": "no key"
    });
    compare(model.anyLit, false, "something with no key could never be found again or closed");
  }

  // --- what a plate says ------------------------------------------------

  function test_a_notification_arrives_with_the_senders_own_words() {
    const model = makeModel();
    model.push(sent("1", {
      "appName": "Thunar",
      "summary": "Copy finished",
      "body": "4 files to /home/ofek"
    }));
    compare(model.anyLit, true);
    compare(model.toasts.length, 1);
    compare(model.toasts[0].appName, "Thunar");
    compare(model.toasts[0].summary, "Copy finished");
    compare(model.toasts[0].body, "4 files to /home/ofek");
  }

  function test_whitespace_a_sender_formatted_for_a_dialog_is_collapsed() {
    const model = makeModel();
    model.push(sent("1", {
      "summary": "  Copy\n\tfinished  ",
      "body": "line one\n\nline two\n"
    }));
    compare(model.toasts[0].summary, "Copy finished");
    compare(model.toasts[0].body, "line one line two");
  }

  function test_a_field_a_sender_left_out_is_empty_and_not_undefined() {
    const model = makeModel();
    model.push({
      "key": "1"
    });
    compare(model.toasts[0].appName, "");
    compare(model.toasts[0].summary, "");
    compare(model.toasts[0].body, "");
    compare(model.toasts[0].urgency, model.urgencyNormal);
  }

  function test_an_urgency_that_is_none_of_the_three_is_normal() {
    const model = makeModel();
    compare(model.normalUrgency(0), model.urgencyLow);
    compare(model.normalUrgency(1), model.urgencyNormal);
    compare(model.normalUrgency(2), model.urgencyCritical);
    compare(model.normalUrgency(7), model.urgencyNormal, "7 must not read as critical");
    compare(model.normalUrgency(-1), model.urgencyNormal);
    compare(model.normalUrgency("critical"), model.urgencyNormal);
    compare(model.normalUrgency(undefined), model.urgencyNormal);
  }

  // --- how long one stays -----------------------------------------------

  function test_an_undeclared_timeout_gets_the_dwell_for_its_urgency() {
    const model = makeModel();
    compare(model.dwellMsFor(model.urgencyLow, -1), model.lowDwellMs);
    compare(model.dwellMsFor(model.urgencyNormal, -1), model.normalDwellMs);
    // Anything unreadable in that field is the same as not asking.
    compare(model.dwellMsFor(model.urgencyNormal, undefined), model.normalDwellMs);
    compare(model.dwellMsFor(model.urgencyNormal, NaN), model.normalDwellMs);
    compare(model.dwellMsFor(model.urgencyNormal, Infinity), model.normalDwellMs);
  }

  function test_a_sender_that_asks_for_forever_does_not_get_it() {
    const model = makeModel();
    // expire_timeout = 0 is "never expire" in the spec. Honoured literally it
    // is a D-Bus call that pins a plate over your work for the session.
    compare(model.dwellMsFor(model.urgencyNormal, 0), model.maxDwellMs);
    compare(model.dwellMsFor(model.urgencyLow, 0), model.maxDwellMs);
  }

  function test_a_declared_dwell_is_honoured_between_the_floor_and_the_ceiling() {
    const model = makeModel();
    compare(model.dwellMsFor(model.urgencyNormal, 3000), 3000);
    compare(model.dwellMsFor(model.urgencyNormal, 5), model.minDwellMs, "a plate gone before it is read wasted the corner");
    compare(model.dwellMsFor(model.urgencyNormal, 600000), model.maxDwellMs, "ten minutes is not a sender's to take");
  }

  function test_only_critical_stays_until_its_sender_withdraws_it() {
    const model = makeModel();
    compare(model.dwellMsFor(model.urgencyCritical, -1), 0);
    compare(model.dwellMsFor(model.urgencyCritical, 500), 0, "critical ignores a sender's short timeout too");

    model.push(sent("1", {
      "urgency": 2
    }));
    compare(model.toasts[0].deadline, 0, "0 is the deadline that never comes");
    suite.fakeNow = 60 * 60;
    model.sweep();
    compare(model.toasts.length, 1, "an hour later, a critical notification is still on screen");
  }

  function test_a_dwell_that_runs_out_takes_the_plate_and_closes_the_notification() {
    const model = makeModel();
    const handle = fakeHandle();
    model.push(sent("1", {
      "timeoutMs": 2000,
      "handle": handle
    }));
    compare(model.toasts[0].deadline, 2, "two seconds on the injected clock");

    suite.fakeNow = 1.9;
    model.sweep();
    compare(model.toasts.length, 1, "still inside its dwell");

    suite.fakeNow = 2.0;
    model.sweep();
    compare(model.toasts.length, 0);
    compare(handle.expired, 1, "the sender must be told its notification expired");
  }

  function test_the_one_timer_is_armed_for_the_soonest_deadline() {
    const model = makeModel();
    model.push(sent("slow", {
      "timeoutMs": 10000
    }));
    compare(model.expiry.running, true);
    compare(model.expiry.interval, 10000);

    model.push(sent("quick", {
      "timeoutMs": 2000
    }));
    compare(model.expiry.interval, 2000, "the timer must wake for whichever leaves first");

    // …and once the soonest is gone, for the one behind it.
    suite.fakeNow = 2;
    model.sweep();
    compare(model.toasts.length, 1);
    compare(model.expiry.interval, 8000);
  }

  function test_a_critical_notification_arms_no_timer() {
    const model = makeModel();
    model.push(sent("1", {
      "urgency": 2
    }));
    compare(model.expiry.running, false, "nothing to wake up for");
  }

  function test_with_no_clock_nothing_expires_on_its_own() {
    const model = makeModel({
      "clock": false
    });
    const handle = fakeHandle();
    model.push(sent("1", {
      "timeoutMs": 2000,
      "handle": handle
    }));
    compare(model.toasts.length, 1);
    compare(model.toasts[0].deadline, 0, "no clock, no deadline — never a guessed one");
    compare(model.expiry.running, false);
    model.sweep();
    compare(model.toasts.length, 1, "a corner that cannot time itself keeps what it was given");
    compare(handle.expired, 0, "and tells no sender its notification ended");
  }

  // --- the cap ----------------------------------------------------------

  function test_past_the_cap_the_newest_are_shown_and_the_rest_are_counted() {
    const model = makeModel();
    for (let i = 1; i <= 5; i++)
      model.push(sent("" + i, {
        "summary": "note " + i
      }));

    compare(model.maxVisible, 3);
    compare(model.toasts.length, 3);
    // Oldest-first within what is shown: a bottom-anchored column then puts
    // the newest nearest the corner.
    compare(model.toasts[0].summary, "note 3");
    compare(model.toasts[1].summary, "note 4");
    compare(model.toasts[2].summary, "note 5");
    compare(model.earlier, 2, "the two older ones are counted, not forgotten");
  }

  function test_the_ones_past_the_cap_still_expire() {
    const model = makeModel();
    const first = fakeHandle();
    model.push(sent("1", {
      "timeoutMs": 2000,
      "handle": first
    }));
    for (let i = 2; i <= 4; i++)
      model.push(sent("" + i, {
        "timeoutMs": 10000
      }));
    compare(model.earlier, 1, "the first one is off screen now");

    suite.fakeNow = 2;
    model.sweep();
    compare(model.earlier, 0);
    compare(model.toasts.length, 3);
    compare(first.expired, 1, "a notification nobody could see still ended on time");
  }

  // --- replacement, and withdrawal --------------------------------------

  function test_a_sender_reusing_an_id_updates_one_plate_in_place() {
    const model = makeModel();
    model.push(sent("dl", {
      "summary": "Downloading 40%"
    }));
    model.push(sent("other", {
      "summary": "Mail"
    }));
    suite.fakeNow = 1;
    model.push(sent("dl", {
      "summary": "Downloading 80%",
      "timeoutMs": 4000
    }));

    compare(model.toasts.length, 2, "an update is one story, not a second one");
    compare(model.toasts[0].summary, "Downloading 80%");
    compare(model.toasts[1].summary, "Mail", "and it keeps its place in the stack");
    compare(model.toasts[0].deadline, 5, "its dwell starts again: the news is fresh");
  }

  function test_a_notification_its_sender_withdraws_leaves_the_corner() {
    const model = makeModel();
    const handle = fakeHandle();
    model.push(sent("1", {
      "handle": handle
    }));
    model.push(sent("2"));
    model.drop("1");
    compare(model.toasts.length, 1);
    compare(model.toasts[0].key, "2");
    compare(handle.expired, 0, "a notification that is already closed must not be closed again");
  }

  function test_dropping_something_that_was_never_here_changes_nothing() {
    const model = makeModel();
    model.push(sent("1", {
      "timeoutMs": 3000
    }));
    const armed = model.expiry.interval;
    model.drop("nope");
    compare(model.toasts.length, 1);
    compare(model.expiry.interval, armed);
  }

  function test_clearing_forgets_everything_and_closes_nothing() {
    const model = makeModel();
    const handle = fakeHandle();
    model.push(sent("1", {
      "timeoutMs": 3000,
      "handle": handle
    }));
    model.clear();
    compare(model.anyLit, false);
    compare(model.expiry.running, false);
    compare(handle.expired, 0);
  }
}
