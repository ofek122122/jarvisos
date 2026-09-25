// Fade — the notifier's one way to make a value move (PLAN D2).
//
// §06 gives motion two rules that matter here: ease toward a target rather
// than snap, and stop entirely on `prefers-reduced-motion`. A toast is the
// one thing on this machine that appears and leaves on its own, so it is
// exactly the surface where a fade earns its frames: something arriving in a
// corner you were not looking at reads as an arrival rather than as a
// repaint. Nothing else in this shell moves at all.
//
// It is one component rather than a Behavior per element for the reason the
// HUD's `Ease` is one: the element that hand-rolls its own animation is the
// element that forgets the off switch, and it forgets it invisibly — a corner
// that still fades after a human asked for stillness. `tools/tests/
// test_gen_theme_qml.py` fails the build if any file in this shell animates
// without naming `Theme.reducedMotion`, which is what makes that one file.
//
// WHY THIS IS NOT THE HUD'S `Ease`. Ease reads `Motion`, a Quickshell
// singleton wrapping `core/MotionPolicy.qml`, which weighs the declared
// preference against a per-session override, a battery and a fullscreen
// window. This shell has the one input the others cannot drift from — the
// versioned preference in personality/theme.toml, reaching QML through the
// generated Theme — and copying MotionPolicy by hand into a third shell would
// be a second copy of a decision with nothing holding the two equal. PLAN
// D18 is the generator doing for the motion trio what it already does for
// Theme.qml, and when it lands this file becomes `Ease` and this paragraph
// goes away.
//
// With the preference set, `enabled` is false: QML assigns the value straight
// through, so stillness costs zero frames rather than a zero-length animation.
import QtQuick

Behavior {
  id: root

  // Which §06 duration this move takes. Default: the ease.
  property real base: Theme.easeMs

  enabled: !Theme.reducedMotion

  animation: PropertyAnimation {
    duration: root.base
    // Decelerate into the target: the value arrives without overshoot, which
    // reads as something settling rather than as an effect playing.
    easing.type: Easing.OutCubic
  }
}
