// Notifications — this machine's org.freedesktop.Notifications daemon (D2).
//
// Quickshell claims the bus name and does the D-Bus work; what this file
// decides is what JarvisOS TELLS every sender it can do, and what it does
// with a notification once one arrives. The lifecycle — how many are on
// screen, for how long, what a replacement means — is next door in
// `core/NotifyModel.qml`, where it is pure QtQuick and tested headlessly.
// Keep it that way: logic that lands in this file is logic no test can reach.
//
// THE CAPABILITY SET IS AN HONESTY DECLARATION, NOT A CONFIG BLOCK. A sender
// asks this daemon what it supports and then decides what to send. Claiming
// `actionsSupported` would make apps offer buttons that this surface can
// never deliver — its input region is empty, so there is no click to invoke
// one with — and the user would watch an app hand them a choice that does
// nothing. So every capability below is false unless these pixels actually
// do it, and the two that are true (`bodySupported`, and body text drawn
// verbatim) are the two the plate draws. That is invariant 10's rule about
// not showing what is not so, applied to the one surface here that has a
// protocol to lie in.
//
// WHAT THIS IS NOT. It is not a bus consumer: nothing Jarvis perceives or
// says comes through here. `jv-hud` is where Jarvis speaks on screen, over
// the real bus (invariant 1), and it keeps the ember accent for that reason —
// a notification is ANOTHER program's news, and any program can put any
// string in `app_name`, including "Jarvis". A corner that spent the accent on
// a name a stranger chose would hand every process on this machine the
// ability to look like the assistant.
pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Services.Notifications
import "core"

Singleton {
  id: root

  readonly property alias toasts: model.toasts
  // What the surface repeats over: the same toasts, as rows keyed by the
  // notification's own id, so a plate already on screen keeps its delegate
  // when another one arrives (PLAN D37). `toasts` stays exported because it is
  // the answer to "what is up", which is a different question from "what does
  // the Repeater build".
  readonly property alias onScreen: model.onScreen
  readonly property alias earlier: model.earlier
  readonly property alias anyLit: model.anyLit

  NotifyModel {
    id: model

    // Quickshell's ElapsedTimer reads CLOCK_MONOTONIC in seconds — the clock
    // a dwell should be measured on, because it does not jump when the wall
    // clock is corrected. This is the only reason the model takes an injected
    // one: the tests have no ElapsedTimer to give it.
    monotonic: () => sinceStart.elapsed()
  }

  ElapsedTimer {
    id: sinceStart
  }

  NotificationServer {
    id: server

    // --- what these pixels can actually do -----------------------------
    //
    // The body is drawn, so it is asked for. Everything else is refused, and
    // each refusal is a thing an app would otherwise send and a human would
    // never see.
    bodySupported: true
    // Plain text only. The plate renders with Text.PlainText, so `<b>` shows
    // up as `<b>` — which is the honest outcome for a daemon that says it
    // does not do markup, and the reason it says so.
    bodyMarkupSupported: false
    bodyHyperlinksSupported: false
    bodyImagesSupported: false
    // No buttons: the surface's input region is empty (see shell.qml), so an
    // action is a promise these pixels cannot keep. PLAN D19.
    actionsSupported: false
    actionIconsSupported: false
    // No icon and no image: the corner draws type, and an app-supplied
    // pixmap is the one thing on it that JarvisOS did not draw.
    imageSupported: false
    inlineReplySupported: false
    // No history and no notification centre yet, so a notification that has
    // gone is gone. Claiming persistence would tell an app it may skip
    // sending something twice because the user can go back and find it.
    persistenceSupported: false

    // A quickshell config reload builds a new model with nothing in it. With
    // `keepOnReload` the old notifications would survive in the server and
    // never be handed to it — alive, never shown, never expiring. Dropping
    // them is the honest half of that pair.
    keepOnReload: false

    onNotification: n => root.take(n)
  }

  // Take one in. `tracked` is what keeps the Notification object alive past
  // this function; without it Quickshell discards the notification and the
  // sender is told it was closed.
  function take(n: Notification): void {
    n.tracked = true;
    const key = "" + n.id;
    model.push({
      "key": key,
      "appName": n.appName,
      "summary": n.summary,
      "body": n.body,
      "urgency": n.urgency,
      "timeoutMs": n.expireTimeout,
      // Held opaquely by the model, which calls expire() on it and reads
      // nothing — that is what lets core/ own the lifecycle without ever
      // importing Quickshell.
      "handle": n
    });
    // However this notification ends — our own dwell running out, its sender
    // withdrawing it, or the user's own action elsewhere — the corner hears
    // about it here and lets go of the plate. `drop` closes nothing, because
    // by the time this fires the notification is already closed.
    n.closed.connect(() => model.drop(key));
  }
}
