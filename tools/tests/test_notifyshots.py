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
import struct
import sys
from pathlib import Path

# One parser for this repo's QML, not two.
from test_gen_theme_qml import ROOT, strip_qml_comments
from test_hudshots import members

# The screens the three shells are really loaded on (PLAN D75/D77). Imported
# rather than copied, because the whole content of the fit gate below is that
# two independently-owned numbers are compared: the corner's own maximum, and
# the shortest output any compositor in this repo hands a shell.
sys.path.insert(0, str(ROOT / "tools" / "shellload"))
import shells  # noqa: E402

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


def model_text() -> str:
    """The model, with its comments — the prose beside `maxVisible` is read as
    well as the number (see the D77 section at the foot of this file)."""
    return (SHELL / "core" / "NotifyModel.qml").read_text("utf-8")


def model_cap() -> str:
    """How many plates the corner shows at once, as the model declares it."""
    cap = re.search(r"property int maxVisible:\s*(\d+)", model_text())
    assert cap, "NotifyModel no longer declares maxVisible"
    return cap.group(1)


def test_the_cap_the_sheet_photographs_is_the_cap_the_model_keeps():
    """Three plates is `NotifyModel.maxVisible`, not a number the harness chose.
    A model that raised its cap and a sheet that kept photographing three would
    be a sheet of a corner nobody runs."""
    cap = model_cap()
    most = max(len(plates) for _, plates in sheet())
    assert most == int(cap), (
        f"the sheet's fullest corner holds {most} plates and the model caps at "
        f"{cap} — re-run bash ops/ralph/notifyshots.sh"
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


# ------------------------------------- the corner's own maximum height (D77)
#
# The one question about this surface that the HUD had to answer the opposite
# way, and the reason this shell has no declared floor and no warn.
#
# `jv-hud` asks the compositor for a FIXED 300x826 box, so a screen shorter
# than 826 crops it; D74 declared that floor in shell.qml and made the shell
# SAY SO in its log, and D75 put a 768 px output under `ops/ralph/shellload.sh`
# to hear the line arrive. This shell's surface is DERIVED — shell.qml asks for
# `stack.implicitHeight + inset*2` — so "does it fit" is not a property of the
# screen, it is a property of how tall the stack can be made, and that is
# bounded twice over: `NotifyModel.maxVisible` bounds the plates, and
# `Toast`'s two-line summary and three-line body bound each plate.
#
# Which turns the whole question into one measurement, and the sheet is where a
# measurement of this surface belongs: the tallest corner a sender can produce
# is a PNG in docs/notify, and its HEIGHT is the reading.

PNG_HEADER = 16  # 8-byte signature, then the IHDR length and tag


def png_size(path: Path) -> tuple[int, int]:
    """One shot's pixel size, straight out of its IHDR.

    Read rather than trusted from the scene, because the scene declares what to
    build and the PNG is what was actually drawn — with the real faces, at the
    real token sizes. The driver already asserts that a shot's image is exactly
    the surface's derived box (`img.height == root.height`), so this number is
    the height the compositor would map and not a canvas the harness chose.
    """
    data = path.read_bytes()[PNG_HEADER : PNG_HEADER + 8]
    assert len(data) == 8, f"{path.name} is not long enough to be a PNG"
    return struct.unpack(">II", data)


def shortest_screen() -> int:
    """The shortest output any compositor in this repo hands a shell.

    `tools/shellload/shells.py`, not a number typed here: it owns that list,
    D75 added the short one to ask the HUD what it does under its own floor,
    and a harness that changed it must move this gate with it.
    """
    return min(o["height"] for o in shells.ALL_OUTPUTS)


def test_the_sheet_photographs_the_corner_at_its_own_maximum():
    """A fit gate over a sheet that never photographs the worst case is a gate
    over whatever happened to be on it. The tallest corner this shell can draw
    is the cap-many plates EACH at its own maximum — both rows present and both
    elided, which is the only evidence that a row really hit its line limit —
    under the `+N EARLIER` line, which is drawn only once the cap is exceeded
    and is itself another row of height. If no shot is all three of those at
    once, the number the next test reads is not the maximum of anything.
    """
    cap = int(model_cap())
    maxed = [
        name
        for name, plates in sheet()
        if len(plates) == cap
        and earlier_of(name)
        and all("summary…" in p and "body…" in p for p in plates)
    ]
    assert maxed, (
        f"no shot holds {cap} plates with both rows elided under an `+N EARLIER` "
        "line, so nothing on this sheet is the tallest corner this shell can draw"
    )


def test_the_tallest_corner_this_shell_can_draw_fits_the_shortest_screen_it_loads_on():
    """The whole of PLAN D77, as two numbers nobody typed together.

    The corner's maximum is the tallest PNG on the sheet — the shot above
    guarantees the worst case is among them, and taking the MAX rather than
    that one shot's height means an unexpectedly tall picture (a font fallback
    with a deeper line box, say) is caught rather than stepped around.

    If this ever goes red the answer is NOT to clamp the stack. A cropped toast
    is still a toast, but the first thing this upward-growing column loses is
    the `+N EARLIER` line at its top — the one element whose whole job is to
    say that something is hidden. The answer is to look at what grew.
    """
    shots = {p.name: png_size(p)[1] for p in SHEET.glob("*.png")}
    assert shots, "docs/notify holds no shots at all"
    tallest, height = max(shots.items(), key=lambda kv: (kv[1], kv[0]))
    floor = shortest_screen()
    assert height <= floor, (
        f"{tallest} is {height} px and the shortest screen any shell in this "
        f"repo is loaded on is {floor} px — the notification corner can now be "
        "cropped, and the first thing it would lose is the `+N EARLIER` line"
    )


CAP_NOTE = re.compile(
    r"`docs/notify/(?P<shot>[\w.\-]+)` is that corner,\s*//\s*"
    r"and it is (?P<tall>\d+) px tall, against a shortest loaded screen of "
    r"(?P<floor>\d+) px"
)


def test_the_note_beside_the_cap_carries_the_numbers_it_was_measured_from():
    """The decision D77 reached lives next to `maxVisible`, because that cap is
    what makes it true — and it quotes both measurements. A comment with a stale
    number in it is worse than a comment with none: this one is the only place a
    reader of the model learns why this shell has no floor and no warn while the
    HUD has both, and it would go on saying so after the corner had outgrown the
    screen. So the two numbers are read back, from the picture and from the
    harness that owns the screen.
    """
    note = CAP_NOTE.search(model_text())
    assert note, (
        "NotifyModel no longer explains, beside `maxVisible`, why the cap is "
        "the floor — see PLAN D77"
    )
    shot = SHEET / note.group("shot")
    assert shot.exists(), f"the note names {note.group('shot')}, which is not on the sheet"
    assert png_size(shot)[1] == int(note.group("tall")), (
        f"the note says {note.group('shot')} is {note.group('tall')} px and it is "
        f"{png_size(shot)[1]} px"
    )
    assert int(note.group("floor")) == shortest_screen(), (
        f"the note's shortest screen is {note.group('floor')} px and "
        f"tools/shellload/shells.py's shortest output is {shortest_screen()} px"
    )
