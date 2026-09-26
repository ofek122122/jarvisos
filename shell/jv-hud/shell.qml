// jv-hud — the JarvisOS heads-up display (blueprint §06, Quickshell/QML).
//
// A layer-shell surface on every monitor under Niri that takes no keyboard
// focus, reserves no screen space, and shows NOTHING unless a real bus
// frame gives it something truthful to say.
//
// Invariant 10 is enforced structurally here, not by convention:
//   · WlrKeyboardFocus.None + focusable:false — the surface CANNOT take
//     the keyboard, so it can never steal focus from your work.
//   · ExclusionMode.Ignore — zero exclusive zone, so no window is ever
//     resized or pushed around by the HUD.
//   · mask: Region {} — an empty input region: every click, scroll and
//     hover passes straight through to the window underneath.
//   · visible is false whenever nothing is on screen. Earned emptiness is
//     the default state, and an unmapped surface costs exactly 0 fps.
//
// And something checks (A10): qmllint only proves that
// `WlrKeyboardFocus.None` RESOLVES — it would be just as happy with
// `.Exclusive`. tools/tests/test_gen_theme_qml.py reads each binding above
// and pins its ONE permitted value — on every Quickshell window in this
// directory, not just this one. It also refuses a HUD file that reaches for
// the keyboard or waits on a pointer the empty mask can never deliver. A
// surface that got any of this wrong would be wrong QUIETLY: the HUD is
// unmapped most of the time, so you would find out by having a click eaten
// or your keyboard taken mid-sentence.
//
// Anything that moves goes through `Ease`/`Motion` (A7), which carries §06's
// reduced-motion switch — so stillness is one setting, not a promise every
// element has to keep on its own.
//
// What it shows today, top to bottom: `LinkPlate` (A23) — the HUD saying
// it has lost sight of the bus, which is the one thing the plates below
// cannot say for themselves (each refuses to guess, and a refusal draws the
// same nothing a calm machine does); `ConfirmPlate` (A20) — the
// destructive action jv-act has stopped in front of, in jv-act's own
// words, readable rather than only audible; `StatePlate` (A3) — what
// jv-voice and jv-ears actually published, idle / listening / speaking /
// interrupted; `OutputPlate` (A40) — that the sink Jarvis is speaking into
// is muted, which is the one way every service can report `ok` while you
// hear nothing; `HeardPlate` (A26) — the words jv-ears took down, for as
// long as Jarvis has not started answering them; `ReplyPlate` (A71) —
// that the answer you just heard was cut off by the context limit, which
// is the one outcome of a turn nothing else on this machine reports;
// `ActionPlate` (A37) —
// what jv-act tried to do to this machine and could not; `GuardPlate`
// (A51) — the Windows binary jv-guard refused to let onto it, which is
// the one time JarvisOS says no to something you asked for;
// `InstallPlate` (A52) — the app jv-compat let through and then could not
// finish installing, which is the one thing on this bus that takes
// minutes and the one the user walks away from; `MicPlate`
// (A4) — whether the microphone is open, from
// jv-ears' own capture counters; and `HealthPlate` (A6) — the services
// that are not well, the llm rung when the brain is on the CPU floor, and
// (B40) how much VRAM is free under it, which is the one thing that tells
// that rung apart from a fault.
// Each one's mapping lives in a tested file under core/, and each draws
// nothing until a real frame gives it something to say, so the ordinary
// state of this surface is unmapped. No element in this shell can display
// a state that did not come off the bus. The camera indicator waits for a
// vision-phase signal to be honest about.
//
// The HUD is a live bus consumer as of A3, so `Bus` is constructed on load
// and its read-only bridge child runs for as long as the shell does. That
// is the cost of telling the truth about the machine; the surface itself
// still maps only when there is something to draw.
import QtQuick
import Quickshell
import Quickshell.Wayland
// The §06 tokens, generated from personality/theme.toml into Theme.qml next
// door (invariant 9: the look is identity, and identity is versioned). No
// QML file in this directory may carry a hex code of its own.
import "."
// The Quickshell-free half (A9): logic and layout that a headless QML test
// can build. `PlateStack` is the corner stack, and the only thing that knows
// whether this surface has anything to show.
import "core"

ShellRoot {
  // One surface per connected monitor. Quickshell.screens is live, so a
  // hotplugged monitor gains a surface without restarting the shell.
  Variants {
    model: Quickshell.screens

    PanelWindow {
      id: surface

      required property var modelData

      // Self-test: `JV_HUD_SELFTEST=1 jv-hud` maps a small marker so a
      // human can confirm the layer-shell surface actually reaches the
      // screen. It reports that the SHELL loaded — never a sensor state,
      // which is why it sits in the corner the real elements do not use.
      readonly property bool selfTest: Quickshell.env("JV_HUD_SELFTEST") === "1"

      screen: modelData

      // Top, not Overlay: the HUD floats over ordinary windows but yields
      // to fullscreen and lock surfaces. It is never the thing in the way.
      WlrLayershell.layer: WlrLayer.Top
      WlrLayershell.namespace: "jv-hud"
      WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
      focusable: false
      exclusionMode: ExclusionMode.Ignore

      anchors {
        top: true
        right: true
      }
      // The edge inset is baked into the surface rather than into
      // `margins`: quickshell's `margins` grouped property has no
      // resolvable type in its qmltypes, and a clean qmllint is worth more
      // than two pixels of layout sugar. The box is the stack of plates
      // plus its inset, with room for the longest line any of them draws —
      // `jv-compat DEGRADED` at 11 px mono — and for the health plate's
      // four rows sitting under the other two. A surface no bigger than
      // what it may ever draw. The height grew with ConfirmPlate (A20),
      // whose question wraps to three 13 px lines above a tool id; its
      // width is capped below this box on purpose (`maxTextPx`), so a long
      // sentence wraps rather than reaching for the middle of the screen.
      // It grew again for LinkPlate (A23), which in practice can never
      // share the surface — every other plate gates on the same link it
      // reports on — but a box sized by an argument about how OTHER
      // elements behave is a box that clips the day one of them changes,
      // and the thing it would clip is the HUD admitting it is blind.
      // And again for HeardPlate (A26), whose transcript wraps to the same
      // three 13 px lines the confirmation does, and which DOES share the
      // surface routinely: the words are up for exactly the stretch
      // `StatePlate` is saying THINKING.
      // And again for GuardPlate (A51) — two lines, 11 px over 13 px —
      // which CAN genuinely share the surface with everything under it: a
      // refused install says nothing about whether a service is unwell or
      // the microphone is open, so this growth is about co-occurrence
      // rather than about margin. Three other files carry this number —
      // both shot harnesses and the sheet's README — and
      // tools/tests/test_hudscreens.py pins the measuring one to this
      // binding, so a box that grows here and nowhere else fails a test
      // rather than quietly cropping a photograph.
      // And again for InstallPlate (A52) — the same two lines GuardPlate
      // draws, and the same argument for the growth: an install that
      // failed says nothing about whether a service is unwell, so the two
      // can genuinely be up together. This is the pair jv-compat can put
      // on screen at once (a refused binary, then a different install
      // that failed), which is exactly the case a box sized by "they
      // never co-occur" would crop.
      //
      // AND THEN SOMETHING MEASURED IT (A63). Every growth above is an
      // ARGUMENT about co-occurrence, written in this comment and checked
      // by nothing: the only fit check that existed ran over the contact
      // sheet, whose tallest picture lights three plates and cleared 688 px
      // by more than five hundred. tools/hudshots/scene/tst_fit.qml builds
      // the case these paragraphs are about — every plate but `link`, each
      // drawing the widest thing its own cap allows, over a health list as
      // long as this machine has services — and that corner was 713 px
      // tall. It did not fit. A layer-shell panel floating over every
      // window was cutting its BOTTOM plate in half, and the bottom plate
      // is `HealthPlate`: the thing that says what is wrong, cropped
      // exactly when everything is.
      //
      // So the height is no longer an argument. It is 2 x insetPx + the
      // measured corner — the same edge gap §06 gives the top and the
      // right, now given to the bottom as well, because a plate ending
      // flush with the edge of a floating panel reads as a crop whether or
      // not it is one. Grow a plate, add a plate, or add a service to this
      // machine and that suite fails with the number of pixels it is over.
      //
      // Which is what ReplyPlate (A71) did: the crowd measured 775 px, 62
      // px more than before — two 11 px rows and the gap above them — so
      // this was 807. The growth is not free and is worth writing down
      // where A70 can read it: the crowded corner is now more than half a
      // 1440p screen, and whether a corner that tall should exist at all
      // is the open question A70 asks, unchanged by this except that the
      // number in it is bigger.
      //
      // And again for the drop row (A75), which is not a new plate: it is
      // one 11 px row and its gap inside `HealthPlate`, so the crowd went
      // 775 -> 794 and this is 826. Worth noting how the growth arrived,
      // because it is the first one that did not come with a plate — a row
      // added to a plate that already exists costs the box exactly as much
      // per line as a plate would, and the suite is what said so rather
      // than a paragraph here guessing.
      // THE WIDTH IS NOT THIS FILE'S ANY MORE (PLAN D16). It is
      // `geometry.hud_corner_px` in personality/theme.toml, because a
      // second process needs it: jv-bar leaves the top-right of its strip
      // empty by exactly this number plus the inset, and it cannot ask —
      // the HUD is another process on another layer, drawing OVER the bar
      // with ExclusionMode.Ignore, so neither surface can detect a clash.
      // While the number lived here, the bar held a copy of it, and the
      // failure was silent both ways round: a plate over the clock, or a
      // bar reserving an emptiness nothing needs. The HEIGHT stays a
      // literal, and the difference is real — the width is a DECLARED
      // choice about how much of the corner Jarvis takes, the height is
      // the MEASURED total of the crowded stack above, owned by the suite
      // that measures it.
      implicitWidth: Theme.hudCornerPx
      implicitHeight: 826
      color: "transparent"
      mask: Region {} // empty: input passes through, always

      // Mapped only while something is genuinely on screen — including
      // while a plate is fading out, or the exit would be a surface
      // vanishing out from under it rather than an element evaporating.
      //
      // The stack answers that question, because a list kept up here does
      // not survive contact with a fourth element (A15): this used to be a
      // hand-written OR with two terms per plate, and the plate that forgot
      // to add itself would simply never have appeared — on a surface that
      // is unmapped on purpose, so nothing would have failed and nothing
      // would have noticed.
      visible: surface.selfTest || stack.anyLit

      // The corner stack. Every plate in it draws nothing until it has
      // something true to say, and makes itself invisible while it has
      // nothing — so an empty plate costs no gap, and the survivors close
      // up rather than leaving a hole where a signal used to be.
      PlateStack {
        id: stack

        anchors.top: parent.top
        anchors.right: parent.right
        anchors.topMargin: Theme.insetPx
        anchors.rightMargin: Theme.insetPx
        spacing: Theme.gapPx

        // Whether this HUD can see the bus at all. First in the stack
        // because it qualifies everything under it: when it is here, the
        // plates below have gone quiet for lack of information rather than
        // for lack of anything happening, and they cannot say so
        // themselves — a refusal and a calm machine draw the same nothing.
        LinkPlate {
          anchors.right: parent.right
        }

        // The question Jarvis is waiting on, from jv-act's own
        // action.confirm. First in the stack because it is the only thing
        // the HUD ever shows that is waiting on YOU, and because its window
        // closes on its own: a plate that appears under three others, in
        // the fifteen seconds you have to answer it, is a plate that was
        // not there. It can only be read — the surface takes no input at
        // all — so answering stays with your voice and `jv confirm`.
        ConfirmPlate {
          anchors.right: parent.right
        }

        // What Jarvis is doing, from speech.state + audio.wake + audio.vad.
        // Draws nothing while idle or while the bus cannot be seen.
        StatePlate {
          anchors.right: parent.right
        }

        // Whether any of what Jarvis is saying is reaching the room, from
        // jv-context's view of the default sink. Directly under the state
        // plate because it qualifies the word immediately above it: with a
        // muted output, SPEAKING is a true frame that adds up to a false
        // impression, and this is the line that says so. On a machine you
        // can hear it is never here at all.
        OutputPlate {
          anchors.right: parent.right
        }

        // What Jarvis heard you say, from jv-ears' own transcript, for as
        // long as the question is still in flight. Directly under the
        // state plate because the two are one reading: that one says
        // Jarvis is thinking, this one says what about. It leaves when the
        // answer starts, which is when the answer itself becomes the
        // better report on whether you were heard correctly.
        HeardPlate {
          anchors.right: parent.right
        }

        // How the last answer ENDED, from jv-brain's own brain.response —
        // and only when the context or token limit cut it off. Directly
        // under the heard line because it closes the sentence those two
        // start: Jarvis is thinking, this is what you asked, and the
        // answer you just heard stops early because it ran out of room.
        // It is the one outcome of a turn with no other route to a
        // screen — a finished reply is its own report, and a brain that
        // could not answer at all already arrives as a degraded
        // heartbeat on the plate at the bottom of this stack.
        ReplyPlate {
          anchors.right: parent.right
        }

        // What came of the last thing Jarvis did to this machine, from
        // jv-act's own action.result — and only when it did not work.
        // Directly under the reply line because it is the end of the same
        // story the plates above tell: Jarvis is doing something, this is
        // what you asked for, and this is why nothing happened. On a
        // machine whose actions all worked it is never here at all.
        ActionPlate {
          anchors.right: parent.right
        }

        // The Windows binary this machine refused to run, from jv-guard's
        // own verdict — and only when it was refused. Directly under the
        // failed action because the two are the same kind of news said by
        // different processes: that one is Jarvis trying to change your
        // machine and failing, this one is Jarvis declining to change it at
        // all. On a machine nobody hands .exe files to it is never here.
        GuardPlate {
          anchors.right: parent.right
        }

        // The Windows app jv-compat could not finish installing, from its
        // own compat.install lifecycle — and only when it failed. Directly
        // under the refused binary because the two are the two halves of
        // invariant 8 said by the two processes that enforce it: that one
        // is a binary that never got to run, this one is a binary that ran
        // inside its prefix and did not work. An install nobody started,
        // or one that worked, draws nothing at all.
        InstallPlate {
          anchors.right: parent.right
        }

        // Whether the microphone is open, from jv-ears' own capture
        // counters. Below the state plate on purpose: what Jarvis is doing
        // changes minute to minute, while the recording light is a
        // standing fact about the room and belongs where it can sit still.
        MicPlate {
          anchors.right: parent.right
        }

        // What is wrong with the machine, when anything is. Last in the
        // stack because it is the one you go and look for rather than the
        // one that catches your eye: the two plates above are about this
        // moment, and this one is about the state of things. On a well
        // machine it is never here at all.
        HealthPlate {
          anchors.right: parent.right
        }
      }

      // WHAT THIS CORNER IS SHOWING, in its own words (PLAN D43).
      //
      // The HUD is unmapped most of the time and draws nothing the rest of
      // it, so until now this machine kept no record of what the corner
      // ever said. "Jarvis never showed me the confirmation" and "Jarvis
      // showed it and I looked away" are the same empty screen afterwards,
      // and the journal had nothing to separate them. This is the surface's
      // own account: one line per change, per monitor, naming the plates
      // that were on it.
      //
      // NAMES ONLY, and that is structural rather than tidy (invariant 7).
      // `plateName` is one word per element — `confirm`, `heard`, `guard` —
      // so what reaches the log is WHICH readings were on screen and never
      // what they said. The words jv-ears took down, the question jv-act
      // asked and the file jv-guard refused all stay inside the process.
      //
      // Per surface, not per shell, because the surfaces can genuinely
      // differ: `Variants` builds one per monitor and each one's plates
      // decide for themselves (D32's fault was a row sized against the
      // wrong monitor). A shell that quietly stopped building a surface for
      // the third screen says so here by never naming it.
      //
      // It is also what makes `ops/ralph/shellload.sh` able to ask whether
      // the plates lit at all (D43): that gate puts a real broker and real
      // frames under a real quickshell, and before this line the only thing
      // it could observe about the result was that nothing threw — which is
      // also what a HUD that ignored every frame looks like.
      Connections {
        target: stack

        function onLitNamesChanged(): void {
          console.info("jv-hud: corner on " + surface.modelData.name + " shows "
            + (stack.litNames.length > 0 ? stack.litNames.join(" ") : "nothing"));
        }
      }

      // Built only under the self-test, in the opposite corner: it is a
      // developer marker, and it must never sit where a sensor state does.
      Loader {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.topMargin: Theme.insetPx
        anchors.leftMargin: Theme.insetPx
        active: surface.selfTest
        sourceComponent: plate
      }

      Component {
        id: plate

        Rectangle {
          implicitWidth: marker.implicitWidth + Theme.padPx * 2
          implicitHeight: marker.implicitHeight + Theme.padPx * 2
          radius: Theme.radiusPx
          color: Theme.ground
          opacity: Theme.plateOpacity
          border.color: Theme.ember // the one accent, used sparingly
          border.width: Theme.hairlinePx

          Column {
            id: marker

            anchors.centerIn: parent
            spacing: 2

            Text {
              text: "jv-hud"
              color: Theme.ember
              font.family: Theme.familyMono
              font.pixelSize: Theme.labelPx
              font.letterSpacing: Theme.labelPx * Theme.labelTrackingEm
            }

            // The state of the HUD's own bus link — a property of this
            // pipe, not of the room. It is NOT a sensor indicator and is
            // never dressed as one: no ember, no dot, just the word.
            Text {
              text: Bus.linkUp ? "bus up" : "bus down"
              color: Bus.linkUp ? Theme.text2 : Theme.text3
              font.family: Theme.familyMono
              font.pixelSize: Theme.labelPx
              font.letterSpacing: Theme.labelPx * Theme.labelTrackingEm

              // §06: ease toward the target, never snap. `Ease` carries
              // the reduced-motion gate with it, so this settles or it
              // assigns instantly — either way it says the same true thing.
              Ease on color {}
            }
          }
        }
      }
    }
  }
}
