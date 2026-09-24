// EarsBudgets — how jv-ears is tuned, as jv-ears reports it (A14).
//
// Two HUD elements make claims that only hold for as long as jv-ears is
// tuned to hold them:
//
//   SpeechState  stops saying "listening" when ears' wake window closes,
//                because ears publishes a window OPENING and nothing when
//                it ends (see core/SpeechState.qml).
//   MicState     stops calling a microphone live when the device has
//                delivered nothing for longer than ears' own stall budget.
//
// Both numbers used to be typed into QML by hand, under comments asking a
// future reader to keep them in step with `EarsConfig.wake_timeout_s` and
// `CaptureMeter.STALL_S`. That is not a mechanism, it is a hope: change
// the service and the HUD goes on asserting the old budget, silently, in
// the direction of over-claiming a microphone. So jv-ears now states its
// own budgets on its sys.health heartbeat — `metrics` is free-form and
// service-local by schema, so nothing frozen moved (invariant 2) — and
// this element is the one place that reads them.
//
//   wake_timeout_s    how long a wake keeps the utterance gate armed.
//   capture_stall_s   how long an open device may deliver nothing before
//                     jv-ears itself calls the heartbeat degraded.
//
// Why this does NOT expire, when MicState's gauges do. A gauge describes a
// moment and stops describing it (a heartbeat speaks for two periods and
// no longer); a budget describes how a service is CONFIGURED, and that
// stays true until the service says otherwise. jv-ears beats immediately
// on start, so a restart with new tuning arrives as a new heartbeat, and a
// dead jv-ears publishes no wakes for the window to measure anyway. The
// cost of getting this wrong is also bounded in the right direction: with
// nothing to read we fall back to ears' shipped defaults, which is exactly
// where the HUD stood before this element existed.
//
// Everything is read off a frame or refused. A budget that is not a finite
// positive number under its ceiling is not a budget — it is a frame we
// cannot use, and the fallback is better than arithmetic on a guess.
import QtQuick

QtObject {
  id: root

  // Anything offering `linkUp` and `latestFrom(topic, src)`: the `Bus`
  // singleton in production, a BusModel the tests drive.
  property var bus: null

  // The service whose tuning this is. sys.health carries every service's
  // heartbeat, so asking by name is the whole point of `latestFrom`.
  property string service: "jv-ears"

  // --- the fallbacks --------------------------------------------------
  //
  // jv-ears' shipped defaults, and the only copies of them left in the
  // HUD. They are what we assert when ears has not told us, which is
  // every moment before its first heartbeat lands. A tools test fails the
  // build if either drifts from the Python that enforces it, so these
  // mirrors cannot rot the way the comments they replaced could.

  // EarsConfig.wake_timeout_s.
  readonly property real wakeWindowDefaultS: 8.0
  // CaptureMeter.STALL_S.
  readonly property real stallDefaultS: 1.0

  // --- what the HUD should actually use -------------------------------

  // Ceilings. A budget is arithmetic the HUD will trust for that long AND
  // a Timer interval, so it is bounded above as well as below: an absurd
  // number is a frame to refuse, not a duration to honour.
  //
  // A minute is already seven times ears' wake default, and past it a
  // single detection would hold a claim about the microphone for longer
  // than anyone could have meant to configure. Chunks arrive every 80 ms,
  // so a ten-second stall budget is over a hundred missed ones — past
  // that the HUD would be calling a deaf microphone live, which is the
  // failure the indicator exists to catch.
  readonly property real wakeWindowCeilingS: 60
  readonly property real stallCeilingS: 10

  // How long a wake word keeps meaning "listening".
  readonly property real wakeWindowS: root.budget("wake_timeout_s", root.wakeWindowDefaultS, root.wakeWindowCeilingS)

  // How long an open device may deliver nothing and still read as live.
  readonly property real stallS: root.budget("capture_stall_s", root.stallDefaultS, root.stallCeilingS)

  // Did that value come off a heartbeat, or are we standing on the
  // default? Nothing draws these — they are what the tests assert on, and
  // they answer honestly when a reported budget was refused: a value we
  // could not use leaves us on the fallback, same as silence.
  readonly property bool wakeWindowReported: root.usable("wake_timeout_s", root.wakeWindowCeilingS)
  readonly property bool stallReported: root.usable("capture_stall_s", root.stallCeilingS)

  // --- reading it off the heartbeat -----------------------------------

  // The gauges on jv-ears' last readable heartbeat, or null. Refused: no
  // link (a cached frame describes a machine we can no longer see), a
  // body from a schema version we were not written against (invariant 2),
  // a heartbeat hedging its confidence (state topics publish conf 1.0 —
  // anything less disagrees with itself), and a body naming a different
  // service than the envelope said published it.
  //
  // `ts` and `period_s` are deliberately NOT required here, though
  // MicState requires both: they are how you tell whether a MEASUREMENT
  // still describes the present, and nothing below is a measurement.
  readonly property var metrics: {
    if (!root.bus || !root.bus.linkUp || typeof root.bus.latestFrom !== "function")
      return null;
    const env = root.bus.latestFrom("sys.health", root.service);
    if (!env || env.v !== 1 || env.conf !== 1 || !env.body)
      return null;
    if (env.body.service !== root.service || !env.body.metrics)
      return null;
    return env.body.metrics;
  }

  // Is there a number here we are willing to act on? One predicate, so
  // the value and the "did we read it" flag can never disagree.
  //
  // `typeof` first and not a coercion: `"12" > 0` is true in JavaScript,
  // and a budget that arrived as a string is a jv-ears we do not
  // understand, not a twelve. The two comparisons then do the rest —
  // NaN and -Infinity fail `> 0`, +Infinity fails the ceiling — so there
  // is no `isFinite` here. There was, until a mutation run showed no
  // input could reach it.
  function usable(name: string, ceilingS: real): bool {
    const m = root.metrics;
    if (m === null)
      return false;
    const v = m[name];
    return typeof v === "number" && v > 0 && v <= ceilingS;
  }

  // That number, or the fallback.
  function budget(name: string, fallback: real, ceilingS: real): real {
    return root.usable(name, ceilingS) ? root.metrics[name] : fallback;
  }
}
