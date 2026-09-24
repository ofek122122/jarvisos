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
    assert probe.count('WAYLAND_DEBUG="1"') == 4, (
        "every jv-hud the idle probe starts must be started with "
        "WAYLAND_DEBUG=1, or the frames it is counting are not being logged"
    )
    assert "WAYLAND_DEBUG" not in shoot.replace(probe, ""), (
        "WAYLAND_DEBUG is set outside the idle probe — the photographs "
        "should be of a HUD doing its job, not one writing a protocol log"
    )


def test_each_idle_window_has_a_control():
    """Every window passes on zero, and so does a probe that is reading
    nothing at all. Each one is therefore paired with a stretch that MUST
    contain commits, counted the same way through the same log: the HUD
    being woken by a real frame after the quiet window, the blind plate
    arriving before the lit one, and a second plate arriving under the
    first in each of the two live-lit ones.
    """
    shoot = (ROOT / "tools" / "hudscreens" / "shoot.py").read_text("utf-8")
    probe = shoot.split("\ndef probe_idle_frames(")[-1].split("\ndef ")[0]
    assert (
        "if not woke:" in probe
        and "if not arriving:" in probe
        and probe.count("if not lighting:") == 2
    ), (
        "the idle probe no longer insists on SEEING commits somewhere, so a "
        "broken instrument — an unset WAYLAND_DEBUG, a libwayland that "
        "renamed its objects — would report a flawless permanent zero"
    )
    assert probe.count("sheet.surface_traffic(") == 8, (
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


# --------------------------------------------- the live-lit window (A42)
#
# A34's lit window could only be held still by `LinkPlate` with NO BUS AT
# ALL, because every other lit state in this HUD is a frame ageing out. So
# "0 fps with a plate on screen" had, for two iterations, only ever been
# measured on a HUD that could see nothing — and a HUD that can see nothing
# is a HUD with nothing arriving to make it re-render. The interesting
# question was never asked: a mapped surface, a live bus, a frame a second,
# and nothing on screen changing.
#
# A40's `OutputState` made it possible, because it is a LIVE READING of two
# topics rather than a latch. These gates hold the two ways that window can
# go vacuous without looking wrong: losing its broker (back to A34's
# measurement under a new name), or letting the plate expire mid-window
# (a zero that is about an unmapped surface again).


def idle_probe_text() -> str:
    shoot = (ROOT / "tools" / "hudscreens" / "shoot.py").read_text("utf-8")
    return shoot.split("\ndef probe_idle_frames(")[-1].split("\ndef ")[0]


def idle_window_text(title: str) -> str:
    """ONE window's source, and not the rest of the probe.

    These gates are greps, and a grep over the whole function is a gate
    that any other window can satisfy on a window's behalf: A43 added a
    fourth one that also starts a broker and also calls `feed_snapshots`,
    and every check written as "somewhere after the words LIVE AND LIT"
    quietly became true of it instead. The windows announce themselves
    with a `# --- TITLE:` banner, so slice on that and let a window that
    lost its banner fail loudly rather than borrow its neighbour's.
    """
    for chunk in idle_probe_text().split("\n    # --- ")[1:]:
        if chunk.startswith(title + ":"):
            return chunk
    raise AssertionError(
        f"the idle probe has no window announcing itself as `# --- {title}:` "
        "— either it was removed or its banner was renamed, and every gate "
        "below it was about to grep a different window"
    )


def test_the_live_lit_window_feeds_the_pair_that_actually_keeps_a_plate_lit():
    """core/OutputState.qml draws only while jv-voice is speaking AND the
    default sink is silent. Either frame wrong and the window measures a
    bare desktop while reporting a triumphant zero — which is A34's quiet
    window with more machinery in front of it.
    """
    assert sheet.VOICE_SPEAKING["publish"]["topic"] == "speech.state"
    assert sheet.VOICE_SPEAKING["publish"]["src"] == "jv-voice", (
        "core/OutputState.qml reads speech.state from jv-voice; a frame under "
        "another src is not one the HUD will believe"
    )
    assert sheet.VOICE_SPEAKING["publish"]["body"]["state"] == "speaking", (
        "the live-lit window needs an utterance IN FLIGHT — `idle` and "
        "`interrupted` both draw nothing, so the plate would never light"
    )
    assert sheet.SINK_MUTED["publish"]["topic"] == "context.system"
    assert sheet.SINK_MUTED["publish"]["src"] == "jv-context"
    assert sheet.SINK_MUTED["publish"]["body"]["audio_muted"] is True, (
        "the live-lit window's snapshot is no longer muted, so OutputPlate "
        "has nothing to say and the window is measuring an unmapped surface"
    )
    beat = sheet.VOICE_DEFAULT_SINK["publish"]
    assert beat["src"] == "jv-voice" and beat["body"]["service"] == "jv-voice", (
        "only the service that does the playing can say which device the "
        "samples land on; core/OutputState.qml reads the gauge by name"
    )
    assert beat["body"]["metrics"]["output_device_pinned"] == 0, (
        "the live-lit window tells the HUD jv-voice PINNED a device, which "
        "is exactly the case A41 added to silence the plate — the window "
        "would be measuring an unmapped surface"
    )
    # And the quiet window's snapshot must stay the opposite of it, or that
    # window stops being about a HUD with nothing to say.
    assert sheet.SINK_OK["publish"]["body"]["audio_muted"] is False, (
        "the quiet window's snapshot is muted, so the HUD now has something "
        "true to say during a window that insists it draws nothing"
    )


def test_both_live_lit_frames_are_legal_bodies_for_their_topics():
    """`schemas/` is bus law (invariant 2) and a harness that publishes an
    illegal body is measuring a machine that cannot exist. Checked here
    rather than trusted, because these two frames are hand-written.
    """
    import json

    for frame in (sheet.VOICE_SPEAKING, sheet.SINK_MUTED, sheet.VOICE_DEFAULT_SINK):
        spec = frame["publish"]
        schema = json.loads(
            (ROOT / "schemas" / f"{spec['topic']}.json").read_text("utf-8")
        )
        body = spec["body"]
        missing = set(schema["required"]) - set(body)
        assert not missing, f"{spec['topic']}: body is missing {sorted(missing)}"
        extra = set(body) - set(schema["properties"])
        assert not extra, f"{spec['topic']}: body has unknown keys {sorted(extra)}"
    enum = json.loads(
        (ROOT / "schemas" / "speech.state.json").read_text("utf-8")
    )["properties"]["state"]["enum"]
    assert sheet.VOICE_SPEAKING["publish"]["body"]["state"] in enum


def test_the_live_lit_window_runs_on_a_real_broker():
    """The whole point of it. A34's lit window starts NO jarvisd, on
    purpose — it needs a state that cannot expire, and a bus the HUD cannot
    see is the only one it says forever. This window's claim is the
    opposite: a HUD that is receiving frames the entire time still renders
    nothing. Without a broker it is A34's window again.
    """
    probe = idle_probe_text()
    live = idle_window_text("LIVE AND LIT")
    assert "LIVE AND LIT" in probe, (
        "the idle probe no longer has a live-lit window, so '0 fps with a "
        "plate on screen' is once again only measured on a HUD with no bus"
    )
    assert "JARVISD_BIN" in live, (
        "the live-lit window starts no jarvisd — a HUD with no bus is A34's "
        "lit window, and the thing this one exists to add is the traffic"
    )
    assert "sheet.VOICE_SPEAKING" in live and "sheet.SINK_MUTED" in live, (
        "the live-lit window no longer publishes the pair that lights "
        "OutputPlate, so whatever it is measuring is not a lit HUD"
    )
    assert "sheet.VOICE_DEFAULT_SINK" in live, (
        "the live-lit window no longer tells the HUD that jv-voice plays "
        "into the default sink (A41), so OutputPlate stays dark and the "
        "window measures StatePlate alone"
    )


def test_the_live_lit_window_keeps_feeding_and_proves_the_plate_stayed():
    """The sneakiest way for this window to report a perfect zero: stop
    feeding. core/OutputState.qml believes one 1 Hz snapshot for three of
    its own periods, so a window that publishes once and then waits six
    seconds watches the plate leave — and an unmapped surface commits
    nothing, which is exactly the zero the probe was hoping for.

    Two things stop that: the feed runs FOR the length of the window, and
    the drawn box is re-measured afterwards and must be identical.
    """
    probe = idle_probe_text()
    live = idle_window_text("LIVE AND LIT")
    assert "feed_snapshots(" in live, (
        "the live-lit window no longer publishes for the length of the "
        "window; OutputState stops believing a snapshot after three of "
        "jv-context's periods and the plate would expire under it"
    )
    assert re.search(r"IDLE_WINDOW_S,\s*muted", live), (
        "the live-lit window's feed no longer covers the measured window"
    )
    assert re.search(r"muted = \[sheet\.VOICE_DEFAULT_SINK, sheet\.SINK_MUTED\]", live), (
        "the live-lit window's feed no longer re-publishes jv-voice's "
        "heartbeat, so HealthState calls it lost two of its periods in and "
        "HealthPlate arrives under the plate being held still"
    )
    assert "if after != box:" in live, (
        "the live-lit window no longer re-measures the plate after the "
        "window, so a plate that expired mid-measurement would report a "
        "zero about an unmapped surface"
    )


def test_the_live_lit_window_proves_it_is_holding_the_output_plate():
    """`StatePlate` has said SPEAKING since A3 and lights on the jv-voice
    frame alone, so "something is drawn" is not evidence that A40's plate
    is on screen. A window holding only StatePlate still would report the
    very same zero while OutputPlate went unmeasured — and OutputPlate is
    the entire reason this window can exist on a live bus.

    So the probe lights it in two steps: an AUDIBLE sink first (StatePlate
    and nothing else), then the mute, and the drawn region has to grow
    downwards from the same top-left corner. That is a plate arriving
    UNDER another one, measured in pixels.
    """
    live = idle_window_text("LIVE AND LIT")
    assert "sheet.SINK_OK" in live, (
        "the live-lit window no longer lights StatePlate on an audible sink "
        "first, so nothing distinguishes 'OutputPlate arrived' from 'the HUD "
        "drew the word SPEAKING'"
    )
    assert "speaking_box" in live, (
        "the live-lit window no longer measures the HUD before the mute, so "
        "there is nothing for the lit one to have grown from"
    )
    # The rule itself — top and right pinned, bottom grown, left free to
    # travel outwards — is `sheet.grew_downwards`, and
    # test_the_growth_rule_is_the_geometry_the_stack_actually_has runs it
    # rather than grepping for it. What is asserted here is only that this
    # window still asks.
    assert "sheet.grew_downwards(speaking_box, box)" in live, (
        "the live-lit window no longer insists the drawn region GREW when the "
        "sink went muted — whatever it holds still for six seconds may not "
        "include OutputPlate at all"
    )


def test_the_readme_says_which_windows_were_on_a_live_bus():
    """The distinction is the whole value of those windows, and it is the
    one a reader will otherwise collapse: two of these zeros are from a HUD
    that could see nothing happening, and two are from a HUD watching a
    frame arrive every second. Naming the plates is what makes the
    difference legible — a zero is a zero either way.
    """
    readme = (SCREENS / "README.md").read_text("utf-8")
    assert "four" in readme.lower(), (
        "docs/hud/screens/README.md still describes three idle windows"
    )
    assert "OUTPUT MUTED" in readme, (
        "docs/hud/screens/README.md does not say which plate the live-lit "
        "window held on screen — without it a reader cannot tell whether "
        "the measurement was of a HUD with a bus or without one"
    )
    assert "MIC NO AUDIO" in readme, (
        "docs/hud/screens/README.md does not say which plates A43's window "
        "held on screen, so a reader cannot tell it apart from the one "
        "above it"
    )


# ------------------------------------- the fourth window: mic and health (A43)
#
# A42's window measures `StatePlate` and `OutputPlate`. Four plates were
# left that had never been watched standing still at all, and two of them
# come cheap: ONE jv-ears heartbeat says both `MIC NO AUDIO` (an open
# device delivering nothing) and `jv-ears DEGRADED` (the service's own word
# for itself), so re-publishing that single frame holds both.
#
# It can go vacuous in a way none of the three above can, which is why
# there is a gate for it here. Those plates believe a heartbeat for two of
# its `period_s` — jv-ears declares 5 — so they outlive a six-second
# silence on their own. A feed that stopped would leave the picture intact
# and turn this back into A34's lit window without failing anything.


def mic_and_health() -> str:
    return idle_window_text("MIC AND HEALTH")


def test_the_mic_and_health_window_runs_on_a_real_broker():
    """Same claim as the window above and the same way of losing it. With
    no jarvisd there is nothing arriving, and "a plate on screen and
    nothing happening" is a measurement A34 already made.
    """
    window = mic_and_health()
    assert "JARVISD_BIN" in window, (
        "A43's window starts no jarvisd — a HUD with no bus is A34's lit "
        "window, and the traffic is the thing this one exists to add"
    )
    assert "sheet.MIC_DEAF" in window and "sheet.MIC_OPEN" in window, (
        "A43's window no longer publishes the heartbeats that light the mic "
        "and health plates, so whatever it measures is not those two plates"
    )


def test_the_two_heartbeats_light_exactly_the_plates_the_window_claims():
    """The window's whole design rests on one coincidence: a device that is
    open and silent is a MicPlate line AND a HealthPlate line, off one
    frame. Both halves are conditions on the body, and either one drifting
    leaves a window that holds one plate while reporting two.
    """
    before = sheet.MIC_OPEN["publish"]["body"]
    after = sheet.MIC_DEAF["publish"]["body"]
    assert before["state"] == "ok", (
        "the first exposure reports jv-ears as something other than ok, so "
        "HealthPlate is already on screen and there is no arrival to measure"
    )
    assert after["state"] == "degraded", (
        "the second exposure no longer has jv-ears calling itself degraded, "
        "so HealthPlate draws its earned nothing and the window holds "
        "MicPlate alone"
    )
    # core/MicState.qml: `mic_open` 1 and a capture younger than the stall
    # budget is `live`; older than it is `stalled`. The budget is jv-ears'
    # own (core/EarsBudgets.qml reads `capture_stall_s`), so the comparison
    # has to be made against the number in the same body.
    for body in (before, after):
        assert body["metrics"]["mic_open"] == 1, (
            "an exposure with no microphone open draws no mic plate at all"
        )
    assert before["metrics"]["capture_age_s"] <= before["metrics"]["capture_stall_s"], (
        "the first exposure's device is already stalled, so MicPlate says "
        "MIC NO AUDIO in both and the growth below is HealthPlate's alone"
    )
    assert after["metrics"]["capture_age_s"] > after["metrics"]["capture_stall_s"], (
        "the second exposure's device is not stalled by jv-ears' own budget, "
        "so MicPlate still says MIC and the window is measuring one plate"
    )


def test_the_two_exposures_differ_only_in_the_device_going_silent():
    """Same discipline A44's shot is held to: a growth measurement is only
    evidence if ONE event separates the two exposures. A pair that also
    moved the stall budget, or changed publisher, would grow the region for
    a reason nobody looked at.
    """
    before = sheet.MIC_OPEN["publish"]
    after = sheet.MIC_DEAF["publish"]
    assert before["topic"] == after["topic"] == "sys.health"
    assert before["src"] == after["src"] == "jv-ears", (
        "core/MicState.qml and core/HealthState.qml both ask for jv-ears by "
        "name and refuse a body naming a service other than its sender"
    )
    assert before["body"]["period_s"] == after["body"]["period_s"], (
        "the two exposures declare different heartbeat periods, which moves "
        "how long the HUD believes them — a second variable in a two-frame "
        "measurement"
    )
    metrics_moved = [
        key
        for key in set(before["body"]["metrics"]) | set(after["body"]["metrics"])
        if before["body"]["metrics"].get(key) != after["body"]["metrics"].get(key)
    ]
    assert metrics_moved == ["capture_age_s"], (
        f"the two exposures' gauges differ on {sorted(metrics_moved)}, not on "
        "the one thing that happened: the device stopped delivering audio"
    )


def test_the_mic_deaf_body_is_a_legal_heartbeat():
    """invariant 2: schemas are law, and a harness publishing an illegal
    body is measuring a machine that cannot exist. Hand-written, so
    checked rather than trusted."""
    import json

    schema = json.loads((ROOT / "schemas" / "sys.health.json").read_text("utf-8"))
    body = sheet.MIC_DEAF["publish"]["body"]
    missing = set(schema["required"]) - set(body)
    assert not missing, f"sys.health: body is missing {sorted(missing)}"
    extra = set(body) - set(schema["properties"])
    assert not extra, f"sys.health: body has unknown keys {sorted(extra)}"
    assert body["state"] in schema["properties"]["state"]["enum"], (
        "core/HealthState.qml renders only the schema's own state words and "
        "turns anything else into `unknown` — a different finding entirely"
    )


def test_the_mic_and_health_window_insists_frames_arrived_while_it_measured():
    """The one way this window can go quietly vacuous, and the reason it
    needs a guard the other three do not. A heartbeat speaks for two of its
    own `period_s` and jv-ears declares 5, so both plates survive a
    six-second silence — a feed that stopped would leave the photograph
    intact, the box check would pass, and the zero would be A34's.
    """
    window = mic_and_health()
    assert re.search(r"beats = feed_snapshots\(IDLE_WINDOW_S, deaf", window), (
        "A43's window no longer feeds heartbeats for the length of the "
        "measured window, so it is a HUD with a plate on screen and nothing "
        "arriving — which is A34's lit window under a new name"
    )
    assert "if beats < 2:" in window, (
        "A43's window no longer checks that anything arrived while it was "
        "measuring. Its plates outlive a six-second silence on their own, so "
        "a dead feed would report a perfect zero about a bus nobody was using"
    )


def test_the_mic_and_health_window_proves_the_health_plate_arrived():
    """`MicPlate` lights off the first heartbeat alone, so "something is
    drawn" is not evidence that HealthPlate is on screen. Lit in two steps
    and measured: the region has to grow DOWNWARDS, which is the health
    line arriving under the mic line on a stack docked to the top-right.
    """
    window = mic_and_health()
    assert "mic_box" in window, (
        "A43's window no longer measures the HUD before the device goes "
        "silent, so there is nothing for the lit one to have grown from"
    )
    assert "sheet.grew_downwards(mic_box, box)" in window, (
        "A43's window no longer insists the drawn region GREW when jv-ears "
        "reported itself degraded — whatever it holds still for six seconds "
        "may not include HealthPlate at all"
    )
    assert "if after != box:" in window, (
        "A43's window no longer re-measures the plates after it, so a pair "
        "that changed under the measurement would go unnoticed"
    )


# ------------------------------------------------- the shot that is a reading
#
# `04-unheard` (A44) is the first shot in this sheet whose subject is a
# LIVE reading rather than an event. Every other picture here is of a
# plate that holds itself up: a wake word happened, jv-act asked a
# question, and the frame behind it stays true on its own for longer than
# a camera takes. core/OutputState.qml is a reading of the present —
# three of jv-context's periods and it stops believing the snapshot — so
# this one has to be HELD, and a harness that stopped holding it would
# write a photograph of a bare desktop or of a plate that had left. These
# are the gates on that, and on the picture showing the two plates its
# caption claims rather than the one StatePlate would have drawn anyway.


def shot_loop_text() -> str:
    shoot = (ROOT / "tools" / "hudscreens" / "shoot.py").read_text("utf-8")
    return shoot.split("\ndef main(")[-1]


def unheard() -> dict:
    for shot in sheet.SHOTS:
        if shot["file"] == "04-unheard":
            return shot
    raise AssertionError(
        "the sheet no longer takes 04-unheard — the one picture in either "
        "sheet where two plates disagree about whether Jarvis is working"
    )


def test_the_unheard_shot_is_split_into_the_event_and_the_reading():
    """jv-voice's `speaking` is an event and ends with a real signal;
    the sink snapshot and the heartbeat are readings and rot where they
    stand. Putting all three in `frames` would publish them once, and the
    picture would be of whatever was left three seconds later.
    """
    shot = unheard()
    assert shot["frames"] == [sheet.VOICE_SPEAKING], (
        "04-unheard's one-shot frame is no longer jv-voice saying it is "
        "speaking, which is the half of this picture StatePlate draws"
    )
    assert sheet.SINK_MUTED in shot["hold"], (
        "04-unheard no longer HOLDS a muted snapshot, so OutputPlate has "
        "nothing to say and the picture is of SPEAKING alone"
    )
    assert sheet.VOICE_DEFAULT_SINK in shot["hold"], (
        "04-unheard's feed no longer re-publishes jv-voice's heartbeat: "
        "core/HealthState.qml calls a service lost after two of its own "
        "period_s, so `jv-voice lost` would arrive under the plate being "
        "photographed — the failure A42's window found the hard way"
    )


def test_a_held_shot_is_actually_fed_while_the_camera_takes_it():
    """The quiet way for this to break is for `hold` to become a key
    nothing reads. Nothing would go red: the picture would still be
    written and, on this machine today, would still be right — publishing
    the pair once lands inside OutputState's three-second window by under
    a second. What would be gone is the reason it is right. A second
    capture, a slower run or a longer settle spends that margin, and the
    failure it turns into is a photograph of a plate that has expired.
    """
    shoot = (ROOT / "tools" / "hudscreens" / "shoot.py").read_text("utf-8")
    settle = shoot.split("\ndef settle(")[-1].split("\ndef ")[0]
    assert "feed_snapshots(" in settle, (
        "shoot.py's settle no longer republishes a held shot's frames, so a "
        "reading is photographed after it has stopped being believed"
    )
    loop = shot_loop_text()
    assert 'hold = shot.get("hold", [])' in loop and "settle(SETTLE_S, hold" in loop, (
        "the shot loop no longer feeds a shot's `hold` frames through its "
        "settle — `hold` is now a key in sheet.py that nothing reads"
    )


def test_the_shorter_exposure_differs_only_in_the_thing_the_shot_is_of():
    """The growth measurement is only evidence if ONE thing changed
    between the two exposures. A `grows_from` that also dropped the
    heartbeat, or changed the volume, would grow the region for a reason
    nobody looked at — and the check would pass while the picture showed
    something else.
    """
    shot = unheard()
    before = {f["publish"]["topic"]: f["publish"]["body"] for f in shot["grows_from"]}
    after = {f["publish"]["topic"]: f["publish"]["body"] for f in shot["hold"]}
    assert set(before) == set(after), (
        f"the two exposures of {shot['file']} carry different topics: "
        f"{sorted(before)} and {sorted(after)}"
    )
    differ = [t for t in before if before[t] != after[t]]
    assert differ == ["context.system"], (
        f"the two exposures of {shot['file']} differ on {differ}, not on the "
        "sink snapshot alone"
    )
    changed = [
        k for k in before["context.system"]
        if before["context.system"][k] != after["context.system"][k]
    ]
    assert changed == ["audio_muted"], (
        f"the two exposures differ on {changed} — the only difference may be "
        "the mute, or the plate that arrives is not the one A40 added"
    )


def test_a_shot_that_grows_from_another_is_measured_on_the_monitor_it_photographs():
    """shoot.py measures the growth on the primary, because that is the
    region it photographed first. A shot that declared `grows_from` and
    never captured the primary would compare a box against None, and the
    only thing the run would prove is that it failed.
    """
    for shot in sheet.SHOTS:
        if shot.get("grows_from"):
            assert "primary" in shot["captures"], (
                f"{shot['file']} grows from a shorter exposure of the primary "
                "and never photographs the primary"
            )


def test_the_growth_rule_is_the_geometry_the_stack_actually_has():
    """A plate arriving UNDER another one, on a stack docked to the
    top-right: the top and right edges pin it, the bottom grows, and the
    left travels outwards because OUTPUT MUTED is a longer line than
    SPEAKING. Every one of those is a way for the rule to be wrong, and
    the inline version of it got the last one backwards first time.
    """
    one = (2244, 16, 2544, 57)
    assert sheet.grew_downwards(one, (2244, 16, 2544, 98)), "a taller stack"
    assert sheet.grew_downwards(one, (2180, 16, 2544, 98)), (
        "the left edge travelling outwards is a longer line, not a move"
    )
    assert not sheet.grew_downwards(one, one), "nothing arrived"
    assert not sheet.grew_downwards(one, (2244, 16, 2544, 40)), "the stack shrank"
    assert not sheet.grew_downwards(one, (2244, 24, 2544, 98)), (
        "the top edge moved: something REPLACED the plate above rather than "
        "arriving under it"
    )
    assert not sheet.grew_downwards(one, (2244, 16, 2500, 98)), (
        "the right edge moved: the stack is no longer docked where it was"
    )
    assert not sheet.grew_downwards(one, (2300, 16, 2544, 98)), (
        "the left edge moved INWARDS: the line got shorter, so this is a "
        "different plate rather than a second one"
    )
    assert not sheet.grew_downwards(None, one), "nothing was drawn first"
    assert not sheet.grew_downwards(one, None), "nothing is drawn now"


def test_the_growth_rule_is_stated_once():
    """Two callers, one rule. A second inline copy is a rule that can
    drift on one side, and the side that drifts is the one nobody is
    looking at.
    """
    shoot = (ROOT / "tools" / "hudscreens" / "shoot.py").read_text("utf-8")
    assert shoot.count("sheet.grew_downwards(") == 3, (
        "the idle probe's two live-lit windows and the shot loop must all ask "
        "sheet.grew_downwards — an inline copy of the geometry is one the "
        "unit tests above do not cover"
    )
    assert "box[3] <= speaking_box[3]" not in shoot, (
        "the live-lit window has an inline growth rule again"
    )


def test_the_readme_shows_the_one_picture_of_two_plates_disagreeing():
    """A photograph nobody is told how to read is decoration. This one
    needs its caption more than most: both plates are telling the truth,
    and the thing the reader is meant to see is that the truth adds up to
    a machine that is not working.
    """
    readme = (SCREENS / "README.md").read_text("utf-8")
    for name in sheet.capture_files(unheard()):
        assert name in readme, f"docs/hud/screens/README.md never shows {name}"
    assert "OUTPUT MUTED" in readme and "SPEAKING" in readme, (
        "docs/hud/screens/README.md shows the unheard shot without naming "
        "the two lines in it"
    )


def test_the_readme_says_the_screens_are_not_byte_reproducible():
    """These PNGs are NOT a fixture, and one journal entry has already
    treated them as one ("the screens are unchanged", as evidence). Two
    runs of an unchanged HUD differ by a couple of pixels along an
    antialiased glyph edge — harmless until somebody reads a clean
    `git status` as proof that nothing moved (A45).
    """
    readme = (SCREENS / "README.md").read_text("utf-8")
    assert "not byte-identical" in readme, (
        "docs/hud/screens/README.md no longer says the screens are not "
        "reproducible byte for byte — without it a clean diff after a "
        "re-run reads as evidence, and a dirty one reads as a regression"
    )
