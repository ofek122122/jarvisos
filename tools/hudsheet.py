#!/usr/bin/env python3
"""Read the HUD's contact sheet back, and say what moved (PLAN B52).

`ops/ralph/hudshots.sh` renders the real plates into `docs/hud/*.png` so that
looking at the HUD stops requiring a seat at ares (A29). It has written
thirteen pictures since, and until this file nothing had ever opened one.

That is not fussiness. B51's first honest mutation run over the plates found
it: `StatePlate.dotColor` can spend the ember — the one accent §06 reserves
for a machine that is genuinely doing something — on every state that is not
idle, and all thirteen photographs, all fifteen driver assertions and all 585
QML tests came back exactly as they were. The sheet was WRITTEN and never
COMPARED, so a plate could say anything it liked in any colour it liked.

A45 made the shots byte-reproducible, which is why this is cheap rather than
a project: the expected bytes already exist and are already committed.

WHERE "EXPECTED" LIVES. In git, always. A run that writes into `docs/hud` and
then compares against `docs/hud` has compared a file to itself, and the
refresh workflow has to stay one command — so `hudshots.sh` renders, then
this compares what it rendered against `HEAD:docs/hud`. Both paths get the
same rule: the grading run (which renders into a scratch directory) and the
refresh run (which renders over the sheet) are checked against the last
COMMITTED sheet, and a refresh that changed the HUD on purpose says so, loudly
and per-shot, with the new PNGs on disk to look at and commit.

AND THE SHEET THAT CANNOT BE BYTE-COMPARED (B74). `ops/ralph/hudscreens.sh`
photographs the REAL shell through a real compositor, and two runs of an
untouched HUD land a few dozen pixels apart on antialiased glyph edges — so
for thirty iterations that sheet could only be overwritten, never checked, and
a stale screen looked exactly as convincing as a current one. `Tolerance` is
the floor that makes it checkable: measured, not guessed, and stated in the
report every time it is applied.

WHAT IT SAYS. Bytes first — identical bytes are the same picture, that is the
ordinary case, and it costs nothing. When they differ, both are decoded and
the finding is a sentence: how many pixels moved, the box they moved in, and
three of them named in colour. "148 px differ inside x 16..29, y 20..33,
#4FB8BF -> #F0714A" is a report about the ember. "the PNGs differ" is not.
"""

from __future__ import annotations

import argparse
import dataclasses
import struct
import subprocess
import sys
import zlib
from pathlib import Path
from typing import Iterable, Mapping

MAGIC = b"\x89PNG\r\n\x1a\n"

# What Qt's offscreen grab actually writes, and the only shape this reads.
# Anything else is not a diff, it is news: see `Unreadable`.
DEPTH = 8
TRUECOLOUR = 2
TRUECOLOUR_ALPHA = 6
CHANNELS = {TRUECOLOUR: 3, TRUECOLOUR_ALPHA: 4}

SAMPLES = 3  # differing pixels named per finding: first, middle, last


@dataclasses.dataclass(frozen=True)
class Tolerance:
    """How far a re-render may sit from the committed sheet and still be the
    same picture (PLAN B74).

    The shots `hudshots.sh` renders are byte-reproducible (A45), so their
    tolerance is `EXACT` and this type is not in their way. The SCREENS are
    not: `hudscreens.sh` photographs a real compositor, and two runs of an
    untouched HUD land a few dozen pixels apart along antialiased glyph edges.
    Without a floor under that, the screens can only be overwritten and never
    checked — and a stale screen looks exactly as convincing as a current one.

    TWO bounds, because one of them cannot do the job alone. The measurement
    that set them (six comparisons over four renders of an unchanged HUD, PLAN
    B74) found up to 111 differing pixels — more than the 16 an ember square
    of 4x4 covers, so a COUNT can never be set below the smallest real change.
    What separates them is amplitude: every one of those differences was at
    most 3 on one channel, and anything a plate can SAY — a word, a colour, a
    box — moves a channel by a hundred or more. So `channel` is the bound that
    discriminates and `pixels` is the backstop it needs, for the one change
    that is small in amplitude and enormous in extent (a plate opacity of
    0.86 -> 0.855 moves every pixel of the glass by one).

    What this deliberately cannot see: a change that is ITSELF the size and
    amplitude of the compositor's rounding, i.e. a glyph landing a fraction of
    a pixel over. That is the price of the floor, and it is the same class of
    difference the floor is made of.
    """

    pixels: int = 0
    channel: int = 0


#: No floor at all: a differing pixel is a finding. The default everywhere,
#: and what the byte-reproducible contact sheet keeps.
EXACT = Tolerance(0, 0)


class Unreadable(Exception):
    """This PNG is not the shape the sheet is made of.

    Deliberately not a diff. A decoder that guesses at a 16-bit or interlaced
    image reports differences that are its own invention, and the honest
    report for "Qt changed what it writes" is that sentence and not a wall of
    changed pixels.
    """


@dataclasses.dataclass(frozen=True)
class Image:
    """One decoded shot, as RGBA bytes in row-major order."""

    width: int
    height: int
    pixels: bytes

    def pixel(self, x: int, y: int) -> tuple[int, int, int, int]:
        i = (y * self.width + x) * 4
        r, g, b, a = self.pixels[i : i + 4]
        return (r, g, b, a)


def parse_hex(text: str) -> tuple[int, int, int, int]:
    """`#RRGGBB` or `#RRGGBBAA` -> a pixel. The scene declares its backdrop in
    the first form and the theme writes both, so a test that wants to say
    "this is the colour it should be" can say it in the notation it reads."""
    s = text.lstrip("#")
    if len(s) not in (6, 8):
        raise ValueError(f"not a hex colour: {text!r}")
    vals = tuple(int(s[i : i + 2], 16) for i in range(0, len(s), 2))
    return vals if len(vals) == 4 else (*vals, 255)


def hexed(px: tuple[int, int, int, int]) -> str:
    """Opaque pixels lose the alpha: the sheet is drawn over an opaque
    backdrop, so `#F0714AFF` on every line would be four characters of noise
    on thirteen pictures. A pixel that is NOT opaque is news and keeps it."""
    r, g, b, a = px
    tail = "" if a == 255 else f"{a:02X}"
    return f"#{r:02X}{g:02X}{b:02X}{tail}"


# ------------------------------------------------------------------- decoding


def _chunks(data: bytes):
    """Walk the chunk stream, refusing anything that does not end in IEND — a
    half-written file must be a refusal and never a picture with a plausible
    top half."""
    if data[:8] != MAGIC:
        raise Unreadable("not a PNG: the 8-byte signature is missing")
    pos, closed = 8, False
    while pos + 8 <= len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        typ = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        if len(body) != length:
            raise Unreadable(
                f"truncated: the {typ.decode('ascii', 'replace')} chunk claims "
                f"{length} bytes and the file has {len(body)}"
            )
        yield typ, body
        if typ == b"IEND":
            closed = True
        pos += 12 + length
    if not closed:
        raise Unreadable("truncated: the file ends without an IEND chunk")


def _unfilter(raw: bytes, width: int, height: int, bpp: int) -> bytes:
    """Undo the five PNG scanline filters. Qt picks one per line and we do not
    get to choose, so all five are here or the decoder only works by luck."""
    stride = width * bpp
    out = bytearray()
    prior = bytes(stride)
    pos = 0
    for y in range(height):
        kind = raw[pos]
        line = bytearray(raw[pos + 1 : pos + 1 + stride])
        pos += 1 + stride
        for i in range(stride):
            left = line[i - bpp] if i >= bpp else 0
            up = prior[i]
            upleft = prior[i - bpp] if i >= bpp else 0
            if kind == 0:
                pass
            elif kind == 1:
                line[i] = (line[i] + left) & 0xFF
            elif kind == 2:
                line[i] = (line[i] + up) & 0xFF
            elif kind == 3:
                line[i] = (line[i] + (left + up) // 2) & 0xFF
            elif kind == 4:
                p = left + up - upleft
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - upleft)
                best = left if (pa <= pb and pa <= pc) else (up if pb <= pc else upleft)
                line[i] = (line[i] + best) & 0xFF
            else:
                raise Unreadable(f"scanline {y} uses filter type {kind}, which is not a filter")
        out += line
        prior = bytes(line)
    return bytes(out)


def decode_png(data: bytes) -> Image:
    """An 8-bit, non-interlaced, truecolour PNG -> RGBA pixels.

    That is exactly what `grabImage(...).save()` writes offscreen. Every other
    shape raises `Unreadable`, on purpose.
    """
    header = None
    body = bytearray()
    for typ, chunk in _chunks(data):
        if typ == b"IHDR":
            header = struct.unpack(">IIBBBBB", chunk)
        elif typ == b"IDAT":
            body += chunk
    if header is None:
        raise Unreadable("no IHDR: this file has no image header")

    width, height, depth, colour, compression, filt, interlace = header
    if interlace:
        raise Unreadable("interlaced: the sheet is written progressive-free and read that way")
    if depth != DEPTH:
        raise Unreadable(f"{depth}-bit samples; this reads {DEPTH}-bit only")
    if colour not in CHANNELS:
        raise Unreadable(
            f"colour type {colour}; this reads truecolour "
            f"({TRUECOLOUR}) and truecolour+alpha ({TRUECOLOUR_ALPHA}) only"
        )
    if compression or filt:
        raise Unreadable(f"compression {compression}, filter method {filt}: not the standard pair")

    bpp = CHANNELS[colour]
    try:
        raw = zlib.decompress(bytes(body))
    except zlib.error as e:
        raise Unreadable(f"the image data will not inflate: {e}") from e
    want = height * (1 + width * bpp)
    if len(raw) != want:
        raise Unreadable(f"the image data is {len(raw)} bytes and a {width}x{height} image needs {want}")

    flat = _unfilter(raw, width, height, bpp)
    if bpp == 4:
        return Image(width, height, flat)
    rgba = bytearray(width * height * 4)
    rgba[0::4] = flat[0::3]
    rgba[1::4] = flat[1::3]
    rgba[2::4] = flat[2::3]
    rgba[3::4] = b"\xff" * (width * height)
    return Image(width, height, bytes(rgba))


# ------------------------------------------------------------------ comparing


def _moved_pixels(want: Image, got: Image) -> list[tuple[int, int]]:
    """Every pixel that is not the same pixel, in reading order."""
    return [
        (x, y)
        for y in range(want.height)
        for x in range(want.width)
        if want.pixel(x, y) != got.pixel(x, y)
    ]


def _worst_channel(want: Image, got: Image, moved: list[tuple[int, int]]) -> int:
    """The largest single-channel move, over every pixel that moved (B74).

    This is the number that tells a compositor rounding a glyph edge apart
    from a plate saying something else. The theme's text sits ~180 from the
    glass it is drawn on and the ember is further still, so anything legible
    lands in the hundreds; antialiasing lands on 1, 2, 3.
    """
    return max(
        (
            max(abs(a - b) for a, b in zip(want.pixel(x, y), got.pixel(x, y)))
            for x, y in moved
        ),
        default=0,
    )


@dataclasses.dataclass(frozen=True)
class Grade:
    """One shot, graded. Both fields empty = the same picture, said plainly.

    `absorbed` is the half that only exists because of the screens: `(pixels,
    worst channel)` for a difference a `Tolerance` decided was the
    compositor's rounding. It is not a finding — but it is not nothing
    either, and the caller prints it, because a floor nobody is told about is
    a comparison nobody can audit.
    """

    finding: str | None = None
    absorbed: tuple[int, int] | None = None


def _report(
    want: Image,
    got: Image,
    moved: list[tuple[int, int]],
    worst: int,
    tolerance: Tolerance,
) -> str:
    total = want.width * want.height
    xs = [x for x, _ in moved]
    ys = [y for _, y in moved]
    picks = sorted({0, len(moved) // 2, len(moved) - 1})[:SAMPLES]
    lines = [
        f"{len(moved)} px of {total} differ ({100 * len(moved) / total:.2f}%), "
        f"inside x {min(xs)}..{max(xs)}, y {min(ys)}..{max(ys)}"
    ]
    for i in picks:
        x, y = moved[i]
        lines.append(f"      ({x},{y})  {hexed(want.pixel(x, y))} -> {hexed(got.pixel(x, y))}")
    # Which bound broke, when there was one to break. A sheet with a noise
    # floor has already forgiven differences this size, so the report has to
    # say what made this one different or the reader cannot tell whether the
    # floor is working.
    if tolerance != EXACT:
        over = []
        if len(moved) > tolerance.pixels:
            over.append(f"{len(moved)} px against a floor of {tolerance.pixels}")
        if worst > tolerance.channel:
            over.append(f"{worst} per channel against a floor of {tolerance.channel}")
        lines.append("      past the compositor's rounding: " + "; ".join(over))
    return "\n".join(lines)


def grade_shot(expected: bytes, actual: bytes, *, tolerance: Tolerance = EXACT) -> Grade:
    """One shot against its committed self.

    Byte equality is the fast path and not the claim: two encodings of the
    same pixels are the same photograph, and calling that a change would make
    this gate a liability the first time Qt picks a different filter.

    With `EXACT` — the default, and what the contact sheet uses — a single
    differing pixel is a finding, because that sheet is byte-reproducible and
    has no honest reason to move. With a floor (B74), a difference that is
    both small enough and faint enough is reported as `absorbed` instead.
    """
    if expected == actual:
        return Grade()

    try:
        want = decode_png(expected)
    except Unreadable as e:
        return Grade(f"the COMMITTED shot is unreadable: {e}")
    try:
        got = decode_png(actual)
    except Unreadable as e:
        return Grade(f"the rendered shot is unreadable: {e}")

    if (want.width, want.height) != (got.width, got.height):
        return Grade(
            f"the run drew {got.width}x{got.height}; the committed shot is "
            f"{want.width}x{want.height}"
        )

    moved = _moved_pixels(want, got)
    if not moved:
        return Grade()

    worst = _worst_channel(want, got, moved)
    # `EXACT` is (0, 0) and a pixel that moved moved by at least one, so this
    # cannot fire for the sheet that has no floor. That is the whole reason
    # the default is a pair of zeroes rather than a None to be checked for.
    if len(moved) <= tolerance.pixels and worst <= tolerance.channel:
        return Grade(absorbed=(len(moved), worst))

    return Grade(_report(want, got, moved, worst, tolerance))


def compare_shot(
    expected: bytes, actual: bytes, *, tolerance: Tolerance = EXACT
) -> str | None:
    """`grade_shot`, for a caller that only wants the finding. `None` = the
    same picture — which now includes "different, and below the floor"."""
    return grade_shot(expected, actual, tolerance=tolerance).finding


def grade_sheet(
    expected: Mapping[str, bytes],
    produced: Mapping[str, bytes],
    *,
    tolerance: Tolerance = EXACT,
) -> dict[str, Grade]:
    """The whole sheet, in file order — every shot either sheet has.

    Both directions matter. A shot the run did NOT write is the strongest
    thing here — a driver that quietly stops photographing a plate would
    otherwise pass a comparison over whatever it did produce — and a shot the
    committed sheet has never seen is a new picture nobody has looked at.
    Neither can be absorbed by any floor: they are not differences of degree.
    """
    out: dict[str, Grade] = {}
    for name in sorted(set(expected) | set(produced)):
        if name not in produced:
            out[name] = Grade(
                "the run did not write it — the committed sheet has this shot "
                "and this render does not"
            )
        elif name not in expected:
            out[name] = Grade(
                "the run wrote a shot the committed sheet has never seen — "
                "look at it, then commit it"
            )
        else:
            out[name] = grade_shot(expected[name], produced[name], tolerance=tolerance)
    return out


def compare_sheet(
    expected: Mapping[str, bytes],
    produced: Mapping[str, bytes],
    *,
    tolerance: Tolerance = EXACT,
) -> list[str]:
    """The findings alone, each prefixed with its shot. Empty = the HUD looks
    like its picture."""
    return [
        f"{name}: {grade.finding}"
        for name, grade in grade_sheet(expected, produced, tolerance=tolerance).items()
        if grade.finding is not None
    ]


# --------------------------------------------------------------- where it comes from


def committed_sheet(root: Path, rev: str, relpath: str) -> dict[str, bytes]:
    """The sheet as committed at `rev` — the only honest source of "expected"
    for a renderer that may be writing over the working copy as it goes."""
    listing = subprocess.run(
        ["git", "-C", str(root), "ls-tree", "--name-only", rev, "--", f"{relpath}/"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    out = {}
    for path in listing:
        name = path.rsplit("/", 1)[-1]
        if not name.endswith(".png"):
            continue
        out[name] = subprocess.run(
            ["git", "-C", str(root), "show", f"{rev}:{path}"],
            capture_output=True,
            check=True,
        ).stdout
    return out


def produced_sheet(out: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(out.glob("*.png"))}


def restore(out: Path, expected: Mapping[str, bytes], names: Iterable[str]) -> None:
    """Put the committed bytes back over shots that only moved by rounding.

    The only file this writes is one it has just compared, and the only bytes
    it writes are the ones it compared that file AGAINST. That is what makes a
    screens run idempotent: without it, `hudscreens.sh` leaves a dirty tree
    after every run of an untouched HUD, and a diff that is always dirty is a
    diff nobody reads (PLAN B74, and B72's second reason for not binding it).
    """
    for name in names:
        (out / name).write_bytes(expected[name])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, required=True, help="the repository")
    ap.add_argument("--out", type=Path, required=True, help="where the run wrote its PNGs")
    ap.add_argument("--rev", default="HEAD", help="the revision the sheet is expected at")
    ap.add_argument("--sheet", default="docs/hud", help="the sheet's path in the tree")
    ap.add_argument(
        "--rerun",
        default="bash ops/ralph/hudshots.sh",
        help="the command that would refresh this sheet, named in the report",
    )
    ap.add_argument(
        "--tolerance-pixels",
        type=int,
        default=0,
        metavar="N",
        help="pixels per shot a re-render may differ by and still be the same "
        "picture (default 0: the contact sheet is byte-reproducible)",
    )
    ap.add_argument(
        "--tolerance-channel",
        type=int,
        default=0,
        metavar="N",
        help="the largest single-channel move that counts as the compositor's "
        "rounding rather than a change (default 0)",
    )
    ap.add_argument(
        "--accept-noise",
        action="store_true",
        help="restore the committed bytes over shots that only moved by "
        "rounding, so a run of an unchanged HUD leaves a clean tree",
    )
    args = ap.parse_args(argv)

    tolerance = Tolerance(args.tolerance_pixels, args.tolerance_channel)
    if args.accept_noise and tolerance == EXACT:
        print(
            "hudsheet: --accept-noise with no floor to accept — pass "
            "--tolerance-pixels and --tolerance-channel, or drop it",
            file=sys.stderr,
        )
        return 2

    expected = committed_sheet(args.root, args.rev, args.sheet)
    produced = produced_sheet(args.out)
    graded = grade_sheet(expected, produced, tolerance=tolerance)
    absorbed = {name: g.absorbed for name, g in graded.items() if g.absorbed}
    findings = [f"{name}: {g.finding}" for name, g in graded.items() if g.finding]

    if absorbed:
        if args.accept_noise:
            restore(args.out, expected, absorbed)
        worst_px = max(px for px, _ in absorbed.values())
        worst_ch = max(ch for _, ch in absorbed.values())
        print(
            f"hudsheet: {len(absorbed)} of {len(produced)} shots differ only by "
            f"the compositor's rounding (worst {worst_px} px, {worst_ch} per "
            f"channel, inside a floor of {tolerance.pixels} px and "
            f"{tolerance.channel} per channel) — "
            + ("restored to the committed bytes" if args.accept_noise else "left as rendered")
        )

    if not findings:
        print(
            f"hudsheet: all {len(produced)} shots match the sheet committed at "
            f"{args.rev}:{args.sheet}"
        )
        return 0

    print(f"hudsheet: {len(findings)} of {len(expected)} shots are not what is committed:")
    print()
    for finding in findings:
        print(f"  {finding}")
    print()
    print(
        "If you changed the HUD on purpose, this is the sheet catching up: the\n"
        "new PNGs are on disk — LOOK at them, then commit them and the next\n"
        f"`{args.rerun}` is green. If you did not change the HUD,\n"
        f"something drew a different picture than the one in {args.sheet}."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
