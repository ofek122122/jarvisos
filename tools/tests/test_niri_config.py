"""modules/niri.nix declares /etc/niri/config.kdl (PLAN F1).

The file it replaces, ~/.config/niri/config.kdl, carried every keybind Ofek
uses and named only one of ares' three monitors, with no position — undeclared,
so a clean-clone rebuild reproduced neither. `modules/niri.nix` writes the file
niri's own fallback search already looks for (its wiki's "Configuration:
Introduction" > Loading, and `system_config_path()` in niri 26.04's own
`src/main.rs`), built from two halves: `modules/niri/config-base.kdl`, read
in with `.text`'d verbatim, and a per-output `output { }` stanza generated
from `hosts/ares/outputs.nix` (PLAN E10/E13's own declaration, not a fourth
copy of the layout).

WHY THIS SUITE AND NOT ONLY `nixtest.sh`. Whether the GENERATED config is
valid niri syntax needs a real evaluation and a real `niri validate`, so that
half lives in `nixtest.sh` (PLAN B72's rule: a nix evaluation belongs there).
What a bare checkout with no nix CAN ask, and the thing this file exists to
ask, is the byte-for-byte claim: that `config-base.kdl` is
`modules/niri/config-orig.kdl` — a frozen, exact copy of the file this
replaces — with its trailing single-output stanza removed and its four
literal hex colours turned into the `@@TOKEN@@` markers modules/niri.nix
spends theme.toml's palette through (invariant 9 — a nix surface may not
carry a colour literal of its own; PLAN F1's own gate caught this the first
time config-base.kdl was written). Nothing else may differ: a rewrite that
dropped a comment, reworded a bind, or silently reordered `binds { }` would
still produce syntactically valid niri config and would still pass
`nixtest.sh`; only a byte comparison against the frozen original catches it.
"""

from pathlib import Path

from test_gen_theme_qml import ROOT

NIRI_DIR = ROOT / "modules" / "niri"
ORIG = NIRI_DIR / "config-orig.kdl"
BASE = NIRI_DIR / "config-base.kdl"
MODULE = ROOT / "modules" / "niri.nix"
OUTPUTS = ROOT / "hosts" / "ares" / "outputs.nix"

# The exact stanza the original file ended with — one monitor, no position,
# because it was the only output niri was ever told about. If this string
# stops appearing at the tail of ORIG, the frozen fixture is not the file
# F1 describes and every claim below is about the wrong "before".
OLD_TAIL = 'output "HDMI-A-1" {\n\tmode "2560x1440@144.006"\n}\n'

# The exact literal -> marker swaps modules/niri.nix performs, and how many
# times each must occur in the original — a count so an ACCIDENTAL extra
# occurrence (or one silently dropped) fails here rather than as a colour
# that quietly stayed a literal or a marker with no token behind it.
COLOUR_MARKERS = [
    ('"#F0714A"', '"@@EMBER@@"', 1),
    ('"#505050"', '"@@LINE@@"', 2),
    ('"#ffc87f"', '"@@WARN@@"', 1),
    ('"#9b0000"', '"@@RISK@@"', 1),
]


def test_frozen_original_ends_with_the_one_output_it_ever_declared():
    text = ORIG.read_text()
    assert text.endswith(OLD_TAIL), (
        "modules/niri/config-orig.kdl no longer ends with the single "
        f"undeclared HDMI-A-1 stanza F1 describes: tail is {text[-200:]!r}"
    )


def test_base_is_the_original_with_only_the_tail_removed_and_colours_marked():
    # Marker substitution only touches LINES THAT PAINT SOMETHING — the same
    # rule test_gen_theme_qml.py's own colour scanner uses (a `//` comment
    # naming a colour is documentation, not a literal to fix). The original
    # also uses "#505050" twice more inside two commented-out
    # `inactive-gradient` examples; those are untouched on purpose, so the
    # count below is of ACTIVE occurrences only, not of the substring anywhere
    # in the file.
    orig = ORIG.read_text()
    base = BASE.read_text()
    assert orig.endswith(OLD_TAIL)
    without_tail = orig[: -len(OLD_TAIL)]
    orig_lines = without_tail.split("\n")

    counts = {literal: 0 for literal, _marker, _count in COLOUR_MARKERS}
    out_lines = []
    for line in orig_lines:
        if line.strip().startswith("//"):
            out_lines.append(line)
            continue
        for literal, marker, _count in COLOUR_MARKERS:
            if literal in line:
                counts[literal] += line.count(literal)
                line = line.replace(literal, marker)
        out_lines.append(line)
    expected = "\n".join(out_lines)

    for literal, _marker, count in COLOUR_MARKERS:
        assert counts[literal] == count, (
            f"expected {literal} exactly {count} time(s) on a non-comment "
            f"line of the original, found {counts[literal]}"
        )
    assert base == expected, (
        "modules/niri/config-base.kdl differs from config-orig.kdl by more "
        "than the trailing output stanza and the four colour markers — "
        f"some bind or comment moved. base is {len(base)} bytes, "
        f"expected {len(expected)}"
    )


def test_base_still_contains_every_bind_the_original_had():
    # Every non-comment line inside `binds { }` in the original must appear,
    # unchanged, somewhere in the base — a stronger, line-order-independent
    # restatement of the byte-diff above, so a future edit to config-base.kdl
    # alone (without touching config-orig.kdl) still gets caught here too.
    orig = ORIG.read_text()
    start = orig.index("\nbinds {")
    end = orig.index("\n}", start) + len("\n}")
    orig_binds = orig[start:end]
    bind_lines = [
        line
        for line in orig_binds.splitlines()
        if line.strip() and not line.strip().startswith("//")
    ]
    assert len(bind_lines) > 50, "sanity: the original binds block looked empty"
    base = BASE.read_text()
    missing = [line for line in bind_lines if line not in base]
    assert not missing, f"config-base.kdl dropped bind line(s): {missing!r}"


def test_module_reads_config_base_and_hosts_ares_outputs():
    text = MODULE.read_text()
    assert "config-base.kdl" in text
    assert "../hosts/ares/outputs.nix" in text


def test_module_never_hardcodes_a_second_monitor_list():
    # F1's whole point is that the layout is declared ONCE (hosts/ares/
    # outputs.nix) and spent here, not re-typed as a second `output { }` list
    # inside the module the way the old file's single stanza was.
    text = MODULE.read_text()
    assert 'output "HDMI-A-1"' not in text
    assert 'output "DP-1"' not in text
    assert 'output "DP-2"' not in text


def test_module_builds_one_stanza_per_declared_output():
    text = MODULE.read_text()
    assert "outputStanza" in text
    assert "o.name" in text and "o.width" in text and "o.height" in text
    assert "o.refresh" in text and "o.x" in text and "o.y" in text


def test_every_marker_in_base_is_spent_by_the_module_from_a_real_token():
    base = BASE.read_text()
    module = MODULE.read_text()
    theme = (ROOT / "personality" / "theme.toml").read_text()
    for _literal, marker, _count in COLOUR_MARKERS:
        name = marker.strip('"@')
        assert marker in base, f"config-base.kdl no longer carries {marker}"
        assert marker in module, f"modules/niri.nix no longer substitutes {marker}"
        token = name.lower()
        assert f'token "{token}"' in module, (
            f"modules/niri.nix substitutes {marker} but does not spend "
            f'token "{token}"'
        )
        assert f"\n{token} = " in theme, (
            f'personality/theme.toml has no palette entry for "{token}"'
        )
