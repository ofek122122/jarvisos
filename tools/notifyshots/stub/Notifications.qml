// Notifications — the shot harness's stand-in for the notifier's real
// singleton (PLAN D20).
//
// STAGED OVER shell/jv-notify/Notifications.qml, never committed next to it:
// the real one IS this machine's org.freedesktop.Notifications daemon. It
// claims a bus name through Quickshell's NotificationServer, and quickshell
// links its QML plugin into its own binary, so no other QML engine can import
// it — the same wall that put every tested element in core/, and the reason
// `Toast.qml` takes its record as a property instead of reading the singleton.
//
// What is left once the D-Bus half is gone is exactly what the corner uses —
// a NotifyModel and a monotonic clock — and this file is that, with the clock
// handed to it instead of read off CLOCK_MONOTONIC.
//
// It is a STAND-IN FOR THE BUS NAME, not for the daemon's judgement: every
// notification the plates see still goes in as the same record the real
// server builds (`key`, `appName`, `summary`, `body`, `urgency`, `timeoutMs`,
// `handle`) and through the real core/NotifyModel.qml — the same cap, the same
// `earlier` count, the same whitespace collapse, the same dwell arithmetic.
// Nothing here decides what a toast says.
//
// The forwarded surface is Notifications.qml's, member for member —
// tools/tests/test_notifyshots.py fails if the two ever drift, because a
// missing member here would not error: a strip reading
// `Notifications.somethingElse` would quietly see `undefined` and photograph
// a corner with nothing in it.
pragma Singleton

import QtQuick
import "core"

Item {
  id: root

  // The clock the model measures dwells against, in seconds. Fixed at 0 and
  // wound by hand: a shot must be a settled instant, and a corner whose
  // plates were expiring against the wall clock while the grab was taken
  // would photograph a different number of them depending on how busy the
  // machine was.
  property real now: 0

  // --- Notifications.qml's surface ------------------------------------

  readonly property var toasts: root.model ? root.model.toasts : []
  readonly property int earlier: root.model ? root.model.earlier : 0
  readonly property bool anyLit: root.model ? root.model.anyLit : false

  // --- the harness half -----------------------------------------------

  // A whole new model per shot rather than `clear()`: every shot must start
  // from a corner that has never been sent anything, and "forget all of them"
  // is the model's answer to a link that went away, not a factory reset.
  function reset(): void {
    if (root.model)
      root.model.destroy();
    root.now = 0;
    root.model = root.modelComponent.createObject(root, {
      monotonic: () => root.now
    });
  }

  // One notification, in the shape the real server hands over. `key` is the
  // sender's notification id as a string, which is what makes a second send
  // under the same key a replacement rather than a second plate.
  function send(record: var): void {
    root.model.push(record);
  }

  // A sender withdrawing one, or the user dismissing it elsewhere: the corner
  // lets go of the plate and closes nothing, exactly as `drop` is called from
  // the real `closed` signal.
  function withdraw(key: string): void {
    root.model.drop("" + key);
  }

  // Move the injected clock forward and let the model sweep, so a shot can be
  // taken of a corner that has been up for a while. Seconds, because that is
  // what the clock the real one injects reads in.
  function wind(seconds: real): void {
    root.now += seconds;
    root.model.sweep();
  }

  property NotifyModel model: null

  readonly property Component modelComponent: Component {
    NotifyModel {}
  }

  Component.onCompleted: root.reset()
}
