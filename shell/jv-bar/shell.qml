// jv-bar — the JarvisOS top bar (blueprint §06, Quickshell/QML, PLAN D1).
//
// A layer-shell strip along the top of every monitor: niri's workspaces for
// THAT monitor on the left, the clock in the middle, and a right end that
// is deliberately empty because the HUD floats there.
//
// HOW IT DIFFERS FROM THE HUD, AND WHY THAT IS NOT A LOOSENING.
// `shell/jv-hud/shell.qml` takes no space, takes no input, and is unmapped
// unless a real frame earned it. This surface keeps two of those three:
//
//   · WlrKeyboardFocus.None + focusable:false — it CANNOT take the
//     keyboard, so it can never interrupt what you are typing into.
//   · mask: Region {} — an empty input region. The bar cannot be clicked
//     at all, which is why nothing in it pretends to be a button. Clicking
//     a workspace to switch to it would be jv-bar changing the state of
//     this machine, and invariant 3 says that is jv-act's alone; it is
//     also not something to add by opening the mask and hoping (PLAN D15).
//   · it DOES reserve its strip, and it is mapped whether or not it has
//     anything to say. That is the difference, and it is a property of
//     what a bar IS rather than a relaxation: a docked surface that
//     vanished when it went quiet would resize every window on the monitor
//     to do it. Earned emptiness is still kept where it can be — an
//     unknown desk draws no workspaces and an unknown time draws no clock,
//     so the empty bar is genuinely empty rather than full of placeholders
//     — and a surface nothing changes on commits no frames, so the cost of
//     being always mapped is 0 fps.
//
// THE RIGHT END IS NOT FREE SPACE. The HUD sets ExclusionMode.Ignore, so
// it is not pushed down by this bar: its plates are drawn OVER the top
// right corner of this strip. `hudReservePx` below is that corner, and
// nothing may be laid out inside it. The clock hides itself rather than be
// drawn underneath a plate, which on ares' three monitors never happens
// and is the kind of thing that should fail visibly on the fourth.
//
// Everything on screen here comes from something real: the workspaces from
// `niri msg --json event-stream` through `Niri`/`core/NiriModel`, the time
// from Quickshell's SystemClock. Neither ever draws a guess — an unknown
// desk and an empty desk look different (nothing, and nothing), which is
// the honest pair.
//
// `clock` below is an id in THIS component, read from inside the per-screen
// delegate `Variants` builds — and by default a delegate resolves an outer id
// dynamically, at whatever the name happens to mean when the binding runs.
// Bound makes that lookup lexical and checkable, which is what lets qmllint
// see the reference at all: without it the two bindings are `unqualified`
// warnings, and -W 0 in pkgs/jv-bar means a warning is a failed build. The
// alternative was a SystemClock per monitor — three timers waking three
// surfaces to draw the same minute.
pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Wayland
// The §06 tokens, generated from personality/theme.toml into Theme.qml next
// door (invariant 9: the look is identity, and identity is versioned). No
// QML file in this directory may carry a hex code of its own.
import "."

ShellRoot {
  id: shell

  // One tick a minute, on the minute, for every surface at once — not a
  // Timer, and not per-screen. At Minutes precision this wakes the process
  // 1,440 times a day instead of 86,400, and every one of those wakeups
  // changes a glyph that someone might read.
  SystemClock {
    id: clock

    precision: SystemClock.Minutes
  }

  // One strip per connected monitor. Quickshell.screens is live, so a
  // hotplugged monitor gains a bar without restarting the shell — and it
  // gains the RIGHT bar, because the workspaces are looked up by the
  // screen's own name.
  Variants {
    model: Quickshell.screens

    PanelWindow {
      id: surface

      required property var modelData

      // The corner the HUD draws in: its 300 px surface plus the §06 edge
      // inset it sits in. Kept as a number rather than an anchor because
      // the HUD is a different process on a different layer — there is
      // nothing here to anchor to, only a promise to keep.
      readonly property int hudReservePx: 300 + Theme.insetPx

      screen: modelData

      // Top, like the HUD: above ordinary windows, below fullscreen and
      // lock surfaces. A bar is never the thing in the way.
      WlrLayershell.layer: WlrLayer.Top
      WlrLayershell.namespace: "jv-bar"
      WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
      focusable: false

      // The one thing this surface takes that the HUD does not: a strip of
      // the screen, exactly as tall as it is, so windows tile below it
      // rather than under it.
      exclusionMode: ExclusionMode.Normal
      exclusiveZone: surface.implicitHeight

      anchors {
        top: true
        left: true
        right: true
      }

      // One label's worth of type with §06's internal padding above and
      // below it. Derived rather than declared: a bar whose height is a
      // number of its own drifts away from the rhythm every other surface
      // on this machine is built on the moment either token moves.
      implicitHeight: Theme.labelPx + Theme.padPx * 2
      // Opaque, and the same ground a HUD plate is painted in: the bar is
      // chrome lying on the desktop, not a hole cut in it. Nothing is ever
      // behind it — it reserves its own strip — so there is nothing for
      // translucency to reveal and no blend to pay for.
      color: Theme.groundDeep
      mask: Region {} // empty: every click, scroll and hover passes through

      // The one hairline: where the bar stops and your windows start.
      Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: Theme.hairlinePx
        color: Theme.lineSoft
      }

      // Left: this monitor's workspaces, and only this monitor's. The join
      // is the output name — Wayland's, which is what Qt reports as the
      // screen name and what niri calls an output. If those two ever stop
      // agreeing this strip goes empty, which is the right way round: the
      // bar would say nothing rather than draw another monitor's desk.
      Workspaces {
        anchors.left: parent.left
        anchors.leftMargin: Theme.insetPx
        anchors.verticalCenter: parent.verticalCenter

        workspaces: Niri.workspacesOn(surface.modelData.name)
      }

      // Middle: the time. Centred on the SCREEN rather than on the space
      // left over, because a clock that sits slightly off-centre reads as
      // a mistake — and hidden outright on a monitor narrow enough for
      // that centre to fall inside the HUD's corner.
      Clock {
        id: face

        anchors.horizontalCenter: parent.horizontalCenter
        anchors.verticalCenter: parent.verticalCenter

        hours: clock.hours
        minutes: clock.minutes
        fits: surface.width / 2 + face.width / 2 < surface.width - surface.hudReservePx
      }

      // Right: nothing, on purpose. See `hudReservePx` above — the HUD
      // draws there, over this strip, and two surfaces in one corner is
      // the one arrangement neither of them can detect.
    }
  }
}
