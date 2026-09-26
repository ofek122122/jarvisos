// The wallpaper, photographed — and the shell whose sheet was the hardest of
// the four to take, because it is the only one whose subject is a PHASE rather
// than a state (PLAN E8).
//
// The HUD earned a sheet by being the thing that speaks; the notification
// corner earned one by holding strings this repo did not write; the bar earned
// one by being the surface that is always there. This one earns it by being the
// surface that is always there and is NEVER the same twice: 6.5 megapixels
// under every window on the machine, breathing on a 14 s cycle and drifting on
// a 96 s one. Nothing in this repo had ever looked at it. `nix build .#jv-wall`
// runs qmllint over it, `shellload.sh` proves it loads, and neither can say
// where the comet is.
//
// HOW A MOMENT IS NAMED. The other three sheets reach a state by feeding a model
// and waiting for it to settle. There is no settling here — the wallpaper never
// arrives anywhere — so the shell was given one number to move (see `phaseMs` in
// shell.qml, and `tools/tests/test_wallshots.py` for the proof that the two
// bindings hanging off it draw exactly what the two animations they replaced
// drew). Every shot on this sheet is that number, set. Nothing on this sheet
// waits for an animation, which is why the same pixels come out of it on any
// machine.
//
// WHAT IT ASSERTS, beyond being pictures. Per shot: which of
// pkgs/jarvis-wallpaper's renders this output resolved (the per-output choice
// and the fallback are the same property, and no picture can tell a bespoke
// render from the primary art — both are a picture of the same drawing), the
// glow's opacity and the comet's rotation AS DRAWN, and one number that is the
// shell's side of a promise nothing else in this repo can check:
//
//   · `headRadius()`, how far the comet's head sits from the instrument's
//     centre. shell.qml anchors the motion at 73.4% x 68.1% of THE ART "so it
//     sits inside the rings, not out on the desk", and `headRadius` holds the
//     head to that anchor: it must be `ir` on every shot.
//   · `artW` / `artH`, THE SIZE THE ART IS ACTUALLY PAINTED AT on this output,
//     which is what closes the promise above (PLAN E9). It used to be open: the
//     anchor was a percentage of the SURFACE, which is the drawing's centre only
//     while the art is rasterized 1:1 at this output's aspect ratio, and the two
//     last shots on this sheet were pictures of the two coming apart — 245 px on
//     a 21:9 panel, and a head landing beside the painted one on a geometry that
//     falls back. Both halves are fixed: pkgs/jarvis-wallpaper COMPOSES each
//     render at its own geometry instead of cropping one drawing, and the shell
//     takes its anchor from `PreserveAspectCrop`'s painted rect. Asserting that
//     rect is what makes the second half checked rather than described — on six
//     of these shots it is the output's own size, and on the fallback it is a
//     1820x1024 drawing on a 1280x1024 screen, which is a number no surface
//     reading percentages of itself could produce.
//
//     What still cannot be asked HERE is whether the art's own instrument is at
//     those fractions: it is an SVG in another package and this surface cannot
//     see inside a PNG. tools/tests/test_wallshots.py reads the three fractions
//     out of both files and fails if they differ, which is the other half of the
//     same claim.
//
// And one boolean that is a fact rather than a promise: `headOnScreen()`. The
// instrument is deliberately three quarters off the bottom right of the field,
// so for about a third of every lap the head is below the screen and the only
// motion on the desktop is the breath. A sheet with no picture of that would be
// quietly claiming the comet is always there.
//
// THE SHEET IS AT `sheetScale`, and says so. The layout is at each monitor's own
// full size — every number asserted here is in the real surface's pixels — and
// only the CAMERA is scaled down, because seven full-resolution photographs of a
// 2560x1440 field is 6 MB of docs/ that says the same thing as seven small ones.
//
// Honest about what it is NOT:
//   · not the compositor. The BACKGROUND layer, the empty input mask,
//     `ExclusionMode.Ignore`, `WlrKeyboardFocus.None` and the
//     one-surface-per-monitor `Variants` are shell.qml's, and a human at ares is
//     the only thing that can confirm them.
//   · not the art. The PNG under everything here is pkgs/jarvis-wallpaper's,
//     rendered from an SVG in this repo by resvg, and it is the same file the
//     running desktop shows. What this sheet is evidence about is what the shell
//     puts OVER it, and where.
//   · not the frame budget. §06 asks for < 2 ms/frame and 0 fps when idle, and
//     those are measurements a compositor takes (PLAN E6), not pictures.
import QtQuick
import QtTest

Item {
  id: root
  clip: true

  // The monitor this shot is taken on, in pixels, set per shot. The wallpaper
  // fills its output (all four anchors), so the geometry IS the screen's and
  // there is no box for the harness to choose — which is the whole reason
  // `jarvisos-<w>x<h>.png` exists and the reason a sheet of this surface has to
  // be taken at several.
  property int screenW: 2560
  property int screenH: 1440

  // How much of the field a pixel of this sheet is. One half: the shots stay
  // legible — the wordmark is still readable and the comet's head is still a
  // head — at a quarter of the bytes. A number and not a magic constant because
  // tools/tests/test_wallshots.py multiplies by it to check that every
  // committed PNG is the geometry its caption claims.
  readonly property real sheetScale: 0.5

  width: Math.round(root.screenW * root.sheetScale)
  height: Math.round(root.screenH * root.sheetScale)

  Field {
    id: field

    // Laid out at the monitor's own size…
    width: root.screenW
    height: root.screenH
    // …and only then scaled, from the top left so that the pixel at (0,0) of
    // the field is the pixel at (0,0) of the shot.
    transformOrigin: Item.TopLeft
    scale: root.sheetScale

    // Where pkgs/jarvis-wallpaper's renders are. The running shell is told by
    // `--set JV_WALL_DIR` in the wrapper; a QML test cannot read an environment
    // variable, and the only absolute path a QML file knows is its own — so the
    // harness symlinks the store path into the stage next to this directory and
    // this resolves it. `file://` comes off again because that prefix is
    // shell.qml's to add, and Field.qml adds it in the same expression.
    wallDir: Qt.resolvedUrl("../art").toString().replace("file://", "")
  }

  TestCase {
    id: suite

    name: "WallShots"
    when: windowShown

    // --- the sheet --------------------------------------------------------

    // name -> the moment, in reading order. The file names carry the order so a
    // directory listing is the sheet.
    //
    // `motion` is the switch, `phase` is the millisecond of the 672 s lap, and
    // `screen` is the output. `art` is the file this geometry must resolve —
    // asserted, because it is the one thing about this surface a picture cannot
    // show — and `paint` is the size that file is actually PAINTED at here,
    // which is the output's own size on every geometry the package composes for
    // and something else entirely on the one it does not (PLAN E9). `glow` and
    // `lap` are the breath and the drift as DRAWN, to the precision a reader can
    // check against the arithmetic in shell.qml. `onScreen` is whether the head
    // is on this output at all.
    readonly property var sheet: [
      // The desktop under prefers-reduced-motion, which is also the desktop
      // under `JV_MOTION=0` and the desktop this shell replaced: the art, with
      // nothing over it. §06's earned emptiness at its most literal, and the one
      // shot on this sheet where every pixel belongs to pkgs/jarvis-wallpaper.
      { "file": "01-still.png", "motion": false, "phase": 0, "screen": [2560, 1440],
        "art": "jarvisos-2560x1440.png", "paint": [2560, 1440],
        "glow": 0.25, "lap": 0, "onScreen": true },
      // The start of a breath, on ares' primary monitor: the glow at its
      // dimmest, and the comet's head at twelve o'clock — which is exactly where
      // pkgs/jarvis-wallpaper PAINTS a head, at the top of the outer ring of its
      // own instrument. Once every 96 s the moving one passes over the still one
      // and the wallpaper has one comet again. That is not a coincidence to fix;
      // it is what the anchor being right looks like — and until PLAN E9 it was
      // only ever right on THIS shot's aspect ratio.
      { "file": "02-breath-low.png", "motion": true, "phase": 0, "screen": [2560, 1440],
        "art": "jarvisos-2560x1440.png", "paint": [2560, 1440],
        "glow": 0.25, "lap": 0, "onScreen": true },
      // Seven seconds later: the breath at its brightest, which is the most this
      // surface is ever allowed to say. The head has moved 26.25° — a quarter of
      // a minute of arc-drift against a four-times-brighter glow, which is the
      // whole argument for two cycles at these two speeds.
      { "file": "03-breath-peak.png", "motion": true, "phase": 7000, "screen": [2560, 1440],
        "art": "jarvisos-2560x1440.png", "paint": [2560, 1440],
        "glow": 1.0, "lap": 26.25, "onScreen": true },
      // Exactly half the 672 s lap, and the shot that says the quiet part out
      // loud: the head is at six o'clock, which on this composition is 562 px
      // BELOW an instrument centre that is already at 68% of a 1440 px screen.
      // It is off the bottom edge, the only motion left on the desktop is the
      // breath, and that is true for about a third of every lap.
      //
      // 336 s is the one phase where BOTH cycles are at a nameable point at
      // once — 24 whole breaths and three and a half laps — which is the only
      // reason a picture at six o'clock can also be a picture of the breath at
      // its dimmest. Anywhere else the two are incommensurate: at 48 s, the
      // other six o'clock, the glow is at 0.963 and the shot is indistinguishable
      // from the one above it.
      { "file": "04-head-below.png", "motion": true, "phase": 336000, "screen": [2560, 1440],
        "art": "jarvisos-2560x1440.png", "paint": [2560, 1440],
        "glow": 0.25, "lap": 180, "onScreen": false },
      // ares' other two monitors, which are the reason `jarvisos-<w>x<h>.png`
      // exists at all (PLAN D10): swaybg scaling the 1440p art onto a 1080p
      // panel cropped the instrument and the wordmark by an amount nobody chose.
      // This is the same drawing, rasterized for this panel — so the wordmark is
      // whole, and the head is still on the ring.
      { "file": "05-side.png", "motion": true, "phase": 24000, "screen": [1920, 1080],
        "art": "jarvisos-1920x1080.png", "paint": [1920, 1080],
        "glow": 0.708, "lap": 90, "onScreen": true },
      // A geometry pkgs/jarvis-wallpaper renders and nothing about which is 16:9
      // — 21:9, and THE SHOT THAT FOUND SOMETHING and is now the shot that shows
      // it fixed (PLAN E9). It used to be a caption on a defect: the art was one
      // 2560x1440 drawing, `resvg --width 2560 --height 1080` over it rasterized
      // at 1:1 and kept the top 1080 rows, so the drawn instrument stayed at
      // y=980 while the shell anchored at 68.1% of an 1080 px SURFACE (y=735),
      // 245 px away, and the wordmark at y=1330 was not in the file at all. The
      // package now COMPOSES this render at 2560x1080 — same drawing, laid out
      // for this canvas — so the instrument is at 68.1% of it, the wordmark is
      // 110 px up from its own bottom edge, and the comet rides the ring that is
      // actually drawn. ares has no 21:9 panel, and this is the only place the
      // fix can be seen.
      { "file": "06-ultrawide.png", "motion": true, "phase": 7000, "screen": [2560, 1080],
        "art": "jarvisos-2560x1080.png", "paint": [2560, 1080],
        "glow": 1.0, "lap": 26.25, "onScreen": true },
      // And a geometry it does NOT render: 5:4, which is a capture device or an
      // old panel and is not in the package's list. The Image fails, the shell
      // falls back to the primary art and crops it to fit rather than showing a
      // black screen — the one error path this surface has, and one nobody had
      // ever seen. It is ALSO the only shot on this sheet where the art is not
      // painted at the output's own size, which makes it the shot that checks
      // the shell's half of PLAN E9: `PreserveAspectCrop` scales the 2560x1440
      // primary art until it covers a 1280x1024 screen, so 1820x1024 of drawing
      // is painted and 270 px of it is cropped off each side. The anchor is read
      // off THAT rect rather than off the surface — 1066,697 instead of 940,697
      // — which is why the moving head lands on the painted one here and used to
      // land 126 px beside it.
      { "file": "07-fallback.png", "motion": true, "phase": 0, "screen": [1280, 1024],
        "art": "jarvisos.png", "paint": [1820.4, 1024],
        "glow": 0.25, "lap": 0, "onScreen": true }
    ]

    function test_the_sheet() {
      for (let i = 0; i < suite.sheet.length; i++) {
        const shot = suite.sheet[i];

        root.screenW = shot.screen[0];
        root.screenH = shot.screen[1];
        // `JV_MOTION=0` for the still shot. `Motion.animate` is the other way
        // to the same boolean — the declared preference in
        // personality/theme.toml, and `JV_REDUCED_MOTION` — and it is not a
        // switch a harness may throw: the stand-in fixes the session override
        // at "" on purpose, so that no shot on any sheet is a picture of the
        // environment the gate happened to run in.
        field.jvMotion = shot.motion ? "" : "0";
        field.phaseMs = shot.phase;

        // WHICH RENDER THIS OUTPUT GOT. `asynchronous: true` is right for a
        // surface that must map before it has a picture and wrong for a camera:
        // a grab one frame early is a photograph of an empty field, and it looks
        // exactly like a wallpaper that failed to load. The fallback shot passes
        // through Image.Error on the way here, which is the path being
        // exercised rather than a race.
        tryVerify(() => field.artReady, 5000, shot.file + ": the art never loaded");
        compare(field.art, shot.art, shot.file + ": the render this output resolved");

        // …AND AT WHAT SIZE IT LANDED (PLAN E9). The file name says which
        // drawing; this says how much of the surface that drawing actually
        // covers, which is the number the shell's anchor is now read off.
        // `PreserveAspectCrop` scales the source until it covers the item and
        // centres it, so on every geometry the package composes for this is the
        // output's own size and on shot 07 it is 1820x1024 of drawing on a
        // 1280x1024 screen. Asserting it is what stops the anchor quietly going
        // back to being a percentage of the surface: that would still be right
        // on six of these shots and wrong on the seventh, which is exactly the
        // defect this sheet found.
        fuzzyCompare(field.artW, shot.paint[0], 0.5,
                     shot.file + ": the art is painted " + field.artW.toFixed(1)
                     + " px wide");
        fuzzyCompare(field.artH, shot.paint[1], 0.5,
                     shot.file + ": the art is painted " + field.artH.toFixed(1)
                     + " px tall");

        // EITHER BOTH MOVING THINGS ARE DRAWN OR NEITHER IS. One switch, and it
        // is the §06 one: a human who asked this machine for less motion gets
        // the art and nothing over it. Half a wallpaper obeying it would be the
        // worst of both.
        compare(field.glowDrawn, shot.motion, shot.file + ": the glow is drawn");
        compare(field.cometDrawn, shot.motion, shot.file + ": the comet is drawn");

        // THE MOMENT, as the two elements report it rather than as the phase
        // implies it. Two shots of this surface look almost identical — the
        // entire vocabulary is one gradient and one 10 px dot — so without these
        // a harness that set a phase nothing was bound to would photograph a
        // plausible wallpaper and assert nothing.
        //
        // Only where motion is on. On the still shot the caption's `glow`, `lap`
        // and `onScreen` are what the moment WOULD be — phase 0, so the reader
        // can see it is the start of a breath rather than a phase that happens
        // to look still — and nothing on screen is theirs to assert.
        if (shot.motion) {
          fuzzyCompare(field.glowOpacity, shot.glow, 0.001, shot.file + ": the breath");
          fuzzyCompare(field.lapDeg, shot.lap, 0.001, shot.file + ": the drift");

          // AND THE HEAD IS ON THE RING. shell.qml promises the motion sits
          // "inside the rings, not out on the desk" — about a drawing it cannot
          // see, rasterized by another package from an SVG at whatever size this
          // output is. A laid-out surface is the only thing that can check it,
          // and `ir` is the radius the outer ring is at.
          fuzzyCompare(field.headRadius(), field.ir, 0.5,
                       shot.file + ": the head is " + field.headRadius().toFixed(1)
                       + " px from the instrument, which is at " + field.ir.toFixed(1));
          compare(field.headOnScreen(), shot.onScreen,
                  shot.file + ": the head is at " + field.headCentre().x.toFixed(0) + ","
                  + field.headCentre().y.toFixed(0) + " on a "
                  + root.screenW + "x" + root.screenH + " output");
        }

        // The instrument's centre, said out loud rather than pinned: it is a
        // percentage of the ART, and the reason it is worth printing is that
        // pkgs/jarvis-wallpaper composes its own instrument at the same three
        // fractions — so on shots 01-06 this is 73.4% x 68.1% of the output, and
        // on shot 07 it is 1066,697 rather than the 940,697 a percentage of a
        // 1280 px surface would give. A reader comparing those numbers with the
        // ones in the package is reading the E9 fix; a machine comparing them is
        // tools/tests/test_wallshots.py.
        console.log(shot.file + ": the instrument is at " + field.ix.toFixed(0) + ","
                    + field.iy.toFixed(0) + " r" + field.ir.toFixed(0) + " of a "
                    + field.artW.toFixed(0) + "x" + field.artH.toFixed(0)
                    + " drawing on a " + root.screenW + "x" + root.screenH + " output");

        const img = grabImage(root);
        compare(img.width, Math.round(shot.screen[0] * root.sheetScale), shot.file + ": width");
        compare(img.height, Math.round(shot.screen[1] * root.sheetScale), shot.file + ": height");
        // Relative to the process's working directory — ops/ralph/wallshots.sh
        // runs the runner from the output directory, which is how a QML test
        // with no way to read an environment variable is told where to put its
        // files.
        img.save(shot.file);
      }
    }
  }
}
