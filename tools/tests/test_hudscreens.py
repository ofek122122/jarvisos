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

import ast
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from test_gen_theme_qml import ROOT, hud_surface_box

sys.path.insert(0, str(ROOT / "tools" / "hudscreens"))
import sheet  # noqa: E402

sys.path.insert(0, str(ROOT / "tools"))
import hudsheet  # noqa: E402

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
    # The width comes back resolved: the shell reads `Theme.hudCornerPx` for
    # it now (PLAN D16), because jv-bar reserves the same corner and the two
    # processes cannot see each other. sheet.py still carries plain numbers,
    # which is what this gate is for — it is a Python module measuring PNGs,
    # not a shell, so it has no Theme to read.
    width, height = hud_surface_box()
    assert (width, height) == (sheet.SURFACE_W, sheet.SURFACE_H), (
        f"shell.qml's surface is {width}x{height} and "
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


def test_only_the_probes_that_read_the_socket_log_ask_for_one():
    """WAYLAND_DEBUG is how the HUD is made to say what it committed. With
    it unset the log is empty, every window reads zero, and the probe
    passes for a HUD animating on all three monitors.

    Two probes read that log now — the idle windows count commits in it
    (A34), and D68's asks it what size the compositor configured each
    surface at — and nothing else in this harness may ask for one. The rule
    is about the PICTURES: a shot taken of a HUD writing a protocol log for
    every frame is a photograph of a machine nobody runs, and the shot loop
    is where that would go unnoticed.
    """
    shoot = (ROOT / "tools" / "hudscreens" / "shoot.py").read_text("utf-8")
    probe = shoot.split("\ndef probe_idle_frames(")[-1].split("\ndef ")[0]
    assert probe.count('WAYLAND_DEBUG="1"') == 5, (
        "every jv-hud the idle probe starts must be started with "
        "WAYLAND_DEBUG=1, or the frames it is counting are not being logged"
    )
    granted = shoot.split("\ndef probe_surface_granted(")[-1].split("\ndef ")[0]
    assert granted.count('WAYLAND_DEBUG="1"') == 1, (
        "the granted-width probe (D68) reads the configure event out of the "
        "HUD's own Wayland log, so its one shell must be started with "
        "WAYLAND_DEBUG=1 — without it the log is empty and the probe's census "
        "fails rather than lying, which is the right way round and still not a "
        "measurement"
    )
    assert shoot.count('WAYLAND_DEBUG="1"') == 6, (
        "a jv-hud is started with WAYLAND_DEBUG=1 outside the two probes that "
        "read that log — the photographs should be of a HUD doing its job, not "
        "one writing a protocol log"
    )
    body = shoot.split("\ndef main(")[-1]
    assert "WAYLAND_DEBUG" not in body, (
        "the shot loop mentions WAYLAND_DEBUG: every PNG in docs/hud/screens "
        "is taken of a HUD that is not being traced, and that is the half of "
        "this rule the sheet depends on"
    )


def test_each_idle_window_has_a_control():
    """Every window passes on zero, and so does a probe that is reading
    nothing at all. Each one is therefore paired with a stretch that MUST
    contain commits, counted the same way through the same log: the HUD
    being woken by a real frame after the quiet window, the blind plate
    arriving before the lit one, and a plate arriving under the one above
    it in each of the four that are fed.
    """
    shoot = (ROOT / "tools" / "hudscreens" / "shoot.py").read_text("utf-8")
    probe = shoot.split("\ndef probe_idle_frames(")[-1].split("\ndef ")[0]
    assert (
        "if not woke:" in probe
        and "if not arriving:" in probe
        and probe.count("if not lighting:") == 4
    ), (
        "the idle probe no longer insists on SEEING commits somewhere, so a "
        "broken instrument — an unset WAYLAND_DEBUG, a libwayland that "
        "renamed its objects — would report a flawless permanent zero"
    )
    assert probe.count("sheet.surface_traffic(") == 12, (
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

    The banner's INDENT is not part of the marker. A49's window runs
    inside the broker and the shell A48's window already started — one
    turn carried to its end rather than a sixth pair of processes — so its
    banner sits a level deeper, and a splitter that insisted on four
    spaces would have handed every one of its gates the window above it.
    """
    for chunk in re.split(r"\n\s*# --- ", idle_probe_text())[1:]:
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
    assert "six" in readme.lower(), (
        "docs/hud/screens/README.md still describes five idle windows"
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
    assert "CONFIRM" in readme, (
        "docs/hud/screens/README.md does not say which plates A48's window "
        "held on screen — and that window is the only one whose frames are "
        "re-taken latches rather than re-read readings"
    )
    assert "ACTION FAILED" in readme, (
        "docs/hud/screens/README.md does not say which plate A49's window "
        "held on screen — it is the last one in the stack, and the only "
        "window in which anything has ever LEFT the screen"
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
    # A84 gave MicPlate a third line — `MIC LOSING AUDIO`, for a device that
    # is open and delivering and dropping chunks anyway. It is wider than
    # `MIC` and it rides on a gauge that is ABSENT here, which is the only
    # reason the first exposure draws the narrow line. An absence is not an
    # assertion, so it is one now: a loss gauge added to either body would
    # change what is on screen and leave the growth below measuring a plate
    # that got wider rather than a plate that arrived.
    for body, which in ((before, "first"), (after, "second")):
        assert "capture_loss_age_s" not in body["metrics"], (
            f"the {which} exposure now reports a discarded chunk, so MicPlate "
            "is drawing a line this window was not measured against"
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


# ---------------------------------- the fifth window: heard and confirm (A48)
#
# The four windows above hold five plates, and every one of them is a
# READING: OutputState believes a snapshot while the snapshots keep coming,
# MicState and HealthState read the heartbeat in front of them. Nothing up
# there has a latch in it.
#
# `HeardPlate` and `ConfirmPlate` are the last two plates in the stack that
# had never been watched standing still, and they are the only two whose
# words come off a LATCH — a final transcript remembered because partials
# would blank it, a question remembered because the answer lands on the
# same topic. Re-publishing therefore means something different here than
# it does above: it RE-TAKES the latch. The envelope is replaced, the key
# moves, `armHold`/`armExpiry` run and a one-shot timer restarts, once a
# second, while the two sentences on screen do not move a pixel.
#
# These gates hold the three ways that window can go vacuous without
# looking wrong: losing its broker, holding HeardPlate alone while the
# question never arrived, and — the one it shares with A43's window and
# not with A42's — letting the latches carry themselves through a silence.


def heard_and_confirm() -> str:
    return idle_window_text("HEARD AND CONFIRM")


def test_the_heard_and_confirm_window_runs_on_a_real_broker():
    """Same claim as the two windows above it and the same way of losing
    it. The subject is a latch being re-taken by an arriving frame; with no
    jarvisd nothing arrives, the latches simply sit there, and "a plate on
    screen and nothing happening" is A34's measurement.
    """
    window = heard_and_confirm()
    assert "JARVISD_BIN" in window, (
        "A48's window starts no jarvisd — a HUD with no bus cannot have a "
        "latch re-taken, and the whole subject of this window is what that "
        "costs"
    )
    assert "sheet.HEARD_FINAL" in window and "sheet.CONFIRM_REQUEST" in window, (
        "A48's window no longer publishes the two frames that light the two "
        "plates it names, so whatever it is measuring is not them"
    )


def test_the_two_frames_light_exactly_the_plates_the_window_claims():
    """core/HeardState.qml reads FINALS from jv-ears and nothing else;
    core/ConfirmState.qml reads a `request` from jv-act. Any of those four
    facts wrong and the window measures a bare desktop while reporting a
    triumphant zero.
    """
    heard = sheet.HEARD_FINAL["publish"]
    assert heard["topic"] == "audio.transcript" and heard["src"] == "jv-ears", (
        "core/HeardState.qml reads jv-ears' transcript topic; a frame under "
        "another src or topic is not one the HUD will draw"
    )
    assert heard["body"]["kind"] == "final", (
        "A48's window publishes a PARTIAL. core/HeardState.qml refuses them "
        "on purpose — they get rewritten — so HeardPlate would never light"
    )
    assert heard["body"]["text"].strip(), (
        "a transcript that flattens to nothing is not a reading, and "
        "core/HeardState.qml refuses it: the plate would stay dark"
    )
    assert heard["body"]["lang"] == "en", (
        "A48's window claims jv-ears detected a language this machine does "
        "not expect, which lights an extra line in HeardPlate (the pinned "
        "ASR is English-only) and changes the box the window measures"
    )
    assert "conf" in heard and 0 < heard["conf"] < 1, (
        "the transcript is published with a composed certainty. Invariant 4 "
        "wants the producer's own number, and no ASR reports 1.0 — this one "
        "is borrowed from the committed recording's final"
    )
    ask = sheet.CONFIRM_REQUEST["publish"]
    assert ask["topic"] == "action.confirm" and ask["src"] == "jv-act", (
        "only jv-act asks; core/ConfirmState.qml reads the topic and the "
        "frame's own fields, and a question from anywhere else is not one"
    )
    assert ask["body"]["kind"] == "request", (
        "A48's window publishes an ANSWER, which is the frame that CLOSES a "
        "question — ConfirmPlate would never appear"
    )
    assert ask["body"]["request_id"], (
        "a question with no request_id is one nothing could ever answer, and "
        "core/ConfirmState.qml refuses to latch it"
    )


def test_the_confirm_window_is_the_one_jv_act_actually_declares():
    """The temptation this window had and refused. `ConfirmState` arms its
    expiry off the window the FRAME declares (A14: the service that enforces
    a budget states it), so publishing 600 would hold the plate up for ten
    minutes and make the feed below unnecessary. It would also be a picture
    of a machine that does not exist — the same thing A43 refused to do to
    a heartbeat's `period_s`.
    """
    declared = sheet.CONFIRM_REQUEST["publish"]["body"]["window_s"]
    schema = json.loads(
        (ROOT / "schemas" / "action.confirm.json").read_text("utf-8")
    )
    assert f"({declared:.0f}s)" in schema["description"], (
        f"the harness publishes a {declared:.0f}s confirmation window and "
        "schemas/action.confirm.json documents a different one — a frame no "
        "jv-act would ever send, believed by core/ConfirmState.qml"
    )
    assert declared < 30, (
        "a confirmation window long enough to outlast the measurement is "
        "what makes the feed below decorative; jv-act's real one is short, "
        "and the re-publish is the subject"
    )


def test_both_heard_and_confirm_frames_are_legal_bodies_for_their_topics():
    """`schemas/` is bus law (invariant 2) and a harness that publishes an
    illegal body is measuring a machine that cannot exist. Checked rather
    than trusted, because both frames are hand-written.
    """
    for frame in (sheet.HEARD_FINAL, sheet.CONFIRM_REQUEST):
        spec = frame["publish"]
        schema = json.loads(
            (ROOT / "schemas" / f"{spec['topic']}.json").read_text("utf-8")
        )
        body = spec["body"]
        missing = set(schema["required"]) - set(body)
        assert not missing, f"{spec['topic']}: body is missing {sorted(missing)}"
        extra = set(body) - set(schema["properties"])
        assert not extra, f"{spec['topic']}: body has unknown keys {sorted(extra)}"
    for topic, field, value in (
        ("audio.transcript", "kind", sheet.HEARD_FINAL["publish"]["body"]["kind"]),
        ("action.confirm", "kind", sheet.CONFIRM_REQUEST["publish"]["body"]["kind"]),
    ):
        schema = json.loads((ROOT / "schemas" / f"{topic}.json").read_text("utf-8"))
        assert value in schema["properties"][field]["enum"]


def test_the_heard_and_confirm_window_proves_the_question_arrived():
    """`HeardPlate` lights off the transcript alone, so "something is
    drawn" is not evidence that ConfirmPlate is on screen — and
    ConfirmPlate is the half of this window nothing else in the harness
    ever holds still. Lit in two steps and measured: the region has to grow
    DOWNWARDS, which is what the stack does when the question docks above
    the heard line and pushes it down.
    """
    window = heard_and_confirm()
    assert "heard_box" in window, (
        "A48's window no longer measures the HUD before jv-act asks, so "
        "there is nothing for the lit one to have grown from"
    )
    assert "sheet.grew_downwards(heard_box, box)" in window, (
        "A48's window no longer insists the drawn region GREW when the "
        "question arrived — whatever it holds still for six seconds may not "
        "include ConfirmPlate at all"
    )
    assert "if after != box:" in window, (
        "A48's window no longer re-measures the plates after it, so a pair "
        "that changed under the measurement would go unnoticed"
    )


def test_the_heard_and_confirm_window_insists_frames_arrived():
    """The way this one goes vacuous, and it is A43's way rather than
    A42's. A latch outlives its own silence: ConfirmState holds the
    question for the 15 s jv-act declared and HeardState holds the line for
    30, so a feed that never ran would leave both plates exactly where they
    are for the whole six seconds and the box check would pass.
    """
    window = heard_and_confirm()
    assert re.search(r"relatches = feed_snapshots\(IDLE_WINDOW_S, asked", window), (
        "A48's window no longer re-publishes for the length of the measured "
        "window — and the re-taking of the latch IS its subject, so what is "
        "left is a HUD with two plates on screen and nothing arriving"
    )
    assert "if relatches < 2:" in window, (
        "A48's window no longer checks that anything arrived while it was "
        "measuring. Both latches outlive a six-second silence on their own, "
        "so a dead feed would report a perfect zero about an idle bus"
    )


def test_the_confirm_frame_is_stated_once():
    """The `03-confirm` shot and A48's window photograph and measure the
    same question. Two copies of it would drift — a summary edited in one
    place is a different plate, a different box, and a test that still
    passes while the two sheets describe different machines.
    """
    src = (ROOT / "tools" / "hudscreens" / "sheet.py").read_text("utf-8")
    kinds = [f["publish"]["body"]["kind"] for f in (sheet.CONFIRM_REQUEST, sheet.CONFIRM_GRANTED)]
    assert src.count('"topic": "action.confirm"') == len(kinds), (
        "tools/hudscreens/sheet.py writes a confirmation frame it did not "
        "name; the topic carries exactly two of them — the question both "
        "the shot and A48's window read, and the answer A49's window closes "
        "it with"
    )
    assert kinds == ["request", "answer"], (
        "the two action.confirm frames are no longer a question and the "
        "answer to it; ConfirmPlate would either never light or never leave"
    )
    for shot in sheet.SHOTS:
        if shot["file"] == "03-confirm":
            assert sheet.CONFIRM_REQUEST in shot["frames"], (
                "03-confirm no longer photographs the frame A48's window "
                "holds still, so the picture and the measurement are of two "
                "different questions"
            )
            break
    else:
        raise AssertionError("the sheet no longer takes 03-confirm")


# --------------------------------- the sixth window: and what came of it (A49)
#
# `ActionPlate` was the last plate in the stack that had never been watched
# standing still, and none of the five windows above could reach it: not
# one of them publishes an `action.result` at all. It is a latch with a
# 30 s hold, exactly like `HeardState`, so A48's mechanism carries over —
# but the frame arriving does one thing more here than it does there.
# Re-taking `ActionState.failure` re-runs `toolFor()`, which reaches back
# to the `intent.action` still on the bus, compares its request_id and
# re-resolves the tool name from scratch. No window above has a binding
# that re-reads a SECOND topic every time the first one arrives.
#
# The design decision A49 was opened to make is that this is not a sixth
# pair of processes. It is the same broker, the same shell and the same
# turn as the window above, carried to its end — which is what forces the
# step nothing in this harness had ever measured: a plate LEAVING. An
# outcome landing while `ConfirmPlate` still stood would be jv-act having
# run a tool it was still asking permission for.


def came_of_it() -> str:
    return idle_window_text("AND WHAT CAME OF IT")


def test_the_outcome_window_adds_no_sixth_process():
    """The thing that makes this a measurement rather than a fixture. A
    window per plate ends with a probe whose cost is its plate count and
    whose staging is its whole content; this one costs a few more seconds
    of a run that was already happening.

    Pinned through the HUD count rather than through a comment, because
    `test_the_idle_probe_reads_the_huds_own_wayland_log` already insists
    every jv-hud the probe starts is started with WAYLAND_DEBUG — so the
    number of those is the number of shells, and the two tests hold each
    other up.
    """
    window = came_of_it()
    assert "JARVISD_BIN" not in window and "JV_HUD_BIN" not in window, (
        "A49's window starts processes of its own. It is meant to be the "
        "END of the turn the window above begins — same broker, same shell "
        "— and a sixth pair is the cost this window was designed to refuse"
    )
    assert idle_probe_text().count('WAYLAND_DEBUG="1"') == 5, (
        "the idle probe starts a number of shells that is no longer five, "
        "so A49's window grew its own after all"
    )


def test_the_outcome_window_publishes_the_turn_it_claims():
    """Three frames, in the order `schemas/intent.action.json` says they
    thread. Any of them missing and the window measures something other
    than what it reports: no intent and the plate is nameless, no answer
    and the machine in the picture cannot exist, no result and
    `ActionPlate` never lights at all.
    """
    window = came_of_it()
    for name in ("TRASH_INTENT", "CONFIRM_GRANTED", "TRASH_FAILED"):
        assert f"sheet.{name}" in window, (
            f"A49's window no longer publishes {name}, so the turn it says "
            "it is photographing is not the one on the bus"
        )
    says_yes = 'publish_shot({"frames": [sheet.CONFIRM_GRANTED]}'
    reports = 'publish_shot({"frames": [sheet.TRASH_FAILED]}'
    assert says_yes in window and reports in window, (
        "A49's window no longer puts the answer and the outcome on the bus "
        "as their own publishes, so nothing below can say which came first"
    )
    assert window.index(says_yes) < window.index(reports), (
        "A49's window publishes the outcome before the answer that allowed "
        "it — jv-act running a tool it is still asking permission for, with "
        "ConfirmPlate quite happily still on screen"
    )


def test_the_outcome_window_proves_the_question_left_and_the_report_arrived():
    """Two geometry checks, and the first one is the new one. `HeardPlate`
    is on screen throughout, so "something is drawn" is evidence of
    nothing: the region has to SHRINK when the answer lands (the stack with
    the question on it was taller at the same top-right corner) and then
    GROW when the failure does.
    """
    window = came_of_it()
    assert "sheet.grew_downwards(answered_box, box)" in window, (
        "A49's window no longer insists the drawn region shrank back when "
        "the user answered — ConfirmPlate may still be standing over a tool "
        "jv-act has already run"
    )
    assert "sheet.grew_downwards(answered_box, acted_box)" in window, (
        "A49's window no longer insists the drawn region GREW when the "
        "outcome arrived — whatever it holds still for six seconds may not "
        "include ActionPlate at all"
    )
    assert "if after != acted_box:" in window, (
        "A49's window no longer re-measures the plates after it, so a pair "
        "that changed under the measurement would go unnoticed"
    )


def test_the_outcome_window_insists_frames_arrived():
    """A48's way of going vacuous, sharpened. BOTH latches here hold for
    30 s — `HeardState` for a transcript, `ActionState` for a failure
    nobody explained — so a feed that never ran would leave the two plates
    exactly where they are for the whole six seconds and the box check
    would pass.
    """
    window = came_of_it()
    assert re.search(r"reruns = feed_snapshots\(IDLE_WINDOW_S, acted", window), (
        "A49's window no longer re-publishes for the length of the measured "
        "window, and the re-taking of the latch IS its subject"
    )
    assert "if reruns < 2:" in window, (
        "A49's window no longer checks that anything arrived while it was "
        "measuring. Both latches outlive a six-second silence on their own, "
        "so a dead feed would report a perfect zero about an idle bus"
    )


def test_the_three_outcome_frames_light_exactly_what_the_window_claims():
    """core/ActionState.qml is strict on purpose, and every one of these is
    a condition it imposes. Get any of them wrong and the window measures a
    HUD holding `HeardPlate` alone while reporting a triumphant zero.
    """
    intent = sheet.TRASH_INTENT["publish"]
    assert intent["topic"] == "intent.action" and intent["src"] == "jv-brain", (
        "the tool name comes off the brain's own request; a frame under "
        "another topic or src is not one core/ActionState.qml reads"
    )
    result = sheet.TRASH_FAILED["publish"]
    assert result["topic"] == "action.result" and result["src"] == "jv-act", (
        "only jv-act reports what it did (invariant 3), and the HUD reads "
        "the outcome off that topic"
    )
    assert result["body"]["ok"] is False, (
        "A49's window publishes a SUCCESS. core/ActionState.qml shows "
        "failures only — an action that worked needs no plate — so "
        "ActionPlate would never light"
    )
    assert result["body"]["error"] not in ("denied", "confirm_timeout"), (
        "A49's window reports how a CONFIRMATION ended, which A22 leaves to "
        "a human and core/ActionState.qml deliberately passes over: the "
        "plate would stay dark"
    )
    answer = sheet.CONFIRM_GRANTED["publish"]
    assert answer["body"]["granted"] is True, (
        "the window answers NO and then reports the tool running anyway — a "
        "machine that does not exist, and jv-act would have published "
        "`denied` instead"
    )
    ids = {
        f["publish"]["body"]["request_id"]
        for f in (
            sheet.CONFIRM_REQUEST,
            sheet.TRASH_INTENT,
            sheet.CONFIRM_GRANTED,
            sheet.TRASH_FAILED,
        )
    }
    assert ids == {sheet.TURN_REQUEST_ID}, (
        "the four frames of one turn no longer carry one request_id. "
        "core/ConfirmState.qml closes only on an answer naming ITS question "
        "and core/ActionState.qml puts a tool name on screen only when the "
        "ids match, so a drifted id is a question that never leaves and a "
        "failure with no name"
    )
    assert (
        sheet.TRASH_INTENT["publish"]["body"]["utterance_id"]
        == sheet.HEARD_FINAL["publish"]["body"]["utterance_id"]
    ), (
        "the intent no longer traces back to the sentence on screen, so the "
        "window photographs two unrelated turns stacked on one another"
    )


def test_the_reported_error_is_a_word_the_hud_will_actually_draw():
    """`reason` is drawn verbatim, out of the frozen enum of
    `schemas/action.result.json`, and core/ActionState.qml refuses any word
    outside a list of its own — a word the reader cannot look up is one the
    failure is better reported without. A frame carrying an unrecognised
    error still lights the plate; it lights it one line shorter, which is a
    different box from the one this window measures.
    """
    word = sheet.TRASH_FAILED["publish"]["body"]["error"]
    schema = json.loads((ROOT / "schemas" / "action.result.json").read_text("utf-8"))
    assert word in schema["properties"]["error"]["enum"], (
        f"'{word}' is not in the frozen enum, so it is a frame no jv-act "
        "could send"
    )
    state = (ROOT / "shell" / "jv-hud" / "core" / "ActionState.qml").read_text("utf-8")
    reportable = state.split("readonly property var reportableReasons: [")[1].split("]")[0]
    assert f'"{word}"' in reportable, (
        f"core/ActionState.qml will not put '{word}' on screen, so the "
        "window measures a plate one line shorter than the one it describes"
    )


def test_the_three_outcome_frames_are_legal_bodies_for_their_topics():
    """`schemas/` is bus law (invariant 2) and a harness that publishes an
    illegal body is measuring a machine that cannot exist. Checked rather
    than trusted, because all three frames are hand-written.
    """
    for frame in (sheet.TRASH_INTENT, sheet.CONFIRM_GRANTED, sheet.TRASH_FAILED):
        spec = frame["publish"]
        schema = json.loads(
            (ROOT / "schemas" / f"{spec['topic']}.json").read_text("utf-8")
        )
        body = spec["body"]
        missing = set(schema["required"]) - set(body)
        assert not missing, f"{spec['topic']}: body is missing {sorted(missing)}"
        extra = set(body) - set(schema["properties"])
        assert not extra, f"{spec['topic']}: body has unknown keys {sorted(extra)}"
    for topic, field, value in (
        ("intent.action", "capability", sheet.TRASH_INTENT["publish"]["body"]["capability"]),
        ("action.confirm", "kind", sheet.CONFIRM_GRANTED["publish"]["body"]["kind"]),
        ("action.confirm", "answered_by", sheet.CONFIRM_GRANTED["publish"]["body"]["answered_by"]),
    ):
        schema = json.loads((ROOT / "schemas" / f"{topic}.json").read_text("utf-8"))
        assert value in schema["properties"][field]["enum"]


def test_the_composed_tool_is_not_in_jv_acts_registry_and_the_sheet_says_so():
    """The one thing in this turn that is NOT the machine as it is, written
    down where a reader of the frames will meet it.

    `services/jv-act/tools.toml` is v0 — "observe + benign only" — and the
    confirmation rule is structural: only destructive and privileged tools
    are ever confirmed. So there is no tool on this machine today that
    could produce an `action.confirm`, and asked for `fs.trash` the real
    jv-act would answer `unknown_tool` and ask nobody anything. The
    machinery being photographed is real, reviewed and built; the tool it
    is holding is one the registry has not been granted yet. Both halves
    have to stay said, and this pins the disclaimer the way A45 pinned the
    reproducibility one.
    """
    tool = sheet.CONFIRM_REQUEST["publish"]["body"]["tool"]
    assert tool == sheet.TRASH_INTENT["publish"]["body"]["tool"], (
        "the question and the intent name two different tools, so the plate "
        "would report a failure of something nobody was asked about"
    )
    registry = (ROOT / "services" / "jv-act" / "tools.toml").read_text("utf-8")
    src = (ROOT / "tools" / "hudscreens" / "sheet.py").read_text("utf-8")
    if f'name = "{tool}"' in registry:
        raise AssertionError(
            f"'{tool}' is in jv-act's registry now, which is good news and "
            "makes the disclaimer in tools/hudscreens/sheet.py wrong — "
            "delete the paragraph under CONFIRM_REQUEST that says the tool "
            "is not registered, and this check with it"
        )
    assert "not in jv-act's registry" in src, (
        "tools/hudscreens/sheet.py no longer says that the tool these "
        "frames name is one jv-act has never been granted. Every number in "
        "the confirmation frame is jv-act's own and the tool is not, and a "
        "reader who is not told reads the whole turn as recorded"
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
    assert shoot.count("sheet.grew_downwards(") == 6, (
        "the idle probe's four fed windows and the shot loop must all ask "
        "sheet.grew_downwards — an inline copy of the geometry is one the "
        "unit tests above do not cover. A49's window asks it TWICE, and the "
        "second one reads the rule backwards: a plate LEAVING is the same "
        "geometry with the arguments swapped"
    )
    assert "box[3] <= speaking_box[3]" not in shoot, (
        "the live-lit window has an inline growth rule again"
    )


# ------------------------------------ one plate, one word, one instant (B93)


def preempted() -> dict:
    for shot in sheet.SHOTS:
        if shot["file"] == "05-preempted":
            return shot
    raise AssertionError(
        "the sheet no longer takes 05-preempted — the only picture of the "
        "word B91 taught the HUD to tell apart from INTERRUPTED"
    )


def test_the_preempted_body_is_a_legal_speech_state():
    """invariant 2: schemas are law, and a harness publishing an illegal
    body is photographing a machine that cannot exist. Hand-written, so
    checked rather than trusted — and the `reason` is checked against the
    frozen enum rather than against the one word this shot needs, because
    a `reason` outside it is the case core/SpeechState.qml deliberately
    draws as plain INTERRUPTED.
    """
    schema = json.loads((ROOT / "schemas" / "speech.state.json").read_text("utf-8"))
    body = preempted()["frames"][0]["publish"]["body"]
    missing = set(schema["required"]) - set(body)
    assert not missing, f"speech.state: body is missing {sorted(missing)}"
    extra = set(body) - set(schema["properties"])
    assert not extra, f"speech.state: body has unknown keys {sorted(extra)}"
    assert body["state"] in schema["properties"]["state"]["enum"], (
        f"speech.state: {body['state']} is not one of the three words the "
        "frozen enum allows, and core/SpeechState.qml draws nothing for a "
        "state it does not recognise"
    )
    assert body["reason"] in schema["properties"]["reason"]["enum"], (
        f"speech.state: {body['reason']} is not a reason jv-voice can send"
    )


def test_the_preempted_frame_is_the_one_jv_voice_actually_publishes():
    """The shot's whole claim is that this body happens on this machine.
    jv-voice's own test asserts the frame verbatim — an urgent utterance
    preempting an interruptible one — so that assertion is the source, and
    a sheet that drifted from it would be a picture of a transition no
    service makes.
    """
    body = preempted()["frames"][0]["publish"]["body"]
    voice = (
        ROOT / "services" / "jv-voice" / "tests" / "test_voice_service.py"
    ).read_text("utf-8")
    asserted = re.search(
        r'==\s*\{"state": "interrupted", "say_id": \w+, "reason": "preempted"\}',
        voice,
    )
    assert asserted, (
        "services/jv-voice no longer asserts the body this shot composes, so "
        "nothing outside docs/hud/screens says this frame is one jv-voice sends"
    )
    assert body["state"] == "interrupted" and body["reason"] == "preempted", (
        f"the shot composes {body}, and jv-voice's own test says the "
        "preemption frame is state=interrupted with reason=preempted"
    )
    assert set(body) == {"state", "say_id", "reason"}, (
        f"the shot composes {sorted(body)} and jv-voice publishes exactly "
        "state, say_id and reason for this transition"
    )


def test_the_preempted_frame_is_the_speaking_one_a_transition_later():
    """The two composed jv-voice frames in this sheet are ONE utterance:
    04-unheard photographs it being spoken and this one photographs it
    being cut short. A second say_id would be two unrelated turns wearing
    the same publisher, and `say_id` is the only thing in either body that
    could say so.
    """
    speaking = sheet.VOICE_SPEAKING["publish"]
    stopped = preempted()["frames"][0]["publish"]
    assert speaking["src"] == stopped["src"] == "jv-voice", (
        "core/SpeechState.qml reads speech.state from jv-voice; a frame "
        "under another name is one this HUD would refuse"
    )
    assert speaking["body"]["say_id"] == stopped["body"]["say_id"], (
        f"the sheet's speaking frame is {speaking['body']['say_id']} and the "
        f"preempted one is {stopped['body']['say_id']} — two turns, "
        "photographed as if they were one"
    )


def test_the_preempted_shot_lights_exactly_the_plate_it_claims():
    """One plate, and the caption says so. Two elements in `core/` read
    `speech.state` — SpeechState, which draws the word, and OutputState,
    which needs a `context.system` snapshot as well before it can say
    anything — so a snapshot added to these frames would put a second line
    under a caption describing one.
    """
    shot = preempted()
    assert "hold" not in shot and "grows_from" not in shot, (
        "05-preempted now feeds or grows from something, so it is no longer "
        "the one-frame shot its caption describes"
    )
    topics = {f["publish"]["topic"] for f in shot["frames"]}
    assert topics == {"speech.state"}, (
        f"05-preempted publishes {sorted(topics)} — the shot is of one word "
        "on one plate, and every other topic here is another plate"
    )
    # FOUR elements read this topic, not one, and only SpeechState draws a
    # word off it alone. The other three read it as an EXIT from something
    # else they are already showing — an outcome, a heard line, a sink —
    # so each of them needs a topic this shot does not publish, and the
    # picture is one plate because of three separate facts rather than one.
    # An element that stopped needing its own subject would put a second
    # line under a caption describing one.
    core = ROOT / "shell" / "jv-hud" / "core"

    def topics_of(path):
        return set(re.findall(r'(?:frameOn|bus\.latest)\("([\w.]+)"\)', path.read_text("utf-8")))

    subjects = {
        "ActionState": "action.result",
        "HeardState": "audio.transcript",
        "OutputState": "context.system",
    }
    readers = sorted(
        path.stem for path in core.glob("*.qml") if "speech.state" in topics_of(path)
    )
    assert readers == sorted(["SpeechState", *subjects]), (
        f"{readers} read speech.state now, and this shot was measured "
        f"against {sorted(['SpeechState', *subjects])} — a new reader may be "
        "drawing a plate the caption does not mention"
    )
    for name, subject in subjects.items():
        assert subject in topics_of(core / f"{name}.qml"), (
            f"core/{name}.qml no longer reads {subject}, so jv-voice's frame "
            "may now be enough to light it on its own and this shot is of "
            "more than one plate"
        )
        assert subject not in topics, (
            f"05-preempted now publishes {subject}, which is what "
            f"core/{name}.qml is waiting for — the caption says one plate"
        )


def test_the_readme_says_the_word_in_this_picture_does_not_linger():
    """The one thing a reader cannot get from the photograph. jv-voice
    publishes `idle` in the statement after this frame, with nothing
    awaited between them, and `idle` draws nothing — so PREEMPTED is on
    screen for one frame's flight over a Unix socket. A caption that left
    that out would be showing a state nobody can actually see and calling
    it what the HUD shows.
    """
    readme = readme_text()
    for name in sheet.capture_files(preempted()):
        assert name in readme, f"docs/hud/screens/README.md never shows {name}"
    section = [s for s in readme.split("\n### ") if "05-preempted-primary.png" in s]
    assert len(section) == 1
    section = section[0]
    assert "PREEMPTED" in section, (
        "the caption never names the word the picture is of"
    )
    assert "INTERRUPTED" in section, (
        "the caption never names the word PREEMPTED is worth telling apart "
        "from, which is the whole of why B91 added it"
    )
    assert re.search(r"\bidle\b", section), (
        "the caption never says jv-voice publishes `idle` immediately after "
        "this frame — without it the picture reads as a state you could sit "
        "and look at, and it is an instant"
    )
    service = (
        ROOT / "services" / "jv-voice" / "jv_voice" / "service.py"
    ).read_text("utf-8")
    assert re.search(
        r'_state\("interrupted", say_id, self\._interrupt_reason or "preempted"\)\n'
        r'\s*await self\._state\("idle"\)',
        service,
    ), (
        "jv-voice no longer publishes `idle` in the statement straight after "
        "the interruption, so the caption is describing a sequence this "
        "service has stopped making — re-read it and rewrite it"
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


# ------------------------- one heartbeat, two plates, a holed recording (A85)
#
# `06-lossy` is the first photograph in this repo of the recording light
# saying anything but a bare `MIC`. Until it, the two ways an open
# microphone stops being one you can trust — silent (`MIC NO AUDIO`) and
# holed (`MIC LOSING AUDIO`) — existed only as prose and as an idle
# window's stopwatch, and the wider of the two shipped unphotographed.
#
# The shot is also the sheet's only TWO-plate picture off a single frame,
# and that is the interesting part rather than an economy: `CaptureMeter`
# calls a losing device `degraded`, so ONE jv-ears beat is a MicPlate line
# and a HealthPlate line at once. Everywhere else in this corner a second
# line means a second publisher agreeing.
#
# So the gates here are about FIDELITY. The frames are composed, which
# means nothing but this file stops them from being a heartbeat jv-ears
# would never send — and a photograph of a machine that cannot exist is
# worse than no photograph, because it looks exactly as real as the others.


def lossy() -> dict:
    for shot in sheet.SHOTS:
        if shot["file"] == "06-lossy":
            return shot
    raise AssertionError(
        "the sheet no longer takes 06-lossy — the only picture of a "
        "microphone that is open, delivering, and losing chunks anyway"
    )


def ears_beats(shot: dict) -> list[dict]:
    """Every jv-ears heartbeat body a shot puts on the bus, in any of the
    three places a shot can put frames."""
    out = []
    for frame in [
        *shot["frames"],
        *shot.get("hold", []),
        *shot.get("grows_from", []),
        *shot.get("widens_from", []),
    ]:
        pub = frame.get("publish")
        if pub and pub["topic"] == "sys.health" and pub["src"] == "jv-ears":
            out.append(pub["body"])
    return out


def capture_meter() -> str:
    return (ROOT / "services" / "jv-ears" / "jv_ears" / "audio.py").read_text("utf-8")


def test_the_lossy_body_is_a_legal_heartbeat():
    """invariant 2: schemas are law. Hand-written, so checked rather than
    trusted — a body with a key `sys.health` does not allow is one jarvisd
    would refuse and the picture would be of an empty corner.
    """
    schema = json.loads((ROOT / "schemas" / "sys.health.json").read_text("utf-8"))
    body = sheet.MIC_LOSSY["publish"]["body"]
    missing = set(schema["required"]) - set(body)
    assert not missing, f"sys.health: body is missing {sorted(missing)}"
    extra = set(body) - set(schema["properties"])
    assert not extra, f"sys.health: body has unknown keys {sorted(extra)}"
    assert body["state"] in schema["properties"]["state"]["enum"], (
        "core/HealthState.qml renders only the schema's own state words and "
        "turns anything else into `unknown` — a different finding entirely"
    )


def test_the_lossy_gauges_are_the_whole_set_jv_ears_would_publish():
    """The fixture is a photograph's worth of jv-ears, so it has to be the
    gauges jv-ears really writes for this device — all of them, and nothing
    invented. `CaptureMeter.metrics()` writes four unconditionally and two
    more once there is something to measure, and a device that is open,
    delivering AND losing has both of those.

    MIC_OPEN and MIC_DEAF are held to the same standard one fault back
    (A87) — the whole set MINUS `capture_loss_age_s`, which a device that
    has never lost a chunk really does omit, and which A43's idle window is
    measured on the absence of.
    """
    src = capture_meter()
    body = re.search(r"\n    def metrics\(.*?\n    def ", src, re.S)
    assert body, "jv_ears/audio.py no longer has a CaptureMeter.metrics()"
    body = body.group(0)
    always = set(re.findall(r'^\s+"(\w+)":', body, re.M))
    conditional = set(re.findall(r'out\["(\w+)"\]', body))
    assert always and conditional, (
        "nothing was parsed out of CaptureMeter.metrics() — its shape moved, "
        "and this gate is now asserting a fixture against an empty set"
    )
    assert set(sheet.MIC_LOSSY["publish"]["body"]["metrics"]) == always | conditional, (
        f"the composed gauges are {sorted(sheet.MIC_LOSSY['publish']['body']['metrics'])} "
        f"and jv-ears publishes {sorted(always | conditional)} for a device "
        "that is open, delivering and losing — the photograph is of a "
        "heartbeat this service does not send"
    )


def test_the_lossy_note_is_the_sentence_jv_ears_composes():
    """`notes` reaches no plate — HealthPlate draws the service and the
    word and nothing else — so this is fidelity for its own sake, and it
    is worth it: the note is the only place the two culprits are named
    apart, and the sheet is where a reader meets the format.
    """
    src = capture_meter()
    note = sheet.MIC_LOSSY["publish"]["body"]["notes"]
    for literal in (
        '"microphone losing audio: " + " and ".join(parts) + " since start"',
        'f"jv-ears dropped {lost.samples / self.rate:.1f}s"',
        'f"{lost.overruns} device overrun{plural} (length unknown)"',
    ):
        assert literal in src, (
            f"CaptureMeter.loss_note() no longer composes {literal} — re-read "
            "it and rewrite the note this sheet publishes"
        )
    assert re.fullmatch(
        r"microphone losing audio: jv-ears dropped \d+\.\ds and "
        r"\d+ device overruns? \(length unknown\) since start",
        note,
    ), (
        f"the sheet publishes {note!r}, which is not the sentence "
        "CaptureMeter.loss_note() composes when both culprits lost audio"
    )


def ears_budget(name: str) -> float:
    """A `CaptureMeter` class constant, read out of the Python that
    enforces it.

    These two are BUDGETS and not measurements: `metrics()` writes them
    from the first heartbeat, before any audio has arrived, because a
    consumer needs to know the rule before it can judge a number by it.
    So a fixture may not choose its own — there is exactly one value
    jv-ears can send, and it is this one.
    """
    src = capture_meter()
    m = re.search(rf"^    {name} = ([\d.]+)$", src, re.M)
    assert m, f"CaptureMeter no longer declares {name} — this gate is reading air"
    return float(m.group(1))


def mic_fixtures() -> dict:
    return {
        "MIC_OPEN": sheet.MIC_OPEN,
        "MIC_DEAF": sheet.MIC_DEAF,
        "MIC_LOSSY": sheet.MIC_LOSSY,
    }


def test_the_budget_gauges_are_the_constants_jv_ears_actually_ships():
    """Every mic fixture here used to publish `capture_stall_s: 2.0`, and
    there is no jv-ears that sends that: the gauge is `CaptureMeter.STALL_S`
    itself, copied onto the heartbeat unchanged. It read as a harmless
    choice because 0.02s is live and 9.4s is stalled against 2.0 exactly as
    they are against 1.0 — which is the whole trouble with an invented
    number, that it costs nothing until the day the real one moves past it
    and the sheet keeps photographing the old rule.

    Held over ALL the sheet's jv-ears beats rather than the three fixtures,
    because the next hand-written heartbeat is the one that would drift.
    """
    stall = ears_budget("STALL_S")
    loss_window = ears_budget("LOSS_S")
    seen = 0
    for shot in sheet.SHOTS:
        for body in ears_beats(shot):
            m = body.get("metrics", {})
            if not m:
                continue
            seen += 1
            assert m.get("capture_stall_s") == stall, (
                f"{shot['file']} publishes capture_stall_s "
                f"{m.get('capture_stall_s')!r} and jv-ears ships "
                f"CaptureMeter.STALL_S, which is {stall}"
            )
            assert m.get("capture_loss_window_s") == loss_window, (
                f"{shot['file']} publishes capture_loss_window_s "
                f"{m.get('capture_loss_window_s')!r} and jv-ears ships "
                f"CaptureMeter.LOSS_S, which is {loss_window}"
            )
    assert seen >= 3, (
        f"only {seen} of this sheet's heartbeats carry gauges at all, so "
        "this gate is passing by having nothing to read"
    )


def test_the_deaf_note_is_the_sentence_jv_ears_composes():
    """`notes` said "capture stalled", which is a summary of the fault and
    not a sentence any jv-ears writes: `CaptureMeter.health()` sends the
    AGE, and the age is the half a reader cannot get anywhere else — the
    plate says the device is deaf, the note says for how long.

    Nothing draws it (HealthPlate draws the service and the word), which is
    why it survived from A43 to A87 unread. Fidelity for its own sake, same
    as the lossy note above: the sheet is where a reader meets the format.
    """
    body = sheet.MIC_DEAF["publish"]["body"]
    literal = 'f"microphone open but no audio for {age:.1f}s"'
    assert literal in capture_meter(), (
        f"CaptureMeter.health() no longer composes {literal} — re-read it "
        "and rewrite the note this sheet publishes"
    )
    age = body["metrics"]["capture_age_s"]
    assert body["notes"] == f"microphone open but no audio for {age:.1f}s", (
        f"the sheet publishes {body['notes']!r} over a device last heard "
        f"from {age}s ago, which is not what jv-ears would have said"
    )


def test_the_healthy_and_deaf_gauges_are_the_whole_set_minus_the_one_loss_gauge():
    """The other two thirds of A87. `CaptureMeter.metrics()` writes four
    gauges unconditionally and two more once there is something to measure,
    and a device that is open and delivering has exactly one of the two: the
    age. The loss age is genuinely absent — a device that never lost a chunk
    omits it — so "the whole set minus that one" is not a concession to
    these fixtures, it IS the faithful body for the device they photograph.

    Which is also why adding the loss age here would not be a fidelity
    improvement but a different device: it moves MicPlate from `MIC` to
    `MIC LOSING AUDIO`, and A43's idle window measures a plate ARRIVING
    against a plate whose width does not move (see the window's own test).
    """
    src = capture_meter()
    body = re.search(r"\n    def metrics\(.*?\n    def ", src, re.S)
    assert body, "jv_ears/audio.py no longer has a CaptureMeter.metrics()"
    body = body.group(0)
    always = set(re.findall(r'^\s+"(\w+)":', body, re.M))
    conditional = set(re.findall(r'out\["(\w+)"\]', body))
    assert "capture_age_s" in conditional and "capture_loss_age_s" in conditional, (
        f"CaptureMeter.metrics() now writes {sorted(conditional)} "
        "conditionally, so the split this gate is built on has moved"
    )
    for name in ("MIC_OPEN", "MIC_DEAF"):
        gauges = set(mic_fixtures()[name]["publish"]["body"]["metrics"])
        assert gauges == always | {"capture_age_s"}, (
            f"sheet.{name} publishes {sorted(gauges)} and jv-ears publishes "
            f"{sorted(always | {'capture_age_s'})} for a device that is open, "
            "delivering and keeping all of it"
        )


def test_reporting_the_loss_window_was_safe_because_no_plate_reads_it():
    """The argument that let A87 add `capture_loss_window_s` to the two
    older fixtures at all, written down so it stays checkable.

    It moves `EarsBudgets.lossWindowS` from the pinned fallback to the
    reported value — the SAME second, since the fallback mirrors
    `CaptureMeter.LOSS_S` and a tools test fails the build if it drifts —
    and the only other thing that changes is `lossWindowReported`, which
    no plate reads. So a gauge arrived, one boolean flipped, and nothing
    on screen moved. The day a plate starts drawing that boolean, this
    goes red and the sheet's pictures need re-reading.
    """
    hud = ROOT / "shell" / "jv-hud"
    budgets = (hud / "core" / "EarsBudgets.qml").read_text("utf-8")
    assert "lossWindowReported" in budgets, (
        "core/EarsBudgets.qml no longer answers whether the loss window came "
        "off a heartbeat, so the claim below is about a property that is gone"
    )
    readers = sorted(
        f.name
        for f in hud.glob("*.qml")
        if "lossWindowReported" in f.read_text("utf-8")
    )
    assert readers == [], (
        f"{readers} now draw whether jv-ears REPORTED its loss window, so "
        "adding capture_loss_window_s to MIC_OPEN and MIC_DEAF changed what "
        "the sheet photographs — re-read the pictures before trusting them"
    )


def test_the_lossy_frame_reads_as_losing_and_not_as_the_fault_above_it():
    """`stalled` and `losing` are both degraded and only one can be drawn:
    core/MicState.qml ranks a stall first, because no audio at all is the
    bigger fact. So a fixture whose `capture_age_s` drifted past the stall
    budget would still light two plates, still pass every gate about the
    picture being lit, and put `MIC NO AUDIO` under a caption about holes.
    """
    m = sheet.MIC_LOSSY["publish"]["body"]["metrics"]
    assert m["mic_open"] == 1, (
        "the composed device is not open, so MicPlate draws nothing at all "
        "and the picture is of an empty corner"
    )
    assert m["capture_age_s"] <= m["capture_stall_s"], (
        f"the composed device last delivered {m['capture_age_s']}s ago "
        f"against jv-ears' own {m['capture_stall_s']}s budget, so MicState "
        "reads it as `stalled` and the plate says MIC NO AUDIO"
    )
    assert m["capture_loss_age_s"] <= m["capture_loss_window_s"], (
        f"the composed loss is {m['capture_loss_age_s']}s old against a "
        f"{m['capture_loss_window_s']}s window, so it is no longer news and "
        "MicPlate says a confident bare MIC"
    )
    assert '"MIC LOSING AUDIO"' in (
        ROOT / "shell" / "jv-hud" / "MicPlate.qml"
    ).read_text("utf-8"), (
        "MicPlate no longer draws the words this picture and its caption "
        "are of"
    )


def test_this_is_the_only_photograph_of_a_microphone_in_trouble():
    """The caption's claim, and the reason the shot is worth its two
    seconds. It is an ASSERTION about the other shots rather than a
    sentence: a loss gauge added to 02-heard would make that picture the
    same picture, and this one's caption would be describing a first that
    had stopped being one.
    """
    healthy = []
    for shot in sheet.SHOTS:
        if shot["file"] == lossy()["file"]:
            continue
        for body in ears_beats(shot):
            m = body.get("metrics", {})
            assert "capture_loss_age_s" not in m, (
                f"{shot['file']} now reports a discarded chunk, so its "
                "microphone is losing audio too and this shot is no longer "
                "the first picture of one"
            )
            assert m["capture_age_s"] <= m["capture_stall_s"], (
                f"{shot['file']} now photographs a stalled device, which is "
                "the other half of the same caption"
            )
            healthy.append(shot["file"])
    assert len(healthy) >= 2, (
        f"only {healthy} photograph an open microphone that is keeping all "
        "of it, so there is nothing in this sheet for the lossy picture to "
        "be read against"
    )


def test_the_lossy_shot_lights_exactly_the_two_plates_its_caption_names():
    """One frame, two plates, and every other plate dark. The two are
    welded — a losing device IS `degraded`, by CaptureMeter — so the
    caption cannot describe one of them; what it CAN stop describing is a
    third, and a third would arrive silently.
    """
    shot = lossy()
    assert "hold" not in shot and "grows_from" not in shot, (
        "06-lossy now feeds or grows from something, so it is no longer the "
        "one-frame shot its caption describes"
    )
    # `widens_from` (A86) is the one exception, and it is not a second
    # frame in the picture: it is the SAME heartbeat from the SAME service
    # with one gauge dropped, photographed and thrown away before the
    # shot re-publishes its own frame. The picture is still one beat.
    assert [f["publish"]["src"] for f in shot.get("widens_from", [])] == ["jv-ears"], (
        "06-lossy's narrower exposure is no longer one jv-ears heartbeat, "
        "so the plate it measures may have moved for a reason nobody looked "
        "at"
    )
    published = {(f["publish"]["topic"], f["publish"]["src"]) for f in shot["frames"]}
    assert published == {("sys.health", "jv-ears")}, (
        f"06-lossy publishes {sorted(published)} — one heartbeat from one "
        "service is the whole of what this picture claims"
    )

    core = ROOT / "shell" / "jv-hud" / "core"
    asks = {}
    for path in sorted(core.glob("*.qml")):
        text = path.read_text("utf-8")
        if not re.search(r'(?:latestFrom|frameOn)\("sys\.health"|publishersOf\("sys\.health"\)', text):
            continue
        asks[path.stem] = set(re.findall(r'property string \w+: "([\w-]+)"', text))
    assert sorted(asks) == [
        "DropState",
        "EarsBudgets",
        "HealthState",
        "MicState",
        "OutputState",
    ], (
        f"{sorted(asks)} read sys.health now, and this shot was measured "
        f"against five elements — a new reader may be drawing a plate the "
        "caption does not mention"
    )
    for name in ("MicState", "EarsBudgets"):
        assert asks[name] == {"jv-ears"}, (
            f"core/{name}.qml no longer asks for jv-ears by name, so the "
            "beat this shot publishes may not be the one it reads"
        )
    for name, whose in (("DropState", "jarvisd"), ("OutputState", "jv-voice")):
        assert asks[name] == {whose} and "jv-ears" not in asks[name], (
            f"core/{name}.qml now reads a jv-ears heartbeat, so this frame "
            "lights a plate the caption does not name"
        )
    assert "publishersOf(\"sys.health\")" in (core / "HealthState.qml").read_text("utf-8"), (
        "core/HealthState.qml no longer reads every publisher of sys.health, "
        "so a degraded jv-ears may no longer reach HealthPlate and the "
        "caption's second line is of a plate that is dark"
    )

    hud = ROOT / "shell" / "jv-hud"
    plates = {path.stem: path.read_text("utf-8") for path in hud.glob("*Plate.qml")}

    def instantiates(text: str, element: str) -> bool:
        # The declaration, not a mention: every one of these files talks
        # about the others in prose, and a plate that merely names an
        # element draws nothing off it.
        return re.search(rf"\b{element} {{", text) is not None

    drawn = sorted(
        name
        for name, text in plates.items()
        if instantiates(text, "MicState") or instantiates(text, "HealthState")
    )
    assert drawn == ["HealthPlate", "MicPlate"], (
        f"{drawn} draw the elements this frame can light on its own, and "
        "the caption describes two plates"
    )
    # The fifth reader is the odd one, and it is not a third plate.
    # EarsBudgets carries jv-ears' own budgets into whichever plate asked
    # for them and decides nothing; StatePlate takes them for the wake
    # window and stays dark here, because the topics it draws off are not
    # on this bus.
    budgeted = sorted(
        name for name, text in plates.items() if instantiates(text, "EarsBudgets")
    )
    assert budgeted == ["MicPlate", "StatePlate"], (
        f"{budgeted} take jv-ears' budgets now — a new one may be a plate "
        "this heartbeat lights"
    )
    speech = (core / "SpeechState.qml").read_text("utf-8")
    subjects = set(re.findall(r'(?:frameOn|bus\.latest\w*)\("([\w.]+)"', speech))
    assert subjects, "core/SpeechState.qml reads no topic at all"
    assert not subjects & {topic for topic, _ in published}, (
        f"core/SpeechState.qml now reads {sorted(subjects & {t for t, _ in published})}, "
        "so StatePlate may light off this heartbeat and the caption names "
        "two plates"
    )


# ------------------------------- the word, and not the box around it (A86)
#
# Every growth assertion this harness had proved a plate ARRIVED: same
# top, same right edge, a taller union. None of them could see a plate
# that stayed exactly where it was and said a LONGER WORD, which is what
# `06-lossy` is a picture of — and so, until A86, nothing in a run would
# have noticed if that picture said `MIC`.
#
# The first thing A86 asked for was a MEASUREMENT and not a gate, because
# the arithmetic said the widening might be worth about a pixel. It is
# worth ZERO. The `deaf -> lossy` pair was photographed through the real
# compositor and the union was (2380, 16, 2543, 93) under BOTH readings:
# `MIC LOSING AUDIO` and `jv-ears DEGRADED` are both sixteen characters of
# 11 px mono, both plates measure 164 px, and the box around the two of
# them cannot tell them apart. So the rectangle this is measured on is the
# plate's own BAND, and these are the gates on that.


def test_row_bands_cuts_the_drawn_rows_into_plates():
    """One contiguous run of drawn rows is one plate, because the stack
    separates its plates with `Theme.gapPx` of untouched desktop and every
    plate is a filled rectangle of glass.
    """
    assert sheet.row_bands([]) == [], "a bare monitor holds no plates"
    assert sheet.row_bands([16]) == [(16, 16)], "one row is one band"
    assert sheet.row_bands(range(16, 51)) == [(16, 50)], "one plate is one band"
    # The real thing, read off 06-lossy-primary.png: MicPlate at 16-50,
    # eight rows of desktop, HealthPlate at 59-93.
    assert sheet.row_bands([*range(16, 51), *range(59, 94)]) == [(16, 50), (59, 93)], (
        "the gap between two plates is not being read as the end of one"
    )
    assert sheet.row_bands([*range(16, 51), *range(51, 94)]) == [(16, 93)], (
        "two plates with no desktop between them are ONE run and must be "
        "reported as one — a band rule that invented a boundary would let "
        "the check below measure a rectangle no plate has"
    )
    assert sheet.row_bands(r for r in [16, 17, 30]) == [(16, 17), (30, 30)], (
        "row_bands must accept the iterator numpy hands it"
    )


def test_the_widening_rule_is_the_geometry_one_plate_actually_has():
    """A plate docked to the right that swaps a word for a longer word
    keeps its top, its bottom and its right edge exactly, and reaches
    further LEFT. Every other edge moving is a different claim, and the
    one that matters most is the equal-length case: `MIC NO AUDIO` and
    `MIC LOSING AUDIO` are told apart by four characters and nothing else,
    so a word the same width as the one before it must fail.
    """
    deaf = (2412, 16, 2543, 50)
    assert sheet.widened(deaf, (2380, 16, 2543, 50)), "four more characters"
    assert not sheet.widened(deaf, deaf), "the same word"
    assert not sheet.widened(deaf, (2484, 16, 2543, 50)), (
        "the plate got SHORTER — this is the `MIC` the whole item is about"
    )
    assert not sheet.widened(deaf, (2380, 16, 2543, 93)), (
        "the bottom moved: a second line, or a different plate entirely"
    )
    assert not sheet.widened(deaf, (2380, 24, 2543, 50)), (
        "the top moved: the stack above this plate changed, so this is not "
        "the same plate measured twice"
    )
    assert not sheet.widened(deaf, (2380, 16, 2500, 50)), (
        "the right edge moved: the plate is no longer docked where it was"
    )
    assert not sheet.widened(None, deaf), "nothing was drawn first"
    assert not sheet.widened(deaf, None), "nothing is drawn now"


def test_the_lossy_shot_measures_its_word_against_the_deaf_reading():
    """MIC_DEAF is the only fixture the widening can be measured against,
    and the reason is HealthPlate: both bodies are the same `degraded`
    from the same jv-ears, so the line under the microphone is identical
    and the mic plate is the only thing in the corner that can move.

    Checked on the two keys HealthPlate actually draws rather than on the
    whole body, because the whole body is SUPPOSED to differ — that is
    what makes the word change.
    """
    shot = lossy()
    narrow = shot["widens_from"]
    assert len(narrow) == 1 and narrow[0] is sheet.MIC_DEAF, (
        f"06-lossy widens from {narrow}, and MIC_DEAF is the only heartbeat "
        "in this sheet that draws the same health line under a different "
        "microphone line"
    )
    before = narrow[0]["publish"]["body"]
    after = shot["frames"][0]["publish"]["body"]
    assert (before["service"], before["state"]) == (after["service"], after["state"]), (
        f"the narrower exposure reports {before['service']} {before['state']} "
        f"and the picture reports {after['service']} {after['state']} — "
        "HealthPlate draws exactly those two, so the band under the "
        "microphone would move too and the measurement would isolate nothing"
    )
    moved = sorted(
        k
        for k in set(before["metrics"]) | set(after["metrics"])
        if before["metrics"].get(k) != after["metrics"].get(k)
    )
    assert moved == ["capture_age_s", "capture_loss_age_s"], (
        f"the two exposures differ on {moved} — the gauges that may move "
        "are the two core/MicState.qml turns into the word, and anything "
        "else is a second reason the plate changed"
    )


def test_the_widening_is_measured_on_a_band_and_the_box_is_why():
    """The rectangle is the point of the whole item. `drawn_box` is the
    union of every plate on the monitor and it does not move between these
    two exposures — photographed, not argued — so a check written on it
    would be a permanent, flawless pass over a picture that could say
    anything.
    """
    loop = shot_loop_text()
    assert "wide = drawn_bands(img, background)" in loop, (
        "the shot loop no longer measures the widening on the plate's own "
        "band"
    )
    assert "narrow = drawn_bands(narrower, background)" in loop, (
        "the narrower exposure is no longer cut into bands, so the two "
        "sides of the comparison are not the same rectangle"
    )
    assert "sheet.widened(narrow[which], wide[which])" in loop, (
        "the shot loop no longer asks sheet.widened — an inline copy of the "
        "geometry is one the unit tests above do not cover"
    )
    assert "drawn_box" not in loop.split('if shot.get("widens_from")')[-1].split(
        "name = f\""
    )[0], (
        "the widening is being measured off drawn_box again, which is the "
        "union of the plates and is the SAME four numbers under both of "
        "these readings"
    )


def test_the_lossy_shot_puts_its_own_frame_back_after_the_narrower_one():
    """The trap this measurement walks into. `grows_from`'s shot declares
    a `hold`, so the settle after the thrown-away exposure re-feeds the
    real frames; 06-lossy deliberately declares none, so without an
    explicit re-publish the settle SLEEPS and the picture committed to the
    sheet is of the NARROWER reading under the wider one's caption — and
    every check here would pass, because the plate really did widen at the
    moment it was measured.
    """
    loop = shot_loop_text()
    after = loop.split('if shot.get("widens_from"):')[1]
    before_settle = after.split("settle(SETTLE_S, hold, bus_addr)")[0]
    assert "publish_shot(shot, bus_addr)" in before_settle, (
        "the shot loop no longer re-publishes a widens_from shot's own "
        "frames after the narrower exposure, so the picture it writes is of "
        "the exposure it was supposed to throw away"
    )


def test_the_band_measurement_refuses_a_pair_that_isolates_nothing():
    """A widening is only evidence about the word if the rest of the
    corner held still. A second plate arriving, or the health line
    changing under the microphone, would move the band the check reads or
    the one beside it — and either would make a pass mean nothing.
    """
    loop = shot_loop_text()
    assert "len(wide) != len(narrow)" in loop, (
        "the shot loop no longer refuses a pair whose plate COUNT changed, "
        "so band 0 may not be the same plate in both exposures"
    )
    assert "if i != which and wide[i] != narrow[i]" in loop, (
        "the shot loop no longer insists every OTHER band is pixel-identical "
        "across the pair, which is the only thing making the widening "
        "evidence about the microphone line rather than about the corner"
    )
    assert lossy()["widens_band"] == 0, (
        "06-lossy measures a band other than the top one, and MicPlate sits "
        "ABOVE HealthPlate in shell.qml's stack"
    )
    stack = (ROOT / "shell" / "jv-hud" / "shell.qml").read_text("utf-8")
    order = re.findall(r"^        (\w+Plate) {$", stack, re.M)
    assert order.index("MicPlate") < order.index("HealthPlate"), (
        "HealthPlate now sits above MicPlate, so 06-lossy's `widens_band` "
        "names the wrong plate and the run would measure the health line"
    )


def test_the_readme_reads_the_holed_recording_picture():
    """A photograph nobody is told how to read is decoration, and this one
    needs three things a reader cannot get from the pixels: which words are
    on it, that ONE heartbeat put both of them there, and what the same
    plate looks like when the microphone is fine.

    The phrases below are therefore reserved: a rewrite that drops them
    turns this gate red, which is the point — re-read the picture and
    write the new sentence.
    """
    readme = readme_text()
    for name in sheet.capture_files(lossy()):
        assert name in readme, f"docs/hud/screens/README.md never shows {name}"
    section = [s for s in readme.split("\n### ") if "06-lossy-primary.png" in s]
    assert len(section) == 1
    section = section[0]
    assert "MIC LOSING AUDIO" in section, (
        "the caption never names the line the picture is of"
    )
    assert "jv-ears DEGRADED" in section, (
        "the caption never names the second plate, which is half of why "
        "this shot exists"
    )
    assert re.search(r"\bone\b[^.]*\bheartbeat\b", section), (
        "the caption never says the two lines come from ONE heartbeat — "
        "without it this reads as two services agreeing, which is what "
        "every other two-plate picture in this sheet actually is"
    )
    # By anchor, and it has to be: every PNG here is shown in exactly ONE
    # `###` section (the gate that says which screens are recordings), so
    # a caption cannot link to another picture by its file name.
    assert "03-confirm-primary" in section, (
        "the caption never points at a picture of the same plate over a "
        "microphone that is keeping all of it, so there is nothing to read "
        "the warn dot and the second word against"
    )
    assert "teal" in section, (
        "the caption never says the dot stopped being teal, which is the "
        "only part of this picture a reader sees before they read a word"
    )


# ------------------------------------------------ the numbers in the prose (A73)
#
# Every measurement above is derived: shoot.py checks the corner against
# `sheet.SURFACE_*`, which this file checks against `shell.qml`. The PROSE
# was not. `docs/hud/screens/README.md` quoted the surface box three times
# and said `300x560`, which was true when A30 wrote it and stopped being
# true four plates later — the box went 560 -> 624 -> 688 -> 745 -> 807 and
# the sentence never moved, because no gate had ever read it.
#
# That is the same class of failure as a stale `SURFACE_H`, one document
# down: a number a reader trusts, that nothing checks. So the boxes the
# prose quotes are pinned to the boxes the harness declares, the way
# `test_the_surface_box_is_the_one_shell_qml_declares` pins the harness to
# the HUD.

def readme_text() -> str:
    return (SCREENS / "README.md").read_text("utf-8")


def declared_boxes() -> dict[tuple[int, int], str]:
    """Every WxH this harness can honestly be describing, and what each one
    is — the surface, each monitor, the whole desk, and the older surface
    the committed pictures were taken against."""
    boxes = {
        (sheet.SURFACE_W, sheet.SURFACE_H): "the surface shell.qml declares",
        (sheet.DESK_WIDTH, sheet.DESK_HEIGHT): "the whole desk",
        shot_box(): "the surface the committed PNGs were photographed against",
    }
    for out in sheet.ALL_OUTPUTS:
        boxes.setdefault((out["width"], out["height"]), f"the {out['role']} monitor")
    return boxes


def shot_box() -> tuple[int, int]:
    return sheet.shot_surface_box(ROOT, str(SCREENS.relative_to(ROOT)))


def test_every_box_the_readme_quotes_is_one_the_harness_declares():
    """The sentence that went stale said `300x560` while shoot.py measured
    against 807, and a reader has no way to tell which of the two is the
    HUD. There is no third source here: a box in this document is the
    surface, a monitor, the desk, or the older surface these pictures were
    taken against — and anything else is a number somebody typed.
    """
    allowed = declared_boxes()
    quoted = sheet.boxes_in_prose(readme_text())
    assert quoted, (
        "docs/hud/screens/README.md quotes no box at all — this gate has "
        "stopped reading the thing it was built for"
    )
    for box in sorted(quoted - set(allowed)):
        raise AssertionError(
            f"docs/hud/screens/README.md quotes {box[0]}x{box[1]}, which is "
            f"nothing this harness declares. It knows "
            + ", ".join(f"{w}x{h} ({what})" for (w, h), what in sorted(allowed.items()))
        )


def test_the_readme_says_its_pictures_predate_the_box_it_quotes():
    """Pinning the prose to `sheet.py` makes the document MORE wrong on its
    own if nothing else changes: the box in the text becomes today's and
    the pictures are still yesterday's, so a reader measures a 688 px HUD
    against an 807 px sentence and finds the sheet lying to them.

    Both numbers are derived — today's from `tools/hudscreens/sheet.py`,
    the pictures' from the commit that last wrote a PNG here — so the
    notice cannot itself go stale, and a re-shoot retires it rather than
    updating it.

    It has been retired (B93 added a screen, so the last commit to write
    one here declared today's box), and this test is now guarding the
    other edge: the notice must not come BACK while the pictures are
    current, and it must return the moment the box moves without them. The
    phrase it keys on is therefore reserved — the paragraph that replaced
    the notice deliberately does not use it, because prose saying a
    condition is over reads to a substring search exactly like prose
    saying it holds.
    """
    then, now = shot_box(), (sheet.SURFACE_W, sheet.SURFACE_H)
    readme = readme_text()
    if then == now:
        assert "older than the box" not in readme, (
            "the committed screens were taken against today's surface box, so "
            "docs/hud/screens/README.md still carries a staleness notice that "
            "is no longer true — delete it"
        )
        return
    assert "older than the box" in readme, (
        f"the committed screens were photographed against a {then[0]}x{then[1]} "
        f"surface and shoot.py now measures {now[0]}x{now[1]}, and "
        "docs/hud/screens/README.md does not say so — every caption below is "
        "then a description of a HUD that is not in the picture"
    )
    for w, h in (then, now):
        assert f"{w}x{h}" in readme, (
            f"docs/hud/screens/README.md says its pictures are older than the "
            f"box without naming {w}x{h} — a reader cannot tell by how much"
        )


# The picture's own box is read out of git rather than written down, which
# is the only version of this that survives: the last three times the
# surface grew, somebody would have had to remember to bump a literal here,
# and the PLAN item that raised this had the number wrong (it says 745; the
# commit that last wrote a PNG here declared 688).


def mkscreens(tmp_path: Path, then: int, now: int) -> Path:
    """A repo shaped like this one's two halves: a sheet module declaring a
    box, and a directory of pictures taken against it. The box then moves
    with the pictures left alone, which is exactly what this repo did."""
    root = tmp_path / "repo"
    (root / "tools" / "hudscreens").mkdir(parents=True)
    (root / "docs" / "hud" / "screens").mkdir(parents=True)

    def git(*args):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)

    def sheet_py(height):
        (root / "tools" / "hudscreens" / "sheet.py").write_text(
            f"SURFACE_W = 300\nSURFACE_H = {height}\n", "utf-8"
        )

    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    sheet_py(then)
    (root / "docs" / "hud" / "screens" / "01-quiet-desk.png").write_bytes(b"\x89PNG")
    git("add", "-A")
    git("commit", "-qm", "shot")
    sheet_py(now)
    (root / "docs" / "hud" / "screens" / "README.md").write_text("prose", "utf-8")
    git("add", "-A")
    git("commit", "-qm", "the box grew, the pictures did not")
    return root


def test_the_shot_box_is_the_one_in_force_when_the_pictures_were_written():
    """Against this repo, where the answer is a fact about its history. For
    a long time it was 688 — the PNGs were last written by the commit that
    took the box there, and five growths after it moved the box without
    moving a picture. B93 added a screen, so the last commit to write one
    is a recent one and the answer is today's box; the notice that existed
    for the gap between the two is retired rather than updated, which is
    what `test_the_readme_says_its_pictures_predate_the_box_it_quotes`
    asserts from the other side."""
    assert shot_box() == (300, 826)


def test_the_shot_box_is_read_out_of_git_and_not_the_working_copy(tmp_path):
    """The whole point. The working copy's `sheet.py` says what the harness
    would photograph TODAY; the pictures were photographed by whatever it
    said on the day they were written, and that copy exists only in git.
    """
    root = mkscreens(tmp_path, then=688, now=807)
    assert sheet.shot_surface_box(root, "docs/hud/screens") == (300, 688)


def test_a_directory_with_no_pictures_in_it_is_refused():
    """`git log -- <dir>/*.png` on a directory with no pictures prints
    nothing, and `git show :sheet.py` on an empty revision would answer
    with the WORKING COPY. That reads as "the pictures are current", which
    is the one wrong answer nobody would think to question."""
    with pytest.raises(ValueError):
        sheet.shot_surface_box(ROOT, "personality")


def test_pictures_older_than_the_sheet_are_an_error_rather_than_todays_box(tmp_path):
    """The other way the question can have no answer: a picture committed
    before this file existed. `git show` fails, and it must be allowed to.
    """
    root = tmp_path / "repo"
    (root / "docs" / "hud" / "screens").mkdir(parents=True)
    (root / "docs" / "hud" / "screens" / "01-quiet-desk.png").write_bytes(b"\x89PNG")
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    for args in (
        ("config", "user.email", "t@t"),
        ("config", "user.name", "t"),
        ("add", "-A"),
        ("commit", "-qm", "a picture, and no sheet to have taken it"),
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    with pytest.raises(subprocess.CalledProcessError):
        sheet.shot_surface_box(root, "docs/hud/screens")


def test_a_sheet_that_declares_no_box_is_refused():
    """The parser is the instrument. If `sheet.py` is reshaped so the box is
    no longer two module-level ints, this must stop rather than quietly
    return half an answer."""
    assert sheet.parse_surface_box("SURFACE_W = 300\nSURFACE_H = 807\n") == (300, 807)
    with pytest.raises(ValueError):
        sheet.parse_surface_box("SURFACE_W = 300\n")
    with pytest.raises(ValueError):
        sheet.parse_surface_box("# SURFACE_W = 300\n# SURFACE_H = 807\n")


def test_the_prose_scanner_reads_a_box_however_a_person_typed_it():
    """The instrument, over the shapes this document actually uses: an
    `x`, a `×`, and either with spaces around it. A scanner that stopped
    matching would report a clean README forever, which is precisely the
    silence the stale `300x560` lived in for five plates.
    """
    assert sheet.boxes_in_prose("the 300x807 box") == {(300, 807)}
    assert sheet.boxes_in_prose("300 × 807 px, the box") == {(300, 807)}
    assert sheet.boxes_in_prose("a 2560 x 1440 panel and a 300x807 surface") == {
        (2560, 1440),
        (300, 807),
    }


def test_the_prose_scanner_is_not_reading_ordinary_prose():
    """...and it has to stay narrow, because this README is full of
    numbers: opacities, pixel counts, drawn regions, seconds. Anything it
    picked up out of those would be a box no harness declares, and the gate
    would fail on a document that is perfectly correct.
    """
    assert sheet.boxes_in_prose("an 11 px label at 0.86 opacity") == set()
    assert sheet.boxes_in_prose("the region (2284, 16, 2543, 178)") == set()
    assert sheet.boxes_in_prose("six windows, 807 px tall, 745 before") == set()


# ------------------------- reading the screens back, with a floor (B74)
#
# `hudshots.sh` has compared its own sheet against HEAD since B52. This
# harness could not: it photographs a real compositor, and two runs of an
# unchanged HUD do not agree to the byte. So for thirty iterations these
# the pictures were WRITTEN and never READ, and nothing in the repo could
# tell a current screen from one taken four plates ago.


def test_the_harness_reads_its_own_sheet_back():
    """The whole of B74: a sheet that can only be overwritten is a sheet that
    cannot go stale out loud. It goes stale silently instead."""
    text = driver_text()
    assert "tools/hudsheet.py" in text, (
        "ops/ralph/hudscreens.sh takes its photographs and never compares "
        "one — a stale screen looks exactly as convincing as a current one"
    )
    assert "--sheet docs/hud/screens" in text, (
        "the screens are compared against some other sheet than their own"
    )


def test_the_floor_it_compares_with_is_the_measured_one():
    """Written down twice is how a measurement goes out of date. The numbers
    live in tools/hudscreens/sheet.py, beside the measurement that set them,
    and the driver reads them from there."""
    text = driver_text()
    assert "sheet.NOISE_PIXELS" in text and "sheet.NOISE_CHANNEL" in text, (
        "ops/ralph/hudscreens.sh does not take its floor from sheet.py"
    )
    for literal in (str(sheet.NOISE_PIXELS), str(sheet.NOISE_CHANNEL)):
        assert f"--tolerance-pixels {literal}" not in text
        assert f"--tolerance-channel {literal}" not in text


def test_it_restores_only_over_the_sheet_it_was_compared_against():
    """--accept-noise puts committed bytes over rendered ones, which is only
    honest for the committed sheet itself. A run pointed at a scratch
    directory is a measurement or a grading run, and must come back holding
    exactly what it rendered — the next person measuring the noise would
    otherwise be measuring the restore."""
    code = [
        line
        for line in driver_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    guarded = [line for line in code if "--accept-noise" in line]
    assert len(guarded) == 1, guarded
    assert "docs/hud/screens" in guarded[0], (
        "ops/ralph/hudscreens.sh restores committed bytes without first "
        f"checking that it is writing over the committed sheet: {guarded[0]!r}"
    )


def test_the_floor_is_far_below_anything_a_plate_can_say():
    """The bound that does the discriminating, checked against the palette it
    is an argument about. §06's text on §06's glass is the FAINTEST thing the
    HUD draws, and it is two orders of magnitude past the floor; the ember is
    further still. A floor raised to where it could swallow a word would fail
    here rather than in a photograph nobody compared.
    """
    palette = tomllib.loads((ROOT / "personality" / "theme.toml").read_text("utf-8"))["palette"]
    glass = hudsheet.parse_hex(palette["ground_deep"])
    for quietest in ("text_3", "teal", "ember"):
        ink = hudsheet.parse_hex(palette[quietest])
        apart = max(abs(a - b) for a, b in zip(ink, glass))
        assert apart > 10 * sheet.NOISE_CHANNEL, (
            f"{quietest} is {apart} from the plate it is drawn on and the "
            f"screens' floor forgives {sheet.NOISE_CHANNEL} per channel — "
            "the floor is close enough to a legible change to hide one"
        )


def test_the_readme_states_the_floor_the_harness_compares_with():
    """The numbers in the prose, pinned to the numbers in the code (A73's
    rule, applied to B74's). A README that quotes a floor the harness no
    longer uses is worse than one that quotes none."""
    readme = (SCREENS / "README.md").read_text("utf-8")
    # Both numbers in the units they are quoted in, because a bare `256` is
    # also the first three digits of this monitor and a bare `3` is in every
    # other sentence on the page — a gate either reads the claim or it reads
    # the page it happens to be printed on.
    assert f"{sheet.NOISE_PIXELS} px" in readme, (
        "docs/hud/screens/README.md does not say how many pixels the harness "
        f"forgives, which is {sheet.NOISE_PIXELS}"
    )
    assert f"{sheet.NOISE_CHANNEL} per channel" in readme, (
        "docs/hud/screens/README.md does not say how faint a difference has "
        f"to be to be forgiven, which is {sheet.NOISE_CHANNEL} per channel"
    )


# ------------------------------ where the run's time goes (B75)
#
# `verify.sh` names this gate and does not run it, on one reason B74 left
# standing: it costs minutes and produces pictures rather than a verdict.
# B75 asks whether a CHEAPER HALF exists — the probes are verdicts, the
# screens are not — and nobody could answer it, because the cost was a
# single number with no parts in it. The run books its own seconds now,
# and `sheet.PHASES` says which half each phase belongs to.
#
# These are the gates on the ACCOUNTING, which is the part that can lie:
# a table that drops a phase, or charges one stretch twice, would report a
# cheap sheet-half that is not there and get this gate bound on a fiction.


def booked_phases():
    """Every phase name the two halves of the harness actually book."""
    shoot = (ROOT / "tools" / "hudscreens" / "shoot.py").read_text("utf-8")
    return set(re.findall(r'cost\.phase\("([a-z]+)"\)', shoot)) | set(
        re.findall(r"^\s*book ([a-z]+) ", driver_text(), re.M)
    )


def test_every_phase_the_harness_books_is_classified_and_the_other_way_round():
    """The two ends of the split. A phase the harness books and nothing
    classifies would be charged to neither half — so the table would be
    printed under a total that excludes it, and the sheet half would look
    smaller than it is. A phase classified here and booked by nobody is a
    row that silently never appears, which is how a gate gets bound on a
    price that was never measured.
    """
    assert booked_phases() == set(sheet.PHASES), (
        "the phases the harness books and the phases sheet.PHASES classifies "
        f"disagree: booked-only {sorted(booked_phases() - set(sheet.PHASES))}, "
        f"classified-only {sorted(set(sheet.PHASES) - booked_phases())}"
    )


def test_the_expensive_probes_are_booked_as_probes_and_the_pictures_as_sheet():
    """The classification is the whole answer to B75, so it is asserted and
    not just declared: the two probes `verify.sh` would want a verdict from
    are on the bill a picture-less run still pays, and the two things only
    the sheet needs — the PNG encodes and reading them back against HEAD —
    are the only ones on the other side.
    """
    kinds = {name: kind for name, (kind, _) in sheet.PHASES.items()}
    assert kinds["idle"] == sheet.PROBE and kinds["click"] == sheet.PROBE
    assert {n for n, k in kinds.items() if k == sheet.SHEET} == {"encode", "compare"}


def test_the_table_accounts_for_every_second_of_the_run():
    """The seconds nobody booked are PRINTED, not dropped. A table that
    silently summed to less than the run took would let the next reader
    divide a half by a total the rows never covered."""
    table = "\n".join(sheet.cost_table([("idle", 60.0), ("encode", 8.0)], 100.0))
    assert "unaccounted" in table
    assert "32.0 s" in table, table


def test_a_phase_that_ran_four_times_is_one_row():
    """Every shot books `processes` and `capture`, so the rows are sums. Four
    rows for four shots would be a table nobody can compare against the next
    run's, which is the only use it has."""
    table = "\n".join(sheet.cost_table([("capture", 1.5)] * 4, 100.0))
    assert len([l for l in table.splitlines() if " capture " in l]) == 1, table
    assert "6.0 s" in table, table


def test_the_two_halves_are_summed_and_shown_as_shares_of_the_run():
    """The bottom line is what B75 gets read for: what a verdict-only run
    would still pay, next to what only the pictures cost."""
    table = "\n".join(
        sheet.cost_table(
            [("idle", 60.0), ("click", 20.0), ("encode", 8.0), ("compare", 2.0)],
            100.0,
        )
    )
    assert f"{sheet.PROBE}" in table and f"{sheet.SHEET}" in table
    assert "80.0 s" in table and "10.0 s" in table, table
    assert "80.0%" in table and "10.0%" in table, table


def test_a_phase_nobody_classified_is_refused_rather_than_ignored():
    """An unknown phase is a table missing a row and a total missing its
    seconds. Refusing it is what makes the gate above enforceable."""
    with pytest.raises(ValueError, match="grim"):
        sheet.cost_table([("grim", 1.0)], 10.0)


def test_an_accounting_that_charges_more_than_the_run_took_is_refused():
    """The one bookkeeping error this table cannot survive: a phase opened
    inside another one charges the same stretch twice, and the sheet half
    would come out cheaper than it is — which is a gate bound on a fiction.
    """
    with pytest.raises(ValueError, match="twice"):
        sheet.cost_table([("idle", 60.0), ("click", 60.0)], 100.0)
    # Tenths are two clocks rounding, not double counting.
    sheet.cost_table([("idle", 100.2)], 100.0)


def test_a_run_that_took_no_time_is_refused():
    """Every share in the table is a fraction of the total."""
    with pytest.raises(ValueError, match="no time"):
        sheet.cost_table([], 0.0)


def test_the_book_refuses_a_phase_opened_inside_another(tmp_path):
    """The runtime half of the same rule. `capture` is called by the shot
    loop AND from inside both probes, so a `cost.phase` in the wrong place
    is a live hazard rather than a hypothetical one — and it would be
    invisible in the table, which is exactly why it raises here instead.
    """
    ticks = iter([0.0, 1.0, 2.0, 3.0])
    cost = sheet.Cost(tmp_path / "cost.tsv", clock=lambda: next(ticks))
    with pytest.raises(RuntimeError, match="inside"):
        with cost.phase("idle"):
            with cost.phase("capture"):
                pass


def test_the_book_records_a_phase_whose_body_failed(tmp_path):
    """A run that dies in a check has still spent the seconds, and the
    stretch it died in is the one worth reading."""
    # The ticks do not start at zero on purpose: a book that wrote down the
    # clock instead of the ELAPSED time would agree with a run that did,
    # forever, if every fake clock in these tests started at 0.0.
    ticks = iter([5.0, 12.0])
    cost = sheet.Cost(tmp_path / "cost.tsv", clock=lambda: next(ticks))
    with pytest.raises(KeyError):
        with cost.phase("checks"):
            raise KeyError("a check said no")
    assert sheet.read_cost((tmp_path / "cost.tsv").read_text("utf-8")) == [
        ("checks", 7.0)
    ]


def test_the_book_opens_the_next_phase_after_closing_the_last(tmp_path):
    """The nesting guard, turned back on the run that respects it. A book
    that never CLOSED a phase would refuse every phase after the first, and
    a harness that books ten of them would die in the second shot — which
    every test around this one misses, because each opens exactly one.
    """
    ticks = iter([0.0, 2.0, 10.0, 13.0])
    cost = sheet.Cost(tmp_path / "cost.tsv", clock=lambda: next(ticks))
    with cost.phase("capture"):
        pass
    with cost.phase("encode"):
        pass
    assert sheet.read_cost((tmp_path / "cost.tsv").read_text("utf-8")) == [
        ("capture", 2.0),
        ("encode", 3.0),
    ]


def test_the_book_is_a_file_because_two_processes_write_it(tmp_path):
    """Half the phases are bash's (the flake, the compositor, the
    comparison) and half are the driver's. Appending, not rewriting: the
    shell's lines are already in the file when python opens it."""
    path = tmp_path / "cost.tsv"
    path.write_text("realize\t12.500\n", "utf-8")
    ticks = iter([100.0, 103.0])
    with sheet.Cost(path, clock=lambda: next(ticks)).phase("click"):
        pass
    assert sheet.read_cost(path.read_text("utf-8")) == [
        ("realize", 12.5),
        ("click", 3.0),
    ]


def test_a_line_neither_half_wrote_is_refused():
    """The file is read by one side and written by two, in two languages."""
    with pytest.raises(ValueError, match="seconds"):
        sheet.read_cost("realize 12.5\n")


def test_the_run_prints_its_table_even_when_the_sheet_changed():
    """The interesting run is the one whose comparison says the HUD moved —
    it exits nonzero by design, and under `set -e` that would take the
    table with it. The price of the run a human is looking at is the price
    worth knowing."""
    driver = driver_text()
    assert "compare_status=$?" in driver and "exit $compare_status" in driver, (
        "ops/ralph/hudscreens.sh lets the comparison's exit status end the "
        "run, so the one run whose cost anybody asks about prints no table"
    )
    assert driver.index("cost_table(") > driver.index("tools/hudsheet.py"), (
        "the table is printed before the comparison it is supposed to price"
    )


# ------------------------- what the real shell said, read back (D39)
#
# Twelve real quickshells run in a pass of this harness — one per shot, one
# per idle window — and every one of them has written its output to a file
# since the first version of it, where nothing ever opened it. D36 made the
# three STAGED harnesses refuse a run whose QML threw; this is the same rule
# over the only gate that loads `shell.qml` at all.


def test_the_root_quickshells_paths_are_under_is_the_hud_this_photographs():
    """`sheet.SHELL_ROOT` is what turns `@core/BusModel.qml` in a log into a
    file this repository has. A root that named the wrong directory would
    produce a report whose every path is a plausible lie."""
    root = ROOT / sheet.SHELL_ROOT
    assert (root / "shell.qml").is_file(), (
        f"{sheet.SHELL_ROOT} is not the directory quickshell is pointed at — "
        "it holds no shell.qml"
    )
    assert (root / "core" / "BusModel.qml").is_file(), root


def test_the_shell_root_is_declared_where_the_script_cannot_write_it():
    """The other half of the staging rule. `SHELL_ROOT` lives in `sheet.py`
    because `hudscreens.sh` may not contain that path in any line it executes,
    and a constant nobody reads would be a comment. So: the script asks for
    it, and does not spell it."""
    code = [
        line
        for line in driver_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert any("SHELL_ROOT" in line for line in code), (
        "ops/ralph/hudscreens.sh does not read sheet.SHELL_ROOT, so the scan's "
        "report names paths relative to a store path"
    )


def test_every_shell_this_starts_is_one_this_heard_from():
    """The liveness half of the D39 scan, and the reason it needs no census
    of its own. `tools/qmlprobe/Probe.qml` exists because a staged scene that
    silently built nothing would scan clean; here the harness already proves
    each log is live before it uses it — every `Proc("jv-hud", …)` is followed
    by `wait_for("Configuration Loaded")`, which is quickshell's own handler
    writing that exact line into that exact file. A shell whose log stayed
    empty never gets past its own start.

    So: as many waits as shells. One more shell than waits and a log nobody
    ever proved was being written would be handed to a scanner that can only
    report what it reads.
    """
    shoot = (ROOT / "tools" / "hudscreens" / "shoot.py").read_text("utf-8")
    shells = len(re.findall(r'"jv-hud",', shoot))
    heard = shoot.count('wait_for("Configuration Loaded")')
    assert shells and shells == heard, (
        f"{shells} jv-hud processes are started and {heard} are waited for — a "
        "shell nobody heard from writes a log the D39 scan cannot speak for"
    )


# ------------------- the ceiling on a pathological run (D58)
#
# `shellload.sh` has had a per-engine ceiling since D50, and D53 then found
# 90 s of un-payable cold-Qt wait inside it. This harness — the other gate
# that runs real quickshells — had NO ceiling at all. 3m00s is its measured
# cost (B75 books the phases); nothing anywhere bounded the run where a
# quickshell comes up and then holds still forever, and that run has to end,
# be reported, and not take the afternoon with it.
#
# What is bounded here is every stretch of `shoot.py` that WAITS: a timeout,
# a settle, a poll loop with a deadline. What is NOT is work — `grim`, a PNG
# encode, a numpy compare, and the two binaries' own exec. A subprocess that
# never returns is outside this claim and stays outside it; the claim is that
# no wait this file chooses to spend is unbounded or unaccounted.
#
# The arithmetic is D50's lesson applied to a bigger file: the waits are
# COUNTED OFF THE SOURCE rather than written down, because a wait added to
# the run and not to the ceiling is exactly the hole D50 found — and at this
# size (about ninety wait sites) a hand-written list would be stale within an
# iteration. So `wait_sites()` walks the AST, every site must land in a
# stretch or in a helper whose call sites are charged, and a way of waiting
# nobody taught this file is refused by name rather than ignored.

SHOOT = ROOT / "tools" / "hudscreens" / "shoot.py"

# A poll inside a bounded loop is free — it is spent INSIDE the deadline, not
# on top of it. What it does cost is one last pass through the body, begun an
# instant before the deadline and finished after it, and the widest body here
# is `wait_for_drawing`'s one-second feed with a publish in it. That overrun
# is charged to every bounded wait, and this is the cap a poll may have.
POLL_CEILING_S = 1.0

# What ONE engine of this harness may cost: a quickshell, its broker, and
# every wait the run spends around them. Per engine rather than per run for
# D50's reason — it is the claim that survives the next window somebody adds,
# and a run ceiling alone breaks on an honest addition instead of on a cost
# problem. The worst today is the heard-and-confirm window at 238 s, which is
# four `wait_for_drawing`s and two engine starts; the room above it is for
# about one more reading, and a window that wants two is a conversation.
STRETCH_CEILING_S = 300.0

# And what the whole pass can cost if every one of them goes pathological:
# thirteen engines, six of them the shot loop, 1714 s — 28.6 minutes against a
# measured 3m20s. (Twelve and 1593 s before D68's granted-width probe, which
# is one more engine and 121 s of it: two process starts, a bounded wait for
# the narrow output to draw, and two stops.) So this is a bound on the run that never happens and not a
# budget for the one that does. Where it goes is the answer D58 was opened
# for: 43% is `READY_TIMEOUT_S`, twenty-two waits of 30 s for a process to
# say one line, and D53 measured that a warm engine here says it in 0.40 s.
# Another 26% is `STOP_TIMEOUT_S`, spent twice per process over 26 stops.
# Those two are the shrink, and this is the number it will be measured
# against.
RUN_CEILING_S = 1800.0

# Every way this file waits, and what one occurrence of it costs the ceiling.
# The helpers are charged at their CALL SITES and their insides skipped, so
# `wait_for_blind_plate`'s own deadline is counted once per call rather than
# once per definition.
CHARGED_HELPERS = {
    "Proc.wait_for",
    "Proc.stop",
    "publish_shot",
    "feed_snapshots",
    "settle",
    "start_client",
    "wait_for_blind_plate",
    "wait_for_drawing",
}

# The three functions of `shoot.py` that spend waits of their own rather than
# lending them to a caller. Every wait site in them has to fall inside one of
# the stretches below.
WAITING_CALLERS = {
    "main",
    "probe_idle_frames",
    "probe_click_through",
    "probe_surface_granted",
}


def shoot_text() -> str:
    return SHOOT.read_text("utf-8")


def shoot_tree() -> ast.Module:
    return ast.parse(shoot_text())


def shoot_constants() -> dict[str, float]:
    """Every module-level number in `shoot.py`, read without importing it.

    Without importing because this suite has no numpy and `shoot.py` does —
    the same reason every other gate in this file reads the harness as text.
    """
    out: dict[str, float] = {}
    for node in shoot_tree().body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            value = ast.literal_eval(node.value)
        except ValueError:
            continue
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out[target.id] = float(value)
    return out


def _units(tree: ast.Module):
    """Every node of `shoot.py`, with its parent and the definition it is
    charged to. A nested function is charged to the one it lives in, so
    `publish_shot`'s async body belongs to `publish_shot` and a method to
    `Proc.<name>`."""
    parent: dict[ast.AST, ast.AST] = {}
    unit: dict[ast.AST, str] = {}

    def walk(node: ast.AST, own: str, cls: str) -> None:
        for child in ast.iter_child_nodes(node):
            parent[child] = node
            here, klass = own, cls
            if isinstance(child, ast.ClassDef):
                klass, here = child.name, ""
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and not own:
                here = f"{cls}.{child.name}" if cls else child.name
            unit[child] = here
            walk(child, here, klass)

    walk(tree, "", "")
    return parent, unit


def wait_sites() -> list[dict]:
    """Every place `shoot.py` waits, with what it waits on.

    A site is a sleep, a `time.monotonic()` deadline, or a call to one of the
    helpers above. `poll` marks the ones spent inside a bounded loop, which
    the ceiling gets for free; `unit` is the definition the site is charged
    to, which is how a helper's insides are kept from being counted twice.
    """
    tree = shoot_tree()
    parent, unit = _units(tree)

    def ancestors(node: ast.AST):
        out = []
        while node in parent:
            node = parent[node]
            out.append(node)
        return out

    sites: list[dict] = []
    for node in ast.walk(tree):
        kind = None
        if isinstance(node, ast.Call):
            called = ast.unparse(node.func)
            if called in ("time.sleep", "asyncio.sleep"):
                kind = "sleep"
            elif called.endswith(".wait_for"):
                kind = "wait_for"
            elif called.endswith(".stop"):
                kind = "stop"
            elif called == "self.p.wait":
                kind = "procwait"
            elif called in CHARGED_HELPERS:
                kind = called
        elif (
            isinstance(node, ast.BinOp)
            and isinstance(node.op, ast.Add)
            and isinstance(node.left, ast.Call)
            and ast.unparse(node.left) == "time.monotonic()"
        ):
            kind = "deadline"
        if kind is None:
            continue
        sites.append(
            {
                "kind": kind,
                "node": node,
                "line": node.lineno,
                "unit": unit.get(node, ""),
                "poll": any(
                    isinstance(a, ast.While) and "time.monotonic" in ast.unparse(a.test)
                    for a in ancestors(node)
                ),
                "loops": [a for a in ancestors(node) if isinstance(a, ast.For)],
            }
        )
    return sites


def stretches() -> dict[str, tuple[int, int, str]]:
    """The engines, as line ranges of `shoot.py`: the body of the shot loop
    (entered once per shot in the sheet), the five idle windows, and the click
    probe. Sliced out of the source rather than listed, so a window renamed
    is a window still covered and a window ADDED is one the census below
    refuses to leave uncounted."""
    text = shoot_text()

    def line(idx: int) -> int:
        return text.count("\n", 0, idx) + 1

    idle = text.index("def probe_idle_frames"), text.index("def probe_click_through")
    marks = [
        idle[0] + m.start()
        for m in re.finditer(r"^    # --- ", text[idle[0] : idle[1]], re.M)
    ]
    out: dict[str, tuple[int, int, str]] = {}
    for i, start in enumerate(marks):
        end = marks[i + 1] if i + 1 < len(marks) else idle[1]
        title = re.match(r"    # --- ([A-Z][A-Z ]+)", text[start:]).group(1).strip()
        out[title.lower()] = (line(start), line(end), text[start:end])
    # These two off the AST rather than off the text, because their ends
    # matter: a wait written just after the shot loop and just before the
    # next phase is a wait spent ONCE, and a stretch that ran to the next
    # landmark would charge it to all six shots and call that a ceiling.
    tree = shoot_tree()
    lines = text.splitlines(keepends=True)

    def span(node) -> tuple[int, int, str]:
        return node.lineno, node.end_lineno + 1, "".join(
            lines[node.lineno - 1 : node.end_lineno]
        )

    out["shot"] = span(
        next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.For) and ast.unparse(n.iter) == "sheet.SHOTS"
        )
    )
    for fn, engine in (
        ("probe_click_through", "click"),
        ("probe_surface_granted", "granted"),
    ):
        out[engine] = span(
            next(
                n
                for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == fn
            )
        )
    return out


def publish_charge() -> float:
    """What one `publish_shot` can hold the run for: the broker's drain, once
    per frame, for the widest thing this harness publishes at once."""
    consts = shoot_constants()
    widest = max(len(s["frames"]) + len(s.get("hold", [])) for s in sheet.SHOTS)
    return consts["PUBLISH_DRAIN_S"] * widest


def site_charge(site: dict) -> float:
    """What one occurrence of a site costs the ceiling.

    Every bounded wait carries the overrun above: the loop tests its deadline
    at the top, so the last pass through the body begins inside the bound and
    ends outside it.
    """
    consts = shoot_constants()
    publish = publish_charge()
    overrun = POLL_CEILING_S + publish
    node = site["node"]

    def named(expr: ast.AST) -> float:
        """The bound, which must be a constant `shoot.py` declares by name."""
        assert isinstance(expr, ast.Name) and expr.id in consts, (
            f"{SHOOT.name}:{site['line']} waits on {ast.unparse(expr)}, which "
            "is not a module constant of that file — a bound nobody named is "
            "a bound this ceiling cannot add up (PLAN D58)"
        )
        return consts[expr.id]

    kind = site["kind"]
    if kind == "sleep":
        return named(node.args[0])
    if kind == "deadline":
        return named(node.right) + overrun
    if kind == "wait_for":
        explicit = [kw.value for kw in node.keywords if kw.arg == "timeout"]
        bound = named(explicit[0]) if explicit else consts["READY_TIMEOUT_S"]
        return bound + overrun
    if kind in ("wait_for_blind_plate", "wait_for_drawing"):
        return consts["BLIND_TIMEOUT_S"] + overrun
    if kind == "start_client":
        return consts["CLIENT_WINDOW_TIMEOUT_S"] + overrun
    if kind == "stop":
        # Terminate, wait, kill, wait: the timeout is spent twice.
        return 2 * consts["STOP_TIMEOUT_S"]
    if kind == "settle":
        # It either sleeps its seconds or feeds them; the feed publishes.
        return named(node.args[0]) + publish
    if kind == "feed_snapshots":
        return named(node.args[0]) + overrun
    if kind == "publish_shot":
        return publish
    raise AssertionError(f"no charge for a {kind} site")


def loop_factor(site: dict, source: str) -> int:
    """How many times a stretch enters a site. Every loop around a wait has to
    be one this file knows how to count — an unknown one is refused rather
    than treated as one pass, because a wait inside a loop nobody counted is
    the same hole as a wait nobody counted at all."""
    times = 1
    for loop in site["loops"]:
        over = ast.unparse(loop.iter)
        if isinstance(loop.iter, (ast.Tuple, ast.List)):
            times *= len(loop.iter.elts)
        elif over == "sheet.SHOTS":
            times *= 1  # the stretch IS one shot; the run multiplies below
        elif over == "shot['captures']":
            times *= max(len(s["captures"]) for s in sheet.SHOTS)
        elif over == "clients":
            times *= source.count("start_client(")
        else:
            raise AssertionError(
                f"{SHOOT.name}:{site['line']} waits inside `for … in {over}`, "
                "which the ceiling does not know how to count (PLAN D58)"
            )
    return times


def stretch_ceilings() -> dict[str, float]:
    """The worst case of every wait each engine of this harness can spend."""
    spans = stretches()
    out = {name: 0.0 for name in spans}
    for site in wait_sites():
        if site["poll"] or site["unit"] in CHARGED_HELPERS:
            continue
        where = [n for n, (lo, hi, _) in spans.items() if lo <= site["line"] < hi]
        assert len(where) == 1, (
            f"{SHOOT.name}:{site['line']} is a {site['kind']} in "
            f"{site['unit']!r} that belongs to {len(where)} engines — a wait "
            "outside every stretch is a wait outside this ceiling (PLAN D58)"
        )
        name = where[0]
        out[name] += site_charge(site) * loop_factor(site, spans[name][2])
    return out


def run_ceiling() -> float:
    """And the whole pass: the shot stretch once per shot in the sheet, every
    other engine once."""
    ceilings = stretch_ceilings()
    shots = len(sheet.SHOTS)
    return ceilings["shot"] * shots + sum(
        v for name, v in ceilings.items() if name != "shot"
    )


def test_no_engine_of_this_harness_can_hang_for_an_afternoon():
    """The claim D58 opened for, and it is about the run that never happens:
    a quickshell that comes up and holds still, a broker that binds nothing, a
    plate that never arrives. Every one of those is a poll with a generous
    timeout, and this is the arithmetic that says what they add up to."""
    ceilings = stretch_ceilings()
    for engine, worst in sorted(ceilings.items()):
        assert worst <= STRETCH_CEILING_S, (engine, worst)
    assert run_ceiling() <= RUN_CEILING_S, ceilings
    # Thirteen engines — six shots and seven probes — so the run bound is not
    # the sum of thirteen stretch bounds. It is asserted below the product for
    # the reason `shellload.sh`'s is: a reader who saw only the per-engine
    # number would be reading a thirteenth of the true worst case.
    engines = len(sheet.SHOTS) + len(ceilings) - 1
    assert RUN_CEILING_S <= STRETCH_CEILING_S * engines
    # And the ceiling is a ceiling rather than a budget: the measured pass is
    # three minutes, and a bound that had drifted down to it would fail the
    # first slow machine this ever runs on.
    assert run_ceiling() >= 4 * 180.0


def test_every_way_this_harness_waits_is_one_the_ceiling_knows_about():
    """The half of a ceiling that drifts silently, and the only reason this
    one is derived instead of written down.

    A wait is one line. `hudscreens.sh` has about ninety of them across twelve
    engines, and D50's bug in the smaller gate was exactly a wait the driver
    spent and the arithmetic did not know about. So the question is not
    whether the sum is right today: it is whether a function that waits can
    exist in that file without this test naming it."""
    tree = shoot_tree()
    _, unit = _units(tree)
    primitive = {s["unit"] for s in wait_sites()}
    # A definition that waits because it calls something that waits, to a
    # fixed point: a helper three calls deep from a sleep is still a helper
    # whose call sites cost seconds.
    methods = {
        f"{cls.name}.{fn.name}"
        for cls in tree.body
        if isinstance(cls, ast.ClassDef)
        for fn in cls.body
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    calls: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        called = ast.unparse(node.func)
        if "." in called:
            tail = called.rsplit(".", 1)[1]
            named = {m for m in methods if m.endswith(f".{tail}")}
        else:
            named = {called}
        calls.setdefault(unit.get(node, ""), set()).update(named)
    waiting = set(primitive)
    while True:
        grown = {
            who
            for who, called in calls.items()
            if who and (called & waiting)
        } | waiting
        if grown == waiting:
            break
        waiting = grown
    waiting.discard("")
    assert waiting == CHARGED_HELPERS | WAITING_CALLERS, (
        "these functions of shoot.py wait and the ceiling does not charge "
        f"them: {sorted(waiting - (CHARGED_HELPERS | WAITING_CALLERS))}; and "
        "these are charged and no longer wait: "
        f"{sorted((CHARGED_HELPERS | WAITING_CALLERS) - waiting)}"
    )


def arguments_of_each_definition() -> dict[str, set[str]]:
    """The parameter names of every definition in `shoot.py`, by the unit it
    is charged to. A wait on an argument is a wait whose bound the CALLER
    named, which is the shape every charged helper here has."""
    tree = shoot_tree()
    _, unit = _units(tree)
    out: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            names = {
                a.arg for a in [*args.posonlyargs, *args.args, *args.kwonlyargs]
            }
            out.setdefault(unit.get(node, ""), set()).update(names)
    return out


def test_every_bound_in_this_harness_is_a_named_number():
    """`start_client` waited 15 s on a bare literal and `Proc.stop` spent 8 s
    twice on another, which is how a harness ends up with no ceiling: there
    was nothing to add up. Every deadline and every settle is a constant at
    the top of the file now, and `site_charge` refuses one that is not.

    A POLL is the exception, and it is the only one: it is spent inside a
    bound that was already named, so the literal is a cadence rather than a
    ceiling — capped here so it stays one."""
    consts = shoot_constants()
    params = arguments_of_each_definition()
    for site in wait_sites():
        node = site["node"]
        if site["poll"]:
            numbers = [
                n.value
                for n in ast.walk(node)
                if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
            ]
            assert all(n <= POLL_CEILING_S for n in numbers), (site["line"], numbers)
            continue
        if site["kind"] == "deadline":
            bound = node.right
        elif site["kind"] == "sleep":
            bound = node.args[0]
        elif site["kind"] == "procwait":
            assert [kw.arg for kw in node.keywords] == ["timeout"], ast.unparse(node)
            bound = node.keywords[0].value
        else:
            continue  # a call site: its bound is the helper's, checked below
        # A name, and one of two kinds of name: a constant at the top of the
        # file, or an argument — which is a bound the CALLER named, and every
        # caller is charged for it above.
        assert isinstance(bound, ast.Name), (
            f"{SHOOT.name}:{site['line']} waits {ast.unparse(bound)}, which is "
            "a number nobody named — the ceiling cannot add up a literal "
            "(PLAN D58)"
        )
        assert bound.id in consts or bound.id in params[site["unit"]], (
            f"{SHOOT.name}:{site['line']} waits on {bound.id}, which is "
            f"neither a constant of {SHOOT.name} nor an argument of "
            f"{site['unit']}"
        )


def test_the_helpers_wait_on_the_bound_the_ceiling_charges_for_them():
    """The table above says `wait_for_blind_plate` costs `BLIND_TIMEOUT_S`.
    Nothing but this test says it is true — the helper could be changed to
    wait on something else entirely and every sum here would go on reading
    the old number, which is the failure mode of every arithmetic written
    beside the thing it measures rather than off it."""
    tree = shoot_tree()
    _, unit = _units(tree)
    deadlines: dict[str, list[str]] = {}
    for site in wait_sites():
        if site["kind"] == "deadline":
            deadlines.setdefault(site["unit"], []).append(
                ast.unparse(site["node"].right)
            )
    assert deadlines["wait_for_blind_plate"] == ["BLIND_TIMEOUT_S"]
    assert deadlines["wait_for_drawing"] == ["BLIND_TIMEOUT_S"]
    assert deadlines["start_client"] == ["CLIENT_WINDOW_TIMEOUT_S"]
    # `Proc.wait_for` waits on its argument, so what the ceiling charges is
    # the DEFAULT — and every call site in this harness takes it.
    assert deadlines["Proc.wait_for"] == ["timeout"]
    waiter = next(
        fn
        for cls in tree.body
        if isinstance(cls, ast.ClassDef)
        for fn in cls.body
        if isinstance(fn, ast.FunctionDef) and fn.name == "wait_for"
    )
    assert ast.unparse(waiter.args.defaults[-1]) == "READY_TIMEOUT_S"
    assert not [
        s for s in wait_sites() if s["kind"] == "wait_for" and s["node"].keywords
    ], "a call site passes its own timeout; the ceiling charges the default"
    # `settle` and `feed_snapshots` are charged their first argument, which
    # only holds while that argument is the number of seconds they wait.
    for name in ("settle", "feed_snapshots"):
        fn = next(
            f
            for f in tree.body
            if isinstance(f, ast.FunctionDef) and f.name == name
        )
        assert fn.args.args[0].arg == "seconds", name


def test_the_ceiling_has_one_engine_for_every_shell_this_harness_starts():
    """The stretches are sliced out of the source, and the one way that can
    go quietly wrong is a SIXTH idle window written without the `# ---`
    marker: its waits would land inside the window above it and be counted
    once against a bound they no longer describe. So the count is pinned to
    the thing a window cannot be written without — its own quickshell."""
    spans = stretches()
    for name, (_, _, source) in spans.items():
        shells = source.count('"jv-hud",')
        assert shells == 1, (
            f"the {name} engine starts {shells} quickshells — an engine is "
            "one shell, and a stretch holding two is a window whose waits "
            "are charged to its neighbour (PLAN D58)"
        )
    started = shoot_text().count('"jv-hud",')
    assert started == len(spans), (
        f"{started} quickshells are started and the ceiling has {len(spans)} "
        f"engines: {sorted(spans)}"
    )


# ------------------- the output that is not a monitor, and what it is for (D68)
#
# D66 taught the HUD that a 300 px corner does not fit on every screen —
# `plateRoomPx` is `min(surface.width, screen.width) - 2 x insetPx`, and the
# plates are capped by it. Every word of that was measured in a QML engine,
# against a plain `Item` whose `width` a test assigns, and the sentence it
# rests on is about a COMPOSITOR: a layer-shell surface anchored to one edge
# is granted the width it asks for whether or not the output is that wide.
# This harness is the only place in the repo that can ask a compositor
# anything, and until D68 it had three outputs, all of them wider than the
# surface, so the question was never put.
#
# These gates hold the two halves of putting it: that the narrow output is
# still narrow (and still outside the desk, so the nine older pictures are
# untouched by it), and that the instrument which reads the answer is reading
# the compositor's event rather than the client's request.


def test_the_narrow_output_is_narrower_than_the_surface_it_asks_about():
    """It has exactly one job. An output that grew past 300 px would leave
    every check in `shoot.py` green with nothing anywhere asking what the HUD
    does when the screen is smaller than the corner — and the picture would
    still be committed, under a caption saying it was."""
    assert sheet.NARROW["width"] == sheet.NARROW_W
    assert sheet.NARROW_W < sheet.SURFACE_W, (
        f"the narrow output is {sheet.NARROW_W}px and the surface asks for "
        f"{sheet.SURFACE_W}px — it is not narrow, so it asks nothing"
    )
    # And wide enough to still be a corner: the plates are capped at the room
    # the output leaves after both insets, and a photograph of nothing at all
    # answers the question no better than a wide screen does.
    assert sheet.NARROW_W - 2 * sheet.INSET > 0, (
        "the narrow output leaves no room between the insets, so the HUD has "
        "nowhere to draw and the shot is of an empty screen"
    )


def test_the_narrow_output_is_not_one_of_ares_monitors():
    """The desk is `OUTPUTS` and ares is the desk. The narrow output is an
    instrument, and the moment it joins that list `DESK_WIDTH` moves — which
    re-photographs nine committed screens to answer a question about a tenth,
    and makes `check_desk_is_bare` a claim about a machine nobody owns.
    """
    assert sheet.NARROW not in sheet.OUTPUTS
    assert sheet.ALL_OUTPUTS == [*sheet.OUTPUTS, sheet.NARROW]
    assert sheet.NARROW["x"] >= sheet.DESK_WIDTH, (
        f"the narrow output starts at x={sheet.NARROW['x']} and the desk is "
        f"{sheet.DESK_WIDTH}px wide — it is inside the desk capture, so every "
        "desk shot in this sheet is now a picture of four screens"
    )
    roles = [o["role"] for o in sheet.ALL_OUTPUTS]
    assert len(roles) == len(set(roles)), f"two outputs share a role: {roles}"


def test_the_compositor_is_given_the_narrow_output_too():
    """The config and the backend have to agree with each other, and neither
    is written where the other can see it: `sway_config()` names the outputs
    and `WLR_HEADLESS_OUTPUTS` says how many the backend makes. A config
    naming four against a backend making three leaves the fourth unconfigured
    at whatever size wlroots defaults to — which is a real screen, drawn on,
    and not the one this asks about."""
    line = (
        f"output {sheet.NARROW['name']} mode "
        f"{sheet.NARROW['width']}x{sheet.NARROW['height']} "
        f"pos {sheet.NARROW['x']} 0"
    )
    assert line in sheet.sway_config(), f"the compositor is never told about {line!r}"
    assert "len(sheet.ALL_OUTPUTS)" in driver_text(), (
        "ops/ralph/hudscreens.sh writes its own WLR_HEADLESS_OUTPUTS instead "
        "of asking the sheet how many outputs there are"
    )
    assert not re.search(r"^export WLR_HEADLESS_OUTPUTS=\d", driver_text(), re.M), (
        "ops/ralph/hudscreens.sh still has a literal output count in it"
    )


# ---------------------- the quiet half of the narrow output (D70)
#
# D68 photographed the 280 px screen LIT. The other half of invariant 10 is
# that a HUD with nothing to say leaves the screen pixel-identical to the bare
# desktop, and that claim is made by `check_desk_is_bare` — which walked
# `sheet.OUTPUTS` over one wide `grim` of the DESK, and the narrow output is
# deliberately outside the desk. So a surface that mapped on that screen while
# it had nothing to say was caught by nothing at all: the quiet shot
# photographs the desk alone, and the lit shots' corner check only bounds the
# box that WAS drawn.
#
# These two gates are the shape of closing it. The first is the coverage
# arithmetic — which outputs that function's exposures actually reach — and it
# is written as a derivation off the sheet rather than as "there are two
# captures", so an output added to `ALL_OUTPUTS` and to nothing else goes red
# here. The second is the reason the fix is not just one more grim: the
# sentence it proves is "nothing is drawn", and numpy hands that same sentence
# to a caller whose capture came back too small.


def units_of(name: str) -> list[ast.AST]:
    """Every node of `shoot.py` charged to one definition."""
    _, unit = _units(shoot_tree())
    return [node for node, own in unit.items() if own == name]


def calls_in(name: str, called: str) -> list[ast.Call]:
    return [
        node
        for node in units_of(name)
        if isinstance(node, ast.Call) and ast.unparse(node.func) == called
    ]


def test_earned_emptiness_is_measured_on_every_output_the_compositor_has():
    """The claim is invariant 10's, and it is about the SCREEN — every screen
    there is, not every screen ares has. `check_desk_is_bare` is the only
    place in this repo that makes it, so which outputs its exposures reach is
    the whole scope of the claim, and it is derived here off `ALL_OUTPUTS`:
    a fifth output declared and photographed by nobody goes red on this line
    rather than passing quietly forever."""
    targets = [ast.literal_eval(c.args[0]) for c in calls_in("check_desk_is_bare", "capture")]
    assert targets, "check_desk_is_bare photographs nothing"
    covered = set()
    for target in targets:
        if target == "desk":
            covered |= {o["role"] for o in sheet.OUTPUTS}
        else:
            covered.add(target)
    missing = {o["role"] for o in sheet.ALL_OUTPUTS} - covered
    assert not missing, (
        f"check_desk_is_bare captures {targets} and so never looks at "
        f"{sorted(missing)} — a surface that mapped on that output with "
        "nothing to say would be caught by nothing: the quiet shot is of the "
        "desk, and a lit shot's corner check only bounds what was drawn"
    )
    # And every exposure it pays for is READ. A grim whose image nothing
    # passes to `drawn_box` is a picture taken to prove a sentence nobody
    # said.
    reads = calls_in("check_desk_is_bare", "drawn_box")
    assert len(reads) == len(targets), (
        f"check_desk_is_bare takes {len(targets)} exposures and reads "
        f"{len(reads)} of them"
    )


def test_a_capture_that_is_not_the_screen_is_refused():
    """`sheet.capture_size_complaint`, exercised on the sizes that would make
    the gate above vacuous. It lives in the sheet so that a test with no
    compositor — and no numpy — can run the rule itself rather than assert
    that some source line mentions it.

    The failure it exists for: every check downstream reads pixels with
    `img[0:h, x:x+w]` or reads the whole array, numpy slicing past the end of
    an array returns a SMALLER array rather than raising, `drawn_box` of an
    empty region is None, and None is spelt "the HUD drew nothing here".
    """
    narrow = sheet.output_by_role("narrow")
    assert sheet.capture_size_complaint("x", (narrow["width"], narrow["height"]), narrow) is None
    assert sheet.capture_size_complaint("x", (sheet.DESK_WIDTH, sheet.DESK_HEIGHT), sheet.DESK) is None

    # A grim that came back with the desk when the narrow output was asked
    # for, and one that came back with a monitor missing off the right of the
    # desk. Both are the wrong screen and both would read as bare.
    wrong = sheet.capture_size_complaint("narrow", (sheet.DESK_WIDTH, sheet.DESK_HEIGHT), narrow)
    assert wrong and narrow["name"] in wrong and f"{narrow['width']}x{narrow['height']}" in wrong
    short = sheet.capture_size_complaint(
        "desk", (sheet.DESK_WIDTH - sheet.OUTPUTS[-1]["width"], sheet.DESK_HEIGHT), sheet.DESK
    )
    assert short, "the desk minus a monitor is accepted as the desk"

    # Transposed and one-pixel: the two shapes a broken capture path actually
    # produces. Transposed matters on its own — the narrow output is the one
    # screen here whose two dimensions could be swapped without the numbers
    # looking wrong.
    assert sheet.capture_size_complaint("x", (narrow["height"], narrow["width"]), narrow)
    assert sheet.capture_size_complaint("x", (1, 1), narrow)

    assert sheet.DESK not in sheet.ALL_OUTPUTS, (
        "the desk has joined the outputs — it is an IMAGE, not a screen, and "
        "the compositor config and the output census both walk that list"
    )


# ------------ the dark verdict on the screen outside the picture (D72)
#
# The gate above is about the desktop with NO HUD on it. This one is about the
# SHOTS, and the hole is the same shape: a desk capture is `sheet.OUTPUTS` in
# one wide grim, the narrow output sits to the right of the desk on purpose,
# and `01-quiet` captures the desk and nothing else.
#
# `01-quiet` is a different dark from D70's. There, no frames arrive at all
# and the surfaces are never mapped. Here frames DO arrive and every plate
# decides it has nothing true to show — which is the case where a plate
# drawing a zero-height sliver or an empty rectangle of glass is a bug, and
# the 280 px output is where such a thing is most likely (its 248 px of room
# is under `ConfirmPlate`'s own cap) and least visible. `check_corner(lit=
# False)` is the other place in shoot.py where "nothing drawn" is the pass,
# and it had never run on that screen.
#
# Both halves below are derived off the sheet rather than asserted as shapes,
# so a fifth output declared and photographed by nobody goes red here.


def test_a_desk_capture_is_a_verdict_about_every_output_there_is():
    """Which screens one desk exposure's verdict reaches — all of them, not
    just the desk's. A shot's `captures` is the list of PICTURES it writes,
    and the sheet has a shot that writes one, so the pictures cannot also be
    the census of screens the shot is a claim about."""
    covered = set()
    for node in units_of("check_capture"):
        # The desk image, sliced one monitor at a time.
        if isinstance(node, ast.For) and ast.unparse(node.iter) == "sheet.OUTPUTS":
            covered |= {o["role"] for o in sheet.OUTPUTS}
    # And every screen it takes an exposure of its own for.
    for call in calls_in("check_capture", "capture"):
        covered.add(ast.literal_eval(call.args[0]))
    missing = {o["role"] for o in sheet.ALL_OUTPUTS} - covered
    assert not missing, (
        f"a desk capture is checked on {sorted(covered)} and so says nothing "
        f"about {sorted(missing)} — `01-quiet` captures the desk alone, so on "
        "that screen a plate that lit up with nothing to say would be caught "
        "by nothing at all"
    )

    # Every image it turns into a verdict is one size check and one corner
    # verdict. The odd one out is either an exposure nobody read — a grim paid
    # for to prove a sentence nobody said — or a read nobody sized, which is
    # the vacuous pass D70 refuses.
    sized = calls_in("check_capture", "check_grim_size")
    verdicts = calls_in("check_capture", "check_corner")
    assert len(sized) == len(verdicts), (
        f"check_capture checks {len(sized)} image size(s) and takes "
        f"{len(verdicts)} corner verdict(s)"
    )
    # And every one of them is asked the SHOT's question. A narrow exposure
    # hard-wired to `lit=True` would pass `01-quiet` with a plate on it, and
    # one hard-wired to False would fail `02-heard` — the dark half is the
    # whole reason this exposure exists.
    for call in verdicts:
        lit = ast.unparse(call.args[-1])
        assert lit == "shot['lit']", (
            f"check_capture line {call.lineno} decides for itself whether the "
            f"HUD should be drawn ({lit}) rather than asking the shot"
        )


def test_the_two_whole_image_verdicts_size_check_before_they_read():
    """`check_capture` and `check_desk_is_bare` are the two places that turn a
    whole image into a verdict, and a size check that runs AFTER the pixels
    are read is not a check. The ordering is the assertion; the rule itself is
    graded above."""
    for name in ("check_capture", "check_desk_is_bare"):
        sized = calls_in(name, "check_grim_size")
        assert sized, f"{name} reads an image it never checked the size of"
        readers = [
            c
            for c in units_of(name)
            if isinstance(c, ast.Call) and ast.unparse(c.func) in ("drawn_box", "check_corner")
        ]
        assert readers, f"{name} checks a size and then reads nothing"
        # One size check per read, in that order — not `the first check comes
        # before the first read` (PLAN D72). Both of these functions now take
        # a SECOND exposure of their own: `check_desk_is_bare` photographs the
        # narrow output after walking the desk, and `check_capture`'s desk
        # branch does the same. Under a min-against-min rule the second
        # image's size check is optional, because the first one already sits
        # above every read in the function — which is precisely the vacuous
        # read D70 exists to refuse, arriving by a new door.
        #
        # So: walk the two kinds of site in source order and insist a read is
        # never reached with fewer size checks behind it than reads. A second
        # grim whose size nobody asked about goes red here, and so does one
        # checked a line too late.
        seen_sized = seen_read = 0
        for lineno, is_read in sorted(
            [(c.lineno, False) for c in sized] + [(c.lineno, True) for c in readers]
        ):
            if is_read:
                assert seen_sized > seen_read, (
                    f"{name} reads pixels at line {lineno} behind "
                    f"{seen_sized} size check(s) and {seen_read} earlier "
                    "read(s) — one of the images it turns into a verdict was "
                    "never checked to be the screen it was asked for, and a "
                    "capture that came back too small reads as 'the HUD drew "
                    "nothing here'"
                )
                seen_read += 1
            else:
                seen_sized += 1
    assert "img.shape[:2] !=" not in shoot_text(), (
        "shoot.py has a hand-rolled capture-size comparison again — the rule "
        "is sheet.capture_size_complaint, which is the copy a test can run"
    )


# Verbatim from a real run of this harness: the four layer surfaces of one
# jv-hud being configured, on a compositor with ares' three monitors and the
# 280 px output. Kept as text for the reason the frame counter's sample is —
# it is the thing the reader has to survive, and a hand-idealised line would
# not be.
GRANTED_LOG = """\
[3395049.239] {Default Queue} zwlr_layer_surface_v1#22.configure(1, 300, 826)
[3395049.301] {Default Queue} zwlr_layer_surface_v1#31.configure(2, 300, 826)
[3395049.354] {Default Queue} zwlr_layer_surface_v1#38.configure(3, 300, 826)
[3395049.402] {Default Queue} zwlr_layer_surface_v1#45.configure(4, 300, 826)
"""


def test_the_configure_reader_reads_a_real_wayland_log():
    """The instrument D68 rests on. It is a regex over a debug log, which is
    not a stable interface — and the way it fails is silent: a pattern that
    stopped matching returns an empty dict, and "no surface was configured
    wrongly" is true of one of those."""
    sizes = sheet.layer_surface_sizes(GRANTED_LOG)
    assert sizes == {22: (300, 826), 31: (300, 826), 38: (300, 826), 45: (300, 826)}
    # Both separators, for COMMIT_RE's reason: libwayland has printed the
    # object id as `@` and the build under this harness prints `#`.
    assert sheet.layer_surface_sizes(
        "[1.0] zwlr_layer_surface_v1@7.configure(1, 300, 826)"
    ) == {7: (300, 826)}
    # The LAST configure per surface, because a surface is reconfigured
    # whenever anything about it changes and what the probe asks about is the
    # size it settled at.
    assert sheet.layer_surface_sizes(
        "[1.0] zwlr_layer_surface_v1@7.configure(1, 300, 826)\n"
        "[2.0] zwlr_layer_surface_v1@7.configure(2, 280, 826)\n"
    ) == {7: (280, 826)}


def test_the_configure_reader_reads_the_answer_and_not_the_question():
    """The whole point is the difference between what the client asked for
    and what the compositor gave it. A reader that counted `set_size` would
    report `300x826` on every output forever — the HUD's own request, read
    back as if it were the compositor agreeing to it, which is exactly the
    assumption D68 exists to stop making."""
    asked = (
        "[1.0]  -> zwlr_layer_surface_v1@7.set_size(300, 826)\n"
        "[1.1]  -> zwlr_layer_surface_v1@7.ack_configure(1)\n"
        "[1.2]  -> zwlr_layer_shell_v1@6.get_layer_surface("
        "new id zwlr_layer_surface_v1@7, wl_surface@5, wl_output@4, 2, \"jv-hud\")\n"
    )
    assert sheet.layer_surface_sizes(asked) == {}
    # And nothing else on the socket. The idle probe's traffic is the busiest
    # thing in these logs and none of it is a layer-surface configure.
    assert sheet.layer_surface_sizes(REAL_WAYLAND_LOG) == {}


def test_the_granted_probe_actually_runs():
    """A probe nobody calls measures nothing, and this one has no picture to
    be missing: the sheet would be complete and the question unasked."""
    body = shoot_text().split("\ndef main(")[-1]
    assert "probe_surface_granted(stage, background)" in body, (
        "tools/hudscreens/shoot.py never calls probe_surface_granted, so "
        "nothing in a run of this harness reads what width the compositor "
        "granted (PLAN D68)"
    )


def test_the_granted_probe_counts_one_surface_per_output():
    """The control. Every way of breaking this probe — a regex that stopped
    matching, a shell that mapped nothing, a log nobody wrote — comes back as
    an empty dict, and an empty dict has no surface configured at the wrong
    size in it. So the census is the measurement: one layer surface per
    output, or the probe says so and stops."""
    probe = shoot_text().split("\ndef probe_surface_granted(")[-1].split("\ndef ")[0]
    assert "len(sizes) != len(sheet.ALL_OUTPUTS)" in probe, (
        "the granted-width probe no longer insists on one configured surface "
        "per output, so it passes on a log it never read"
    )
    assert "sheet.layer_surface_sizes(" in probe


def test_the_narrow_output_is_photographed():
    """D68 is two claims and the probe above is one of them. The other is a
    picture: what the corner LOOKS like when the screen is narrower than it
    is, which no measurement substitutes for and which this sheet exists to
    provide."""
    shots = [s for s in sheet.SHOTS if "narrow" in s["captures"]]
    assert shots, (
        "no shot photographs the narrow output — the HUD on a screen smaller "
        "than its own surface is measured and still never seen (PLAN D68)"
    )
    for shot in shots:
        assert shot["lit"], (
            f"{shot['file']} photographs the narrow output dark, which is a "
            "picture of a bare desktop and says nothing about the corner"
        )
