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

import re
import sys
from pathlib import Path

import pytest

from test_gen_theme_qml import ROOT, strip_qml_comments, theme_tokens

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
    # And the wait is not optional for any shell: one `load` per shell, one
    # wait inside it.
    assert text.count("def load(") == 1
    assert text.count("proc.wait_for(") == 1


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
    for out in shells.OUTPUTS:
        assert f"output {out['name']} mode {out['width']}x{out['height']}" in config
    assert "WLR_HEADLESS_OUTPUTS=3" in script_text()


def test_the_compositor_config_comes_from_the_one_place_that_declares_it():
    """The script may not write its own monitor list: a size that drifted
    between the two would make the checks be about a machine nobody ran."""
    assert "shells.sway_config()" in script_text()
    for out in shells.OUTPUTS:
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


def test_exactly_one_shell_is_given_something_real_to_do():
    """And it is the notifier, because its whole input is the session bus and
    a D-Bus client is therefore the whole of its world. The other two would
    need a broker and a compositor this gate deliberately does not start —
    which is the limit the header states and this pins."""
    woken = [s.attr for s in shells.SHELLS if s.wake]
    assert woken == ["jv-notify"]


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
    were."""
    whole = shells.usable_areas(0)
    assert whole == {
        out["name"]: (out["width"], out["height"]) for out in shells.OUTPUTS
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
    assert whens == [("before", "False"), ("while", "True"), ("after", "False")], whens


def test_the_monitors_the_compositor_really_has_are_checked_before_any_shell():
    """The floor under everything else. `WLR_HEADLESS_OUTPUTS=3` and the
    `output` lines in the config are both REQUESTS; until D44 nothing read the
    answer, and a run that got one output would have loaded one delegate per
    shell, scanned one surface's worth of log and reported that all three
    shells load.

    Before any shell, because the alternative is three identical failures
    underneath the one that explains them."""
    text = DRIVER.read_text("utf-8")
    assert text.index("check_outputs()") < text.index("for shell in shells.SHELLS")
    assert '"-t", "get_outputs"' in text


def test_the_gate_still_costs_seconds_and_not_minutes():
    """The whole argument for this being a step rather than a named command.
    The compositor is polled, and a poll with a generous timeout is how a 25 s
    gate becomes a 3-minute one — so the ceiling is bounded and small, and the
    worst case is one timeout per reading per shell."""
    worst = shells.MAPPED_TIMEOUT_S * 3 * len(shells.SHELLS)
    assert worst <= 90, worst
    assert 0 < shells.MAPPED_POLL_S <= 0.25


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


def test_the_gate_does_not_read_the_broker_it_never_starts():
    """The deliberate narrowing. Nothing here starts a jarvisd — the HUD runs
    blind, which is the header's second limit — so a change to the bus cannot
    move this verdict, and binding it would spend these seconds on every Rust
    edit to learn that."""
    got = dependents.commands(ROOT, ["services/jarvisd/src/main.rs"])
    assert "bash ops/ralph/shellload.sh" not in got, sorted(got)
