// InstallPlate — the Windows app that did not get installed (PLAN A52).
//
// jv-compat runs a Windows installer silently, inside a bubblewrapped Wine
// prefix, for as long as that installer takes. It is the longest-running
// thing on this bus and the only one the user walks away from: `jv-compat
// install ~/Downloads/thing.exe` and then back to whatever they were
// doing. When it fails, the report is an exit code in a terminal that is
// no longer on screen — so the HUD, which is, says so instead.
//
// The mapping lives next door in core/InstallState.qml, where it is pure
// QtQuick and tested headlessly (the A9 rule); this file is wiring and
// pixels.
//
// §06, and why it looks like this:
//   · FAILURES only, and so nothing while an install is running. A
//     progress indicator is a shape this HUD does not have, and whether
//     it should is a question for a human (A52) rather than something to
//     arrive by accident. An install that worked is reported by the app
//     being on the machine.
//   · `risk`, never ember. Ember means Jarvis is doing something; this is
//     Jarvis having failed to. Same colour as ActionPlate's failure and
//     GuardPlate's `blocked`, because it is the same family of news.
//   · the app's slug, in the brightest tier, because WHICH app did not
//     install is the one thing the reader is here for. It arrives already
//     believed-or-refused by InstallState — a slug that does not have the
//     shape of a prefix directory name never gets here at all.
//   · the hash INSTEAD of the slug when there is no usable slug, labelled
//     as a hash. Never a blank bright line, which reads as a rendering
//     fault rather than as a missing field.
//   · no error text. The last 500 bytes of a Windows installer's stdout
//     is for the log and for the answer you get when you ask out loud;
//     `core/InstallState.qml` does not even carry it.
//   · nothing counts down and nothing pulses. The only motion is the
//     plate arriving and leaving through `Ease`, which carries the
//     reduced-motion switch with it (A7).
//
// It is a READOUT, like every other plate: the surface takes no keyboard
// and has an empty input region (invariant 10), so there is no "retry"
// button here and there never will be. Installing anything goes through
// jv-compat, which screens first (invariant 8).
import QtQuick
import "."
import "core"

Item {
  id: root

  // What became of the last install jv-compat attempted. `Bus` is the
  // read-only link (A5): the HUD subscribes and can do nothing else.
  readonly property InstallState install: InstallState {
    bus: Bus
  }

  // How wide a slug may be before it elides. The surface is 300 px and the
  // plate sits inside its inset; same number as HeardPlate, ActionPlate
  // and GuardPlate, because it is the same box. InstallState caps the slug
  // in characters as well — this is the cap a reader sees, that one is the
  // cap on what is believed to be a slug at all.
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
  readonly property string plateName: "install"

  // On screen exactly while the last install attempted failed and that is
  // still the news.
  readonly property bool shown: root.install.failed

  // True while anything is still drawn, including the fade out, so
  // shell.qml can keep the surface mapped until the plate is really gone.
  readonly property bool lit: plate.opacity > 0

  // What is drawn, held across the fade out. InstallState's outputs go
  // empty the instant a failure stops being current — correctly, they
  // answer "is this true NOW" — and a plate whose identity line empties
  // 180 ms before the plate does is one that spends its exit saying
  // INSTALL FAILED about nothing at all.
  property string heldApp: ""
  property string heldFingerprint: ""

  // One key for both fields, so a second failure that carries the same
  // hash prefix still replaces the slug above it. The separator is `\0`
  // written as an ESCAPE and never as a raw byte: a source file carrying
  // the byte itself is one git calls binary and diffs as `Bin 8407
  // bytes`, which is how GuardPlate first landed, unreviewable.
  readonly property string liveKey: root.install.app + "\0" + root.install.fingerprint

  onLiveKeyChanged: {
    // The failure is leaving; keep what is on screen until it has. The
    // test is `failed` rather than "are the strings empty", because a
    // failure CAN legitimately have neither — a frame whose slug is not a
    // slug and whose hash is not hex is still an install that failed, and
    // is reported nameless (ActionState's rule for an outcome it cannot
    // attribute) rather than not at all. Those two cases have to be told
    // apart, or a nameless failure would inherit the last one's name.
    if (!root.install.failed)
      return;
    root.heldApp = root.install.app;
    root.heldFingerprint = root.install.fingerprint;
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
      // Half the plate rhythm: the verdict and the app it is about are one
      // reading, not two stacked plates.
      spacing: Theme.gapPx / 2

      Row {
        spacing: Theme.gapPx

        Rectangle {
          // The same 6 px dot every plate uses: one HUD, one vocabulary.
          // `risk` because an install that failed is something stopped,
          // not something impaired.
          width: 6
          height: 6
          radius: width / 2
          anchors.verticalCenter: parent.verticalCenter
          color: Theme.risk
        }

        Text {
          // Not "APP", not "WINE": jv-compat's whole job is the install,
          // and `compat.install` is the topic a reader can go and tap.
          text: "INSTALL"
          color: Theme.text2
          font.family: Theme.familyMono
          font.pixelSize: Theme.labelPx
          font.letterSpacing: Theme.labelPx * Theme.labelTrackingEm
        }

        Text {
          // The schema's own event word, upper case like every label in
          // this HUD — so what you read here is what you can grep for in
          // jv-compat's log and in schemas/compat.install.json.
          text: "FAILED"
          color: Theme.risk
          font.family: Theme.familyMono
          font.pixelSize: Theme.labelPx
          font.letterSpacing: Theme.labelPx * Theme.labelTrackingEm
        }
      }

      Text {
        id: appText

        // The app's slug — the prefix directory name, which is also what
        // you would type to try again. The brightest tier, because on the
        // rare occasion this plate is up, WHICH app is the thing the user
        // is here to read.
        text: root.heldApp
        visible: root.heldApp.length > 0
        width: Math.min(appText.implicitWidth, root.textPx)
        elide: Text.ElideRight
        color: Theme.text
        font.family: Theme.familyMono
        font.pixelSize: Theme.bodyPx
      }

      Text {
        id: shaText

        // The installer's hash, and only when there is no slug to show
        // instead — labelled, so twelve hex digits cannot be mistaken for
        // an app called `9f2c4b7a1e08`. This is the identity jv-guard's
        // log uses and the only thing about this file that may ever leave
        // the machine (invariant 7).
        text: "sha256 " + root.heldFingerprint
        visible: root.heldApp.length === 0 && root.heldFingerprint.length > 0
        width: Math.min(shaText.implicitWidth, root.textPx)
        elide: Text.ElideRight
        color: Theme.text3
        font.family: Theme.familyMono
        font.pixelSize: Theme.labelPx
      }
    }
  }
}
