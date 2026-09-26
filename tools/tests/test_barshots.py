"""The contact sheet in docs/bar is the top bar, or it is worse than nothing.

`ops/ralph/barshots.sh` renders the real strip into PNGs (PLAN D13), the way
`hudshots.sh` and `notifyshots.sh` do for the other two shells, and by the same
two duplications: it STAGES a copy of shell/jv-bar with the two singletons that
import Quickshell replaced, and it rebuilds shell.qml's surface in a file a
plain QML engine can load.

Both of those drift. The failure mode is specific and silent: shell.qml moves
the clock, or drops the hairline, and the sheet still renders nine perfectly
good pictures of a bar that no longer exists. Nothing errors. These are the
gates that make that loud instead.

Why this shell needed a sheet is worth restating here, because it is what
justifies a third harness at all: the bar is the one surface that is ALWAYS on
screen. The HUD is unmapped until a frame earns it and the corner is unmapped
until somebody sends something; the strip is up from the moment the session
starts until it ends, on every monitor. Two of its questions are answered by
nothing else in this repo — whether the workspaces row stays clear of the
corner shell.qml reserves for the HUD (another process, on another layer, that
draws there and cannot be asked), and whether the clock is on screen at all,
which depends on how wide the monitor is. Both are properties of a laid-out
surface at a real width, and both were unmeasured until this sheet.
"""

import json
import re
from pathlib import Path

# One parser for this repo's QML, not four.
from test_gen_theme_qml import ROOT, strip_qml_comments
from test_hudshots import members
from test_notifyshots import stack_of

SHELL = ROOT / "shell" / "jv-bar"
SHOTS = ROOT / "tools" / "barshots"
SHEET = ROOT / "docs" / "bar"

SCENE_DIR = SHOTS / "scene"
SCENE = SCENE_DIR / "tst_shots.qml"
# The lines niri wrote, kept once for every driver in the directory (PLAN D34):
# the sheet and the settle both start from a desk, and two copies of a
# recording drift twice.
DESK = SCENE_DIR / "Desk.qml"
# The surface shell.qml composes inside its PanelWindow, staged where an engine
# without Quickshell can build it.
STRIP = SCENE_DIR / "Strip.qml"
SCRIPT = ROOT / "ops" / "ralph" / "barshots.sh"
RECORDING = ROOT / "harness" / "fixtures" / "niri" / "ares-desk.jsonl"

# The four words `Workspaces.reading()` can return, which are the only words a
# caption on this sheet may use.
READINGS = ("urgent", "focused", "active", "idle")


def scene_text() -> str:
    return SCENE.read_text("utf-8")


def desk_text() -> str:
    return DESK.read_text("utf-8")


SHEET_ENTRY = re.compile(
    r'\{\s*"file":\s*"(?P<file>[^"]+)".*?"screen":\s*(?P<screen>\d+)'
    r'.*?"desk":\s*\[(?P<desk>[^]]*)\].*?"clock":\s*"(?P<clock>[^"]*)"',
    re.S,
)


def sheet() -> list[dict]:
    """Each shot as the scene declares it: the file, the monitor width, the
    labels it claims are on screen, and the clock as drawn."""
    out = [
        {
            "file": m.group("file"),
            "screen": int(m.group("screen")),
            "desk": re.findall(r'"([^"]+)"', m.group("desk")),
            "clock": m.group("clock"),
        }
        for m in SHEET_ENTRY.finditer(strip_qml_comments(scene_text()))
    ]
    assert out, "found no sheet entries with a `desk` list in the scene"
    return out


def test_the_harness_draws_what_the_shell_draws():
    """Strip.qml is a copy of shell.qml's surface, and a copy goes stale. An
    element the shell draws and the harness does not is an element nobody has
    ever seen a picture of. The ORDER matters as much as the membership: the
    hairline is declared first so that it is UNDER the row and the clock, and a
    sheet that photographed it on top would be asserting a bar the user never
    sees."""
    shell = stack_of((SHELL / "shell.qml").read_text("utf-8"), "PanelWindow {")
    # The staged strip IS the surface, so it is walked from its own root — the
    # same walk over the same shape, rather than a second parser.
    strip = stack_of(STRIP.read_text("utf-8"), "Rectangle {")
    assert strip == shell, (
        f"tools/barshots/scene/Strip.qml draws {strip} but shell.qml draws {shell} "
        "— fix the strip, then re-run bash ops/ralph/barshots.sh"
    )


def test_the_strip_is_the_ground_and_the_height_the_shell_asks_for():
    """The bar is opaque and derives its own height from the type scale, which
    is unlike either other shell: the HUD and the corner float, transparently,
    over whatever is behind them. So this sheet's paper IS the surface's own
    ground rather than a neutral grey the harness chose — there is nothing
    behind a bar to reveal — and the strip must be exactly as tall as the real
    one or every shot is a picture of a bar with the wrong rhythm."""
    shell = strip_qml_comments((SHELL / "shell.qml").read_text("utf-8"))
    strip = strip_qml_comments(STRIP.read_text("utf-8"))
    for line in ("implicitHeight: Theme.labelPx + Theme.padPx * 2", "color: Theme.groundDeep"):
        assert line in shell, line
        assert line in strip, line


def test_the_clock_asks_the_same_question_about_the_huds_corner():
    """`fits` is the whole of "is there room for the clock where it wants to
    be", and it is the one binding on this surface that depends on how wide the
    monitor is. It is written in shell.qml against the PanelWindow's id and in
    the staged strip against its own, so the two are compared with the id
    normalised away: everything else about the expression — that the centre is
    the SCREEN's centre and that the reserve is subtracted from the right edge
    — has to be identical, or the sheet photographs a clock that appears and
    disappears at a width the real bar does not."""
    shell = strip_qml_comments((SHELL / "shell.qml").read_text("utf-8"))
    strip = strip_qml_comments(STRIP.read_text("utf-8"))
    wanted = "fits: @.width / 2 + face.width / 2 < @.width - @.hudReservePx"
    assert wanted.replace("@", "surface") in shell, "shell.qml no longer centres the clock on the screen"
    assert wanted.replace("@", "root") in strip, "the staged strip no longer asks shell.qml's question"


def test_the_reserved_corner_is_one_number_in_both():
    """The corner the HUD draws in, which this surface promises to keep empty.

    The width in it is no longer a number in either file: D16 moved it into
    `geometry.hud_corner_px`, so the bar and the HUD read one token and the
    staged strip reads the same expression the bar does. What is left for
    this gate is the half a token cannot fix — a sheet whose strip reserved
    the corner differently from the bar would be a sheet agreeing with
    itself, whatever the number in it came from."""
    reserve = "hudReservePx: Theme.hudCornerPx + Theme.insetPx"
    for path in (SHELL / "shell.qml", STRIP):
        assert reserve in strip_qml_comments(path.read_text("utf-8")), path


def test_the_sheet_asserts_that_nothing_is_laid_out_in_the_huds_corner():
    """The bar's side of a promise made to a process that cannot hear it. The
    HUD sets `ExclusionMode.Ignore` and draws its plates over the top right of
    this strip; neither surface can detect the other. So the ONLY thing that
    can ever check it is a laid-out bar at a real width, which is this sheet —
    and it has to be an assertion rather than a picture, because a label under
    a HUD plate looks fine in a PNG of the bar alone."""
    strip = strip_qml_comments(STRIP.read_text("utf-8"))
    assert "hudOverflowPx" in strip, "the strip no longer measures its own reach into the corner"
    scene = strip_qml_comments(scene_text())
    assert "compare(strip.hudOverflowPx, 0" in scene, (
        "nothing asserts that the workspaces row stays out of the HUD's corner"
    )
    assert "compare(strip.clockOverlapPx" in scene, (
        "nothing asserts that the workspaces row stays clear of the clock"
    )


def test_both_surfaces_tell_the_row_how_much_room_it_has():
    """The row is a `Row`: it is as wide as its children, and its children are
    names the USER chose the length of. `roomPx` is the whole of what stops it
    (PLAN D32), and it is arithmetic only the SURFACE can do — how wide this
    monitor is, where the clock is centred, how much of the right end the HUD
    draws over. So it is written twice, once per surface, and compared here
    with the id normalised away: a staged strip that gave its row a different
    budget would photograph a collapse that happens at a width the real bar
    does not collapse at.

    The `Math.max(0, …)` is part of the expression and not a detail of it
    (PLAN D35): below it the subtraction goes negative, and negative is how
    `core/RowFit.qml` spells "nobody has said how wide this surface is" —
    which draws every label, into the corner the HUD's plates land in. A
    strip that clamped and a bar that did not would photograph an empty row
    on the monitor where the real one overflows."""
    shell = strip_qml_comments((SHELL / "shell.qml").read_text("utf-8"))
    strip = strip_qml_comments(STRIP.read_text("utf-8"))
    wanted = (
        "roomPx: Math.max(0, (face.visible ? face.x : @.width - @.hudReservePx)"
        " - Theme.insetPx - Theme.gapPx)"
    )
    assert wanted.replace("@", "surface") in shell, (
        "shell.qml no longer tells the workspaces row how much room it has"
    )
    assert wanted.replace("@", "root") in strip, (
        "the staged strip budgets the row differently from the bar"
    )


def test_the_sheet_photographs_a_row_that_did_not_fit():
    """The shot D32 was raised to take, and it is three shots' worth of one
    decision. A row with more names than room drops WHOLE labels and says how
    many it dropped; the workspace the output is showing is never among them,
    so the `+N` is not always the last thing on the row; and a dropped
    workspace that is asking for you turns the marker `warn`, because a row
    that hid a window's call for attention and said nothing would be doing
    exactly the thing the marker exists to prevent.

    All three are captions, which is the point: the rule itself is arithmetic
    and is tested in shell/jv-bar/tests/tst_rowfit.qml, at round numbers, away
    from any font. What a sheet adds is that the numbers were REAL ones — a
    1920 px monitor, JetBrains Mono at the token size, the clock where the
    clock is — and that the row still ends clear of both the clock and the
    corner the HUD draws in, which every shot here asserts."""
    marked = [s for s in sheet() if any(c.startswith("+") for c in s["desk"])]
    assert marked, (
        "no shot on this sheet has more names on it than the strip has room for, "
        "so nothing photographs what happens when the row is cut"
    )
    assert any(not s["desk"][-1].startswith("+") for s in marked), (
        "every collapsed shot puts the `+N` last, so none of them photographs the "
        "one you are on being held back — which is the half of the rule that is "
        "not arithmetic"
    )
    assert any("+" in c and c.endswith(":urgent") for s in marked for c in s["desk"]), (
        "no shot hides a workspace that is asking for you, so nothing photographs "
        "the marker in `warn`"
    )


def test_no_driver_keeps_its_own_copy_of_the_surface():
    """One copy of shell.qml's surface, in Strip.qml, so that "the harness draws
    what the shell draws" is one claim. A driver that declared a Workspaces row
    itself would be a second surface, and the check above would not see it."""
    for driver in sorted(SCENE_DIR.glob("tst_*.qml")):
        stray = re.findall(
            r"^\s*(Workspaces|Clock)\s*\{", strip_qml_comments(driver.read_text("utf-8")), re.M
        )
        assert not stray, (
            f"{driver.name} declares {sorted(set(stray))} itself — compose the bar in "
            "Strip.qml, which is the one file pinned to shell.qml"
        )


def test_no_driver_keeps_its_own_copy_of_the_recording():
    """One copy of the line niri wrote, in Desk.qml, for the same reason there
    is one copy of the surface. A driver that pasted the snapshot in again
    would be a second thing to keep in step with
    harness/fixtures/niri/ares-desk.jsonl, and the gate above would only ever
    look at one of them."""
    for driver in sorted(SCENE_DIR.glob("tst_*.qml")):
        stray = re.findall(r"WorkspacesChanged", strip_qml_comments(driver.read_text("utf-8")))
        assert not stray, (
            f"{driver.name} writes a niri snapshot itself — put it in Desk.qml, which "
            "is the one file pinned to the recording"
        )


def test_the_stand_ins_offer_everything_the_real_singletons_do():
    """A strip reading `Niri.somethingTheStandInForgot` does not error: QML
    hands it `undefined`, the Repeater builds nothing, and the shot is a picture
    of a bar with no workspaces on it — which is a picture this shell is
    DESIGNED to be able to draw (an unknown desk draws nothing), so it would
    look exactly right. Missing members have to fail HERE or they never fail at
    all."""
    for name in ("Niri.qml", "Motion.qml"):
        real = members(SHELL / name)
        stub = members(SHOTS / "stub" / name)
        assert real <= stub, (
            f"tools/barshots/stub/{name} is missing {sorted(real - stub)}, which the "
            "strip can read on the real one and would see as undefined here"
        )


def test_the_stand_ins_replace_nothing_but_the_quickshell_singletons():
    """The value of the sheet is that everything in it is the real file. Every
    stand-in is one more thing that is not — so there are two, both named here,
    and both for the same reason: they import Quickshell, whose QML plugin is
    linked into the quickshell binary and cannot be resolved by any other
    engine."""
    stubs = sorted(p.name for p in (SHOTS / "stub").glob("*.qml"))
    assert stubs == ["Motion.qml", "Niri.qml"], (
        f"tools/barshots/stub holds {stubs}: a third stand-in means a third piece "
        "of this shell the sheet is only pretending to show"
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


def test_the_stand_in_for_niri_replaces_the_pipe_and_not_the_model():
    """What the stand-in is allowed to be. The real `Niri.qml` is a child
    process, a parser hookup and a respawn timer around
    `core/NiriModel.qml`; the stand-in must be the same model with the child
    process gone. A stand-in that answered `workspacesOn` itself would make
    every shot a picture of the harness's idea of a desk — the per-output
    filter, the `idx` sort and the refusal to invent a workspace all live in
    that model, and they are what the pictures are evidence about."""
    stub = strip_qml_comments((SHOTS / "stub" / "Niri.qml").read_text("utf-8"))
    assert "NiriModel {" in stub, "the stand-in no longer drives the real model"
    assert "root.model.ingest(line)" in stub, (
        "the stand-in no longer feeds niri's own lines through the real parser"
    )
    assert "root.model.workspacesOn(output)" in stub, (
        "the stand-in answers `workspacesOn` itself instead of asking the model"
    )


def test_every_staged_file_is_the_real_one_or_a_declared_stand_in():
    """The script copies the shell verbatim and then writes over exactly two
    files. Anything else it stages is a piece of this bar the sheet is showing
    you a stand-in for without saying so."""
    script = SCRIPT.read_text("utf-8")
    written = set(re.findall(r'cp "\$root/tools/barshots/stub/(\S+?)" "\$stage/', script))
    assert written == {p.name for p in (SHOTS / "stub").glob("*.qml")}, written
    # And the one file it DELETES, which is the Quickshell half that has no
    # stand-in because the harness rebuilds it as Strip.qml instead.
    assert 'rm -f "$stage/shell.qml"' in script


def test_the_drivers_snapshot_is_the_line_niri_really_wrote():
    """Six of the nine shots are ares' own desk, and they are worth that much
    only while the line is the recording. A QML engine cannot read a file out of
    the repository, so this is a copy — and the failure a copy has is the one no
    desk written from memory would catch: `idx` that is really `index`, a `name`
    that is absent rather than null. Every one of those parses, changes nothing,
    and leaves a sheet of nine pictures of an empty bar that all look plausible.
    """
    lines = [l for l in RECORDING.read_text("utf-8").splitlines() if l.strip()]
    recorded = re.search(r"property string recorded:\s*'([^']*)'", desk_text())
    assert recorded, "Desk.qml no longer carries the recorded snapshot"
    assert recorded.group(1) == lines[0], (
        "the snapshot in tools/barshots/scene/Desk.qml is not "
        "harness/fixtures/niri/ares-desk.jsonl line 1 any more. One of the two "
        "was edited; the recording is the one that is evidence."
    )


def test_a_composed_desk_is_built_in_the_shape_niri_sends():
    """Two shots need a desk ares does not have — named workspaces, and a
    crowded row — so the driver builds the line itself. A builder is the place
    a composed shot stops being evidence: a field named `workspace_name`
    instead of `name` would parse, draw nothing, and photograph a bar that is
    empty for a reason the real one never has. So every key it writes is a key
    of the recorded line."""
    lines = [l for l in RECORDING.read_text("utf-8").splitlines() if l.strip()]
    real = set(json.loads(lines[0])["WorkspacesChanged"]["workspaces"][0])
    built = set(re.findall(r'"(\w+)":\s*r\.|"(\w+)":\s*null', strip_qml_comments(desk_text())))
    composed = {a or b for a, b in built}
    assert composed == real, (
        f"the composed snapshot writes {sorted(composed)} and niri sends "
        f"{sorted(real)} — a shot built out of fields the compositor does not "
        "send is not a picture of this machine"
    )


def test_every_shot_the_scene_takes_is_committed_and_vice_versa():
    """An uncommitted shot is one nobody can look at without running the
    harness; an orphaned PNG is a picture of a bar that no longer exists. Both
    are the sheet quietly ceasing to be the sheet."""
    taken = [s["file"] for s in sheet()]
    committed = sorted(p.name for p in SHEET.glob("*.png"))
    assert sorted(taken) == committed, (
        f"the scene takes {sorted(taken)} and docs/bar holds {committed} — run "
        "bash ops/ralph/barshots.sh and commit the result"
    )


def test_every_shot_is_described_and_the_composed_ones_say_so():
    """Six of these are ares' own desk and two are not, and a reader cannot tell
    by looking: a composed workspace name renders exactly like a recorded one.
    A sheet that let a composed picture be read as evidence about this machine
    would be doing the one thing a screenshot must never do — so the README
    says so, and every shot has a section a person can read beside the
    picture."""
    readme = (SHEET / "README.md").read_text("utf-8")
    assert "composed" in readme.lower()
    sections = readme.split("\n### ")[1:]
    for shot in sheet():
        name = shot["file"]
        shown = [s for s in sections if name in s]
        assert shown, f"docs/bar/README.md never mentions {name}"
        assert len(shown) == 1, f"docs/bar/README.md shows {name} in {len(shown)} sections"
        assert f"![{name}]({name})" in shown[0], (
            f"docs/bar/README.md describes {name} without showing it"
        )


def test_every_caption_is_a_reading_the_row_can_actually_produce():
    """The captions are the only thing telling two of these pictures apart — the
    whole vocabulary on this surface is a few characters in one of four greys —
    so they are checked twice: the driver checks them against the row, and this
    checks that the words are ones the row can say. A caption claiming
    `1:selected` would assert forever against a row that can only ever say
    `1:focused`, and the shot would go green saying nothing."""
    row = strip_qml_comments((SHELL / "Workspaces.qml").read_text("utf-8"))
    body = re.search(r"function reading\(w: var\): string \{(.*?)\n  \}", row, re.S)
    assert body, "Workspaces.qml no longer names what a workspace is doing in one place"
    declared = set(re.findall(r'"(\w+)"', body.group(1)))
    assert set(READINGS) == declared, (
        f"Workspaces.reading() says {sorted(declared)} and this sheet is written "
        f"against {sorted(READINGS)}"
    )
    seen: set[str] = set()
    for shot in sheet():
        for caption in shot["desk"]:
            label, _, reading = caption.rpartition(":")
            assert label, f"{shot['file']}: {caption!r} carries no label"
            assert reading in READINGS, (
                f"{shot['file']}: {reading!r} is not a word Workspaces.reading() says"
            )
            seen.add(reading)
    # And the sheet must actually exercise the vocabulary. A sheet that only
    # ever showed `1:focused` would be nine pictures of one case.
    assert seen == set(READINGS), f"no shot on this sheet draws {sorted(set(READINGS) - seen)}"


def test_the_colour_of_a_reading_is_chosen_where_the_word_is():
    """The pairing that makes the caption worth anything. `reading()` names what
    a workspace is doing and `tint()` turns that word into a token — so a
    caption saying `focused` over a label painted `text_3` is not a mistake this
    file can make. Both halves are checked here because the sheet's whole claim
    about colour rests on them being the same decision."""
    row = strip_qml_comments((SHELL / "Workspaces.qml").read_text("utf-8"))
    assert "function reading(w: var): string" in row
    assert "function tint(reading: string): color" in row
    # The word is attached to the label ONCE, in `entry()`, and everything
    # downstream carries that word rather than asking again: the delegate
    # paints `tint(reading)` off its own role and the caption prints the same
    # string. A delegate that re-derived the reading from the workspace would
    # be a second decision, and two decisions can differ.
    assert "\"reading\": root.reading(w)" in row, (
        "the things this row draws no longer carry the word `reading()` gave them"
    )
    assert "color: root.tint(reading)" in row, (
        "the delegate no longer takes its colour through tint(reading()), so the "
        "word in the caption and the colour on screen are two decisions"
    )
    assert "drew: root.shown.map(e => e.label + \":\" + e.reading)" in row, (
        "the row's account of what it drew no longer goes through reading()"
    )
    # …and the `+N` is in `drew` for the same reason every label is: it is a
    # thing on screen with a colour, and a sheet that photographed a row with
    # something in it the caption did not mention would be asserting less than
    # the picture shows.
    assert "function hidden(ws: var, plan: var): string" in row, (
        "nothing decides what the workspaces behind the `+N` amount to, so the "
        "marker cannot be painted from a reading and is not in the caption"
    )
    # …and each of the four is a §06 token rather than a colour of its own.
    for token in ("Theme.warn", "Theme.teal", "Theme.text2", "Theme.text3"):
        assert token in row, token


def test_the_sheet_photographs_both_monitor_sizes_ares_really_has():
    """The bar spans its output, so WIDTH is the one thing about this surface a
    harness cannot choose for itself — every question worth asking here (is the
    clock on screen, does the row reach the HUD's corner) is a question about a
    particular monitor. ares has two sizes, and the recording names them."""
    widths = {s["screen"] for s in sheet()}
    assert {2560, 1920} <= widths, (
        f"the sheet is taken at {sorted(widths)}; ares' own monitors are 2560 and 1920"
    )
    readme = (SHEET / "README.md").read_text("utf-8")
    for width in sorted(widths):
        assert str(width) in readme, f"docs/bar/README.md never says which shots are {width} px"


def test_the_sheet_photographs_the_clock_drawn_and_the_clock_gone():
    """`visible` on the clock has two reasons to be false and both are states
    the real bar is in: nothing has said the time yet (the first seconds of a
    session), and the monitor is too narrow for the centre to clear the HUD's
    corner. A sheet with no shot of either would photograph only the case that
    never fails."""
    clocks = [s["clock"] for s in sheet()]
    assert any(c for c in clocks), "no shot on this sheet draws the clock at all"
    assert any(not c for c in clocks), (
        "no shot photographs the bar with its clock gone, which is what a narrow "
        "monitor and an unknown time both look like"
    )
    # The narrow one is the one that cannot be inferred from the desk: it is a
    # width, and the sheet has to actually take it at that width.
    narrow = [s for s in sheet() if not s["clock"] and s["desk"]]
    assert narrow, (
        "every shot with no clock also has no workspaces, so nothing here "
        "distinguishes `the monitor is too narrow` from `nothing has started yet`"
    )


def test_the_sheet_photographs_a_desk_that_is_unknown_and_one_that_was_lost():
    """The two ways this bar has nothing to say, and they are the shots that
    prove it says nothing rather than guessing. A desk niri has not described
    yet and a desk whose event stream ended both draw no workspaces — and the
    second is the one that matters, because the model is holding a snapshot it
    could have gone on drawing."""
    scene = strip_qml_comments(scene_text())
    assert "Niri.drop(" in scene, (
        "no shot takes the bar through the stream ending, so nothing photographs "
        "the desk being forgotten"
    )
    empty = [s for s in sheet() if not s["desk"]]
    assert len(empty) >= 2, (
        f"{len(empty)} shot(s) draw an empty desk; there are two ways to be empty "
        "and they are worth telling apart"
    )
