// HealthPlate — the glance that only appears when something is wrong (A6).
//
// §06's earned emptiness, taken literally: a machine where every service
// heard from says `ok` draws NOTHING here. There is no green dashboard, no
// row of reassuring lights — a readout that is on screen all day is a
// readout nobody reads, and the one thing this has to do is be noticed the
// day it does appear.
//
// Which makes the silence ambiguous, and deliberately so: an empty corner
// means "nothing is wrong" OR "the HUD cannot see the bus", and those are
// the same amount of information — none. The alternative is worse. A plate
// reading "all services ok" from a bus that died three minutes ago is the
// exact failure invariant 10 exists to prevent, and there is no way to
// distinguish the two cases without claiming something. (The bus link's
// own state is developer information and lives in the self-test marker in
// shell.qml, where it cannot be mistaken for a fact about the machine.)
//
// What it draws, worst first:
//   · one line per unwell service — `jv-brain DEGRADED` — in the service's
//     own name, and the schema's own word for its state. Never a
//     friendlier paraphrase, and never a state word the schema does not
//     define; core/HealthState.qml turns anything it cannot read into
//     `unknown` rather than passing it through to a screen.
//   · `+N MORE` when there are more findings than fit. Truncation that
//     does not say it truncated reads as a complete list.
//   · `llm CPU RUNG 4` when the brain is on the CPU floor (invariant 6).
//     No service calls that a fault, so it is not coloured as one — but
//     it is the only thing on this machine that explains a Jarvis which
//     takes thirty seconds to answer.
//
// Colour is the severity and nothing else. Ember never appears: ember
// means Jarvis is doing something (§06), and a service falling over is
// not Jarvis doing something. Nothing pulses — a blinking alarm would
// spend GPU every frame to say what a still dot already says, and §06
// asks for 0 fps when nothing is happening. The only motion is the plate
// arriving and leaving, through `Ease`, which carries the reduced-motion
// switch (A7).
import QtQuick
import "."
import "core"

Item {
  id: root

  // What the heartbeats say. `Bus` is the read-only link (A5): the HUD
  // subscribes and can do nothing else.
  readonly property HealthState health: HealthState {
    bus: Bus
  }

  // How many findings fit before the list becomes a wall. Past this the
  // count is more useful than the names — and the machine has bigger
  // problems than the HUD's typography.
  property int maxLines: 3

  // On screen exactly while there is something to report.
  readonly property bool shown: root.health.reporting

  // True while anything is still drawn, including the fade out, so
  // shell.qml can keep the surface mapped until the plate is really gone.
  readonly property bool lit: plate.opacity > 0

  // One entry per line: { name, detail, tone }. Built as a whole so the
  // rendered list is one atomic thing rather than three Repeaters racing
  // to agree about what is wrong.
  readonly property var lines: {
    const health = root.health;
    let out = [];
    for (const finding of health.findings.slice(0, root.maxLines))
      out.push({
        "name": finding.service,
        "detail": finding.state.toUpperCase(),
        "tone": root.toneOf(finding.severity)
      });
    const hidden = health.findingCount - root.maxLines;
    if (hidden > 0)
      out.push({
        "name": "",
        "detail": "+" + hidden + " MORE",
        "tone": Theme.text3
      });
    if (health.llmOnCpu)
      out.push({
        "name": "llm",
        "detail": health.llmRung >= 0 ? "CPU RUNG " + health.llmRung : "CPU",
        "tone": Theme.warn
      });
    return out;
  }

  // Severity, as colour. The theme spends `risk` only where something is
  // genuinely broken — a service in `error`, or one whose heartbeats
  // stopped — `warn` where it is impaired or unreadable, and nothing at
  // all on a service that is merely starting or shutting down.
  function toneOf(severity: int): color {
    if (severity >= 4)
      return Theme.risk;
    if (severity >= 2)
      return Theme.warn;
    return Theme.text3;
  }

  implicitWidth: plate.implicitWidth
  implicitHeight: plate.implicitHeight

  // A plate answers for itself: it takes room in the stack exactly while it
  // is on screen, so a silenced plate leaves no gap and the ones below it
  // close up. `shown || lit` and not just `lit`, so the plate is in the
  // layout from the first frame of its fade rather than appearing into it.
  // PlateStack reads the same two properties to decide whether the surface
  // is mapped at all (A15) — nothing upstream keeps a list of us.
  visible: root.shown || root.lit

  Rectangle {
    id: plate

    implicitWidth: rows.implicitWidth + Theme.padPx * 2
    implicitHeight: rows.implicitHeight + Theme.padPx * 2
    radius: Theme.radiusPx
    color: Theme.groundDeep
    border.color: Theme.lineSoft
    border.width: Theme.hairlinePx

    // Summon and evaporate (§06). Gone means opacity 0 AND not rendered:
    // an invisible item costs no frames.
    opacity: root.shown ? Theme.plateOpacity : 0
    visible: plate.opacity > 0

    Ease on opacity {
      base: root.shown ? Theme.fadeInMs : Theme.fadeOutMs
    }

    Column {
      id: rows

      anchors.centerIn: parent
      // Half the plate rhythm: these lines are one reading, not a stack
      // of separate plates, and the gap should say so.
      spacing: Theme.gapPx / 2

      Repeater {
        model: root.lines

        Row {
          id: line

          required property var modelData

          spacing: Theme.gapPx

          Rectangle {
            // The same 6 px dot StatePlate and MicPlate use: one HUD, one
            // vocabulary. Here it carries the severity.
            width: 6
            height: 6
            radius: width / 2
            anchors.verticalCenter: parent.verticalCenter
            color: line.modelData.tone
          }

          Text {
            // The service's own name, lowercase, exactly as it is spelled
            // on the bus and in `systemctl` — this line should be
            // copyable into the next thing you type.
            text: line.modelData.name
            color: Theme.text2
            font.family: Theme.familyMono
            font.pixelSize: Theme.labelPx
            font.letterSpacing: Theme.labelPx * Theme.labelTrackingEm
            visible: line.modelData.name.length > 0
          }

          Text {
            text: line.modelData.detail
            color: line.modelData.tone
            font.family: Theme.familyMono
            font.pixelSize: Theme.labelPx
            font.letterSpacing: Theme.labelPx * Theme.labelTrackingEm
          }
        }
      }
    }
  }
}
