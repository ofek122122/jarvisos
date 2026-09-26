// jv-notify — the JarvisOS notification corner (blueprint §06, PLAN D2).
//
// This machine's org.freedesktop.Notifications daemon, and the bottom-right
// corner it draws in. A layer-shell surface that takes no keyboard, reserves
// no screen space, cannot be clicked, and is unmapped whenever nothing has
// been sent — the HUD's contract exactly, for the same reason: a surface that
// floats over every window has to be provably unable to get in the way.
//
//   · WlrKeyboardFocus.None + focusable:false — it CANNOT take the keyboard.
//   · ExclusionMode.Ignore — zero exclusive zone, so no window is ever
//     resized or pushed around by a notification arriving.
//   · mask: Region {} — an empty input region: every click, scroll and hover
//     passes through to the window underneath. Which is also why this daemon
//     tells senders `actionsSupported: false` (see Notifications.qml): there
//     is no click here to invoke an action with, so it does not advertise
//     one. PLAN D19 is what it would take to offer them honestly.
//   · visible is false whenever the corner is empty, and an unmapped surface
//     costs exactly 0 fps. §06's earned emptiness is the ordinary state of a
//     notification daemon — most of a day has nothing in it.
//
// WHY THE BOTTOM RIGHT. The top right is the HUD's (it draws over the bar's
// strip there, and `jv-bar` reserves that corner for it); the top strip is the
// bar's; the top left is where the bar puts your workspaces. The bottom right
// is the one corner of this desktop nothing else claims, and it is where a
// Wayland desktop puts notifications anyway — so a message arriving lands
// somewhere a person already looks, without ever sharing a corner with Jarvis
// speaking. Two surfaces in one corner is the one arrangement neither of them
// can detect.
//
// WHY EVERY MONITOR, when the bar is per-monitor and each strip shows only
// its own desk. Because a workspace IS a property of a monitor and a
// notification is not: nothing on this machine publishes which screen you are
// looking at (niri's focus is not read here, and the flake names no primary
// output — PLAN D4/D10), so choosing one monitor means choosing it by a guess
// and a guess is how a message is missed entirely. Three copies of a toast is
// a cost; a toast you never saw is a failure. `jv-hud` resolved the same
// question the same way. PLAN D21 is what would change the answer.
//
// THE BOX IS DERIVED, NOT DECLARED. `implicitHeight` is the stack plus its
// inset, so the surface is exactly as tall as what is in it. That is the one
// structural difference from the HUD, whose fixed 300x826 box had to be
// MEASURED after a crowded corner turned out to be cut in half (A63) — a
// surface sized by its own content cannot crop its own bottom plate, so there
// is no equivalent of that failure here and no fit test needed to catch it.
// The cost is that the surface resizes as toasts come and go, which for a
// panel that reserves nothing and takes no input is free.
//
// Everything on screen here comes from a real notification: `Notifications`
// is the D-Bus server and draws nothing of its own, the cap and the dwell are
// `core/NotifyModel.qml`, and an empty corner is an unmapped one. Nothing in
// this shell can show a message that was not sent to it.
//
// `Notifications` is a singleton constructed on load, so the daemon claims
// the bus name for as long as the shell runs — a notification daemon that
// only existed while something was on screen would be a daemon that was never
// there when an app went looking for one. The surface still maps only when
// there is something to draw.
pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Wayland
// The §06 tokens, generated from personality/theme.toml into Theme.qml next
// door (invariant 9: the look is identity, and identity is versioned). No QML
// file in this directory may carry a hex code of its own.
import "."

ShellRoot {
  id: shell

  // One corner per connected monitor. Quickshell.screens is live, so a
  // hotplugged monitor gains one without restarting the shell.
  Variants {
    model: Quickshell.screens

    PanelWindow {
      id: surface

      required property var modelData

      screen: modelData

      // Top, like the HUD and the bar: above ordinary windows, below
      // fullscreen and lock surfaces. A notification is never the thing in
      // the way, and it must never draw over a lock screen.
      WlrLayershell.layer: WlrLayer.Top
      WlrLayershell.namespace: "jv-notify"
      WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
      focusable: false
      exclusionMode: ExclusionMode.Ignore

      anchors {
        bottom: true
        right: true
      }

      // The edge inset is baked into the surface rather than into `margins`,
      // for the reason the HUD gives: quickshell's `margins` grouped property
      // has no resolvable type in its qmltypes, and a clean qmllint is worth
      // more than two pixels of layout sugar.
      implicitWidth: stack.implicitWidth + Theme.insetPx * 2
      implicitHeight: stack.implicitHeight + Theme.insetPx * 2
      color: "transparent"
      mask: Region {} // empty: input passes through, always

      // Mapped only while something has actually been sent. Nothing fades
      // out, so there is no state where the corner is empty and still drawn.
      visible: Notifications.anyLit

      Column {
        id: stack

        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: Theme.insetPx
        spacing: Theme.gapPx

        // How many are being tracked and NOT on screen, above the ones that
        // are. It is a count of things the corner is deliberately not
        // showing, which is the one thing a capped stack owes the person
        // reading it — a cap nobody is told about is indistinguishable from
        // a daemon that dropped their notification.
        Text {
          text: "+" + Notifications.earlier + " EARLIER"
          visible: Notifications.earlier > 0
          color: Theme.text3
          font.family: Theme.familyMono
          font.pixelSize: Theme.labelPx
          font.letterSpacing: Theme.labelPx * Theme.labelTrackingEm
          textFormat: Text.PlainText
        }

        // Oldest first, so the newest plate is the one nearest the corner —
        // the shortest distance from where a message appears to where the
        // last one did.
        // Keyed by the notification's id, never by position (PLAN D37).
        // `Notifications.onScreen` is a ListModel `NotifyModel` keeps in step
        // with `toasts`, so a plate that is still up keeps its delegate — and
        // a delegate that survives keeps `arrived` true and does not fade in
        // again. Repeating over the array instead meant every plate in the
        // corner was destroyed and rebuilt whenever ANY notification arrived,
        // was replaced or went away, so all three blinked and the fade stopped
        // meaning "this one is new".
        //
        // The record is rebuilt from the roles because a ListModel holds
        // values, not objects: `Toast` takes one record, which is what lets it
        // import nothing but QtQuick and the generated Theme.
        Repeater {
          model: Notifications.onScreen

          Toast {
            required property string appName
            required property string summary
            required property string body
            required property int urgency

            toast: ({
                "appName": appName,
                "summary": summary,
                "body": body,
                "urgency": urgency
              })
          }
        }
      }
    }
  }
}
