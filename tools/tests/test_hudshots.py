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

SCENE = SHOTS / "scene" / "tst_shots.qml"

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


def test_the_sheet_stacks_the_same_plates_the_shell_does():
    """The scene is a copy of shell.qml's corner stack, and a copy of a list
    is a list that goes stale. A plate the shell shows and the sheet does not
    is a plate nobody has ever seen a picture of — which is the exact thing
    this whole harness exists to prevent.
    """
    shell = plate_stack_children((SHELL / "shell.qml").read_text("utf-8"))
    scene = plate_stack_children(scene_text())
    assert scene == shell, (
        "tools/hudshots/scene/tst_shots.qml stacks "
        f"{scene} but shell.qml stacks {shell} — regenerate the scene (and "
        "then the sheet: bash ops/ralph/hudshots.sh)"
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
