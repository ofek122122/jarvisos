"""The load gate loads the shipped shells, or it is a green light on nothing.

`ops/ralph/shellload.sh` starts all three shells under a real quickshell on a
headless compositor and refuses a run whose QML threw (PLAN D41). Its whole
value over the three shot harnesses is that NOTHING is staged: no stub
singleton, no rebuilt stack, no second copy of `shell.qml` — the binary it runs
is the one a `nixos-rebuild switch` would install. The obvious way to make a
stubborn run go green is to stage a file, and every picture would still look
perfect afterwards.

These are the gates on that, plus the ones that would make the run be about a
machine nobody described: the wrong number of monitors, a shell missing from the
list, a session bus shared with the user's own desktop.

The claims that need a compositor are NOT here — they are the gate itself, and
it is a step in `verify.sh` (25 s) precisely so they run. What IS here is
everything that would make that step assert nothing while still exiting 0.
"""

import ast
import json
import re
import sys
from pathlib import Path

import pytest

from test_gen_theme_qml import (
    ROOT,
    hud_min_screen_height,
    hud_surface_box,
    strip_qml_comments,
    theme_tokens,
)

sys.path.insert(0, str(ROOT / "tools" / "shellload"))
import shells  # noqa: E402

sys.path.insert(0, str(ROOT / "tools" / "hudscreens"))
import sheet  # noqa: E402

sys.path.insert(0, str(ROOT / "tools"))
import dependents  # noqa: E402
import qmlerrors  # noqa: E402

SCRIPT = ROOT / "ops" / "ralph" / "shellload.sh"
DRIVER = ROOT / "tools" / "shellload" / "load.py"


def script_text() -> str:
    return SCRIPT.read_text("utf-8")


def executed_lines() -> list[str]:
    """Every line of the gate that is not a comment or blank.

    The same reading `test_hudscreens.py` takes of its own harness: a rule
    about what a script may not DO has to be a rule about what it runs, or the
    prose explaining the rule trips it.
    """
    return [
        line
        for line in script_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


# ------------------------------------------------------- nothing is staged


def test_the_gate_loads_the_shipped_binaries_and_stages_nothing():
    """The one claim this gate has over `hudshots.sh`, `barshots.sh` and
    `notifyshots.sh`, all three of which stage a copy of the shell and delete
    `shell.qml` from it because ShellRoot cannot resolve outside quickshell.
    This one loads the store path `nix build` produced, so a `cp` out of the
    working tree — the natural fix for a stubborn run — would quietly turn it
    into a gate on a file nobody ships.

    Blunt on purpose: the string `shell/` may not appear in any line this
    script executes. `tools/shellload/shells.py` holds the three roots, which
    is why the scan can still name a file a reader can open.
    """
    offenders = [line for line in executed_lines() if "shell/" in line]
    assert offenders == [], offenders
    assert "cp " not in "\n".join(executed_lines())


def test_every_shell_is_realized_from_the_flake_and_nothing_else():
    """`nix build $root#<attr>` is the only way a binary enters this run. A
    path assembled by hand would be a shell this flake does not declare."""
    assert 'nix build "$root#$attr"' in script_text()
    for shell in shells.SHELLS:
        assert (ROOT / "pkgs" / shell.attr / "default.nix").is_file(), shell.attr


def test_the_driver_cannot_build_anything():
    """The loop that realizes the shells is in the script, not in `load.py`,
    so the half of this harness that MEASURES has no way to produce a binary.
    A driver that could build one could build a different one."""
    text = DRIVER.read_text("utf-8")
    assert "nix build" not in text
    assert "nix-build" not in text


# ------------------------------------------------- the shells it is about


def test_every_shell_in_the_repo_is_loaded():
    """The failure this gate exists to prevent, one level up: a fourth shell
    lands in `shell/`, nothing adds it here, and the gate goes on reporting
    that every shell loads. `shell/jv-lock` is not a Quickshell shell (it has
    no `shell.qml`) and is excluded by having asked the directory."""
    onrepo = sorted(
        p.parent.name for p in ROOT.glob("shell/*/shell.qml")
    )
    assert sorted(s.attr for s in shells.SHELLS) == onrepo, (
        f"the repo has shells {onrepo} and the gate loads "
        f"{sorted(s.attr for s in shells.SHELLS)}"
    )


def test_each_shell_names_the_directory_that_really_holds_its_shell_qml():
    """The `--prefix` the scan reports paths under. Wrong, and every fault it
    finds names a file this repository does not have — which is the difference
    between a report someone acts on and one they distrust."""
    for shell in shells.SHELLS:
        assert (ROOT / shell.root / "shell.qml").is_file(), shell.root
        assert shell.root == f"shell/{shell.attr}"


def test_the_scan_prefix_turns_a_real_quickshell_fault_into_a_repo_path():
    """Measured rather than asserted about: this is the line quickshell really
    logged when a throwing binding was injected into the bar's PanelWindow —
    a shell whose `shell.qml` nothing in this repo had ever loaded."""
    line = (
        "  WARN scene: @shell.qml[83:-1]: TypeError: Cannot read property "
        "'count' of undefined"
    )
    bar = next(s for s in shells.SHELLS if s.attr == "jv-bar")
    threw = qmlerrors.scan(line, prefix=bar.root)
    assert [t.where for t in threw] == ["shell/jv-bar/shell.qml:83"]


def test_the_environment_variable_each_binary_arrives_in_is_its_own():
    """Two shells handed over in one variable is two runs of one shell, and
    both logs would look clean."""
    names = [s.env for s in shells.SHELLS]
    assert len(set(names)) == len(names), names
    # And the script does not name any of them: it exports whichever variable
    # `shells.py` asked for, which is the same reason the roots live there.
    assert 'export "$var=' in script_text()
    for shell in shells.SHELLS:
        assert shell.env not in "\n".join(executed_lines()), shell.env


# ----------------------------------------------------------- the census


def test_every_shell_is_waited_for_before_anything_is_scanned():
    """`qmlerrors.py` over an empty file reports "nothing threw", so a harness
    that started no engine grades itself clean forever — which is why the three
    staged harnesses had to grow a census in D38. This one needs none, and the
    reason is this wait: `READY` is a line quickshell's own logger writes once
    the root component is built, so a log nobody wrote and an engine that died
    on a syntax error are both a non-zero exit before the scan."""
    text = DRIVER.read_text("utf-8")
    assert "wait_for(shells.READY" in text
    # And the wait is not optional for any engine: one `load` for the three
    # shells, one `load_blind` for the HUD's second run (PLAN D47), and one
    # wait on READY inside each. Both go through `ReadyBudget.wait` since D53,
    # which is the only place the string `shells.READY` is waited on — a second
    # one would be an engine outside the run's budget.
    assert text.count("def load(") == 1
    assert text.count("def load_blind(") == 1
    assert text.count("ready.wait(proc)") == 2
    assert text.count("wait_for(shells.READY") == 1


def test_a_shell_that_never_loads_is_a_failure_and_not_a_skip():
    """`wait_for` raises; `load` does not catch it. The one caller counts the
    failures and exits non-zero, which is the whole verdict this gate is."""
    text = DRIVER.read_text("utf-8")
    assert "raise Fail(" in text
    assert "return 1" in text


def test_the_ready_line_is_the_one_the_other_real_quickshell_gate_waits_on():
    """The only other gate in this repo that runs a real quickshell waits on
    the same string. Two harnesses waiting on two different lines would mean
    one of them was waiting on something quickshell no longer says."""
    hudscreens = (ROOT / "tools" / "hudscreens" / "shoot.py").read_text("utf-8")
    assert f'wait_for("{shells.READY}")' in hudscreens


# ------------------------------------------------------- the environment


def test_the_monitors_are_the_ones_the_screen_sheet_uses():
    """Stated in both places and held equal here, which is the third-suite
    shape invariant 1 asks for. An import instead would have made every edit
    to the screen sheet's noise floor wake this gate, and `sheet.py` is a
    declared read of a 3-minute harness."""
    assert [
        (o["name"], o["width"], o["height"], o["x"]) for o in shells.OUTPUTS
    ] == [(o["name"], o["width"], o["height"], o["x"]) for o in sheet.OUTPUTS]


def test_there_are_three_monitors_and_the_compositor_is_given_all_of_them():
    """The load-bearing part of the monitor list, and it is the count rather
    than the sizes: all three shells build one surface per
    `Quickshell.screens` entry, so a single-output run loads one delegate and
    calls it a shell. D37's fault and D32's are both per-surface."""
    assert len(shells.OUTPUTS) == 3
    config = shells.sway_config()
    for out in shells.ALL_OUTPUTS:
        assert f"output {out['name']} mode {out['width']}x{out['height']}" in config


def test_the_compositor_is_given_the_short_output_too():
    """The config and the backend have to agree with each other, and neither is
    written where the other can see it: `sway_config()` names the outputs and
    `WLR_HEADLESS_OUTPUTS` says how many the backend makes. A config naming four
    against a backend making three leaves the fourth unconfigured at whatever
    size wlroots defaults to — which is a real screen, drawn on, and not the one
    D75 added it to be."""
    line = (
        f"output {shells.SHORT['name']} mode "
        f"{shells.SHORT['width']}x{shells.SHORT['height']} "
        f"pos {shells.SHORT['x']} 0"
    )
    assert line in shells.sway_config(), f"the compositor is never told about {line!r}"
    assert "len(shells.ALL_OUTPUTS)" in script_text(), (
        "ops/ralph/shellload.sh writes its own WLR_HEADLESS_OUTPUTS instead of "
        "asking shells.py how many outputs there are"
    )
    assert not re.search(r"^export WLR_HEADLESS_OUTPUTS=\d", script_text(), re.M), (
        "ops/ralph/shellload.sh still has a literal output count in it"
    )


def test_the_short_output_sits_beside_the_monitors_and_not_over_one():
    """Every output the compositor is given needs its own place in the layout,
    or the fourth lands on top of a monitor and `check_outputs` fails on an `x`
    nobody chose. To the RIGHT of all three, which is also what keeps it out of
    every reading that is about ares."""
    edges = []
    for out in shells.ALL_OUTPUTS:
        edges.append((out["x"], out["x"] + out["width"]))
    edges.sort()
    for (_, ends), (starts, _) in zip(edges, edges[1:]):
        assert ends <= starts, edges
    assert shells.SHORT["x"] == max(o["x"] + o["width"] for o in shells.OUTPUTS)


def test_the_compositor_config_comes_from_the_one_place_that_declares_it():
    """The script may not write its own monitor list: a size that drifted
    between the two would make the checks be about a machine nobody ran."""
    assert "shells.sway_config()" in script_text()
    for out in shells.ALL_OUTPUTS:
        assert out["name"] not in "\n".join(executed_lines())


def test_the_session_bus_is_this_runs_own_and_is_never_the_users():
    """MEASURED, and the sharpest thing in this file. Without this the
    notifier reaches the user's live session bus and races the real
    notification daemon for `org.freedesktop.Notifications` — observed as
    "presumably because one is already registered". Winning that race would
    have been a test harness taking over the notifications of the desktop it
    was running inside."""
    ran = "\n".join(executed_lines())
    assert "dbus-daemon" in ran
    assert 'export DBUS_SESSION_BUS_ADDRESS="' in ran
    # Set from the daemon this run started, and from nothing else.
    assert "--print-address" in ran
    # `dbus-run-session` is the convenient wrapper and the wrong one: it
    # inherits the machine's service directories. It is named in the header
    # saying so, which is why this reads the executed lines.
    assert "dbus-run-session" not in ran


def test_the_private_bus_can_activate_nothing():
    """The other half. `dbus-run-session` inherits the machine's service
    directories, and the first version of this started four xdg portals and a
    keyring inside a gate about three QML files — none from this flake, all of
    them noise in the log this scans. A config with no `<servicedir>` can start
    nothing nobody asked for."""
    assert "<servicedir>" not in shells.DBUS_CONF
    assert "<standard_session_servicedirs" not in shells.DBUS_CONF
    assert "<type>session</type>" in shells.DBUS_CONF


def test_the_bus_listens_inside_the_runs_own_directory():
    conf = shells.dbus_conf("/tmp/stage/run")
    assert "<listen>unix:tmpdir=/tmp/stage/run</listen>" in conf
    assert "%(tmp)s" not in conf


def test_quickshells_colour_is_turned_off():
    """Load-bearing, exactly as in `hudscreens.sh`: quickshell colours every
    level with ANSI escapes whether or not anything is watching, and
    `\\x1b[33m` in front of `WARN` is not a prefix the scanner knows — so the
    whole gate would come back clean over a shell throwing on every frame."""
    assert "export NO_COLOR=1" in script_text()


def test_the_shells_are_told_to_use_wayland():
    """Qt picks xcb otherwise, finds no display, and the layer-shell attached
    properties quietly fail to attach — which looks like a shell that loaded
    and drew nothing."""
    assert "export QT_QPA_PLATFORM=wayland" in script_text()


# ---------------------------------------------------- the notifier's client


def test_the_one_shell_nothing_wakes_is_the_bar_and_the_reason_is_its_wrapper():
    """Two of the three are given something real to do: the notifier a D-Bus
    client, the HUD a broker and eleven frames (PLAN D43). The bar is the one
    with no cheap answer, and the reason is not a gap in imagination —
    `JV_BAR_NIRI` is `--set` into its wrapper, so its event stream cannot be
    pointed at a fake without staging the shell, which is the one thing this
    gate refuses.

    Pinned because it is the limit the header states, and a header that said
    "the bar runs blind" over a bar somebody had since woken would be the
    coverage claim nobody re-read."""
    dark = [s.attr for s in shells.SHELLS if not s.wake]
    assert dark == ["jv-bar"]
    wrapper = (ROOT / "pkgs" / "jv-bar" / "default.nix").read_text("utf-8")
    assert "--set JV_BAR_NIRI" in wrapper


def test_every_way_of_waking_a_shell_is_one_the_driver_can_carry_out():
    """`wake` names the waker rather than flagging that there is one, so a
    name nothing implements would be a shell this gate silently loaded cold.
    The driver refuses one at runtime; this refuses it at test time."""
    driver = DRIVER.read_text("utf-8")
    for shell in shells.SHELLS:
        if not shell.wake:
            continue
        assert f'shell.wake == "{shell.wake}"' in driver, shell.attr


def test_the_notification_is_sent_by_a_client_and_not_by_the_shell():
    """An external caller on purpose: a reply is a fact about the running
    daemon, where the same claim made inside the shell would be a fact about
    the QML that declares it."""
    text = DRIVER.read_text("utf-8")
    assert 'need("GDBUS_BIN")' in text
    assert "GDBUS_BIN=" in script_text()


def test_the_notification_does_not_claim_to_be_from_jarvis():
    """`Notifications.qml`'s own rule: any program can put any string in
    `app_name`, and a corner that let a stranger look like the assistant would
    hand every process on this machine the assistant's face. A test fixture is
    a stranger."""
    assert "jarvis" not in shells.NOTIFY["app_name"].lower()
    assert shells.NOTIFY["app_name"] == "jv-shellload"


def test_the_capability_check_is_the_honesty_declaration_the_shell_makes():
    """Asked through the protocol, not read out of the QML — but it has to be
    the SAME set, or the gate is checking a claim this repo does not make.
    `Notifications.qml` says every capability is false unless these pixels
    really do it; the two halves are held equal here."""
    text = (ROOT / "shell" / "jv-notify" / "Notifications.qml").read_text("utf-8")
    declared = dict(
        (m.group(1), m.group(2) == "true")
        for m in re.finditer(r"^\s{4}(\w+Supported): (true|false)$", text, re.M)
    )
    assert declared, "Notifications.qml declares no capabilities at all"
    # The spec's capability name for each flag this gate has an opinion about.
    # Not every flag quickshell offers is here — `imageSupported`,
    # `inlineReplySupported` and `persistenceSupported` have no name this gate
    # asks for — which is why the real gate is the count below.
    names = {
        "bodySupported": "body",
        "bodyMarkupSupported": "body-markup",
        "bodyHyperlinksSupported": "body-hyperlinks",
        "bodyImagesSupported": "body-images",
        "actionsSupported": "actions",
        "actionIconsSupported": "action-icons",
    }
    for flag, capability in names.items():
        assert flag in declared, flag
        want = (
            shells.CAPABILITIES_REQUIRED
            if declared[flag]
            else shells.CAPABILITIES_REFUSED
        )
        assert capability in want, (flag, declared[flag])


def test_the_shell_turns_on_exactly_one_capability_and_it_is_the_body():
    """The count, and it is the gate a mapping table cannot be. Every
    capability in that file is a thing an app would otherwise send and a human
    would never see; the two that are true are the body and the body drawn
    verbatim. A seventh flag flipping to `true` fails here and nowhere else."""
    text = (ROOT / "shell" / "jv-notify" / "Notifications.qml").read_text("utf-8")
    on = sorted(
        m.group(1)
        for m in re.finditer(r"^\s{4}(\w+Supported): true$", text, re.M)
    )
    assert on == ["bodySupported"], on
    assert set(shells.CAPABILITIES_REQUIRED) == {"body"}


def test_the_refused_capability_that_matters_most_is_refused():
    """Actions. The corner's input region is empty, so a button is a promise
    those pixels cannot keep — and a daemon that advertised one would have
    every app on this machine offering choices that do nothing (invariant
    10)."""
    assert "actions" in shells.CAPABILITIES_REFUSED
    assert "actions" not in shells.CAPABILITIES_REQUIRED


def test_the_notification_is_sent_the_way_the_spec_orders_its_arguments():
    """Eight of them, in `Notify`'s own order. A summary passed where the body
    goes would render a perfectly plausible plate."""
    args = shells.notify_args()
    assert len(args) == 8
    assert args[0] == '"jv-shellload"'
    assert args[1] == "0"  # replaces_id
    assert args[3] == f'"{shells.NOTIFY["summary"]}"'
    assert shells.NOTIFY["body"] in args[4]
    assert args[5] == "@as []"  # actions: typed, because gdbus refuses a bare []
    assert args[6] == "@a{sv} {}"  # hints


def test_a_string_with_a_quote_in_it_survives_the_gvariant_quoting():
    spec = dict(shells.NOTIFY, summary='he said "no" \\ and left')
    args = shells.notify_args(spec)
    assert args[3] == '"he said \\"no\\" \\\\ and left"'


def test_the_reply_parsers_read_what_gdbus_really_prints():
    """The two replies this gate reads, in gdbus' own GVariant text."""
    assert shells.notify_id("(uint32 7,)\n") == 7
    assert shells.capabilities("([],)\n") == []
    assert shells.capabilities("(['body'],)\n") == ["body"]
    assert shells.capabilities("(['body', 'persistence'],)\n") == [
        "body",
        "persistence",
    ]


@pytest.mark.parametrize(
    "reply", ["", "()", "(0,)", "(int32 7,)", "uint32 7"]
)
def test_a_reply_that_is_not_an_id_is_refused_rather_than_read_as_zero(reply):
    """A parser that fell back to 0 would report "the daemon accepted nothing"
    for a daemon that answered something this gate cannot read — two different
    facts, and only one of them is a bug in the shell."""
    with pytest.raises(ValueError):
        shells.notify_id(reply)


# ------------------------------------------------ did it MAP (PLAN D44)
#
# `Configuration Loaded` is quickshell saying the root component built. A
# `PanelWindow` whose layer-shell properties failed to attach gets that line
# too, so the gate asks the compositor a second question: what did this
# surface take off each monitor. These are the checks on the arithmetic and on
# the declaration behind it — the measurement itself needs a compositor and is
# the gate.


def bar_declared_height() -> str:
    """The expression `shell/jv-bar/shell.qml` sets its own height to.

    Read out of the QML rather than trusted, the way `hud_surface_box()` reads
    the HUD's box: a gate that pinned a number the shell no longer contains
    would be pinning `None`.
    """
    bar = (ROOT / "shell" / "jv-bar" / "shell.qml").read_text("utf-8")
    bar = strip_qml_comments(bar)
    found = re.search(r"^\s*implicitHeight:\s*(.+?)\s*$", bar, re.M)
    assert found, "shell/jv-bar/shell.qml no longer declares an implicitHeight"
    return found.group(1)


def test_the_strip_this_gate_expects_is_the_one_the_bar_declares():
    """The copy, and the third file that holds both ends of it equal.

    `shells.bar_strip_px()` states the bar's height in the tokens it is
    derived from, because there is nothing to import: the number the bar uses
    only exists inside a running QML engine, out of a `Theme.qml` generated
    from exactly these two tokens. This is the invariant-1 shape the repo
    already uses for `OUTPUTS` vs `sheet.OUTPUTS` — stated twice, held equal
    by a suite that reads both.

    Both ends are DERIVED, which is the part worth keeping: "one label with
    §06's padding above and below" survives a change to the type scale, and a
    gate that pinned 31 would not.
    """
    assert bar_declared_height() == "Theme.labelPx + Theme.padPx * 2", (
        "the bar's height should read as one label plus §06's padding twice; "
        f"shell.qml says {bar_declared_height()!r}, and "
        "shells.bar_strip_px() no longer derives the same thing"
    )
    tokens = theme_tokens()
    want = int(tokens["type"]["label_px"]) + int(tokens["geometry"]["pad_px"]) * 2
    assert shells.bar_strip_px(shells.theme_toml_path().read_text("utf-8")) == want


def test_the_strip_is_read_from_the_file_the_shells_theme_is_generated_from():
    """`personality/theme.toml`, and it must be the real one.

    A path that resolved to nothing would make `bar_strip_px` raise rather
    than lie, which is the right failure — but a path that resolved to a
    DIFFERENT theme file would hand the gate a plausible wrong number, and
    the bar would be measured against a strip nobody ships.
    """
    assert shells.theme_toml_path() == ROOT / "personality" / "theme.toml"
    assert shells.theme_toml_path().is_file()
    gate = next(
        g for g in dependents.DECLARED_GATES if g.script == "ops/ralph/shellload.sh"
    )
    assert "personality/theme.toml" in gate.reads


def test_exactly_one_shell_takes_space_and_it_is_the_bar():
    """The HUD and the notifier are never in anybody's way (invariant 10): a
    surface that reserved a strip would resize every window on the monitor to
    do it. The bar is the one surface that is supposed to, and it is a
    property of what a bar IS rather than a relaxation."""
    reserving = [s.attr for s in shells.SHELLS if s.reserves_top]
    assert reserving == ["jv-bar"], reserving


def test_the_usable_area_is_the_monitor_minus_the_strip_on_every_one():
    """Every monitor, not the first. The bar builds one surface per
    `Quickshell.screens` entry, so a strip reserved on one output and missing
    from the other two is exactly the per-surface fault D32 and D37 both
    were.

    Every OUTPUT since D75, which is one more than the monitors: a strip is a
    property of the bar's surface, so the short screen is owed one too, and on
    that output it is arithmetic rather than a decision — 31 px shorter than
    itself, like all the rest."""
    whole = shells.usable_areas(0)
    assert whole == {
        out["name"]: (out["width"], out["height"]) for out in shells.ALL_OUTPUTS
    }
    strip = shells.usable_areas(31)
    assert set(strip) == set(whole)
    for name, (width, height) in strip.items():
        assert (width, height) == (whole[name][0], whole[name][1] - 31), name


def test_the_shell_that_reserves_nothing_is_asked_the_same_question():
    """Zero is a real expectation and not a skip. The check the gate makes for
    the HUD and the notifier is `usable_areas(0)` — the monitors, untouched —
    so it has an answer that can be wrong, which is what makes it the control
    that turns the bar's 31 missing pixels into the BAR'S."""
    assert shells.usable_areas(0) != shells.usable_areas(
        shells.bar_strip_px(shells.theme_toml_path().read_text("utf-8"))
    )


def window_body(shell: shells.Shell) -> str:
    """This shell's own layer-shell window, from its declaration down.

    The window, not the plates inside it: all three `shell.qml` declare their
    `PanelWindow` at one indent under `Variants`, so its own properties are the
    ones two spaces further in. A `visible:` on an element deeper than that is a
    plate deciding whether it has anything to say, which is the opposite
    question.
    """
    text = (ROOT / shell.root / "shell.qml").read_text("utf-8")
    return text[text.index("    PanelWindow {") :]


def window_visibility(shell: shells.Shell) -> str | None:
    """The `visible:` binding on that window, or None if it has none."""
    found = re.findall(r"^      visible: (.+)$", window_body(shell), re.MULTILINE)
    assert len(found) <= 1, (shell.attr, found)
    return found[0] if found else None


def window_always_mapped(shell: shells.Shell) -> bool:
    """Whether that window exists for as long as the shell does.

    Absent is the shipped way of saying so — `PanelWindow.visible` defaults to
    true — and the literal is the same statement written down, so both count.
    What matters is whether the window was ever INVISIBLE, not the spelling.
    """
    gate = window_visibility(shell)
    return gate is None or gate.strip() == "true"


def window_zone(shell: shells.Shell) -> str | None:
    """The `exclusiveZone:` binding on that window, or None if it has none.

    Absent is the load-bearing case rather than an omission: `exclusiveZone`
    defaults to 0, and 0 is layer-shell for "reserve nothing". Two of the three
    shells say it that way, which is why this returns None rather than "0".
    """
    found = re.findall(
        r"^      exclusiveZone: (.+?)(?: //.*)?$", window_body(shell), re.MULTILINE
    )
    assert len(found) <= 1, (shell.attr, found)
    return found[0] if found else None


def window_declares_a_zone(shell: shells.Shell) -> bool:
    """Whether that window asks for any screen space at all.

    Spelled as the ZONE rather than as `exclusionMode`, because the two are not
    the same question and the difference is measured: the bar built with
    `ExclusionMode.Ignore` and this binding left alone STILL reserved all 31 px
    (PLAN D45). What a surface asks for is `exclusiveZone`; `exclusionMode` is
    about whose zones it is positioned around.
    """
    zone = window_zone(shell)
    return zone is not None and zone.strip() not in ("0", "-1")


def window_anchors(shell: shells.Shell) -> set[str]:
    """Which screen edges that window is anchored to."""
    body = window_body(shell)
    block = body[body.index("      anchors {") : body.index("      }")]
    return set(re.findall(r"^        (\w+): true$", block, re.MULTILINE))


# Which anchor sets sway honours an exclusive zone for: ONE edge, or an edge plus
# both perpendicular ones. `apply_exclusive` in sway matches an anchor mask
# against exactly those two shapes per edge and drops the zone otherwise — which
# is why a corner-anchored surface can declare any zone it likes and take
# nothing.
#
# EVERY ENTRY IS MEASURED, and six of the eight were not until D60 — they were
# this rule written out by hand and believed. That mattered because the list is
# the load-bearing conjunct of both tests below: a wrong entry is a
# `reserves_top` the biconditional accepts, which is this gate reporting three
# whole monitors as a PROOF that a discarded zone takes nothing. Each one is a
# run of the real gate, `ops/ralph/shellload.sh`, with `jv-notify` anchored that
# way and nothing else changed — `ExclusionMode.Normal`, `exclusiveZone: 100`,
# `visible: true`, every other shell shipped. The note against each is what the
# compositor then reported on all three monitors, against a shipped 2560x1440
# and 1920x1080. The D44 section in `tools/shellload/shells.py` is where the
# whole record lives; this is the ledger the tests read.
ZONED_ANCHORS = {
    frozenset({"top"}): "2560x1340 and 1920x980 — 100 off the height (D60)",
    frozenset({"bottom"}): "2560x1340 and 1920x980 — 100 off the height (D60)",
    frozenset({"left"}): "2460x1440 and 1820x1080 — 100 off the width (D60)",
    frozenset({"right"}): "2460x1440 and 1820x1080 — 100 off the width (D60)",
    frozenset({"top", "left", "right"}): (
        "the bar's own 31 px strip, off every monitor, on every run of this "
        "gate — the one entry a shipped shell exercises (D44)"
    ),
    frozenset({"bottom", "left", "right"}): (
        "2560x1340 and 1920x980, workspace `y: 0`, so off the bottom (D59 run B)"
    ),
    frozenset({"left", "top", "bottom"}): "2460x1440 and 1820x1080 (D60)",
    frozenset({"right", "top", "bottom"}): "2460x1440 and 1820x1080 (D60)",
}

# And the shapes whose zone the compositor was watched DISCARDING, which is the
# other direction and the one a list of accepted shapes cannot state. Same
# injection throughout: a real zone, a mapped surface, and the whole 35-second
# gate GREEN anyway.
DISCARDED_ANCHORS = {
    frozenset({"top", "right"}): "the HUD's corner — every monitor whole (D54)",
    frozenset({"bottom", "right"}): (
        "the notifier's corner, the shape that ships — every monitor whole "
        "(D59 run A)"
    ),
    frozenset({"top", "bottom", "left", "right"}): (
        "ALL FOUR EDGES, which is the shape a full-screen overlay takes and the "
        "one nobody would expect to be dropped: `apply_exclusive` compares the "
        "mask for EQUALITY against one edge or one triplet, and four edges is "
        "neither — every monitor whole (D60)"
    ),
}


def test_the_shapes_sway_zones_are_the_rule_they_claim_to_be():
    """`ZONED_ANCHORS` is sway's `apply_exclusive` written out, so it is
    generated here and compared rather than proof-read.

    Two failures this refuses, and they are different failures. A MISSING or
    misspelled entry — `{"left", "top", "bottom"}` typed as `{"left", "top"}` —
    is a shell whose zone really does come off a monitor being called a control,
    which is invariant 10 broken by a typo in a test. A SPURIOUS entry is the
    same mistake pointing the other way: a discarded zone read as a proof of
    mapping, so a bar that stopped mapping altogether keeps its green.

    The generator is the rule in eight words — one edge, or an edge plus both
    perpendiculars — and the list is 8 entries because there are four edges and
    two shapes each. What it cannot check is that sway's rule IS this rule; that
    is what the measurement against every entry is for, and this test also
    refuses an entry that carries no measurement, because an unmeasured entry
    added later would inherit the confidence of the eight that were run.

    The flake pins a sway BINARY and not a checkout, so deriving the list from
    its source is not available here — which is the whole reason these are
    measurements and not a citation."""
    perpendicular = {
        "top": {"left", "right"},
        "bottom": {"left", "right"},
        "left": {"top", "bottom"},
        "right": {"top", "bottom"},
    }
    rule = {frozenset({edge}) for edge in perpendicular} | {
        frozenset({edge} | others) for edge, others in perpendicular.items()
    }
    assert set(ZONED_ANCHORS) == rule, sorted(
        map(sorted, set(ZONED_ANCHORS) ^ rule)
    )
    assert len(rule) == 8
    for shape, measurement in ZONED_ANCHORS.items():
        assert measurement.strip(), sorted(shape)
    # And the refutations are shapes the rule really does reject, or one of the
    # two ledgers is describing a compositor the other one is not.
    assert not set(DISCARDED_ANCHORS) & rule, sorted(
        map(sorted, set(DISCARDED_ANCHORS) & rule)
    )
    for shape, measurement in DISCARDED_ANCHORS.items():
        assert measurement.strip(), sorted(shape)


def test_the_only_shell_whose_zone_is_proven_is_configured_for_it():
    """What the three zone readings are worth, as a rule rather than a
    paragraph — and every conjunct of it is a run of the real gate.

    A surface takes screen space off a monitor only when THREE things are true
    at once, and D59 is the 2x2 that separated the last two. All four cells are
    the notifier, through `ops/ralph/shellload.sh`, `ExclusionMode.Normal` and
    `exclusiveZone: 100` throughout:

      anchors           visible:                  reserved
      bottom+right      true                      nothing          (D59 run A)
      bottom+left+right true                      100 px, bottom   (D59 run B)
      bottom+left+right Notifications.anyLit      nothing          (D59 run C)
      bottom+right      Notifications.anyLit      nothing    (what ships today)

    Only the cell with both bites, and it bit to the pixel — 2560x1340 and
    1920x980 on all three monitors, workspace `y: 0`, so the 100 px really did
    come off the BOTTOM edge it is anchored to.

    SO THE TWO EARLIER ATTRIBUTIONS WERE EACH HALF RIGHT, which is what D59 was
    raised to settle. D44 watched a 100 px zone come off the notifier and put it
    down to conditional visibility; D54 watched the HUD's identical zone be
    discarded with `visible: true` set and put it down to the corner anchor. Run
    C says D44's mechanism is real (a `PanelWindow` publishes its zone at
    creation, and one declared while the window was invisible never reaches the
    compositor). Run A says D54's is real on the notifier too (a bare corner is
    neither one edge nor an edge plus both perpendiculars, so `apply_exclusive`
    drops the zone whatever its value). Neither harness was wrong about its own
    cause; each had found only one of two, and the D44 record's own error was
    narrower than either — that run had widened the anchors and did not say so,
    which run B reproduces exactly.

    So `reserves_top` is a claim about a CONFIGURATION and not about a QML
    property: this gate may call a reading a proof only for a shell that asks
    for a zone, is mapped when it asks, and is anchored in a shape sway zones.
    The bar is that shell, and the other two miss on all three counts — which is
    the point of `test_a_shell_whose_zero_is_only_a_control_asks_for_nothing`
    below, because a zero reading cannot tell you which of the three saved it.

    What this refuses is a `reserves_top` that drifted from the QML: a corner
    told to reserve a strip would have its zone discarded by the compositor and
    this gate would report three whole monitors as a PROOF that it takes
    nothing."""
    for shell in shells.SHELLS:
        reserves = (
            window_declares_a_zone(shell)
            and window_always_mapped(shell)
            and frozenset(window_anchors(shell)) in ZONED_ANCHORS
        )
        assert reserves == shell.reserves_top, (
            shell.attr,
            window_zone(shell),
            window_visibility(shell),
            sorted(window_anchors(shell)),
        )
    # And it is the bar, alone — or the rule above is a tautology over a list
    # with one kind of entry in it.
    assert [s.attr for s in shells.SHELLS if s.reserves_top] == ["jv-bar"]
    # The bar's strip is the one number this gate proves, so the QML that
    # publishes it has to be the QML that says so.
    bar = next(s for s in shells.SHELLS if s.reserves_top)
    assert window_anchors(bar) == {"top", "left", "right"}
    body = window_body(bar)
    assert "exclusionMode: ExclusionMode.Normal" in body
    assert "exclusiveZone: surface.implicitHeight" in body


def test_a_shell_whose_zero_is_only_a_control_asks_for_nothing():
    """The other two shells miss the rule above on ALL THREE counts, and that
    is defence in depth rather than a description of today's QML.

    The gate reads one number for each of them — every monitor whole, while the
    shell is up — and D59's 2x2 is the measurement that says what that number
    can and cannot see. Three separate things are keeping it at zero, the
    reading cannot tell you which, and two of the three are invisible to it
    entirely: run A and run C are both `exclusiveZone: 100` on a shipped shell
    with the expensive gate GREEN. So a zone declared on the notifier's corner
    today is a strip taken off every monitor the day somebody widens its anchors
    for a full-width toast, or drops the `visible:` gate to stop the corner
    rebuilding — and each of those is a reasonable-looking commit of its own, in
    which the 35-second gate stays green and nothing names the combination.

    Pinning all three closes that: every single-property step towards a surface
    that reserves space is a red line in a 0.1-second test, on the commit that
    takes it, and the author has to move `reserves_top` deliberately instead of
    discovering it on a monitor. Invariant 10 is the reason it is worth a red
    that a compositor would not give: the HUD and the notifier float over every
    window on this machine and their whole license to do so is that they cannot
    push one around.
    """
    for shell in shells.SHELLS:
        if shell.reserves_top:
            continue
        # It asks for nothing. The one of the three the gate CAN see, and only
        # while the other two also hold — which is why it is pinned here rather
        # than left to the run.
        assert not window_declares_a_zone(shell), (shell.attr, window_zone(shell))
        # It is not mapped unless it has something to say, so a zone it grew
        # would be published at a moment the compositor was not listening.
        assert not window_always_mapped(shell), (shell.attr, window_visibility(shell))
        # And it is anchored to a bare corner, which sway drops a zone for.
        assert frozenset(window_anchors(shell)) not in ZONED_ANCHORS, sorted(
            window_anchors(shell)
        )
        assert len(window_anchors(shell)) == 2, sorted(window_anchors(shell))
        # And its corner is one the compositor was WATCHED discarding a zone
        # for, rather than one merely absent from the list above — both of
        # these two have been through the real gate with a live 100 px zone on
        # them (D54, D59 run A), which is the only reason this loop is allowed
        # to treat an anchor shape as a reason for the zero it reads.
        assert frozenset(window_anchors(shell)) in DISCARDED_ANCHORS, sorted(
            window_anchors(shell)
        )
    # Both of them, or the loop above is a rule about an empty list.
    assert [s.attr for s in shells.SHELLS if not s.reserves_top] == [
        "jv-hud",
        "jv-notify",
    ]
    # The corners they are anchored to are the two §06 assigns them, and they
    # are different corners: two surfaces in one corner is the one arrangement
    # neither of them can detect (shell/jv-notify/shell.qml says so).
    assert window_anchors(shells.hud_shell()) == {"top", "right"}
    notify = next(s for s in shells.SHELLS if s.attr == "jv-notify")
    assert window_anchors(notify) == {"bottom", "right"}


def test_the_compositor_is_asked_over_its_own_socket():
    """`swaymsg` needs SWAYSOCK, which is a different socket from the wayland
    one and does not exist until sway has started. Without it every IPC call
    in the driver fails with "Unable to retrieve socket path" — observed, on
    the first run of this check — and a gate whose only new question cannot
    be asked is the failure this test is about."""
    lines = executed_lines()
    assert any("SWAYMSG_BIN=" in line for line in lines)
    assert any("SWAYSOCK=" in line for line in lines)
    # Out of the run's own private runtime dir, like the wayland socket above
    # it: a gate that reached the user's live compositor would be asking a
    # different session what this shell reserved.
    sock = next(line for line in lines if "SWAYSOCK=" in line)
    assert "$XDG_RUNTIME_DIR" in sock, sock


def test_the_driver_cannot_change_what_the_compositor_reports():
    """Read-only, and bluntly. `swaymsg` also EXECUTES commands — it is how
    `tools/hudscreens/shoot.py` moves a cursor and focuses a window — and a
    harness that could create a window could shrink a usable area itself. The
    only calls here are `-t <tree>` queries.
    """
    text = DRIVER.read_text("utf-8")
    calls = re.findall(r'swaymsg\(([^)]*)\)', text)
    asked = [c for c in calls if c.strip() and "*args" not in c]
    assert asked, "the driver no longer asks the compositor anything"
    for call in asked:
        assert call.strip().startswith('"-t"'), call


def test_a_shell_is_read_before_during_and_after_it_runs():
    """Three readings, and two of them are the control. A strip that was
    already missing before the bar started was not the bar's, and one that
    never came back was never a layer surface's zone at all — so a run that
    only looked while the shell was up could report a reservation made by
    something else in the session."""
    text = DRIVER.read_text("utf-8")
    whens = re.findall(r'check_zone\(shell, "(\w+)", up=(\w+)\)', text)
    triple = [("before", "False"), ("while", "True"), ("after", "False")]
    # Twice, once per run: the blind HUD (PLAN D47) is a fourth engine on the
    # same compositor, and its readings need the same two controls — more so,
    # because it is the run in which the HUD's surface really is mapped.
    assert whens == triple * 2, whens


def test_the_monitors_the_compositor_really_has_are_checked_before_any_shell():
    """The floor under everything else. `WLR_HEADLESS_OUTPUTS` and the
    `output` lines in the config are both REQUESTS; until D44 nothing read the
    answer, and a run that got one output would have loaded one delegate per
    shell, scanned one surface's worth of log and reported that all three
    shells load.

    Before any shell, because the alternative is three identical failures
    underneath the one that explains them."""
    text = DRIVER.read_text("utf-8")
    assert text.index("check_outputs()") < text.index("for shell in shells.SHELLS")
    assert '"-t", "get_outputs"' in text


# The ceiling on what one hung engine can cost, and it is a bound on a
# PATHOLOGICAL run rather than a budget (PLAN D50). Nothing here is expected to
# spend a whole timeout: the measured run is 32 s, which is the number the
# gate's price claim rests on and the one its header quotes. What this is for is
# the run where a quickshell comes up and then holds still forever — it has to
# end, be reported, and not take the afternoon with it.
ENGINE_CEILING_S = 100.0

# And what the whole run can cost if EVERY engine does that, which is four
# times the above and is asserted only to keep it four times the above: the
# engines are sequential, so a ceiling per engine is not a ceiling on the run,
# and a reader who saw only the per-engine number would be reading a third of
# the true worst case.
RUN_CEILING_S = 300.0


def engine_load_bounds() -> dict[str, float]:
    """The worst READY wait of each engine, in the order `main` starts them.

    Its own function because D53's whole claim is about this one wait: the cold
    bound belongs to whichever engine touches Qt first and to none of the rest,
    and a reader who could only see the totals below could not tell a run with
    one cold engine from a run with four.
    """
    names = [shell.attr for shell in shells.SHELLS] + [shells.HUD_BLIND_LOG]
    return {
        name: (
            shells.READY_TIMEOUT_COLD_S if i == 0 else shells.READY_WARM_CEILING_S
        )
        for i, name in enumerate(names)
    }


def engine_zone_readings() -> dict[str, int]:
    """How many times each engine asks the compositor what it reserved.

    COUNTED OFF THE DRIVER rather than written down here, because the count is
    multiplied by `MAPPED_TIMEOUT_S` below: a reading added to the run and not to
    the arithmetic is 8 s of pathological wait outside the ceiling, which is
    exactly the hole D50 found in the load wait. A number in this file would go
    stale the same way.

    Two slices, because the engines do not share code the way they share a
    compositor. `load()` runs once per entry in `shells.SHELLS`, so its readings
    are each of those engines'. The blind engine's are everything from
    `load_blind` down, which is its own three and — since D54 was measured and
    closed rather than built — no fourth.
    """
    text = DRIVER.read_text("utf-8")
    per_shell = text[text.index("def load(") : text.index("def load_blind(")]
    blind = text[text.index("def load_blind(") : text.index("def main(")]
    out = {shell.attr: per_shell.count("check_zone(shell,") for shell in shells.SHELLS}
    out[shells.HUD_BLIND_LOG] = blind.count("check_zone(shell,")
    return out


def engine_ceilings() -> dict[str, float]:
    """The worst case of every wait ONE engine of this gate can spend.

    Per engine, which is D50's repair of a test that summed the whole run into
    a single number. Two things were wrong with the sum. It broke on the next
    honest addition rather than on a cost problem — D47 took it from 136 to 148
    against a limit of 150, so the D49 relink would have read as expensive when
    it is nine seconds of waiting on a corner. And what it summed was not the
    worst case: the load wait was left out entirely, which is 30 s per engine
    of pathological wait — a quickshell that maps nothing and says nothing is
    exactly the run a ceiling exists for, and it was the one run the ceiling
    did not cover.

    Stated as an argument about ONE ENGINE because that is the claim that stays
    true as runs are added: this gate starts a fresh quickshell per reading, and
    no one of them may hang for minutes.

    And the load wait is not the same number for all four since D53. The cold
    one is paid by whichever engine the run starts first — `shells.SHELLS[0]`,
    because `main` walks that list and then runs the blind HUD — and every
    engine after it is bounded by what the run measured, whose worst case is
    `READY_WARM_CEILING_S`. That is where the blind engine's headroom came
    from: 98 s of ceiling to 80.
    """
    # Every engine pays for these: the load, and the compositor readings around
    # it (before / while / after, PLAN D44), counted off the driver so the
    # arithmetic cannot drift from the run.
    reads = engine_zone_readings()
    out = {
        name: load + shells.MAPPED_TIMEOUT_S * reads[name]
        for name, load in engine_load_bounds().items()
    }
    base = out[shells.HUD_BLIND_LOG]
    # The frames run waits for the publisher's first round and then for the
    # corner to name ten plates. Two different waits on two different numbers
    # since D52 — the publisher's is about a process starting, the corner's
    # about a cold Qt, and they were one number only because there was one
    # publisher.
    out[shells.hud_shell().attr] = (
        out[shells.hud_shell().attr]
        + shells.HUD_PUBLISH_TIMEOUT_S
        + shells.HUD_LIT_TIMEOUT_S
    )
    # And the blind run is three acts: it waits out the grace, then the socket
    # and the corner going dark again (PLAN D49), then a second publisher and
    # the corner lighting back up (PLAN D52). It is this gate's most expensive
    # engine by some way, at 80 s of 100: the headroom D53 bought is still
    # unspent, because the act D54 would have put here does not exist.
    out[shells.HUD_BLIND_LOG] = (
        base
        + shells.HUD_BLIND_TIMEOUT_S
        + shells.HUD_RELINK_BUS_TIMEOUT_S
        + shells.HUD_RELINK_TIMEOUT_S
        + shells.HUD_PUBLISH_TIMEOUT_S
        + shells.HUD_RECOVER_TIMEOUT_S
    )
    return out


def test_no_single_engine_can_hang_this_gate_for_minutes():
    """The whole argument for this being a step rather than a named command.
    Everything here is polled, and a poll with a generous timeout is how a 32 s
    gate becomes a 3-minute one — so every wait is bounded, and the bound is
    per engine (PLAN D50) because that is the claim that survives the next run
    somebody adds."""
    ceilings = engine_ceilings()
    # Every engine this gate really starts has a ceiling, and nothing else does:
    # a run added to the driver with no wait written down here is a run outside
    # this claim.
    assert sorted(ceilings) == sorted(name for name, _ in shells.scan_targets())
    for engine, worst in ceilings.items():
        assert worst <= ENGINE_CEILING_S, (engine, worst)
    assert sum(ceilings.values()) <= RUN_CEILING_S, ceilings
    assert RUN_CEILING_S <= ENGINE_CEILING_S * len(ceilings)
    assert 0 < shells.MAPPED_POLL_S <= 0.25
    # And the compositor readings the arithmetic paid for are the ones the run
    # really makes. This is the half of a ceiling that drifts silently: a reading
    # is one line, it is 8 s of worst case, and D50's bug was exactly a wait the
    # driver spent and the arithmetic did not know about.
    reads = engine_zone_readings()
    assert set(reads) == set(ceilings)
    # Three per engine — before / while / after, PLAN D44 — for all four of them.
    assert list(reads.values()) == [3] * len(reads), reads
    # And the frames go out faster than the plate that needs them goes stale,
    # or the ceiling above is spent waiting for a corner that keeps dimming.
    assert 0 < shells.HUD_ROUND_S <= 1.0


def budget_text() -> str:
    """`ReadyBudget` alone, the way `relink_text()` is one function alone: the
    rules about a derived bound are that class's, and a slice that ran on into
    `load()` would answer them with the caller."""
    text = DRIVER.read_text("utf-8")
    return text[text.index("class ReadyBudget") : text.index("def swaymsg(")]


def test_only_one_engine_of_a_run_is_given_the_cold_bound():
    """D53, and it is the arithmetic above rather than a saving.

    `READY_TIMEOUT_COLD_S` is written against a cold Qt and a cold font cache.
    That cost is paid by whichever engine touches this machine first and by
    none of the three after it — so four engines holding it put 120 s of
    un-payable wait into the run's worst case, which is a ceiling that had
    stopped describing the run. Exactly one engine may hold it now."""
    bounds = engine_load_bounds()
    cold = [
        name
        for name, worst in bounds.items()
        if worst == shells.READY_TIMEOUT_COLD_S
    ]
    assert cold == [shells.SHELLS[0].attr], cold
    # And it is the FIRST engine `main` starts, which is the only way the
    # driver could have spent it — a cold bound on engine three would be a
    # ceiling nobody could reach from a run nobody runs.
    assert list(bounds) == [s.attr for s in shells.SHELLS] + [shells.HUD_BLIND_LOG]
    # And the warm bound really is the smaller one, or the split is a rename.
    assert shells.READY_WARM_CEILING_S < shells.READY_TIMEOUT_COLD_S


def test_the_warm_bound_is_derived_from_what_this_run_measured():
    """The reason it is a function and not a fifth constant. A second static
    number would be a second guess at a cost nobody has measured; this one is
    the run's own slowest load with room on it, so a machine three times slower
    than ares gets three times the bound without anybody editing a file."""
    warm = shells.warm_ready_timeout
    # Monotone: a bound that has learned the machine is slow must not un-learn
    # it, which is also why `ReadyBudget` keeps the SLOWEST rather than the last.
    seen = [warm(x / 10) for x in range(0, 300)]
    assert seen == sorted(seen)
    # Floored, so a fast first engine cannot make the bound brittle...
    assert warm(0.0) == shells.READY_WARM_FLOOR_S
    # ...and capped, so `engine_ceilings()` has a static number to add up.
    assert warm(1e6) == shells.READY_WARM_CEILING_S
    assert shells.READY_WARM_FLOOR_S < shells.READY_WARM_CEILING_S
    # In between it is the measurement, multiplied.
    assert warm(2.0) == 2.0 * shells.READY_WARM_FACTOR
    assert shells.READY_WARM_FACTOR >= 2


def test_the_warm_bound_covers_the_load_this_gate_actually_measures():
    """The failure direction that matters: a bound that fires on a healthy run
    is a gate that gets switched off, which is the sentence the cold number was
    written under and it applies to this one too.

    Measured on ares, every engine of the run — including the first, because
    the caches are warm across runs — says `Configuration Loaded` in 0.40 s.
    The floor alone is twelve times that before the derivation adds anything."""
    measured = 0.40
    assert shells.warm_ready_timeout(measured) >= measured * 10
    # And the engine that sets the bound is covered by the bound it sets, which
    # is what makes the derivation safe: a warm load cannot exceed the cold one
    # it followed, so any first load the cap does not bind on is covered too.
    for first in [0.1, 0.4, 1.0, shells.READY_WARM_CEILING_S / shells.READY_WARM_FACTOR]:
        assert shells.warm_ready_timeout(first) > first


def test_the_ready_budget_is_one_object_for_the_whole_run():
    """"The first engine" is the whole of the distinction, so a budget built
    per shell would hand the cold number to all four again — which is the bug
    D53 is about, reintroduced by a constructor in the wrong place."""
    text = DRIVER.read_text("utf-8")
    assert text.count("ReadyBudget()") == 1
    built = text[text.index("ReadyBudget()") :]
    assert built.index("for shell in shells.SHELLS") < built.index("load_blind(stage, ready)")
    # Both runs are handed it rather than making their own.
    assert "def load(shell: shells.Shell, stage: Path, ready: ReadyBudget)" in text
    assert "def load_blind(stage: Path, ready: ReadyBudget)" in text


def test_a_warm_engine_that_runs_out_says_where_its_bound_came_from():
    """A derived bound is a worse report than a constant one unless it says so.
    `jv-bar never said 'Configuration Loaded' in 5s` over a 30 s constant sends
    a reader to the shell; over a number this run computed it has to send them
    to the measurement and to the constant that capped it, because on a slow
    enough machine the repair really is the constant."""
    budget = budget_text()
    assert "READY_WARM_CEILING_S" in budget
    assert "PLAN D53" in budget
    # And the cold engine's failure is NOT dressed up with a derivation it did
    # not have: there was nothing measured to derive it from.
    assert "if warm is None:" in budget
    assert budget.index("if warm is None:") < budget.index("raise Fail(")


# ------------------------------------------------------------- the wiring


def test_the_gate_is_planned_for_every_shell_it_loads():
    """The whole point of being a declared gate: a change to any of the three
    shells must name this command. Before D41 a change to `shell/jv-bar` named
    `qmltest.sh` and `barshots.sh`, neither of which loads `shell.qml`."""
    for shell in shells.SHELLS:
        got = dependents.commands(ROOT, [f"{shell.root}/shell.qml"])
        assert f"bash ops/ralph/shellload.sh" in got, (shell.attr, sorted(got))


def test_the_gate_is_run_here_unlike_the_one_that_takes_photographs():
    """The reason it is a separate gate. `hudscreens.sh` is 3m15s and produces
    a directory of pictures somebody has to look at, so it is named rather than
    run (B72/B75). This is the cheap half B75 asked about — a verdict, in 25 s,
    with no sheet to rewrite — so it is bound like any other step."""
    gate = next(
        g for g in dependents.DECLARED_GATES if g.script == "ops/ralph/shellload.sh"
    )
    assert gate.runs_here
    assert not gate.note
    for shell in shells.SHELLS:
        unrun = [s for s, _ in dependents.unrun(ROOT, [f"{shell.root}/shell.qml"])]
        assert "ops/ralph/shellload.sh" not in unrun, shell.attr


def test_the_gate_is_planned_for_everything_that_carries_a_frame_to_a_plate():
    """The inverse of what this test used to say, and the reason is D43.

    Until the HUD was woken, nothing here started a broker: the HUD ran blind,
    a change to the bus could not move the verdict, and binding these seconds
    to every Rust edit would have bought nothing. The HUD's half of this gate
    IS that broker now, so all three paths a frame travels are declared — the
    broker, the client library the publisher and the bridge both speak, and the
    bridge itself, which is the child process `pkgs/jv-hud` pins into the
    wrapper and the only thing in this repo that carries a frame into a plate.
    """
    for path in (
        "services/jarvisd/src/broker.rs",
        "services/pylib/jarvis_bus/client.py",
        "services/jv-hud-bridge/jv_hud_bridge/bridge.py",
    ):
        got = dependents.commands(ROOT, [path])
        assert "bash ops/ralph/shellload.sh" in got, (path, sorted(got))


# ------------------------------------------------- the HUD's frames (D43)
#
# The HUD used to be the shell here with nothing to say: `Bus` blind, every
# plate refusing to guess, `visible: selfTest || stack.anyLit` false — so no
# wl_surface of its was ever created and every plate was outside this gate. It
# gets a real broker and eleven real frames now. These are the checks on the
# frames and on the census that reads the result; the measurement itself needs
# a compositor and is the gate.


def hud_shell_text() -> str:
    return strip_qml_comments(
        (ROOT / "shell" / "jv-hud" / "shell.qml").read_text("utf-8")
    )


def stacked_plate_names() -> list[str]:
    """The `plateName` of every plate in `shell/jv-hud/shell.qml`'s stack, in
    stack order, read out of the plates' own files.

    Two hops on purpose. The stack names TYPES (`ConfirmPlate`) and the corner
    logs NAMES (`confirm`), and the mapping between them lives in each plate —
    so a test that assumed `XxxPlate` -> `xxx` would agree with a plate that
    had renamed itself and disagree with nothing.
    """
    body = hud_shell_text()
    start = body.index("PlateStack {")
    names = []
    for kind in re.findall(r"^\s{8}([A-Z][A-Za-z]*Plate) \{", body[start:], re.M):
        plate = strip_qml_comments(
            (ROOT / "shell" / "jv-hud" / f"{kind}.qml").read_text("utf-8")
        )
        found = re.search(r'plateName:\s*"([a-z]+)"', plate)
        assert found, f"{kind}.qml no longer declares a plateName"
        names.append(found.group(1))
    return names


def test_every_plate_the_hud_stacks_is_lit_by_this_gate_or_named_as_dark():
    """The drift guard, and the whole reason the lit list is worth stating.

    A twelfth plate lands in the stack, nothing adds it here, and the gate goes
    on reporting that the HUD's corner lights — over a plate no frame in this
    repo has ever reached. Both lists are in stack order because the corner
    logs in stack order, so this also pins the sequence the census matches.
    """
    stacked = stacked_plate_names()
    assert stacked, "no plates found in shell/jv-hud/shell.qml's stack"
    assert [n for n in stacked if n not in shells.HUD_PLATES_DARK] == list(
        shells.HUD_PLATES_LIT
    ), (stacked, shells.HUD_PLATES_LIT)
    for dark in shells.HUD_PLATES_DARK:
        assert dark in stacked, dark


def test_the_plate_that_cannot_be_lit_here_is_the_one_about_the_bus_itself():
    """And it is not an omission — it is a second run (PLAN D47). `LinkPlate`
    is on screen exactly while the HUD cannot SEE the bus, so lighting it in
    the run above would mean taking the broker away, and then there would be
    no frames for anything else. `shell.qml` makes the same observation about
    its own box: in practice it can never share the surface. So this tuple is
    both the plate the frames run must NOT light and the whole of what the
    blind run's corner must show."""
    assert shells.HUD_PLATES_DARK == ("link",)
    link = strip_qml_comments(
        (ROOT / "shell" / "jv-hud" / "LinkPlate.qml").read_text("utf-8")
    )
    assert "shown: root.link.blind" in link


def test_the_corner_line_this_gate_reads_is_the_one_the_hud_writes():
    """The copy, and the third file that holds both ends equal.

    `hud_corner_line()` restates the template `shell/jv-hud/shell.qml` logs,
    because there is nothing to import — the string only exists inside a
    running QML engine. Assembled here out of the QML's own literals, so a
    reworded line fails this rather than turning the census into a wait that
    times out with no explanation.
    """
    body = hud_shell_text()
    parts = re.findall(r'console\.info\((.*?)\);', body, re.S)
    assert len(parts) == 1, parts
    literals = re.findall(r'"([^"]*)"', parts[0])
    # The template, in the order the QML concatenates it: prefix, the joiner
    # between the monitor and the plates, the separator inside the list, and
    # the word for an empty corner.
    assert literals == [
        "jv-hud: corner on ",
        " shows ",
        " ",
        "nothing",
    ], literals
    assert shells.hud_corner_line("HEADLESS-1", ("a", "b")) == (
        literals[0] + "HEADLESS-1" + literals[1] + "a" + literals[2] + "b"
    )
    assert shells.hud_corner_line("HEADLESS-1", ()) == (
        literals[0] + "HEADLESS-1" + literals[1] + literals[3]
    )


def test_the_corner_is_read_on_every_monitor_and_not_just_somewhere():
    """`Variants` builds one surface per screen and each one's plates decide
    for themselves — D32's fault was a row sized against the wrong monitor's
    width. A census that accepted one line would pass a shell that had quietly
    stopped building the third surface, so the driver asks each monitor by
    name and this holds the parser to answering per monitor."""
    said = "\n".join(
        shells.hud_corner_line(out["name"], shells.HUD_PLATES_LIT)
        for out in shells.ALL_OUTPUTS[:-1]
    )
    for out in shells.ALL_OUTPUTS[:-1]:
        assert shells.hud_corner_plates(said, out["name"]) == list(
            shells.HUD_PLATES_LIT
        ), out["name"]
    missed = shells.ALL_OUTPUTS[-1]["name"]
    assert shells.hud_corner_plates(said, missed) is None, missed
    driver = code_lines(DRIVER)
    assert "for out in shells.ALL_OUTPUTS" in driver


def test_a_corner_that_never_spoke_is_told_apart_from_one_that_went_dark():
    """Two different repairs. None is a surface that was never built; an empty
    list is a surface that is there and has nothing to say, which is the
    ordinary state of this HUD and must never read as the same failure."""
    dark = shells.hud_corner_line("HEADLESS-1", ())
    assert shells.hud_corner_plates(dark, "HEADLESS-1") == []
    assert shells.hud_corner_plates(dark, "HEADLESS-2") is None


def test_the_newest_line_is_the_one_read_because_a_corner_is_a_sequence():
    """The plates arrive over a round or two — `output` needs jv-context's
    snapshot, `heard` needs the transcript after the speaking frame — so the
    corner names a growing set. Reading the first line would grade the HUD on
    the instant it woke up."""
    said = "\n".join(
        [
            shells.hud_corner_line("HEADLESS-1", ()),
            shells.hud_corner_line("HEADLESS-1", ("mic", "health")),
            shells.hud_corner_line("HEADLESS-1", shells.HUD_PLATES_LIT),
        ]
    )
    assert shells.hud_corner_plates(said, "HEADLESS-1") == list(shells.HUD_PLATES_LIT)


def test_the_corner_names_the_plates_and_never_what_they_say():
    """Structural, not tidy (invariant 7). The corner's account reaches
    journald on a real machine, and `plateName` is one word per element — so
    what is recorded is WHICH readings were on screen and never the words
    jv-ears took down, the question jv-act asked or the file jv-guard
    refused."""
    body = hud_shell_text()
    found = re.search(r"console\.info\((.*?)\);", body, re.S)
    assert found
    logged = found.group(1)
    assert "litNames" in logged
    # Nothing in the logged expression may reach into a plate's own content.
    for reach in ("text", "summary", "body", "transcript", "verdict", "file"):
        assert reach not in logged, reach


# ------------------- the screen the corner does not fit on (PLAN D75)
#
# The fourth output, which is not a monitor. `shell/jv-hud/shell.qml` declares
# the shortest screen its corner is for and D74 settled that as a DECLARED
# FLOOR rather than as a clamp: on a shorter screen the compositor crops the
# bottom of the stack, every plate is still drawn, and the shell says so in its
# log. `tools/tests/test_gen_theme_qml.py` grades the declaration by reading
# shell.qml, which is all a suite with no compositor can do with a file no
# engine in this repo loads. These are the gates that make the gate itself ask
# the question as a behaviour — the ones that do not need a compositor.


def test_the_short_output_is_under_the_floor_the_hud_declares():
    """The whole point of the fourth output, and the number is not this file's
    to choose: 768 has to be under `shell/jv-hud/shell.qml`'s own floor or the
    compositor crops nothing, the HUD says nothing, and the reading in
    `load.py` waits three seconds to assert that a shell was quiet about a
    screen it had no business mentioning.

    The floor is read out of the shell rather than restated here, which makes
    this the third file holding the two together: a plate that made the corner
    taller raises the floor, and an output between the old floor and the new
    one would make this gate green and vacuous at the same time."""
    floor = hud_min_screen_height()
    assert shells.SHORT["height"] < floor, (
        f"{shells.SHORT['name']} is {shells.SHORT['height']}px and shell.qml's "
        f"corner is {floor}px, so it is not a short screen at all and nothing "
        "this gate reads about it can fail"
    )
    # And it is not one of ares', which is the care `sheet.py` takes over its
    # own fourth output: `OUTPUTS` is the machine that exists, and three things
    # in this file count it.
    assert shells.SHORT not in shells.OUTPUTS
    assert all(out["height"] >= floor for out in shells.OUTPUTS), (
        "one of ares' monitors is now under the floor shell.qml declares — "
        "which is a decision to reopen (D74), not a harness to adjust"
    )


def test_each_harness_fourth_output_asks_one_question_and_not_the_others():
    """Two harnesses, two compositors, two fourth outputs, and they are not the
    same experiment. `sheet.py`'s is 280 px WIDE and 1080 tall: the width
    question (D66's clamp, which is real code), photographed. This one is 1024
    px wide and 768 TALL: the height question (D74's floor, which is a
    declaration and a warn), read out of a log. Each has to be clear of the
    other's question, or a failure on one axis is reported as the other —
    and both bounds come from the shell they are both about."""
    corner_w, _ = hud_surface_box()
    floor = hud_min_screen_height()
    assert shells.SHORT["width"] >= corner_w, (
        f"{shells.SHORT['name']} is {shells.SHORT['width']}px wide against a "
        f"{corner_w}px corner, so it is also asking D68's width question and "
        "a clipped sentence there would be read as a cropped stack"
    )
    assert sheet.NARROW["height"] >= floor, (
        f"the screen sheet's narrow output is {sheet.NARROW['height']}px tall "
        f"against a {floor}px corner, so it is also a short screen — and the "
        "pictures taken of it would be pictures of a cropped corner"
    )
    assert sheet.NARROW["width"] < corner_w
    # The names collide on purpose and it is the backend's doing: the fourth
    # output of a headless wlroots is HEADLESS-4 whatever it was made for.
    assert shells.SHORT["name"] == sheet.NARROW["name"]


def test_the_short_screen_line_this_gate_reads_is_the_one_the_hud_writes():
    """The copy, and the third file that holds both ends equal — the shape
    `hud_corner_line()` already uses, because the string only exists inside a
    running QML engine. Assembled here out of the QML's own literals, so a
    reworded warn fails this rather than turning the reading in `load.py` into
    a three-second wait with no explanation."""
    body = hud_shell_text()
    warns = re.findall(r"console\.warn\((.*?)\);", body, re.S)
    assert len(warns) == 1, warns
    literals = re.findall(r'"([^"]*)"', warns[0])
    # The template, in the order the QML concatenates it: the prefix, the
    # joiner before the screen's height, the one before the corner's, and
    # whatever is left of the sentence. The three numbers are sentinels — this
    # is a claim about the wording and not about the floor, which is read out of
    # the shell by the gate above.
    assembled = (
        literals[0] + "HEADLESS-9" + literals[1] + "111"
        + literals[2] + "222" + "".join(literals[3:])
    )
    assert shells.hud_short_screen_line("HEADLESS-9", 111, 222) == assembled, (
        "the template in shells.py is not the one shell.qml writes: "
        f"{shells.hud_short_screen_line('HEADLESS-9', 111, 222)!r} against "
        f"{assembled!r}"
    )


def test_the_short_screen_report_is_per_output_and_reads_the_newest():
    """A screen that changed mode under a running HUD is entitled to a second
    verdict, and the report is per output because the news is WHICH screen. A
    parser that answered from any line would let a warn about the short output
    stand in for silence about a monitor — which is the absence half of the
    reading in `load.py`, and the half no regex over shell.qml can ask."""
    said = "\n".join(
        [
            "  WARN qml: " + shells.hud_short_screen_line("HEADLESS-4", 600, 826),
            "  WARN qml: " + shells.hud_short_screen_line("HEADLESS-4", 768, 826),
        ]
    )
    assert shells.hud_short_screen_report(said, "HEADLESS-4") == (768, 826)
    assert shells.hud_short_screen_report(said, "HEADLESS-1") is None
    assert shells.hud_short_screen_report("", "HEADLESS-4") is None
    # Prefixed by whatever quickshell's logger puts in front of it, which is why
    # the line is searched for rather than matched from the start.
    bare = shells.hud_short_screen_line("HEADLESS-4", 768, 826)
    assert shells.hud_short_screen_report(bare, "HEADLESS-4") == (768, 826)


def test_the_short_screen_warn_is_invisible_to_the_scan_that_reads_the_log():
    """Which is why the driver has to ASSERT it. `tools/qmlerrors.py` requires
    a source location and one of ECMAScript's error names, so a `console.warn`
    carrying plain prose reads clean through it — measured here rather than
    assumed, because the whole D75 reading rests on it: if the scan DID fail on
    this line, every run of this gate would now be red and the assertion below
    would be the thing nobody could find."""
    line = "  WARN qml: " + shells.hud_short_screen_line("HEADLESS-4", 768, 826)
    assert qmlerrors.scan(line, prefix=shells.hud_shell().root) == []
    driver = code_lines(DRIVER)
    assert "hud_short_screen_report" in driver, (
        "the driver no longer reads the line at all, and nothing else in this "
        "repo can see it"
    )
    # Both directions: the short output has to have said it and the monitors
    # have to have been left out of it.
    assert "shells.SHORT" in driver and "for out in shells.OUTPUTS" in driver


def test_the_frames_this_gate_publishes_are_the_screen_sheets_own():
    """Eight of the eleven are byte-equal to a named frame in
    `tools/hudscreens/sheet.py`, and this is the third file that says so.

    Restated rather than imported for the reason `OUTPUTS` is: `sheet.py` is a
    declared read of a 3-minute harness, and importing it would make every edit
    to that harness's noise floor wake this gate. A copy with a test is the
    shape invariant 1 asks for; a copy without one is drift.
    """
    shared = {
        "speech.state": sheet.VOICE_SPEAKING,
        "context.system": sheet.SINK_MUTED,
        "audio.transcript": sheet.HEARD_FINAL,
        "action.confirm": sheet.CONFIRM_REQUEST,
        "intent.action": sheet.TRASH_INTENT,
        "action.result": sheet.TRASH_FAILED,
    }
    mine = {f["topic"]: f for f in shells.HUD_FRAMES}
    for topic, theirs in shared.items():
        spec = theirs["publish"]
        assert mine[topic]["src"] == spec["src"], topic
        assert mine[topic]["body"] == spec["body"], topic
        assert mine[topic].get("conf", 1.0) == spec.get("conf", 1.0), topic
    # The two `sys.health` beats, which share a topic and so are keyed by src.
    beats = {f["src"]: f for f in shells.HUD_FRAMES if f["topic"] == "sys.health"}
    assert beats["jv-ears"]["body"] == sheet.MIC_LOSSY["publish"]["body"]
    assert beats["jv-voice"]["body"] == sheet.VOICE_DEFAULT_SINK["publish"]["body"]


def test_the_three_new_frames_are_the_three_plates_nothing_had_ever_fed():
    """jv-guard refusing a binary, jv-compat failing an install, and jv-brain
    running out of room. Nothing in this repo had ever composed one, which is
    why those three plates had never seen a real frame — so the claim is worth
    pinning the other way round: these topics are NOT in the screen sheet."""
    sheet_topics = {
        f["publish"]["topic"]
        for shot in sheet.SHOTS
        for f in shot.get("frames", [])
        if "publish" in f
    }
    for topic in ("guard.verdict", "compat.install", "brain.response"):
        assert topic in {f["topic"] for f in shells.HUD_FRAMES}, topic
        assert topic not in sheet_topics, topic


def test_every_frame_is_a_body_the_frozen_schema_allows():
    """`schemas/` is bus law (invariant 2), and a harness that publishes an
    illegal body is lighting a plate over a machine that cannot exist. Three
    of these are hand-written here for the first time."""
    for frame in shells.HUD_FRAMES:
        schema = json.loads(
            (ROOT / "schemas" / f"{frame['topic']}.json").read_text("utf-8")
        )
        body = frame["body"]
        missing = set(schema["required"]) - set(body)
        assert not missing, f"{frame['topic']}: body is missing {sorted(missing)}"
        extra = set(body) - set(schema["properties"])
        assert not extra, f"{frame['topic']}: body has unknown keys {sorted(extra)}"
        for key, value in body.items():
            enum = schema["properties"][key].get("enum")
            if enum is not None:
                assert value in enum, f"{frame['topic']}.{key}={value!r} not in {enum}"


def test_only_the_transcript_hedges_its_confidence():
    """Six of the HUD's state machines refuse a frame whose envelope is not
    UNHEDGED (`conf >= 1`), so a composed frame that quietly carried less would
    light nothing and look like a plate that had broken. `audio.transcript` is
    the one topic whose confidence is the producer's own (invariant 4)."""
    hedged = [f["topic"] for f in shells.HUD_FRAMES if f.get("conf", 1.0) < 1.0]
    assert hedged == ["audio.transcript"]
    for state in ("Guard", "Install", "Reply", "Action", "Confirm", "Output"):
        text = (ROOT / "shell" / "jv-hud" / "core" / f"{state}State.qml").read_text(
            "utf-8"
        )
        assert "envelope.conf >= 1" in text, state


def test_the_frames_are_ordered_so_the_two_latching_plates_survive_a_round():
    """The one thing about this list that is not interchangeable. `heard` goes
    dark once `speech.state` is stamped after the words (HeardState latches
    `answering`) and `action` goes dark the same way (ActionState's
    `noteExplained`) — so the speaking frame goes FIRST and everything else is
    newer than it. Republishing the set in order is what keeps that true every
    round."""
    order = [f["topic"] for f in shells.HUD_FRAMES]
    assert order.index("speech.state") == 0, order
    assert order.index("speech.state") < order.index("audio.transcript")
    assert order.index("speech.state") < order.index("action.result")
    # And the intent before the outcome it names, or the plate lights with no
    # tool on it: the request id is the only thread between the two.
    assert order.index("intent.action") < order.index("action.result")
    for state, latch in (("Heard", "answering"), ("Action", "noteExplained")):
        text = (ROOT / "shell" / "jv-hud" / "core" / f"{state}State.qml").read_text(
            "utf-8"
        )
        assert latch in text, state


def code_lines(path: Path) -> str:
    """One Python file with its comments and its docstrings taken out.

    The same reading `executed_lines()` takes of the bash: a rule about what a
    file may not DO has to be a rule about what it runs, or the prose
    explaining the rule trips it. Docstrings are dropped through `ast` rather
    than by pattern, because a triple quote inside a comment is exactly the
    shape that would defeat one.
    """
    text = path.read_text("utf-8")
    tree = ast.parse(text)
    drop = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
            continue
        body = node.body
        if body and isinstance(body[0], ast.Expr) and isinstance(
            body[0].value, ast.Constant
        ) and isinstance(body[0].value.value, str):
            drop.update(range(body[0].lineno, body[0].end_lineno + 1))
    return "\n".join(
        line
        for n, line in enumerate(text.splitlines(), start=1)
        if n not in drop and not line.strip().startswith("#")
    )


def test_the_publisher_only_ever_publishes():
    """A read-only consumer is what the HUD is; a write-only client is what
    this gate's half must be. A publisher that subscribed could report that a
    frame arrived, which is a claim about the bus and not about the HUD — and
    the HUD's own account of its corner is the only census here worth having.
    """
    text = code_lines(ROOT / "tools" / "shellload" / "publish.py")
    for forbidden in ("subscribe", "next_frame", "next_event"):
        assert forbidden not in text, forbidden
    assert ".publish(" in text


def test_the_publisher_is_a_process_and_the_driver_keeps_no_event_loop():
    """The reason it is next door rather than inline: the bus client is
    asyncio, the driver is not, and a driver that grew an event loop to keep
    one plate fresh would be taking its measurements inside somebody else's
    scheduler."""
    driver = code_lines(DRIVER)
    assert "asyncio" not in driver
    assert "publish.py" in driver
    assert "PUBLISH" in driver


def test_the_frames_keep_coming_because_one_plate_needs_them_to():
    """`output` reads jv-context's 1 Hz snapshot and core/OutputState.qml calls
    one older than 3 s stale — correctly, because a mixer reading from ten
    seconds ago is not a reading of this room. A single pass would light the
    plate and lose it again before the compositor had been asked anything."""
    out = (ROOT / "shell" / "jv-hud" / "core" / "OutputState.qml").read_text("utf-8")
    found = re.search(r"property real snapshotS:\s*([0-9.]+)", out)
    assert found, "core/OutputState.qml no longer declares a snapshotS"
    assert shells.HUD_ROUND_S < float(found.group(1)), (
        f"the publisher republishes every {shells.HUD_ROUND_S}s and the "
        f"snapshot goes stale at {found.group(1)}s"
    )
    assert "output" in shells.HUD_PLATES_LIT


def test_the_broker_is_realized_from_the_flake_and_started_by_the_script():
    """Same rule as the shells: `nix build` is the one thing in this harness
    that is not a measurement, so it lives in the script and the driver cannot
    reach it. A driver that could build a broker could build a different one.
    """
    assert 'nix build "$root#jarvisd"' in script_text()
    assert (ROOT / "services" / "jarvisd" / "Cargo.toml").is_file()
    for half in (DRIVER, ROOT / "tools" / "shellload" / "publish.py"):
        text = code_lines(half)
        assert "nix build" not in text, half.name
        assert "jarvisd" not in text, half.name


def test_the_broker_the_blind_run_starts_is_the_one_the_script_already_made():
    """D49 needs a broker STARTED after its HUD has been failing to connect, so
    the driver starts one — and it may still not build one. It arrives in an
    environment variable, out of the same store path the script realized for the
    frames run, because two acts of one run measured against two different
    brokers is not one measurement."""
    assert 'export JARVISD_BIN="$jarvisd/bin/jarvisd"' in script_text()
    assert script_text().index("jarvisd=$(nix build") < script_text().index(
        'export JARVISD_BIN='
    )
    text = code_lines(DRIVER)
    assert 'need("JARVISD_BIN")' in text
    # The only path it may name is the bus, which is the stage's.
    assert "/nix/store" not in text


def test_the_bus_is_this_runs_own_socket_and_not_the_machines():
    """The same rule the session bus gets, for the same reason. The real one is
    `/run/jarvis/bus.sock`; a gate that published eleven composed frames onto
    the bus of a live desktop would put a confirmation nobody asked for in
    front of the user."""
    lines = [ln for ln in executed_lines() if "JARVIS_BUS" in ln]
    assert lines, "the gate never sets JARVIS_BUS"
    assert any('JARVIS_BUS="$stage/' in ln for ln in lines), lines
    assert not any("/run/jarvis" in ln for ln in executed_lines())


def test_the_broker_is_killed_with_everything_else():
    """A jarvisd left behind holds a socket in a directory the trap is about
    to delete, and the next run's HUD would link to a broker nobody is
    publishing on — which reads as a HUD that ignored its frames."""
    text = script_text()
    trap = text[text.index("cleanup()") : text.index("trap cleanup EXIT")]
    assert "buspid" in trap
    assert "buspid=$!" in text


# ------------------------------------------- the blind HUD (PLAN D47)
#
# The eleventh plate, and the run that exists only to light it. Everything
# above is a HUD with a broker under it; `LinkPlate` is on screen exactly while
# there is none. These are the checks on that second run that do not need a
# compositor — the measurement itself is the gate.


def test_the_blind_run_loads_the_same_shipped_hud_as_the_frames_run():
    """A second binary would be a second shell, and this claim is about THIS
    one. The driver takes it out of `SHELLS` by `wake`, so the shell list stays
    the only place that decides which of the three is the HUD — and it arrives
    in the same `env` variable the script exported for the first run."""
    text = DRIVER.read_text("utf-8")
    blind = text[text.index("def load_blind("):text.index("def main(")]
    assert "shells.hud_shell()" in blind
    assert "need(shell.env)" in blind
    assert "nix build" not in blind
    hud = shells.hud_shell()
    assert hud.attr == "jv-hud" and hud.root == "shell/jv-hud"


def test_exactly_one_shell_is_the_one_this_second_run_is_about():
    """`hud_shell()` picks by `wake`, and two shells woken by frames would
    mean the blind run silently chose one of them."""
    assert [s.attr for s in shells.SHELLS if s.wake == "hud"] == ["jv-hud"]
    saved = shells.SHELLS
    shells.SHELLS = saved + (saved[0],)
    try:
        with pytest.raises(ValueError):
            shells.hud_shell()
    finally:
        shells.SHELLS = saved


def test_the_only_thing_changed_about_the_blind_run_is_the_bus():
    """The whole point. The compositor, the private session bus, the pinned
    bridge in the wrapper and the theme all have to be identical to the run
    that lit ten plates, or what this measures is not "the bus is gone". So
    the environment is this process's own with exactly one key replaced."""
    found = re.search(r"env = dict\(os\.environ, (\w+)=([^)]+)\)", blind_text())
    assert found, blind
    assert found.group(1) == "JARVIS_BUS"
    assert "shells.HUD_BLIND_BUS" in found.group(2)


def test_the_bus_the_blind_run_is_given_is_one_nothing_creates_in_time():
    """A path rather than an empty string, and a path under the run's own
    stage. `jv-hud-bridge` falls back to its own default when `--bus` and
    `$JARVIS_BUS` are both empty, so a blank would be a HUD that quietly found
    the machine's real socket — and this gate would have blinded nothing.

    "In time" is D49: the socket does eventually arrive, because the second act
    starts a real broker on it. What must not exist is a socket there BEFORE the
    blind census, which is what the two rules below are about — the machine's
    own bus, and the one the script starts for the frames run."""
    assert shells.HUD_BLIND_BUS
    assert not shells.HUD_BLIND_BUS.startswith("/")
    # Not the socket the script really starts jarvisd on, which is the one
    # thing it could collide with.
    real = next(line for line in executed_lines() if "JARVIS_BUS=" in line)
    assert shells.HUD_BLIND_BUS not in real, real
    # And the script never touches it: the name is spelled once, in `shells.py`,
    # and reaches both the HUD's environment and the late broker's argv through
    # the constant.
    assert shells.HUD_BLIND_BUS not in "\n".join(executed_lines())
    driver = code_lines(DRIVER)
    assert shells.HUD_BLIND_BUS not in driver
    # Three uses, and they are the three acts of this run: the HUD's own
    # environment, the broker `relink` starts on it, and the publisher `recover`
    # speaks on it (PLAN D52).
    assert driver.count("shells.HUD_BLIND_BUS") == 3


def test_the_blind_corner_must_name_the_dark_plate_and_nothing_else():
    """The stronger half of what this run proves. Every state machine under
    this corner is built to REFUSE rather than guess from a bus it cannot see,
    and a refusal draws the same nothing a calm machine does — so no picture
    can tell them apart. A corner naming exactly `link` can: a plate that had
    started guessing would be named beside it."""
    blind = blind_text()
    assert "list(shells.HUD_PLATES_DARK)" in blind
    # And the ten are not expected HERE. They are expected of this same engine
    # two acts later, once the bus is back (PLAN D52) — which is a different
    # function and the reason `blind_text()` stops where it does.
    assert "HUD_PLATES_LIT" not in blind
    # The two lists cannot overlap, or the expectation is unsatisfiable in one
    # of the two runs.
    assert not set(shells.HUD_PLATES_LIT) & set(shells.HUD_PLATES_DARK)


def test_every_reading_of_the_corner_is_the_same_reading():
    """One census, three callers. The way a corner is READ — newest line per
    screen, every screen, exact order — is the same question whether there are
    ten plates on it, one, or none, and two copies of it would be two answers.
    The third caller is D49's: the same blind HUD once the bus arrives."""
    text = DRIVER.read_text("utf-8")
    assert text.count("def corner_census(") == 1
    # The definition and four callers: ten plates on a HUD that always had a
    # bus, one on a HUD that never did, none on that same HUD once it does
    # (D49), and the ten again on that same HUD once it is fed (D52).
    assert text.count("corner_census(") == 5


def test_the_blind_run_outlasts_the_grace_it_is_about():
    """The wait is mostly a real wait rather than a ceiling: `LinkState` says
    nothing for `graceS` seconds on purpose, so a timeout at or under it would
    fail a HUD that behaved perfectly. Headroom on top for a cold Qt."""
    grace = shells.link_grace_s(shells.link_state_path().read_text("utf-8"))
    assert grace > 0
    assert shells.HUD_BLIND_TIMEOUT_S >= grace + 5, (grace, shells.HUD_BLIND_TIMEOUT_S)


def test_the_grace_is_read_out_of_the_qml_rather_than_copied_into_this_gate():
    """Unlike `bar_strip_px()` and `hud_corner_line()`, which are copies held
    equal by a third file. Those two are EXPECTATIONS — the gate states what
    the shell must do and goes red when it does not. This one is a duration
    the gate has to outlast, and a stale copy of it would make the gate flaky
    rather than red. So it is read, and it fails loudly when there is nothing
    to read."""
    assert shells.link_state_path().is_file()
    grace = shells.link_grace_s(shells.link_state_path().read_text("utf-8"))
    # Read where it is USED, not once into a constant: the gate's own numbers
    # are copies held equal by a test, and this one has no fixed value at all.
    assert "shells.link_grace_s(" in DRIVER.read_text("utf-8")
    assert grace not in [
        v for v in vars(shells).values() if isinstance(v, float)
    ], grace
    # And a QML that stopped declaring it is a loud failure rather than a
    # default nobody chose.
    with pytest.raises(ValueError):
        shells.link_grace_s("QtObject { property real somethingElse: 5.0 }")


# ------------------------------- and then the bus comes back (PLAN D49)
#
# The other half of the blind run, and the more dangerous one. `LinkState`
# deliberately never clears the flag its grace set, so a `link` plate that
# latched on forever passes the blind census exactly as the shipped HUD does —
# and a permanent NO BUS over a healthy machine teaches the user to ignore the
# one plate that qualifies all the others. These are the checks on that second
# act that do not need a compositor.


def blind_text() -> str:
    """`load_blind()` alone, without the two acts it calls into.

    It used to run to `def main(`, which was the same thing until D49 and D52
    put `relink()` and `recover()` between the two — and `recover` expects the
    ten LIT plates, which is exactly what the blind census must not."""
    text = DRIVER.read_text("utf-8")
    return text[text.index("def load_blind(") : text.index("def relink(")]


def relink_text() -> str:
    """`relink()` alone, and NOT the rest of the driver under it.

    It used to be everything from `def relink(` to the end of the file, which
    was the same thing until D52 put a third act below it. The two are now
    different questions — what the relink does on a bus nobody has published
    on, and what `recover()` does once somebody has — and a slice that ran to
    the end of the file would answer the first with the second."""
    text = DRIVER.read_text("utf-8")
    return text[text.index("def relink(") : text.index("def recover(")]


def test_the_blind_run_does_not_end_with_the_hud_still_saying_no_bus():
    """The fault this act exists for, stated as the shape of the driver: the
    blind census is not the last thing that happens to that HUD. The broker
    arrives on its bus and the same surface, the same engine and the same log
    have to report a corner that went dark."""
    text = DRIVER.read_text("utf-8")
    blind = text[text.index("def load_blind(") : text.index("def main(")]
    assert "def relink(" in blind
    assert "relink(stage, proc)" in blind
    # The same engine's log, or this is a claim about some other HUD.
    assert "hud.logpath" in blind
    assert "list(shells.HUD_PLATES_RELINKED)" in blind


def test_the_corner_that_comes_back_is_empty_and_that_is_an_expectation():
    """`HUD_PLATES_RELINKED` is deliberately empty, and empty is a reading
    rather than an absence: `hud_corner_plates` parses the QML's own word
    `nothing`. Two ways to fail it, and they are different faults — a corner
    still naming `link` is the latch, and a corner naming anything else is a
    plate that started guessing the moment it could see a bus."""
    assert shells.HUD_PLATES_RELINKED == ()
    assert shells.hud_corner_plates(
        shells.hud_corner_line("HEADLESS-1", ()), "HEADLESS-1"
    ) == list(shells.HUD_PLATES_RELINKED)
    # And nothing has published a frame on this broker YET, so no other plate
    # has anything to say. Read over the relink alone rather than to the end of
    # the file: D52 hands the same broker to a publisher immediately afterwards,
    # and the whole reason THAT reading means something is that this one came
    # first, on a bus nobody had spoken on.
    assert "PUBLISH" not in relink_text()
    assert "HUD_FRAMES" not in relink_text()


def test_the_empty_corner_is_only_read_after_the_hud_said_it_was_blind():
    """What makes that reading mean anything. An empty corner is also what a HUD
    that never lit a plate looks like — so this only counts because the blind
    census has already required the NEWEST line on every screen to be `link`,
    and `hud_corner_plates` reads the newest. Order, therefore, is load-bearing:
    the relink is inside `load_blind`, after its census."""
    text = DRIVER.read_text("utf-8")
    blind = text[text.index("def load_blind(") : text.index("def relink(")]
    assert blind.index("HUD_PLATES_DARK") < blind.index("relink(stage, proc)")
    # And the newest line is what the census reads, which is the property the
    # order above leans on.
    said = "\n".join(
        [
            shells.hud_corner_line("HEADLESS-1", ("link",)),
            shells.hud_corner_line("HEADLESS-1", ()),
        ]
    )
    assert shells.hud_corner_plates(said, "HEADLESS-1") == []


def test_the_relink_wait_outlasts_the_retry_it_is_waiting_for():
    """Like the grace, this is a real wait rather than a ceiling — and what it
    has to outlast is the BRIDGE's patience, not the HUD's. By the time the
    broker appears the bridge has been failing for several seconds, so its
    backoff has doubled its way to the maximum and the socket can arrive one
    instant after a failed attempt. Headroom on top for the connect, the
    subscribe and the fade the plate leaves on."""
    backoff = shells.bridge_max_backoff_s(shells.bridge_path().read_text("utf-8"))
    assert backoff > 0
    assert shells.HUD_RELINK_TIMEOUT_S >= backoff + 5, (
        backoff,
        shells.HUD_RELINK_TIMEOUT_S,
    )
    # The socket is a different kind of wait and is bounded separately: binding
    # one is not a cold font cache, so a broker that has not bound in that long
    # is not going to — and spending the corner's budget on it would report the
    # wrong repair.
    assert shells.HUD_RELINK_BUS_TIMEOUT_S < shells.HUD_RELINK_TIMEOUT_S


def test_the_backoff_is_read_out_of_the_bridge_rather_than_copied():
    """The same rule `link_grace_s` follows, for the same reason: a duration the
    gate has to OUTLAST must be read, or a stale copy makes the run flaky rather
    than red. A bridge given more patience than the wait above allows is a gate
    that fails a HUD which was about to recover."""
    assert shells.bridge_path().is_file()
    assert "shells.bridge_max_backoff_s(" in DRIVER.read_text("utf-8")
    with pytest.raises(ValueError):
        shells.bridge_max_backoff_s("FIRST_BACKOFF_S = 0.5\n")
    # And it really READS: a bridge that declared a different number gets a
    # different answer, which is what tells this apart from a constant with a
    # file path next to it. Checked this way rather than by scanning `shells.py`
    # for the value, the way the grace is: `MAPPED_TIMEOUT_S` is coincidentally
    # the same 8.0, so a value scan would be asserting that two unrelated
    # numbers stay unequal.
    assert shells.bridge_max_backoff_s("MAX_BACKOFF_S = 99.5\n") == 99.5


def test_the_late_broker_is_not_graded_as_a_qml_engine():
    """`tools/qmlerrors.py` reads what a QML engine said. A broker's tracing
    lines under a scanner that knows quickshell's prefixes would be graded by a
    reader of the wrong language — and worse, would read clean whatever it said.
    Its log is quoted into the failure message instead, which is the one place
    "did the thing I started even come up" is worth having."""
    assert shells.HUD_RELINK_BROKER_LOG not in [
        name for name, _ in shells.scan_targets()
    ]
    assert shells.HUD_RELINK_BROKER_LOG not in [s.attr for s in shells.SHELLS]
    assert shells.HUD_RELINK_BROKER_LOG != shells.HUD_BLIND_LOG
    assert "broker.tail(" in relink_text()


def test_the_late_broker_is_stopped_by_the_driver_that_started_it():
    """The script's trap only knows the pids it started. A broker left holding
    a socket in a directory about to be deleted is the shape of a leak this
    harness has had before, so it is stopped in a `finally` like the publisher —
    on the failing path too, which is the one that matters."""
    relink = relink_text()
    assert "finally:" in relink
    assert relink.index("finally:") < relink.index("broker.stop()")


def test_the_blind_runs_log_is_scanned_like_every_other_engines():
    """The D39 failure, one run further out: a blind HUD that reached
    `Configuration Loaded` and threw on every screen is exactly what this gate
    was written for, and a log nobody scanned reports nothing. The scan loop
    iterates engines rather than shells for that reason, and the blind log is
    read under the HUD's root because it is the same store path."""
    targets = shells.scan_targets()
    assert len(targets) == len(shells.SHELLS) + 1
    assert (shells.HUD_BLIND_LOG, shells.hud_shell().root) in targets
    names = [name for name, _ in targets]
    assert len(set(names)) == len(names), names
    # Its own file, or the two HUD runs' corners would be read out of one log.
    assert shells.HUD_BLIND_LOG not in [s.attr for s in shells.SHELLS]
    assert "shells.scan_targets()" in script_text()
    assert "$stage/$logname.log" in script_text()


# ------------------------------------- and then it works again (PLAN D52)
#
# The third act of the blind run, which is what turns two readings into a
# CYCLE: blind → says so → lets go → reports the machine again. These are the
# checks on it that do not need a compositor.


def recover_text() -> str:
    """`recover()` alone, the same way `relink_text()` is the relink alone."""
    text = DRIVER.read_text("utf-8")
    return text[text.index("def recover(") : text.index("def main(")]


def test_the_hud_that_survived_the_outage_has_to_light_a_plate_again():
    """The hole D52 is about. D49 ends with an empty corner, which proves the
    plate let go and nothing else — the engine that was blind is never shown a
    frame, and the ten-plate census belongs to a different quickshell that had
    a broker from birth. So the recovered corner is read too, on the SAME
    engine's log, against the SAME ten plates."""
    text = DRIVER.read_text("utf-8")
    assert "def recover(" in text
    assert "recover(stage, hud, broker)" in relink_text()
    recover = recover_text()
    # The blind engine's own log and the blind engine's own name, or this is a
    # census of the HUD that was never blind.
    assert "hud.logpath" in recover
    assert "shells.HUD_BLIND_LOG" in recover
    # And the expectation is the frames run's tuple itself rather than a copy:
    # the recovered corner has to be the same corner.
    assert "list(shells.HUD_PLATES_LIT)" in recover


def test_the_recovered_corner_is_only_read_after_the_corner_went_dark():
    """What makes the reading mean anything, and it is D49's own argument one
    act further on. `hud_corner_plates` reads the NEWEST line, and the relink
    census has already required that line to be `nothing` on every screen — so
    ten plates here can only be a line the HUD wrote after the bus came back.
    Order is load-bearing, which is why `recover` is called from inside
    `relink` rather than being a run of its own: the broker has to still be
    alive, and the dark census has to have already happened."""
    relink = relink_text()
    assert relink.index("HUD_PLATES_RELINKED") < relink.index("recover(stage, hud, broker)")
    said = "\n".join(
        [
            shells.hud_corner_line("HEADLESS-1", ("link",)),
            shells.hud_corner_line("HEADLESS-1", ()),
            shells.hud_corner_line("HEADLESS-1", shells.HUD_PLATES_LIT),
        ]
    )
    assert shells.hud_corner_plates(said, "HEADLESS-1") == list(shells.HUD_PLATES_LIT)


def test_the_late_publisher_speaks_on_the_bus_the_blind_hud_can_see():
    """The one thing about this publisher that differs from the frames run's,
    and getting it wrong would be the worst kind of pass here.
    `jarvis_bus.default_addr()` reads `JARVIS_BUS`, and the value this process
    inherited is the SCRIPT's broker — the one the frames run used. A publisher
    that took the inherited one would light the corner from a bus the blind HUD
    has never been able to reach, which is a green run that measures nothing."""
    recover = recover_text()
    assert "JARVIS_BUS=str(stage / shells.HUD_BLIND_BUS)" in recover
    assert "env=dict(os.environ," in recover
    # And it is the same socket `relink` gave the broker, or the two halves of
    # this act are about two different buses.
    assert "shells.HUD_BLIND_BUS" in relink_text()


def test_the_late_publisher_is_stopped_and_is_not_graded_as_a_qml_engine():
    """Its own log, for `Proc.wait_for` to quote when it dies — and NOT a scan
    target, for the reason the late broker is not one: `tools/qmlerrors.py`
    reads what a QML engine said, and a publisher is not one, so over its log
    it would report "nothing threw" whatever it said.

    And stopped in a `finally` like every other process this driver starts: it
    republishes forever by design, and the stage directory is about to be
    deleted out from under it."""
    scanned = [name for name, _ in shells.scan_targets()]
    assert shells.HUD_RECOVER_LOG not in scanned
    assert shells.HUD_RECOVER_LOG not in [s.attr for s in shells.SHELLS]
    assert shells.HUD_RECOVER_LOG != shells.HUD_RELINK_BROKER_LOG
    assert shells.HUD_RECOVER_LOG != shells.HUD_BLIND_LOG
    recover = recover_text()
    assert "finally:" in recover
    assert recover.index("finally:") < recover.index("pub.stop()")


def test_the_publisher_wait_is_its_own_number_and_not_the_corners():
    """D52's one change to the act above it, and it is a correctness one rather
    than a saving. `HUD_LIT_TIMEOUT_S` is a cold Qt building a scene of eleven
    plates; the publisher's round is a python process starting and connecting
    to a socket that is already bound. They were one number because there was
    one publisher, and there are two now — so the number that is about a corner
    is spent on corners."""
    assert shells.HUD_PUBLISH_TIMEOUT_S < shells.HUD_LIT_TIMEOUT_S
    assert shells.HUD_PUBLISH_TIMEOUT_S >= 2
    text = DRIVER.read_text("utf-8")
    for wait in re.findall(r'wait_for\("round 1", ([^)]+)\)', text):
        assert wait == "shells.HUD_PUBLISH_TIMEOUT_S", wait
    # Both publishers, or one of them is bounded by a number about something
    # else.
    assert text.count('wait_for("round 1"') == 2


def test_the_recovered_corner_is_given_less_time_than_the_cold_one():
    """Not a budget and not a saving: a statement about what each wait waits
    ON. The frames run's twenty seconds cover a cold Qt AND a bridge that has
    to spawn, connect and subscribe. This engine has been up for half a minute
    and D49's census has already proved its bridge is connected, so what is
    left is the frames travelling — which is one round and change."""
    assert shells.HUD_RECOVER_TIMEOUT_S < shells.HUD_LIT_TIMEOUT_S
    # But comfortably more than a round, or the gate fails a HUD that was
    # about to light.
    assert shells.HUD_RECOVER_TIMEOUT_S >= shells.HUD_ROUND_S * 8


def test_the_blind_run_is_counted_in_the_verdict_and_not_only_logged():
    """`load_blind` raising has to be a non-zero exit, like any shell that
    did not load — a run that reported its failure and returned 0 is the shape
    of a gate that quietly stopped asking half its question."""
    text = DRIVER.read_text("utf-8")
    after = text[text.index("load_blind(stage, ready)", text.index("def main(")):]
    assert "bad += 1" in after[: after.index("if bad:")]


# ---------------------------------- and what the BROKERS said (PLAN D51)
#
# Two `jarvisd` run in this gate — the script's, for the frames, and the one
# `relink()` starts on the blind HUD's own socket (D49) — and until D51 the
# only thing that had ever opened either log was the failure message D49
# quotes it into. Every claim above about the HUD is a reading of what those
# brokers did, so a broker that came up and then refused the bridge reads from
# the corner as a HUD that ignored its frames. These are the checks on the
# second reader's WIRING; the reader's own rule is in `test_brokerlog.py`.


def test_every_broker_this_gate_starts_has_its_log_read():
    """Two brokers, two entries, and no third: a target list that drifted from
    the brokers the run really starts is a log nobody reads, which is the
    silence D51 exists to remove."""
    targets = shells.broker_targets()
    assert len(targets) == 2
    assert (shells.FRAMES_BROKER_LOG, shells.FRAMES_BUS) in targets
    assert (shells.HUD_RELINK_BROKER_LOG, shells.HUD_BLIND_BUS) in targets
    names = [name for name, _ in targets]
    assert len(set(names)) == len(names), names
    # Two brokers on one socket would be two brokers this gate cannot tell
    # apart, and the census would pass for whichever wrote first.
    buses = [bus for _, bus in targets]
    assert len(set(buses)) == len(buses), buses


def test_the_broker_logs_and_the_qml_logs_are_read_by_different_readers():
    """The mirror of `test_the_late_broker_is_not_graded_as_a_qml_engine`, now
    that there is something else to grade them with. `qmlerrors.py` over a
    tracing line says nothing threw whatever the line says, and `brokerlog.py`
    over a quickshell log refuses it — so the two lists must not overlap in
    either direction."""
    qml = {name for name, _ in shells.scan_targets()}
    brokers = {name for name, _ in shells.broker_targets()}
    assert qml & brokers == set()
    assert brokers & {s.attr for s in shells.SHELLS} == set()
    text = script_text()
    assert "tools/brokerlog.py" in text
    assert "shells.broker_targets()" in text
    assert "$stage/$logname.log" in text


def test_the_socket_the_script_hands_over_is_the_one_the_census_is_about():
    """The census is that each broker announced the path THIS run gave it, so
    the path the script exports and the path the reader is told have to be one
    string. They are: both come out of `shells.py`, which is why the script
    reads the name rather than spelling `bus.sock` itself."""
    lines = executed_lines()
    assert 'export JARVIS_BUS="$stage/$busname"' in lines
    assert any("shells.FRAMES_BROKER_LOG" in ln for ln in lines)
    assert any("shells.FRAMES_BUS" in ln for ln in lines)
    assert any('--listening "$stage/$busfile"' in ln for ln in lines)
    # And nothing spells either of them by hand any more, which is the whole
    # reason they moved: a second spelling is how a gate ends up grading a
    # file nobody writes.
    assert not any("bus.sock" in ln for ln in lines), lines
    assert not any("jarvisd.log" in ln for ln in lines), lines


def test_a_broker_that_went_wrong_invalidates_the_run_it_was_under():
    """Its verdict has to reach the exit code, and ahead of the loading: a
    corner with nothing on it is what a broken broker looks like from here, so
    a run that reported `3 of 4 runs did not load` and exited on that alone
    would send the reader to the HUD."""
    text = script_text()
    assert "broker_status=0" in text
    assert "|| broker_status=$?" in text
    assert '[ "$broker_status" -ne 0 ] && exit "$broker_status"' in text
    assert text.index('[ "$broker_status"') < text.index("exit $load_status")
    # The QML scan still wins, because a scene that threw was throwing while
    # everything else here was being measured.
    assert text.index('[ "$scan_status"') < text.index('[ "$broker_status"')


def test_the_broker_reader_is_declared_by_the_gate_that_runs_it():
    """`tools/brokerlog.py` is named by no nix evaluation and by no import
    this repo can walk, exactly like `tools/qmlerrors.py` — so a change to it
    would run nothing unless the gate declares it. It is the half of this gate
    that can go wrong quietly: a reader that stopped matching what tracing
    prints would report a healthy broker forever."""
    assert (ROOT / "tools" / "brokerlog.py").is_file()
    (gate,) = [g for g in dependents.DECLARED_GATES if g.script == "ops/ralph/shellload.sh"]
    assert "tools/brokerlog.py" in gate.reads
