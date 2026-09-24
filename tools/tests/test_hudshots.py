"""The contact sheet in docs/hud is the HUD, or it is worse than nothing.

`ops/ralph/hudshots.sh` renders the real plates into PNGs so that looking at
the HUD stops requiring a seat at ares (PLAN A29). It does that by STAGING a
copy of shell/jv-hud with two singletons replaced — the only two that import
Quickshell — and by rebuilding shell.qml's plate stack in a file a plain QML
engine can load.

Both of those are duplication, and duplication drifts. The failure mode is
specific and silent: a new plate is added to shell.qml, never appears in the
sheet, and the sheet still renders seven perfectly good pictures of a HUD
that no longer exists. Nothing errors. These are the gates that make that
loud instead.
"""

import re
from pathlib import Path

# One parser for the HUD's QML, not two: the theme gates already had to read
# shell.qml's plate stack, and a second implementation of "what is inside
# this block" would be a second thing to be subtly wrong.
from test_gen_theme_qml import ROOT, plate_stack_children, strip_qml_comments

SHELL = ROOT / "shell" / "jv-hud"
SHOTS = ROOT / "tools" / "hudshots"
SHEET = ROOT / "docs" / "hud"

SCENE_DIR = SHOTS / "scene"
SCENE = SCENE_DIR / "tst_shots.qml"
# The corner stack both drivers build: the sheet (A29) and the sequence
# replay (A54). One copy of shell.qml's stack, in one file, so that "the
# harness stacks what the shell stacks" is one claim and not one per driver.
CORNER = SCENE_DIR / "Corner.qml"

# Every member a QML file offers its consumers: properties (including
# aliases), functions and signals, declared at any depth — the HUD writes
# them all at the top level of these files.
MEMBER = re.compile(
    r"""^\s*(?:readonly\s+)?(?:property\s+(?:alias\s+)?[\w.<>]+\s+(?P<prop>\w+)
        |function\s+(?P<func>\w+)\s*\(
        |signal\s+(?P<sig>\w+))""",
    re.M | re.X,
)


def members(path: Path) -> set[str]:
    text = strip_qml_comments(path.read_text("utf-8"))
    out = set()
    for m in MEMBER.finditer(text):
        out.add(m.group("prop") or m.group("func") or m.group("sig"))
    return out


def scene_text() -> str:
    return SCENE.read_text("utf-8")


SHEET_ENTRY = re.compile(
    r'\{\s*"file":\s*"(?P<file>[^"]+)".*?"plates":\s*\[(?P<plates>[^]]*)\]',
    re.S,
)


def sheet() -> list[tuple[str, list[str]]]:
    """The scene's sheet: each shot's file name and the plates it claims are on
    screen, in the order they are declared (A53)."""
    out = [
        (m.group("file"), re.findall(r'"([^"]+)"', m.group("plates")))
        for m in SHEET_ENTRY.finditer(strip_qml_comments(scene_text()))
    ]
    assert out, "found no sheet entries with a `plates` list in the scene"
    return out


def test_the_harness_stacks_the_same_plates_the_shell_does():
    """Corner.qml is a copy of shell.qml's corner stack, and a copy of a list
    is a list that goes stale. A plate the shell shows and the harness does
    not is a plate nobody has ever seen a picture of — nor asserted a
    trajectory for (A54) — which is the exact thing this harness exists to
    prevent. The ORDER matters as much as the membership: it is the reading
    order of the corner, and both drivers assert `litNames` against it.
    """
    shell = plate_stack_children((SHELL / "shell.qml").read_text("utf-8"))
    corner = plate_stack_children(CORNER.read_text("utf-8"))
    assert corner == shell, (
        "tools/hudshots/scene/Corner.qml stacks "
        f"{corner} but shell.qml stacks {shell} — regenerate the corner (and "
        "then the sheet: bash ops/ralph/hudshots.sh)"
    )


def test_no_driver_keeps_its_own_copy_of_the_corner():
    """There was one copy of the stack per harness until Corner.qml (A54), and
    the sequence replay would have made a second. Copies of a list are the
    failure this file exists to catch, so the drivers must not hold one: a
    plate declared inside a driver is a plate that is in one harness and not
    the other, and the check above would not see it.
    """
    for driver in sorted(SCENE_DIR.glob("tst_*.qml")):
        stray = re.findall(
            r"^\s*(\w+Plate)\s*\{", strip_qml_comments(driver.read_text("utf-8")), re.M
        )
        assert not stray, (
            f"{driver.name} declares {sorted(set(stray))} itself — stack plates "
            "in Corner.qml, which is the one file pinned to shell.qml"
        )


def test_the_stub_bus_offers_everything_the_real_one_does():
    """A plate reading `Bus.somethingTheStubForgot` does not error: QML hands
    it `undefined`, the plate decides it has nothing to say, and the shot is
    a picture of a plate that works fine on the real bus. Missing members
    have to fail HERE or they never fail at all.
    """
    real = members(SHELL / "Bus.qml")
    stub = members(SHOTS / "stub" / "Bus.qml")
    assert real <= stub, (
        f"tools/hudshots/stub/Bus.qml is missing {sorted(real - stub)}, which "
        "the plates can read on the real bus and would see as undefined here"
    )


def test_the_stub_motion_offers_everything_the_real_one_does():
    """Same failure, quieter: a missing `Motion.animate` reads as false, every
    Behavior silently switches off, and the sheet becomes a picture of a HUD
    in permanent reduced-motion — which is a setting, not the default.
    """
    real = members(SHELL / "Motion.qml")
    stub = members(SHOTS / "stub" / "Motion.qml")
    assert real <= stub, (
        f"tools/hudshots/stub/Motion.qml is missing {sorted(real - stub)}"
    )


def test_the_stubs_replace_nothing_but_the_two_quickshell_singletons():
    """The value of the sheet is that everything in it is the real file. Every
    stub is one more thing that is not — so there are two, both named here,
    and both for the same reason: they import Quickshell, whose QML plugin is
    linked into the quickshell binary and cannot be resolved by any other
    engine.
    """
    stubs = sorted(p.name for p in (SHOTS / "stub").glob("*.qml"))
    assert stubs == ["Bus.qml", "Motion.qml"], (
        f"tools/hudshots/stub holds {stubs}: a third stub means a third piece "
        "of the HUD the sheet is only pretending to show"
    )
    for name in stubs:
        real = (SHELL / name).read_text("utf-8")
        assert "import Quickshell" in real, (
            f"{name} no longer imports Quickshell, so the shot harness can use "
            "the real file and should stop carrying a copy of it"
        )


def test_the_backdrop_is_not_one_of_jarviss_colours():
    """The grey behind the plates is the sheet's, not the HUD's — the real
    surface is transparent. If it were ever a theme token, a reader would have
    no way to tell the photograph's paper from Jarvis's own palette.
    """
    backdrop = re.search(
        r'property color backdrop:\s*"(#[0-9A-Fa-f]{6})"', scene_text()
    )
    assert backdrop, "the scene no longer declares a single backdrop colour"
    palette = set(
        re.findall(r'^\s*\w+\s*=\s*"(#[0-9A-Fa-f]{6})"', 
                   (ROOT / "personality" / "theme.toml").read_text("utf-8"), re.M)
    )
    assert backdrop.group(1).upper() not in {c.upper() for c in palette}, (
        f"the sheet's backdrop {backdrop.group(1)} is a personality/theme.toml "
        "colour, so the paper and the HUD are now the same thing"
    )


def test_every_shot_the_scene_takes_is_committed_and_vice_versa():
    """An uncommitted shot is one nobody can look at without running the
    harness; an orphaned PNG is a picture of a HUD that no longer exists. Both
    are the sheet quietly ceasing to be the sheet.
    """
    taken = re.findall(r'"file":\s*"([^"]+)"', scene_text())
    assert taken, "the scene declares no shots at all"
    committed = sorted(p.name for p in SHEET.glob("*.png"))
    assert sorted(taken) == committed, (
        f"the scene takes {sorted(taken)} and docs/hud holds {committed} — "
        "run bash ops/ralph/hudshots.sh and commit the result"
    )


def test_the_sheet_says_which_shots_are_recordings_and_which_are_written():
    """Some shots replay harness/fixtures/sessions and some are frames written
    by hand, because nothing in the repo has ever recorded jv-voice speaking or
    jv-act asking (B10/A28). A sheet that blurs the two would let a composed
    picture be read as evidence about the machine — the one thing a screenshot
    of a HUD must never do.
    """
    readme = (SHEET / "README.md").read_text("utf-8")
    # One `### ` section per shot: the heading, the image, and the paragraph
    # that says where its frames came from.
    sections = readme.split("\n### ")
    for name in re.findall(r'"file":\s*"([^"]+)"', scene_text()):
        shown = [s for s in sections if name in s]
        assert shown, f"docs/hud/README.md never mentions {name}"
        assert len(shown) == 1, f"docs/hud/README.md shows {name} in {len(shown)} sections"
        assert re.search(r"\b(recorded|composed)\b", shown[0].lower()), (
            f"docs/hud/README.md shows {name} without saying whether its frames "
            "are recorded or composed"
        )


def test_every_shot_says_which_plates_are_in_it():
    """A53. The scene's only per-shot assertion used to be `anyLit` — a single
    bit that nine of the ten shots answered `true` — so the sheet could prove
    a picture had SOMETHING in it and never what. An entry without a `plates`
    list is a shot back in that state, and it would be the one shot nobody
    notices, because the other nine still pass.
    """
    files = re.findall(r'"file":\s*"([^"]+)"', strip_qml_comments(scene_text()))
    named = [f for f, _ in sheet()]
    assert files == named, (
        f"every sheet entry must declare `plates`; {sorted(set(files) - set(named))} "
        "do not, so those shots are checked only by 'something was drawn'"
    )
    assert '"lit"' not in strip_qml_comments(scene_text()), (
        "the old one-bit `lit` flag is back in the sheet; `plates` supersedes "
        "it and the two would drift"
    )


def test_every_plate_in_the_shell_is_lit_in_some_shot():
    """A plate the sheet renders but never LIGHTS is a plate nobody has ever
    seen a picture of.

    The older gate above proves each plate is in the scene's stack, which is
    only the claim that it was built — every plate in this HUD draws nothing
    until a real frame gives it something to say, so a plate can sit in all
    ten shots and appear in none of them. That is the normal state of most of
    them, and it is exactly how a new element gets added, rendered, committed
    and still never looked at.
    """
    lit = {name for _, plates in sheet() for name in plates}
    for child in plate_stack_children((SHELL / "shell.qml").read_text("utf-8")):
        want = child[: -len("Plate")].lower()
        assert want in lit, (
            f"{child} is in the shell's stack and no shot in docs/hud has it on "
            f"screen, so there is no picture of it. Add a shot that lights it."
        )


def test_the_sheet_tells_the_reader_which_plates_each_shot_shows():
    """The captions are for a human, and a human is the only thing that has
    ever been able to tell two of these plates apart in a PNG.

    `HealthPlate` and `ActionPlate` draw the same two lines in the same
    severity colour in the same corner; `GuardPlate` makes three. So the
    README's per-shot `**On screen:**` line is read off the scene and checked
    against it — a prose description can drift into naming the wrong element,
    and this line cannot.
    """
    readme = (SHEET / "README.md").read_text("utf-8")
    sections = readme.split("\n### ")
    for name, plates in sheet():
        shown = [s for s in sections if name in s]
        assert len(shown) == 1, f"docs/hud/README.md shows {name} in {len(shown)} sections"
        line = re.search(r"^\*\*On screen:\*\*(.+)$", shown[0], re.M)
        assert line, f"docs/hud/README.md's {name} section has no `**On screen:**` line"
        got = re.findall(r"`([^`]+)`", line.group(1))
        if not plates:
            assert not got and "nothing" in line.group(1), (
                f"{name} has no plate on screen, and its line must say so "
                f"in words rather than name one: {line.group(1).strip()}"
            )
            continue
        assert got == plates, (
            f"docs/hud/README.md says {name} shows {got}; the scene asserts "
            f"{plates}. The README is what a reader believes the picture is of."
        )
