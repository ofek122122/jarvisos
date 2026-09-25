"""tools/hudsheet.py — reading the contact sheet back (PLAN B52).

`ops/ralph/hudshots.sh` has written thirteen PNGs since A29 and nothing has
ever opened one. That is not a gap in taste, it is a gap in the gates: B51's
first honest grading run mutated `StatePlate.dotColor` so that the ember —
the one accent §06 spends on nothing else — was painted on every state that
is not idle, and all thirteen photographs, all fifteen driver tests and all
585 QML tests stayed exactly as they were. The sheet is WRITTEN and never
COMPARED, so a plate may say anything it likes in any colour it likes.

A45 already made the shots byte-reproducible, which is the whole reason this
is cheap: the expected bytes exist, they are committed, and `git show` is the
only place they can honestly come from — a run that writes into `docs/hud`
and then compares against `docs/hud` has compared a file to itself.

So: bytes first (identical bytes are identical pictures, and that is the
common case and costs nothing), and when they differ, DECODE both and say
what moved. "148 px differ inside x 16..29, y 20..33, #4FB8BF -> #F0714A" is
a sentence about the ember; "the PNGs differ" is not.
"""

from __future__ import annotations

import re
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import hudsheet  # noqa: E402

# The prose scanner (A73) lives with the screen sheet's other instruments,
# and this document is gated by the same one on purpose: two regexes reading
# for the same mistake in two READMEs is one of them going quietly out of
# date while the other keeps passing.
sys.path.insert(0, str(ROOT / "tools" / "hudscreens"))
import sheet  # noqa: E402

SHEET = ROOT / "docs" / "hud"
SCENE = ROOT / "tools" / "hudshots" / "scene" / "tst_shots.qml"


# ------------------------------------------------------------ a PNG, by hand

FILTERS = (0, 1, 2, 3, 4)


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def _filtered(raw: bytes, prior: bytes, bpp: int, kind: int) -> bytes:
    out = bytearray()
    for i, x in enumerate(raw):
        left = raw[i - bpp] if i >= bpp else 0
        up = prior[i]
        upleft = prior[i - bpp] if i >= bpp else 0
        if kind == 0:
            out.append(x)
        elif kind == 1:
            out.append((x - left) & 0xFF)
        elif kind == 2:
            out.append((x - up) & 0xFF)
        elif kind == 3:
            out.append((x - (left + up) // 2) & 0xFF)
        else:
            out.append((x - _paeth(left, up, upleft)) & 0xFF)
    return bytes(out)


def png(
    rows: list[list[tuple[int, ...]]],
    *,
    color_type: int = 2,
    depth: int = 8,
    interlace: int = 0,
    filters: list[int] | None = None,
    chunks: int = 1,
) -> bytes:
    """Encode an image the way Qt would, and on demand the ways it would not.

    `filters` chooses the per-scanline filter type, because a decoder that
    only ever meets filter 0 is a decoder that has only ever met a test.
    """
    height = len(rows)
    width = len(rows[0])
    bpp = {0: 1, 2: 3, 6: 4}[color_type]
    filters = filters or [0] * height

    body = bytearray()
    prior = bytes(width * bpp)
    for y, row in enumerate(rows):
        raw = bytes(v for px in row for v in px[:bpp])
        body.append(filters[y])
        body += _filtered(raw, prior, bpp, filters[y])
        prior = raw

    def chunk(typ: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + typ
            + data
            + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, depth, color_type, 0, 0, interlace)
    z = zlib.compress(bytes(body))
    step = max(1, -(-len(z) // chunks))
    parts = [z[i : i + step] for i in range(0, len(z), step)]
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + b"".join(chunk(b"IDAT", p) for p in parts)
        + chunk(b"IEND", b"")
    )


def flat(width: int, height: int, colour: tuple[int, ...]) -> list[list[tuple[int, ...]]]:
    return [[colour] * width for _ in range(height)]


# ------------------------------------------------------------------ decoding


def test_a_hand_written_png_round_trips_under_every_filter():
    """All five PNG filter types, because Qt picks per scanline and we do not
    get to choose. A decoder that gets Paeth wrong reads a gradient as noise
    and would report every shot as different for the rest of time."""
    rows = [
        [(x * 3 % 256, y * 7 % 256, (x + y) % 256) for x in range(9)] for y in range(5)
    ]
    for kind in FILTERS:
        img = hudsheet.decode_png(png(rows, filters=[kind] * len(rows)))
        assert (img.width, img.height) == (9, 5), kind
        for y in range(5):
            for x in range(9):
                assert img.pixel(x, y) == (*rows[y][x], 255), (kind, x, y)


def test_alpha_survives_and_opaque_is_the_default():
    rgba = [[(9, 8, 7, 64), (1, 2, 3, 255)]]
    assert hudsheet.decode_png(png(rgba, color_type=6)).pixel(0, 0) == (9, 8, 7, 64)
    assert hudsheet.decode_png(png([[(9, 8, 7)]])).pixel(0, 0) == (9, 8, 7, 255)


def test_the_image_data_may_arrive_in_several_chunks():
    """libpng splits IDAT; so does Qt on anything large. The committed shots
    happen to use one chunk each, which is exactly why this is a test and not
    an observation."""
    rows = [[(x, y, 0) for x in range(40)] for y in range(40)]
    one = hudsheet.decode_png(png(rows))
    many = hudsheet.decode_png(png(rows, chunks=5))
    assert one.pixels == many.pixels


@pytest.mark.parametrize(
    "kwargs, says",
    [
        ({"depth": 16}, "16"),
        ({"color_type": 0}, "colour type 0"),
        ({"interlace": 1}, "interlaced"),
    ],
)
def test_what_it_cannot_read_it_refuses_out_loud(kwargs, says):
    """A decoder that guesses at an unfamiliar PNG reports differences that
    are its own. The shots are 8-bit truecolour and non-interlaced; anything
    else means Qt changed what it writes, and that is news, not a diff."""
    rows = flat(2, 2, (1, 2, 3, 4))
    with pytest.raises(hudsheet.Unreadable) as e:
        hudsheet.decode_png(png(rows, **{"color_type": 6, **kwargs}))
    assert says in str(e.value)


def test_a_truncated_file_is_refused_rather_than_padded():
    data = png(flat(4, 4, (1, 2, 3)))
    with pytest.raises(hudsheet.Unreadable):
        hudsheet.decode_png(data[: len(data) // 2])


def test_a_header_that_lies_about_the_size_is_refused():
    """The chunk stream is intact, the CRCs are right, and the IHDR claims one
    more row than the image data holds. Without the length check that reads as
    a picture with a missing last line, and every comparison after it is a
    report about an off-by-one that only ever existed in this decoder."""
    data = bytearray(png(flat(4, 4, (1, 2, 3))))
    ihdr = data[16:29]                      # 8 magic + 4 length + 4 type
    ihdr[7] = 5                             # height, low byte of the second u32
    data[16:29] = ihdr
    data[29:33] = struct.pack(">I", zlib.crc32(b"IHDR" + bytes(ihdr)) & 0xFFFFFFFF)

    with pytest.raises(hudsheet.Unreadable) as e:
        hudsheet.decode_png(bytes(data))
    assert "needs" in str(e.value)


def test_something_that_is_not_a_png_at_all_is_refused():
    with pytest.raises(hudsheet.Unreadable):
        hudsheet.decode_png(b"<html>not a picture</html>")


# ----------------------------------------------------------------- comparing


def test_identical_bytes_are_no_finding():
    data = png(flat(3, 3, (0x31, 0x35, 0x3B)))
    assert hudsheet.compare_shot(data, data) is None


def test_two_encodings_of_the_same_picture_are_no_finding():
    """Byte equality is the fast path, not the claim. A45 makes the shots
    reproducible, but a PNG that says the same thing with different filters
    is the same picture and this must not call it a change."""
    rows = [[(x * 5 % 256, 0, 9) for x in range(6)] for _ in range(4)]
    a = png(rows, filters=[0, 0, 0, 0])
    b = png(rows, filters=[1, 2, 3, 4])
    assert a != b
    assert hudsheet.compare_shot(a, b) is None


def test_a_changed_pixel_is_counted_boxed_and_named():
    rows = flat(10, 10, (0x4F, 0xB8, 0xBF))
    after = [list(r) for r in rows]
    for y in range(2, 5):
        for x in range(3, 6):
            after[y][x] = (0xF0, 0x71, 0x4A)

    finding = hudsheet.compare_shot(png(rows), png(after))
    assert finding is not None
    assert "9 px" in finding and "100" in finding  # 9 of 100
    assert "x 3..5" in finding and "y 2..4" in finding
    assert "#4FB8BF" in finding and "#F0714A" in finding


def test_the_samples_span_the_change_and_are_capped():
    """Three coordinates, from the start, middle and end of the changed run —
    a diff that dumps every pixel is a diff nobody reads, and one that dumps
    only the first is a diff that hides a second colour."""
    rows = flat(30, 30, (0, 0, 0))
    after = [list(r) for r in rows]
    for y in range(30):
        for x in range(30):
            after[y][x] = (255, 255, 255)

    finding = hudsheet.compare_shot(png(rows), png(after))
    coords = re.findall(r"\((\d+),(\d+)\)", finding)
    assert len(coords) == 3
    assert coords[0] == ("0", "0") and coords[-1] == ("29", "29")


def test_alpha_shows_in_the_colour_when_it_is_not_opaque():
    a = png([[(1, 2, 3, 255)]], color_type=6)
    b = png([[(1, 2, 3, 128)]], color_type=6)
    finding = hudsheet.compare_shot(a, b)
    assert "#010203 -> #01020380" in finding


def test_a_different_size_is_reported_as_a_size_and_not_as_pixels():
    """A plate that grew past the surface box changes the picture's SHAPE.
    Diffing that pixelwise would report every pixel after the first row and
    say nothing; the two numbers are the finding."""
    finding = hudsheet.compare_shot(png(flat(4, 4, (0, 0, 0))), png(flat(4, 5, (0, 0, 0))))
    assert "4x4" in finding and "4x5" in finding
    assert "differ" not in finding


def test_a_shot_that_cannot_be_decoded_is_a_finding_and_not_a_crash():
    """The comparator runs at the end of a long render; a corrupt file must
    end up in the report next to the others, not as a traceback that hides
    the twelve findings above it."""
    finding = hudsheet.compare_shot(png(flat(2, 2, (0, 0, 0))), b"truncated")
    assert finding is not None and "unreadable" in finding.lower()


# --------------------------------------------------------------- the whole sheet


def test_a_sheet_that_matches_has_no_findings():
    shots = {"01.png": png(flat(2, 2, (1, 1, 1))), "02.png": png(flat(2, 2, (2, 2, 2)))}
    assert hudsheet.compare_sheet(shots, dict(shots)) == []


def test_a_shot_the_run_did_not_write_is_a_finding():
    """The strongest mutation this catches: a driver that stops taking a
    picture at all. Comparing only what was produced would call that clean."""
    expected = {"01.png": png(flat(2, 2, (1, 1, 1))), "02.png": png(flat(2, 2, (2, 2, 2)))}
    (finding,) = hudsheet.compare_sheet(expected, {"01.png": expected["01.png"]})
    assert finding.startswith("02.png")
    assert "did not write" in finding


def test_a_shot_the_sheet_has_never_seen_is_a_finding():
    expected = {"01.png": png(flat(2, 2, (1, 1, 1)))}
    produced = dict(expected, **{"14-new.png": png(flat(2, 2, (3, 3, 3)))})
    (finding,) = hudsheet.compare_sheet(expected, produced)
    assert finding.startswith("14-new.png")
    assert "commit" in finding


def test_findings_come_back_in_sheet_order():
    expected = {f"0{i}.png": png(flat(2, 2, (i, i, i))) for i in (1, 2, 3)}
    produced = {f"0{i}.png": png(flat(2, 2, (9, 9, 9))) for i in (1, 2, 3)}
    assert [f.split(".png")[0] for f in hudsheet.compare_sheet(expected, produced)] == [
        "01",
        "02",
        "03",
    ]


# ------------------------------------------------------- against the real sheet


def committed() -> dict[str, bytes]:
    return hudsheet.committed_sheet(ROOT, "HEAD", "docs/hud")


def test_the_committed_sheet_is_what_git_says_it_is():
    shots = committed()
    assert len(shots) == len(list(SHEET.glob("*.png")))
    assert set(shots) == {p.name for p in SHEET.glob("*.png")}
    assert "README.md" not in shots


def scene_box() -> tuple[int, int]:
    """The box the scene renders into, read off the scene. `test_hudshots.py`
    pins every driver in that directory to `shell.qml`'s surface (A63), so
    this is the HUD's own box and not a copy that can quietly drift from it.
    """
    text = SCENE.read_text("utf-8")
    return (
        int(re.search(r"^\s*width:\s*(\d+)", text, re.M).group(1)),
        int(re.search(r"^\s*height:\s*(\d+)", text, re.M).group(1)),
    )


def test_every_committed_shot_is_the_surface_box_the_scene_declares():
    """The first thing in this repo to open a committed PNG. shell.qml's
    surface is 300x826 and the scene renders that box exactly (A29), so a
    shot of any other size is a sheet taken with a different harness."""
    box = scene_box()
    for name, data in sorted(committed().items()):
        img = hudsheet.decode_png(data)
        assert (img.width, img.height) == box, (
            f"{name} is {img.width}x{img.height}; the scene photographs a "
            f"{box[0]}x{box[1]} surface"
        )


def test_every_box_the_readme_quotes_is_the_box_the_scene_renders():
    """A74. This sheet opens with "300 × 807 px, the box", and until now
    nothing read that sentence — it is right today only because A71 happened
    to update it by hand. Its twin one directory down was not so lucky: it
    said `300x560` through four growths of the surface, and A73 pinned it.
    Same failure, same instrument, other document.

    Stricter than A73's gate, deliberately. That sheet may quote monitors and
    the whole desk because it photographs a real compositor on real screens.
    This one disclaims everything a compositor owns — layer-shell, the input
    mask, the exclusive zone, the three monitors — so the only box it can
    honestly be describing is the one the scene renders, and a monitor size
    appearing here is prose that has wandered into the other sheet's subject.

    Nor is there an older-than-the-box case to state, the way A73 had to:
    `hudshots.sh` re-renders these PNGs on every HUD iteration and the test
    above measures every one of them against this same box, so the pictures
    cannot be older than the sentence.
    """
    box = scene_box()
    quoted = sheet.boxes_in_prose((SHEET / "README.md").read_text("utf-8"))
    assert quoted, (
        "docs/hud/README.md quotes no box at all — the sentence this gate was "
        "built to hold has gone, and a gate over nothing passes forever"
    )
    for other in sorted(quoted - {box}):
        raise AssertionError(
            f"docs/hud/README.md quotes {other[0]}x{other[1]}; the scene "
            f"renders {box[0]}x{box[1]}, which is the only box this sheet "
            "describes — monitors and the desk belong to docs/hud/screens"
        )


def test_the_quiet_shot_is_an_empty_field_of_the_declared_backdrop():
    """§06's earned emptiness, asserted in bytes for the first time.
    01-quiet.png is a HUD that can see the bus and has nothing to say, so
    every one of its 206 400 pixels is the backdrop the scene declares —
    and the backdrop is deliberately NOT a theme colour, so any Jarvis ink
    anywhere in this picture is a plate that spoke when it should not have."""
    backdrop = re.search(r'property color backdrop:\s*"(#[0-9A-Fa-f]{6})"', SCENE.read_text("utf-8"))
    assert backdrop, "the scene no longer declares a backdrop colour"
    want = hudsheet.parse_hex(backdrop.group(1))

    img = hudsheet.decode_png(committed()["01-quiet.png"])
    seen = {img.pixel(x, y) for y in range(img.height) for x in range(img.width)}
    assert seen == {want}, (
        f"01-quiet.png draws {sorted(seen - {want})[:4]} as well as the "
        f"backdrop {backdrop.group(1)} — something is lit in the quiet shot"
    )


def test_the_committed_sheet_compares_clean_against_itself():
    shots = committed()
    assert hudsheet.compare_sheet(shots, dict(shots)) == []


# ----------------------------------------------------------------------- CLI


SCRIPT = ROOT / "ops" / "ralph" / "hudshots.sh"


def test_the_renderer_reads_its_own_sheet_back():
    """A comparator nothing calls is a comparator that grades nothing.

    `hudshots.sh` is the only thing that renders the sheet and it is also the
    only thing `--runner shots` executes, so this call is the whole of B52's
    reach: without it the mutation harness goes back to grading thirteen
    pictures by their file names. It has to run AFTER the renderer, over the
    directory the renderer was told to write to (a grading run renders into a
    scratch directory, and comparing docs/hud against docs/hud would be the
    one comparison that can never fail), and its exit status has to survive —
    an `|| true` here would be a green run over a sheet that moved.
    """
    script = SCRIPT.read_text("utf-8")
    assert "set -euo pipefail" in script, "a failing comparator would not stop the script"

    call = re.search(r"^(?!\s*#).*tools/hudsheet\.py.*$", script, re.M)
    assert call, "hudshots.sh renders the sheet and never reads it back (B52)"
    line = call.group(0)
    assert '--out "$out"' in line, (
        f"the comparator grades {line.strip()!r} — it has to grade the directory "
        "the renderer wrote to, which under --runner shots is a scratch dir"
    )
    assert "||" not in line and not line.rstrip().endswith("true"), (
        f"the comparator's exit status is swallowed: {line.strip()!r}"
    )
    assert script.index("qmltestrunner") < call.start(), (
        "the sheet is compared before it is rendered"
    )


def test_the_sheet_tells_its_reader_that_it_is_compared():
    """docs/hud/README.md is what a person meets before the pictures, and it
    spent thirteen shots saying the opposite — that nothing byte-compares
    them, because a pixel assertion breaks when a font ships a new version.
    The fonts are pinned from the flake, so it does not; but a document that
    tells a reader a gate does not exist is worse than no document, and the
    reader who needs this line is the one whose deliberate HUD change has
    just ended `hudshots.sh` nonzero."""
    readme = (SHEET / "README.md").read_text("utf-8")
    assert "hudsheet.py" in readme, (
        "the sheet does not tell its reader it is compared, or how to refresh it"
    )
    assert "not byte-compared" not in readme


def run_cli(out: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "hudsheet.py"), "--root", str(ROOT), "--out", str(out), *extra],
        capture_output=True,
        text=True,
    )


def test_the_cli_is_green_on_a_faithful_copy_of_the_sheet(tmp_path):
    out = tmp_path / "shots"
    out.mkdir()
    for p in SHEET.glob("*.png"):
        shutil.copy(p, out / p.name)

    done = run_cli(out)
    assert done.returncode == 0, done.stdout + done.stderr
    # The COUNT, read off the sheet rather than written down. It was the
    # literal `13` until A71 added a fourteenth shot, at which point this
    # was a check that the sheet had not grown — which is a thing that is
    # supposed to happen and is already asserted next door.
    assert f"all {len(list(SHEET.glob('*.png')))} shots match" in done.stdout


def test_the_cli_names_the_shot_that_moved_and_exits_nonzero(tmp_path):
    """The whole point, end to end: a run whose plates drew something else.
    Standing one shot in for another is the cheapest way to make a picture
    that is the right SIZE and the wrong CONTENT — which is precisely what
    a mutated `dotColor` produces."""
    out = tmp_path / "shots"
    out.mkdir()
    for p in SHEET.glob("*.png"):
        shutil.copy(p, out / p.name)
    shutil.copy(SHEET / "01-quiet.png", out / "04-speaking.png")

    done = run_cli(out)
    assert done.returncode == 1
    assert "04-speaking.png" in done.stdout
    # The denominator is the surface box, read off the scene rather than
    # written down: a literal here went stale the day A63 grew the box and
    # failed this test for a reason that had nothing to do with what it is
    # about.
    shot = hudsheet.decode_png((SHEET / "01-quiet.png").read_bytes())
    assert f"px of {shot.width * shot.height} differ" in done.stdout
    assert "hudshots.sh" in done.stdout, "a failure that does not say how to refresh"


def test_the_cli_says_nothing_about_shots_that_did_not_move(tmp_path):
    out = tmp_path / "shots"
    out.mkdir()
    for p in SHEET.glob("*.png"):
        shutil.copy(p, out / p.name)
    shutil.copy(SHEET / "01-quiet.png", out / "04-speaking.png")

    done = run_cli(out)
    assert "03-heard.png" not in done.stdout


# ------------------------- the floor under a sheet that cannot be compared (B74)
#
# Everything above is about `docs/hud`, which is byte-reproducible and keeps
# `EXACT`. `docs/hud/screens` is not: it is photographed through a real
# compositor, and two runs of an UNCHANGED HUD land a few dozen pixels apart
# on antialiased glyph edges. For thirty iterations that meant those seven
# screens could only be overwritten — nothing ever asked whether they still
# showed the HUD this repo draws, and a stale screen is exactly as convincing
# as a current one.
#
# The floor that makes them checkable is measured (see NOISE_PIXELS in
# tools/hudscreens/sheet.py). What these tests hold is the shape of it: that
# it absorbs the rounding, that it absorbs NOTHING else, that it says out loud
# whenever it absorbed anything, and that the sheet which does not need it
# does not get it.

FLOOR = hudsheet.Tolerance(pixels=256, channel=3)

GLASS = (0x0C, 0x11, 0x16)


def nudged(rows, count: int, delta: int):
    """A copy of `rows` with `count` pixels moved by `delta` on one channel.

    The shape the compositor's rounding actually takes, and the reason the
    count alone cannot grade it: single values, one channel, scattered.
    """
    out = [list(r) for r in rows]
    width = len(rows[0])
    for i in range(count):
        y, x = divmod(i, width)
        r, g, b = out[y][x][:3]
        out[y][x] = (r, g + delta, b)
    return out


def test_a_faint_scatter_is_the_compositors_rounding_and_not_a_finding():
    rows = flat(40, 40, GLASS)
    grade = hudsheet.grade_shot(png(rows), png(nudged(rows, 30, 1)), tolerance=FLOOR)
    assert grade.finding is None
    assert grade.absorbed == (30, 1), grade


def test_the_same_scatter_is_a_finding_on_the_sheet_that_has_no_floor():
    """The contact sheet renders offscreen and IS reproducible (A45), so one
    pixel out of place there is news. The floor is a property of the sheet
    being compared, not of this comparator, and the default is no floor."""
    rows = flat(40, 40, GLASS)
    finding = hudsheet.compare_shot(png(rows), png(nudged(rows, 30, 1)))
    assert finding is not None and "30 px" in finding
    assert "floor" not in finding, "a sheet with no floor must not talk about one"


def test_a_faint_change_too_wide_to_be_rounding_is_a_finding():
    """The backstop, and the reason the count is in the floor at all: a plate
    opacity of 0.86 -> 0.855 moves every pixel of the glass by one. Each of
    those pixels is indistinguishable from rounding; there are just far too
    many of them."""
    rows = flat(40, 40, GLASS)
    finding = hudsheet.compare_shot(
        png(rows), png(nudged(rows, FLOOR.pixels + 1, 1)), tolerance=FLOOR
    )
    assert finding is not None
    assert f"{FLOOR.pixels + 1} px against a floor of {FLOOR.pixels}" in finding
    assert "per channel against" not in finding, (
        "the amplitude was inside the floor and the report blamed it anyway"
    )


def test_one_loud_pixel_is_a_finding_however_few():
    """The bound that actually discriminates. Anything a plate can SAY — a
    word, a colour, a box — moves a channel by a hundred or more, so a single
    pixel past the amplitude floor is a change however small the count."""
    rows = flat(40, 40, GLASS)
    finding = hudsheet.compare_shot(
        png(rows), png(nudged(rows, 1, FLOOR.channel + 1)), tolerance=FLOOR
    )
    assert finding is not None
    assert f"{FLOOR.channel + 1} per channel against a floor of {FLOOR.channel}" in finding
    assert "px against a floor" not in finding


def test_the_worst_channel_is_the_worst_and_not_the_first():
    """One loud pixel among three hundred faint ones is still a change, and a
    report that read only the first differing pixel would absorb it."""
    rows = flat(40, 40, GLASS)
    after = nudged(rows, 30, 1)
    after[20][20] = (0xF0, 0x71, 0x4A)
    finding = hudsheet.compare_shot(png(rows), png(after), tolerance=FLOOR)
    assert finding is not None and "per channel against a floor" in finding


def test_a_shot_that_is_missing_or_new_is_never_absorbed():
    """Neither is a difference of degree, so no floor may reach them: a
    driver that quietly stops photographing a plate must not be graded as
    rounding."""
    one = png(flat(4, 4, GLASS))
    gone = hudsheet.grade_sheet({"a.png": one}, {}, tolerance=FLOOR)["a.png"]
    fresh = hudsheet.grade_sheet({}, {"a.png": one}, tolerance=FLOOR)["a.png"]
    assert gone.finding and gone.absorbed is None
    assert fresh.finding and fresh.absorbed is None


def test_an_unreadable_or_resized_shot_is_never_absorbed():
    rows = flat(8, 8, GLASS)
    bigger = hudsheet.grade_shot(png(rows), png(flat(9, 8, GLASS)), tolerance=FLOOR)
    broken = hudsheet.grade_shot(png(rows), b"not a png at all", tolerance=FLOOR)
    assert bigger.finding and bigger.absorbed is None
    assert broken.finding and broken.absorbed is None


def test_restore_writes_back_exactly_what_it_compared_against(tmp_path):
    """The idempotence half. What it writes is the bytes it graded the file
    against — not a re-encode, not a copy of something else on disk — because
    the only thing that makes overwriting a photograph honest is that the
    photograph it replaces was just proved to be the same picture."""
    out = tmp_path / "shots"
    out.mkdir()
    committed = png(flat(8, 8, GLASS))
    (out / "01.png").write_bytes(png(nudged(flat(8, 8, GLASS), 4, 1)))
    hudsheet.restore(out, {"01.png": committed}, ["01.png"])
    assert (out / "01.png").read_bytes() == committed


# ------------------------------------------------------------ and through the CLI


def nudge_file(path: Path, count: int, delta: int) -> None:
    """Move `count` pixels of a real committed shot by `delta`, in place."""
    img = hudsheet.decode_png(path.read_bytes())
    rows = [[img.pixel(x, y)[:3] for x in range(img.width)] for y in range(img.height)]
    path.write_bytes(png(nudged(rows, count, delta)))


@pytest.fixture
def copied_sheet(tmp_path) -> Path:
    out = tmp_path / "shots"
    out.mkdir()
    for p in SHEET.glob("*.png"):
        shutil.copy(p, out / p.name)
    return out


FLOOR_ARGS = ("--tolerance-pixels", str(FLOOR.pixels), "--tolerance-channel", str(FLOOR.channel))


def test_the_cli_absorbs_the_rounding_stays_green_and_says_what_it_absorbed(copied_sheet):
    """A floor nobody is told about is a comparison nobody can audit, so the
    count and the amplitude it forgave are printed on a GREEN run."""
    nudge_file(copied_sheet / "01-quiet.png", 30, 1)
    done = run_cli(copied_sheet, *FLOOR_ARGS)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "30 px" in done.stdout and "1 per channel" in done.stdout
    assert "left as rendered" in done.stdout
    assert "shots match" in done.stdout


def test_the_cli_leaves_the_rendered_file_alone_unless_asked(copied_sheet):
    """A grading run into a scratch directory — or the next person measuring
    the noise — must get back exactly what was rendered."""
    nudge_file(copied_sheet / "01-quiet.png", 30, 1)
    before = (copied_sheet / "01-quiet.png").read_bytes()
    run_cli(copied_sheet, *FLOOR_ARGS)
    assert (copied_sheet / "01-quiet.png").read_bytes() == before


def test_accept_noise_puts_the_committed_bytes_back(copied_sheet):
    """What makes a screens run idempotent: an unchanged HUD leaves a clean
    tree, so a dirty `git status` after a run means something again."""
    nudge_file(copied_sheet / "01-quiet.png", 30, 1)
    done = run_cli(copied_sheet, *FLOOR_ARGS, "--accept-noise")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "restored to the committed bytes" in done.stdout
    assert (copied_sheet / "01-quiet.png").read_bytes() == (SHEET / "01-quiet.png").read_bytes()


def test_accept_noise_does_not_touch_a_shot_that_really_moved(copied_sheet):
    """The dangerous mutation, and the one this file exists to catch: a
    restore that ran on findings would delete the evidence of a changed HUD
    and report it green."""
    nudge_file(copied_sheet / "01-quiet.png", 4, 40)
    changed = (copied_sheet / "01-quiet.png").read_bytes()
    done = run_cli(copied_sheet, *FLOOR_ARGS, "--accept-noise")
    assert done.returncode == 1
    assert (copied_sheet / "01-quiet.png").read_bytes() == changed


def test_accept_noise_restores_the_rounding_and_only_the_rounding(copied_sheet):
    """The refresh a real HUD change produces: one screen drew something
    else, and the other six jittered on a glyph edge the way they always do.
    The restore has to run — that is what keeps the diff down to the picture
    that moved — and it has to touch NOTHING else, or the evidence of the
    change is overwritten by the bytes it was supposed to be compared with,
    and the run reports it green.
    """
    nudge_file(copied_sheet / "01-quiet.png", 30, 1)
    moved = copied_sheet / "02-listening.png"
    nudge_file(moved, 4, 40)
    changed = moved.read_bytes()

    done = run_cli(copied_sheet, *FLOOR_ARGS, "--accept-noise")
    assert done.returncode == 1
    assert "02-listening.png" in done.stdout
    assert (copied_sheet / "01-quiet.png").read_bytes() == (SHEET / "01-quiet.png").read_bytes()
    assert moved.read_bytes() == changed, (
        "the restore reached a shot that really moved: a changed HUD would be "
        "put back to its old picture and the change reported green"
    )


def test_accept_noise_without_a_floor_is_refused(copied_sheet):
    """There is nothing to accept, and a flag that silently does nothing is
    how a screens run would quietly stop being idempotent."""
    done = run_cli(copied_sheet, "--accept-noise")
    assert done.returncode == 2
    assert "no floor" in done.stderr


def test_a_green_run_with_nothing_absorbed_says_nothing_about_a_floor(copied_sheet):
    done = run_cli(copied_sheet, *FLOOR_ARGS)
    assert done.returncode == 0
    assert "rounding" not in done.stdout


def test_the_report_names_the_harness_that_would_refresh_this_sheet(copied_sheet):
    """Two harnesses share this comparator now, and a screens run that told
    the reader to re-run `hudshots.sh` would send them to the wrong sheet."""
    shutil.copy(SHEET / "01-quiet.png", copied_sheet / "04-speaking.png")
    done = run_cli(copied_sheet, "--rerun", "bash ops/ralph/hudscreens.sh")
    assert done.returncode == 1
    assert "bash ops/ralph/hudscreens.sh" in done.stdout
    assert "hudshots" not in done.stdout


def test_the_contact_sheet_is_still_compared_to_the_byte():
    """The floor belongs to the screens and to nothing else. `hudshots.sh`
    renders offscreen and is byte-reproducible (A45), so a tolerance there
    would be teeth removed from the gate that has them."""
    shots = (ROOT / "ops" / "ralph" / "hudshots.sh").read_text("utf-8")
    assert "--tolerance" not in shots and "--accept-noise" not in shots, (
        "ops/ralph/hudshots.sh compares its sheet with a floor — that sheet "
        "is byte-reproducible and has no honest reason to move at all"
    )
