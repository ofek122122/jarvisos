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
    # And the wait is not optional for any engine: one `load` for the three
    # shells, one `load_blind` for the HUD's second run (PLAN D47), and one
    # wait on READY inside each.
    assert text.count("def load(") == 1
    assert text.count("def load_blind(") == 1
    assert text.count("proc.wait_for(shells.READY") == 2


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
    triple = [("before", "False"), ("while", "True"), ("after", "False")]
    # Twice, once per run: the blind HUD (PLAN D47) is a fourth engine on the
    # same compositor, and its readings need the same two controls — more so,
    # because it is the run in which the HUD's surface really is mapped.
    assert whens == triple * 2, whens


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


def engine_ceilings() -> dict[str, float]:
    """The worst case of every wait ONE engine of this gate can spend.

    Per engine, which is D50's repair of a test that summed the whole run into
    a single number. Two things were wrong with the sum. It broke on the next
    honest addition rather than on a cost problem — D47 took it from 136 to 148
    against a limit of 150, so the D49 relink would have read as expensive when
    it is nine seconds of waiting on a corner. And what it summed was not the
    worst case: `READY_TIMEOUT_S` was left out entirely, which is 30 s per
    engine of pathological wait — a quickshell that maps nothing and says
    nothing is exactly the run a ceiling exists for, and it was the one run the
    ceiling did not cover.

    Stated as an argument about ONE ENGINE because that is the claim that stays
    true as runs are added: this gate starts a fresh quickshell per reading, and
    no one of them may hang for minutes.
    """
    # Every engine pays for these: the load, and the three compositor readings
    # around it (before / while / after, PLAN D44).
    base = shells.READY_TIMEOUT_S + shells.MAPPED_TIMEOUT_S * 3
    out = {shell.attr: base for shell in shells.SHELLS}
    # The frames run waits for the publisher's first round and then for the
    # corner to name ten plates.
    out[shells.hud_shell().attr] = base + shells.HUD_LIT_TIMEOUT_S * 2
    # And the blind run waits out the grace, then the socket, then the corner
    # going dark again (PLAN D49).
    out[shells.HUD_BLIND_LOG] = (
        base
        + shells.HUD_BLIND_TIMEOUT_S
        + shells.HUD_RELINK_BUS_TIMEOUT_S
        + shells.HUD_RELINK_TIMEOUT_S
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
    # And the frames go out faster than the plate that needs them goes stale,
    # or the ceiling above is spent waiting for a corner that keeps dimming.
    assert 0 < shells.HUD_ROUND_S <= 1.0


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
        for out in shells.OUTPUTS[:-1]
    )
    for out in shells.OUTPUTS[:-1]:
        assert shells.hud_corner_plates(said, out["name"]) == list(
            shells.HUD_PLATES_LIT
        ), out["name"]
    missed = shells.OUTPUTS[-1]["name"]
    assert shells.hud_corner_plates(said, missed) is None, missed
    driver = code_lines(DRIVER)
    assert "for out in shells.OUTPUTS" in driver


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
    text = DRIVER.read_text("utf-8")
    blind = text[text.index("def load_blind("):text.index("def main(")]
    found = re.search(r"env = dict\(os\.environ, (\w+)=([^)]+)\)", blind)
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
    assert driver.count("shells.HUD_BLIND_BUS") == 2


def test_the_blind_corner_must_name_the_dark_plate_and_nothing_else():
    """The stronger half of what this run proves. Every state machine under
    this corner is built to REFUSE rather than guess from a bus it cannot see,
    and a refusal draws the same nothing a calm machine does — so no picture
    can tell them apart. A corner naming exactly `link` can: a plate that had
    started guessing would be named beside it."""
    text = DRIVER.read_text("utf-8")
    blind = text[text.index("def load_blind("):text.index("def main(")]
    assert "list(shells.HUD_PLATES_DARK)" in blind
    assert "HUD_PLATES_LIT" not in blind
    # The two lists cannot overlap, or the expectation is unsatisfiable in one
    # of the two runs.
    assert not set(shells.HUD_PLATES_LIT) & set(shells.HUD_PLATES_DARK)


def test_every_reading_of_the_corner_is_the_same_reading():
    """One census, three callers. The way a corner is READ — newest line per
    monitor, every monitor, exact order — is the same question whether there are
    ten plates on it, one, or none, and two copies of it would be two answers.
    The third caller is D49's: the same blind HUD once the bus arrives."""
    text = DRIVER.read_text("utf-8")
    assert text.count("def corner_census(") == 1
    assert text.count("corner_census(") == 4  # the definition and three callers


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
    # And nothing on this broker publishes a frame, so no other plate has
    # anything to say: the publisher is the frames run's alone.
    relink = DRIVER.read_text("utf-8")
    relink = relink[relink.index("def relink(") :]
    assert "PUBLISH" not in relink
    assert "HUD_FRAMES" not in relink


def test_the_empty_corner_is_only_read_after_the_hud_said_it_was_blind():
    """What makes that reading mean anything. An empty corner is also what a HUD
    that never lit a plate looks like — so this only counts because the blind
    census has already required the NEWEST line on every monitor to be `link`,
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
    relink = DRIVER.read_text("utf-8")
    relink = relink[relink.index("def relink(") :]
    assert "broker.tail(" in relink


def test_the_late_broker_is_stopped_by_the_driver_that_started_it():
    """The script's trap only knows the pids it started. A broker left holding
    a socket in a directory about to be deleted is the shape of a leak this
    harness has had before, so it is stopped in a `finally` like the publisher —
    on the failing path too, which is the one that matters."""
    relink = DRIVER.read_text("utf-8")
    relink = relink[relink.index("def relink(") :]
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


def test_the_blind_run_is_counted_in_the_verdict_and_not_only_logged():
    """`load_blind` raising has to be a non-zero exit, like any shell that
    did not load — a run that reported its failure and returned 0 is the shape
    of a gate that quietly stopped asking half its question."""
    text = DRIVER.read_text("utf-8")
    after = text[text.index("load_blind(stage)", text.index("def main(")):]
    assert "bad += 1" in after[: after.index("if bad:")]
