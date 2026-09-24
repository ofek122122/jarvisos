// LinkState — can the HUD still see the bus? (A23)
//
// Every element in this HUD is built to refuse. MicState will not say "off"
// when it cannot tell; SpeechState will not say "idle" from a bus it cannot
// see; ConfirmState lets go of a latched question the moment the link drops;
// BusModel empties its whole cache on `up:false`, because a stale indicator
// is worse than no indicator. All of those refusals are correct and all of
// them reach the screen identically: the plate draws nothing.
//
// Which is the gap this element fills. An empty corner is ALSO what a quiet,
// well machine looks like — it is the HUD's default state, on purpose (§06,
// earned emptiness). So the same absence of pixels carries two opposite
// meanings, and the user has no way to tell "Jarvis is idle" from "this
// screen has been blind for a minute and the microphone could be open".
// Invariant 10 says the HUD always truthfully shows sensor state; silence
// that cannot be distinguished from a reading is not the truth, it is a
// coin flip.
//
// This element does NOT report on the machine. It reports on the pipe — the
// one thing the HUD can observe without the bus, namely whether it has one.
// That distinction is why it carries no accent colour and no dot next door
// in LinkPlate.qml: it is the panel talking about itself, never a sensor.
//
// The one piece of judgement here is the WAIT. A down link is ordinary and
// usually brief: jv-hud-bridge retries 0.5 s after a link that worked drops
// (FIRST_BACKOFF_S), and Bus.qml respawns the bridge process itself 2 s
// after it dies. A warning that blinks on every jarvisd restart is a warning
// that gets ignored on the day it is real, so nothing is said until the
// outage has outlasted both of those cadences — and a tools test fails the
// build if either of them ever grows past the grace.
//
// Nothing here is a claim about the room, so nothing here can be a lie about
// the room. The only way this element is wrong is by staying quiet, which is
// what the grace is measured for.
import QtQuick

QtObject {
  id: root

  // Anything offering `linkUp` and `linkError`: the `Bus` singleton in
  // production, a BusModel the tests drive. Null is not an error — it is
  // an element that can see nothing, which is what this reports.
  property var bus: null

  // How long the bus may be invisible before that is worth saying. Longer
  // than every ordinary reconnect and shorter than a person's patience.
  // A budget this file decides, unlike A14's mirrored ones: no service
  // enforces it, it is purely how long the HUD is willing to be silent
  // about its own blindness.
  property real graceS: 5.0

  // How much of the bridge's explanation is worth carrying to the screen:
  // two wrapped lines of the quiet tier, and an ellipsis if there was more.
  property int maxReasonChars: 72

  // --- the outputs ------------------------------------------------------

  // True only while the bridge holds a live, subscribed bus connection.
  // `=== true`, never truthiness: a stand-in that does not answer says
  // `undefined`, and "I did not say" must not read as "yes".
  readonly property bool linked: !!root.bus && root.bus.linkUp === true

  // The whole claim: this HUD has not been able to see the bus for long
  // enough that its silence is no longer evidence of a quiet machine.
  readonly property bool blind: !root.linked && root.waited

  // Why, in the bridge's own words — "connect: ..." when jarvisd is not
  // there, "bus closed the connection" when it went away. Passed through
  // rather than summarised: that distinction is the whole value of the
  // second line, and this file has no better information than the process
  // holding the socket. Empty until there is a report to reason about, so
  // BusModel's initial "starting" never reaches a screen.
  readonly property string reason: {
    if (!root.blind || !root.bus || typeof root.bus.linkError !== "string")
      return "";
    return root.oneLine(root.bus.linkError);
  }

  // --- the wait ---------------------------------------------------------

  // Has the CURRENT outage run past the grace? Set by the timer below,
  // cleared when a new outage starts being timed — and deliberately NOT
  // cleared when the link returns, because `blind` already knows there is
  // no outage to describe then. One fact per line: this one is about a
  // duration, `linked` is about now, and neither stands in for the other.
  // A plain property, not a computed one: every path that sets it is in
  // `armGrace`.
  property bool waited: false

  // One shot, armed only while an outage is being timed — so a HUD with a
  // healthy link runs no timer, and one that has already reported runs no
  // timer either (§06: 0 fps when nothing is happening).
  readonly property Timer grace: Timer {
    repeat: false
    onTriggered: root.waited = true
  }

  onLinkedChanged: root.armGrace()
  onGraceSChanged: root.armGrace()
  // `linked` is false at construction and stays false while a bridge fails
  // to connect, so no change signal ever fires for the outage the HUD boots
  // into — which is the most important one there is: nothing on this machine
  // is running. The wait therefore starts when the element does. There is
  // deliberately no `onBusChanged`: the production binding (`bus: Bus`) is
  // already in place when this runs, and every later change of link state
  // arrives through `linked`.
  Component.onCompleted: root.armGrace()

  function armGrace(): void {
    if (root.linked) {
      // Nothing to time. What the last outage did is not forgotten here —
      // `blind` is false because the link is up, not because we cleared a
      // flag, and the next outage clears it when it starts.
      root.grace.running = false;
      return;
    }
    // A new outage is timed from scratch. Without this, an outage that was
    // already reported would hand its verdict to the next brief blip.
    root.waited = false;
    // A grace of zero (or less) is a request for no wait at all. Handled
    // here rather than by the Timer: `restart()` with a zero interval
    // fires a frame later, which would read as an outage that was missed.
    if (!(root.graceS > 0)) {
      root.grace.running = false;
      root.waited = true;
      return;
    }
    root.grace.interval = Math.ceil(root.graceS * 1000);
    root.grace.restart();
  }

  // One paragraph: the label wraps on its own width, but a newline of the
  // bridge's own would break the plate's layout rather than the sentence,
  // and a tab would open a hole in the middle of it. A clipped reason says
  // that it was clipped, for the same reason ConfirmPlate's question does —
  // text that stops without saying so reads as complete.
  function oneLine(text: string): string {
    const flat = text.replace(/\s+/g, " ").trim();
    if (flat.length <= root.maxReasonChars)
      return flat;
    return flat.slice(0, root.maxReasonChars - 1) + "…";
  }
}
