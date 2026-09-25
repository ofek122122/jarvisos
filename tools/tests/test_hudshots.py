"""The contact sheet in docs/hud is the HUD, or it is worse than nothing.

`ops/ralph/hudshots.sh` renders the real plates into PNGs so that looking at
the HUD stops requiring a seat at ares (PLAN A29). It does that by STAGING a
copy of shell/jv-hud with two singletons replaced — the only two that import
Quickshell — and by rebuilding shell.qml's plate stack in a file a plain QML
engine can load.

Both of those are duplication, and duplication drifts. The failure mode is
specific and silent: a new plate is added to shell.qml, never appears in the
sheet, and the sheet still renders seven perfectly good pictures of a HUD
that no longer exists. Nothing errors. These are the gates that make that
loud instead.
"""

import ast
import hashlib
import json
import re
import sys
import tempfile
import tomllib
from pathlib import Path

# One parser for the HUD's QML, not two: the theme gates already had to read
# shell.qml's plate stack, and a second implementation of "what is inside
# this block" would be a second thing to be subtly wrong.
from test_gen_theme_qml import ROOT, plate_stack_children, strip_qml_comments

# jv-guard's own scanner, its own verdict logic and its own PE fixture
# builder — three imports, no copies. The sheet photographs one verdict that
# a service composes in words (13-suspicious.png), and the only way to keep
# a picture of a sentence honest is to go and ask the thing that says it;
# see test_the_suspicious_shot_photographs_a_verdict_jv_guard_can_produce.
# Nothing here is a service talking to a service (invariant 1): this is a
# test reading a module, the way the gates above read shell.qml.
GUARD = ROOT / "services" / "jv-guard"
sys.path[:0] = [str(GUARD), str(GUARD / "tests")]
from jv_guard.heuristics import PEHeuristicScanner  # noqa: E402
from jv_guard.scan import ClamAVScanner, ScanReport, decide  # noqa: E402
from test_pe_heuristics import MEM_EXECUTE, MEM_READ, MEM_WRITE, build_pe  # noqa: E402

# A section the CPU may execute, that is also writable: the unpacker-stub
# shape, and what both of UPX's sections really carry.
RWX = MEM_EXECUTE | MEM_READ | MEM_WRITE

SHELL = ROOT / "shell" / "jv-hud"
SHOTS = ROOT / "tools" / "hudshots"
SHEET = ROOT / "docs" / "hud"

SCENE_DIR = SHOTS / "scene"
SCENE = SCENE_DIR / "tst_shots.qml"
# The corner stack both drivers build: the sheet (A29) and the sequence
# replay (A54). One copy of shell.qml's stack, in one file, so that "the
# harness stacks what the shell stacks" is one claim and not one per driver.
CORNER = SCENE_DIR / "Corner.qml"

# Every member a QML file offers its consumers: properties (including
# aliases), functions and signals, declared at any depth — the HUD writes
# them all at the top level of these files.
MEMBER = re.compile(
    r"""^\s*(?:readonly\s+)?(?:property\s+(?:alias\s+)?[\w.<>]+\s+(?P<prop>\w+)
        |function\s+(?P<func>\w+)\s*\(
        |signal\s+(?P<sig>\w+))""",
    re.M | re.X,
)


def members(path: Path) -> set[str]:
    text = strip_qml_comments(path.read_text("utf-8"))
    out = set()
    for m in MEMBER.finditer(text):
        out.add(m.group("prop") or m.group("func") or m.group("sig"))
    return out


def scene_text() -> str:
    return SCENE.read_text("utf-8")


SHEET_ENTRY = re.compile(
    r'\{\s*"file":\s*"(?P<file>[^"]+)".*?"plates":\s*\[(?P<plates>[^]]*)\]',
    re.S,
)


def sheet() -> list[tuple[str, list[str]]]:
    """The scene's sheet: each shot's file name and the plates it claims are on
    screen, in the order they are declared (A53)."""
    out = [
        (m.group("file"), re.findall(r'"([^"]+)"', m.group("plates")))
        for m in SHEET_ENTRY.finditer(strip_qml_comments(scene_text()))
    ]
    assert out, "found no sheet entries with a `plates` list in the scene"
    return out


def test_the_harness_stacks_the_same_plates_the_shell_does():
    """Corner.qml is a copy of shell.qml's corner stack, and a copy of a list
    is a list that goes stale. A plate the shell shows and the harness does
    not is a plate nobody has ever seen a picture of — nor asserted a
    trajectory for (A54) — which is the exact thing this harness exists to
    prevent. The ORDER matters as much as the membership: it is the reading
    order of the corner, and both drivers assert `litNames` against it.
    """
    shell = plate_stack_children((SHELL / "shell.qml").read_text("utf-8"))
    corner = plate_stack_children(CORNER.read_text("utf-8"))
    assert corner == shell, (
        "tools/hudshots/scene/Corner.qml stacks "
        f"{corner} but shell.qml stacks {shell} — regenerate the corner (and "
        "then the sheet: bash ops/ralph/hudshots.sh)"
    )


def test_no_driver_keeps_its_own_copy_of_the_corner():
    """There was one copy of the stack per harness until Corner.qml (A54), and
    the sequence replay would have made a second. Copies of a list are the
    failure this file exists to catch, so the drivers must not hold one: a
    plate declared inside a driver is a plate that is in one harness and not
    the other, and the check above would not see it.
    """
    for driver in sorted(SCENE_DIR.glob("tst_*.qml")):
        stray = re.findall(
            r"^\s*(\w+Plate)\s*\{", strip_qml_comments(driver.read_text("utf-8")), re.M
        )
        assert not stray, (
            f"{driver.name} declares {sorted(set(stray))} itself — stack plates "
            "in Corner.qml, which is the one file pinned to shell.qml"
        )


def test_the_stub_bus_offers_everything_the_real_one_does():
    """A plate reading `Bus.somethingTheStubForgot` does not error: QML hands
    it `undefined`, the plate decides it has nothing to say, and the shot is
    a picture of a plate that works fine on the real bus. Missing members
    have to fail HERE or they never fail at all.
    """
    real = members(SHELL / "Bus.qml")
    stub = members(SHOTS / "stub" / "Bus.qml")
    assert real <= stub, (
        f"tools/hudshots/stub/Bus.qml is missing {sorted(real - stub)}, which "
        "the plates can read on the real bus and would see as undefined here"
    )


def test_the_stub_motion_offers_everything_the_real_one_does():
    """Same failure, quieter: a missing `Motion.animate` reads as false, every
    Behavior silently switches off, and the sheet becomes a picture of a HUD
    in permanent reduced-motion — which is a setting, not the default.
    """
    real = members(SHELL / "Motion.qml")
    stub = members(SHOTS / "stub" / "Motion.qml")
    assert real <= stub, (
        f"tools/hudshots/stub/Motion.qml is missing {sorted(real - stub)}"
    )


def test_the_stubs_replace_nothing_but_the_two_quickshell_singletons():
    """The value of the sheet is that everything in it is the real file. Every
    stub is one more thing that is not — so there are two, both named here,
    and both for the same reason: they import Quickshell, whose QML plugin is
    linked into the quickshell binary and cannot be resolved by any other
    engine.
    """
    stubs = sorted(p.name for p in (SHOTS / "stub").glob("*.qml"))
    assert stubs == ["Bus.qml", "Motion.qml"], (
        f"tools/hudshots/stub holds {stubs}: a third stub means a third piece "
        "of the HUD the sheet is only pretending to show"
    )
    for name in stubs:
        real = (SHELL / name).read_text("utf-8")
        assert "import Quickshell" in real, (
            f"{name} no longer imports Quickshell, so the shot harness can use "
            "the real file and should stop carrying a copy of it"
        )


def test_the_backdrop_is_not_one_of_jarviss_colours():
    """The grey behind the plates is the sheet's, not the HUD's — the real
    surface is transparent. If it were ever a theme token, a reader would have
    no way to tell the photograph's paper from Jarvis's own palette.
    """
    backdrop = re.search(
        r'property color backdrop:\s*"(#[0-9A-Fa-f]{6})"', scene_text()
    )
    assert backdrop, "the scene no longer declares a single backdrop colour"
    palette = set(
        re.findall(r'^\s*\w+\s*=\s*"(#[0-9A-Fa-f]{6})"', 
                   (ROOT / "personality" / "theme.toml").read_text("utf-8"), re.M)
    )
    assert backdrop.group(1).upper() not in {c.upper() for c in palette}, (
        f"the sheet's backdrop {backdrop.group(1)} is a personality/theme.toml "
        "colour, so the paper and the HUD are now the same thing"
    )


def test_every_shot_the_scene_takes_is_committed_and_vice_versa():
    """An uncommitted shot is one nobody can look at without running the
    harness; an orphaned PNG is a picture of a HUD that no longer exists. Both
    are the sheet quietly ceasing to be the sheet.
    """
    taken = re.findall(r'"file":\s*"([^"]+)"', scene_text())
    assert taken, "the scene declares no shots at all"
    committed = sorted(p.name for p in SHEET.glob("*.png"))
    assert sorted(taken) == committed, (
        f"the scene takes {sorted(taken)} and docs/hud holds {committed} — "
        "run bash ops/ralph/hudshots.sh and commit the result"
    )


def test_the_sheet_says_which_shots_are_recordings_and_which_are_written():
    """Some shots replay harness/fixtures/sessions and some are frames written
    by hand, because nothing in the repo has ever recorded jv-voice speaking or
    jv-act asking (B10/A28). A sheet that blurs the two would let a composed
    picture be read as evidence about the machine — the one thing a screenshot
    of a HUD must never do.
    """
    readme = (SHEET / "README.md").read_text("utf-8")
    # One `### ` section per shot: the heading, the image, and the paragraph
    # that says where its frames came from.
    sections = readme.split("\n### ")
    for name in re.findall(r'"file":\s*"([^"]+)"', scene_text()):
        shown = [s for s in sections if name in s]
        assert shown, f"docs/hud/README.md never mentions {name}"
        assert len(shown) == 1, f"docs/hud/README.md shows {name} in {len(shown)} sections"
        assert re.search(r"\b(recorded|composed)\b", shown[0].lower()), (
            f"docs/hud/README.md shows {name} without saying whether its frames "
            "are recorded or composed"
        )


def test_every_shot_says_which_plates_are_in_it():
    """A53. The scene's only per-shot assertion used to be `anyLit` — a single
    bit that nine of the ten shots answered `true` — so the sheet could prove
    a picture had SOMETHING in it and never what. An entry without a `plates`
    list is a shot back in that state, and it would be the one shot nobody
    notices, because the other nine still pass.
    """
    files = re.findall(r'"file":\s*"([^"]+)"', strip_qml_comments(scene_text()))
    named = [f for f, _ in sheet()]
    assert files == named, (
        f"every sheet entry must declare `plates`; {sorted(set(files) - set(named))} "
        "do not, so those shots are checked only by 'something was drawn'"
    )
    assert '"lit"' not in strip_qml_comments(scene_text()), (
        "the old one-bit `lit` flag is back in the sheet; `plates` supersedes "
        "it and the two would drift"
    )


def test_every_plate_in_the_shell_is_lit_in_some_shot():
    """A plate the sheet renders but never LIGHTS is a plate nobody has ever
    seen a picture of.

    The older gate above proves each plate is in the scene's stack, which is
    only the claim that it was built — every plate in this HUD draws nothing
    until a real frame gives it something to say, so a plate can sit in all
    ten shots and appear in none of them. That is the normal state of most of
    them, and it is exactly how a new element gets added, rendered, committed
    and still never looked at.
    """
    lit = {name for _, plates in sheet() for name in plates}
    for child in plate_stack_children((SHELL / "shell.qml").read_text("utf-8")):
        want = child[: -len("Plate")].lower()
        assert want in lit, (
            f"{child} is in the shell's stack and no shot in docs/hud has it on "
            f"screen, so there is no picture of it. Add a shot that lights it."
        )


def test_the_sheet_tells_the_reader_which_plates_each_shot_shows():
    """The captions are for a human, and a human is the only thing that has
    ever been able to tell two of these plates apart in a PNG.

    `HealthPlate` and `ActionPlate` draw the same two lines in the same
    severity colour in the same corner; `GuardPlate` makes three. So the
    README's per-shot `**On screen:**` line is read off the scene and checked
    against it — a prose description can drift into naming the wrong element,
    and this line cannot.
    """
    readme = (SHEET / "README.md").read_text("utf-8")
    sections = readme.split("\n### ")
    for name, plates in sheet():
        shown = [s for s in sections if name in s]
        assert len(shown) == 1, f"docs/hud/README.md shows {name} in {len(shown)} sections"
        line = re.search(r"^\*\*On screen:\*\*(.+)$", shown[0], re.M)
        assert line, f"docs/hud/README.md's {name} section has no `**On screen:**` line"
        got = re.findall(r"`([^`]+)`", line.group(1))
        if not plates:
            assert not got and "nothing" in line.group(1), (
                f"{name} has no plate on screen, and its line must say so "
                f"in words rather than name one: {line.group(1).strip()}"
            )
            continue
        assert got == plates, (
            f"docs/hud/README.md says {name} shows {got}; the scene asserts "
            f"{plates}. The README is what a reader believes the picture is of."
        )


def packed_deterministically(n: int) -> bytes:
    """`n` bytes with the flat histogram a compressed payload has, from a
    fixed seed.

    jv-guard's own fixtures use `os.urandom`, which is right for a
    threshold test and wrong here: the reason string this gate compares
    carries the entropy to two decimals, so the bytes have to be the same
    bytes on every machine and every run.

    The zero tail is not padding for its own sake. A real UPX1 section is
    a compressed payload plus the unpacker's stub and its alignment slack,
    which is why a packed section measures 7.9-something rather than a
    flat 8.00 — a fixture that measured 8.00 would put a number in the
    sheet that no real binary produces.
    """
    tail = 8192
    out = bytearray()
    digest = hashlib.sha256(b"jarvisos-hudshots-13-suspicious").digest()
    while len(out) < n - tail:
        out += digest
        digest = hashlib.sha256(digest).digest()
    return bytes(out[: n - tail]) + b"\x00" * tail


def json_object_after(text: str, at: int) -> dict:
    """The brace-balanced object literal starting at or after `at`, read as
    JSON. The scene writes its frame bodies as plain double-quoted
    literals, so they are JSON — one of them, `shot_guard_install`'s, uses
    a `const` for a hash it repeats and is deliberately not read here.
    """
    start = text.index("{", at)
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise AssertionError("unbalanced braces in the scene")


def test_the_suspicious_shot_photographs_a_verdict_jv_guard_can_produce():
    """A66. `13-suspicious.png` is the sheet's only picture of the approved
    policy's middle rung, and every word in the frame behind it was typed
    into a QML file by hand.

    That is ordinarily fine — most of this sheet is composed and the README
    says so per shot. It is not fine here, because this frame is the one
    place in the repo where the HUD asserts what ANOTHER service says. Until
    jv-guard grew a shape engine, `decide()` could not return `suspicious`
    at all, and a shot of `GuardPlate`'s `warn` branch would have been a
    picture of an intention. The distance between "a colour with no
    producer" and "a colour with one" is exactly this test: build a binary
    of the shape the engine is looking for, run the REAL engine and the
    REAL `decide()` over it, and hold the composed frame to what comes
    back.

    What it does not check: the sha256, which is the hash of a file that
    does not exist and could not be anything else.
    """
    scene = strip_qml_comments(scene_text())
    assert "function shot_suspicious" in scene, (
        "the scene no longer takes a `suspicious` shot, so the only picture "
        "of GuardPlate's warn branch is gone"
    )
    at = scene.index("function shot_suspicious")
    frame = json_object_after(scene, scene.index('"guard.verdict"', at))

    # The UPX shape, in a real PE: a section with virtual space and no bytes
    # on disk to unpack into, and a writable executable one holding the
    # compressed payload. jv-guard's own builder, so a change to what it
    # emits reaches this gate rather than going around it.
    blob = build_pe(
        [
            ("UPX0", RWX, b"", 512 * 1024),
            ("UPX1", RWX, packed_deterministically(512 * 1024), None),
        ]
    )
    with tempfile.TemporaryDirectory() as tmp:
        exe = Path(tmp) / "nfs2se-widescreen-patch.exe"
        exe.write_bytes(blob)
        shape = PEHeuristicScanner().scan(exe)

    # ClamAV ran and recognised nothing. It has to be in the list: the shape
    # engine is ADVISORY, it may raise suspicion and may never grant trust,
    # and `decide()` returns no verdict at all when no authoritative engine
    # ran. A `suspicious` verdict is therefore always two engines' work, and
    # `scanned_by` in the photographed frame has to say so.
    real = decide(frame["sha256"], [ScanReport(ClamAVScanner.name, ran=True), shape])
    assert real is not None, "no authoritative engine in this fixture's reports"

    assert frame["verdict"] == real.verdict
    assert frame["scanned_by"] == real.scanned_by
    assert frame["reasons"] == real.reasons, (
        "the reasons in 13-suspicious.png are not the sentences jv-guard "
        "produces for a packed binary any more. Update the scene's frame and "
        "re-run bash ops/ralph/hudshots.sh."
    )


# ------------------------------------------- the words other services say
#
# A67. The gate above is the sheet's first: a composed frame held to what
# the service it quotes would really publish. It is not the only frame
# here that quotes one. `05-confirm.png` carries a question jv-act asks,
# `06-health.png` carries jv-brain's rung, `08-action.png` carries a tool
# call and one of jv-act's error words, `11-install.png` and
# `12-guard-install.png` carry jv-compat's lifecycle. Every one of those
# was typed by hand into a QML file and nothing checked that the named
# producer could emit it.
#
# It is worth checking because a composed frame is a CLAIM about this
# machine — the README says "composed" per shot and that is a claim about
# provenance, not about plausibility. A picture of jv-compat publishing an
# event jv-compat does not have is not a picture of an intention; it is a
# picture of a machine that does not exist, and a reader has no way to
# tell it from the rest of the sheet.
#
# What these gates do NOT do is run a service. They read a producer the
# way the gates above read `shell.qml`: jv-compat's installer and
# jv-brain's ladder are imported or parsed, jv-act's registry is TOML, and
# jv-act's Rust is read for the literals it sends. Free text stays free
# text — an installer's stderr and a service's `notes` are composed and
# say so in docs/hud/README.md.

BRAIN = ROOT / "services" / "jv-brain"
COMPAT = ROOT / "services" / "jv-compat"
ACT = ROOT / "services" / "jv-act"

sys.path[:0] = [str(BRAIN), str(COMPAT)]
from jv_brain.config import LADDER  # noqa: E402
from jv_brain.launcher import gpu_floor_mb  # noqa: E402
from jv_compat import fingerprint as compat_fingerprint  # noqa: E402

BRACKETS = {"(": ")", "[": "]", "{": "}"}


def skip_literal(text: str, i: int) -> int:
    """The index just past the string literal that starts at `text[i]`.

    Brackets and commas live inside these frames' strings — a reason with
    a parenthetical, a path, an installer's stderr — so every scan below
    steps over literals rather than counting the characters in them.
    """
    quote = text[i]
    i += 1
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == quote:
            return i + 1
        i += 1
    raise AssertionError("unterminated string literal")


def bracketed(text: str, start: int) -> str:
    """The bracketed run beginning at `text[start]`, literals ignored."""
    assert text[start] in BRACKETS, f"no bracket at {start}"
    depth, i = 0, start
    while i < len(text):
        c = text[i]
        if c in "\"'":
            i = skip_literal(text, i)
            continue
        if c in BRACKETS:
            depth += 1
        elif c in BRACKETS.values():
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
        i += 1
    raise AssertionError("unbalanced brackets")


def call_args(text: str, open_paren: int) -> list[str]:
    """The top-level argument sources of the call whose `(` is at
    `open_paren`. Used on QML and on Python: both write a call the same
    way, and neither is being interpreted here — only split."""
    inner = bracketed(text, open_paren)[1:-1]
    args, depth, start, i = [], 0, 0, 0
    while i < len(inner):
        c = inner[i]
        if c in "\"'":
            i = skip_literal(inner, i)
            continue
        if c in BRACKETS:
            depth += 1
        elif c in BRACKETS.values():
            depth -= 1
        elif c == "," and depth == 0:
            args.append(inner[start:i])
            start = i + 1
        i += 1
    args.append(inner[start:])
    return [a.strip() for a in args if a.strip()]


def shot_source(name: str) -> str:
    """The body of `function shot_<name>()`, comments stripped."""
    scene = strip_qml_comments(scene_text())
    m = re.search(r"function\s+shot_" + name + r"\s*\(\s*\)", scene)
    assert m, f"the scene no longer takes a `{name}` shot"
    return bracketed(scene, scene.index("{", m.end()))


def frames_in(shot: str) -> list[tuple[str, str, dict]]:
    """Every `suite.send()` in a shot, as (topic, src, body).

    The bodies are plain double-quoted QML object literals, which are
    JSON. `shot_guard_install` binds the two sha256s to consts and uses
    them in four frames each, so those are substituted back in first —
    the alternative is a gate that silently skips the one shot with two
    stories in it.
    """
    src = shot_source(shot)
    for name, value in re.findall(r'const\s+(\w+)\s*=\s*"([^"]*)"', src):
        src = re.sub(r":\s*" + name + r"\b", ': "' + value + '"', src)
    out = []
    for m in re.finditer(r"suite\.send\s*\(", src):
        args = call_args(src, m.end() - 1)
        out.append((json.loads(args[0]), json.loads(args[1]), json.loads(args[2])))
    return out


def beats_in(shot: str) -> list[tuple[str, str, dict]]:
    """Every `suite.beat()` in a shot, as (service, state, metrics)."""
    src = shot_source(shot)
    out = []
    for m in re.finditer(r"suite\.beat\s*\(", src):
        args = call_args(src, m.end() - 1)
        metrics = json.loads(args[2]) if len(args) > 2 and args[2].startswith("{") else {}
        out.append((json.loads(args[0]), json.loads(args[1]), metrics))
    return out


def compat_event_shapes() -> dict[str, list[frozenset]]:
    """Every `compat.install` event jv-compat's installer publishes, and
    the extra fields it carries at each call site.

    Read out of `install.py` rather than imported: `_event` is a method on
    an installer that wants a bus and a runner, and what is wanted here is
    its vocabulary, which is the six literals it passes.
    """
    src = (COMPAT / "jv_compat" / "install.py").read_text("utf-8")
    out: dict[str, list[frozenset]] = {}
    for m in re.finditer(r"self\._event\s*\(", src):
        args = call_args(src, m.end() - 1)
        # _event(event, app, sha256, **extra): three positional, then the
        # keywords that become the rest of the body.
        out.setdefault(json.loads(args[0]), []).append(
            frozenset(a.split("=", 1)[0].strip() for a in args[3:])
        )
    assert out, "found no compat.install publishes in jv-compat's installer"
    return out


def compat_fingerprint_words() -> tuple[set[str], set[str]]:
    """The installer frameworks and architectures jv-compat can report.

    The arch table is imported, private name and all, because it IS the
    mapping — a sheet naming an arch that no PE machine word produces
    would be a picture of a fingerprinter this machine does not have.
    """
    src = (COMPAT / "jv_compat" / "fingerprint.py").read_text("utf-8")
    installers = set(re.findall(r'installer\s*=\s*"(\w+)"', src))
    arches = set(re.findall(r'arch\s*=\s*"(\w+)"', src))
    arches |= set(compat_fingerprint._MACHINES.values())
    assert installers and arches, "jv-compat's fingerprinter names nothing"
    return installers, arches


def compat_stderr_tail() -> int:
    """How much of a failing installer's stderr jv-compat forwards."""
    src = (COMPAT / "jv_compat" / "install.py").read_text("utf-8")
    m = re.search(r"detail\[-(\d+):\]", src)
    assert m, "jv-compat no longer truncates the installer's stderr"
    return int(m.group(1))


def compat_refusals(verdict: dict) -> set[str]:
    """What jv-compat would say on `compat.install` about this verdict.

    Not a restatement of its rule — jv-compat's OWN expressions, lifted
    out of `install.py` by `ast` and evaluated over the photographed
    verdict. There are three refusals in that file (no screening, a
    blocked verdict, a suspicious one) and only one of them composes
    nothing of its own, which is the entire point: a hand-typed refusal
    that reads like a sentence jv-compat wrote is a frame the real
    service would never send. Restating "it joins the reasons with '; '"
    here instead would be a copy of the rule, and a copy that stayed
    green when jv-compat reworded the sentence is exactly the drift every
    other gate in this file exists to catch.

    ONLY the refusals that are ABOUT A VERDICT. jv-compat grew a fourth
    `blocked` event in B65 whose sentence is built out of a recipe's grant
    problems and never touches the screening at all, and this helper has
    exactly one thing to hand it: the verdict in the photograph. An
    expression naming anything else is skipped rather than guessed at — it
    is not a sentence this shot could be showing, and evaluating it with an
    invented binding would put a made-up refusal into the set the shot is
    checked against. (Before this line existed it did not skip and did not
    guess: it raised `NameError` out of the gate, which is how B65 left the
    tools suite red for two iterations — `runtests.sh jv-compat` was the
    suite that got run, and this gate reads jv-compat from next door.)
    """
    src = (COMPAT / "jv_compat" / "install.py").read_text("utf-8")
    out = set()
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (isinstance(fn, ast.Attribute) and fn.attr == "_event"):
            continue
        if not (node.args and getattr(node.args[0], "value", None) == "blocked"):
            continue
        for kw in node.keywords:
            if kw.arg != "error":
                continue
            free = {n.id for n in ast.walk(kw.value) if isinstance(n, ast.Name)}
            if free - {"verdict"}:
                continue  # a refusal about something other than the screening
            out.add(eval(ast.unparse(kw.value), {"__builtins__": {}}, {"verdict": verdict}))
    assert out, "jv-compat's installer no longer refuses anything about a verdict"
    return out


def test_the_install_shots_photograph_events_jv_compat_publishes():
    """A67. Two shots are made of `compat.install` frames — the failed
    install and the pair of overlapping ones — and between them they
    claim five of jv-compat's six lifecycle events.

    An event name is a vocabulary, so it is checkable; so is the SHAPE,
    because `_event` takes three positional fields and whatever keywords
    the call site adds. A `prefix_created` carrying an `error`, or a
    `failed` carrying a `recipe`, would be a frame `core/InstallState.qml`
    reads perfectly well and jv-compat would never send.

    The `blocked` in the overlapping shot gets the strongest check here,
    and it is the one that matters most: jv-compat does not compose that
    sentence, it joins the refusing verdict's own reasons. So the two
    frames in that picture — jv-guard's refusal and jv-compat's word for
    it — have to agree, which is a thing a hand-typed pair drifts out of
    the first time either is edited.

    Not checked: a `failed` error, which is the installer's last 500 bytes
    of stderr — free text from the one thing invariant 8 calls untrusted
    outright. Only its length, which install.py does fix.
    """
    shapes = compat_event_shapes()
    installers, arches = compat_fingerprint_words()
    seen = 0
    for shot in ("install", "guard_install"):
        frames = frames_in(shot)
        verdicts = {
            b["sha256"]: b for t, _, b in frames if t == "guard.verdict"
        }
        for topic, src, body in frames:
            if topic != "compat.install":
                continue
            seen += 1
            where = f"{shot}/{body.get('event')}"
            assert src == "jv-compat", f"{where}: only jv-compat publishes this topic"
            assert body["event"] in shapes, (
                f"{where}: jv-compat's installer publishes {sorted(shapes)} and "
                "nothing else, so this frame is of a lifecycle it does not have"
            )
            extras = frozenset(body) - {"event", "app", "sha256"}
            assert extras in shapes[body["event"]], (
                f"{where}: jv-compat sends this event with "
                f"{[sorted(s) for s in shapes[body['event']]]} beyond the three "
                f"fixed fields; the frame carries {sorted(extras)}"
            )
            if "installer" in body:
                assert body["installer"] in installers, (
                    f"{where}: jv-compat's fingerprinter reports {sorted(installers)}"
                )
            if "arch" in body:
                assert body["arch"] in arches, (
                    f"{where}: jv-compat's fingerprinter reports {sorted(arches)}"
                )
            if body["event"] == "failed":
                assert len(body["error"]) <= compat_stderr_tail(), (
                    f"{where}: jv-compat sends the installer's last "
                    f"{compat_stderr_tail()} bytes and no more"
                )
            verdict = verdicts.get(body["sha256"])
            if body["event"] == "blocked" and verdict:
                said = compat_refusals(verdict)
                assert body["error"] in said, (
                    f"{where}: jv-compat writes one of {sorted(said)} when it "
                    "refuses — it does not compose a sentence, it joins the "
                    f"verdict's own reasons. The picture shows jv-guard saying "
                    f"{verdict['reasons']} and jv-compat reporting "
                    f"{body['error']!r}, which no refusal of it produces."
                )
    assert seen >= 6, f"only {seen} compat.install frames in the sheet; the shots changed"


def test_the_health_shot_photographs_a_rung_jv_brain_can_report():
    """A67. `06-health.png` says the brain is on rung 4 and off the GPU,
    which is the one number in the shot that explains the slowness rather
    than merely reporting it.

    The ladder is five rungs in `jv_brain/config.py` and the CPU floor is
    the last of them, so both halves are checkable: the rung has to be one
    that exists, and `llm_gpu` has to agree with whether that rung runs on
    the GPU. A frame saying rung 4 on the GPU would be a picture of a
    fallback that did not happen, and the plate would draw it without
    complaint.

    The pairing is jv-brain's too: `_health` writes both metrics or
    neither, from the same rung file. And the metric NAMES are read off
    jv-brain, because `metrics` is free-form by schema — a service-local
    key nobody publishes is a key `jv health` will never print.

    B46 added the requirement beside it: `llm_gpu_floor_mb`, which the
    HUD draws under the free-VRAM reading as `NEEDS 5424 MiB`. That one
    is recomputed here off the same ladder rather than compared to a
    constant — it is `min()` over the GPU rungs, and a reordered or
    re-quantised ladder moves it.

    Not checked: `notes`. It is free text, and "VRAM pressure: fell back
    to CPU" is a composed sentence in a composed frame.
    """
    brain = (BRAIN / "jv_brain" / "service.py").read_text("utf-8")
    known = set(re.findall(r'metrics\["(\w+)"\]', brain))
    assert "llm_rung" in known, "jv-brain no longer reports a rung on sys.health"
    rungs = {r.index: r for r in LADDER}
    saw = 0
    for service, state, metrics in beats_in("health"):
        if service != "jv-brain":
            assert not metrics, (
                f"{service} publishes its own metrics; this gate only knows "
                "jv-brain's, so a frame claiming one needs its own check"
            )
            continue
        unknown = set(metrics) - known
        assert not unknown, (
            f"jv-brain's heartbeat never carries {sorted(unknown)} — `metrics` is "
            "free-form by schema, so an invented key is one nothing can read"
        )
        if "llm_rung" not in metrics:
            continue
        saw += 1
        rung = rungs.get(metrics["llm_rung"])
        assert rung is not None, (
            f"rung {metrics['llm_rung']} is not on jv-brain's ladder "
            f"({sorted(rungs)}), so this picture is of a fallback it cannot take"
        )
        assert "llm_gpu" in metrics, (
            "jv-brain writes llm_rung and llm_gpu together or not at all"
        )
        assert metrics["llm_gpu"] == (1.0 if rung.gpu else 0.0), (
            f"rung {rung.index} is {rung.label!r}, which runs "
            f"{'on the GPU' if rung.gpu else 'on the CPU'}; the frame says "
            f"llm_gpu={metrics['llm_gpu']}"
        )
        # B46: the second row of the picture. The floor is not a figure
        # anyone chose — it is `min()` over the GPU rungs of the same
        # ladder above, in whole MiB rounded up — and the HUD renders it
        # verbatim, so a sheet showing a floor jv-brain would not compute
        # is a picture of another machine's ladder. Present exactly while
        # the shot is of a brain that is off the card: that is the only
        # state in which jv-brain publishes it at all.
        floor = gpu_floor_mb()
        if rung.gpu or floor is None:
            assert "llm_gpu_floor_mb" not in metrics, (
                "jv-brain withholds the floor once the requirement is met, "
                "or when its ladder has no GPU rung to meet"
            )
            continue
        assert "llm_gpu_floor_mb" in metrics, (
            "the shot is of a brain on the CPU with a card present, which is "
            "exactly when jv-brain publishes the floor — and the second row "
            "of the health plate is the picture of it"
        )
        assert metrics["llm_gpu_floor_mb"] == float(floor), (
            f"jv-brain's ladder needs {floor} MiB free before it would pick "
            f"the card; the frame says {metrics['llm_gpu_floor_mb']}, so the "
            "picture is of a requirement it never publishes"
        )
    assert saw == 1, f"{saw} rungs in the health shot; it photographs exactly one"


def act_registry() -> dict[str, dict]:
    """jv-act's tool registry — data, reviewed like code (invariant 3)."""
    data = tomllib.loads((ACT / "tools.toml").read_text("utf-8"))
    return {t["name"]: t for t in data["tool"]}


def act_error_words() -> set[str]:
    """Every word jv-act puts in `action.result.error`.

    Read out of the Rust, not out of `schemas/action.result.json`: the
    schema is the law and the question here is what the service says. The
    two agree today and the gate would be worth less if it asked the
    document instead of the producer.
    """
    src = (ACT / "src" / "service.rs").read_text("utf-8")
    words = set(re.findall(r'"error":\s*"(\w+)"', src))
    # The confirmation's two outcomes are chosen into a variable first.
    for pair in re.findall(r'let error = if .*?"(\w+)".*?"(\w+)"', src):
        words |= set(pair)
    assert "execution_failed" in words, "jv-act's error vocabulary moved"
    return words


def test_the_cut_off_shot_photographs_a_turn_jv_brain_can_end():
    """A71. `14-cut-off.png` is a picture of one word out of a frozen enum,
    so the word has to be one the enum has AND one jv-brain can reach.

    Three things are checkable and none of them is prose:

    · the enum. `schemas/brain.response.json` freezes `finish_reason` at
      three words, and the plate draws whichever one arrives — so a frame
      inventing a fourth would render a caption no reader could look up.
    · the producer. jv-brain does not forward llama-server's word: it
      normalises it in one line of `_stream_turn`, and `tool_calls` (which
      the enum has no word for) never leaves that function, because the
      tool loop only returns when there are none. `length` has to be a
      word that line can still produce, or this shot photographs a state
      the service stopped being able to publish.
    · the schema's own rule about `text`, which is the reason
      `core/ReplyState.qml` refuses an empty truncation: an empty string
      is allowed "only with finish_reason=error". A `length` with nothing
      in it would draw a plate about words nobody ever heard.

    Not checked: the text, the model name and the latency. They are a
    composed sentence, a GGUF filename and a plausible number in a
    composed frame, and not one of them reaches a pixel.
    """
    schema = json.loads((ROOT / "schemas" / "brain.response.json").read_text("utf-8"))
    enum = schema["properties"]["finish_reason"]["enum"]
    backends = schema["properties"]["backend"]["enum"]
    brain = (BRAIN / "jv_brain" / "service.py").read_text("utf-8")
    normalise = re.search(r'^\s*reason = .*finish == "length".*$', brain, re.M)
    assert normalise, (
        "jv-brain no longer normalises llama-server's finish_reason in one "
        "line of _stream_turn — this gate was reading that line"
    )
    saw = 0
    for topic, src, body in frames_in("cutoff"):
        if topic != "brain.response":
            continue
        saw += 1
        assert src == "jv-brain", f"{src} does not publish brain.response"
        word = body.get("finish_reason")
        assert word in enum, (
            f"`{word}` is not one of schemas/brain.response.json's {enum}, so "
            "the plate would draw a caption nobody can look up"
        )
        assert f'"{word}"' in normalise.group(0), (
            f"jv-brain's _stream_turn cannot produce `{word}` any more; this "
            "shot photographs a turn the service no longer ends that way"
        )
        assert body["text"], (
            "the schema allows an empty `text` only with finish_reason=error, "
            "and core/ReplyState.qml refuses a truncation with nothing in it"
        )
        assert body.get("backend") in backends, (
            f"`{body.get('backend')}` is not one of {backends}"
        )
    assert saw == 1, f"the cut-off shot carries {saw} brain.response frames"


def test_the_action_shot_photographs_a_call_and_a_failure_jv_act_can_produce():
    """A67. `08-action.png` is two composed frames: jv-brain asking for a
    tool and jv-act reporting that it did not work.

    Both are checkable against things that are not prose. The tool is a
    REGISTRY name — the plate draws it verbatim on the argument that what
    you read is what you can grep for in the audit log — so it has to be
    in the registry, its args have to be the args that tool declares, and
    the capability has to be the one the registry gives it rather than the
    requester's opinion of it. `needs_confirmation` is jv-brain's own rule
    (`capability in ("destructive", "privileged")`) and is derived here
    the same way.

    The error word is jv-act's, out of its Rust. `detail` is not: it is
    the failing command's stderr, so all that can be pinned is WHICH
    command — jv-act runs `gtk-launch` for `app.launch` and never the
    application itself, and a detail quoting a shell's or another
    language's not-found message would be a picture of a machine that
    execs the app directly.
    """
    registry = act_registry()
    errors = act_error_words()
    frames = {topic: body for topic, _, body in frames_in("action")}
    intent = frames["intent.action"]
    result = frames["action.result"]

    spec = registry.get(intent["tool"])
    assert spec is not None, (
        f"{intent['tool']} is not in jv-act's registry ({sorted(registry)}), so "
        "the real jv-act would answer `unknown_tool` and never run anything"
    )
    declared = spec.get("args", {})
    assert set(intent["args"]) <= set(declared), (
        f"{intent['tool']} declares {sorted(declared)}; the frame passes "
        f"{sorted(intent['args'])}, which jv-act would reject as invalid_args"
    )
    required = {k for k, v in declared.items() if v.get("required")}
    assert required <= set(intent["args"]), (
        f"{intent['tool']} requires {sorted(required)} and the frame omits "
        f"{sorted(required - set(intent['args']))}"
    )
    assert intent["capability"] == spec["capability"], (
        f"the registry calls {intent['tool']} {spec['capability']!r}"
    )
    assert intent["needs_confirmation"] == (
        spec["capability"] in ("destructive", "privileged")
    ), "jv-brain derives needs_confirmation from the capability; this frame does not"

    assert result["request_id"] == intent["request_id"], (
        "the ids must match or core/ActionState.qml draws the failure with no "
        "tool name, which is not the picture this shot is of"
    )
    assert result["error"] in errors, (
        f"jv-act sends {sorted(errors)} and not {result['error']!r}"
    )
    # The argv head jv-act plans for this tool: the program whose stderr a
    # `detail` would be.
    exec_src = (ACT / "src" / "exec.rs").read_text("utf-8")
    arm = re.search(
        r'"' + re.escape(intent["tool"]) + r'"\s*=>.*?s\("([^"]+)"\)', exec_src, re.S
    )
    assert arm, f"jv-act's executor no longer plans a command for {intent['tool']}"
    assert result["detail"].startswith(arm.group(1) + ":"), (
        f"jv-act runs {arm.group(1)!r} for {intent['tool']}, so a failure's "
        f"detail is that program's stderr; the frame quotes {result['detail']!r}"
    )


def test_the_confirm_shot_photographs_a_question_jv_act_could_ask():
    """A67, and the half of it that could not be closed.

    `05-confirm.png` is the only picture of the one thing this HUD shows
    that is waiting on YOU, and the numbers in it are jv-act's own: the
    window is the 15 s `service.rs` opens, and `kind` is the literal it
    sends. Both are read out of the Rust here.

    So is the SHAPE of the question, which is the part that was wrong
    until A67 looked. jv-act does not compose a sentence about the
    invocation — it sends `format!("{} — yes or no?", spec.description)`,
    the tool's registry description and a fixed tail. A summary naming
    fourteen files in a directory was a picture of a machine that explains
    what it is about to do, and this one cannot; the question it asks is
    generic, and A21's reader deserves to be judging the real one.

    What stays composed, and is said in docs/hud/README.md: the
    description itself. `fs.trash` is not in jv-act's registry — v0 is
    "observe + benign only" and the confirmation rule is structural, so
    there is no tool on this machine today that could produce an
    `action.confirm` at all. The machinery is real, built and reviewed;
    the tool it is holding is one the registry has not been granted. This
    pins that disclaimer the way `tools/hudscreens/sheet.py` pins its own.
    """
    src_rs = (ACT / "src" / "service.rs").read_text("utf-8")
    frames = {topic: body for topic, _, body in frames_in("confirm")}
    confirm = frames["action.confirm"]

    window = re.search(r"confirm_window_s:\s*([\d.]+)", src_rs)
    assert window, "jv-act no longer declares a default confirmation window"
    assert confirm["window_s"] == float(window.group(1)), (
        f"jv-act opens a {window.group(1)} s window; the frame says "
        f"{confirm['window_s']} and core/ConfirmState.qml would believe it"
    )
    kinds = re.search(r'"kind":\s*"(\w+)",\s*"request_id"', src_rs)
    assert kinds and confirm["kind"] == kinds.group(1), (
        f"jv-act asks with kind={kinds.group(1) if kinds else '?'!r}"
    )

    summary = re.search(r'"summary":\s*format!\("([^"]*)",\s*([\w.]+)\)', src_rs)
    assert summary, "jv-act no longer formats the summary from one value"
    template, source = summary.group(1), summary.group(2)
    assert template.count("{}") == 1 and source == "spec.description", (
        f"jv-act now composes the question out of {source} — the frame in the "
        "scene is a registry description plus a fixed tail, which was all it "
        "could say when this shot was taken. Re-take it: bash ops/ralph/hudshots.sh"
    )
    tail = template.split("{}", 1)[1]
    assert confirm["summary"].endswith(tail), (
        f"jv-act's question ends {tail!r}; the frame says "
        f"{confirm['summary']!r}"
    )
    described = confirm["summary"][: -len(tail)]

    registry = act_registry()
    tool = confirm["tool"]
    if tool in registry:
        raise AssertionError(
            f"'{tool}' is in jv-act's registry now, which is good news and makes "
            "the scene's disclaimer wrong: replace the composed description with "
            f"{registry[tool].get('description')!r}, delete the paragraph in "
            "tools/hudshots/scene/tst_shots.qml that says the tool is not "
            "registered, and this branch with it"
        )
    assert "not in jv-act's registry" in scene_text(), (
        "the scene no longer says that the tool this shot names is one jv-act "
        "has never been granted. Every number in the frame is jv-act's and the "
        "tool is not, and a reader who is not told reads the picture as a "
        "machine that has it"
    )
    assert all(
        t["capability"] in ("observe", "benign") for t in registry.values()
    ), (
        "the registry has a destructive or privileged tool now, so a REAL "
        "confirmation is photographable — take that shot instead of this one"
    )
    styles = {t["description"] for t in registry.values()}
    assert described and described[0].isupper() and not described.endswith("."), (
        f"jv-act would put a registry description here, and every one of them "
        f"reads like {sorted(styles)[0]!r}; the frame says {described!r}"
    )


def test_every_driver_renders_the_box_the_shell_asks_for():
    """A63. Three drivers in tools/hudshots/scene declare a surface box, and
    all three of them hold a COPY of shell.qml's — the sheet renders into it,
    the sequence replay lays out inside it, and tst_fit.qml asserts against
    it. A box that grew in the shell and not here would leave the fit check
    asserting yesterday's edge, which is worse than no check: it would go on
    passing while the real surface cropped.

    (test_hudscreens.py makes the same pin for the OTHER harness, which
    measures the real binary under a real compositor. Same failure, same
    fix; this is the half that lives in a QML engine.)
    """
    shell = (SHELL / "shell.qml").read_text("utf-8")
    box = (
        int(re.search(r"^\s*implicitWidth:\s*(\d+)", shell, re.M).group(1)),
        int(re.search(r"^\s*implicitHeight:\s*(\d+)", shell, re.M).group(1)),
    )
    for driver in sorted(SCENE_DIR.glob("tst_*.qml")):
        text = strip_qml_comments(driver.read_text("utf-8"))
        width = re.search(r"^\s*width:\s*(\d+)", text, re.M)
        height = re.search(r"^\s*height:\s*(\d+)", text, re.M)
        assert width and height, f"{driver.name} declares no surface box"
        assert (int(width.group(1)), int(height.group(1))) == box, (
            f"{driver.name} renders {width.group(1)}x{height.group(1)} and "
            f"shell.qml's surface is {box[0]}x{box[1]}"
        )


def test_the_drivers_know_every_plate_the_corner_stacks():
    """Two drivers carry `everyPlate`, a list of the names the plates call
    themselves — tst_sequence.qml checks no trajectory ever contains a name
    outside it, and tst_fit.qml builds its crowd by REMOVING one name from
    it. Both go quiet rather than loud when the list is short: a new plate
    missing from it is a plate the sequence never validates and, worse, a
    plate the fit check simply does not expect to be on screen, so the
    crowd it measures is one plate lighter than the corner really is.

    The names are pinned elsewhere (test_gen_theme_qml.py holds each plate's
    `plateName` to its own file name), so the corner's stack is the truth
    these lists have to match.
    """
    expected = [
        name[: -len("Plate")].lower()
        for name in plate_stack_children(CORNER.read_text("utf-8"))
    ]
    for driver in sorted(SCENE_DIR.glob("tst_*.qml")):
        text = strip_qml_comments(driver.read_text("utf-8"))
        found = re.search(r"property var everyPlate:\s*\[([^]]*)\]", text)
        if not found:
            continue
        listed = re.findall(r'"([^"]+)"', found.group(1))
        assert listed == expected, (
            f"{driver.name} knows {listed} and Corner.qml stacks {expected}"
        )


def test_the_fit_crowd_is_sized_by_this_machines_real_services():
    """A63's crowd puts every service on this machine into one health plate,
    because "everything is unwell" is the tallest the health list can get and
    the tallest corner is what the box is sized for. That roster is a COPY of
    services/, and a tenth service would make the real worst case one row
    taller than the measured one — silently, because the crowd would still
    light the same nine plates and still fit.
    """
    fit = SCENE_DIR / "tst_fit.qml"
    found = re.search(
        r"property var roster:\s*\[([^]]*)\]", strip_qml_comments(fit.read_text("utf-8"))
    )
    assert found, "tst_fit.qml no longer declares the roster it crowds the health plate with"
    listed = re.findall(r'"([^"]+)"', found.group(1))
    # pylib is a library, not a service: nothing runs it and nothing on the
    # bus has ever carried its name.
    services = sorted(
        d.name for d in (ROOT / "services").iterdir() if d.is_dir() and d.name != "pylib"
    )
    assert sorted(listed) == services, (
        f"tst_fit.qml crowds the health plate with {sorted(listed)} and this "
        f"repo has {services}"
    )
