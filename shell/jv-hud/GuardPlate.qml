// GuardPlate — the program this machine refused to run (A51).
//
// Invariant 8: a Windows binary is untrusted by default, `jv-guard` screens
// every one of them, and `jv-compat` fails closed on anything that is not
// clean. That refusal is the one moment JarvisOS tells its user NO about
// something they asked for, and it used to happen entirely off screen — a
// terminal error, a verdict on the bus, and a HUD showing the same empty
// corner it shows for a machine nobody has asked to install anything.
//
// The mapping lives next door in core/GuardState.qml, where it is pure
// QtQuick and tested headlessly (the A9 rule); this file is wiring and
// pixels.
//
// §06, and why it looks like this:
//   · severity as colour, never identity — HealthPlate's rule, because
//     this plate is part of the same "something is wrong" family. `risk`
//     for `blocked`, which is final; `warn` for `suspicious`, which the
//     confirmation flow may still override. Never ember: ember means
//     Jarvis is doing something, and this is Jarvis declining to.
//   · REFUSALS only. A clean binary draws nothing — the install carrying
//     on is the report that it passed.
//   · the verdict in the screener's own word, `BLOCKED`, out of a frozen
//     enum. It is the word in `jv-guard`'s log and in
//     schemas/guard.verdict.json, so what you read here is what you can
//     go and grep for.
//   · the file's own name and nothing else of the path. It is the
//     identity a reader needs at a glance, and the rest of the path is
//     more of this filesystem than the question requires on a panel that
//     sits above every window. The name arrives already made safe to draw
//     (GuardState.plainName) because it is the one string in this HUD an
//     attacker chose.
//   · the hash INSTEAD of the name when there is no name, labelled as a
//     hash. Never a blank bright line, which reads as a rendering fault
//     rather than as a missing field.
//   · no reasons. "Matched ClamAV signature X" is what the schema says is
//     spoken on request; a glance tells you a file was refused and which,
//     and asking why is what your voice is for.
//   · nothing counts down and nothing pulses. The only motion is the
//     plate arriving and leaving through `Ease`, which carries the
//     reduced-motion switch with it (A7).
//
// It is a READOUT, like every other plate: the surface takes no keyboard
// and has an empty input region (invariant 10), so there is no "run it
// anyway" button here and there never will be. Overriding a `suspicious`
// verdict goes through the confirmation flow, out loud or through `jv`,
// where jv-act can refuse it.
import QtQuick
import "."
import "core"

Item {
  id: root

  // What the screener made of the last binary it was handed. `Bus` is the
  // read-only link (A5): the HUD subscribes and can do nothing else.
  readonly property GuardState guard: GuardState {
    bus: Bus
  }

  // How wide a file name may be before it elides. The surface is 300 px
  // and the plate sits inside its inset; same number as HeardPlate and
  // ActionPlate, because it is the same box. GuardState caps the name in
  // characters as well — this is the cap a reader sees, that one is the
  // cap on what is carried at all.
  property int maxTextPx: 240

  // The room this plate really HAS, and -1 for as long as nothing has said
  // (PLAN D66). The cap above is a choice about how much of the corner a
  // sentence may take, made for the 300 px surface ares' monitors give it; on
  // an output narrower than that corner the cap alone lays this text out past
  // the left edge of the screen, which is where it cannot be read. Both files
  // that compose the stack hand this down — `shell.qml` from the surface the
  // compositor configured, `tools/hudshots/scene/Corner.qml` from the box its
  // driver renders into — and `tools/tests/test_hudshots.py` fails if a plate
  // that declares a cap is left out of either one.
  property int roomPx: -1

  // The cap, narrowed to that room. The rule is `core/PlateFit.qml` and not a
  // `Math.min` here for one reason `tests/tst_platefit.qml` spells out: an
  // unmeasured room has to leave the cap standing and a room of ZERO has to
  // not, and the naive arithmetic answers both with the same negative number.
  readonly property int textPx: root.fit.textPx(root.maxTextPx, root.roomPx, Theme.padPx)

  // The rule itself, which owns no state and holds no reading.
  readonly property PlateFit fit: PlateFit {}

  // Which plate this is, in one word (A53). The stack collects these
  // so that "something arrived in the corner" can become "THIS plate
  // arrived" — see `litNames` in core/PlateStack.qml.
  readonly property string plateName: "guard"

  // On screen exactly while the last binary screened was refused and the
  // news is still current.
  readonly property bool shown: root.guard.refused

  // True while anything is still drawn, including the fade out, so
  // shell.qml can keep the surface mapped until the plate is really gone.
  readonly property bool lit: plate.opacity > 0

  // What is drawn, held across the fade out. GuardState's outputs go empty
  // the instant a refusal stops being current — correctly, they answer
  // "is this true NOW" — and this is the one plate in the stack whose
  // label is not a constant: `BINARY` with no verdict after it is not a
  // shorter line, it is an unfinished one, and an unfinished line is what
  // a reader would see for the 180 ms of every exit.
  property string heldVerdict: ""
  property string heldFile: ""
  property string heldFingerprint: ""

  // One key for the whole reading, so a second refusal that happens to
  // carry the same verdict word still replaces the name under it. The
  // separator is `\0` — written as an ESCAPE, not as a raw byte: this
  // string joins three attacker-influenced fields, so it needs a joiner
  // none of them can contain, and a source file carrying the byte itself
  // is one git calls binary and diffs as `Bin 8407 bytes`. That is how
  // this whole plate first landed, unreviewable;
  // tools/tests/test_gen_theme_qml.py now refuses it.
  readonly property string liveKey: root.guard.verdict + "\0" + root.guard.file + "\0" + root.guard.fingerprint

  onLiveKeyChanged: {
    if (root.guard.verdict.length === 0)
      return; // the refusal is leaving; keep what is on screen until it has
    root.heldVerdict = root.guard.verdict;
    root.heldFile = root.guard.file;
    root.heldFingerprint = root.guard.fingerprint;
  }

  implicitWidth: plate.implicitWidth
  implicitHeight: plate.implicitHeight

  // A plate answers for itself: it takes room in the stack exactly while
  // it is on screen, so a silent plate leaves no gap and the ones below it
  // close up. PlateStack reads the same two properties to decide whether
  // the surface is mapped at all (A15).
  visible: root.shown || root.lit

  Rectangle {
    id: plate

    implicitWidth: rows.implicitWidth + Theme.padPx * 2
    implicitHeight: rows.implicitHeight + Theme.padPx * 2
    radius: Theme.radiusPx
    color: Theme.groundDeep
    border.color: Theme.lineSoft
    border.width: Theme.hairlinePx

    opacity: root.shown ? Theme.plateOpacity : 0
    visible: plate.opacity > 0

    Ease on opacity {
      base: root.shown ? Theme.fadeInMs : Theme.fadeOutMs
    }

    Column {
      id: rows

      anchors.centerIn: parent
      // Half the plate rhythm: the verdict and the file it is about are
      // one reading, not two stacked plates.
      spacing: Theme.gapPx / 2

      Row {
        spacing: Theme.gapPx

        Rectangle {
          // The same 6 px dot every plate uses: one HUD, one vocabulary.
          // Coloured by severity, like HealthPlate's rows — `blocked` is
          // something stopped, `suspicious` is something impaired.
          width: 6
          height: 6
          radius: width / 2
          anchors.verticalCenter: parent.verticalCenter
          color: root.heldVerdict === "blocked" ? Theme.risk : Theme.warn
        }

        Text {
          // Not "FILE", not "INSTALLER": a binary is what invariant 8 is
          // about and what jv-guard screens, whether it arrived as an
          // installer, a patch or a portable .exe.
          text: "BINARY"
          color: Theme.text2
          font.family: Theme.familyMono
          font.pixelSize: Theme.labelPx
          font.letterSpacing: Theme.labelPx * Theme.labelTrackingEm
        }

        Text {
          // The screener's own word. Upper case like every label in this
          // HUD, and never a friendlier paraphrase: "unsafe" is not a
          // word anybody can look up in schemas/guard.verdict.json.
          text: root.heldVerdict.toUpperCase()
          color: root.heldVerdict === "blocked" ? Theme.risk : Theme.warn
          font.family: Theme.familyMono
          font.pixelSize: Theme.labelPx
          font.letterSpacing: Theme.labelPx * Theme.labelTrackingEm
        }
      }

      Text {
        id: fileText

        // The file's own name, already made safe to draw. The brightest
        // tier, because on the rare occasion this plate is up, WHICH file
        // was refused is the thing the user is here to read.
        text: root.heldFile
        visible: root.heldFile.length > 0
        width: Math.min(fileText.implicitWidth, root.textPx)
        elide: Text.ElideRight
        color: Theme.text
        font.family: Theme.familyMono
        font.pixelSize: Theme.bodyPx
      }

      Text {
        id: shaText

        // The hash, and only when there is no name to show instead —
        // labelled, so twelve hex digits cannot be mistaken for a file
        // called `9f2c4b7a1e08`. This is the identity jv-guard's log uses
        // and the only thing about this file that may ever leave the
        // machine (invariant 7).
        text: "sha256 " + root.heldFingerprint
        visible: root.heldFile.length === 0 && root.heldFingerprint.length > 0
        width: Math.min(shaText.implicitWidth, root.textPx)
        elide: Text.ElideRight
        color: Theme.text3
        font.family: Theme.familyMono
        font.pixelSize: Theme.labelPx
      }
    }
  }
}
