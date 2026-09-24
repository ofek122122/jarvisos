// Motion — the shot harness's stand-in for the HUD's motion singleton.
//
// STAGED OVER shell/jv-hud/Motion.qml for one reason only: the real one
// reads `Quickshell.env("JV_HUD_REDUCED_MOTION")`, and Quickshell cannot
// be imported by any engine but its own. Everything else is the real
// file — the same core/MotionPolicy.qml, handed the same declared
// preference out of personality/theme.toml — so a shot animates (or does
// not) for the reason the running HUD would.
//
// The per-session env override is fixed at "" here: a screenshot taken
// with a developer's shell variable in it would be a picture of that
// shell rather than of the declared look. The driver waits past the
// longest §06 duration before it grabs, so what lands in the PNG is the
// settled frame either way.
pragma Singleton

import QtQuick
import "core"

Item {
  id: root

  readonly property bool animate: root.policy.animate
  readonly property string suppressedBy: root.policy.suppressedBy

  readonly property int easeMs: root.policy.ms(Theme.easeMs)
  readonly property int fadeInMs: root.policy.ms(Theme.fadeInMs)
  readonly property int fadeOutMs: root.policy.ms(Theme.fadeOutMs)
  readonly property int pulseMs: root.policy.ms(Theme.pulseMs)

  function ms(base: real): real {
    return root.policy.ms(base);
  }

  readonly property MotionPolicy policy: MotionPolicy {
    declaredReduced: Theme.reducedMotion
    envOverride: ""
  }
}
