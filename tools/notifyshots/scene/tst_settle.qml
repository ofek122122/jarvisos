// The corner's one animation, measured — because a notification arriving is
// supposed to move ONE plate and this shell moved all of them (PLAN D37).
//
// `Toast.qml` fades its plate up from zero on the frame after it is built, and
// says why in a paragraph: something appearing in a corner you were not
// looking at should read as an arrival rather than as a repaint. That is a
// claim about ONE plate. The plates already on screen are not arriving; they
// have been there for seconds, and the only honest thing for them to do while
// a new one lands is nothing at all.
//
// They did not do nothing. `Notifications.toasts` is a JS array that
// `NotifyModel` REPLACES on every push — it must; a list mutated in place is a
// list no binding hears about — and a `Repeater` handed a new array does not
// diff it. It destroys every delegate and builds new ones, so every plate in
// the corner was a BRAND NEW Toast with `arrived` false, fading up from zero
// again. Three notifications on screen and a fourth arriving meant the whole
// corner blinking, which is the exact opposite of what the fade is for: an
// arrival stops meaning "this one is new" the moment everything does it.
//
// This is the same fault the bar had, in the other direction. There, a
// rebuilt delegate meant an `Ease on color` that never ran (D34); here, a
// rebuilt delegate means a fade that runs when nothing arrived. One cause,
// and one fix: `core/KeyedRows.qml` syncs the row into a ListModel BY THE
// NOTIFICATION'S ID, so a plate whose key is still there keeps its delegate —
// and a delegate that survives keeps `arrived` true and stays where it is.
//
// WHY NO PICTURE CAN HOLD THIS. `docs/notify`'s shots wait past `fadeInMs`
// before they grab, deliberately, so that what lands in a PNG is a settled
// plate — which means a corner that blinked on its way to that frame and a
// corner that never moved develop into byte-identical files. Same for every
// other gate this shell has: `shell/jv-notify/tests` is the model's
// arithmetic with no engine under it, `tools/tests/test_notifyshots.py` reads
// QML as text, and `nix build .#jv-notify` is a linter. All of them pass over
// a plate that blinked. The only observation that can see it is one taken
// DURING the fade, which is what this file is.
//
// Honest about what it is NOT. Not the compositor and not a daemon — the
// records go in through the same stand-in the sheet uses, in the shape the
// real server builds, through the real core/NotifyModel.qml. Not a claim
// about frames or about the 2 ms/frame budget either. One question: when a
// notification arrives, what moves.
import QtQuick
import QtTest
import ".."

Item {
  id: root

  // The surface's own box, derived the way shell.qml derives it — the same
  // expression the sheet's driver uses. Nothing here is about the box; a
  // strip laid out at some other width would simply be a strip nobody has a
  // picture of.
  width: strip.implicitWidth + Theme.insetPx * 2
  height: strip.implicitHeight + Theme.insetPx * 2

  Strip {
    id: strip

    anchors.right: parent.right
    anchors.bottom: parent.bottom
    anchors.margins: Theme.insetPx
  }

  TestCase {
    id: suite

    name: "NotifySettle"
    when: windowShown

    function init() {
      Notifications.reset();
    }

    // One notification, in the shape the real server hands over — the same
    // builder the sheet's driver uses, minus the shot. `key` is explicit here
    // because half of what this file is about is what happens when a key
    // comes back.
    function notify(key, appName, summary) {
      Notifications.send({
        "key": "" + key,
        "appName": appName,
        "summary": summary,
        "body": "",
        "urgency": 1,
        "timeoutMs": -1,
        "handle": null
      });
    }

    // Everything on screen, painted and finished moving. Twice the fade
    // because the wait is a floor and not a promise: `wait` returns no
    // earlier than it was asked to, and a plate one frame short of its target
    // would make every assertion below a coin toss.
    function settled() {
      suite.wait(Theme.fadeInMs * 2);
    }

    // The plates that are up, as the strip paints them. Rounded, because the
    // question is "is this plate where it belongs" and the answer must not
    // depend on the last bit of a float that an easing curve produced.
    function painted(): var {
      return strip.opacities().map(o => Math.round(o * 1000) / 1000);
    }

    readonly property real lit: Math.round(Theme.plateOpacity * 1000) / 1000

    // THE FAULT, and the shape of the observation that can see it. One plate
    // has been on screen long enough to have finished arriving; a second
    // notification lands; the first must not move a pixel while the second
    // fades in.
    //
    // Both halves are needed and neither is enough. Without the moving half
    // this file would pass on a shell where nothing animates at all — where
    // the fade was deleted rather than fixed — and "the old plate did not
    // move" would be true for the wrong reason.
    function test_a_second_notification_fades_only_itself() {
      verify(Motion.animate, "motion is suppressed in this stage, so there is "
             + "nothing here to measure (" + Motion.suppressedBy + ")");

      suite.notify(1, "syncthing", "Folder “photos” is up to date");
      suite.settled();
      compare(strip.shown, 1, "one plate, arrived");
      compare(suite.painted(), [suite.lit], "and painted at the plate tint");

      // A second sender, while the first plate is still up. Oldest first, so
      // index 0 stays the one that was already there.
      suite.notify(2, "nix", "Build finished");
      compare(strip.shown, 2, "two plates now");

      // Sampled ACROSS the fade rather than at one instant: where in the
      // curve a sample lands depends on how long the event loop happened to
      // block, and the claim is about the whole move.
      let arriving = 0;
      const trail = [];
      for (let i = 0; i < 6; i++) {
        suite.wait(Math.round(Theme.fadeInMs / 8));
        const now = suite.painted();
        trail.push(now.join("/"));
        // The plate that was already there. Anything but `lit` is the corner
        // blinking.
        compare(now[0], suite.lit, "the plate that was ALREADY on screen moved to "
                + now[0] + " while a different notification arrived — the "
                + "Repeater rebuilt it, so it is fading in again (samples: "
                + trail.join(" ") + ")");
        if (now[1] > 0 && now[1] < suite.lit)
          arriving += 1;
      }
      console.log("the arrival, sampled: " + trail.join(" "));
      verify(arriving > 0, "the new plate went straight to " + suite.painted()[1]
             + " — nothing faded, so the half of this test that watches the OLD "
             + "plate hold still is passing for the wrong reason");

      suite.settled();
      compare(suite.painted(), [suite.lit, suite.lit], "both plates, arrived");
      compare(strip.captions(), ["normal name summary", "normal name summary"],
              "and both still saying what they were sent");
    }

    // A REPLACEMENT is the case freedesktop has and nothing else does: a
    // sender reuses its own id to update a notification it already sent — a
    // download at 40%, then at 80%. `NotifyModel` keeps it in place in the
    // stack on purpose, because it is one story and not two. That decision is
    // only visible if the PLATE stays too: a replacement that rebuilt the
    // delegate would fade the plate out of and back into existence, which is
    // exactly how a corner says "this is new".
    function test_a_replacement_updates_the_plate_it_is_replacing() {
      suite.notify(7, "firefox", "Downloading jarvis.iso — 40%");
      suite.notify(9, "nix", "Build finished");
      suite.settled();
      compare(strip.shown, 2, "the download and the build");
      compare(suite.painted(), [suite.lit, suite.lit], "both arrived");

      // Same key, new words.
      suite.notify(7, "firefox", "Downloading jarvis.iso — 80%");
      compare(strip.shown, 2, "still two plates — a replacement is not a second one");

      for (let i = 0; i < 6; i++) {
        suite.wait(Math.round(Theme.fadeInMs / 8));
        compare(suite.painted(), [suite.lit, suite.lit],
                "a plate moved while a notification was merely UPDATED — every "
                + "delegate was rebuilt, so the corner blinks on a progress bar");
      }
    }

    // And one going away. A sender withdrawing a notification, or the dwell
    // running out, removes one plate from a column — the others are not
    // arriving, they are simply lower down. Leaving is instant here by design
    // (`Toast.qml` says why: a plate that lingered through a fade-out would be
    // a plate showing a notification that no longer exists), so the only thing
    // to assert is that the survivors hold still.
    function test_a_withdrawal_moves_no_other_plate() {
      suite.notify(1, "syncthing", "Folder “photos” is up to date");
      suite.notify(2, "nix", "Build finished");
      suite.notify(3, "bluetooth", "Headphones connected");
      suite.settled();
      compare(strip.shown, 3, "a full corner");

      // The middle one, so the survivors are on both sides of the hole.
      Notifications.withdraw("2");
      compare(strip.shown, 2, "one fewer");

      for (let i = 0; i < 6; i++) {
        suite.wait(Math.round(Theme.fadeInMs / 8));
        compare(suite.painted(), [suite.lit, suite.lit],
                "a plate faded because a DIFFERENT notification was withdrawn");
      }
      compare(strip.captions(), ["normal name summary", "normal name summary"],
              "the two that were not withdrawn");
    }
  }
}
