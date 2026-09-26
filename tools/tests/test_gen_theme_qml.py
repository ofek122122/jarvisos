"""tools/gen_theme_qml.py — personality/theme.toml -> the HUD's Theme singleton.

Invariant 9: theme tokens are identity and live in `personality/`, versioned
next to the voice and the system prompt. The HUD must therefore never carry a
hex code of its own — it consumes a generated singleton, and these tests are
what keep that true: they check the generator, they check the committed output
is in sync with the toml, they check the toml still agrees with the blueprint's
§06 palette, and they check no QML file has grown a literal colour.
"""

from __future__ import annotations

import dataclasses
import html
import json
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
reduced_motion = false
ease_ms = 200
plate_opacity = 0.86

[geometry]
inset_px = 16
hud_corner_px = 300
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


# Every shell that consumes the tokens, as the tests below are parameterized
# over it. There are two — `jv-hud`, the corner overlay, and `jv-bar`, the top
# bar (PLAN D1) — and every claim about registration, about core/ being
# Quickshell-free and about the committed output being the toml's is the same
# claim for both. Parameterizing rather than copying is the point: the bar was
# added by extending a table, and it arrived already covered.
SHELLS = pytest.mark.parametrize(
    "shell", [pytest.param(s, id=s.name) for s in gen.SHELLS.values()]
)


def test_qmldir_registers_every_singleton_and_no_module_name():
    qmldir = gen.render_qmldir(gen.SHELLS["jv-hud"])
    assert "singleton Theme 1.0 Theme.qml" in qmldir
    assert "singleton Bus 1.0 Bus.qml" in qmldir
    # A `module` line would claim a module name Quickshell did not assign;
    # the directory import (`import "."`) needs no such line.
    assert not any(l.startswith("module ") for l in qmldir.splitlines())
    # And the bar's is its own file, listing its own types: one table for both
    # shells would register the HUD's plates into a directory where every one
    # of them is a file that does not exist.
    bar = gen.render_qmldir(gen.SHELLS["jv-bar"])
    assert "singleton Niri 1.0 Niri.qml" in bar
    assert "Bus.qml" not in bar


@SHELLS
def test_every_qml_singleton_on_disk_is_registered_and_vice_versa(shell):
    """An unregistered singleton resolves to nothing at runtime and to a
    confusing qmllint error at build time. The two must agree exactly."""
    where = ROOT / "shell" / shell.name
    on_disk = {
        q.name for q in where.glob("*.qml") if "pragma Singleton" in q.read_text("utf-8")
    }
    assert on_disk == {file for _, file in shell.singletons}
    for name, file in shell.singletons:
        assert (where / file).exists(), f"{file} is registered but missing"
        assert (where / file).read_text("utf-8").startswith(
            "//"
        ), f"{file} should open with a comment saying what it is"
        assert name == file[: -len(".qml")], "the type name is the file name"


@SHELLS
def test_qmldir_registers_every_plain_component_on_disk_and_vice_versa(shell):
    """A qmldir exposes only what it lists, so an unregistered component is
    not a type at all — and the failure reads as a typo in the USING file,
    miles from the missing line. shell.qml is exempt: it is loaded by path."""
    where = ROOT / "shell" / shell.name
    on_disk = {
        q.name
        for q in where.glob("*.qml")
        if q.name != "shell.qml" and "pragma Singleton" not in q.read_text("utf-8")
    }
    assert on_disk == {file for _, file in shell.components}
    qmldir = gen.render_qmldir(shell)
    for name, file in shell.components:
        assert f"{name} 1.0 {file}" in qmldir
        assert f"singleton {name}" not in qmldir, f"{file} is a component, not a singleton"
        assert name == file[: -len(".qml")], "the type name is the file name"


@SHELLS
def test_every_shell_gets_the_same_theme_singleton_byte_for_byte(shell):
    """Two shells, one identity (§06). They cannot SHARE the file — each is
    copied into the store on its own and `import "."` resolves inside one
    directory — so the copies are generated from one renderer instead, and
    this is what says they never diverged. A bar whose ember had drifted one
    step from the HUD's ember would look deliberate to everyone."""
    theme = (ROOT / "shell" / shell.name / "Theme.qml").read_text("utf-8")
    assert theme == (ROOT / "shell" / "jv-hud" / "Theme.qml").read_text("utf-8")


@SHELLS
def test_every_shell_gets_the_same_motion_trio_byte_for_byte(shell):
    """§06's stillness rule is ONE decision, in three processes (PLAN D18).

    `Ease` + `Motion` + `core/MotionPolicy` is the only place the rule is
    decidable — declared preference, session override, battery, fullscreen —
    and a shell that carried its own copy would answer a slightly different
    question the first time one of them was edited. They cannot share a file
    (`import "."` resolves inside one store copy), so they are generated from
    one renderer, exactly like Theme.qml, and this is what says the three
    copies are still one decision. It is also what lets ONE suite
    (shell/jv-hud/tests/tst_motionpolicy.qml) be the test for all of them."""
    for name in ("Ease.qml", "Motion.qml", "core/MotionPolicy.qml"):
        mine = (ROOT / "shell" / shell.name / name).read_text("utf-8")
        assert mine == (ROOT / "shell" / "jv-hud" / name).read_text("utf-8"), name


@SHELLS
def test_the_generated_types_are_registered_without_any_shell_naming_them(shell):
    """A fourth shell gets the tokens and the motion trio by existing.

    The generated types are not in `SINGLETONS`/`COMPONENTS`/`CORE` — the
    per-shell tables hold only what a human wrote — so the way a new shell
    ends up with a `Motion` of its own is by someone copying one, and there is
    nothing to copy. This pins that: every registry carries them, and no
    hand-written table does."""
    for table, entry in (
        (shell.singletons, ("Theme", "Theme.qml")),
        (shell.singletons, ("Motion", "Motion.qml")),
        (shell.components, ("Ease", "Ease.qml")),
        (shell.core, ("MotionPolicy", "MotionPolicy.qml")),
    ):
        assert entry in table, f"{shell.name} does not register {entry[1]}"
    hand_written = (
        gen.SINGLETONS + gen.COMPONENTS + gen.CORE
        + gen.BAR_SINGLETONS + gen.BAR_COMPONENTS + gen.BAR_CORE
        + gen.NOTIFY_SINGLETONS + gen.NOTIFY_COMPONENTS + gen.NOTIFY_CORE
    )
    generated = gen.GENERATED_SINGLETONS + gen.GENERATED_COMPONENTS + gen.GENERATED_CORE
    assert not set(hand_written) & set(generated), (
        "a shell's own table names a type this script generates for every "
        "shell: two places to edit, and one of them will be forgotten"
    )


@SHELLS
def test_a_shared_core_type_is_generated_into_exactly_the_shells_that_ask(shell):
    """The third category, between "every shell gets it" and "this shell wrote
    it" (PLAN D37).

    `MotionPolicy` is §06's stillness RULE and applies to a shell by the shell
    existing, so it is in every registry without being asked for.
    `KeyedRows` is MACHINERY — it only means anything to a shell that repeats
    over a list something replaces wholesale — so its body lives in this
    script and a shell opts in by naming it in its own `*_CORE` table. Two
    things can then come apart, and both are silent: a shell that lists a
    shared type it is not written the file for has a qmldir line pointing at
    nothing, and a renderer nobody names is dead code that still looks
    maintained. This pins the pair together at the one place they meet,
    `outputs()`.
    """
    written = gen.outputs(gen.THEME_TOML, shell)
    for name, filename in shell.core:
        if name in gen.SHARED_CORE:
            assert f"core/{filename}" in written, (
                f"{shell.name} registers the shared type {name} and is not "
                f"written core/{filename}"
            )
            assert (ROOT / "shell" / shell.name / "core" / filename).exists()


def test_every_shared_core_renderer_is_named_by_some_shell():
    """A body in SHARED_CORE that no registry lists is a file this script can
    render and nothing on disk has: dead code wearing a generated header."""
    named = {
        name
        for s in gen.SHELLS.values()
        for name, _ in s.core
    }
    assert set(gen.SHARED_CORE) <= named, (
        f"{sorted(set(gen.SHARED_CORE) - named)} is rendered by nothing that asks for it"
    )


def test_the_shells_that_share_a_core_type_share_it_byte_for_byte():
    """The same reason as the motion trio: they cannot share a FILE (`import
    "."` resolves inside one store copy), so they share a renderer, and this is
    what says the copies never drifted. Two shells with two slightly different
    answers to "are these rows the same rows" is exactly how one of them gets
    a fade that means nothing again."""
    for name, filename in sorted({e for s in gen.SHELLS.values() for e in s.core}):
        if name not in gen.SHARED_CORE:
            continue
        copies = {
            s.name: (ROOT / "shell" / s.name / "core" / filename).read_text("utf-8")
            for s in gen.SHELLS.values()
            if (name, filename) in s.core
        }
        assert len(set(copies.values())) == 1, (
            f"{filename} differs between {sorted(copies)}"
        )


def test_motion_republishes_every_duration_token_gated():
    """`Motion.<token>` is 0 while motion is suppressed; `Theme.<token>` is not.

    Which means a duration that exists in theme.toml and NOT on Motion is a
    duration an element can only reach ungated. So the properties are derived
    from the tokens rather than listed: adding `[motion] slide_ms = 90` to
    theme.toml gives every shell a gated `Motion.slideMs` with no edit here."""
    tokens = gen.load_tokens(MINIMAL.replace("ease_ms = 200", "ease_ms = 200\nslide_ms = 90"))
    qml = gen.render_motion_qml(tokens)
    assert "readonly property int easeMs: policy.ms(Theme.easeMs)" in qml
    assert "readonly property int slideMs: policy.ms(Theme.slideMs)" in qml
    # …and nothing that is not a duration: `reduced_motion` is the preference
    # the policy CONSUMES, not a number anything animates for.
    assert "reducedMotion: policy.ms" not in qml
    assert "plateOpacity" not in qml


def test_one_environment_variable_stills_the_whole_desktop():
    """Three shells draw one desktop. A session override that reached the HUD's
    corner while the bar and the toasts kept moving would be a preference half
    obeyed, which is worse than one never offered — so there is one variable,
    and every shell's Motion reads exactly it."""
    for shell in gen.SHELLS.values():
        motion = (ROOT / "shell" / shell.name / "Motion.qml").read_text("utf-8")
        assert f'Quickshell.env("{gen.MOTION_ENV}")' in motion, shell.name
    # The name is documented where a human looks for it, not only in QML.
    assert gen.MOTION_ENV in (ROOT / "personality" / "theme.toml").read_text("utf-8")
    assert gen.MOTION_ENV in (ROOT / "shell" / "jv-hud" / "README.md").read_text("utf-8")


# --- D29: a render harness's stand-in is the same file ---------------------

# The one the HUD's contact sheet stages. There are two now (PLAN D20 added the
# notification corner's), and the sweeps below run over `gen.STANDINS` so a
# third is a table entry; this name is kept for the tests whose subject is one
# particular file.
STUB_MOTION = ROOT / "tools" / "hudshots" / "stub" / "Motion.qml"
HUD_STANDIN = next(s for s in gen.STANDINS if s.shell == "jv-hud")


def qml_code(text: str) -> list[str]:
    """The lines that run, stripped: the prose is where the two are ALLOWED
    to differ (one of them has to say it is a stand-in), and the code is where
    they are not."""
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("//")
    ]


def test_the_shots_stand_in_is_the_real_motion_with_three_lines_swapped():
    """PLAN D29. `ops/ralph/hudshots.sh` stages a Motion of its own over the
    HUD's, because the shots run under plain `qml` and Quickshell links its
    QML plugin into its own binary. That stand-in was a HAND COPY — of a
    generated file, which is the exact drift this generator exists to stop one
    level down — and `test_hudshots.py` could only catch a MISSING member, not
    a stand-in that answers the question differently.

    So both are rendered from one body, and this is the claim that makes the
    sheet worth looking at: the ONLY code that differs is the import, the root
    type and where the session override comes from. Everything that decides
    whether a plate moves is the same bytes, so a shot animates — or does not
    — for the reason the running HUD would."""
    tokens = gen.load_tokens(MINIMAL)
    real = set(qml_code(gen.render_motion_qml(tokens)))
    # EVERY stand-in, not just the HUD's: the claim is about the mechanism, and
    # a second harness that wandered off the shared body would be exactly the
    # hand copy D29 removed, re-introduced one table row over.
    for standin in gen.STANDINS:
        stub = set(qml_code(gen.render_motion_qml(tokens, gen.standin_motion(standin))))
        assert real - stub == {
            "import Quickshell",
            "Singleton {",
            f'envOverride: Quickshell.env("{gen.MOTION_ENV}") || ""',
        }, standin.shell
        assert stub - real == {"QtObject {", 'envOverride: ""'}, standin.shell


def test_every_stand_in_names_the_shell_it_replaces_and_the_script_that_stages_it():
    """The prose is the only thing that differs between two stand-ins, and it is
    the only thing telling a reader which file this one is standing in for. A
    stand-in whose preface named the other harness would send whoever is
    debugging a sheet to the wrong script."""
    tokens = gen.load_tokens(MINIMAL)
    for standin in gen.STANDINS:
        text = gen.render_motion_qml(tokens, gen.standin_motion(standin))
        assert f"shell/{standin.shell}/Motion.qml" in text
        assert standin.script in text
        assert "@SHELL@" not in text and "@SCRIPT@" not in text
        # And the script it names exists and stages this exact file, so the
        # table cannot point at a harness nobody wrote.
        script = ROOT / standin.script
        assert script.exists(), standin.script
        rel = standin.dir.relative_to(ROOT).as_posix()
        assert rel in script.read_text("utf-8"), f"{standin.script} never stages {rel}"


def test_a_new_duration_token_reaches_the_shots_stand_in_too():
    """The republished durations are derived from [motion], in BOTH renderings.
    A duration that arrived in the HUD and not in the thing that photographs it
    would make every shot a picture of a shell nobody runs."""
    tokens = gen.load_tokens(MINIMAL.replace("ease_ms = 200", "ease_ms = 200\nslide_ms = 90"))
    for standin in gen.STANDINS:
        stub = gen.render_motion_qml(tokens, gen.standin_motion(standin))
        assert "readonly property int slideMs: policy.ms(Theme.slideMs)" in stub, standin.shell


def test_the_committed_stand_in_is_what_the_generator_renders():
    """The same drift gate the shells get, for the file that is not a shell's.
    `--check` (below) covers it too; this one names it, so a stale stand-in
    fails as itself rather than as a line in a list."""
    rendered = gen.stub_outputs(ROOT / "personality" / "theme.toml")
    assert set(rendered) == {s.dir / "Motion.qml" for s in gen.STANDINS}
    for path, text in rendered.items():
        assert path.exists(), f"{path} is generated and not committed"
        assert text == path.read_text("utf-8"), path


def test_the_stand_in_imports_no_quickshell_at_all():
    """The whole reason it exists: ONE Quickshell import anywhere in the staged
    tree makes the entire directory unimportable to every engine but
    quickshell's own, and the shots do not have that engine."""
    for standin in gen.STANDINS:
        text = (standin.dir / "Motion.qml").read_text("utf-8")
        # In the CODE. The comments name Quickshell freely, and have to: a
        # reader who does not know why this file is here will delete it.
        assert not [line for line in qml_code(text) if "Quickshell" in line], standin.shell
        assert "DO NOT EDIT" in text, "a stand-in nobody knows is generated gets edited"


def test_a_build_sandbox_is_never_asked_for_the_stand_in(tmp_path):
    """`pkgs/jv-hud` runs this generator with `--out-dir .` inside a sandbox
    that holds ONE shell's tree and no tools/ at all. The stand-in's path is
    absolute — `STUB_DIR` is derived from this script's own location — so a
    sandbox run that emitted it would write outside the sandbox, or fail the
    build outright when the script's directory is a read-only store path. A
    `--out-dir` run emits the shell's six files and touches nothing else.

    The theme here is deliberately NOT the repo's: with the committed tokens
    the stand-in would render byte-identical and the write would be skipped as
    a no-op, so this test would pass while the guard was gone. One changed
    duration is what makes the difference observable."""
    theme = tmp_path / "theme.toml"
    theme.write_text(MINIMAL.replace("ease_ms = 200", "ease_ms = 201"), "utf-8")
    out = tmp_path / "shell"
    # Every stand-in, because every one of them is a shell somebody builds:
    # pkgs/jv-notify runs this the same way pkgs/jv-hud does (PLAN D20).
    for standin in gen.STANDINS:
        path = standin.dir / "Motion.qml"
        before = path.read_bytes()
        try:
            rc = gen.main(
                ["--shell", standin.shell, "--theme", str(theme), "--out-dir", str(out)]
            )
            after = path.read_bytes()
        finally:
            # Put the checkout back before asserting anything: a failing test
            # that leaves a generated file rewritten is a failure that spreads.
            path.write_bytes(before)
        assert rc == 0
        assert after == before, f"a --out-dir run wrote {path}, outside its sandbox"
        written = sorted(str(q.relative_to(out)) for q in out.rglob("*") if q.is_file())
        assert written == sorted(gen.outputs(theme, gen.SHELLS[standin.shell]))
        for q in sorted(out.rglob("*"), key=lambda q: -len(q.parts)):
            q.unlink() if q.is_file() else q.rmdir()


def test_the_stand_in_goes_out_with_the_shell_it_stands_in_for(tmp_path, monkeypatch):
    """WHICH shell carries the stand-in is a coupling, and it was stated only in
    a comment. A mutation sweep found it ungraded: pointing `STUB_SHELL` at
    jv-bar survived every test above, because a repo-root `--check` names all
    three shells and so kept rendering the stand-in either way. What it would
    have broken is the run a person actually makes after touching the HUD —
    `--shell jv-hud` — which would have rewritten the HUD's Motion and left the
    sheet's behind, the exact drift D29 closed, reopened one level up.

    Both halves are the claim. A shell's run emits its own, because that is the
    file it stands in for; it does not emit another shell's, because a stand-in
    rewritten by a run that has nothing to do with it is a surprise in someone
    else's diff. Patching the two output roots keeps this out of the checkout
    entirely.

    There used to be a third half — jv-bar, which carried no stand-in at all and
    so had to write none of them. D13 gave it one, so every shell carries one
    now and the "none" case has no example left. What is checked instead is the
    count: three harnesses for three shells, so a fourth stand-in is a
    deliberate edit here rather than a table that grew unnoticed.
    """
    assert {s.shell for s in gen.STANDINS} == set(gen.SHELLS), (
        "every shell this generator writes is photographed by a harness that "
        "stages a stand-in Motion over it, and the table no longer says so"
    )
    monkeypatch.setattr(gen, "SHELL_DIR", tmp_path / "shell")
    moved = tuple(
        dataclasses.replace(s, dir=tmp_path / "standin" / s.shell) for s in gen.STANDINS
    )
    monkeypatch.setattr(gen, "STANDINS", moved)
    theme = tmp_path / "theme.toml"
    theme.write_text(MINIMAL, "utf-8")

    # Each shell writes its own stand-in and nobody else's.
    for mine in moved:
        assert gen.main(["--shell", mine.shell, "--theme", str(theme)]) == 0
        assert (mine.dir / "Motion.qml").read_text("utf-8") == gen.render_motion_qml(
            gen.load_tokens(MINIMAL), gen.standin_motion(mine)
        )
        for other in moved:
            if other.shell != mine.shell:
                assert not (other.dir / "Motion.qml").exists(), (
                    f"{mine.shell}'s run wrote {other.shell}'s stand-in"
                )
        (mine.dir / "Motion.qml").unlink()


# Every QML animation type. If one of these appears in a shell's file, that
# file is capable of moving the screen, and §06 says something has to be able
# to stop it.
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


@SHELLS
def test_nothing_animates_without_going_through_motion(shell):
    """§06: motion is off with prefers-reduced-motion, on battery, and under
    a fullscreen window. A9's rule keeps logic testable; this one keeps the
    OFF switch reachable — an element that hand-rolls an animation without
    consulting `Motion` would keep breathing after a human asked it to stop,
    and nothing else in the build would notice.

    Files under core/ cannot reference Motion (it is a Quickshell singleton),
    which is exactly right: core/ is logic, and logic does not animate.

    Every shell, since D18: before it, the notifier had this test in its own
    weaker form (its one fade was gated on `Theme.reducedMotion`, which
    honours the versioned preference and neither the session override nor the
    machine), and the bar had no animation to test because it had no way to
    make one. One `Motion` each, generated, means one claim for all three.
    """
    root = ROOT / "shell" / shell.name
    offenders = []
    for qml in sorted(root.rglob("*.qml")):
        if qml.is_relative_to(root / "tests"):
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


# --- B89: a plate draws every word its element can say --------------------

# The convention this gate is written against: an element that decides
# between a CLOSED set of words calls the result `state`, and writes it as a
# block. `core/MicState.qml` and `core/SpeechState.qml` both do; the
# one-line string properties elsewhere in `core/` (`ActionState.tool`,
# `HeardState.text`, `GuardState.verdict`) pass free text off the bus
# through and have no word set to cover.
STATE_BLOCK = re.compile(r"^  readonly property string state: \{$", re.M)

# `typeof x === "number"` is a JavaScript type name, not something the HUD
# ever puts on a screen. It is the one kind of literal that appears in these
# blocks without being a word the element can return.
TYPEOF_LITERAL = re.compile(r'typeof\s[^=!]*[=!]==\s*"([^"]*)"')

# What counts as the plate NAMING a word: backticks or double quotes. Not a
# bare occurrence — `live` is in the first line of MicPlate.qml as part of
# "the live-microphone indicator", and a gate a passing sentence satisfies
# is a gate that fires on nothing. The point is a decision written where
# the next author will read it, and the repo already spells a word off the
# wire that way.
def names_word(text: str, word: str) -> bool:
    return f"`{word}`" in text or f'"{word}"' in text


def strip_qml_comments(text: str) -> str:
    return re.sub(r"//[^\n]*", "", text)


def state_words(element: str) -> set[str]:
    """Every word `readonly property string state` can hand a plate."""
    found = STATE_BLOCK.search(element)
    if found is None:
        return set()
    body, depth = [], 0
    for ch in element[found.end() - 1:]:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
        body.append(ch)
    code = strip_qml_comments("".join(body))
    noise = set(TYPEOF_LITERAL.findall(code))
    return {w for w in re.findall(r'"([^"]*)"', code) if w and w not in noise}


def state_elements_of(plate: str) -> list[str]:
    """The `core/*State.qml` types a plate declares as properties of its own."""
    return re.findall(r"^  readonly property (\w+State) \w+:", plate, re.M)


def test_every_plate_names_every_word_its_state_element_can_say():
    """B89: the mapping from an element's word to what a plate draws lives in
    one ternary in the plate, and nothing asserts it covers the set.

    `MicState` decides between five words and `MicPlate` draws three of them,
    two by deliberate silence. Add a sixth tomorrow and the plate draws `MIC`
    over it: nothing goes red, because the QML suites test the ELEMENT — they
    are headless, and a plate imports Quickshell singletons a headless run
    cannot load (A56) — and the screenshot sheets only photograph the states
    somebody remembered to stage. So it is a claim about two files, asserted
    by a third thing that reads them both.

    It asks for a NAME and not for a branch, because drawing a word as
    nothing is a real decision — `off` and `unknown` are both silence on
    MicPlate, for different reasons, and both of those reasons are worth more
    on screen than a branch would be. What it will not allow is the word
    going unmentioned, which is the shape the silent failure takes.
    """
    hud = ROOT / "shell" / "jv-hud"
    checked: dict[str, str] = {}
    for child in plate_stack_children(shell_text()):
        plate = (hud / f"{child}.qml").read_text("utf-8")
        for kind in state_elements_of(plate):
            element = hud / "core" / f"{kind}.qml"
            assert element.exists(), f"{child}.qml declares a {kind} with no {element}"
            words = state_words(element.read_text("utf-8"))
            if not words:
                continue
            checked[kind] = child
            missing = sorted(w for w in words if not names_word(plate, w))
            assert not missing, (
                f"core/{kind}.qml can say {sorted(words)} and {child}.qml never "
                f"names {missing}. Whatever it draws for those words, it draws "
                f"by falling off the end of a ternary — and drawing one as "
                f"NOTHING is a decision too, so name it in the comment beside "
                f"the line and say why. A word no plate mentions is the one "
                f"that reaches a screen as the wrong word with nothing red."
            )

    # Non-vacuity, both ways. This gate finds its work by a convention — a
    # `state` block in an element a plate declares — and a convention is
    # exactly the thing a rename makes silently untrue. So: it must have
    # found some work, and every element that HAS a word set must be drawn
    # by a plate that was checked.
    assert checked, (
        "no plate in the stack declares an element with a `state` block, so "
        "this gate just passed without reading anything. Either the plates "
        "stopped declaring their elements as `readonly property <Kind> <name>:` "
        "or the elements stopped calling their word `state`"
    )
    deciders = {
        f.stem
        for f in sorted((hud / "core").glob("*State.qml"))
        if state_words(f.read_text("utf-8"))
    }
    assert deciders == set(checked), (
        f"{sorted(deciders - set(checked))} decide between words that no plate "
        f"in the stack draws, so nothing here reads them. An element whose "
        f"word set has no consumer is either dead or wired into something "
        f"this gate cannot see"
    )


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


def scan(files: list[Path], patterns: tuple[str, ...]) -> list[str]:
    hits = []
    for qml in files:
        code = strip_qml_comments(qml.read_text("utf-8"))
        for n, line in enumerate(code.splitlines(), 1):
            for pat in patterns:
                if re.search(pat, line):
                    hits.append(f"{qml.relative_to(ROOT)}:{n}: {line.strip()}")
    return hits


def test_nothing_in_the_hud_asks_for_the_keyboard():
    hits = scan(hud_qml_files(), KEYBOARD_GRABS)
    assert not hits, (
        "invariant 10: the HUD never steals focus. Taking the keyboard is a "
        "human's call and starts at `keyboardFocus`, not here:\n"
        + "\n".join(hits)
    )


def test_nothing_in_the_hud_waits_for_a_pointer_it_can_never_receive():
    hits = scan(hud_qml_files(), POINTER_SINKS)
    assert not hits, (
        "the surface's input region is empty, so these handlers can never "
        "fire — a promise the HUD cannot keep:\n" + "\n".join(hits)
    )


# --- D1: the bar is a second surface, and it is docked ---------------------
#
# Everything above is about a surface that takes no space and vanishes when it
# has nothing to say. The bar is the first thing on this machine that keeps a
# strip of every monitor whether or not anything is happening on it, which is
# the one §06 licence a new surface can talk itself into — so what it may and
# may not do is pinned here, in the same shape and for the same reason.


def bar_qml_files() -> list[Path]:
    bar = ROOT / "shell" / "jv-bar"
    return [q for q in sorted(bar.rglob("*.qml")) if not q.is_relative_to(bar / "tests")]


# The bar's version of SAFE_SURFACE. Three of the five values are identical to
# the HUD's — it cannot take the keyboard, it sits on Top and not Overlay, its
# input region is empty — and the two that differ are the definition of a bar:
# it paints its own ground, and it reserves its strip so windows tile BELOW it
# rather than under it. Written out rather than derived from the HUD's table,
# because every difference between the two surfaces is a decision someone has
# to make again on purpose.
SAFE_BAR_SURFACE = {
    "WlrLayershell.keyboardFocus": "WlrKeyboardFocus.None",
    "focusable": "false",
    "WlrLayershell.layer": "WlrLayer.Top",
    # A named layer-shell surface: `jv-bar`, so a human reading `niri msg
    # --json layers` can tell the two shells apart.
    "WlrLayershell.namespace": '"jv-bar"',
    # It reserves — the one thing the HUD never does — and it reserves EXACTLY
    # its own height. A hard-coded zone is a strip of screen nobody gets back
    # the day the type size moves.
    "exclusionMode": "ExclusionMode.Normal",
    "exclusiveZone": "surface.implicitHeight",
    # Opaque ground, because nothing is ever behind a surface that reserves
    # its own space: a translucent bar would pay for a blend of the wallpaper.
    "color": "Theme.groundDeep",
}


def test_every_bar_surface_pins_the_properties_that_make_it_safe():
    """Invariant 10 for a docked surface (PLAN D1).

    The HUD's version of this test is what caught A10; the bar needs its own
    because three of these values are deliberately not the HUD's, so a shared
    table would have to say "or" and would then be satisfied by either — which
    is exactly the check that passes on a bar that has quietly stopped
    reserving its strip, or started painting over your windows.
    """
    surfaces = 0
    for qml in bar_qml_files():
        for name, body in window_bodies(qml.read_text("utf-8")):
            surfaces += 1
            where = f"{qml.relative_to(ROOT)}'s {name}"
            for prop, value in SAFE_BAR_SURFACE.items():
                assert assigned(body, prop) == [value], (
                    f"{where} must bind `{prop}: {value}` exactly once — "
                    f"got {assigned(body, prop)}. This is invariant 10, and a "
                    f"surface that gets it wrong is wrong quietly."
                )
            mask = assigned(body, "mask")
            assert len(mask) == 1 and re.fullmatch(r"Region\s*\{\s*\}", mask[0]), (
                f"{where} must bind `mask: Region {{}}` — an EMPTY input "
                f"region. A clickable workspace would be jv-bar changing the "
                f"state of this machine, which is invariant 3's line. Got "
                f"{mask}."
            )
    assert surfaces, (
        "found no Quickshell window in shell/jv-bar — either the bar stopped "
        "mapping a surface, or this gate stopped being able to see one"
    )


def test_nothing_in_the_bar_asks_for_the_keyboard():
    hits = scan(bar_qml_files(), KEYBOARD_GRABS)
    assert not hits, (
        "invariant 10: no surface on this machine steals focus, and a bar "
        "that took the keyboard would take it from whatever you are typing "
        "into:\n" + "\n".join(hits)
    )


def test_nothing_in_the_bar_waits_for_a_pointer_it_can_never_receive():
    hits = scan(bar_qml_files(), POINTER_SINKS)
    assert not hits, (
        "the bar's input region is empty, so these handlers can never fire. "
        "This is the one place that matters most: a workspace label is the "
        "most clickable-looking thing on the desktop, and a handler here is "
        "how `mask` gets opened later 'to make it work':\n" + "\n".join(hits)
    )


# --- D2: the notification corner is a third surface, and it draws strangers'
#     words ------------------------------------------------------------------
#
# jv-notify keeps the HUD's contract exactly — no keyboard, no exclusive zone,
# no input region, unmapped when empty — so it gets the HUD's table rather than
# a third one. What is new here is WHAT it draws: every other surface on this
# machine shows something JarvisOS published, and this one shows text that
# arrived over D-Bus from any process with a session. So the checks below are
# about the two ways that goes wrong quietly.


def notify_qml_files() -> list[Path]:
    notify = ROOT / "shell" / "jv-notify"
    return [
        q for q in sorted(notify.rglob("*.qml")) if not q.is_relative_to(notify / "tests")
    ]


def test_every_notify_surface_pins_the_properties_that_make_it_safe():
    """Invariant 10 for the notification corner (PLAN D2).

    The same table as the HUD's, because it is the same promise: a surface that
    floats over every window, takes no space, takes no keyboard, and passes
    every click through. It is asserted separately only because the file set is
    different — a shell added tomorrow that nothing swept would be a surface
    nobody checked."""
    surfaces = 0
    for qml in notify_qml_files():
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
                f"region. It is also what `actionsSupported: false` is the "
                f"other half of: with no click to invoke one, a notification "
                f"action is a promise these pixels cannot keep. Got {mask}."
            )
    assert surfaces, (
        "found no Quickshell window in shell/jv-notify — either the corner "
        "stopped mapping a surface, or this gate stopped being able to see one"
    )


def test_nothing_in_the_notifier_asks_for_the_keyboard():
    hits = scan(notify_qml_files(), KEYBOARD_GRABS)
    assert not hits, (
        "invariant 10: no surface on this machine steals focus, and a toast "
        "that took the keyboard would take it from whatever you are typing "
        "into the moment a stranger's program sent one:\n" + "\n".join(hits)
    )


def test_nothing_in_the_notifier_waits_for_a_pointer_it_can_never_receive():
    hits = scan(notify_qml_files(), POINTER_SINKS)
    assert not hits, (
        "the surface's input region is empty, so these handlers can never "
        "fire. A notification action is the obvious thing to reach for here "
        "and it needs the mask opened first, which is a decision about "
        "invariant 10 and not a handler:\n" + "\n".join(hits)
    )


def test_the_notifier_declares_no_capability_its_pixels_do_not_have():
    """The honesty declaration, read off the file (PLAN D2).

    A notification daemon answers GetCapabilities, and every sender decides
    what to send from the answer. Claiming `actions` would make apps offer
    buttons on a surface whose input region is empty — the user watches an app
    hand them a choice that does nothing. Claiming `body-markup` would mean
    interpreting markup from strangers on a surface that floats over every
    window; the plates render Text.PlainText, so the claim would also be false.

    So each of these is pinned to false HERE rather than left to a default,
    and the pairing with the pixels is what this test is for: qmllint would be
    perfectly happy with `actionsSupported: true`."""
    text = strip_qml_comments(
        (ROOT / "shell" / "jv-notify" / "Notifications.qml").read_text("utf-8")
    )
    server = dict(re.findall(r"^\s*(\w+Supported)\s*:\s*(true|false)", text, re.M))
    assert server.get("bodySupported") == "true", "the plate draws the body, so it asks for one"
    for cap in (
        "actionsSupported",  # no click: the mask is empty
        "actionIconsSupported",
        "bodyMarkupSupported",  # the plates are Text.PlainText
        "bodyHyperlinksSupported",
        "bodyImagesSupported",
        "imageSupported",  # the corner draws type, not a sender's pixmap
        "inlineReplySupported",
        "persistenceSupported",  # no history, so nothing may skip a resend
    ):
        assert server.get(cap) == "false", (
            f"{cap} must be declared false until these pixels do it: "
            f"got {server.get(cap)!r}. A capability is a promise to every "
            f"process on this machine."
        )

    # And the other half of `bodyMarkupSupported: false`: every Text in this
    # shell that shows a sender's string renders it as plain text. A daemon
    # that said it does not do markup and then interpreted `<img>` anyway
    # would be rendering strangers' markup over every window.
    for qml in notify_qml_files():
        code = strip_qml_comments(qml.read_text("utf-8"))
        texts = len(re.findall(r"\bText\s*\{", code))
        plain = len(re.findall(r"textFormat\s*:\s*Text\.PlainText", code))
        assert texts == plain, (
            f"{qml.relative_to(ROOT)} has {texts} Text elements and {plain} "
            f"that pin Text.PlainText. Every string on this surface came from "
            f"a program that is not this one."
        )


def theme_tokens() -> dict[str, dict[str, object]]:
    """personality/theme.toml, through the generator's own loader."""
    return gen.load_tokens((ROOT / "personality" / "theme.toml").read_text("utf-8"))


def hud_surface_box() -> tuple[int, int]:
    """shell/jv-hud/shell.qml's surface box in px, with its WIDTH resolved.

    The width is not a literal any more (PLAN D16): it is
    `Theme.hudCornerPx`, i.e. `geometry.hud_corner_px`, because jv-bar has to
    leave exactly that much of its strip empty and cannot ask another process
    how wide it is. Every gate that measures against the HUD's box goes
    through here, so a harness copy is still pinned to the shell's box and the
    shell's box is pinned to the one declaration — and a gate that went back
    to matching a run of digits after `implicitWidth:` would be pinning a
    number the shell no longer contains, which a regex reports as `None`
    rather than as a failure.

    The height IS a literal, and that asymmetry is the point: the width is a
    declared choice about how much of the corner Jarvis takes, the height is
    the measured total of the crowded stack (tst_fit.qml), so it has no
    business in a versioned identity file.
    """
    hud = strip_qml_comments((ROOT / "shell" / "jv-hud" / "shell.qml").read_text("utf-8"))
    width = re.search(r"^\s*implicitWidth:\s*(.+)$", hud, re.M)
    height = re.search(r"^\s*implicitHeight:\s*(\d+)\s*$", hud, re.M)
    assert width and height, "shell/jv-hud/shell.qml no longer declares a fixed surface box"
    assert width.group(1).strip() == "Theme.hudCornerPx", (
        "the HUD's surface width should be the one declared corner, "
        f"`Theme.hudCornerPx`; shell.qml says {width.group(1).strip()!r}"
    )
    return int(theme_tokens()["geometry"]["hud_corner_px"]), int(height.group(1))


def test_the_hud_surface_measures_the_room_its_plates_have():
    """D66. Six plates cap their own text at a number chosen for the 300 px
    corner, and `core/PlateFit.qml` narrows that cap to the room the surface
    really has. The surface is what MEASURES the room, and this is the only
    gate that can look at it: `shell.qml` is the Quickshell half, so no QML
    engine in this repo loads it and no mutation of it can be graded. Measured
    — a mutation removing the clamp below survived every suite.

    Three things have to be true of that expression, and each of them was a
    real bug in the two hours this item took:

      · it asks the SCREEN, not only itself. A layer-shell surface anchored to
        one edge is granted the width it asks for whether or not the output is
        that wide, so `surface.width` alone is 300 px on a 256 px monitor and
        the room would come out 44 px too generous — with the difference off
        the left of the screen.
      · it CLAMPS at zero. `Math.min(...) - insetPx * 2` goes negative on a
        narrow output, PlateFit reads a negative room as "nobody has measured
        this surface", and the narrowest screen then draws the widest plate.
        That is D35's bug on the bar's row, one process over.
      · and zero still differs from unmeasured. Before the first configure
        `width` is 0, and a plate that elided in the first frame of every
        session would be hiding the news to protect a margin.

    What proves the BEHAVIOUR is `tools/hudshots/scene/Corner.qml`, which
    computes the same room for the harnesses and is driven through nine
    surface widths by `tst_fit.qml`. This gate is what keeps the two from
    drifting on the half that has no engine.
    """
    hud = strip_qml_comments((ROOT / "shell" / "jv-hud" / "shell.qml").read_text("utf-8"))
    room = re.search(r"property\s+int\s+plateRoomPx:(.*?)(?=\n\n)", hud, re.S)
    assert room, "shell/jv-hud/shell.qml no longer measures the room its plates have"
    expr = " ".join(room.group(1).split())

    assert "modelData.width" in expr, (
        "the room has to be bounded by the OUTPUT's width as well as by the "
        f"surface's own, or a narrow monitor is measured as a wide one: {expr}"
    )
    assert "Math.max(0," in expr, (
        "the room has to be clamped at zero, or a surface narrower than two "
        f"insets hands PlateFit a negative and every cap comes back: {expr}"
    )
    assert "-1" in expr and "surface.width > 0" in expr, (
        "a surface nobody has configured yet has to stay distinguishable from "
        f"one with no room to give: {expr}"
    )
    # The same inset, twice, and named rather than typed — §06 gives this
    # corner that gap at the top and the right, and the plates earn it on the
    # left for the reason the box's height already gives it to the bottom.
    assert "Theme.insetPx * 2" in expr, (
        f"the room should spend two `Theme.insetPx`, not a number: {expr}"
    )


def test_the_bar_leaves_the_corner_the_hud_draws_in():
    """Two processes, two layers, one corner — and nothing can see the clash.

    The HUD sets `ExclusionMode.Ignore`, so it is NOT pushed down by the bar:
    its plates are drawn over the top-right of the bar's strip. Neither
    surface can detect the other (different process, different layer), so the
    only thing keeping them apart is the width the bar reserves.

    That width used to be a COPY of the HUD's box, typed into a file that
    cannot see it, and this gate was the honest floor under the copy: it read
    both and failed if the HUD outgrew the reserve. D16 removed the copy —
    both shells now read `geometry.hud_corner_px` — so what is left to check
    is that they still do, and that neither has quietly gone back to a
    number. The arithmetic is checked too, because `+ Theme.insetPx` is the
    half the token cannot carry: the HUD sits that far off the edge, so a
    reserve of the bare corner would leave a plate over the last inset.
    """
    corner, _ = hud_surface_box()
    inset = int(theme_tokens()["geometry"]["inset_px"])

    bar = strip_qml_comments((ROOT / "shell" / "jv-bar" / "shell.qml").read_text("utf-8"))
    reserve = re.search(r"property\s+int\s+hudReservePx:\s*(.+)$", bar, re.M)
    assert reserve, "shell/jv-bar/shell.qml no longer reserves the HUD's corner"
    assert reserve.group(1).strip() == "Theme.hudCornerPx + Theme.insetPx", (
        "the reserve should read as `Theme.hudCornerPx + Theme.insetPx`, so "
        "the HUD's corner and the §06 inset are both spent rather than "
        f"retyped; got {reserve.group(1).strip()!r}"
    )
    # The two are now the same token by inspection, so there is no inequality
    # left to check — what there is instead is a number worth being able to
    # read off a failure, and a sanity floor on it: a corner narrower than the
    # inset it sits in would be a HUD that is all margin.
    assert corner > inset > 0, (
        f"the HUD's corner is {corner} px and the §06 inset it sits in is "
        f"{inset} px; the bar reserves {corner + inset} px for the pair"
    )


def test_the_bars_recorded_snapshot_is_the_line_niri_really_wrote():
    """`tst_nirimodel.qml` drives the model with niri's own opening line.

    It has to be a COPY — a QML engine cannot read a file out of the
    repository — and a copy of a recording is worth having only while it is
    still the recording. The failure this prevents is the one no unit test
    written from memory can catch: `idx` that is really `index`, a `name`
    that is absent rather than null. Every one of those parses, changes
    nothing, and leaves a bar drawing no workspaces on a machine full of them.
    """
    recorded = (ROOT / "harness" / "fixtures" / "niri" / "ares-desk.jsonl").read_text("utf-8")
    lines = [l for l in recorded.splitlines() if l.strip()]
    assert len(lines) == 6, f"the recording is {len(lines)} lines; the fixture moved"

    test = (ROOT / "shell" / "jv-bar" / "tests" / "tst_nirimodel.qml").read_text("utf-8")
    snapshot = re.search(r"property string snapshot:\s*'([^']*)'", test)
    assert snapshot, "tst_nirimodel.qml no longer carries the recorded snapshot"
    assert snapshot.group(1) == lines[0], (
        "the snapshot in tst_nirimodel.qml is not harness/fixtures/niri/"
        "ares-desk.jsonl line 1 any more. One of the two was edited; the "
        "recording is the one that is evidence."
    )

    # The other five are shortened where a window title held this machine's
    # paths, so only their EVENT KIND is compared — which is the half the
    # test's claim rests on: these are the events the bar does not read, in
    # the order niri sent them.
    unread = re.findall(r"^\s*'(\{\"[A-Za-z]+\".*)'[,\s]*$", test, re.M)
    kinds = [json.loads(u) for u in unread]
    assert [list(k)[0] for k in kinds] == [list(json.loads(l))[0] for l in lines[1:]], (
        "the five unread events in tst_nirimodel.qml are no longer the five "
        "niri sent after the snapshot"
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
    (
        "capture loss window",
        Path("services/jv-ears/jv_ears/audio.py"),
        re.compile(r"^\s*LOSS_S = ([\d.]+)", re.M),
        re.compile(r"^\s*(?:readonly\s+)?property\s+real\s+(lossWindow\w*S)\s*:\s*([\d.]+)\s*$", re.M),
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
        ("MicPlate.qml", "MicState", "lossWindowS"),
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


# --- B40: the VRAM row may never be drawn on its own account ---------------


def test_the_vram_row_is_gated_on_the_rung_it_explains():
    """VramState says nothing until something is waiting on the card.

    The gate is an input (`brainOnCpu`), fed from HealthState's reading of
    jv-brain's own heartbeat, because two files deciding the same fact off the
    same topic is how they come to disagree. The cost of that shape is that
    the wiring lives in a plate, and plates cannot be tested headless — they
    import the Quickshell singletons. A HealthPlate that built a VramState and
    forgot the binding would be silent, correct-looking, and wrong in exactly
    one direction: the free-VRAM figure on screen all day, which is the
    all-day gauge §06 refuses and the reason the gate exists.

    Two claims, because either alone can rot: the gate is bound to the rung,
    and the row is drawn only while VramState says it is worth drawing.
    """
    plate = ROOT / "shell" / "jv-hud" / "HealthPlate.qml"
    text = strip_qml_comments(plate.read_text("utf-8"))
    assert "VramState {" in text, "HealthPlate no longer builds a VramState"
    assert re.search(r"^\s*brainOnCpu\s*:\s*\w+\.\w+\.llmOnCpu\s*$", text, re.M), (
        "HealthPlate builds a VramState and never binds `brainOnCpu` to the "
        "rung HealthState read, so the VRAM figure would be on screen all day"
    )
    assert re.search(r"if\s*\(\s*\w+\.vram\.reporting\s*\)", text), (
        "HealthPlate draws its vram row without asking VramState whether there "
        "is anything worth reporting"
    )


def test_the_requirement_row_is_bound_to_the_brain_that_publishes_it():
    """B46: the second row quotes jv-brain, and may not invent it.

    Same shape as the gate above and the same reason for it: the floor
    (`llm_gpu_floor_mb`) arrives on jv-brain's own heartbeat, HealthState is
    the file that owns that heartbeat and its expiry, and VramState takes the
    number as an INPUT. A plate that built the element and forgot the binding
    would draw the reading with no requirement under it — silent, correct
    looking, and a row short — and nothing headless can catch it, because
    plates import the Quickshell singletons.

    The third claim is the one that matters most on screen: the requirement is
    drawn only while VramState offers it, and VramState offers it only under a
    reading. A row that appeared on its own would put "the brain needs 5424
    MiB" in front of someone who has not been told what their card has.
    """
    plate = ROOT / "shell" / "jv-hud" / "HealthPlate.qml"
    text = strip_qml_comments(plate.read_text("utf-8"))
    assert re.search(r"^\s*gpuFloorMb\s*:\s*\w+\.\w+\.llmGpuFloorMb\s*$", text, re.M), (
        "HealthPlate builds a VramState and never binds `gpuFloorMb` to the "
        "floor HealthState read, so the reading would stand with nothing to "
        "compare it against"
    )
    assert re.search(r"if\s*\(\s*\w+\.vram\.needKnown\s*\)", text), (
        "HealthPlate draws its requirement row without asking VramState "
        "whether there is a reading to put it under"
    )


# --- A75: the drop row is the plate's own reason to appear -----------------


def test_the_drop_row_is_wired_to_the_plate_that_draws_it():
    """A75: HealthState cannot see `drops`, so HealthPlate must ask twice.

    `HealthState.reporting` is findings-or-rung and knows nothing about the
    broker's drop count — the field lives on jarvisd's heartbeat with a
    different lifetime (one period, not two) and is read by DropState. So the
    plate has two reasons to be on screen, and the one that rots silently is
    the second: a HealthPlate that built a DropState and left `shown` bound to
    HealthState alone would compose the row, never map the surface, and look
    exactly like a machine whose bus is fine. On a machine where every service
    says `ok` that is the ONLY finding there is.

    Three claims, because each can rot alone: the element is built, the row is
    drawn only while it reports, and `shown` counts it.
    """
    plate = ROOT / "shell" / "jv-hud" / "HealthPlate.qml"
    text = strip_qml_comments(plate.read_text("utf-8"))
    assert "DropState {" in text, "HealthPlate no longer builds a DropState"
    assert re.search(r"if\s*\(\s*\w+\.drops\.reporting\s*\)", text), (
        "HealthPlate draws its bus row without asking DropState whether there "
        "is anything worth reporting"
    )
    assert re.search(
        r"^\s*readonly\s+property\s+bool\s+shown\s*:.*\.drops\.reporting", text, re.M
    ), (
        "HealthPlate's `shown` does not count the drop count, so a bus "
        "shedding frames on an otherwise healthy machine would draw nothing"
    )


def test_the_drop_row_names_no_topic_and_no_subscriber():
    """A75/A77: the count is an aggregate, so the row may not attribute it.

    jarvisd sums every subscriber connection's tally into one map before
    publishing it, which means the HUD may not be the reader that lost
    anything — and the map's keys are not all topics (`_lagged`, `_ctl`). A
    row that named a key would read as "audio.vad is broken" when the fault is
    a slow consumer three processes away, and it would not fit the 300 px box
    either. So DropState renders a total and the plate quotes it verbatim: no
    key from the map may reach a screen through either file.

    Checked against the SOURCE rather than a render, because the two places
    this could go wrong are a renderer that interpolates a key and a plate
    that reaches past `line` into the frame.
    """
    for name in ("core/DropState.qml", "HealthPlate.qml"):
        text = strip_qml_comments((ROOT / "shell" / "jv-hud" / name).read_text("utf-8"))
        for key in ("_lagged", "_ctl"):
            assert key not in text, (
                f"{name} names `{key}`, one of the broker's own map keys — the "
                "count is an aggregate and the row attributes it to nobody (A77)"
            )
        assert "body.drops[" not in text, (
            f"{name} indexes into the drops map by key, which is how a topic "
            "name reaches a screen"
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


@SHELLS
def test_core_qmldir_registers_every_component_and_no_module_name(shell):
    qmldir = gen.render_core_qmldir(shell)
    assert f"# shell/{shell.name}/core" in qmldir
    assert not any(l.startswith("singleton ") for l in qmldir.splitlines())
    assert not any(l.startswith("module ") for l in qmldir.splitlines())
    assert "core/qmldir" in gen.outputs(ROOT / "personality" / "theme.toml", shell)
    # The comment has to name the table a reader must edit, and there is one
    # per shell — a generated file that sends you to the wrong table is worse
    # than one that sends you nowhere.
    assert f"{shell.registry}CORE in tools/gen_theme_qml.py" in qmldir


@SHELLS
def test_every_core_component_on_disk_is_registered_and_vice_versa(shell):
    core = ROOT / "shell" / shell.name / "core"
    on_disk = {q.name for q in core.glob("*.qml")}
    assert on_disk == {file for _, file in shell.core}
    for name, file in shell.core:
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


@SHELLS
def test_core_imports_nothing_but_qtquick(shell):
    """shell/<shell>/core is the half that headless QML tests can load.

    Importing a directory resolves every type its qmldir lists, so ONE
    Quickshell import anywhere in core/ makes the whole directory
    unimportable to qmltestrunner — quickshell links its QML plugin into its
    own binary. That would silently take this shell's only QML tests with it
    (`qmltest.sh` for the HUD, `bartest.sh` for the bar), so it fails here
    instead, loudly.
    """
    allowed = {"QtQuick"}
    offenders = []
    for qml in sorted((ROOT / "shell" / shell.name / "core").rglob("*.qml")):
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


# --- the desktop half of the same rule (D7) -----------------------------------
#
# The QML gates above say a HUD file may not carry a colour or a font family.
# The desktop is the same identity and had no such gate, and the day
# modules/theme.nix was written by hand it drifted: the terminal and the
# launcher painted text in #E6ECF0 / #9BAAB4 / #64747F, none of which is a §06
# token (#E4EAEE / #9FADB7 / #6E7E89), plus #F79070, which is not a token at
# all. Nothing failed, because nothing was asking.
#
# Every path below is a file that paints something, holds a colour, and is NOT
# allowed to be silent about it. The table is exhaustive in both directions:
# an unlisted file with a colour fails, and a listed file that no longer has
# one fails too, so an exception cannot outlive the drift it excuses.
COLOUR_EXCEPTIONS = {
    # The boot path. GUARDRAILS forbids the loop from touching modules/boot-*.nix,
    # and these four files are what those modules paint — a human has already
    # photographed this screen and has to photograph it again. Measured drift and
    # the token each colour should become: proposal R9 in
    # docs/optimization-backlog.md.
    "modules/grub-theme/theme.txt": "boot path — human review (R9)",
    "modules/grub-theme/background.svg": "boot path — human review (R9)",
    "modules/grub-theme/default.nix": "boot path — human review (R9)",
    "modules/plymouth-theme/default.nix": "boot path — human review (R9)",
    # The wallpaper WAS here ("needs a rendered look first"): its colours are
    # gradient stops and hairline strokes, and whether a vignette still reads
    # as depth once its darkest stop becomes a token is a thing to LOOK at.
    # D8 looked — resvg renders the PNG in the sandbox — and the answer was
    # that the old outer stop (#05080B) was darker than `ground_deep` itself,
    # so HUD plates read as LIGHTER than the desktop behind them. The field is
    # `ground` settling into `ground_deep` now, and the file carries no
    # literal, so its exception is gone rather than reworded.
}

HEX = re.compile(r"#[0-9A-Fa-f]{6}\b")


def _bearing_files(pattern: re.Pattern[str]) -> dict[str, list[str]]:
    """{path: [what matched in it]} for everything under modules/ + pkgs/.

    Discovered, not declared, so a new file painting a new surface is covered
    the day it is written — which is the failure these gates exist for. Comment
    lines are skipped: a comment naming the hex or the face it replaced is
    documentation, and modules/theme.nix's own header is the case in point.
    """
    found: dict[str, list[str]] = {}
    for base in ("modules", "pkgs"):
        for path in sorted((ROOT / base).rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            try:
                lines = path.read_text("utf-8").splitlines()
            except UnicodeDecodeError:
                continue  # a binary asset carries no literal to read
            hits = [
                hit
                for line in lines
                if not line.lstrip().startswith(("#", "//", "<!--", "*"))
                for hit in pattern.findall(line)
            ]
            if hits:
                found[str(path.relative_to(ROOT))] = hits
    return found


def colour_bearing_files() -> dict[str, list[str]]:
    return _bearing_files(HEX)


def test_no_nix_surface_carries_a_literal_colour_of_its_own():
    offenders = {
        path: hits for path, hits in colour_bearing_files().items() if path not in COLOUR_EXCEPTIONS
    }
    assert not offenders, "colour belongs in personality/theme.toml:\n" + "\n".join(
        f"{path}: {', '.join(sorted(set(hits)))}" for path, hits in sorted(offenders.items())
    )


def test_every_recorded_colour_exception_still_has_a_colour_in_it():
    """A stale excuse is worse than none: it reads as "known drift, being
    handled" for a file that was cleaned up months ago, and it hides the next
    literal somebody adds to it."""
    bearing = colour_bearing_files()
    stale = sorted(path for path in COLOUR_EXCEPTIONS if path not in bearing)
    assert not stale, (
        "these files no longer carry a colour, so drop them from "
        "COLOUR_EXCEPTIONS (and from R9 if that is what they were):\n" + "\n".join(stale)
    )


# The surfaces that MUST still be reaching the palette, and the fewest tokens
# each one has to be spending. The literal gate above cannot say this: it is
# satisfied by a file with no colour in it at all, so a surface that stopped
# asking theme.toml anything — because its shapes were deleted, or because
# someone moved the palette back into a `let` under another name — passes it
# silently. These two paint the whole desktop between them.
PAINTERS = {
    "modules/theme.nix": 8,
    "pkgs/jarvis-wallpaper/default.nix": 6,
    # The lock screen (PLAN D3). Eleven, because every state its indicator can
    # be in is a colour it has to name: leave one out and swaylock keeps its
    # own default there, which is off-palette by construction. The flags
    # themselves are gated in tools/tests/test_jv_lock.py.
    "pkgs/jv-lock/default.nix": 11,
}

TOKEN_CALL = re.compile(r'\btoken\s+"([a-z0-9_]+)"')
FACE_CALL = re.compile(r'\bface\s+"([a-z0-9_]+)"')


def test_every_colour_a_nix_surface_spends_is_a_token_theme_toml_defines():
    """Nix reaches the palette ONLY through `token "<name>"`, so this can be
    checked without evaluating nix — which matters, because the tools suite is
    the one that runs in a bare checkout with no nix at all. Discovered the
    same way the literal gate is: any file that spends a colour is subject to
    it, not just the two that do today."""
    palette = gen.load_tokens((ROOT / "personality" / "theme.toml").read_text("utf-8"))["palette"]
    spending = {path: sorted(set(hits)) for path, hits in _bearing_files(TOKEN_CALL).items()}

    missing = {
        path: [name for name in names if name not in palette]
        for path, names in spending.items()
        if any(name not in palette for name in names)
    }
    assert not missing, "colours [palette] does not define:\n" + "\n".join(
        f"{path}: {names}" for path, names in sorted(missing.items())
    )

    for path, least in PAINTERS.items():
        asked = spending.get(path, [])
        assert len(asked) >= least, (
            f"{path} paints a surface of this desktop and should be spending at "
            f"least {least} §06 tokens; it asks for {asked}"
        )


# Faces are identity exactly like colours (invariant 9), and a hand-spelled
# family is the same drift one field over — modules/fonts.nix installs only
# what theme.toml names, so a name written anywhere else is one nothing
# guarantees is installed, and fontconfig answers a miss with a substitute
# rather than an error. Same table shape as COLOUR_EXCEPTIONS, exhaustive in
# both directions.
FACE_EXCEPTIONS = {
    # The two files whose JOB is to name a family: the binding from a name to
    # a package, and the package that provides one and checks that the face
    # inside it really reports that name.
    "modules/fonts.nix": "providerOf — the one place a family is bound",
    "pkgs/archivo/default.nix": "provides family_sans; must name it to check it",
    # The boot path, for the same reason its colours are excepted: GUARDRAILS
    # makes it human-review, and R9 is where it gets measured.
    "modules/grub-theme/default.nix": "boot path — human review (R9)",
    "modules/grub-theme/background.svg": "boot path — human review (R9)",
    "modules/plymouth-theme/default.nix": "boot path — human review (R9)",
}


def face_bearing_files() -> dict[str, list[str]]:
    faces = {
        family
        for key, family in gen.load_tokens(
            (ROOT / "personality" / "theme.toml").read_text("utf-8")
        )["type"].items()
        if key.startswith("family_")
    }
    assert faces, "theme.toml names no face at all"
    return _bearing_files(re.compile("|".join(re.escape(f) for f in sorted(faces))))


def test_no_nix_surface_names_a_font_family_of_its_own():
    """The mirror of test_no_qml_file_names_a_font_family_of_its_own, one level
    out: a GTK `gtk-font-name`, an alacritty `family =`, or an SVG
    `font-family=` with a face spelled into it."""
    offenders = {
        path: hits for path, hits in face_bearing_files().items() if path not in FACE_EXCEPTIONS
    }
    assert not offenders, (
        "a font family belongs in personality/theme.toml, reached through "
        f'`face "<role>"`:\n'
        + "\n".join(f"{path}: {', '.join(sorted(set(hits)))}" for path, hits in sorted(offenders.items()))
    )


def test_every_recorded_face_exception_still_names_a_face():
    """A stale excuse hides the next family somebody spells into that file."""
    bearing = face_bearing_files()
    stale = sorted(path for path in FACE_EXCEPTIONS if path not in bearing)
    assert not stale, (
        "these files no longer name a font family, so drop them from "
        "FACE_EXCEPTIONS:\n" + "\n".join(stale)
    )


def test_every_face_a_nix_surface_asks_for_is_a_role_theme_toml_names():
    """`face "mono"` for a role [type] does not name throws at eval; this is
    that check where it runs without nix. Both painters set type — the desktop
    in GTK/Qt/terminal, the wallpaper in its wordmark — so both must be asking
    theme.toml rather than spelling it."""
    types = gen.load_tokens((ROOT / "personality" / "theme.toml").read_text("utf-8"))["type"]
    asking = {path: sorted(set(hits)) for path, hits in _bearing_files(FACE_CALL).items()}
    for path, roles in sorted(asking.items()):
        for role in roles:
            assert f"family_{role}" in types, (
                f'{path} asks for the face "{role}"; theme.toml names no family_{role}'
            )
    for path in PAINTERS:
        assert asking.get(path), (
            f"{path} sets type; it must ask theme.toml for the family through "
            f'`face "<role>"` rather than spelling one'
        )
