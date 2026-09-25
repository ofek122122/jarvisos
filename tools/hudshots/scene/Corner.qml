// Corner — the HUD's corner stack, staged for the harnesses that drive the
// real plates without a compositor (PLAN A54).
//
// shell.qml composes this stack inline, and it has to: the stack lives
// inside a PanelWindow, and that file is the Quickshell half no other
// engine can load. So everything that wants to exercise the REAL plates
// headlessly — the contact sheet in tst_shots.qml (A29), the sequence
// replay in tst_sequence.qml (A54) — needs a copy of it, and until this
// file there was one copy per harness.
//
// One copy for all of them, in one place, so that "the harness stacks what
// the shell stacks" is a single claim and not a claim per driver.
// tools/tests/test_hudshots.py reads the plate list out of this file and
// out of shell.qml and fails if the two ever differ — a new plate that
// never reaches a harness would be a new plate nobody looked at, and a
// harness that stacks plates in a different ORDER would photograph and
// assert a corner the user never sees.
//
// Same order, same self-anchoring, same spacing as shell.qml. The position
// on the surface is the consumer's: the sheet needs the plates inset in a
// box the size of the real surface, and the replay does not draw at all.
// Each plate reaches for the `Bus` singleton itself — which in this stage
// is tools/hudshots/stub/Bus.qml — so there is nothing to wire here.
import QtQuick
import ".."
import "../core"

PlateStack {
  spacing: Theme.gapPx

  LinkPlate {
    anchors.right: parent.right
  }

  ConfirmPlate {
    anchors.right: parent.right
  }

  StatePlate {
    anchors.right: parent.right
  }

  OutputPlate {
    anchors.right: parent.right
  }

  HeardPlate {
    anchors.right: parent.right
  }

  ReplyPlate {
    anchors.right: parent.right
  }

  ActionPlate {
    anchors.right: parent.right
  }

  GuardPlate {
    anchors.right: parent.right
  }

  InstallPlate {
    anchors.right: parent.right
  }

  MicPlate {
    anchors.right: parent.right
  }

  HealthPlate {
    anchors.right: parent.right
  }
}
