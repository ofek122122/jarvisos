// jv-wall — the JarvisOS animated wallpaper (blueprint §06).
//
// A layer-shell surface on the BACKGROUND layer of every monitor: the static
// instrument art underneath, with the small amount of motion §06 allows on top
// — the ember glow breathing, and the comet head drifting around its arc.
//
// WHY THIS IS STILL "EARNED EMPTINESS". §06 says motion should encode a signal
// and cost < 2 ms/frame with 0 fps when idle. A wallpaper has no signal to
// encode, so it gets the weakest possible motion: two long, slow cycles with no
// sharp edges, nothing that pulls the eye, and nothing that competes with the
// HUD's ember — the one accent that means "Jarvis is doing something". It is
// composed PER OUTPUT (the PNG is rendered at each monitor's own size, so
// nothing is cropped or stretched), and either switch below freezes it back to
// exactly the old static wallpaper.
//
// THE TWO SWITCHES, AND WHY NEITHER IS THE OTHER (PLAN E6). §06 says motion is
// off under prefers-reduced-motion, and this shell used to honour that NOWHERE:
// it read a `JV_MOTION` of its own and nothing else, so the versioned
// preference in personality/theme.toml and the session override every other
// shell obeys both left the glow breathing. `Motion` is that one desktop-wide
// gate — declared preference, JV_REDUCED_MOTION, and the machine states as
// sources appear behind it — and it is the reason this directory is a
// registered shell in tools/gen_theme_qml.py at all: a wallpaper with no
// vocabulary of its own still needs the switch, and the switch is generated.
// `JV_MOTION=0` stays as the NARROWER one: stop the wallpaper without telling
// the rest of the desktop to go still.
//
// Colour comes from the generated Theme singleton (invariant 9) like every
// other surface: the glow and the comet are `Theme.ember` at the alpha each
// one needs, so the accent that means "Jarvis is doing something" is the same
// colour here as in the HUD's corner by construction rather than by matching
// hex codes.
//
// Every id referenced from inside a Variants delegate is qualified, and
// ComponentBehavior: Bound makes those lookups lexical. The package lints this
// file with warnings-as-errors, so an unqualified access fails the build.
pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Wayland
import "."

ShellRoot {
  id: shell

  // May the wallpaper move? Both switches, and `Motion.animate` first because
  // it is the one §06 requires: a human who asked this machine for less motion
  // has already answered this question for every shell on it.
  readonly property bool motion: Motion.animate
                                 && Quickshell.env("JV_MOTION") !== "0"
  readonly property string wallDir: Quickshell.env("JV_WALL_DIR")

  Variants {
    model: Quickshell.screens

    PanelWindow {
      id: surface
      required property var modelData

      // The instrument sits at ~73.4% x 68.1% of the art; the motion is
      // anchored there so it sits inside the rings, not out on the desk.
      readonly property real ix: surface.width * 0.734
      readonly property real iy: surface.height * 0.681
      readonly property real ir: Math.min(surface.width, surface.height) * 0.39

      screen: surface.modelData
      WlrLayershell.layer: WlrLayer.Background
      WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
      WlrLayershell.exclusionMode: ExclusionMode.Ignore
      WlrLayershell.namespace: "jv-wall"
      focusable: false
      mask: Region {}

      // All four, spelled one per line like the other three shells: the
      // gate's parsers read this block, and a one-line form is a surface whose
      // anchors they read as none at all.
      anchors {
        top: true
        bottom: true
        left: true
        right: true
      }
      color: "transparent"

      // The per-output still, rendered at this monitor's exact geometry by
      // pkgs/jarvis-wallpaper — never scaled, never cropped.
      Image {
        id: still
        anchors.fill: parent
        source: "file://" + shell.wallDir + "/jarvisos-"
                + Math.round(surface.width) + "x" + Math.round(surface.height) + ".png"
        fillMode: Image.PreserveAspectCrop
        cache: true
        asynchronous: true
        // A geometry with no bespoke render falls back to the primary art
        // rather than showing nothing.
        onStatusChanged: {
          if (still.status === Image.Error)
            still.source = "file://" + shell.wallDir + "/jarvisos.png";
        }
      }

      // ---- the motion, all of it -------------------------------------------

      // 1. the ember glow, breathing (14 s round trip)
      Rectangle {
        id: glow
        x: surface.ix - surface.ir
        y: surface.iy - surface.ir
        width: surface.ir * 2
        height: surface.ir * 2
        radius: glow.width / 2
        visible: shell.motion
        opacity: 0.25
        // Ember, fading to the same ember at zero alpha rather than to
        // `transparent` — which is transparent BLACK, and interpolating to it
        // would drag a grey through the middle of the gradient.
        gradient: Gradient {
          GradientStop {
            position: 0.0
            color: Qt.rgba(Theme.ember.r, Theme.ember.g, Theme.ember.b, 0.10)
          }
          GradientStop {
            position: 1.0
            color: Qt.rgba(Theme.ember.r, Theme.ember.g, Theme.ember.b, 0.0)
          }
        }

        SequentialAnimation on opacity {
          running: shell.motion
          loops: Animation.Infinite
          NumberAnimation { to: 1.0; duration: 7000; easing.type: Easing.InOutSine }
          NumberAnimation { to: 0.25; duration: 7000; easing.type: Easing.InOutSine }
        }
      }

      // 2. the comet head, drifting around the outer ring (96 s per lap)
      Item {
        id: comet
        x: surface.ix
        y: surface.iy
        visible: shell.motion

        Rectangle {
          id: head
          width: 10
          height: 10
          radius: head.width / 2
          color: Theme.ember
          opacity: 0.85
          x: -head.width / 2
          y: -surface.ir - head.height / 2
        }

        RotationAnimation on rotation {
          running: shell.motion
          loops: Animation.Infinite
          from: 0
          to: 360
          duration: 96000 // drift, not spin
        }
      }
    }
  }
}
