// The notification corner, photographed — because this is the one surface on
// this machine whose CONTENT comes from programs this repo did not write
// (PLAN D20).
//
// Every other surface JarvisOS draws is fed by the bus, and the bus is
// schema'd: `schemas/` says what a frame may contain and jarvisd refuses
// anything else. A notification is the opposite. Any process with a D-Bus
// session can call `Notify` with any string of any length in any script, and
// the plate it lands on floats over every window on the machine. So "what does
// a toast do with a 4000-character summary, an app name that is one unbroken
// 120-character word, a body full of `<img>` tags, or three criticals at once"
// is not a hypothetical — it is Tuesday — and until this file the only answer
// was qmllint's, which is that the QML parses.
//
// What it DOES assert, per shot, is the caption: which plates are up, in
// stacking order, and what each one says it drew — the urgency as a word, the
// rows that are really there, and whether a row had to ELIDE
// (`Toast.drew`). That last one is the whole point of the long shots: a
// summary that overflowed its two lines and a summary that fit look identical
// in every test that is not a picture, and the difference is whether the plate
// is a plate or a wall.
//
// Honest about what it is NOT:
//   · not the compositor. Layer-shell, the empty input mask, the zero
//     exclusive zone, the unmapped-when-empty surface and the three monitors
//     are shell.qml's, and nothing here exercises them. This is the CONTENT of
//     one surface.
//   · not a daemon. There is no D-Bus session here: the records go in through
//     the stand-in next door, in the same shape the real server builds, and
//     through the real core/NotifyModel.qml. What a real sender's bytes turn
//     into on the wire is Quickshell's, not ours.
//   · not a recording. Nothing in this repo has ever recorded a real
//     notification (there is no fixture format for one), so every shot here is
//     composed — which docs/notify/README.md says, per shot, because a
//     composed picture presented as a capture is worse than no picture.
import QtQuick
import QtTest
import ".."

Item {
  id: root

  // THE SURFACE'S OWN BOX, derived exactly as shell.qml derives it:
  // `stack.implicitWidth + inset*2` by `stack.implicitHeight + inset*2`. So
  // every PNG on this sheet is the size the compositor would actually map, and
  // the sheet is a picture of the surface rather than of the stack sitting in
  // the middle of a canvas somebody chose.
  //
  // That is the one structural difference from the HUD, whose 300x826 box is
  // fixed and had to be MEASURED after a crowded corner turned out to be cut
  // in half (A63). A surface sized by its own content cannot crop its own
  // bottom plate — so there is no fit test here, and instead the shot asserts
  // that the box really is derived: a plate wider than the box would be a
  // plate drawing over the desktop beside it.
  width: strip.implicitWidth + Theme.insetPx * 2
  height: strip.implicitHeight + Theme.insetPx * 2

  // NOT the corner. The real surface is `color: "transparent"` and floats over
  // whatever Niri has on screen; a PNG has to put something behind the plates
  // or the translucency (`plate_opacity = 0.86`) is invisible and the sheet
  // renders on whatever background a browser feels like. The same flat neutral
  // grey the HUD's sheet uses, deliberately not a theme token — a colour that
  // appeared in personality/theme.toml would be a colour a reader could
  // mistake for Jarvis's. tools/tests/test_notifyshots.py holds that line.
  readonly property color backdrop: "#31353B"

  Rectangle {
    anchors.fill: parent
    color: root.backdrop
  }

  // The stack, as shell.qml composes it, where shell.qml puts it: bottom
  // right, one inset in from both edges. Oldest first, so the newest plate is
  // the one nearest the corner.
  Strip {
    id: strip

    anchors.right: parent.right
    anchors.bottom: parent.bottom
    anchors.margins: Theme.insetPx
  }

  TestCase {
    id: suite

    name: "NotifyShots"
    when: windowShown

    property int nextId: 0

    // --- senders ------------------------------------------------------

    // One notification, in the shape `Notifications.take()` builds from a real
    // `Notification` object. Every field is the sender's except `key`, which is
    // its id: a second send under the same key is a replacement, which is why
    // the default is a fresh one every time.
    function notify(appName, summary, body, urgency, timeoutMs, key) {
      Notifications.send({
        "key": key === undefined ? "" + suite.nextId++ : "" + key,
        "appName": appName,
        "summary": summary,
        "body": body === undefined ? "" : body,
        "urgency": urgency === undefined ? 1 : urgency,
        "timeoutMs": timeoutMs === undefined ? -1 : timeoutMs,
        "handle": null
      });
    }

    // freedesktop's urgency numbers, spelled out for the same reason the model
    // spells them out: a bare 2 in a shot builder is a number nobody can check.
    readonly property int low: 0
    readonly property int normal: 1
    readonly property int critical: 2

    // `n` copies of `unit`, for the strings this sheet exists to ask about.
    // Built rather than pasted: a 4000-character literal in a QML file is a
    // file nobody can read, and the LENGTH is the whole content of the shot.
    function rep(unit, n) {
      let out = "";
      for (let i = 0; i < n; i++)
        out += unit;
      return out;
    }

    // --- shots --------------------------------------------------------

    // The ordinary one, and the reason there is no `quiet` shot on this sheet:
    // an empty corner is an UNMAPPED surface (`visible: Notifications.anyLit`),
    // which is not a picture of anything. The first thing to photograph here is
    // one notification, from one program, saying one thing.
    function shot_one() {
      suite.notify("Firefox", "Download finished", "nixos-25.11-minimal-x86_64.iso — 892 MB");
    }

    // Low urgency and nothing under the summary. Two §06 rules in one picture:
    // the dot goes to `text_3` (the quietest of the three readings), and a body
    // the sender did not send is ABSENT rather than an empty line — so a
    // one-line notification is a one-line plate.
    function shot_low() {
      suite.notify("Spotify", "Now playing — Talk Talk, It's My Life", "", suite.low);
    }

    // The one urgency that gets a colour of its own, and the one thing allowed
    // to stay until it is withdrawn (`dwellMsFor` returns 0 for Critical). The
    // `risk` dot is a sender saying something is wrong — and it is deliberately
    // NOT the ember: every process on this machine can send this, and the
    // accent belongs to the one publisher that cannot be impersonated.
    function shot_critical() {
      suite.notify("smartd", "Drive failing self-test", "/dev/sdb: 2 reallocated sectors since 03:14", suite.critical);
    }

    // The corner exactly full: three plates, the cap. Oldest at the top,
    // newest nearest the corner, which is the shortest distance from where a
    // message appears to where the last one did.
    function shot_three() {
      suite.notify("Element", "ofek: are you seeing the same build failure?", "", suite.low);
      suite.notify("Steam", "Half-Life: Alyx finished installing", "108.4 GB on /games");
      suite.notify("systemd", "jv-ears.service entered failed state", "Restarting in 5 s (3 of 5)", suite.critical);
    }

    // Five sent, three shown. The `+2 EARLIER` line above the stack is the one
    // thing a capped corner owes the person reading it: a cap nobody is told
    // about is indistinguishable from a daemon that dropped their notification.
    function shot_earlier() {
      for (let i = 1; i <= 5; i++)
        suite.notify("git-sync", "Pushed " + i + " commits to origin/ralph/auto", "");
    }

    // THE QUESTION THIS SHEET EXISTS FOR. A sender that formatted its text for
    // a dialog box: 4000 characters of summary and 1200 of body. §06 gives a
    // glance two lines and three, then an ellipsis — and `Toast.drew` reports
    // `summary…`/`body…` only if `Text.truncated` says the elide really
    // happened, so this shot is the assertion that a plate cannot grow to the
    // height of the screen no matter what is sent to it.
    function shot_long() {
      suite.notify("Thunderbird",
                   suite.rep("Re: the quarterly figures, as discussed at some length. ", 66),
                   suite.rep("Sent from a device that does not know what a summary is. ", 21));
    }

    // A sender that left `app_name` empty — which apps do, and which is why the
    // name row is `visible: appName.length > 0`. An anonymous notification says
    // so by having no name, not by showing the word "unknown": the dot sits
    // alone on the top row and the summary is the first thing read.
    function shot_no_name() {
      suite.notify("", "Backup completed", "restic: 4 new snapshots, 12.1 GB");
    }

    // `bodyMarkupSupported: false`, in pixels. The daemon tells every sender it
    // does not do markup; `Text.PlainText` is what makes that true, so an
    // `<img>` from a stranger is five characters on a plate rather than a
    // fetch. The whitespace in the same string is the other half: `oneLine`
    // collapses the tabs and newlines a dialog was formatted with, so a
    // glance-sized plate shows a sentence instead of two words and a lot of
    // air.
    function shot_markup() {
      suite.notify("some-app", "<b>URGENT</b> — click <a href=\"http://example.invalid\">here</a>",
                   "line one\n\n\tline two, indented\n<img src=\"http://example.invalid/track.gif\">");
    }

    // AN APP NAME THAT CANNOT BE BROKEN: 120 characters with no space in them,
    // which is what a badly-behaved sender puts in `app_name` (a reverse-DNS
    // id, a whole command line, a stack frame). The name row is the one line on
    // this plate with no wrap and no width of its own, so if this drew past the
    // plate's edge the corner would be painting on the desktop beside it — and
    // the assertion that it does not is `width` in the caption below.
    function shot_long_name() {
      suite.notify(suite.rep("org.freedesktop.impl.portal.desktop.", 3) + "Notifier",
                   "Permission requested", "Screen sharing — Firefox");
    }

    // Text this repo did not choose the shape of: combining marks stacked past
    // what a line box expects (the "Zalgo" case), in the name AND the summary.
    // A notification is the one surface where a stranger picks the codepoints,
    // and a mono font with a fixed line height is where that shows.
    function shot_combining() {
      const zalgo = "n͓̥ͯo͓͏t͓͈i͓ͦc͓͈e͓͟";
      suite.notify(zalgo, zalgo + " " + zalgo, zalgo);
    }

    // --- the sheet ----------------------------------------------------

    // name -> builder, in reading order. The file names carry the order so a
    // directory listing is the sheet.
    //
    // `plates` is the CAPTION, asserted: one entry per plate on screen, in
    // stacking order (oldest first, newest nearest the corner), each one the
    // plate's own account of what it drew. `earlier` is the `+N EARLIER` line
    // as drawn, "" when there is none.
    readonly property var sheet: [
      { "file": "01-one.png", "build": suite.shot_one, "earlier": "", "plates": ["normal name summary body"] },
      { "file": "02-low.png", "build": suite.shot_low, "earlier": "", "plates": ["low name summary"] },
      { "file": "03-critical.png", "build": suite.shot_critical, "earlier": "", "plates": ["critical name summary body"] },
      { "file": "04-three.png", "build": suite.shot_three, "earlier": "", "plates": ["low name summary", "normal name summary body", "critical name summary body"] },
      // Five sent under five keys, so five plates are TRACKED and three are
      // drawn. All three captions identical is the point of the line above
      // them: without it these two shots would look like the same corner.
      { "file": "05-earlier.png", "build": suite.shot_earlier, "earlier": "+2 EARLIER", "plates": ["normal name summary", "normal name summary", "normal name summary"] },
      // BOTH ellipses, and they are the assertion. `summary…` means
      // `Text.truncated` is true — the two-line maximum and the elide really
      // stopped 4000 characters — and `body…` says the same of the three-line
      // one. A plate that grew instead would say `summary body` here and look,
      // in a PNG, like a picture of a lot of text.
      { "file": "06-long.png", "build": suite.shot_long, "earlier": "", "plates": ["normal name summary… body…"] },
      // No `name` in the caption: the row is gone, not blank.
      { "file": "07-no-name.png", "build": suite.shot_no_name, "earlier": "", "plates": ["normal summary body"] },
      { "file": "08-markup.png", "build": suite.shot_markup, "earlier": "", "plates": ["normal name summary body"] },
      { "file": "09-long-name.png", "build": suite.shot_long_name, "earlier": "", "plates": ["normal name summary body"] },
      { "file": "10-combining.png", "build": suite.shot_combining, "earlier": "", "plates": ["normal name summary body"] }
    ]

    function test_the_sheet() {
      for (let i = 0; i < suite.sheet.length; i++) {
        const shot = suite.sheet[i];

        Notifications.reset();
        suite.nextId = 0;
        shot.build();

        // Past the one animation in this shell — the arrival fade — plus the
        // ease, so the grab lands on a settled plate rather than inside a
        // fade-up. Nothing here pulses (that is the HUD's open microphone), so
        // this sheet settles in a third of a second per shot rather than the
        // HUD's two.
        wait(Theme.fadeInMs + Theme.easeMs);

        // WHAT IS ON SCREEN, as the plates themselves report it. A PNG of one
        // plate looks almost exactly like a PNG of another: the whole
        // vocabulary is a dot, a name and two paragraphs, so a harness that
        // sent a record the model refused would photograph a plausible corner
        // and assert nothing. This line is what says the picture is a picture
        // OF something.
        compare(strip.captions().join(" · "), shot.plates.join(" · "),
                shot.file + ": the plates on screen");
        compare(strip.shown, shot.plates.length, shot.file + ": how many plates");
        compare(strip.earlierText, shot.earlier, shot.file + ": the EARLIER line");

        // AND EVERY PLATE IS INSIDE ITS OWN BORDER. The surface is only as
        // wide as the stack says it is, and the stack is as wide as its widest
        // plate — so a row that painted past its plate would paint past the
        // surface, onto the desktop, on a panel with no input region that
        // nothing can move. `09-long-name.png` is the shot that asks.
        const over = strip.overflows();
        for (let p = 0; p < over.length; p++) {
          compare(over[p], 0, shot.file + ": plate " + p + " paints "
                  + over[p] + " px past its own edge");
        }
        verify(strip.implicitWidth + Theme.insetPx * 2 === root.width,
               shot.file + ": the surface is " + root.width + " px for a "
               + strip.implicitWidth + " px stack");

        const img = grabImage(root);
        compare(img.width, root.width, shot.file + ": width");
        compare(img.height, root.height, shot.file + ": height");
        // Relative to the process's working directory —
        // ops/ralph/notifyshots.sh runs the runner from the output directory,
        // which is how a QML test with no way to read an environment variable
        // is told where to put its files.
        img.save(shot.file);
      }
    }
  }
}
