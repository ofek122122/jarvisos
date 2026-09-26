// GpuThermalState — is the card running hot, right now? (G5)
//
// jv-context's `NvidiaSmiProbe` (services/jv-context/jv_context/system.py)
// reads `temperature.gpu`/`fan.speed` off the same card `VramState` already
// quotes for free VRAM — but neither number belongs on `context.system`:
// that schema is frozen (GUARDRAILS: schemas/** is human-review-only), so
// they ride `sys.health`'s own free-form `metrics` bag instead, the exact
// seam F5c used for jv-dictate's `recording` gauge. This element therefore
// reads jv-context's OWN heartbeat rather than `context.system`, and
// follows `DictateState`'s reading rules (a service-named metrics gauge,
// not `VramState`'s snapshot-topic rules) almost line for line.
//
// EARNED EMPTINESS, THE SAME ARGUMENT `HealthPlate` MAKES FOR ITSELF. This
// plate draws "NOTHING is wrong" by staying empty (its own header), and a
// temperature reading sitting under it all day — on a card that idles
// nowhere near its limits — would be exactly the all-day gauge §06 refuses.
// So `reporting` is not "do we know the temperature", it is "is the
// temperature worth a look": only once the card crosses `hotThresholdC`.
// Below that line this element is known but silent, same as `VramState` is
// known but silent while the brain is on the GPU.
//
// `hotThresholdC` is a fact about this machine, not a guess at another
// service's configuration (contrast `VramState`'s refusal to judge
// sufficiency against jv-brain's ladder): a GTX 1660 SUPER throttles in the
// high 80s/low 90s Celsius, ares idles in the 30s-40s under normal desktop
// load, and 80 sits early enough to be a warning and late enough that it is
// never ordinary background noise.
//
// The fan line is a QUOTE next to the temperature, the same relationship
// `VramState`'s `needLine` has to its own reading: it explains the line
// above rather than standing alone, so it only ever appears alongside it.
import QtQuick

QtObject {
  id: root

  // Anything offering `linkUp`, `latestFrom(topic, src)` and `ageOf()`:
  // the `Bus` singleton in production, a BusModel the tests drive.
  property var bus: null

  // The service that owns the GPU probe.
  property string service: "jv-context"

  // See the header: a fact about ares' own card, not a per-service
  // configuration this element would be guessing at.
  property real hotThresholdC: 80.0

  // --- the outputs --------------------------------------------------------

  // Is there a fresh temperature figure at all? False on a card-less
  // machine, a dead link, a jv-context too old to report the gauge, or a
  // heartbeat this file may not read (schema version, hedged conf, ...).
  readonly property bool known: root.metrics !== null

  readonly property real tempC: root.known ? root.metrics.gpu_temp_c : -1

  // Is the fan figure usable? Kept separate from `known`: the probe's own
  // contract (services/jv-context/jv_context/system.py) always reports
  // both together or neither, but this element does not assume its
  // publisher's internals — a heartbeat with a temperature and no fan
  // number is read as exactly that, not refused outright.
  readonly property bool fanKnown: root.known && typeof root.metrics.gpu_fan_pct === "number"

  readonly property real fanPct: root.fanKnown ? root.metrics.gpu_fan_pct : -1

  // Worth a line on HealthPlate. See the header on earned emptiness.
  readonly property bool reporting: root.known && root.tempC >= root.hotThresholdC

  // The line, as `HealthPlate` draws it — "GPU 82°C" — or "" when there is
  // nothing to say. Whole degrees: nothing here is decided by a fraction.
  readonly property string line: root.reporting ? "GPU " + Math.round(root.tempC) + "°C" : ""

  // The quote beneath it — "FAN 64%" — never without the reading it
  // explains (see the header).
  readonly property bool fanReporting: root.reporting && root.fanKnown
  readonly property string fanLine: root.fanReporting ? "FAN " + Math.round(root.fanPct) + "%" : ""

  // --- the heartbeat we are willing to believe ----------------------------

  // The last sys.health from `service`, or null. Rejected outright: a body
  // from a schema version we were not written against (invariant 2), a
  // frame with no orderable `ts`, a heartbeat hedging its confidence
  // (state topics publish conf 1.0), a body naming a DIFFERENT service than
  // the envelope said published it, and one with no usable `period_s`,
  // which is how long we may believe it.
  readonly property var health: {
    if (!root.bus || !root.bus.linkUp || typeof root.bus.latestFrom !== "function")
      return null;
    const env = root.bus.latestFrom("sys.health", root.service);
    if (!env || env.v !== 1 || typeof env.ts !== "number" || env.conf !== 1 || !env.body)
      return null;
    if (env.body.service !== root.service || !(env.body.period_s > 0))
      return null;
    return env;
  }

  // The gauges, or null if this heartbeat carries no readable temperature.
  // Null is NOT "cold": a jv-context too old to report the gauge is one we
  // cannot read a reading from, and guessing "cold" there is the lie that
  // matters — the same rule `DictateState.metrics` follows for "idle".
  readonly property var metrics: {
    const env = root.health;
    if (env === null || root.healthStale)
      return null;
    const m = env.body.metrics;
    return m && typeof m.gpu_temp_c === "number" ? m : null;
  }

  // --- how long a heartbeat describes the present -------------------------

  // schemas/sys.health.json: "Missing 2 consecutive periods = presumed
  // dead". So a heartbeat speaks for two of its own periods and no longer.
  readonly property bool healthStale: root.health === null || root.expired || root.ageOf(root.health) > root.health.body.period_s * 2

  // Set by the timer below, cleared by every fresh heartbeat. A plain
  // property, not a computed one: no binding re-evaluates because a clock
  // moved, and this element's whole job is to stop claiming things.
  property bool expired: false

  // Identity of the heartbeat currently believed — `seq` is per-publisher
  // and strictly increasing, so this changes exactly once per frame.
  readonly property string healthKey: root.health === null ? "" : root.health.seq + "@" + root.health.ts

  onHealthKeyChanged: root.armExpiry()

  // One shot, armed only while there is a heartbeat to expire — a HUD with
  // no jv-context on the bus runs no timer at all (§06: 0 fps when nothing
  // is happening).
  readonly property Timer expiry: Timer {
    repeat: false
    onTriggered: root.expired = true
  }

  function armExpiry(): void {
    root.expired = false;
    if (root.health === null) {
      root.expiry.running = false;
      return;
    }
    // Whatever is LEFT of the two periods: a frame that spent time in
    // flight is already partway through its own life.
    const left = root.health.body.period_s * 2 - root.ageOf(root.health);
    if (!(left > 0)) {
      root.expiry.running = false;
      root.expired = true;
      return;
    }
    root.expiry.interval = Math.max(1, Math.ceil(left * 1000));
    root.expiry.restart();
  }

  function ageOf(envelope: var): real {
    return root.bus && typeof root.bus.ageOf === "function" ? root.bus.ageOf(envelope) : Infinity;
  }
}
