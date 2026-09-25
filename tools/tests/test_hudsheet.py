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


def test_every_committed_shot_is_the_surface_box_the_scene_declares():
    """The first thing in this repo to open a committed PNG. shell.qml's
    surface is 300x807 and the scene renders that box exactly (A29), so a
    shot of any other size is a sheet taken with a different harness."""
    text = SCENE.read_text("utf-8")
    box = (
        int(re.search(r"^\s*width:\s*(\d+)", text, re.M).group(1)),
        int(re.search(r"^\s*height:\s*(\d+)", text, re.M).group(1)),
    )
    for name, data in sorted(committed().items()):
        img = hudsheet.decode_png(data)
        assert (img.width, img.height) == box, (
            f"{name} is {img.width}x{img.height}; the scene photographs a "
            f"{box[0]}x{box[1]} surface"
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


def run_cli(out: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "hudsheet.py"), "--root", str(ROOT), "--out", str(out)],
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
