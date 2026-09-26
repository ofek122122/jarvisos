"""The monitors this machine declares, and the art composed for them (PLAN E10).

`hosts/ares/outputs.nix` is a new kind of file in this repo: pure data about the
hardware, imported by `flake.nix` rather than read out of `config`, because the
first thing that needs it is a package ARGUMENT and a package argument cannot
come out of a NixOS module. Before it, the wallpaper composed a render for each
of five geometries written inside the package — `2560x1440 1920x1080 3840x2160
2560x1080 1366x768` — three of which no output on this machine can display, and
a real monitor plugged in tomorrow would have got the primary art scaled and
cropped instead of art composed for it.

WHY THESE ASSERTIONS ARE HERE AND NOT IN A NIX EVALUATION. This suite runs in a
bare checkout and reads source text (the same reason `test_jv_lock.py` splits
its claims from `nixtest.sh`'s), so it cannot ask Nix what `geometries` came out
to. What it CAN do is the thing no single file can do about itself: hold the
declaration, the package that spends it, the flake that connects them, the sheet
that borrows it and the prose in CLAUDE.md to each other. Invariant 1's shape —
every claim about a relation between two parts of this repo is made by a third
that reads them both.

The behaviour of a BAD declaration is checked where it can be: the five refusals
in the package are evaluation-time throws, and `ops/ralph/nixtest.sh` asks the
real flake. Here we only check they still exist, because a throw deleted is a
throw that passes every text search for its own message.
"""

import re
from pathlib import Path

from test_gen_theme_qml import ROOT

ARES_OUTPUTS = ROOT / "hosts" / "ares" / "outputs.nix"
SHEET_OUTPUTS = ROOT / "tools" / "wallshots" / "outputs.nix"
ART = ROOT / "pkgs" / "jarvis-wallpaper" / "default.nix"
FLAKE = ROOT / "flake.nix"
CLAUDE_MD = ROOT / "CLAUDE.md"


def _nix_uncommented(text: str) -> str:
    """A Nix source with its `#` comments removed, tracking quotes so that a `#`
    inside a string survives. Written out rather than a regex because these
    files are mostly comment and one of the values is a quoted refresh rate — a
    naive `#.*$` would also be fine today and would silently eat half a colour
    literal the day one appears."""
    out, quoted, i = [], False, 0
    while i < len(text):
        ch = text[i]
        if quoted:
            if ch == "\\":
                out.append(text[i : i + 2])
                i += 2
                continue
            if ch == '"':
                quoted = False
            out.append(ch)
        elif ch == '"':
            quoted = True
            out.append(ch)
        elif ch == "#":
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        else:
            out.append(ch)
        i += 1
    return "".join(out)


_FIELD = re.compile(r"(?P<key>[A-Za-z_][\w-]*)\s*=\s*(?P<val>\"[^\"]*\"|[\w.]+)\s*;")


def declared_outputs(path: Path) -> list[dict]:
    """The list of outputs a declaration file evaluates to, parsed from its text.

    Handles exactly the two shapes this repo uses — a bare list of flat
    attrsets, and `import <other>.nix ++ [ … ]`, which is how the contact sheet
    says "ares' monitors and one more" without writing ares' monitors again. It
    REFUSES anything else rather than returning what it managed to find: a
    parser that quietly returns `[]` on a file it does not understand makes
    every test below vacuously green, which is the failure mode this whole item
    is about.
    """
    text = _nix_uncommented(path.read_text("utf-8"))
    entries: list[dict] = []
    for rel in re.findall(r"\bimport\s+([\w./-]+\.nix)", text):
        entries += declared_outputs((path.parent / rel).resolve())
    body = re.sub(r"\bimport\s+[\w./-]+\.nix", "", text)
    blocks = re.findall(r"\{([^{}]*)\}", body)
    # Whatever is left once the attrsets are cut out has to be list and operator
    # punctuation — a `let`, a function argument or a nested attrset means this
    # parser is reading a file it was not written for.
    leftover = re.sub(r"\{[^{}]*\}", "", body)
    assert not re.search(r"[A-Za-z]", leftover), (
        f"{path.relative_to(ROOT)} is not a flat list of attrsets any more "
        f"({leftover.strip()!r} is left over) — declared_outputs() would report "
        "a subset of it as the whole truth"
    )
    for block in blocks:
        out: dict = {}
        for field in _FIELD.finditer(block):
            raw = field.group("val")
            if raw.startswith('"'):
                out[field.group("key")] = raw[1:-1]
            elif raw in ("true", "false"):
                out[field.group("key")] = raw == "true"
            else:
                out[field.group("key")] = int(raw)
        # Same argument as the leftover check, one level down: an entry whose
        # fields did not parse would be an output silently missing from the list.
        assert _FIELD.sub("", block).strip() == "", (
            f"{path.relative_to(ROOT)} has an entry declared_outputs() cannot "
            f"read: {block.strip()!r}"
        )
        entries.append(out)
    assert entries, f"{path.relative_to(ROOT)} declares no outputs at all"
    return entries


def geometries_of(outputs: list[dict]) -> list[str]:
    """The de-duplicated `WxH` list the package composes for — ares' two 1080p
    panels are one composition."""
    seen = []
    for out in outputs:
        geom = f"{out['width']}x{out['height']}"
        if geom not in seen:
            seen.append(geom)
    return seen


def art_source() -> str:
    return ART.read_text("utf-8")


# ---------------------------------------------------------- the declaration


def test_every_declared_output_says_what_the_art_and_the_layout_both_need():
    """The shape of an entry, held once so the tests below can trust it. Two
    consumers, two sets of fields: the wallpaper needs integer pixels and
    exactly one primary, and the layout PLAN E5 will generate needs a name, a
    refresh rate and a left edge. A missing `x` is the one that would be
    invisible — niri would stack two outputs on top of each other and the flake
    would build."""
    for out in declared_outputs(ARES_OUTPUTS):
        assert isinstance(out.get("name"), str) and out["name"], out
        for px in ("width", "height", "x"):
            assert isinstance(out.get(px), int), (
                f"{out.get('name')} declares {px}={out.get(px)!r}, and the art "
                "de-duplicates geometries by value: \"1920\" and 1920 are two "
                "compositions of the same panel"
            )
        assert out["width"] > 0 and out["height"] > 0, out
        # A refresh rate is a string on purpose: 144.006 is what the primary has
        # to be ASKED for to be offered 144 at all (memory/ares-hardware-
        # firstboot), and a Nix float would print it as 144.006 or 144.0060
        # depending on the version that formats it.
        assert re.fullmatch(r"\d+\.\d+", str(out.get("refresh", ""))), (
            f"{out['name']} declares refresh={out.get('refresh')!r}; the modes this "
            "machine is offered are exact decimals, not rounded ints"
        )


def test_ares_declares_exactly_one_primary_output():
    """`jarvisos.png` is composed at the primary's geometry, and it is both the
    lock screen's image (pkgs/jv-lock) and what shell/jv-wall crops onto any
    output with no bespoke render. Two primaries or none is a throw in the
    package; this is the same claim about the file that must never provoke it."""
    primary = [o for o in declared_outputs(ARES_OUTPUTS) if o.get("primary")]
    assert len(primary) == 1, f"ares declares {len(primary)} primary outputs: {primary}"
    assert primary[0]["width"] >= max(o["width"] for o in declared_outputs(ARES_OUTPUTS)), (
        "the primary is not the widest output ares has — which is allowed, but "
        "every geometry bigger than it now falls back to art it has to crop, so "
        "this is a decision and not an oversight"
    )


def test_the_declaration_is_the_monitors_claude_md_says_this_machine_has():
    """CLAUDE.md's hardware list is the prose a human wrote about ares and the
    thing every session reads first; `hosts/ares/outputs.nix` is now what the
    build believes. Those being the same three monitors is exactly the kind of
    agreement that rots silently — the prose cannot fail, and until E10 nothing
    in the flake carried the numbers at all."""
    line = next(
        (ln for ln in CLAUDE_MD.read_text("utf-8").splitlines() if "Monitors:" in ln),
        None,
    )
    assert line, "CLAUDE.md no longer says which monitors this machine has"
    prose: list[tuple[int, int, int]] = []
    for count, w, h, hz in re.findall(r"(?:(\d+)x )?(\d+)x(\d+)@(\d+)", line):
        prose += [(int(w), int(h), int(hz))] * int(count or 1)
    declared = [
        (o["width"], o["height"], int(float(o["refresh"]))) for o in declared_outputs(ARES_OUTPUTS)
    ]
    assert sorted(prose) == sorted(declared), (
        f"CLAUDE.md describes {sorted(prose)} and hosts/ares/outputs.nix declares "
        f"{sorted(declared)} — one of them is wrong about the hardware"
    )
    # And which one the prose calls primary, since that decides the fallback art.
    marked = re.search(r"(\d+)x(\d+)@\d+ \(primary\)", line)
    assert marked, "CLAUDE.md no longer marks one monitor as the primary"
    primary = next(o for o in declared_outputs(ARES_OUTPUTS) if o.get("primary"))
    assert (primary["width"], primary["height"]) == (int(marked.group(1)), int(marked.group(2))), (
        f"CLAUDE.md's primary is {marked.group(0)} and the declaration's is "
        f"{primary['name']} at {primary['width']}x{primary['height']}"
    )


# ------------------------------------------------- the art that spends it


def test_the_art_composes_the_declared_geometries_and_no_written_list():
    """E10 itself. The loop's list is the `outputs` argument, interpolated, and
    the assertion that matters is the ABSENCE: a geometry written in the builder
    is art for a monitor nobody declared, which is what the package shipped for
    two phases. A regression here does not fail — it renders five PNGs, three of
    which no surface will ever ask for."""
    art = art_source()
    loop = re.search(r"for geom in (?P<list>[^;]*); do", art)
    assert loop, "pkgs/jarvis-wallpaper no longer loops over the geometries it renders"
    assert loop.group("list").strip() == "${lib.concatStringsSep \" \" geometries}", (
        f"the render list is `{loop.group('list').strip()}` — a geometry spelled in "
        "the builder is art composed for a monitor this host does not declare"
    )
    assert re.search(r"geometries = lib\.unique \(map geometry declared\);", art), (
        "the geometry list no longer comes from the declared outputs"
    )
    # …and the primary art, which is the fallback, is composed at the geometry of
    # the output declared primary rather than at a size that happens to match it.
    assert re.search(
        r"compose \$\{toString primary\.width\} \$\{toString primary\.height\} wp\.svg", art
    ), "the primary art is no longer composed at the declared primary's geometry"


def test_the_package_takes_the_outputs_it_composes_for_and_defaults_nothing():
    """A default list would be the same guess one level up and harder to see:
    `callPackage` supplies it without a word, and the host's real monitors never
    reach the art. So the argument is declared with no `?` — missing is an
    evaluation error — and this is the test that notices somebody making the
    build convenient again."""
    art = art_source()
    args = art[art.index("{") : art.index("}:")]
    assert re.search(r"^\s*outputs,\s*$", args, re.M), (
        "pkgs/jarvis-wallpaper does not take an `outputs` argument, or gives it a "
        f"default: {args.strip()!r}"
    )


def test_the_package_refuses_every_declaration_that_would_build_anyway():
    """Five ways a bad declaration produces a wallpaper that BUILDS, and the four
    throws that refuse them. They are here as text because this suite cannot evaluate Nix (the
    real refusals are verified against the flake by ops/ralph/nixtest.sh), and
    they are worth a text test anyway: each one is a silent success, which is
    the only kind of bug this package has ever had."""
    art = art_source()
    for what, needle in (
        ("an empty list", r"empty `outputs` list"),
        ("a non-integer size", r"without an\n\s*integer width and height"),
        ("a zero or negative size", r"resvg rasterizes a zero-sized"),
        ("no primary or several", r"needs exactly one output with `primary = true`"),
        ("a size that reaches resvg unchecked", r"if o\.width < 1 \|\| o\.height < 1"),
    ):
        assert re.search(needle, art), (
            f"pkgs/jarvis-wallpaper no longer refuses {what}; that declaration now "
            "renders art nobody looks at and exits 0"
        )


# ------------------------------------------- the flake that connects them


def test_the_flake_fills_the_art_from_the_host_that_owns_the_monitors():
    """The connection E10 is, in the one file that can make it. Two
    instantiations of one package: the desktop's, from the host's declaration,
    and the contact sheet's, from the sheet's — and the second exists so the
    first stops rendering geometries this machine cannot display."""
    flake = FLAKE.read_text("utf-8")
    for attr, decl in (
        ("jarvis-wallpaper", "./hosts/ares/outputs.nix"),
        ("jarvis-wallpaper-sheet", "./tools/wallshots/outputs.nix"),
    ):
        call = re.search(
            rf"{re.escape(attr)} = pkgs\.callPackage \./pkgs/jarvis-wallpaper \{{\s*"
            rf"outputs = import {re.escape(decl)};",
            flake,
        )
        assert call, f"flake.nix does not build {attr} from {decl}"


def test_the_sheets_outputs_are_this_machines_plus_a_reason():
    """The sheet's list imports ares' rather than restating it, so "the sheet is
    taken at every geometry this machine really has" is true by construction —
    and what it ADDS is one canvas ares has no panel for, because every output
    this host declares is 16:9 and a sheet of those alone would photograph the
    composer's one aspect ratio. docs/wall/06-ultrawide.png was the picture of
    PLAN E9's defect and is now the picture of it fixed; it is the only place in
    this repo a composed non-16:9 render can be looked at."""
    assert "import ../../hosts/ares/outputs.nix" in SHEET_OUTPUTS.read_text("utf-8"), (
        "tools/wallshots/outputs.nix no longer imports ares' own outputs — the "
        "sheet can now drift off the monitors it is evidence about"
    )
    ares = geometries_of(declared_outputs(ARES_OUTPUTS))
    sheet = geometries_of(declared_outputs(SHEET_OUTPUTS))
    assert sheet[: len(ares)] == ares, f"the sheet composes {sheet}, ares declares {ares}"
    extra = sheet[len(ares) :]
    assert extra, "the sheet's art is exactly the machine's, so nothing on it is 21:9"
    ratios = {round(int(g.split("x")[0]) / int(g.split("x")[1]), 3) for g in ares}
    assert any(
        round(int(g.split("x")[0]) / int(g.split("x")[1]), 3) not in ratios for g in extra
    ), (
        f"the sheet adds {extra}, and every one of those is an aspect ratio ares "
        f"already has {sorted(ratios)} — the extra render buys no coverage"
    )
