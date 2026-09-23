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


def test_qmldir_registers_the_singleton_and_no_module_name():
    qmldir = gen.render_qmldir()
    assert "singleton Theme 1.0 Theme.qml" in qmldir
    # A `module` line would claim a module name Quickshell did not assign;
    # the directory import (`import "."`) needs no such line.
    assert not any(l.startswith("module ") for l in qmldir.splitlines())


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
