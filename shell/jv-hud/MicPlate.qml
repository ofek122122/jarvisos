// MicPlate — the live-microphone indicator (A4).
//
// Invariant 10: the mic indicator is not optional and not fakeable. This
// file is the "not optional" half — it is on screen for as long as the
// device is open, whether or not Jarvis is listening to you, whether or
// not anyone is talking. The "not fakeable" half is next door in
// core/MicState.qml, which will not say a microphone is open unless
// jv-ears published counters proving the device delivered audio.
//
// It deliberately says nothing about attention. StatePlate's "listening"
// is Jarvis attending to you; this is the room being recorded. jv-ears
// runs its VAD continuously, so the two are on screen at different times
// and neither is derived from the other.
//
// §06, and why it looks like this:
//   · a closed microphone draws NOTHING. Earned emptiness: silence needs
//     no badge, and a dark indicator is the honest picture of a dark mic.
//     So does `unknown` — a HUD that cannot see the bus says nothing at
//     all rather than inventing reassurance.
//   · teal, not ember. theme.toml reserves ember for Jarvis doing
//     something; an open microphone is YOUR state, the same reasoning
//     that made listening teal.
//   · nothing pulses. A breathing dot would spend GPU every frame to say
//     what a still one already says, and §06 asks for 0 fps when nothing
//     is happening. The only motion here is the plate arriving and the
//     colour moving, both through `Ease`, which carries the reduced-motion
//     switch (A7) so neither can escape it.
//   · `warn`, not `risk`, for a stalled device: the theme spends those
//     colours only where something is genuinely degraded, and an open mic
//     delivering nothing is exactly that — still recording as far as the
//     OS is concerned, and deaf. A microphone dropping chunks takes the
//     same colour for the same reason (A84): it is recording the room
//     with holes in it, which is not the teal this plate reserves for a
//     recording anyone should trust.
import QtQuick
import "."
import "core"

Item {
  id: root

  // How jv-ears is tuned, as jv-ears reports it (A14) — the budget below
  // is ears', not a number this file decided on.
  readonly property EarsBudgets ears: EarsBudgets {
    bus: Bus
  }

  // What jv-ears' heartbeat says about the device. `Bus` is the read-only
  // link (A5): the HUD subscribes and can do nothing else.
  readonly property MicState mic: MicState {
    bus: Bus
    stallS: root.ears.stallS
    lossWindowS: root.ears.lossWindowS
  }

  // Which plate this is, in one word (A53). The stack collects these
  // so that "something arrived in the corner" can become "THIS plate
  // arrived" — see `litNames` in core/PlateStack.qml.
  readonly property string plateName: "mic"

  // On screen exactly while the microphone is open — capturing (whole or
  // with holes in it) or stalled. `off` and `unknown` are both silence,
  // for different reasons.
  readonly property bool shown: root.mic.capturing || root.mic.stalled

  // True while anything is still drawn, including the fade out, so
  // shell.qml can keep the surface mapped until the plate is really gone.
  readonly property bool lit: plate.opacity > 0

  // Teal: audio is being captured, all of it. Warn: the device is open
  // and either silent or losing chunks — one colour for "this recording
  // is not what you think it is", because from where the user sits those
  // are the same warning, and the word beside the dot says which.
  readonly property color dotColor: root.mic.stalled || root.mic.losing ? Theme.warn : Theme.teal

  // The one line this plate says. "MIC" alone is the recording light; a
  // second word appears only when there is a second thing to say, and it
  // says what is wrong rather than dressing it up. Only one can be true
  // at a time — MicState ranks them, so the plate never has to.
  readonly property string label: root.mic.stalled ? "MIC NO AUDIO" : root.mic.losing ? "MIC LOSING AUDIO" : "MIC"

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

    implicitWidth: row.implicitWidth + Theme.padPx * 2
    implicitHeight: row.implicitHeight + Theme.padPx * 2
    radius: Theme.radiusPx
    color: Theme.groundDeep
    border.color: Theme.lineSoft
    border.width: Theme.hairlinePx

    opacity: root.shown ? Theme.plateOpacity : 0
    visible: plate.opacity > 0

    Ease on opacity {
      base: root.shown ? Theme.fadeInMs : Theme.fadeOutMs
    }

    Row {
      id: row

      anchors.centerIn: parent
      spacing: Theme.gapPx

      Rectangle {
        // The same 6 px dot StatePlate uses: one HUD, one vocabulary.
        width: 6
        height: 6
        radius: width / 2
        anchors.verticalCenter: parent.verticalCenter
        color: root.dotColor

        // The colour moves only because the microphone's state moved.
        Ease on color {}
      }

      Text {
        text: root.label
        color: Theme.text2
        font.family: Theme.familyMono
        font.pixelSize: Theme.labelPx
        font.letterSpacing: Theme.labelPx * Theme.labelTrackingEm
      }
    }
  }
}
