"""tools/gen_theme_qml.py — personality/theme.toml -> the HUD's Theme singleton.

Invariant 9: theme tokens are identity and live in `personality/`, versioned
next to the voice and the system prompt. The HUD must therefore never carry a
hex code of its own — it consumes a generated singleton, and these tests are
what keep that true: they check the generator, they check the committed output
is in sync with the toml, they check the toml still agrees with the blueprint's
§06 palette, and they check no QML file has grown a literal colour.
"""

from __future__ import annotations

import html
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import gen_theme_qml as gen  # noqa: E402

MINIMAL = """
[palette]
ground = "#0C1116"
text = "#E4EAEE"
ember = "#F0714A"
ground_deep = "#090D12"

[type]
family_mono = "JetBrains Mono"
label_px = 11

[motion]
ease_ms = 200
plate_opacity = 0.86

[geometry]
inset_px = 16
"""


def gen_from(text: str) -> str:
    return gen.render_theme_qml(gen.load_tokens(text))


# --- generator shape -------------------------------------------------------


def test_renders_a_singleton_with_camelcase_typed_properties():
    qml = gen_from(MINIMAL)
    assert "pragma Singleton" in qml
    assert qml.startswith("//"), "generated file must announce that it is generated"
    assert "DO NOT EDIT" in qml
    assert 'readonly property color ground: "#0C1116"' in qml
    assert 'readonly property color groundDeep: "#090D12"' in qml
    assert 'readonly property string familyMono: "JetBrains Mono"' in qml
    assert "readonly property int labelPx: 11" in qml
    assert "readonly property int easeMs: 200" in qml
    assert "readonly property real plateOpacity: 0.86" in qml


def test_output_is_deterministic_and_ordered_like_the_toml():
    assert gen_from(MINIMAL) == gen_from(MINIMAL)
    qml = gen_from(MINIMAL)
    assert qml.index("ground:") < qml.index("familyMono:") < qml.index("easeMs:")


def test_qmldir_registers_every_singleton_and_no_module_name():
    qmldir = gen.render_qmldir()
    assert "singleton Theme 1.0 Theme.qml" in qmldir
    assert "singleton Bus 1.0 Bus.qml" in qmldir
    # A `module` line would claim a module name Quickshell did not assign;
    # the directory import (`import "."`) needs no such line.
    assert not any(l.startswith("module ") for l in qmldir.splitlines())


def test_every_qml_singleton_on_disk_is_registered_and_vice_versa():
    """An unregistered singleton resolves to nothing at runtime and to a
    confusing qmllint error at build time. The two must agree exactly."""
    hud = ROOT / "shell" / "jv-hud"
    on_disk = {
        q.name for q in hud.glob("*.qml") if "pragma Singleton" in q.read_text("utf-8")
    }
    assert on_disk == {file for _, file in gen.SINGLETONS}
    for name, file in gen.SINGLETONS:
        assert (hud / file).exists(), f"{file} is registered but missing"
        assert (hud / file).read_text("utf-8").startswith(
            "//"
        ), f"{file} should open with a comment saying what it is"
        assert name == file[: -len(".qml")], "the type name is the file name"


def test_qmldir_registers_every_plain_component_on_disk_and_vice_versa():
    """A qmldir exposes only what it lists, so an unregistered component is
    not a type at all — and the failure reads as a typo in the USING file,
    miles from the missing line. shell.qml is exempt: it is loaded by path."""
    hud = ROOT / "shell" / "jv-hud"
    on_disk = {
        q.name
        for q in hud.glob("*.qml")
        if q.name != "shell.qml" and "pragma Singleton" not in q.read_text("utf-8")
    }
    assert on_disk == {file for _, file in gen.COMPONENTS}
    qmldir = gen.render_qmldir()
    for name, file in gen.COMPONENTS:
        assert f"{name} 1.0 {file}" in qmldir
        assert f"singleton {name}" not in qmldir, f"{file} is a component, not a singleton"
        assert name == file[: -len(".qml")], "the type name is the file name"


# Every QML animation type. If one of these appears in a HUD file, that file
# is capable of moving the screen, and §06 says something has to be able to
# stop it.
ANIMATION_TYPES = (
    "Behavior",
    "PropertyAnimation",
    "NumberAnimation",
    "ColorAnimation",
    "RotationAnimation",
    "SpringAnimation",
    "SmoothedAnimation",
    "SequentialAnimation",
    "ParallelAnimation",
    "PauseAnimation",
    "PropertyAction",
    "AnchorAnimation",
    "PathAnimation",
    r"\w*Animator",  # OpacityAnimator, XAnimator, …
)


def test_nothing_animates_without_going_through_motion():
    """§06: motion is off with prefers-reduced-motion, on battery, and under
    a fullscreen window. A9's rule keeps logic testable; this one keeps the
    OFF switch reachable — an element that hand-rolls an animation without
    consulting `Motion` would keep breathing after a human asked it to stop,
    and nothing else in the build would notice.

    Files under core/ cannot reference Motion (it is a Quickshell singleton),
    which is exactly right: core/ is logic, and logic does not animate.
    """
    hud = ROOT / "shell" / "jv-hud"
    offenders = []
    for qml in sorted(hud.rglob("*.qml")):
        if qml.is_relative_to(hud / "tests"):
            continue
        text = qml.read_text("utf-8")
        code = "\n".join(
            l for l in text.splitlines() if not l.lstrip().startswith("//")
        )
        used = [a for a in ANIMATION_TYPES if re.search(rf"\b{a}\b\s*(\{{|on\b)", code)]
        if used and "Motion." not in code:
            offenders.append(f"{qml.relative_to(ROOT)}: {', '.join(used)}")
    assert not offenders, (
        "these animate without consulting Motion, so reduced-motion cannot "
        "turn them off:\n" + "\n".join(offenders)
    )


# --- A15: the surface is mapped by the stack, not by a list --------------

# One QML token: an identifier, a brace, or a comment to be ignored.
QML_TOKEN = re.compile(r"(//[^\n]*)|([A-Za-z_]\w*)|(\{)|(\})")


def shell_text() -> str:
    return (ROOT / "shell" / "jv-hud" / "shell.qml").read_text("utf-8")


def surface_visible_expr(text: str) -> str:
    """The PanelWindow's own `visible:` binding — the one that decides whether
    the HUD reaches the screen at all."""
    exprs = re.findall(r"^      visible:(.+)$", text, re.M)
    assert len(exprs) == 1, f"expected exactly one surface-level visible:, got {exprs}"
    return exprs[0].strip()


def plate_stack_children(text: str) -> list[str]:
    """Type names declared DIRECTLY inside shell.qml's PlateStack block."""
    body = text[text.index("PlateStack {") + len("PlateStack {"):]
    depth, last, kids = 0, None, []
    for comment, ident, opening, closing in QML_TOKEN.findall(body):
        if comment:
            continue
        if ident:
            last = ident
        elif opening:
            depth += 1
            if depth == 1 and last and last[0].isupper():
                kids.append(last)
        elif closing:
            depth -= 1
            if depth < 0:
                break
    assert kids, "found no children in shell.qml's PlateStack"
    return kids


def test_the_shell_does_not_hand_enumerate_its_plates():
    """A15: `visible` on the surface used to be an OR with two terms per
    element, and it grew one every time the HUD did. The plate that forgot to
    add itself would never have appeared — on a surface that is unmapped by
    design, so nothing would fail and nothing would notice. The stack answers
    now (core/PlateStack.qml, tested headlessly); this keeps the list from
    growing back, because a list that is WRONG here is invisible.
    """
    expr = surface_visible_expr(shell_text())
    assert "anyLit" in expr, (
        "the surface must ask the stack whether anything is on screen: " + expr
    )
    assert not re.search(r"plate", expr, re.I), (
        "the surface names individual plates again, so the next element can be "
        "forgotten silently: " + expr
    )


def test_every_plate_in_the_stack_answers_for_itself():
    """core/PlateStack.qml counts a child that answers NEITHER `shown` nor
    `lit` as drawing — fail-safe, because a lost plate is worse than an empty
    mapped surface. This is what keeps that branch unreachable in the real
    shell, and what keeps a plate from taking up a gap in the stack it never
    fills.
    """
    hud = ROOT / "shell" / "jv-hud"
    for child in plate_stack_children(shell_text()):
        assert child.endswith("Plate"), (
            f"{child} sits in the corner stack but is not a plate; PlateStack "
            "can only ask plates whether they are on screen"
        )
        qml = hud / f"{child}.qml"
        assert qml.exists(), f"{child} in the stack has no {qml.name}"
        text = qml.read_text("utf-8")
        for prop in ("shown", "lit"):
            assert f"readonly property bool {prop}:" in text, (
                f"{qml.name} never declares `{prop}`, so the stack cannot ask it "
                "whether it is on screen"
            )
        own = re.findall(r"^  visible:(.+)$", text, re.M)
        assert len(own) == 1, f"{qml.name} must declare its own root visible:, got {own}"
        assert "shown" in own[0] and "lit" in own[0], (
            f"{qml.name}'s visible must be `shown || lit`: shown so it is in the "
            f"layout from the first frame of its fade, lit so it keeps its place "
            f"until the fade ends. Got:{own[0]}"
        )


def test_every_plate_says_which_plate_it_is():
    """A53: `anyLit` made "is anything on screen" answerable and left "WHICH
    plate" to a human with the picture in front of them.

    Five checks across the two shot harnesses measure that the drawn corner
    got taller or shorter, and not one of them can name the plate that did
    it — a `HealthPlate` saying `jv-voice lost` and an `ActionPlate` saying an
    action failed are the same corner, the same two lines, the same severity
    colour and nearly the same pixels. `core/PlateStack.qml` collects
    `plateName` from its children so the assertion can be about the caption.

    The name has to be the plate's own claim about itself, and it also has to
    be impossible for it to lie, so it is pinned HERE to the file name rather
    than agreed by convention: `GuardPlate.qml` says `"guard"` or this fails.
    That also keeps `litNames`'s `"?"` branch unreachable in the real shell,
    the same way the `shown`/`lit` check above keeps `anyLit`'s fail-safe
    unreachable.
    """
    hud = ROOT / "shell" / "jv-hud"
    seen: dict[str, str] = {}
    for child in plate_stack_children(shell_text()):
        qml = hud / f"{child}.qml"
        want = child[: -len("Plate")].lower()
        got = re.findall(
            r'^  readonly property string plateName: "([^"]*)"$',
            qml.read_text("utf-8"),
            re.M,
        )
        assert got == [want], (
            f'{qml.name} must declare `readonly property string plateName: '
            f'"{want}"` exactly once — got {got}. The stack reports these as '
            f"the plates that are on screen, so a name that drifts from the "
            f"file is a harness confidently naming the wrong element."
        )
        assert want not in seen, (
            f"{qml.name} and {seen[want]} would both report {want!r}; two "
            f"plates with one name makes the list unreadable"
        )
        seen[want] = qml.name


# --- A10: invariant 10, asserted rather than assumed ----------------------

# Quickshell's window types. Each one puts a surface on the compositor, and
# every surface the HUD maps has to be safe the same way — so this gate is
# written against the TYPE, not against shell.qml, and a second surface added
# tomorrow is covered the day it is written.
WINDOW_TYPES = ("PanelWindow", "FloatingWindow", "PopupWindow")

# Invariant 10 spelled in Quickshell, with the ONE value each property may
# have. Until now these lines were asserted by nobody: qmllint checks that
# `WlrKeyboardFocus.None` RESOLVES, and would be just as happy with
# `.Exclusive`. Every one of them is a property whose wrong value is
# invisible on a surface that is unmapped most of the time — you would find
# out because the HUD ate a click, or took your keyboard mid-sentence.
SAFE_SURFACE = {
    # cannot take the keyboard, so it can never steal focus from your work
    "WlrLayershell.keyboardFocus": "WlrKeyboardFocus.None",
    "focusable": "false",
    # zero exclusive zone: no window is ever resized or pushed around by it
    "exclusionMode": "ExclusionMode.Ignore",
    # over ordinary windows, UNDER fullscreen and the lock screen. Overlay
    # would put sensor state on top of a locked session.
    "WlrLayershell.layer": "WlrLayer.Top",
    # the window itself paints nothing; each plate brings its own ground.
    # An opaque colour here is a 300x260 box over your work every time a
    # plate has something to say.
    "color": '"transparent"',
}


def strip_qml_comments(text: str) -> str:
    """Drop `//` comments, leaving braces and code intact.

    A `//` inside a string literal is not a comment, so only one with an even
    number of quotes before it on its line counts. (`/* */` is not handled
    because the HUD does not use it; a file that grows one will show up as a
    parse the gates disagree about, not as a silent pass.)
    """
    out = []
    for line in text.splitlines():
        i = line.find("//")
        while i != -1:
            if line.count('"', 0, i) % 2 == 0:
                line = line[:i]
                break
            i = line.find("//", i + 2)
        out.append(line)
    return "\n".join(out)


def window_bodies(text: str) -> list[tuple[str, str]]:
    """(type, body) for every Quickshell window block in `text`.

    The body is the window's OWN lines only. A nested element's properties
    are its own business — the self-test marker's `color: Theme.ground` is
    not the surface's colour, and a file-wide grep would happily confuse the
    two and then pass forever.
    """
    depth, bodies, out = 0, {}, []
    for line in strip_qml_comments(text).splitlines():
        start = depth
        if start in bodies:
            bodies[start][1].append(line)
        opening = re.match(r"\s*(\w+)\s*\{\s*$", line)
        depth += line.count("{") - line.count("}")
        if opening and opening.group(1) in WINDOW_TYPES:
            bodies[start + 1] = (opening.group(1), [])
        for d in [d for d in bodies if d > depth]:
            name, acc = bodies.pop(d)
            out.append((name, "\n".join(acc)))
    for d in sorted(bodies):
        out.append((bodies[d][0], "\n".join(bodies[d][1])))
    return out


def assigned(body: str, prop: str) -> list[str]:
    """Every value bound to `prop` at this block's own level."""
    return [v.strip() for v in re.findall(rf"^\s*{re.escape(prop)}\s*:(.+)$", body, re.M)]


def hud_qml_files() -> list[Path]:
    hud = ROOT / "shell" / "jv-hud"
    return [q for q in sorted(hud.rglob("*.qml")) if not q.is_relative_to(hud / "tests")]


def test_no_qml_file_is_a_file_git_calls_binary():
    """A source file with a NUL byte in it is a file nobody reviewed.

    git decides text-or-binary by looking for a NUL in the first 8 kB, and a
    file it calls binary has no diff at all: `GuardPlate.qml | Bin 0 -> 8407
    bytes`, which is how the entire A51 plate landed — 226 lines of a surface
    that sits above every window, committed as an opaque blob, with no line
    for a human to object to. It was not sabotage and it was not noticed: the
    plate wanted a joiner no attacker-chosen file name could contain, and
    `"\0"` typed as the byte itself works perfectly at runtime.

    So the escape is the rule, not the byte. The check is deliberately about
    the FILE and not about QML: it is the same claim for every `.qml` in the
    tree, including the harness stages, because "its diff is readable" is a
    property of a text file rather than of a language.

    Only `\t` and `\n` are allowed through. A stray `\r` would not make git
    call the file binary, but it would make every line of it differ from the
    one next to it for a reason nobody can see, which is the same failure one
    notch quieter.
    """
    qmls = sorted(
        q
        for d in ("shell", "tools", "pkgs", "harness")
        for q in (ROOT / d).rglob("*.qml")
    )
    assert len(qmls) > 20, f"found only {len(qmls)} QML files; the glob is wrong"
    for qml in qmls:
        raw = qml.read_bytes()
        where = qml.relative_to(ROOT)
        assert b"\x00" not in raw, (
            f"{where} contains a raw NUL byte, so git calls it binary and "
            f"commits it with no diff. Write the escape — `\\0` — which is the "
            f"same string at runtime and a reviewable line in the file."
        )
        bad = sorted({b for b in raw if b < 0x20 and b not in (0x09, 0x0A)})
        assert not bad, (
            f"{where} contains control bytes {[hex(b) for b in bad]}; a source "
            f"file is text, and a byte you cannot see is a change nobody can read"
        )
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError as exc:  # pragma: no cover - a corrupt tree
            pytest.fail(f"{where} is not valid UTF-8: {exc}")


def test_every_hud_surface_pins_the_properties_that_make_it_safe():
    """A10: the last corner of invariant 10 that nothing was watching.

    `core/` cannot hold these — they ARE Quickshell types, and the offscreen
    window a headless test gets is never exposed, so it cannot answer a
    surface question either. That leaves the source, read strictly: not "the
    word appears in the file" but "this window binds exactly this value and
    no other".
    """
    surfaces = 0
    for qml in hud_qml_files():
        for name, body in window_bodies(qml.read_text("utf-8")):
            surfaces += 1
            where = f"{qml.relative_to(ROOT)}'s {name}"
            for prop, value in SAFE_SURFACE.items():
                assert assigned(body, prop) == [value], (
                    f"{where} must bind `{prop}: {value}` exactly once — "
                    f"got {assigned(body, prop)}. This is invariant 10, and a "
                    f"surface that gets it wrong is wrong quietly."
                )
            mask = assigned(body, "mask")
            assert len(mask) == 1 and re.fullmatch(r"Region\s*\{\s*\}", mask[0]), (
                f"{where} must bind `mask: Region {{}}` — an EMPTY input "
                f"region, so every click, scroll and hover passes through to "
                f"the window underneath. Got {mask}."
            )
            zone = assigned(body, "exclusiveZone")
            assert zone in ([], ["0"]), (
                f"{where} asks for an exclusive zone of {zone}; the HUD never "
                f"takes screen space away from your windows."
            )
    assert surfaces, (
        "found no Quickshell window in shell/jv-hud — either the HUD stopped "
        "mapping a surface, or this gate stopped being able to see one"
    )


# Every way a QML file can reach for the keyboard. The layer-shell property
# above already tells the compositor not to offer it, so these are inert
# today — which is exactly why one would get committed. If the HUD ever
# needs to take the keyboard (a command palette, a text field), that is a
# human's decision about invariant 10 and it starts by changing
# `keyboardFocus`, not by adding a widget that quietly assumes it.
KEYBOARD_GRABS = (
    r"\bforceActiveFocus\b",
    r"\bfocus\s*:\s*true\b",
    r"\bactiveFocusOnTab\s*:\s*true\b",
    r"\bKeys\s*[.{]",
    r"\b(?:TextInput|TextEdit|TextField|TextArea|FocusScope)\s*\{",
    r"WlrKeyboardFocus\.(?:Exclusive|OnDemand)",
)

# With `mask: Region {}` the surface receives no pointer events at all, so
# any of these is a handler that can never fire: dead code that reads like a
# feature, and the kind of thing someone later "fixes" by opening the mask.
POINTER_SINKS = (
    r"\b(?:MouseArea|HoverHandler|TapHandler|DragHandler|PinchHandler"
    r"|WheelHandler|PointHandler)\s*\{",
)


def scan_hud(patterns: tuple[str, ...]) -> list[str]:
    hits = []
    for qml in hud_qml_files():
        code = strip_qml_comments(qml.read_text("utf-8"))
        for n, line in enumerate(code.splitlines(), 1):
            for pat in patterns:
                if re.search(pat, line):
                    hits.append(f"{qml.relative_to(ROOT)}:{n}: {line.strip()}")
    return hits


def test_nothing_in_the_hud_asks_for_the_keyboard():
    hits = scan_hud(KEYBOARD_GRABS)
    assert not hits, (
        "invariant 10: the HUD never steals focus. Taking the keyboard is a "
        "human's call and starts at `keyboardFocus`, not here:\n"
        + "\n".join(hits)
    )


def test_nothing_in_the_hud_waits_for_a_pointer_it_can_never_receive():
    hits = scan_hud(POINTER_SINKS)
    assert not hits, (
        "the surface's input region is empty, so these handlers can never "
        "fire — a promise the HUD cannot keep:\n" + "\n".join(hits)
    )


# --- A14: the budgets the HUD falls back to are jv-ears' own ---------------

# Each budget jv-ears now publishes on its heartbeat, the Python that
# enforces it, and the QML property names that mirror it as a fallback.
# The mirror cannot be deleted — the HUD has to say something before the
# first heartbeat lands — so it is pinned instead.
BUDGET_MIRRORS = (
    (
        "wake window",
        Path("services/jv-ears/jv_ears/config.py"),
        re.compile(r"^\s*wake_timeout_s: float = ([\d.]+)", re.M),
        re.compile(r"^\s*(?:readonly\s+)?property\s+real\s+(wakeWindow\w*S)\s*:\s*([\d.]+)\s*$", re.M),
    ),
    (
        "capture stall",
        Path("services/jv-ears/jv_ears/audio.py"),
        re.compile(r"^\s*STALL_S = ([\d.]+)", re.M),
        re.compile(r"^\s*(?:readonly\s+)?property\s+real\s+(stall\w*S)\s*:\s*([\d.]+)\s*$", re.M),
    ),
)


def test_the_huds_fallback_budgets_still_match_the_jv_ears_that_enforces_them():
    """A14: jv-ears states its budgets on sys.health, and the HUD reads them.

    But it can only read them once a heartbeat has landed, so the shipped
    defaults still live in QML — and a copy under a comment asking the next
    reader to keep it in step is exactly what A14 set out to delete. So the
    copies are checked against the Python instead. Both directions matter and
    neither is symmetric: a wake window LONGER than ears' keeps "listening"
    on screen over a disarmed microphone, and a stall budget longer than
    ears' calls a deaf one live.
    """
    core = ROOT / "shell" / "jv-hud" / "core"
    for label, source, py, qml in BUDGET_MIRRORS:
        m = py.search((ROOT / source).read_text("utf-8"))
        assert m, f"cannot find the {label} budget in {source} — did it move or get renamed?"
        enforced = float(m.group(1))
        found = {}
        for path in sorted(core.glob("*.qml")):
            for name, value in qml.findall(strip_qml_comments(path.read_text("utf-8"))):
                found[f"{path.name}:{name}"] = float(value)
        # The same name shape covers the ceilings EarsBudgets refuses a
        # reported budget above. They are not mirrors and must not equal the
        # default — but a ceiling BELOW what jv-ears enforces would refuse
        # the truth and silently fall back to the mirror forever, so they
        # are checked here rather than filtered out and forgotten.
        ceilings = {k: v for k, v in found.items() if "Ceiling" in k}
        mirrors = {k: v for k, v in found.items() if k not in ceilings}
        assert len(mirrors) >= 2, (
            f"expected the {label} fallback in both the element that uses it and "
            f"core/EarsBudgets.qml, found {sorted(mirrors)} — a renamed property is "
            "invisible to this gate, which is the one thing it cannot allow"
        )
        wrong = {k: v for k, v in mirrors.items() if v != enforced}
        assert not wrong, (
            f"the HUD's {label} fallback disagrees with the {source.name} that "
            f"enforces it ({enforced}): {wrong}"
        )
        low = {k: v for k, v in ceilings.items() if v <= enforced}
        assert not low, (
            f"a {label} ceiling at or below what jv-ears enforces ({enforced}) "
            f"would make the HUD refuse ears' own tuning: {low}"
        )


def test_the_plates_take_their_budgets_from_jv_ears_not_from_the_fallback():
    """The fallback must stay a fallback.

    A plate that instantiates SpeechState or MicState and forgets to bind the
    budget would run on the hand-written default forever — correct today,
    wrong the day jv-ears is retuned, and silent either way, because the HUD
    would go on drawing a perfectly plausible indicator.
    """
    hud = ROOT / "shell" / "jv-hud"
    for plate, element, prop in (
        ("StatePlate.qml", "SpeechState", "wakeWindowS"),
        ("MicPlate.qml", "MicState", "stallS"),
    ):
        text = strip_qml_comments((hud / plate).read_text("utf-8"))
        assert f"{element} {{" in text, f"{plate} no longer builds a {element}"
        assert "EarsBudgets {" in text, (
            f"{plate} builds a {element} but no EarsBudgets, so its `{prop}` is "
            "whatever the HUD guessed rather than what jv-ears reports"
        )
        assert re.search(rf"^\s*{prop}\s*:\s*\w+\.\w+\.{prop}\s*$", text, re.M), (
            f"{plate} never binds `{prop}` to the EarsBudgets it built"
        )


# --- A20: an element cannot read a topic nothing subscribes to -------------

# Every way a core/ element can ask the bus about a topic. Each one takes the
# topic as a literal string, which is what makes this checkable at all.
TOPIC_READS = re.compile(r"\b(?:latest|latestFrom|publishersOf)\(\s*\"([^\"]+)\"")

# The bridge's own list, read out of the source rather than imported: this
# gate has to run in CI's bare checkout, where no service is installed.
BRIDGE_TOPICS = re.compile(r"DEFAULT_TOPICS: Sequence\[str\] = \(([^)]*)\)", re.S)


def test_every_topic_the_hud_reads_is_one_the_bridge_subscribes_to():
    """The HUD only ever sees what jv-hud-bridge subscribed to.

    An element that reads a topic missing from that list is not broken in any
    way anything would notice: it builds, it lints, its own tests pass (they
    hand it frames directly), and on the machine it simply draws nothing,
    forever, on a surface that is unmapped by design. That is the A15 failure
    mode again — the plate that never appears — arriving through the other
    end of the pipe.

    One direction only. The bridge may subscribe ahead of the element that
    will read a topic; it may not fall behind one that already does.
    """
    bridge = ROOT / "services" / "jv-hud-bridge" / "jv_hud_bridge" / "bridge.py"
    block = BRIDGE_TOPICS.search(bridge.read_text("utf-8"))
    assert block, f"cannot find DEFAULT_TOPICS in {bridge.name} — did it move or get renamed?"
    subscribed = set(re.findall(r'"([^"]+)"', block.group(1)))
    assert subscribed, "the bridge subscribes to nothing at all"

    core = ROOT / "shell" / "jv-hud" / "core"
    read = {}
    for path in sorted(core.glob("*.qml")):
        for topic in TOPIC_READS.findall(strip_qml_comments(path.read_text("utf-8"))):
            read.setdefault(topic, []).append(path.name)
    assert read, "no core/ element reads the bus at all — did the call shape change?"

    missing = {t: v for t, v in read.items() if t not in subscribed}
    assert not missing, (
        "these elements read topics jv-hud-bridge never subscribes to, so they "
        f"would draw nothing on the machine and nothing would fail: {missing}"
    )


# --- A37: bodies the HUD may carry but must not render ---------------------

# Two body fields ride the bridge because the envelope is forwarded whole,
# and neither may reach a screen. `intent.action.args` is whatever the tool
# was asked to operate on — a path, a search string, a window title — and
# `action.result.detail` is free text jv-act writes for logs. The HUD's case
# for reading action bodies at all (bridge.py) is that a registry tool name
# and a frozen error enum are VOCABULARY; these two are content, and drawing
# them would put the contents of the user's machine on a panel that is on
# top of every window.
#
# core/ only, because core/ is where a bus body is read: a plate receives
# whatever its element decided to expose and never touches an envelope.
# `detail` is an ordinary English word — HealthPlate has a row field by that
# name, built out of the health schema's own state words — so this gate is
# scoped to the half of the HUD where the name can only mean the bus field.
UNRENDERED_BODY_FIELDS = (
    ("args", "intent.action.args — whatever the tool was asked to operate on"),
    ("detail", "action.result.detail — free text for logs and debugging"),
)


def test_no_core_element_reads_the_body_fields_the_hud_only_carries():
    """A body the bridge forwards is not a body the HUD may draw.

    The gate is the field NAME anywhere in core/, not a particular read
    shape, because there are a dozen ways to reach a property in QML and
    only one of them is worth having a rule about. If an element ever needs
    a local called `args`, that is the moment to argue for it in review
    rather than the moment this test is deleted.
    """
    core = ROOT / "shell" / "jv-hud" / "core"
    for path in sorted(core.glob("*.qml")):
        text = strip_qml_comments(path.read_text("utf-8"))
        for field, what in UNRENDERED_BODY_FIELDS:
            assert not re.search(rf"\b{field}\b", text), (
                f"{path.name} names `{field}` outside a comment. That is {what}, "
                "which this pipe carries and the HUD must never render "
                "(invariant 7)."
            )


# --- A23: the blind-HUD warning must outlast every ordinary reconnect ------

# The two cadences that decide how long a healthy machine can be off the bus.
# Neither lives anywhere near LinkState, and each one is free to grow for a
# reason that has nothing to do with the HUD.
RECONNECT_CADENCES = (
    (
        "jv-hud-bridge's first retry after a link that worked dropped",
        Path("services/jv-hud-bridge/jv_hud_bridge/bridge.py"),
        re.compile(r"^FIRST_BACKOFF_S = ([\d.]+)", re.M),
        1.0,  # seconds, as written
    ),
    (
        "Bus.qml respawning the bridge process after it died",
        Path("shell/jv-hud/Bus.qml"),
        re.compile(r"^\s*id: respawn\s*\n\s*interval:\s*(\d+)", re.M),
        0.001,  # milliseconds, as written
    ),
)


def test_the_blind_warning_waits_longer_than_a_reconnect_takes():
    """A23: LinkPlate says the HUD has lost sight of the bus.

    Its whole value is that it is rare. A down link is ordinary — the bridge
    retries a fraction of a second after jarvisd restarts, and Quickshell
    respawns the bridge itself a couple of seconds after it crashes — so a
    warning that appeared during either would blink on every rebuild, and a
    warning that blinks is one nobody reads on the day it is real.

    The grace is therefore only correct RELATIVE to two numbers in two other
    files, neither of which has any reason to think about the HUD. Pinning
    the relation is the only way a future retune of either shows up as a
    failure here rather than as a plate that cries wolf.
    """
    link = (ROOT / "shell" / "jv-hud" / "core" / "LinkState.qml").read_text("utf-8")
    m = re.search(r"^\s*property real graceS:\s*([\d.]+)\s*$", strip_qml_comments(link), re.M)
    assert m, "cannot find `graceS` in core/LinkState.qml — a renamed grace is invisible here"
    grace = float(m.group(1))

    for label, source, pattern, scale in RECONNECT_CADENCES:
        found = pattern.search((ROOT / source).read_text("utf-8"))
        assert found, f"cannot find {label} in {source} — did it move or get renamed?"
        cadence = float(found.group(1)) * scale
        assert grace > cadence, (
            f"the HUD waits {grace}s before reporting a blind link, but {label} "
            f"takes {cadence}s — so an ordinary reconnect would put the warning "
            "on screen, which is how a real one gets ignored"
        )


# --- A26: the words and the "thinking" beside them share one window -------


def test_the_heard_line_and_the_thinking_word_time_out_together():
    """A26: HeardPlate shows what you said while Jarvis works on it.

    Both elements are making the SAME claim about the same turn — a
    question is in flight — and both stop making it when they can no longer
    see whether anyone is working. They are separate files with separate
    windows because they answer different questions, which is exactly how
    two numbers that must agree end up drifting apart in silence.

    The harmful direction is `holdS` growing past `thinkWindowS`: the
    sentence would sit there after the HUD had given up on the turn it
    belongs to, words with nothing left saying they are still live. The
    other direction is merely odd — "THINKING" with nothing under it — and
    equality is the only relation that catches a retune of either.

    Equal lengths are only half the rule, and this gate only ever checked
    that half. Two equal windows started at different instants are not one
    window: until A57 this one was timed from the transcript, which lands
    however long the ASR took after the `audio.vad speech_end` SpeechState
    times its own from, so the words outlived the word above them by exactly
    that much. The other half — both windows anchored to the same frame —
    is a behaviour and is proved where behaviour can be: HeardState's
    `anchor`, under tst_heardstate.qml, which pairs the two real elements on
    one bus and fails if the line outlives the "THINKING".
    """
    core = ROOT / "shell" / "jv-hud" / "core"
    windows = {}
    for name, prop in (("SpeechState.qml", "thinkWindowS"), ("HeardState.qml", "holdS")):
        text = strip_qml_comments((core / name).read_text("utf-8"))
        m = re.search(rf"^\s*property real {prop}:\s*([\d.]+)\s*$", text, re.M)
        assert m, f"cannot find `{prop}` in core/{name} — a renamed window is invisible here"
        windows[f"{name}:{prop}"] = float(m.group(1))
    assert len(set(windows.values())) == 1, (
        "the HUD asserts a question is in flight for two different lengths of "
        f"time: {windows}"
    )


def test_core_qmldir_registers_every_component_and_no_module_name():
    qmldir = gen.render_core_qmldir()
    assert "BusModel 1.0 BusModel.qml" in qmldir
    assert not any(l.startswith("singleton ") for l in qmldir.splitlines())
    assert not any(l.startswith("module ") for l in qmldir.splitlines())
    assert "core/qmldir" in gen.outputs(ROOT / "personality" / "theme.toml")


def test_every_core_component_on_disk_is_registered_and_vice_versa():
    core = ROOT / "shell" / "jv-hud" / "core"
    on_disk = {q.name for q in core.glob("*.qml")}
    assert on_disk == {file for _, file in gen.CORE}
    for name, file in gen.CORE:
        text = (core / file).read_text("utf-8")
        assert text.startswith("//"), f"{file} should open with a comment saying what it is"
        assert "pragma Singleton" not in text, f"{file} is a component, not a singleton"
        assert name == file[: -len(".qml")], "the type name is the file name"


def test_bus_forwards_every_function_busmodel_offers():
    """`Bus` is BusModel plus the Quickshell half, and elements see only it.

    A function added to core/BusModel.qml and not forwarded is invisible to
    every element — and invisible *quietly*: a defensive element checks
    `typeof bus.fn === "function"` and falls back to knowing nothing, so the
    HUD goes blank rather than breaking. That happened once while building
    A4. qmllint cannot catch it (the call is on an injected `var`), the
    headless tests cannot catch it (they drive a BusModel directly), so it
    is caught here.

    The two lines that take the bridge's input are not element API — that
    asymmetry is the point of the file and is listed, not guessed.
    """
    hud = ROOT / "shell" / "jv-hud"
    not_element_api = {"ingest", "applyLink", "elapsed"}
    fns = set(re.findall(r"^\s*function\s+(\w+)\(", (hud / "core" / "BusModel.qml").read_text("utf-8"), re.M))
    bus = (hud / "Bus.qml").read_text("utf-8")
    missing = sorted(f for f in fns - not_element_api if f"function {f}(" not in bus)
    assert not missing, (
        "core/BusModel.qml offers functions that Bus.qml never forwards, so no "
        "element can reach them: " + ", ".join(missing)
    )


def test_core_imports_nothing_but_qtquick():
    """shell/jv-hud/core is the half that headless QML tests can load.

    Importing a directory resolves every type its qmldir lists, so ONE
    Quickshell import anywhere in core/ makes the whole directory
    unimportable to qmltestrunner — quickshell links its QML plugin into its
    own binary. That would silently take the HUD's only QML tests with it,
    so it fails here instead, loudly.
    """
    allowed = {"QtQuick"}
    offenders = []
    for qml in sorted((ROOT / "shell" / "jv-hud" / "core").rglob("*.qml")):
        for n, line in enumerate(qml.read_text("utf-8").splitlines(), 1):
            m = re.match(r"\s*import\s+(\S+)", line)
            if m and m.group(1) not in allowed:
                offenders.append(f"{qml.relative_to(ROOT)}:{n}: {line.strip()}")
    assert not offenders, (
        "core/ may import only QtQuick, or the headless tests stop running:\n"
        + "\n".join(offenders)
    )


# --- validation: a bad token must never reach a screen ---------------------


@pytest.mark.parametrize(
    "bad",
    [
        'ground = "#0c1116"',  # lowercase hex: two spellings of one colour
        'ground = "#0C111"',  # too short
        'ground = "0C1116"',  # no hash
        'ground = "rebeccapurple"',  # named colours are not tokens
        "ground = 12",  # not a colour at all
    ],
)
def test_palette_entries_must_be_uppercase_six_digit_hex(bad):
    text = MINIMAL.replace('ground = "#0C1116"', bad)
    with pytest.raises(gen.ThemeError):
        gen.load_tokens(text)


def test_missing_required_token_is_an_error():
    text = MINIMAL.replace('ember = "#F0714A"', "")
    with pytest.raises(gen.ThemeError, match="ember"):
        gen.load_tokens(text)


def test_unknown_section_is_an_error_not_a_silent_drop():
    with pytest.raises(gen.ThemeError, match="pallette"):
        gen.load_tokens(MINIMAL + '\n[pallette]\nx = "#000000"\n')


def test_key_must_be_snake_case():
    with pytest.raises(gen.ThemeError, match="groundDeep"):
        gen.load_tokens(MINIMAL.replace("ground_deep", "groundDeep"))


def test_nested_tables_are_rejected():
    with pytest.raises(gen.ThemeError):
        gen.load_tokens(MINIMAL + '\n[motion.sub]\nx = 1\n')


# --- the committed output, and the repo's own tokens -----------------------


def test_committed_theme_qml_matches_personality_theme_toml():
    """`--check` is the drift gate; it also runs inside the jv-hud build."""
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "gen_theme_qml.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_repo_theme_toml_is_valid_and_carries_the_section_set():
    tokens = gen.load_tokens((ROOT / "personality" / "theme.toml").read_text("utf-8"))
    assert set(tokens) == set(gen.SECTIONS)


def test_palette_still_agrees_with_the_blueprint_dark_tokens():
    """The theme is the blueprint's §06 palette, not a lookalike of it."""
    css = html.unescape((ROOT / "docs" / "blueprint.html").read_text("utf-8"))
    dark = dict(re.findall(r"--([a-z0-9-]+):(#[0-9A-Fa-f]{6})", css.split("prefers-color-scheme")[1]))
    palette = gen.load_tokens((ROOT / "personality" / "theme.toml").read_text("utf-8"))["palette"]
    checked = 0
    for key, value in palette.items():
        var = key.replace("_", "-")
        if var in dark:
            assert value.upper() == dark[var].upper(), f"{key} drifted from --{var}"
            checked += 1
    assert checked >= 12, "expected the blueprint's dark tokens to be the palette"


def test_no_qml_file_carries_a_literal_colour():
    offenders = []
    for qml in sorted((ROOT / "shell").rglob("*.qml")):
        if qml.name == "Theme.qml":
            continue  # the generated singleton is where colour is allowed to exist
        for n, line in enumerate(qml.read_text("utf-8").splitlines(), 1):
            if re.search(r'"#[0-9A-Fa-f]{3,8}"', line):
                offenders.append(f"{qml.relative_to(ROOT)}:{n}: {line.strip()}")
    assert not offenders, "colour belongs in personality/theme.toml:\n" + "\n".join(offenders)


def test_no_qml_file_names_a_font_family_of_its_own():
    """A8, and the same rule as colour: a face is identity, so it lives in
    personality/theme.toml and reaches QML only through the generated
    singleton. `font.family: "monospace"` would render in whatever fontconfig
    picked that day — which is precisely the drift modules/fonts.nix now
    installs a declared face to prevent, and it would reintroduce it one
    binding at a time with nothing failing."""
    offenders = []
    for qml in sorted((ROOT / "shell").rglob("*.qml")):
        if qml.name == "Theme.qml":
            continue  # the generated singleton is where a family may exist
        for n, line in enumerate(qml.read_text("utf-8").splitlines(), 1):
            if line.lstrip().startswith("//"):
                continue
            if re.search(r"\bfamily\s*:", line) and not re.search(r"\bTheme\.family\w+", line):
                offenders.append(f"{qml.relative_to(ROOT)}:{n}: {line.strip()}")
    assert not offenders, (
        "a font family belongs in personality/theme.toml, reached through "
        "Theme.familySans / Theme.familyMono:\n" + "\n".join(offenders)
    )


def test_every_face_the_theme_names_is_bound_to_a_package_and_no_other():
    """A8: theme.toml has named Archivo and JetBrains Mono since A2, and for
    fifteen iterations nothing installed either — fontconfig found no such
    family and silently substituted.

    `modules/fonts.nix` reads the names out of theme.toml itself, so the two
    cannot disagree about WHICH faces are wanted; what it holds of its own is
    the binding from a name to something that provides it. That binding is
    checked at eval time by the module (a missing one throws, a spare one
    fails an assertion) — this is the same check in the one place it can run
    without nix: the `tools` CI job on a bare checkout, in a second, with a
    diff instead of a stack trace."""
    fonts_nix = (ROOT / "modules" / "fonts.nix").read_text("utf-8")
    block = re.search(r"\n  providerOf = \{\n(.*?)\n  \};\n", fonts_nix, re.S)
    assert block, "modules/fonts.nix no longer has a providerOf table to check"
    bound = set(re.findall(r'^\s*"([^"]+)"\s*=', block.group(1), re.M))

    tokens = gen.load_tokens((ROOT / "personality" / "theme.toml").read_text("utf-8"))
    named = {v for k, v in tokens["type"].items() if k.startswith("family_")}
    assert named, "theme.toml names no face at all"
    assert named == bound, (
        "personality/theme.toml and modules/fonts.nix disagree about which "
        f"faces this machine has: theme.toml names {sorted(named)}, "
        f"modules/fonts.nix provides {sorted(bound)}"
    )


def test_the_font_resolve_check_is_wired_into_the_system_build():
    """A19: `modules/fonts.nix` proves the declared faces really ANSWER —
    `fc-match` for each family and for the generic behind it, against the
    fontconfig configuration this machine will actually have — and that proof
    only happens if the check is a dependency of the system build.

    Unwiring it is the one mutation nothing else notices: the faces still
    install, the module still evaluates, every other gate stays green, and
    the check simply never runs again. CI cannot run it (it instantiates the
    system, it does not build it), so this is the cheap guard that the gate is
    still attached to something."""
    fonts_nix = (ROOT / "modules" / "fonts.nix").read_text("utf-8")
    assert re.search(r"^  resolveCheck =", fonts_nix, re.M), (
        "modules/fonts.nix no longer defines resolveCheck — the faces are "
        "installed but nothing asks fontconfig what it answers for their names"
    )
    checks = re.search(r"^  system\.checks = \[(.*?)\];", fonts_nix, re.M | re.S)
    assert checks and "resolveCheck" in checks.group(1), (
        "modules/fonts.nix defines resolveCheck but no longer puts it in "
        "system.checks, so `nixos-rebuild build` never builds it and the "
        "check passes by never running"
    )


def test_every_role_the_theme_names_has_a_fontconfig_generic_behind_it():
    """theme.toml calls the generic families the fallbacks, so a role with no
    generic behind it falls back to nothing — and the generic is also what
    the A19 resolve check ASKS for in place of the family. The module throws
    at eval for a role it cannot place; this is that check where it runs
    without nix. The other direction matters too: a generic for a role the
    theme does not name is an alias pointed at a face nobody declared."""
    fonts_nix = (ROOT / "modules" / "fonts.nix").read_text("utf-8")
    block = re.search(r"\n  genericOf = \{\n(.*?)\n  \};\n", fonts_nix, re.S)
    assert block, "modules/fonts.nix no longer has a genericOf table to check"
    roles = set(re.findall(r"^    (\w+) = \{", block.group(1), re.M))

    tokens = gen.load_tokens((ROOT / "personality" / "theme.toml").read_text("utf-8"))
    named = {k[len("family_") :] for k in tokens["type"] if k.startswith("family_")}
    assert named, "theme.toml names no face at all"
    assert named == roles, (
        "personality/theme.toml and modules/fonts.nix disagree about which "
        f"type roles exist: theme.toml names {sorted(named)}, "
        f"modules/fonts.nix places {sorted(roles)}"
    )
