"""The screen sheet is the real HUD, or it is a very convincing lie.

`ops/ralph/hudscreens.sh` photographs the shipped `jv-hud` on a real
compositor with ares' three monitors (PLAN A30). Its whole value over the
contact sheet in `docs/hud` is that NOTHING is staged: no stub singletons,
no rebuilt plate stack, no second copy of anything. A future edit that
quietly stages a file — the obvious way to make a stubborn run go green —
would take that value away while every picture still looked perfect.

These are the gates on that, plus the ordinary drift gates: a shot the
harness takes and nobody committed is a shot nobody can look at, and a
committed PNG the harness no longer takes is a picture of a HUD that no
longer exists.

The pixel-level claims — the corner, the focus, the emptiness, and the
click that has to reach the window underneath (A32) — are NOT here. They
need a compositor, so they live in tools/hudscreens/shoot.py and run when
the sheet is made. What IS here is everything that would make those checks
run against the wrong machine, or not run at all.
"""

import re
import sys
from pathlib import Path

from test_gen_theme_qml import ROOT

sys.path.insert(0, str(ROOT / "tools" / "hudscreens"))
import sheet  # noqa: E402

SCREENS = ROOT / "docs" / "hud" / "screens"
DRIVER = ROOT / "ops" / "ralph" / "hudscreens.sh"


def driver_text() -> str:
    return DRIVER.read_text("utf-8")


def test_every_screen_the_harness_takes_is_committed_and_vice_versa():
    """An uncommitted screen is one nobody can look at without a compositor;
    an orphan is a picture of a HUD that no longer exists. Both are the
    sheet quietly ceasing to be the sheet.
    """
    declared = sheet.all_files()
    assert declared, "the sheet declares no shots at all"
    committed = sorted(p.name for p in SCREENS.glob("*.png"))
    assert sorted(declared) == committed, (
        f"the harness takes {sorted(declared)} and docs/hud/screens holds "
        f"{committed} — run bash ops/ralph/hudscreens.sh and commit the result"
    )


def test_the_harness_photographs_the_shipped_binary_and_stages_nothing():
    """The one claim this sheet makes that the contact sheet cannot: the
    thing in the picture is the thing a `nixos-rebuild switch` installs.
    A staging copy would make a broken run easy to fix and the pictures
    worthless, and it would not look like a regression in any diff.
    """
    text = driver_text()
    assert 'nix build "$root#jv-hud"' in text, (
        "ops/ralph/hudscreens.sh no longer builds .#jv-hud — if it is running "
        "anything else, it is not photographing the HUD that ships"
    )
    # Comments may name shell/jv-hud all they like; this is about what the
    # script DOES. Anything that copies, links or overlays a QML file is a
    # staged HUD wearing the shipped one's name.
    code = [
        line
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    for line in code:
        for staging in ("cp ", "ln -s", "shell/jv-hud", "share/jv-hud"):
            assert staging not in line, (
                f"ops/ralph/hudscreens.sh runs {line.strip()!r}: the whole point "
                "of this harness is that it stages nothing and stubs nothing. If "
                "a file really has to be substituted, it belongs in the hudshots "
                "sheet, which says so on every page."
            )


def test_the_harness_never_sets_the_self_test():
    """`JV_HUD_SELFTEST=1` maps a marker whatever the bus says. A sheet
    taken with it on would show a surface on every monitor and prove
    nothing at all about whether a real frame put it there — and the quiet
    shot, the control for every other measurement, would be a picture of
    the marker.
    """
    assert "JV_HUD_SELFTEST" not in driver_text(), (
        "ops/ralph/hudscreens.sh sets JV_HUD_SELFTEST, so the surface maps "
        "whether or not the bus gave it anything to say"
    )


def test_the_monitors_are_ares_monitors():
    """CLAUDE.md: 2560x1440 primary plus two 1920x1080. If the sheet ever
    quietly shrinks to one small screen, every corner measurement in
    shoot.py still passes and the one question A13/A27 asked — what three
    monitors look like — stops being asked.
    """
    sizes = sorted((o["width"], o["height"]) for o in sheet.OUTPUTS)
    assert sizes == [(1920, 1080), (1920, 1080), (2560, 1440)], (
        f"tools/hudscreens/sheet.py declares {sizes}, which is not ares"
    )
    # Side by side, no overlap and no gap: the desk shot is one grim
    # capture across the whole layout, and an overlap would photograph one
    # monitor twice.
    x = 0
    for out in sheet.OUTPUTS:
        assert out["x"] == x, f"{out['name']} starts at {out['x']}, expected {x}"
        x += out["width"]
    assert sheet.DESK_WIDTH == x


def test_at_least_one_shot_is_dark_and_at_least_one_is_lit():
    """The measurements are two-sided and both sides are needed. Without a
    lit shot nothing proves the HUD ever draws; without a dark one nothing
    proves it ever stops — and a harness whose bus never reached the HUD
    would sail through a sheet made only of dark shots.
    """
    lit = [s["file"] for s in sheet.SHOTS if s["lit"]]
    dark = [s["file"] for s in sheet.SHOTS if not s["lit"]]
    assert lit, "no shot lights the HUD: nothing here proves a frame ever arrived"
    assert dark, "no shot leaves the HUD dark: nothing here proves earned emptiness"


def test_a_lit_shot_is_photographed_on_every_monitor():
    """A13 and A27 are questions about THREE screens. A sheet of
    single-monitor crops answers neither, however good the crops are.
    """
    desks = [s["file"] for s in sheet.SHOTS if s["lit"] and "desk" in s["captures"]]
    assert desks, (
        "no lit shot captures the whole desk — the one thing this sheet exists "
        "to show is the same plate on all three monitors at once"
    )


def test_the_backdrop_is_not_one_of_jarviss_colours():
    """The grey behind the HUD is the photograph's, not Jarvis's — the real
    surface is transparent. Same rule the contact sheet lives by, and the
    same reason: a reader must never have to wonder whether a colour on
    screen came from personality/theme.toml.
    """
    palette = {
        c.upper()
        for c in re.findall(
            r'^\s*\w+\s*=\s*"(#[0-9A-Fa-f]{6})"',
            (ROOT / "personality" / "theme.toml").read_text("utf-8"),
            re.M,
        )
    }
    assert sheet.BACKDROP.upper() not in palette, (
        f"the sheet's backdrop {sheet.BACKDROP} is a personality/theme.toml "
        "colour, so the paper and the HUD are now the same thing"
    )


def test_the_two_sheets_photograph_the_hud_on_the_same_paper():
    """docs/hud and docs/hud/screens are read one after the other. Two
    different greys would read as two different HUDs, and the reader would
    have no way to know which difference was Jarvis's.
    """
    scene = (ROOT / "tools" / "hudshots" / "scene" / "tst_shots.qml").read_text("utf-8")
    other = re.search(r'property color backdrop:\s*"(#[0-9A-Fa-f]{6})"', scene)
    assert other, "the contact sheet no longer declares a single backdrop colour"
    assert other.group(1).upper() == sheet.BACKDROP.upper(), (
        f"the contact sheet's paper is {other.group(1)} and the screens' is "
        f"{sheet.BACKDROP}"
    )


def test_the_surface_box_is_the_one_shell_qml_declares():
    """shoot.py measures every monitor against this box. If shell.qml grows
    its surface and the sheet does not hear about it, the check gets looser
    than the thing it is checking and stops being a check.
    """
    shell = (ROOT / "shell" / "jv-hud" / "shell.qml").read_text("utf-8")
    width = re.search(r"^\s*implicitWidth:\s*(\d+)", shell, re.M)
    height = re.search(r"^\s*implicitHeight:\s*(\d+)", shell, re.M)
    assert width and height, "shell.qml no longer declares a fixed surface box"
    assert (int(width.group(1)), int(height.group(1))) == (
        sheet.SURFACE_W,
        sheet.SURFACE_H,
    ), (
        f"shell.qml's surface is {width.group(1)}x{height.group(1)} and "
        f"sheet.py measures against {sheet.SURFACE_W}x{sheet.SURFACE_H}"
    )


def test_the_inset_is_the_one_the_theme_declares():
    """Same failure, one level down: the right-hand gap shoot.py measures is
    `geometry.inset_px`, and a theme that moved it would leave the check
    asserting yesterday's edge.
    """
    toml = (ROOT / "personality" / "theme.toml").read_text("utf-8")
    inset = re.search(r"^\s*inset_px\s*=\s*(\d+)", toml, re.M)
    assert inset, "personality/theme.toml no longer declares inset_px"
    assert int(inset.group(1)) == sheet.INSET, (
        f"theme.toml insets by {inset.group(1)}px and sheet.py measures "
        f"{sheet.INSET}px"
    )


def test_the_readme_says_which_screens_are_recordings_and_which_are_written():
    """Some frames are the committed recordings and some are written by
    hand, because nothing in the repo has ever recorded jv-voice speaking
    or jv-act asking (B10/A28). Blurring the two would let a composed
    picture be read as evidence about the machine — the one thing a
    photograph of a HUD must never do.
    """
    readme = (SCREENS / "README.md").read_text("utf-8")
    sections = readme.split("\n### ")
    for shot in sheet.SHOTS:
        for name in sheet.capture_files(shot):
            shown = [s for s in sections if name in s]
            assert shown, f"docs/hud/screens/README.md never shows {name}"
            assert len(shown) == 1, (
                f"docs/hud/screens/README.md shows {name} in {len(shown)} sections"
            )
            assert re.search(r"\b(recorded|composed)\b", shown[0].lower()), (
                f"docs/hud/screens/README.md shows {name} without saying whether "
                "its frames are recorded or composed"
            )


def test_the_compositor_never_follows_the_mouse():
    """The click probe (A32) warps the cursor and then presses a button.
    With focus-follows-mouse on, the WARP could move focus by itself and
    every click would look like it had been routed through the HUD — the
    probe would pass on a surface that eats input.
    """
    assert "focus_follows_mouse no" in sheet.sway_config(), (
        "the harness compositor follows the mouse, so the click probe can no "
        "longer tell a routed button from a cursor that merely moved"
    )


def test_the_compositor_is_given_the_monitors_the_sheet_declares():
    """One source for ares' monitors. A config that drifted from
    `sheet.OUTPUTS` would leave every geometric check measuring a screen
    the compositor does not have.
    """
    config = sheet.sway_config()
    for out in sheet.OUTPUTS:
        line = (
            f"output {out['name']} mode {out['width']}x{out['height']} "
            f"pos {out['x']} 0"
        )
        assert line in config, f"the compositor is never told about {line!r}"


def test_the_driver_takes_its_compositor_config_from_the_sheet():
    """...and takes it from there rather than writing a second copy, which
    is the only way the check above means anything.
    """
    assert "sheet.sway_config()" in driver_text(), (
        "ops/ralph/hudscreens.sh builds its own sway config, so the compositor "
        "the checks describe and the one they run on can drift apart"
    )


def test_the_click_probe_has_a_second_client_to_pass_through_to():
    """`mask: Region {}` is a claim about a window UNDERNEATH the HUD, so
    it cannot be measured without one. If the driver stops realizing a
    client, the probe has nothing to click onto.
    """
    driver = driver_text()
    assert "nixpkgs wev" in driver and "WEV_BIN" in driver, (
        "ops/ralph/hudscreens.sh no longer provides a second Wayland client, "
        "so A32's pass-through has nothing to pass through to"
    )
    shoot = (ROOT / "tools" / "hudscreens" / "shoot.py").read_text("utf-8")
    assert 'os.environ["WEV_BIN"]' in shoot, "shoot.py never starts that client"


def test_the_click_probe_actually_runs():
    """A measurement that is defined and never called is the most
    convincing kind of missing check: it reads as covered in every diff.
    """
    shoot = (ROOT / "tools" / "hudscreens" / "shoot.py").read_text("utf-8")
    body = shoot.split("\ndef main(")[-1]
    assert "probe_click_through(" in body, (
        "tools/hudscreens/shoot.py defines the click probe but main() never "
        "runs it, so the empty input mask is unmeasured again"
    )


def test_the_readme_says_what_the_click_probe_proved_and_what_it_did_not():
    """The probe's witness is sway's routing, not the client's own
    wl_pointer — a headless seat has no pointer capability. A reader who
    took it for the stronger claim would over-trust it, which is exactly
    the failure every other page of this sheet is written against.
    """
    readme = (SCREENS / "README.md").read_text("utf-8")
    assert "mask: Region {}" in readme, (
        "docs/hud/screens/README.md no longer says the empty input mask is "
        "measured here"
    )
    assert "wl_pointer" in readme, (
        "docs/hud/screens/README.md claims the click reaches the window "
        "without saying that no client ever received a pointer event — the "
        "witness is sway's routing, and the difference matters"
    )


# ------------------------------------------------------------- the idle probe
#
# "0 fps when idle" (invariant 10, §06) is the only invariant-10 claim that
# is about COST rather than behaviour, and until A34 it was the last one
# resting on an argument rather than a number. `probe_idle_frames` counts
# the HUD's own Wayland commits over two windows — a quiet bus with the
# surface unmapped, and a plate on screen with nothing new to say — and
# both must come back zero.
#
# The danger in a probe that passes on zero is that EVERY way of breaking
# it also returns zero: a regex that stops matching a new libwayland
# format, an env var that stops being set, a log that is no longer the
# HUD's. So the probe carries a control in each window, and these tests
# hold the two things a control cannot: that the counter counts real log
# lines, and that the probe is still called at all.

# Verbatim from a real run of this harness: the fade-in of one plate, on
# one of the three surfaces. Kept as text on purpose — it is the thing the
# counter has to survive, and a hand-idealised line would not be.
REAL_WAYLAND_LOG = """\
[06:36:34.125153]  -> wl_surface#41.frame(new id wl_callback#58)
[06:36:34.125166] {mesa egl surface queue}  -> wl_surface#41.attach(wl_buffer#49, 0, 0)
[06:36:34.125171] {mesa egl surface queue}  -> wl_surface#41.damage_buffer(0, 0, 2147483647, 2147483647)
[06:36:34.125383] {mesa egl surface queue}  -> wl_surface#41.commit()
[06:36:34.126367]  -> wl_surface#45.frame(new id wl_callback#59)
[06:36:34.126602] {mesa egl surface queue}  -> wl_surface#45.commit()
[06:36:34.140288]  -> wl_surface#35.frame(new id wl_callback#56)
[06:36:34.140457] {mesa egl surface queue}  -> wl_surface#35.commit()
"""

# The same traffic as older libwayland printed it. The build under this
# harness can change without anyone choosing to change it.
OLD_WAYLAND_LOG = """\
[3282897.348]  -> wl_surface@41.frame(new id wl_callback@58)
[3282897.349]  -> wl_surface@41.commit()
"""


def test_the_frame_counter_counts_a_real_wayland_log():
    """The instrument, over the lines it will actually be given. If this
    drifts, the probe reports a perfect zero for a HUD rendering at 60 fps
    — which is worse than not measuring at all.
    """
    assert sheet.surface_traffic(REAL_WAYLAND_LOG) == (3, 3)
    assert sheet.surface_traffic(OLD_WAYLAND_LOG) == (1, 1)


def test_the_frame_counter_counts_surfaces_and_not_everything_else():
    """A commit is a frame reaching the screen. The other objects on that
    socket commit too — a subsurface's parent, a cursor, an output's
    configuration round trip — and counting those would make the idle
    windows fail for reasons that are not rendering.
    """
    assert sheet.surface_traffic("[1]  -> xdg_surface#12.commit()\n") == (0, 0)
    assert sheet.surface_traffic("[1]  -> wl_surface#12.destroy()\n") == (0, 0)
    assert sheet.surface_traffic("[1] wl_callback#58.done(1234)\n") == (0, 0)


def test_the_idle_probe_actually_runs():
    """A measurement that is defined and never called is the most
    convincing kind of missing check: it reads as covered in every diff.
    """
    shoot = (ROOT / "tools" / "hudscreens" / "shoot.py").read_text("utf-8")
    body = shoot.split("\ndef main(")[-1]
    assert "probe_idle_frames(" in body, (
        "tools/hudscreens/shoot.py defines the idle probe but main() never "
        "runs it, so '0 fps when idle' is unmeasured again"
    )


def test_the_idle_probe_reads_the_huds_own_wayland_log():
    """WAYLAND_DEBUG is how the HUD is made to say what it committed. With
    it unset the log is empty, every window reads zero, and the probe
    passes for a HUD animating on all three monitors.
    """
    shoot = (ROOT / "tools" / "hudscreens" / "shoot.py").read_text("utf-8")
    probe = shoot.split("\ndef probe_idle_frames(")[-1].split("\ndef ")[0]
    assert probe.count('WAYLAND_DEBUG="1"') == 2, (
        "every jv-hud the idle probe starts must be started with "
        "WAYLAND_DEBUG=1, or the frames it is counting are not being logged"
    )
    assert "WAYLAND_DEBUG" not in shoot.replace(probe, ""), (
        "WAYLAND_DEBUG is set outside the idle probe — the photographs "
        "should be of a HUD doing its job, not one writing a protocol log"
    )


def test_each_idle_window_has_a_control():
    """Both windows pass on zero, and so does a probe that is reading
    nothing at all. Each one is therefore paired with a stretch that MUST
    contain commits, counted the same way through the same log: the HUD
    being woken by a real frame after the quiet window, and the blind
    plate arriving before the lit one.
    """
    shoot = (ROOT / "tools" / "hudscreens" / "shoot.py").read_text("utf-8")
    probe = shoot.split("\ndef probe_idle_frames(")[-1].split("\ndef ")[0]
    assert "if not woke:" in probe and "if not arriving:" in probe, (
        "the idle probe no longer insists on SEEING commits somewhere, so a "
        "broken instrument — an unset WAYLAND_DEBUG, a libwayland that "
        "renamed its objects — would report a flawless permanent zero"
    )
    assert probe.count("sheet.surface_traffic(") == 4, (
        "the controls have to be measured by the same counter as the windows "
        "they vouch for, or they vouch for nothing"
    )


def test_the_readme_says_what_the_idle_probe_proved_and_what_it_did_not():
    """§06 budgets the ambient scene at "< 2 ms of GPU per frame AND 0 fps
    when idle". This harness is pixman on a headless backend and can only
    answer the second half; a reader who took it for the first would think
    the GPU budget had been measured on a 1660 SUPER.
    """
    readme = (SCREENS / "README.md").read_text("utf-8")
    assert "0 fps" in readme, (
        "docs/hud/screens/README.md no longer says the idle frame count is "
        "measured here"
    )
    assert "pixman" in readme, (
        "docs/hud/screens/README.md claims the HUD costs nothing when idle "
        "without saying that no GPU millisecond was measured — this "
        "compositor renders in software and its timings are about no machine"
    )
