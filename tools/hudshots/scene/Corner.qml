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
  id: corner

  spacing: Theme.gapPx

  // The room the plates have, worked out the way shell.qml works it out (PLAN
  // D66). It is here rather than in the three drivers for the same reason the
  // plate list is: one claim about what the harnesses stack, not one per
  // driver. Each driver anchors this stack into an Item the size of the real
  // surface and sets those margins itself, so the box is simply the parent's
  // width, less the inset it is anchored by at each edge — clamped at zero,
  // and zero kept distinct from "no parent at all", for the reason shell.qml
  // spells out beside its own copy of this: a bare subtraction turns a surface
  // with no room into a surface nobody has measured, and `core/PlateFit.qml`
  // answers those two with opposite widths.
  readonly property int plateRoomPx: corner.parent !== null && corner.parent.width > 0
    ? Math.max(0, corner.parent.width - Theme.insetPx * 2)
    : -1

  LinkPlate {
    anchors.right: parent.right
    roomPx: corner.plateRoomPx
  }

  ConfirmPlate {
    anchors.right: parent.right
    roomPx: corner.plateRoomPx
  }

  StatePlate {
    anchors.right: parent.right
  }

  OutputPlate {
    anchors.right: parent.right
  }

  HeardPlate {
    anchors.right: parent.right
    roomPx: corner.plateRoomPx
  }

  ReplyPlate {
    anchors.right: parent.right
  }

  ActionPlate {
    anchors.right: parent.right
    roomPx: corner.plateRoomPx
  }

  GuardPlate {
    anchors.right: parent.right
    roomPx: corner.plateRoomPx
  }

  InstallPlate {
    anchors.right: parent.right
    roomPx: corner.plateRoomPx
  }

  MicPlate {
    anchors.right: parent.right
  }

  HealthPlate {
    anchors.right: parent.right
  }
}
