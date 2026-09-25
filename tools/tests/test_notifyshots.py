"""The contact sheet in docs/notify is the notification corner, or it is worse
than nothing.

`ops/ralph/notifyshots.sh` renders the real toasts into PNGs (PLAN D20), the
way `hudshots.sh` does for the HUD, and by the same two duplications: it STAGES
a copy of shell/jv-notify with the two singletons that import Quickshell
replaced, and it rebuilds shell.qml's stack in a file a plain QML engine can
load.

Both of those drift. The failure mode is specific and silent: shell.qml grows a
row, or reorders the stack, and the sheet still renders ten perfectly good
pictures of a corner that no longer exists. Nothing errors. These are the gates
that make that loud instead.

Why this shell needs the sheet more than the other two is worth restating here,
because it is what justifies a second harness at all: this is the only surface
on the machine whose CONTENT comes from programs this repo did not write. The
first run of the sheet found the name row painting 656 px past its plate on an
app name with no space in it — a real bug, in shipped code, that every headless
test in the repo was blind to.
"""

import re
from pathlib import Path

# One parser for this repo's QML, not two.
from test_gen_theme_qml import ROOT, strip_qml_comments
from test_hudshots import members

SHELL = ROOT / "shell" / "jv-notify"
SHOTS = ROOT / "tools" / "notifyshots"
SHEET = ROOT / "docs" / "notify"

SCENE_DIR = SHOTS / "scene"
SCENE = SCENE_DIR / "tst_shots.qml"
# The stack shell.qml composes inline, staged where an engine without
# Quickshell can build it.
STRIP = SCENE_DIR / "Strip.qml"
SCRIPT = ROOT / "ops" / "ralph" / "notifyshots.sh"


def scene_text() -> str:
    return SCENE.read_text("utf-8")


SHEET_ENTRY = re.compile(
    r'\{\s*"file":\s*"(?P<file>[^"]+)".*?"plates":\s*\[(?P<plates>[^]]*)\]',
    re.S,
)


def sheet() -> list[tuple[str, list[str]]]:
    """Each shot's file name and the captions it claims are on screen."""
    out = [
        (m.group("file"), re.findall(r'"([^"]+)"', m.group("plates")))
        for m in SHEET_ENTRY.finditer(strip_qml_comments(scene_text()))
    ]
    assert out, "found no sheet entries with a `plates` list in the scene"
    return out


def stack_of(text: str, opener: str = "Column {") -> list[tuple[int, str]]:
    """What a container holds, in order, as (depth, element).

    Brace-walked rather than matched by indentation, because the two files this
    compares are indented four levels apart: shell.qml's stack is inside a
    PanelWindow inside a Variants inside a ShellRoot, and the staged one is the
    root. Depth is kept because the delegate inside the Repeater is part of the
    composition — a strip that repeated something else would stack the same two
    elements — and the ORDER is the point: the `+N EARLIER` line is above the
    plates because the ones it counts are older than everything on screen.

    `opener` is which container to walk. It exists because the bar's harness
    asks exactly this question of a PanelWindow and a Rectangle
    (tools/tests/test_barshots.py), and two brace-walks would eventually be two
    answers.
    """
    body = strip_qml_comments(text)
    start = body.index(opener) + len(opener)
    out: list[tuple[int, str]] = []
    depth = 1
    i = start
    while i < len(body) and depth > 0:
        c = body[i]
        if c == "}":
            depth -= 1
        elif c == "{":
            # The identifier this block belongs to, if it is a CHILD
            # (`Toast {`) rather than a binding (`onX: { … }`, an object
            # literal) or a value assigned to one (`mask: Region {}`, which is
            # a property of the surface and not something drawn in it).
            head = re.search(r"([A-Z]\w*)\s*$", body[:i])
            before = body[:i].rstrip()
            valued = re.search(r":\s*[A-Z]\w*\s*$", body[:i])
            if head and not before.endswith(":") and not valued:
                out.append((depth, head.group(1)))
            depth += 1
        i += 1
    assert depth == 0, f"the {opener.split()[0]}'s braces do not balance"
    return out


def test_the_harness_stacks_what_the_shell_stacks():
    """Strip.qml is a copy of shell.qml's column, and a copy goes stale. A row
    the shell shows and the harness does not is a row nobody has ever seen a
    picture of. The ORDER matters as much as the membership: the `+N EARLIER`
    line is above the plates because the ones it counts are older than
    everything on screen, and a sheet that photographed it below them would be
    asserting a corner the user never sees.
    """
    shell = stack_of((SHELL / "shell.qml").read_text("utf-8"))
    # The staged strip IS a Column, so it is given one to find: the same walk
    # over the same shape, rather than a second parser for the root element.
    strip = stack_of("Column {" + STRIP.read_text("utf-8").split("Column {", 1)[1])
    assert strip == shell, (
        f"tools/notifyshots/scene/Strip.qml stacks {strip} but shell.qml stacks "
        f"{shell} — fix the strip, then re-run bash ops/ralph/notifyshots.sh"
    )


def test_the_strip_draws_the_same_earlier_line_the_shell_does():
    """The one string on this surface that is not a sender's. It says how many
    notifications are being tracked and deliberately NOT shown, and it is the
    only thing standing between a cap and a daemon that looks like it lost your
    message — so the harness must photograph the shell's sentence, not one of
    its own."""
    for path in (SHELL / "shell.qml", STRIP):
        text = strip_qml_comments(path.read_text("utf-8"))
        assert '"+" + Notifications.earlier + " EARLIER"' in text, path
        assert "visible: Notifications.earlier > 0" in text, path


def test_no_driver_keeps_its_own_copy_of_the_stack():
    """One copy of shell.qml's column, in Strip.qml, so that "the harness stacks
    what the shell stacks" is one claim. A driver that declared a Toast itself
    would be a second stack, and the check above would not see it."""
    for driver in sorted(SCENE_DIR.glob("tst_*.qml")):
        stray = re.findall(
            r"^\s*(Toast|Repeater)\s*\{", strip_qml_comments(driver.read_text("utf-8")), re.M
        )
        assert not stray, (
            f"{driver.name} declares {sorted(set(stray))} itself — stack plates in "
            "Strip.qml, which is the one file pinned to shell.qml"
        )


def test_the_stand_ins_offer_everything_the_real_singletons_do():
    """A strip reading `Notifications.somethingTheStandInForgot` does not error:
    QML hands it `undefined`, the Repeater builds nothing, and the shot is a
    picture of an empty corner that works fine on the real daemon. Missing
    members have to fail HERE or they never fail at all.

    `take()` is excluded on purpose and is the one member that cannot be
    forwarded: it takes a Quickshell `Notification` object, sets `tracked` on it
    and connects its `closed` signal, which is the entire half of that file the
    stand-in exists to remove. The stand-in's `send()` takes the record `take()`
    builds, so what the model sees is the same either way.
    """
    for name, skip in (("Notifications.qml", {"take"}), ("Motion.qml", set())):
        real = members(SHELL / name) - skip
        stub = members(SHOTS / "stub" / name)
        assert real <= stub, (
            f"tools/notifyshots/stub/{name} is missing {sorted(real - stub)}, which "
            "the corner can read on the real one and would see as undefined here"
        )


def test_the_stand_ins_replace_nothing_but_the_quickshell_singletons():
    """The value of the sheet is that everything in it is the real file. Every
    stand-in is one more thing that is not — so there are two, both named here,
    and both for the same reason: they import Quickshell, whose QML plugin is
    linked into the quickshell binary and cannot be resolved by any other
    engine."""
    stubs = sorted(p.name for p in (SHOTS / "stub").glob("*.qml"))
    assert stubs == ["Motion.qml", "Notifications.qml"], (
        f"tools/notifyshots/stub holds {stubs}: a third stand-in means a third "
        "piece of this shell the sheet is only pretending to show"
    )
    for name in stubs:
        real = (SHELL / name).read_text("utf-8")
        assert "import Quickshell" in real, (
            f"{name} no longer imports Quickshell, so the shot harness can use the "
            "real file and should stop carrying a copy of it"
        )
        staged = strip_qml_comments((SHOTS / "stub" / name).read_text("utf-8"))
        assert "Quickshell" not in staged, (
            f"the stand-in for {name} imports Quickshell itself — ONE of those "
            "anywhere in the stage makes the whole directory unimportable"
        )


def test_every_staged_file_is_the_real_one_or_a_declared_stand_in():
    """The script copies the shell verbatim and then writes over exactly two
    files. Anything else it stages is a piece of this corner the sheet is
    showing you a stand-in for without saying so."""
    script = SCRIPT.read_text("utf-8")
    written = set(re.findall(r'cp "\$root/tools/notifyshots/stub/(\S+?)" "\$stage/', script))
    assert written == {p.name for p in (SHOTS / "stub").glob("*.qml")}, written
    # And the one file it DELETES, which is the Quickshell half that has no
    # stand-in because the harness rebuilds it as Strip.qml instead.
    assert 'rm -f "$stage/shell.qml"' in script


def test_the_backdrop_is_not_one_of_jarviss_colours():
    """The grey behind the plates is the sheet's, not the corner's — the real
    surface is transparent. If it were ever a theme token, a reader would have
    no way to tell the photograph's paper from Jarvis's own palette."""
    backdrop = re.search(r'property color backdrop:\s*"(#[0-9A-Fa-f]{6})"', scene_text())
    assert backdrop, "the scene no longer declares a single backdrop colour"
    palette = set(
        re.findall(
            r'^\s*\w+\s*=\s*"(#[0-9A-Fa-f]{6})"',
            (ROOT / "personality" / "theme.toml").read_text("utf-8"),
            re.M,
        )
    )
    assert backdrop.group(1).upper() not in {c.upper() for c in palette}, (
        f"the sheet's backdrop {backdrop.group(1)} is a personality/theme.toml "
        "colour, so the paper and the corner are now the same thing"
    )


def test_the_shot_box_is_the_box_the_shell_asks_for():
    """Every PNG is the size the compositor would really map, because the driver
    derives it the way shell.qml derives it. Two expressions, one arithmetic: a
    driver that chose a canvas instead would photograph the stack floating in
    the middle of a box nobody asks for, and the emptiness around it would be
    the harness's rather than the corner's."""
    shell = strip_qml_comments((SHELL / "shell.qml").read_text("utf-8"))
    scene = strip_qml_comments(scene_text())
    for dim, side in (("Width", "implicitWidth"), ("Height", "implicitHeight")):
        assert f"implicit{dim}: stack.{side} + Theme.insetPx * 2" in shell, dim
        assert f"{dim.lower()}: strip.{side} + Theme.insetPx * 2" in scene, dim


def test_every_shot_the_scene_takes_is_committed_and_vice_versa():
    """An uncommitted shot is one nobody can look at without running the
    harness; an orphaned PNG is a picture of a corner that no longer exists.
    Both are the sheet quietly ceasing to be the sheet."""
    taken = [name for name, _ in sheet()]
    committed = sorted(p.name for p in SHEET.glob("*.png"))
    assert sorted(taken) == committed, (
        f"the scene takes {sorted(taken)} and docs/notify holds {committed} — "
        "run bash ops/ralph/notifyshots.sh and commit the result"
    )


def test_every_shot_is_described_and_says_it_is_composed():
    """Nothing in this repo has ever recorded a real notification, so every shot
    here is written by hand. A sheet that let a composed picture be read as
    evidence about the machine would be doing the one thing a screenshot of a
    surface must never do — so the README says so, once, at the top, and every
    shot has a section a person can read beside the picture."""
    readme = (SHEET / "README.md").read_text("utf-8")
    assert "composed" in readme.lower()
    # The preamble is dropped: it names a shot on purpose (the bug the first run
    # found is the reason this sheet exists), and a shot mentioned in the prose
    # is not a shot shown twice.
    sections = readme.split("\n### ")[1:]
    for name, _ in sheet():
        shown = [s for s in sections if name in s]
        assert shown, f"docs/notify/README.md never mentions {name}"
        assert len(shown) == 1, f"docs/notify/README.md shows {name} in {len(shown)} sections"
        assert f"![{name}]({name})" in shown[0], (
            f"docs/notify/README.md describes {name} without showing it"
        )


def test_every_shot_says_what_is_on_screen_and_the_words_are_the_plates_own():
    """The captions are the only thing telling two of these pictures apart, so
    they have to be checked twice: the driver checks them against the plates,
    and this checks that the vocabulary is one the plates can actually produce.
    A caption claiming `urgent name` would assert forever against a plate that
    can only ever say `critical name`, and the shot would go green saying
    nothing.
    """
    # `Toast.drew` is built from exactly these words.
    allowed = {"low", "normal", "critical", "name", "summary", "body", "summary…", "body…"}
    seen: set[str] = set()
    for name, plates in sheet():
        assert plates, f"{name} claims no plates at all"
        for caption in plates:
            words = caption.split()
            assert words[0] in {"low", "normal", "critical"}, (
                f"{name}: a caption must open with the urgency, not {words[0]!r}"
            )
            for word in words:
                assert word in allowed, f"{name}: {word!r} is not a word Toast.drew says"
            seen |= set(words)
    # And the sheet must actually exercise the vocabulary: every urgency, an
    # elide, and a plate with its name row gone. A sheet that only ever showed
    # `normal name summary body` would be ten pictures of one case.
    for word in allowed:
        assert word in seen, f"no shot on this sheet produces {word!r}"


def test_the_sheet_photographs_a_corner_that_is_full_and_one_that_is_over():
    """The cap is the model's single most visible decision and the `+N EARLIER`
    line is the only thing that makes it honest. One shot at exactly the cap and
    one past it is what tells a reader which of the two they are looking at —
    without the second, nothing here would ever draw that line."""
    caps = [(n, p, e) for n, p in sheet() for e in [earlier_of(n)]]
    full = [n for n, p, e in caps if len(p) == 3 and not e]
    over = [n for n, p, e in caps if len(p) == 3 and e]
    assert full, "no shot photographs a corner at exactly the cap"
    assert over, "no shot photographs a corner past the cap, so `+N EARLIER` is never drawn"
    for name in over:
        assert re.fullmatch(r"\+\d+ EARLIER", earlier_of(name)), earlier_of(name)


def earlier_of(name: str) -> str:
    """The `earlier` string a shot claims, as declared in the scene."""
    m = re.search(
        r'"file":\s*"' + re.escape(name) + r'".*?"earlier":\s*"([^"]*)"',
        strip_qml_comments(scene_text()),
        re.S,
    )
    assert m, f"{name} declares no `earlier` string"
    return m.group(1)


def test_the_cap_the_sheet_photographs_is_the_cap_the_model_keeps():
    """Three plates is `NotifyModel.maxVisible`, not a number the harness chose.
    A model that raised its cap and a sheet that kept photographing three would
    be a sheet of a corner nobody runs."""
    model = (SHELL / "core" / "NotifyModel.qml").read_text("utf-8")
    cap = re.search(r"property int maxVisible:\s*(\d+)", model)
    assert cap, "NotifyModel no longer declares maxVisible"
    most = max(len(plates) for _, plates in sheet())
    assert most == int(cap.group(1)), (
        f"the sheet's fullest corner holds {most} plates and the model caps at "
        f"{cap.group(1)} — re-run bash ops/ralph/notifyshots.sh"
    )


def test_the_plate_that_can_overflow_is_bound_and_the_sheet_asks_it_to():
    """The bug this harness found on its first run, and the two halves of it not
    coming back. The name row is the only row on the plate holding a string a
    stranger chose the SHAPE of and it must be width-bound and elided; and the
    sheet must keep a shot whose app name cannot be broken across lines, or the
    binding is unexercised the day someone removes it.
    """
    toast = strip_qml_comments((SHELL / "Toast.qml").read_text("utf-8"))
    assert "elide: Text.ElideRight" in toast
    assert "width: Math.min(implicitWidth, rows.width" in toast, (
        "the app name row is no longer bound to the plate's width — an app_name "
        "with no space in it paints over the desktop beside the plate"
    )
    assert "overflowPx" in toast, "the plate no longer measures its own overflow"
    assert "overflowPx" in STRIP.read_text("utf-8"), "the strip no longer reads it"
    assert "strip.overflows()" in scene_text(), (
        "nothing asserts that a plate stays inside its own border"
    )
    # A name long enough to need the elide, in some shot: `rep(unit, n)` with a
    # unit that has no space in it.
    rep = re.search(r'suite\.rep\("([^" ]+)",\s*(\d+)\)\s*\+', scene_text())
    assert rep and len(rep.group(1)) * int(rep.group(2)) >= 100, (
        "no shot sends an app name long enough to need the binding above"
    )
