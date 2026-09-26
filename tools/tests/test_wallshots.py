"""The contact sheet in docs/wall is the wallpaper, or it is worse than nothing.

`ops/ralph/wallshots.sh` renders the real field into PNGs (PLAN E8), the way
`hudshots.sh`, `notifyshots.sh` and `barshots.sh` do for the other three shells,
and by the same two duplications: it STAGES a copy of shell/jv-wall with the one
singleton that imports Quickshell replaced, and it rebuilds shell.qml's surface
in a file a plain QML engine can load.

Both of those drift. The failure mode is specific and silent: shell.qml moves the
instrument's anchor, or drops the glow, and the sheet still renders seven
perfectly good pictures of a desktop that no longer exists. Nothing errors. These
are the gates that make that loud instead.

There is a third thing here the other three harnesses do not need, and it is the
reason this shell was the last to get a sheet. Its subject is a PHASE, not a
state — a wallpaper never arrives anywhere — so the two cycles were rewritten as
bindings on one number the harness can set. `test_the_breath_is_the_curve_it_replaced`
is what makes that a refactor rather than a redesign: it holds the closed form in
shell.qml to a dense sample of the animation pair it replaced, in Python, because
the one deterministic way to compare two easing curves is to compare the curves.
"""

import math
import re
from pathlib import Path

# One parser for this repo's QML, not five.
from test_gen_theme_qml import ROOT, strip_qml_comments
from test_hudshots import members
from test_notifyshots import stack_of

SHELL = ROOT / "shell" / "jv-wall"
SHOTS = ROOT / "tools" / "wallshots"
SHEET = ROOT / "docs" / "wall"

SCENE_DIR = SHOTS / "scene"
SCENE = SCENE_DIR / "tst_shots.qml"
# The surface shell.qml composes inside its PanelWindow, staged where an engine
# without Quickshell can build it.
FIELD = SCENE_DIR / "Field.qml"
SCRIPT = ROOT / "ops" / "ralph" / "wallshots.sh"
# The package that rasterizes the art every shot is mostly made of, and the one
# list of geometries it renders.
ART = ROOT / "pkgs" / "jarvis-wallpaper" / "default.nix"


def scene_text() -> str:
    return SCENE.read_text("utf-8")


def shell_text() -> str:
    return strip_qml_comments((SHELL / "shell.qml").read_text("utf-8"))


def field_text() -> str:
    return strip_qml_comments(FIELD.read_text("utf-8"))


SHEET_ENTRY = re.compile(
    r'\{\s*"file":\s*"(?P<file>[^"]+)"'
    r'.*?"motion":\s*(?P<motion>true|false)'
    r'.*?"phase":\s*(?P<phase>\d+)'
    r'.*?"screen":\s*\[(?P<screen>[^]]*)\]'
    r'.*?"art":\s*"(?P<art>[^"]*)"'
    r'.*?"glow":\s*(?P<glow>[\d.]+)'
    r'.*?"lap":\s*(?P<lap>[\d.]+)'
    r'.*?"onScreen":\s*(?P<onscreen>true|false)',
    re.S,
)


def sheet() -> list[dict]:
    """Each shot as the scene declares it: the file, whether the wallpaper was
    allowed to move, the millisecond of the lap, the output, the render that
    output must resolve, and the breath, the drift and the head as drawn."""
    out = [
        {
            "file": m.group("file"),
            "motion": m.group("motion") == "true",
            "phase": int(m.group("phase")),
            "screen": [int(n) for n in m.group("screen").split(",")],
            "art": m.group("art"),
            "glow": float(m.group("glow")),
            "lap": float(m.group("lap")),
            "onScreen": m.group("onscreen") == "true",
        }
        for m in SHEET_ENTRY.finditer(strip_qml_comments(scene_text()))
    ]
    assert out, "found no sheet entries with an `art` in the scene"
    return out


# ------------------------------------------------- the phase, and the refactor


def in_out_sine(x: float) -> float:
    """Qt's `Easing.InOutSine`, as Qt documents it: -(cos(pi*x) - 1) / 2.

    Written here rather than measured off a running animation on purpose. The
    claim being checked is about two CURVES, and sampling an animation would be
    measuring this machine's frame timing — a test that fails on a loaded
    builder and passes on an idle one is not evidence about the wallpaper.
    """
    return (1.0 - math.cos(math.pi * x)) / 2.0


def test_the_breath_is_the_curve_it_replaced():
    """The whole of what E8 changed about what is on screen, which is nothing.

    The glow used to be a `SequentialAnimation on opacity`: 0.25 -> 1.0 over
    7000 ms with `Easing.InOutSine`, then 1.0 -> 0.25 over 7000 ms with the
    same. It is now a binding on one number, and the arithmetic that makes those
    identical is that InOutSine is symmetric — e(1-x) == 1-e(x) — so the fall is
    the rise read backwards and the whole 14 s round trip is one cosine.

    That is an algebraic claim and this is where it is checked, densely, rather
    than in the QML comment that asserts it. The numbers of the OLD pair are
    written out here because they no longer exist anywhere else in the repo:
    the point of a regression test for a refactor is that it still knows what
    was replaced.
    """
    m = re.search(
        r"opacity:\s*([\d.]+)\s*-\s*([\d.]+)\s*\*\s*Math\.cos\("
        r"2\s*\*\s*Math\.PI\s*\*\s*surface\.phaseMs\s*/\s*(\d+)\)",
        shell_text(),
    )
    assert m, "shell.qml no longer breathes on a cosine of `phaseMs`"
    mid, amp, period = float(m.group(1)), float(m.group(2)), int(m.group(3))

    lo, hi, half = 0.25, 1.0, 7000
    assert period == 2 * half, f"the breath's period is {period} ms, not {2 * half}"
    for step in range(0, period + 1):
        # The pair this replaced, evaluated at the same instant: the rise for
        # the first half of the round trip, the fall for the second.
        t = float(step)
        was = (
            lo + (hi - lo) * in_out_sine(t / half)
            if t <= half
            else hi + (lo - hi) * in_out_sine((t - half) / half)
        )
        now = mid - amp * math.cos(2 * math.pi * t / period)
        assert abs(was - now) < 1e-12, (
            f"at {t:.0f} ms of the breath the animations drew {was:.9f} and the "
            f"binding draws {now:.9f} — the refactor in PLAN E8 changed the look"
        )


def test_the_drift_is_the_rotation_it_replaced():
    """The comet's half, which is the easy one and is here because it is the
    half that would be quietly wrong. `RotationAnimation` is linear by default
    and ran 0 -> 360 over 96000 ms; the binding is that ramp written out. What a
    test adds is the modulo — the phase now runs to the whole lap, so a binding
    that divided by the lap instead of by 96000 would turn the wallpaper's
    comet into something that takes eleven minutes to go round and would look
    entirely plausible."""
    m = re.search(
        r"rotation:\s*360\s*\*\s*\(surface\.phaseMs\s*%\s*(\d+)\)\s*/\s*(\d+)",
        shell_text(),
    )
    assert m, "shell.qml no longer drifts on a linear ramp of `phaseMs`"
    assert m.group(1) == m.group(2) == "96000", (
        f"the comet's lap is {m.group(1)}/{m.group(2)} ms, and it was 96000"
    )


def test_the_lap_is_where_both_cycles_meet():
    """`phaseMs` runs to `lapMs` and wraps. Both cycles have to be back where
    they started at that instant or the wallpaper jumps once every lap — which
    is a glitch nobody would ever catch on a surface that changes this slowly,
    and one a machine can check in one line."""
    m = re.search(r"readonly property int lapMs:\s*(\d+)", shell_text())
    assert m, "shell.qml no longer names the lap the phase runs to"
    lap = int(m.group(1))
    for cycle in (14000, 96000):
        assert lap % cycle == 0, (
            f"the lap is {lap} ms and one cycle is {cycle} ms, so the wrap back to "
            "zero is a jump in it"
        )
    assert lap == math.lcm(14000, 96000), (
        f"the lap is {lap} ms; the two cycles first agree again at "
        f"{math.lcm(14000, 96000)} ms, and anything longer is a phase nobody can name"
    )


def test_the_phase_is_a_number_the_shell_moves_and_the_harness_sets():
    """The seam itself, and both halves of it. The SHELL animates the phase,
    because a wallpaper that stopped moving would be the bug this refactor could
    introduce. The HARNESS does not, because a sheet that waited on an animation
    would be a photograph of this machine's frame timing."""
    assert "NumberAnimation on phaseMs {" in shell_text(), (
        "nothing moves `phaseMs` in the running shell — the wallpaper is frozen"
    )
    assert "NumberAnimation" not in field_text(), (
        "the staged field animates something; every shot on this sheet is a phase "
        "the driver SETS, and an animation under it makes the pixels a race"
    )
    assert "property real phaseMs: 0" in field_text(), (
        "the staged field no longer has a phase for the driver to set"
    )


# ------------------------------------------------------- the staged surface


def test_the_harness_draws_what_the_shell_draws():
    """Field.qml is a copy of shell.qml's surface, and a copy goes stale. An
    element the shell draws and the harness does not is an element nobody has
    ever seen a picture of. The ORDER matters as much as the membership: the art
    is declared first so that it is UNDER the glow and the comet, and a sheet
    that photographed the still on top would be asserting a desktop that is
    simply the wallpaper."""
    shell = stack_of((SHELL / "shell.qml").read_text("utf-8"), "PanelWindow {")
    # The staged field IS the surface, so it is walked from its own root — the
    # same walk over the same shape, rather than a second parser.
    field = stack_of(FIELD.read_text("utf-8"), "Item {")
    assert field == shell, (
        f"tools/wallshots/scene/Field.qml draws {field} but shell.qml draws {shell} "
        "— fix the field, then re-run bash ops/ralph/wallshots.sh"
    )


def test_both_surfaces_anchor_the_motion_at_the_same_place():
    """The three numbers that decide where every moving pixel on this desktop
    goes. They are a percentage of the SURFACE, so they are written twice — once
    per surface — and compared here with the id normalised away. A field that
    anchored its instrument anywhere else would photograph a comet riding a ring
    the real wallpaper's comet does not ride, and every assertion on the sheet
    would agree with it."""
    shell, field = shell_text(), field_text()
    wanted = (
        "readonly property real ix: @.width * 0.734",
        "readonly property real iy: @.height * 0.681",
        "readonly property real ir: Math.min(@.width, @.height) * 0.39",
    )
    for line in wanted:
        assert line.replace("@", "surface") in shell, f"shell.qml no longer says {line}"
        assert line.replace("@", "root") in field, f"the staged field no longer says {line}"


def normalised(text: str, *ids: str) -> str:
    """`text` with the surfaces' own names and their line breaks taken out.

    The two files spell the same expression against different ids — shell.qml
    reaches the wallpaper's directory through `shell` (the ShellRoot) and its
    size through `surface` (the PanelWindow), and the staged field is one object
    and calls itself `root` — and they are indented four levels apart, so a
    continuation line wraps in a different column. Neither difference is
    something a reader of the two would call a difference, and both would make
    an exact comparison fail for a reason nobody should have to debug.
    """
    for name in ids:
        text = text.replace(name + ".", "@.")
    return " ".join(text.split())


def test_both_surfaces_pick_the_same_render_and_fall_back_the_same_way():
    """Which of pkgs/jarvis-wallpaper's files an output gets, and what happens
    when there is not one. This is the only thing on this surface that can fail,
    and both halves are one expression written twice: the per-output name, and
    the `Image.Error` handler that falls back to the primary art rather than
    leaving a black screen. A field that fell back differently would make shot
    07 a picture of the harness."""
    shell = normalised(shell_text(), "shell", "surface")
    field = normalised(field_text(), "root")
    source = (
        'source: "file://" + @.wallDir + "/jarvisos-" '
        '+ Math.round(@.width) + "x" + Math.round(@.height) + ".png"'
    )
    assert source in shell, "shell.qml no longer names its render per output"
    assert source in field, "the staged field picks a different render from the shell"
    fallback = 'still.source = "file://" + @.wallDir + "/jarvisos.png";'
    assert fallback in shell, "shell.qml no longer falls back to the primary art"
    assert fallback in field, "the staged field falls back differently from the shell"


def test_both_surfaces_ask_the_same_switch_whether_to_move():
    """The §06 switch, which is the one decision this surface makes that is not
    geometry. shell.qml asks two sources — `Motion.animate`, the desktop-wide
    gate behind which the declared preference and `JV_REDUCED_MOTION` sit, and
    its own narrower `JV_MOTION` — and the staged field asks the same two with
    only the environment read replaced by a property.

    That replacement is the point and it is the only one allowed. `Motion` is
    the REAL generated singleton here, reached through the stand-in, so the
    still shot on this sheet is the switch working rather than a boolean the
    driver set; a field that had answered `motion` itself would have
    photographed a wallpaper that stops for a reason the real one does not."""
    assert (
        "readonly property bool motion: Motion.animate"
        in normalised(shell_text(), "shell")
    ), "shell.qml no longer asks Motion whether it may move"
    assert 'Quickshell.env("JV_MOTION") !== "0"' in shell_text(), (
        "shell.qml no longer honours its own narrower switch"
    )
    assert (
        'readonly property bool motion: Motion.animate && @.jvMotion !== "0"'
        in normalised(field_text(), "root")
    ), "the staged field decides whether to move differently from the shell"


def test_the_stand_in_offers_everything_the_real_singleton_does():
    """A field reading `Motion.somethingTheStandInForgot` does not error: QML
    hands it `undefined`, `motion` goes falsy, and the shot is a picture of a
    wallpaper with nothing over it — which is a picture this shell is DESIGNED
    to be able to draw (shot 01 is exactly that), so it would look entirely
    right. Missing members have to fail HERE or they never fail at all."""
    real = members(SHELL / "Motion.qml")
    stub = members(SHOTS / "stub" / "Motion.qml")
    assert real <= stub, (
        f"tools/wallshots/stub/Motion.qml is missing {sorted(real - stub)}, which the "
        "field can read on the real one and would see as undefined here"
    )


def test_the_stand_in_replaces_nothing_but_the_quickshell_singleton():
    """The value of the sheet is that everything in it is the real file. Every
    stand-in is one more thing that is not — so there is ONE, which is fewer
    than any other harness in this repo has, because this shell's whole
    vocabulary is the theme and a switch."""
    stubs = sorted(p.name for p in (SHOTS / "stub").glob("*.qml"))
    assert stubs == ["Motion.qml"], (
        f"tools/wallshots/stub holds {stubs}: a second stand-in means a second piece "
        "of this shell the sheet is only pretending to show"
    )
    real = (SHELL / "Motion.qml").read_text("utf-8")
    assert "import Quickshell" in real, (
        "Motion.qml no longer imports Quickshell, so the shot harness can use the "
        "real file and should stop carrying a copy of it"
    )
    staged = strip_qml_comments((SHOTS / "stub" / "Motion.qml").read_text("utf-8"))
    assert "Quickshell" not in staged, (
        "the stand-in for Motion.qml imports Quickshell itself — ONE of those "
        "anywhere in the stage makes the whole directory unimportable"
    )


def test_every_staged_file_is_the_real_one_or_a_declared_stand_in():
    """The script copies the shell verbatim and then writes over exactly one
    file. Anything else it stages is a piece of this wallpaper the sheet is
    showing you a stand-in for without saying so."""
    script = SCRIPT.read_text("utf-8")
    written = set(re.findall(r'cp "\$root/tools/wallshots/stub/(\S+?)" "\$stage/', script))
    assert written == {p.name for p in (SHOTS / "stub").glob("*.qml")}, written
    # And the one file it DELETES, which is the Quickshell half that has no
    # stand-in because the harness rebuilds it as Field.qml instead.
    assert 'rm -f "$stage/shell.qml"' in script


def test_the_art_under_the_sheet_is_the_package_the_desktop_runs():
    """Most of every pixel on this sheet belongs to pkgs/jarvis-wallpaper, and a
    sheet rendered against art from somewhere else — a checked-in PNG, a copy in
    the harness, whatever this machine happens to have in /etc — would be a
    picture of that instead. So the script BUILDS the flake's own attribute and
    links the store path into the stage, and the driver resolves it relative to
    its own file because a QML test cannot read an environment variable."""
    script = SCRIPT.read_text("utf-8")
    assert 'nix build "$root#jarvis-wallpaper"' in script, (
        "the harness no longer builds the art it photographs"
    )
    assert 'ln -s "$art/share/backgrounds" "$stage/art"' in script, (
        "the art is no longer staged where the driver looks for it"
    )
    assert 'Qt.resolvedUrl("../art")' in strip_qml_comments(scene_text()), (
        "the driver no longer finds the art the script staged"
    )


def test_no_driver_keeps_its_own_copy_of_the_surface():
    """One copy of shell.qml's surface, in Field.qml, so that "the harness draws
    what the shell draws" is one claim. A driver that declared an Image or a
    glow itself would be a second surface, and the check above would not see
    it."""
    for driver in sorted(SCENE_DIR.glob("*.qml")):
        if driver == FIELD:
            continue
        stray = re.findall(
            r"^\s*(Image|Gradient|GradientStop)\s*\{",
            strip_qml_comments(driver.read_text("utf-8")),
            re.M,
        )
        assert not stray, (
            f"{driver.name} declares {sorted(set(stray))} itself — compose the "
            "wallpaper in Field.qml, which is the one file pinned to shell.qml"
        )


# ------------------------------------------------------------------ the sheet


def test_every_shot_the_scene_takes_is_committed_and_vice_versa():
    """An uncommitted shot is one nobody can look at without running the
    harness; an orphaned PNG is a picture of a desktop that no longer exists.
    Both are the sheet quietly ceasing to be the sheet."""
    taken = [s["file"] for s in sheet()]
    committed = sorted(p.name for p in SHEET.glob("*.png"))
    assert sorted(taken) == committed, (
        f"the scene takes {sorted(taken)} and docs/wall holds {committed} — run "
        "bash ops/ralph/wallshots.sh and commit the result"
    )


def test_every_shot_is_described_and_shown():
    """A phase is not self-evident. Four of these pictures are the same monitor
    at four moments of one lap and two of them are a defect being photographed —
    a reader who cannot tell which is which is looking at seven pictures of a
    wallpaper. So the README says, per shot, what moment it is and what to look
    at."""
    readme = (SHEET / "README.md").read_text("utf-8")
    sections = readme.split("\n### ")[1:]
    for shot in sheet():
        name = shot["file"]
        shown = [s for s in sections if name in s]
        assert shown, f"docs/wall/README.md never mentions {name}"
        assert len(shown) == 1, f"docs/wall/README.md shows {name} in {len(shown)} sections"
        assert f"![{name}]({name})" in shown[0], (
            f"docs/wall/README.md describes {name} without showing it"
        )


def test_every_committed_shot_is_the_geometry_its_caption_claims():
    """The sheet is taken at half scale and says so, which is a claim about
    every PNG in it: the layout is at the monitor's own full size and only the
    camera is scaled. A shot whose file was any other size would be a picture of
    a monitor nobody named — and the arithmetic is the one thing a reader
    comparing a caption to a picture cannot do by eye."""
    scale = re.search(r"readonly property real sheetScale:\s*([\d.]+)", scene_text())
    assert scale, "the scene no longer says what scale the sheet is at"
    factor = float(scale.group(1))
    for shot in sheet():
        raw = (SHEET / shot["file"]).read_bytes()[16:24]
        width = int.from_bytes(raw[:4], "big")
        height = int.from_bytes(raw[4:], "big")
        assert [width, height] == [round(n * factor) for n in shot["screen"]], (
            f"{shot['file']} is {width}x{height}; its caption says a "
            f"{shot['screen'][0]}x{shot['screen'][1]} output at {factor}"
        )


def test_the_sheet_photographs_the_wallpaper_moving_and_stopped():
    """`motion` has two values and they are the §06 switch: a human who asked
    this machine for less motion gets the art and nothing over it. A sheet with
    no still shot would photograph only the case that is allowed to be
    interesting."""
    moods = {s["motion"] for s in sheet()}
    assert moods == {True, False}, (
        "every shot on this sheet is taken with motion " + str(moods.pop()) + "; the "
        "other one is what prefers-reduced-motion looks like on this desktop"
    )


def test_the_sheet_photographs_the_breath_at_both_ends():
    """The glow spends 14 s going from 0.25 to 1.0 and back, and the two ends
    are the whole range this surface is ever allowed to say. A sheet taken
    entirely in the middle would be a picture of a wallpaper that never
    breathes."""
    glows = sorted(s["glow"] for s in sheet() if s["motion"])
    assert glows[0] == 0.25, f"nothing on this sheet is the breath at its dimmest: {glows}"
    assert glows[-1] == 1.0, f"nothing on this sheet is the breath at its brightest: {glows}"


def test_the_sheet_photographs_the_head_on_the_screen_and_off_it():
    """For about a third of every lap the comet is below the bottom edge of the
    screen and the only motion on the desktop is the breath. That is a fact
    about the composition rather than a fault — the instrument is deliberately
    three quarters off the corner of the art — and a sheet with no picture of it
    would be quietly claiming the comet is always there."""
    places = {s["onScreen"] for s in sheet() if s["motion"]}
    assert places == {True, False}, (
        "every moving shot on this sheet has the comet on screen; the lap takes it "
        "off the bottom for a third of every 96 s and nothing here shows that"
    )


def test_the_sheet_photographs_every_output_ares_really_has():
    """The wallpaper fills its output, so the GEOMETRY is the one thing about
    this surface a harness cannot choose for itself: it decides which of
    pkgs/jarvis-wallpaper's renders is used and where the instrument lands. ares
    has two sizes and the sheet has to actually be taken at both."""
    shapes = {tuple(s["screen"]) for s in sheet()}
    assert {(2560, 1440), (1920, 1080)} <= shapes, (
        f"the sheet is taken at {sorted(shapes)}; ares' own monitors are 2560x1440 "
        "and 1920x1080"
    )


def test_every_render_a_shot_claims_is_one_the_package_makes():
    """The captions name a file in another package's output, and that is the one
    assertion on this sheet nothing on screen can check — a bespoke render and
    the primary art scaled are pictures of the same drawing. So the names are
    held to pkgs/jarvis-wallpaper's own list: a shot claiming a geometry the
    package stopped rendering would assert forever against a fallback."""
    art = ART.read_text("utf-8")
    geoms = re.search(r"for geom in ([\d x]+); do", art)
    assert geoms, "pkgs/jarvis-wallpaper no longer lists the geometries it renders"
    rendered = {f"jarvisos-{g}.png" for g in geoms.group(1).split()}
    rendered.add("jarvisos.png")  # the primary art, which is also the fallback
    for shot in sheet():
        assert shot["art"] in rendered, (
            f"{shot['file']} claims {shot['art']}, and pkgs/jarvis-wallpaper renders "
            f"{sorted(rendered)}"
        )
        # …and the claim has to match the output, or the caption is just a
        # string that happens to be in the list.
        bespoke = f"jarvisos-{shot['screen'][0]}x{shot['screen'][1]}.png"
        expected = bespoke if bespoke in rendered else "jarvisos.png"
        assert shot["art"] == expected, (
            f"{shot['file']} is a {shot['screen'][0]}x{shot['screen'][1]} output, which "
            f"resolves {expected}, and its caption says {shot['art']}"
        )


def test_the_sheet_photographs_a_geometry_the_package_does_not_render():
    """The one error path this surface has. An output with no bespoke render
    makes the Image fail, and the shell falls back to the primary art rather
    than showing a black screen — a handler nobody had ever seen fire. A sheet
    of only supported geometries would be a sheet of the case that cannot
    fail."""
    fell_back = [s for s in sheet() if s["art"] == "jarvisos.png"]
    assert fell_back, (
        "every shot on this sheet is a geometry pkgs/jarvis-wallpaper renders, so "
        "nothing photographs the fallback"
    )
