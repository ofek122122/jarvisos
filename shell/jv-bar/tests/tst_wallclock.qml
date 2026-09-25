// WallClock — the two glyphs a bar shows, under test (PLAN D1).
//
// A clock is the one thing on this bar that is always true, which makes it
// the one element with no excuse for being wrong. The failures worth a test
// are small and all of the same kind — a reading that is not what the
// machine's clock says:
//
//   · 1:05 for five past one. A bar is read at a glance and a glance reads
//     COLUMNS; an hour that is sometimes one glyph and sometimes two moves
//     the minutes sideways every morning.
//   · 13:00 shown as 1:00. §06 spends no pixel on decoration and "PM" is
//     three of them; 24-hour is also the only reading that cannot be
//     misread, which is what a clock is for.
//   · a ticking second. Nothing on this machine is read to the second off a
//     bar, and a digit that changes 60 times a minute is 60 wakeups a
//     minute for a pixel nobody looked at — §06's 0 fps when idle is the
//     rule it breaks, and the reason the source is Quickshell's
//     SystemClock at Minutes precision rather than a Timer.
//   · 00:00 before the clock has been read. The bar starts before its
//     source does, and midnight is a real time: an unknown one has to be
//     unrepresentable rather than merely unlikely, or the bar will
//     confidently show the wrong one for as long as it takes to start.
import QtQuick
import QtTest
import "../core"

TestCase {
  id: suite
  name: "WallClock"

  Component {
    id: wallClock
    WallClock {}
  }

  function spawn(component) {
    const o = component.createObject(suite);
    verify(o, "failed to instantiate a test object");
    return o;
  }

  function at(h, m) {
    const c = spawn(wallClock);
    c.hours = h;
    c.minutes = m;
    return c.text;
  }

  function test_nothing_has_told_it_the_time_yet() {
    // Not "00:00". The bar maps before its clock source does, and the one
    // reading a clock must never give is a plausible wrong one.
    compare(spawn(wallClock).text, "");
  }

  function test_the_time_is_two_zero_padded_columns() {
    compare(suite.at(9, 5), "09:05");
    compare(suite.at(0, 0), "00:00");
    compare(suite.at(23, 59), "23:59");
  }

  function test_the_afternoon_is_the_afternoon_and_not_one_oclock() {
    compare(suite.at(13, 0), "13:00");
    compare(suite.at(12, 0), "12:00");
  }

  function test_there_are_no_seconds_in_it() {
    compare(suite.at(7, 7).length, 5);
  }

  function test_a_reading_off_the_clock_face_is_not_a_time() {
    // An hour of 24 or a minute of 60 is not a late evening, it is a source
    // this element does not understand. Drawing nothing is the only honest
    // thing left.
    compare(suite.at(24, 0), "");
    compare(suite.at(0, 60), "");
    compare(suite.at(-1, 30), "");
    compare(suite.at(10, -1), "");
    compare(suite.at(10.5, 30), "");
  }
}
