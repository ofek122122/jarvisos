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
from typing import Mapping

MAGIC = b"\x89PNG\r\n\x1a\n"

# What Qt's offscreen grab actually writes, and the only shape this reads.
# Anything else is not a diff, it is news: see `Unreadable`.
DEPTH = 8
TRUECOLOUR = 2
TRUECOLOUR_ALPHA = 6
CHANNELS = {TRUECOLOUR: 3, TRUECOLOUR_ALPHA: 4}

SAMPLES = 3  # differing pixels named per finding: first, middle, last


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


def compare_shot(expected: bytes, actual: bytes) -> str | None:
    """One shot against its committed self. `None` = the same picture.

    Byte equality is the fast path and not the claim: two encodings of the
    same pixels are the same photograph, and calling that a change would make
    this gate a liability the first time Qt picks a different filter.
    """
    if expected == actual:
        return None

    try:
        want = decode_png(expected)
    except Unreadable as e:
        return f"the COMMITTED shot is unreadable: {e}"
    try:
        got = decode_png(actual)
    except Unreadable as e:
        return f"the rendered shot is unreadable: {e}"

    if (want.width, want.height) != (got.width, got.height):
        return (
            f"the run drew {got.width}x{got.height}; the committed shot is "
            f"{want.width}x{want.height}"
        )

    moved = [
        (x, y)
        for y in range(want.height)
        for x in range(want.width)
        if want.pixel(x, y) != got.pixel(x, y)
    ]
    if not moved:
        return None

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
    return "\n".join(lines)


def compare_sheet(
    expected: Mapping[str, bytes], produced: Mapping[str, bytes]
) -> list[str]:
    """The whole sheet, in file order. Empty = the HUD looks like its picture.

    Both directions matter. A shot the run did NOT write is the strongest
    thing here — a driver that quietly stops photographing a plate would
    otherwise pass a comparison over whatever it did produce — and a shot the
    committed sheet has never seen is a new picture nobody has looked at.
    """
    findings = []
    for name in sorted(set(expected) | set(produced)):
        if name not in produced:
            findings.append(
                f"{name}: the run did not write it — the committed sheet has "
                f"this shot and this render does not"
            )
        elif name not in expected:
            findings.append(
                f"{name}: the run wrote a shot the committed sheet has never "
                f"seen — look at it, then commit it"
            )
        else:
            one = compare_shot(expected[name], produced[name])
            if one is not None:
                findings.append(f"{name}: {one}")
    return findings


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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, required=True, help="the repository")
    ap.add_argument("--out", type=Path, required=True, help="where the run wrote its PNGs")
    ap.add_argument("--rev", default="HEAD", help="the revision the sheet is expected at")
    ap.add_argument("--sheet", default="docs/hud", help="the sheet's path in the tree")
    args = ap.parse_args(argv)

    expected = committed_sheet(args.root, args.rev, args.sheet)
    produced = produced_sheet(args.out)
    findings = compare_sheet(expected, produced)

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
        "`bash ops/ralph/hudshots.sh` is green. If you did not change the HUD,\n"
        "something drew a different picture than the one in docs/hud."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
