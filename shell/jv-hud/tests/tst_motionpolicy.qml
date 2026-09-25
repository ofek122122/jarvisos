// MotionPolicy — the HUD's permission to move, under test (PLAN A7).
//
// The thing worth defending here is the negative case. Motion that fails to
// start is obvious; motion that fails to STOP is the bug you ship, because
// the machine that asked for stillness is not the machine you develop on.
// So most of these tests are about suppression: that every §06 condition
// silences everything, that the reason is reported honestly, that a gated
// duration really is zero, and — the one that would rot silently — that
// `animate` is a live binding rather than a value read once at startup.
import QtQuick
import QtTest
import "../core"

TestCase {
  id: suite
  name: "MotionPolicy"

  Component {
    id: motionPolicy
    MotionPolicy {}
  }

  function make(props) {
    const policy = motionPolicy.createObject(suite, props || {});
    verify(policy, "MotionPolicy failed to instantiate");
    return policy;
  }

  // What an element actually does with this object: bind to it. A binding
  // re-evaluates only if the property it reads is a real notifying one, so
  // this catches a `animate` that got computed once and frozen. The null
  // guard reports -1/"?" so a test that forgets to attach reads as broken
  // rather than as "motion off".
  QtObject {
    id: watcher

    property var source: null
    readonly property int animate: watcher.source ? (watcher.source.animate ? 1 : 0) : -1
    readonly property string reason: watcher.source ? watcher.source.suppressedBy : "?"
  }

  // --- the default: a machine that asked for nothing gets motion ---------

  function test_animates_by_default() {
    const p = make();
    verify(p.animate, "no suppressing condition means motion is allowed");
    compare(p.suppressedBy, "");
    compare(p.prefersReduced, false);
  }

  function test_durations_pass_through_while_animating() {
    const p = make();
    compare(p.ms(200), 200);
    compare(p.ms(1600), 1600);
    // `ms` declares a real parameter, so QML converts before the function
    // sees it. Written down because it is the reason the guard below tests
    // values rather than types.
    compare(p.ms("200"), 200);
  }

  // --- suppression: each §06 condition, and what it says about itself ----

  function test_declared_preference_stops_everything() {
    const p = make({
      "declaredReduced": true
    });
    verify(!p.animate, "theme.toml asked for no motion");
    compare(p.suppressedBy, "reduced-motion");
    compare(p.ms(200), 0);
  }

  function test_battery_stops_everything() {
    const p = make({
      "onBattery": true
    });
    verify(!p.animate);
    compare(p.suppressedBy, "battery");
    compare(p.ms(200), 0);
  }

  function test_fullscreen_stops_everything() {
    const p = make({
      "fullscreen": true
    });
    verify(!p.animate);
    compare(p.suppressedBy, "fullscreen");
    compare(p.ms(200), 0);
  }

  function test_the_users_own_wish_is_the_reason_it_names() {
    // Several conditions at once: the one a human asked for is reported.
    const p = make({
      "declaredReduced": true,
      "onBattery": true,
      "fullscreen": true
    });
    compare(p.suppressedBy, "reduced-motion");
  }

  function test_machine_conditions_are_reported_in_order() {
    const p = make({
      "onBattery": true,
      "fullscreen": true
    });
    compare(p.suppressedBy, "battery");
  }

  // --- the environment override: exactly two strings mean anything ------

  function test_env_forces_reduced_motion_on() {
    const p = make({
      "declaredReduced": false,
      "envOverride": "1"
    });
    verify(p.prefersReduced, "JV_REDUCED_MOTION=1 overrides the token");
    compare(p.suppressedBy, "reduced-motion");
  }

  function test_env_forces_reduced_motion_off() {
    const p = make({
      "declaredReduced": true,
      "envOverride": "0"
    });
    verify(!p.prefersReduced, "JV_REDUCED_MOTION=0 overrides the token");
    verify(p.animate);
  }

  function test_env_zero_does_not_override_the_machine() {
    // "let it move" is a statement about the preference, not a licence to
    // animate while a fullscreen window or a battery says otherwise.
    const p = make({
      "declaredReduced": true,
      "envOverride": "0",
      "onBattery": true
    });
    verify(!p.animate);
    compare(p.suppressedBy, "battery");
  }

  function test_unset_env_defers_to_the_token_data() {
    return [
      {
        tag: "unset",
        env: ""
      },
      {
        tag: "true",
        env: "true"
      },
      {
        tag: "yes",
        env: "yes"
      },
      {
        tag: "on",
        env: "on"
      },
      {
        tag: "01",
        env: "01"
      },
      {
        tag: "spaced",
        env: " 1"
      }
    ];
  }

  function test_unset_env_defers_to_the_token(row) {
    // Anything that is not exactly "1" or "0" is not an answer, so the
    // declared preference stands — in both directions.
    const off = make({
      "declaredReduced": false,
      "envOverride": row.env
    });
    verify(off.animate, row.tag + " should leave the token alone");
    const on = make({
      "declaredReduced": true,
      "envOverride": row.env
    });
    verify(!on.animate, row.tag + " should leave the token alone");
  }

  // --- gated durations ---------------------------------------------------

  function test_a_nonsense_duration_is_zero_data() {
    return [
      {
        tag: "negative",
        base: -1
      },
      {
        tag: "zero",
        base: 0
      },
      {
        tag: "nan",
        base: NaN
      },
      {
        tag: "undefined",
        base: undefined
      },
      {
        tag: "not-a-number",
        base: "cat"
      },
      {
        tag: "null",
        base: null
      }
    ];
  }

  function test_a_nonsense_duration_is_zero(row) {
    const p = make();
    compare(p.ms(row.base), 0, row.tag + " is not a duration");
  }

  // --- the binding: this is the one that would rot quietly ---------------

  function test_elements_see_the_change_live() {
    const p = make();
    watcher.source = p;
    compare(watcher.animate, 1, "motion is on to begin with");
    compare(watcher.reason, "");

    p.declaredReduced = true;
    compare(watcher.animate, 0, "turning the preference on must reach bindings");
    compare(watcher.reason, "reduced-motion");

    p.declaredReduced = false;
    compare(watcher.animate, 1, "and turning it back off must too");
    compare(watcher.reason, "");

    p.fullscreen = true;
    compare(watcher.animate, 0);
    compare(watcher.reason, "fullscreen");
    p.fullscreen = false;

    p.envOverride = "1";
    compare(watcher.animate, 0, "the env override is live as well");
    watcher.source = null;
  }
}
