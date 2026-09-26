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

      // WHERE THE ART LANDED, which is not always this surface (PLAN E9). Under
      // `PreserveAspectCrop` Qt scales the drawing until it covers the item and
      // centres it, so `paintedWidth`/`paintedHeight` are the size of the SCALED
      // drawing — larger than the surface in one axis by exactly the amount being
      // cropped off both ends of it. Asked of the engine rather than worked out from
      // `sourceSize`, because the question is where the crop actually put the picture.
      //
      // Zero until the Image has one, and then this surface's own size as the
      // stand-in: a first frame with the anchor in the wrong place is a frame with no
      // art under it to be wrong about.
      readonly property real artW: still.paintedWidth > 0
                                   ? still.paintedWidth : surface.width
      readonly property real artH: still.paintedHeight > 0
                                   ? still.paintedHeight : surface.height

      // The instrument sits at 73.4% x 68.1% of THE ART, with its outer ring at 39%
      // of the art's shorter side — the three fractions pkgs/jarvis-wallpaper
      // composes every one of its renders to, held to that package by
      // tools/tests/test_wallshots.py. The motion is anchored there so it sits inside
      // the rings, not out on the desk.
      //
      // They used to be fractions of the SURFACE, which is the very same expression
      // whenever the art is this output's own bespoke render — `artW` is then `width`,
      // the overflow is zero and both halves of it vanish — and was 245 px wrong on a
      // 21:9 panel and wrong on every geometry that falls back to the primary art
      // instead (PLAN E9). docs/wall/06-ultrawide.png and 07-fallback.png are the
      // before pictures.
      readonly property real ix: (surface.width - surface.artW) / 2
                                 + surface.artW * 0.734
      readonly property real iy: (surface.height - surface.artH) / 2
                                 + surface.artH * 0.681
      readonly property real ir: Math.min(surface.artW, surface.artH) * 0.39

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

      // ONE CLOCK, AND WHY IT IS A NUMBER (PLAN E8). Both cycles below used to
      // be animations of their own — a `SequentialAnimation` on the glow's
      // opacity and a `RotationAnimation` on the comet's — and a surface
      // animated that way has no moment anybody can NAME. That is what stopped
      // this shell having a contact sheet: the other three sheets photograph
      // STATES, reached by feeding a model and waiting for it to settle, and a
      // phase is not a state. `wait(14000)` is not one either — it is a
      // different picture on every machine.
      //
      // So both cycles are bindings on one number, and the number is the only
      // thing that moves. `tools/wallshots/scene/tst_shots.qml` sets it and
      // grabs; nothing waits for anything.
      //
      // WHAT IS ON SCREEN DID NOT CHANGE, and that is arithmetic rather than a
      // claim. `Easing.InOutSine` is (1 - cos(πx))/2, and it is symmetric:
      // e(1-x) == 1-e(x). So a 0.25 → 1.0 InOutSine over 7 s followed by a
      // 1.0 → 0.25 InOutSine back is, at every instant, one cosine of the
      // whole 14 s — 0.625 - 0.375·cos(2π·phase/14000) — and a `RotationAnimation`
      // 0 → 360 is linear by default, which is 360·(phase mod 96000)/96000.
      // `tools/tests/test_wallshots.py` checks that algebra against a dense
      // sample of the pair this replaced rather than taking it on trust — in
      // Python, because the one deterministic way to compare two easing curves
      // is to compare the curves, and sampling a running animation would be
      // measuring this machine's frame timing instead.
      //
      // The lap is 672 s because that is where the two cycles agree again
      // (lcm(14, 96) = 672): the wrap from the end of one lap back to zero is a
      // continuous instant in BOTH of them, so nothing on screen jumps once
      // every eleven minutes.
      readonly property int lapMs: 672000
      property real phaseMs: 0
      NumberAnimation on phaseMs {
        running: shell.motion
        loops: Animation.Infinite
        from: 0
        to: surface.lapMs
        duration: surface.lapMs
      }

      // 1. the ember glow, breathing (14 s round trip)
      Rectangle {
        id: glow
        x: surface.ix - surface.ir
        y: surface.iy - surface.ir
        width: surface.ir * 2
        height: surface.ir * 2
        radius: glow.width / 2
        visible: shell.motion
        // The breath. Dimmest at the start of every 14 s round trip, brightest
        // 7 s in — the value the SequentialAnimation this replaced held at the
        // same instant, for the reason spelled out above `phaseMs`.
        opacity: 0.625 - 0.375 * Math.cos(2 * Math.PI * surface.phaseMs / 14000)
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
      }

      // 2. the comet head, drifting around the outer ring (96 s per lap)
      Item {
        id: comet
        x: surface.ix
        y: surface.iy
        visible: shell.motion
        // Drift, not spin: one lap of the outer ring every 96 s, linear,
        // because a head that sped up and slowed down is a thing the eye
        // follows.
        rotation: 360 * (surface.phaseMs % 96000) / 96000

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
      }
    }
  }
}
