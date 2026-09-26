"""tools/artsample.py — the first gate in this repo that looks at the ART (E11).

Every other gate on the wallpaper looks at the SHELL over it. `shellload.sh`
proves jv-wall loads, the jv-wall build lints its QML, `wallshots.sh`
photographs the surface and `test_wallshots.py` holds the shell's anchor to the
art's three fractions — and not one of them opens a PNG that
`pkgs/jarvis-wallpaper` wrote. Nothing did, for the whole life of that package.

E9 is what that cost. `awk -v sub=...` names a gawk builtin, gawk refused the
whole program with one line on stderr, `eval ""` set nothing, and every
coordinate in the drawing expanded to the empty string: `translate( )`, `r=""`,
`y=""`. resvg IGNORES an invalid attribute rather than failing, so it rendered a
wallpaper with the instrument collapsed into the top-left corner and exited 0 —
and so did the package, and so did `nix build`, and so did every gate. What
caught it was a human looking at a picture.

So these are tests about a CHECKER, and the checker's claim is deliberately
narrow: the art puts a reticle at `instrumentX` x `instrumentY` of its canvas
and a comet head one `instrumentR` above it, both painted in the one warm colour
§06 has, and the corners of the field are the field.

THE SAMPLE POINTS COME FROM THE CONTRACT, NEVER FROM THE IMAGE, which is what
makes a collapsed instrument visible: a radius that rasterized to nothing leaves
the head's point on empty ground, and a drawing that slid into a corner leaves
ember where the field should be. Both of the degenerate render's halves fail,
separately, and the test for each is below.

The last four tests are the ones this suite is the THIRD PARTY to (invariant 1):
a checker is only evidence about the art if the builder points it at the art's
own `instrument*` bindings and the theme's own colours, and neither the package
nor the checker can say that about itself.
"""

import re
import sys

import pytest

# One parser for this repo's nix and QML, not five; and one PNG writer, the one
# the contact sheet's own decoder is tested with.
from test_gen_theme_qml import ROOT
from test_hudsheet import flat, png

sys.path.insert(0, str(ROOT / "tools"))

import artsample  # noqa: E402

ART = ROOT / "pkgs" / "jarvis-wallpaper" / "default.nix"
THEME = ROOT / "personality" / "theme.toml"


def token(name: str) -> str:
    """The art's own colours, as personality/theme.toml spells them. Read rather
    than written: a test that hard-codes #F0714A is one more place the ember
    lives, and invariant 9 says there is exactly one."""
    m = re.search(rf'^{name} = "(#[0-9A-Fa-f]{{6}})"', THEME.read_text("utf-8"), re.M)
    assert m, f"personality/theme.toml no longer has a {name}"
    return m.group(1)


EMBER = token("ember")
GROUND = token("ground")
GROUND_DEEP = token("ground_deep")
LINE = token("line")

#: Every colour the corners of the field are allowed to be made of: the
#: vignette's two ends and the grid's hairline.
FIELD = (GROUND, GROUND_DEEP, LINE)

# A canvas small enough to encode in a test and large enough for the six sample
# points to be six distinct pixels.
W, H = 200, 120
CONTRACT = artsample.Contract(0.734, 0.681, 0.39)

#: The absolute radii the art paints its two warm marks at — `circle r="6"` for
#: the reticle core and `r="9"` for the comet's head. Absolute, not scaled: they
#: are the reason the sample can be an EXACT colour match at every geometry.
CORE = 6


def rgb(colour: str) -> tuple[int, int, int]:
    return artsample.parse_hex(colour)[:3]


def warm_points(w: int = W, h: int = H) -> list[tuple[int, int]]:
    """Where a correct render paints ember, taken from the checker's own sample
    list — so a test cannot accidentally agree with a checker that moved."""
    return [(s.x, s.y) for s in artsample.samples(CONTRACT, w, h) if s.want == "warm"]


def field_of(w: int = W, h: int = H) -> list[list[tuple[int, ...]]]:
    return flat(w, h, rgb(GROUND_DEEP))


def disc(rows, cx: int, cy: int, r: int, colour: tuple[int, ...]) -> None:
    h, w = len(rows), len(rows[0])
    for y in range(max(0, cy - r), min(h, cy + r + 1)):
        for x in range(max(0, cx - r), min(w, cx + r + 1)):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                rows[y][x] = colour


def render(*discs: tuple[int, int, int], w: int = W, h: int = H) -> bytes:
    """A field of `ground_deep` with ember discs painted on it — the whole of the
    art this checker can see, and a composition it can be handed by a test.

    `discs` are `(x, y, r)` in pixels, so a test can put the instrument where the
    contract says, a few pixels off it, or in the corner the gawk bug put it.
    """
    rows = field_of(w, h)
    for cx, cy, r in discs:
        disc(rows, cx, cy, r, rgb(EMBER))
    return png(rows)


def composed(w: int = W, h: int = H) -> bytes:
    """The render the art is supposed to make: a reticle at the two fractions and
    a comet head one radius above it."""
    return render(*[(x, y, CORE) for x, y in warm_points(w, h)], w=w, h=h)


def check(data: bytes, contract: artsample.Contract = CONTRACT):
    return artsample.check_image(
        artsample.decode_png(data), contract, warm=EMBER, field=FIELD
    )


# ------------------------------------------------------- the composed render


def test_a_composed_render_passes_and_says_what_it_saw():
    """The ordinary case, and the half that has to be quiet or the gate gets
    switched off. It still REPORTS every pixel it read: a check whose output is
    "ok" cannot be audited, and the colour actually found at the contract's own
    point is the whole of the evidence this gate produces."""
    findings, seen = check(composed())
    assert findings == [], findings
    assert len(seen) == len(artsample.samples(CONTRACT, W, H)) == 6
    assert any("centre" in line and EMBER.upper() in line.upper() for line in seen)
    assert any("head" in line and EMBER.upper() in line.upper() for line in seen)


def test_the_samples_are_the_contract_and_not_the_image():
    """Where this gate gets its coordinates is the whole reason it works. A
    checker that FOUND the instrument and then measured it would pass a wallpaper
    whose instrument is anywhere at all — which is exactly the picture E9
    shipped. These points are arithmetic on the three fractions and nothing
    else."""
    points = {s.name: (s.x, s.y) for s in artsample.samples(CONTRACT, W, H)}
    assert points["centre"] == (round(0.734 * W), round(0.681 * H))
    assert points["head"] == (round(0.734 * W), round(0.681 * H - 0.39 * min(W, H)))
    # …and the corners are the field, inset far enough to clear the grid's
    # hairline at x=0 and y=0 and nowhere near the wordmark at x=120.
    assert points["top-left"] == (artsample.INSET, artsample.INSET)
    assert points["bottom-right"] == (W - 1 - artsample.INSET, H - 1 - artsample.INSET)


# ----------------------------------------------- the render E9 actually shipped


def test_the_degenerate_render_fails_both_halves():
    """THE BUG THIS FILE EXISTS FOR. Every coordinate empty means `translate( )`
    is the identity and every radius is the default, so what resvg drew was the
    reticle and the head on top of each other at the origin: an ember smudge in
    the top-left corner of a field with no instrument in it.

    Both halves of that are findings, separately — the instrument is missing from
    where the contract says it is, AND the corner of the field is not the field.
    Either one alone would be a checker that a drawing which merely MOVED could
    still fool."""
    findings, _ = check(render((0, 0, 20)))
    blamed = " ".join(findings)
    assert len(findings) >= 3, findings
    for name in ("centre", "head", "top-left"):
        assert name in blamed, f"{name} is not in the report: {findings}"
    # And it says what it wanted and what it found, so the report is actionable
    # without opening the PNG it is about.
    assert EMBER.upper() in blamed.upper() and GROUND_DEEP.upper() in blamed.upper()


def test_a_radius_that_rasterized_to_nothing_is_a_finding():
    """The half of the contract no other gate can see, and the centre sample
    cannot either: `instrumentR`. An instrument drawn in the right place with no
    radius leaves the comet's head on empty ground, while the shell's anchor, the
    sheet's `paint` and the centre pixel all still agree."""
    centre, head = warm_points()
    findings, _ = check(render((*centre, CORE)))
    assert len(findings) == 1, findings
    assert "head" in findings[0] and f"({head[0]},{head[1]})" in findings[0]


def test_an_instrument_a_few_pixels_off_is_a_finding():
    """The drift this is a gate against is not always catastrophic. A composer
    that rounds the wrong way, or one of the three fractions edited in only one
    of the two languages it is written in, moves the drawing a little — and the
    reticle is 12 px across, so a little is all it takes for the contract's own
    point to land on ground."""
    off = [(x + CORE + 3, y, CORE) for x, y in warm_points()]
    findings, _ = check(render(*off))
    assert len(findings) == 2, findings


# ------------------------------------------------------ the field, and the type


def test_a_wordmark_in_the_corner_is_a_finding_even_though_it_is_cool():
    """The corner claim is two bounds, because one cannot do the job. Ember is
    caught by WARMTH — it is the only warm colour §06 has — and the wordmark is
    not warm at all: `text` is a cool near-white. What catches that is
    BRIGHTNESS, against the brightest colour the field is allowed to be made of,
    which is the grid's `line`. A wordmark that slid into the corner is the same
    class of failure as an instrument that did, and the art moves both of them
    with the same arithmetic."""
    rows = field_of()
    for y in range(12):
        for x in range(40):
            rows[y][x] = rgb(token("text"))
    for x, y in warm_points():
        disc(rows, x, y, CORE, rgb(EMBER))
    findings, _ = check(png(rows))
    assert len(findings) == 1, findings
    assert "top-left" in findings[0] and "brighter" in findings[0]


def test_the_grid_and_the_gradient_are_not_findings():
    """What the field bound must NOT fire on, or it is a gate nobody can keep
    green: the vignette between `ground` and `ground_deep`, and the grid's
    hairline of `line` at 14% over either. The real renders come out #090D12 and
    #0A0E13 at the four corners — measured on all six — but the bound has to hold
    for a corner that lands ON a grid line, which is the one thing an inset
    cannot promise at every geometry."""
    grid = tuple(round(0.14 * c + 0.86 * g) for c, g in zip(rgb(LINE), rgb(GROUND)))
    for corner in (rgb(GROUND), rgb(GROUND_DEEP), rgb(LINE), grid):
        rows = field_of()
        for y in range(20):
            for x in range(20):
                rows[y][x] = corner
        for x, y in warm_points():
            disc(rows, x, y, CORE, rgb(EMBER))
        findings, _ = check(png(rows))
        assert findings == [], f"the field is allowed to be {corner}: {findings}"


# --------------------------------------------------------- refusing, not passing


def test_a_sample_outside_the_image_is_a_finding_and_not_a_crash():
    """A canvas so small that the instrument's outer ring is off the top of it.
    That is not a picture this package can produce, and `list index out of range`
    in a build log is a worse report than a sentence, so it is one."""
    findings, _ = check(render(w=40, h=40), artsample.Contract(0.5, 0.1, 0.9))
    assert any("outside" in f for f in findings), findings


def test_an_unreadable_file_is_a_refusal():
    """The failure mode this whole gate is a response to is a renderer that exits
    0 on garbage, so a checker that shrugs at a file it cannot decode would be
    the same mistake one level up."""
    with pytest.raises(artsample.Unreadable):
        artsample.decode_png(composed()[:-40])
    assert (
        artsample.main(
            [
                "--at",
                "0.734,0.681",
                "--radius",
                "0.39",
                "--warm",
                EMBER,
                "--field",
                GROUND,
                str(ART),
            ]
        )
        == 1
    )


def test_the_cli_grades_a_file_and_exits_on_the_findings(tmp_path):
    """The shape `pkgs/jarvis-wallpaper` calls: the fractions and the tokens in,
    a list of files, an exit status the builder can trust."""
    good = tmp_path / "jarvisos-composed.png"
    good.write_bytes(composed())
    bad = tmp_path / "jarvisos-degenerate.png"
    bad.write_bytes(render((0, 0, 20)))
    argv = ["--at", "0.734,0.681", "--radius", "0.39", "--warm", EMBER]
    for colour in FIELD:
        argv += ["--field", colour]
    assert artsample.main([*argv, str(good)]) == 0
    assert artsample.main([*argv, str(good), str(bad)]) == 1
    # And a run with no files is a refusal, never a green: a glob that matched
    # nothing is exactly how this gate would go quietly missing.
    assert artsample.main(argv) == 2


# ------------------------------------------- the contract with the package itself


def builder() -> str:
    return ART.read_text("utf-8")


def invocation() -> str:
    """The artsample call inside pkgs/jarvis-wallpaper's builder, as written, with
    the shell's quotes taken off — every hex colour in it has to be quoted,
    because a bare `#F0714A` starts a bash comment."""
    m = re.search(
        r"python3 [^\n]*artsample\.py(?:[^\n]*\\\n)*[^\n]*", builder()
    )
    assert m, (
        "pkgs/jarvis-wallpaper does not run tools/artsample.py — the art is back "
        "to having no gate that reads a pixel of it (PLAN E11)"
    )
    return m.group(0).replace("'", "").replace('"', "")


def test_the_package_samples_the_fractions_it_composes_with():
    """THE DRIFT THIS SUITE IS THE THIRD PARTY TO. The checker is only evidence
    about the art if it is pointed at the same three fractions the art composes
    with — and a checker pointed at a hand-written 0.734 would keep passing for
    ever after somebody edited `instrumentX`. So the builder interpolates the LET
    BINDINGS rather than their values, which is checkable without evaluating any
    nix."""
    args = invocation()
    for name in ("instrumentX", "instrumentY", "instrumentR"):
        assert f"${{toString {name}}}" in args, (
            f"pkgs/jarvis-wallpaper passes artsample.py coordinates that do not "
            f"come from its own {name}"
        )
    assert not re.search(r"--(at|radius) [\d.]", args), (
        "the artsample call spells a fraction out; they are the art's own "
        "`instrument*` bindings or they are a second copy that will drift"
    )


def test_the_package_spends_the_theme_on_the_check_too():
    """The same argument for the colours. §06's ember is the one thing the warm
    samples can be, `personality/theme.toml` is the only place a colour exists
    (invariant 9), and a hex literal here would be the next surface to drift off
    it — which is what the top of this package's own file is about."""
    args = invocation()
    assert "--warm ${ember}" in args, "the warm sample is not the theme's ember"
    for name in ("${ground}", "${groundDeep}", "${line}"):
        assert f"--field {name}" in args, (
            f"the field bound is not given {name}, which the art paints the "
            "corners of every render with"
        )
    assert not re.search(r"#[0-9A-Fa-f]{6}", args), (
        "the artsample call carries a hex colour; theme.toml is the only place a "
        "colour exists"
    )


def test_the_check_reads_every_render_the_package_writes():
    """A gate that names its files one by one is a gate that stops covering the
    geometry somebody adds to the loop next. It is pointed at the output
    directory instead, so E10 — making that list the RIGHT list, filled by
    `hosts/ares` — cannot quietly outrun it."""
    args = invocation()
    assert "backgrounds" in args and "*.png" in args, (
        "artsample.py is not pointed at every PNG in the package's output"
    )


def test_the_check_runs_after_every_render_is_written():
    """Order is part of the claim: sampling a directory the loop has not finished
    filling would check whichever renders happened to exist when it ran."""
    text = builder()
    assert text.index(invocation().split("\n")[0]) > text.index("for geom in "), (
        "pkgs/jarvis-wallpaper samples its output before the per-output renders "
        "are written — the bespoke geometries would go unchecked"
    )
