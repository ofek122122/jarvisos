#!/usr/bin/env python3
"""Read a pixel of the art, and refuse a render the drawing is not in (PLAN E11).

`pkgs/jarvis-wallpaper` rasterizes six PNGs that sit under every window on this
machine, and until this file nothing in the repo had ever opened one. Every gate
the wallpaper has is a gate on the SHELL over it: the jv-wall build lints its
QML, `shellload.sh` loads it under a real quickshell, `wallshots.sh` photographs
the surface, and `test_wallshots.py` holds the shell's anchor to the art's three
fractions. All four can be green over a render with no drawing in it.

WHAT THAT COST, once, and why this exists. E9's composer did its arithmetic in
awk, and `-v sub=...` names a gawk builtin: gawk refused the whole program with
one line on stderr, `eval ""` set nothing, and every coordinate in the drawing
expanded to the empty string — `translate( )`, `r=""`, `y=""`. resvg IGNORES an
invalid attribute rather than failing, so it rendered a wallpaper with the
instrument collapsed into the top-left corner and exited 0. So did the package.
So did `nix build`. So did every gate in this repo. What caught it was a human
looking at a PNG, which is not a gate.

WHAT IT CHECKS, and it is deliberately six pixels rather than an image diff.
There is no expected raster to compare against — the art is generated from a
theme and composed per geometry, so a committed golden PNG would have to be
regenerated for every canvas anybody ever adds (E10) and would make a palette
change look like a regression. What IS stable is the CONTRACT: the art puts a
reticle at `instrumentX` x `instrumentY` of its canvas and a comet head one
`instrumentR` above it, both painted in the one warm colour §06 has, and the
corners of the field are the field.

  · `centre` and `head` must be EXACTLY the ember. Measured on all six renders
    the package writes, at every geometry: #F0714A, exact, no antialiasing
    anywhere near them. The two marks are `circle r="6"` and `circle r="9"` in
    ABSOLUTE px, so the sample lands deep inside an opaque fill whatever the
    canvas is — which is what makes an exact match honest here rather than
    brittle.
  · the four corners must be COOL and DARK: no channel brighter than the
    brightest colour the field is made of, and never warmer than neutral. Two
    bounds because neither does the job alone — ember is caught by warmth (it is
    the only warm colour in the palette) and the wordmark is a cool near-white
    that only brightness can catch.

THE SAMPLE POINTS COME FROM THE CONTRACT AND NEVER FROM THE IMAGE. A checker
that located the instrument and then measured it would pass a wallpaper with the
instrument anywhere at all, which is precisely the picture E9 shipped. Because
the points are arithmetic on the three fractions, a radius that rasterized to
nothing leaves the head's point on bare ground and a drawing that slid into the
corner leaves ember where the field should be — the degenerate render fails
both, separately.

WHAT IT CANNOT SEE, stated because a gate whose reach is unstated gets trusted
for the whole picture: everything between those points. The rings, the dashed
tick, the teal, the grid's pitch, the wordmark's face and the vignette are not
read at all — `docs/wall/` is the sheet a human looks at for those, and this is
the thing that makes a build fail without one.

The decoder is `tools/hudsheet.py`'s, unchanged: pure Python, 8-bit,
non-interlaced, and about a microsecond per pixel — 22 s for all six renders,
which is the price of this gate and is paid inside a package that rebuilds only
when the art or the theme moves.
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
from pathlib import Path

from hudsheet import Image, Unreadable, decode_png, hexed, parse_hex

Pixel = tuple[int, int, int, int]

#: How far in from each edge a corner is sampled. Far enough to clear the grid's
#: hairline, which the pattern draws at x=0 and y=0, and nowhere near the
#: wordmark, which the art sets at x=120 — so the bound below is about the field
#: and not about what happens to be painted at the very first pixel.
INSET = 4

#: Warm means "ember is here": red above blue. Every colour in §06's palette but
#: the ember is cool (ground -10 on this measure, line -19, text -10, teal -112),
#: so a corner that is warm AT ALL is a corner with the instrument in it. The
#: bound is therefore neutral rather than a margin somebody chose.
NEUTRAL = 0


@dataclasses.dataclass(frozen=True)
class Contract:
    """The three fractions `pkgs/jarvis-wallpaper` composes with and
    `shell/jv-wall` anchors to — the one contract in this repo written in two
    languages. This checker is a third reader of them, and the builder passes its
    own `instrument*` bindings so there is no fourth copy."""

    x: float
    y: float
    r: float


@dataclasses.dataclass(frozen=True)
class Sample:
    """One pixel this gate reads, and what the art says has to be there."""

    name: str
    x: int
    y: int
    want: str  # "warm" | "field"
    why: str


def samples(contract: Contract, width: int, height: int) -> list[Sample]:
    """The six points, derived from the contract and the canvas alone.

    `head` is one `instrumentR` of the SHORTER side above the centre, which is
    where the comet's head is drawn — twelve o'clock on the outer ring. It is the
    only sample that reads the radius, and the radius is the half of the contract
    a picture of the shell cannot check.
    """
    cx, cy = round(contract.x * width), round(contract.y * height)
    ro = contract.r * min(width, height)
    far_x, far_y = width - 1 - INSET, height - 1 - INSET
    return [
        Sample("centre", cx, cy, "warm", "the reticle at the instrument's centre"),
        Sample(
            "head",
            cx,
            round(contract.y * height - ro),
            "warm",
            "the comet's head, twelve o'clock on the instrument's outer ring",
        ),
        Sample("top-left", INSET, INSET, "field", "the empty field"),
        Sample("top-right", far_x, INSET, "field", "the empty field"),
        Sample("bottom-left", INSET, far_y, "field", "the empty field"),
        Sample("bottom-right", far_x, far_y, "field", "the empty field"),
    ]


def ceiling(field: tuple[Pixel, ...]) -> int:
    """The brightest single channel the field is allowed to reach: the grid's
    `line` over the vignette's two ends, as the builder hands them over. Derived
    from the tokens rather than chosen, so a palette that gets lighter moves this
    bound with it."""
    return max(max(px[:3]) for px in field)


def _warm_finding(sample: Sample, got: Pixel, warm: Pixel) -> str | None:
    if got[:3] == warm[:3]:
        return None
    return (
        f"{sample.name} ({sample.x},{sample.y}) is {hexed(got)} — the contract "
        f"puts {sample.why} exactly here, drawn in {hexed(warm)}"
    )


def _field_finding(sample: Sample, got: Pixel, field: tuple[Pixel, ...]) -> str | None:
    warmth = got[0] - got[2]
    if warmth > NEUTRAL:
        return (
            f"{sample.name} ({sample.x},{sample.y}) is {hexed(got)} — warmer than "
            f"anything {sample.why} is made of (red over blue by {warmth}); the "
            "ember is the only warm colour in the palette"
        )
    bright = max(got[:3])
    if bright > ceiling(field):
        return (
            f"{sample.name} ({sample.x},{sample.y}) is {hexed(got)} — brighter on "
            f"one channel ({bright}) than the brightest colour {sample.why} is "
            f"made of ({ceiling(field)}: "
            + ", ".join(hexed(px) for px in field)
            + ")"
        )
    return None


def check_image(
    image: Image,
    contract: Contract,
    *,
    warm: str,
    field: tuple[str, ...] | list[str],
) -> tuple[list[str], list[str]]:
    """One decoded render against the contract.

    Returns the findings and, separately, what it SAW: every sample as a pixel,
    printed on every run. A check whose output is the word "ok" cannot be
    audited, and the colour found at the contract's own point is the whole of the
    evidence this gate produces.
    """
    want_warm = parse_hex(warm)
    want_field = tuple(parse_hex(c) for c in field)
    findings: list[str] = []
    seen: list[str] = []
    for sample in samples(contract, image.width, image.height):
        if not (0 <= sample.x < image.width and 0 <= sample.y < image.height):
            findings.append(
                f"{sample.name} ({sample.x},{sample.y}) is outside a "
                f"{image.width}x{image.height} render — {sample.why} cannot be "
                "read, so nothing here says the drawing is in this canvas"
            )
            continue
        got = image.pixel(sample.x, sample.y)
        seen.append(f"{sample.name}({sample.x},{sample.y})={hexed(got)}")
        finding = (
            _warm_finding(sample, got, want_warm)
            if sample.want == "warm"
            else _field_finding(sample, got, want_field)
        )
        if finding:
            findings.append(finding)
    return findings, seen


def check_file(
    path: Path,
    contract: Contract,
    *,
    warm: str,
    field: tuple[str, ...] | list[str],
) -> tuple[list[str], list[str]]:
    """One file on disk. A file that will not decode is a finding and never a
    pass: the failure this gate answers is a renderer that exited 0 on garbage,
    so shrugging at an unreadable PNG would be the same mistake one level up."""
    try:
        image = decode_png(path.read_bytes())
    except Unreadable as e:
        return [f"this file is not a render this can read: {e}"], []
    except OSError as e:
        return [f"this file cannot be read: {e}"], []
    return check_image(image, contract, warm=warm, field=field)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--at",
        required=True,
        metavar="FX,FY",
        help="the instrument's centre as a fraction of the canvas — the art's "
        "own instrumentX and instrumentY",
    )
    ap.add_argument(
        "--radius",
        required=True,
        type=float,
        metavar="FR",
        help="the outer ring as a fraction of the canvas's shorter side — the "
        "art's own instrumentR",
    )
    ap.add_argument(
        "--warm",
        required=True,
        metavar="HEX",
        help="the one warm colour the instrument's marks are painted in "
        "(theme.toml's ember)",
    )
    ap.add_argument(
        "--field",
        action="append",
        default=[],
        metavar="HEX",
        help="a colour the empty field is allowed to be made of; repeatable, "
        "and the brightest of them is the corner bound",
    )
    ap.add_argument("renders", nargs="*", type=Path, help="the PNGs to sample")
    args = ap.parse_args(argv)

    if not args.renders:
        # A glob that matched nothing is exactly how this gate would go quietly
        # missing, so it is an error and not an empty green.
        print(
            "artsample: no renders to sample — the glob matched nothing, and a "
            "gate over zero files is not a gate",
            file=sys.stderr,
        )
        return 2
    if not args.field:
        print("artsample: no --field colour given, so there is no corner bound", file=sys.stderr)
        return 2
    try:
        fx, fy = (float(n) for n in args.at.split(","))
    except ValueError:
        print(f"artsample: --at wants FX,FY and got {args.at!r}", file=sys.stderr)
        return 2

    contract = Contract(fx, fy, args.radius)
    failed = 0
    for path in args.renders:
        findings, seen = check_file(path, contract, warm=args.warm, field=args.field)
        print(f"artsample: {path.name}  " + "  ".join(seen))
        # Every line of this report on ONE stream, in the order it was found:
        # the findings and the pixels they are about interleave unreadably in a
        # build log otherwise, which is where this gate does its work.
        for finding in findings:
            print(f"  {finding}")
        failed += bool(findings)

    if not failed:
        print(
            f"artsample: {len(args.renders)} renders carry the drawing at "
            f"{fx} x {fy} of their own canvas, with the comet's head at "
            f"{args.radius} of the shorter side"
        )
        return 0

    print(
        f"\nartsample: {failed} of {len(args.renders)} renders do not carry the "
        "drawing.\nThe art composes an instrument at those fractions and this read "
        "the pixels where\nit has to be. resvg ignores an invalid attribute rather "
        "than failing, so a\nrender with no drawing in it exits 0 — that is the "
        "whole reason this runs.\nLOOK at the PNGs named above."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
