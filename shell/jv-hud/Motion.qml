// Motion — the HUD's permission to move, bound to its real sources (PLAN A7).
//
// The decision itself is next door in core/MotionPolicy.qml, where it is
// pure QtQuick and therefore tested. This file is the wiring: it hands the
// policy the preference a human actually set, and republishes the §06
// duration tokens with the gate already applied, so an element writes
//
//     Behavior on opacity { enabled: Motion.animate
//                           NumberAnimation { duration: Motion.easeMs } }
//
// or, for the common case, just `Ease on opacity {}` — and "motion off"
// stops being a rule every element has to remember. The durations are 0
// while motion is suppressed, so even an animation that forgot to check
// `animate` still cannot move the screen.
//
// Nothing here is a sensor: this is a preference and a machine state, never
// something the room is doing. Elements gate their MOTION on it, never their
// CONTENT — a still HUD must still tell the truth.
pragma Singleton

import QtQuick
import Quickshell
import "core"

Singleton {
  id: root

  // May the HUD animate at all? Gate `Behavior.enabled` and any standalone
  // animation's `running` on this: a disabled Behavior assigns straight
  // through, which costs zero frames rather than a zero-length animation.
  readonly property bool animate: policy.animate

  // Why motion is off ("" while it is on) — for a diagnostics readout, and
  // so "why did it go still?" has an answer that is not a guess.
  readonly property string suppressedBy: policy.suppressedBy

  // The §06 durations, already gated. Same names as the theme tokens on
  // purpose: reach for Motion.easeMs, not Theme.easeMs, whenever the number
  // is going to end up in an animation.
  readonly property int easeMs: policy.ms(Theme.easeMs)
  readonly property int fadeInMs: policy.ms(Theme.fadeInMs)
  readonly property int fadeOutMs: policy.ms(Theme.fadeOutMs)
  readonly property int pulseMs: policy.ms(Theme.pulseMs)

  // Gate any other duration (a per-element one, a fraction of a token)
  // through here, so it obeys the same switch.
  function ms(base: real): real {
    return policy.ms(base);
  }

  readonly property MotionPolicy policy: MotionPolicy {
    // The standing preference, versioned in personality/theme.toml.
    declaredReduced: Theme.reducedMotion
    // …and a per-session override for a machine you are sitting at right
    // now: JV_HUD_REDUCED_MOTION=1 to stop motion, =0 to force it back on.
    // Quickshell.env returns null when unset; the policy expects a string.
    envOverride: Quickshell.env("JV_HUD_REDUCED_MOTION") || ""
    // fullscreen/onBattery are left at false: no source publishes either
    // one yet (see core/MotionPolicy.qml). When one does, it binds here.
  }
}
