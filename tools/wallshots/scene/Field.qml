// Field — the wallpaper's surface, staged for the harness that photographs it
// without a compositor and without Quickshell (PLAN E8).
//
// shell.qml composes this inside a PanelWindow, and it has to: the surface IS
// the layer-shell window, and that file is the Quickshell half no other engine
// can load. So anything that wants to exercise the REAL wallpaper headlessly
// needs a copy of it — and it is here, once, rather than inside the driver, so
// that "the harness draws what the shell draws" is a single claim.
// tools/tests/test_wallshots.py reads the composition out of this file and out
// of shell.qml and fails if the two differ: a field that dropped the glow, or
// anchored the comet somewhere else, would photograph and assert a desktop
// nobody has.
//
// Same three children, same order, same anchors as shell.qml. The two things
// handed in rather than bound are the two that come from Quickshell there: how
// big this output is (`Variants` gives shell.qml a screen; there are no screens
// here) and where the art is (`Quickshell.env("JV_WALL_DIR")`, which the
// wrapper in pkgs/jv-wall sets to the jarvis-wallpaper store path). Everything
// else — the per-output file name, the fallback, the glow, the comet, the
// instrument's anchor — is the shell's own file.
//
// WHAT IT IS NOT. Not the compositor: the BACKGROUND layer, the empty input
// mask, `ExclusionMode.Ignore`, `WlrKeyboardFocus.None` and the
// one-surface-per-monitor `Variants` are shell.qml's, and a human at the
// machine is still the only thing that can confirm them. Not the art either:
// the PNG is rendered from an SVG by pkgs/jarvis-wallpaper and is reproducible
// from this repo — what a sheet of this surface is evidence about is what the
// shell puts OVER it, and where.
import QtQuick
import ".."

Item {
  id: root

  // --- what the shell gets from Quickshell and the harness hands in ----

  // The narrower of the shell's two switches: `JV_MOTION`, the one that stops
  // the wallpaper without telling the rest of the desktop to go still. A
  // property here because it is an environment variable there, and a shot that
  // inherited whoever ran the gate's environment would be a picture of that
  // session rather than of this desktop. "" is the variable unset.
  property string jvMotion: ""

  // May the wallpaper move? shell.qml's expression, with only that read
  // replaced — `Motion.animate` is the REAL generated singleton, reached
  // through the stand-in the harness stages over it, so the still shot on this
  // sheet is the §06 switch working rather than a boolean the driver set.
  readonly property bool motion: Motion.animate && root.jvMotion !== "0"

  // Where pkgs/jarvis-wallpaper's renders are, as an absolute path — the
  // wrapper's `--set JV_WALL_DIR` in the running shell. An absolute path and
  // not a URL, because that is what shell.qml prefixes `file://` onto, and the
  // whole point of this file is that the expression under it is the shell's.
  property string wallDir: ""

  // WHERE THE ART LANDED, which is not always this surface (PLAN E9). Under
  // `PreserveAspectCrop` Qt scales the drawing until it covers the item and
  // centres it, so `paintedWidth`/`paintedHeight` are the size of the SCALED
  // drawing — larger than the surface in one axis by exactly the amount being
  // cropped off both ends of it. Asked of the engine rather than worked out from
  // `sourceSize`, because the question is where the crop actually put the picture.
  //
  // Zero until the Image has one, and then this surface's own size as the
  // stand-in: a first frame with the anchor in the wrong place is a frame with no
  // art under it to be wrong about.
  readonly property real artW: still.paintedWidth > 0
                               ? still.paintedWidth : root.width
  readonly property real artH: still.paintedHeight > 0
                               ? still.paintedHeight : root.height

  // The instrument sits at 73.4% x 68.1% of THE ART, with its outer ring at 39%
  // of the art's shorter side — the three fractions pkgs/jarvis-wallpaper
  // composes every one of its renders to, held to that package by
  // tools/tests/test_wallshots.py. The motion is anchored there so it sits inside
  // the rings, not out on the desk.
  //
  // They used to be fractions of the SURFACE, which is the very same expression
  // whenever the art is this output's own bespoke render — `artW` is then `width`,
  // the overflow is zero and both halves of it vanish — and was 245 px wrong on a
  // 21:9 panel and wrong on every geometry that falls back to the primary art
  // instead (PLAN E9). docs/wall/06-ultrawide.png and 07-fallback.png are the
  // before pictures.
  readonly property real ix: (root.width - root.artW) / 2 + root.artW * 0.734
  readonly property real iy: (root.height - root.artH) / 2 + root.artH * 0.681
  readonly property real ir: Math.min(root.artW, root.artH) * 0.39

  // --- what the harness reads back -------------------------------------

  // Which of pkgs/jarvis-wallpaper's files this output actually resolved, as a
  // bare file name. The per-output choice and the fallback are the same
  // property from two different geometries, and a sheet that only showed the
  // pixels could not tell a bespoke render from the primary art scaled: both
  // are a picture of the same drawing.
  readonly property string art: {
    const s = still.source.toString();
    return s.substring(s.lastIndexOf("/") + 1);
  }

  // Has the art arrived? `asynchronous: true` in the shell, which is right for
  // a surface that must map before it has a picture and wrong for a camera: a
  // grab taken one frame too early is a photograph of an empty field, and it
  // would look exactly like a wallpaper that failed to load.
  readonly property bool artReady: still.status === Image.Ready

  // Is either moving thing on screen at all? One switch decides both, and a
  // wallpaper where half of it obeyed prefers-reduced-motion would be the worst
  // of both — so the sheet asserts them separately and the shell binds them to
  // one property.
  readonly property bool glowDrawn: glow.visible
  readonly property bool cometDrawn: comet.visible

  // The glow's opacity and the comet's rotation as DRAWN, which is the whole of
  // what the phase means on screen. Read off the two elements rather than
  // recomputed here: a caption that re-derived the breath from `phaseMs` would
  // agree with itself forever.
  readonly property real glowOpacity: glow.opacity
  readonly property real lapDeg: comet.rotation

  // Where the comet's head centre landed, in this surface's own pixels — asked
  // of Qt with `mapToItem` rather than worked out here, because the thing worth
  // checking is where the ENGINE put it. This is the one fact about this shell
  // that only a laid-out surface knows, and the claim shell.qml makes in prose:
  // the motion is anchored at the instrument "so it sits inside the rings, not
  // out on the desk". A head drifting around a centre the art does not have, or
  // at a radius the rings do not have, is a wallpaper with two instruments in
  // it — and it would look perfectly plausible in a PNG.
  //
  // A function and not a binding: `mapToItem` reads the transform rather than
  // any property, so a binding would be evaluated once and never again when the
  // phase moved. The driver sets the phase and then asks.
  function headCentre(): point {
    return comet.mapToItem(root, head.x + head.width / 2, head.y + head.height / 2);
  }

  // How far that centre is from the instrument's, which must be `ir` on every
  // shot: the head rides the outer ring and nothing else.
  function headRadius(): real {
    const c = root.headCentre();
    return Math.hypot(c.x - root.ix, c.y - root.iy);
  }

  // …and whether it is on this output at all. It is NOT, for about a third of
  // every lap: the instrument is deliberately three quarters off the bottom
  // right of the art, so the bottom of its ring is below the screen. That is a
  // fact about the composition rather than a fault, and a sheet with no shot of
  // it would be quietly claiming otherwise.
  function headOnScreen(): bool {
    const c = root.headCentre();
    return c.x >= 0 && c.x <= root.width && c.y >= 0 && c.y <= root.height;
  }

  // --- the surface, exactly as shell.qml composes it -------------------

  // The per-output still, rendered at this monitor's exact geometry by
  // pkgs/jarvis-wallpaper — never scaled, never cropped.
  Image {
    id: still
    anchors.fill: parent
    source: "file://" + root.wallDir + "/jarvisos-"
            + Math.round(root.width) + "x" + Math.round(root.height) + ".png"
    fillMode: Image.PreserveAspectCrop
    cache: true
    asynchronous: true
    // A geometry with no bespoke render falls back to the primary art
    // rather than showing nothing.
    onStatusChanged: {
      if (still.status === Image.Error)
        still.source = "file://" + root.wallDir + "/jarvisos.png";
    }
  }

  // ---- the motion, all of it -------------------------------------------

  // The one clock, as a number the driver SETS rather than an animation that
  // runs (PLAN E8, and the paragraph above `phaseMs` in shell.qml). This is the
  // one line of the motion the stage does not copy: there is no
  // `NumberAnimation on phaseMs` here, because a harness that waited for one
  // would be photographing this machine's frame timing. Everything the phase
  // MEANS — both bindings below — is the shell's.
  property real phaseMs: 0

  // 1. the ember glow, breathing (14 s round trip)
  Rectangle {
    id: glow
    x: root.ix - root.ir
    y: root.iy - root.ir
    width: root.ir * 2
    height: root.ir * 2
    radius: glow.width / 2
    visible: root.motion
    // The breath. Dimmest at the start of every 14 s round trip, brightest
    // 7 s in — the value the SequentialAnimation this replaced held at the
    // same instant, for the reason spelled out above `phaseMs`.
    opacity: 0.625 - 0.375 * Math.cos(2 * Math.PI * root.phaseMs / 14000)
    // Ember, fading to the same ember at zero alpha rather than to
    // `transparent` — which is transparent BLACK, and interpolating to it
    // would drag a grey through the middle of the gradient.
    gradient: Gradient {
      GradientStop {
        position: 0.0
        color: Qt.rgba(Theme.ember.r, Theme.ember.g, Theme.ember.b, 0.10)
      }
      GradientStop {
        position: 1.0
        color: Qt.rgba(Theme.ember.r, Theme.ember.g, Theme.ember.b, 0.0)
      }
    }
  }

  // 2. the comet head, drifting around the outer ring (96 s per lap)
  Item {
    id: comet
    x: root.ix
    y: root.iy
    visible: root.motion
    // Drift, not spin: one lap of the outer ring every 96 s, linear,
    // because a head that sped up and slowed down is a thing the eye
    // follows.
    rotation: 360 * (root.phaseMs % 96000) / 96000

    Rectangle {
      id: head
      width: 10
      height: 10
      radius: head.width / 2
      color: Theme.ember
      opacity: 0.85
      x: -head.width / 2
      y: -root.ir - head.height / 2
    }
  }
}
