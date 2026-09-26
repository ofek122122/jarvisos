"""Photograph the REAL HUD on a real compositor, and measure what it drew.

Driven by `ops/ralph/hudscreens.sh`, which is what puts a wlroots
compositor with ares' three monitors — and, since D68, one output narrower
than the HUD's own surface — underneath it (PLAN A30). This half
does the rest: for each shot in `sheet.py` it starts a real jarvisd, runs
the real `jv-hud` — quickshell, layer-shell, its own read-only bridge —
publishes the shot's frames onto the bus, photographs every monitor with
`grim`, and CHECKS the pixels before writing them.

The checks are the reason this is worth having over A29's contact sheet.
A29 could only ever say "the plates draw this"; the compositor can be
asked things no QML engine knows:

  · the surface reserves NO space. sway reports each workspace's usable
    rect, and an exclusive zone shrinks it. Read `check_no_space_reserved`
    for what that does and does not prove today.
  · the surface takes NO focus. The seat's focused node is read before
    the HUD exists and again while it is drawing, and it must be the same
    node. `WlrKeyboardFocus.None` was also only ever read, never tried.
  · the HUD is on EVERY monitor, in the corner it claims. Each output's
    drawn region has to fall inside the 300x826 box shell.qml declares,
    inset from the top-right corner. An anchor that silently flipped, or
    a `Variants` that stopped making one surface per screen, would look
    completely fine in a photograph nobody measured.
  · earned emptiness is REAL emptiness. The quiet shot must come back
    pixel-identical to the bare desktop — not "looks dark", but every
    OUTPUT untouched, which is what an unmapped surface means. Every
    output and not every monitor: the narrow one is outside the desk
    capture, so it is looked at through a second exposure (D70).
  · a click over the HUD reaches the window UNDERNEATH it (A32). The
    empty input mask was the one invariant-10 claim left resting on a
    reading of shell.qml, because it cannot be measured without a second
    client to pass through to. `probe_click_through` puts one there.
  · the HUD renders NOTHING while nothing changes (A34). "0 fps when
    idle" was an argument about how Qt Quick works, and the thing that
    breaks it is one ordinary edit — a pulse, a counter, an animation
    left looping. `probe_idle_frames` counts commits on the HUD's own
    side of the Wayland socket over five windows — quiet, lit, lit on a
    bus that never stops talking (A42), the two plates a single
    re-published heartbeat can hold still (A43), and the two whose words
    come off a latch that is re-taken once a second (A48) — with a
    control for each.

Nothing here asserts a pixel COLOUR: a font ships a new version, Qt
changes its rasteriser, and a byte comparison fails in a way nobody can
read. Geometry and emptiness are stable; glyph shapes are not.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sheet  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "pylib"))
sys.path.insert(0, str(ROOT / "harness"))

# How long to give the shell after quickshell says it loaded, and after the
# frames are on the bus. Past §06's longest ease and well inside both
# windows a shot depends on — SpeechState's 30 s think window and the 15 s
# jv-act declares in the confirm frame — so the camera lands on a settled
# plate rather than inside a fade or after an expiry.
SETTLE_S = 1.6
READY_TIMEOUT_S = 30.0

# How long a process gets to go away politely before it is killed, and then
# to be reaped. Named rather than inlined because it is spent TWICE per
# process, once per shot and once per idle window, and the ceiling in
# tools/tests/test_hudscreens.py adds it up: every bound in this file is a
# constant up here so that arithmetic reads the run rather than a guess at it
# (PLAN D58).
STOP_TIMEOUT_S = 8.0

# The drain after a publish. The broker fans out from its own task, so the
# socket is held open this long per frame — see `publish_shot`.
PUBLISH_DRAIN_S = 0.1


def log(msg: str) -> None:
    print(f"hudscreens: {msg}", flush=True)


class Fail(Exception):
    pass


# ---------------------------------------------------------------- compositor


def swaymsg(*args: str):
    out = subprocess.run(
        [os.environ["SWAYMSG_BIN"], "-r", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return json.loads(out)


def seat_focus():
    """The node the seat's keyboard is on. Read before the HUD exists and
    again while it draws: a layer surface that took the keyboard would
    move it, and the user would find out by having a keystroke eaten
    mid-sentence."""
    return [(s["name"], s["focus"]) for s in swaymsg("-t", "get_seats")]


def focused_node() -> int:
    """The id of the node the seat's keyboard is on — one number rather
    than `seat_focus`'s list, because the click probe compares it against
    a specific window it started."""
    seats = swaymsg("-t", "get_seats")
    if len(seats) != 1:
        raise Fail(f"expected exactly one seat, got {[s['name'] for s in seats]}")
    return seats[0]["focus"]


def toplevels() -> list:
    """Every ordinary window sway is managing. Layer surfaces — the HUD,
    the backdrop — are NOT in here, which is the point: this is the list
    of things a click can be passed through to."""
    found: list = []

    def walk(node) -> None:
        if node.get("app_id"):
            found.append(node)
        for key in ("nodes", "floating_nodes"):
            for child in node.get(key, []):
                walk(child)

    walk(swaymsg("-t", "get_tree"))
    return found


def usable_rects():
    """Each workspace's rect, keyed by output. sway shrinks this by every
    layer surface's exclusive zone, so comparing it against the output's
    own size is a direct measurement of `ExclusionMode.Ignore`."""
    return {w["output"]: w["rect"] for w in swaymsg("-t", "get_workspaces")}


def check_the_outputs_are_the_ones_the_sheet_declares() -> None:
    """Every output, which since D68 is not every monitor: ares' three plus
    the 280 px one that exists to ask what the HUD does on a screen narrower
    than its own surface. Exact equality in both directions — a fourth output
    the compositor invented, or a narrow one it never made, would leave the
    checks below measuring a machine the sheet does not describe.
    """
    got = {
        o["name"]: (o["current_mode"]["width"], o["current_mode"]["height"], o["rect"]["x"])
        for o in swaymsg("-t", "get_outputs")
    }
    want = {o["name"]: (o["width"], o["height"], o["x"]) for o in sheet.ALL_OUTPUTS}
    if got != want:
        raise Fail(f"compositor has outputs {got}, sheet declares {want}")


def check_no_space_reserved() -> None:
    """No window is resized or pushed around by the HUD (invariant 10).

    What this proves, and the limit is worth stating because it was found
    by trying rather than assumed: on TODAY'S surface it proves nothing.
    wlr-layer-shell only honours an exclusive zone for a surface anchored
    to one edge, or to an edge plus both perpendicular ones — and this one
    is anchored to a CORNER (top + right). Setting `exclusionMode` to
    Normal or to Auto changes the usable rect by zero pixels; both were
    built and photographed to check. What actually keeps the HUD out of
    everyone's way is the corner anchor, and `ExclusionMode.Ignore` is the
    belt to its braces.

    It is kept because the day those anchors change — a status strip along
    the top edge is the obvious future — the zone becomes real, and this
    is the line that notices. VERIFIED it bites: anchoring left+right+top
    with ExclusionMode.Auto took HEADLESS-1's usable area to 2560x880.
    """
    rects = usable_rects()
    # Every output, not every monitor (D68). The narrow one is where an
    # exclusive zone would do the most damage — 300 px of reserved corner on
    # a 280 px screen is the whole screen — so it is the last output this
    # check should skip.
    for out in sheet.ALL_OUTPUTS:
        r = rects.get(out["name"])
        if r is None:
            raise Fail(f"{out['name']} has no workspace at all")
        if (r["width"], r["height"]) != (out["width"], out["height"]):
            raise Fail(
                f"{out['name']}: usable area is {r['width']}x{r['height']} but the "
                f"monitor is {out['width']}x{out['height']} — the HUD reserved "
                "space, so exclusionMode is no longer Ignore (invariant 10)"
            )


# ------------------------------------------------------------------ processes


class Proc:
    def __init__(self, name: str, argv: list[str], logpath: Path, env: dict):
        self.name = name
        self.logpath = logpath
        self._fh = logpath.open("wb")
        self.p = subprocess.Popen(argv, stdout=self._fh, stderr=subprocess.STDOUT, env=env)

    def stop(self) -> None:
        if self.p.poll() is None:
            self.p.terminate()
            try:
                self.p.wait(timeout=STOP_TIMEOUT_S)
            except subprocess.TimeoutExpired:
                self.p.kill()
                self.p.wait(timeout=STOP_TIMEOUT_S)
        self._fh.close()

    def mark(self) -> int:
        """Where this process's log has got to. `since()` reads on from
        here, so a measurement can be taken over a stretch of a log that
        is still being written."""
        return self.logpath.stat().st_size

    def since(self, mark: int) -> str:
        """Everything the process logged after `mark`."""
        with self.logpath.open("rb") as fh:
            fh.seek(mark)
            return fh.read().decode("utf-8", "replace")

    def wait_for(self, needle: str, timeout: float = READY_TIMEOUT_S) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.p.poll() is not None:
                raise Fail(
                    f"{self.name} exited with {self.p.returncode} before saying "
                    f"{needle!r}:\n{self.logpath.read_text('utf-8', 'replace')[-2000:]}"
                )
            if needle in self.logpath.read_text("utf-8", "replace"):
                return
            time.sleep(0.2)
        raise Fail(
            f"{self.name} never said {needle!r} in {timeout:.0f}s:\n"
            f"{self.logpath.read_text('utf-8', 'replace')[-2000:]}"
        )


# ---------------------------------------------------------------------- bus


def publish_shot(shot: dict, bus_addr: str) -> None:
    """Put the shot's frames on the bus, as the services that would have
    sent them. Recordings go through harness/replay.py so they are the
    committed lines and nothing else; composed frames carry their own
    `src`, because every consumer in this HUD checks it."""
    import asyncio

    import replay as harness_replay
    from jarvis_bus import BusClient, mono_now

    async def go() -> None:
        for action in shot["frames"]:
            if "replay" in action:
                path = ROOT / "harness" / "fixtures" / "sessions" / f"{action['replay']}.jsonl"
                # --instant: the recording's own pacing is a property of the
                # room, and a photograph has no use for it. Every frame is
                # re-stamped to now, which is what a turn that just happened
                # looks like to a HUD reading ages off the envelope.
                sent = await harness_replay.replay(path, bus_addr, instant=True)
                log(f"  replayed {action['replay']}: {sent} frames")
                continue
            spec = action["publish"]
            bus = await BusClient.connect(bus_addr, src=spec["src"])
            await bus.publish_env(
                {
                    "topic": spec["topic"],
                    "ts": mono_now(),
                    "seq": 0,
                    "src": spec["src"],
                    "conf": float(spec.get("conf", 1.0)),
                    "v": 1,
                    "body": spec["body"],
                }
            )
            # The broker fans out from its own task; closing the socket the
            # instant after a write can drop the frame before it is read.
            await asyncio.sleep(PUBLISH_DRAIN_S)
            await bus.close()
            log(f"  published {spec['topic']} as {spec['src']}")

    asyncio.run(go())


def feed_snapshots(seconds: float, frames: list, bus_addr: str) -> int:
    """Publish `frames` at jv-context's own 1 Hz for `seconds`; return how
    many times.

    The idle probe's two live-bus windows both need this, for opposite
    reasons. The quiet one needs traffic the HUD has NOTHING to say about,
    to ask whether a frame arriving costs a frame drawn. The live-lit one
    (A42) needs traffic that keeps a plate TRUE: core/OutputState.qml
    believes a snapshot for three of jv-context's periods, so a window that
    published once and then waited would watch the plate expire — and an
    unmapped surface commits nothing, which is exactly the zero the probe
    was hoping to see.

    1 Hz because that is the rate schemas/context.system.json states for
    the topic. The cadence is the point: it is what a HUD on a running
    machine is actually subjected to, all day, forever.
    """
    sent = 0
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        publish_shot({"frames": frames}, bus_addr)
        sent += 1
        time.sleep(max(0.0, min(1.0, deadline - time.monotonic())))
    return sent


def settle(seconds: float, hold: list, bus_addr: str) -> None:
    """Let the HUD arrive at what its frames mean — and, for a shot whose
    subject is a LIVE reading, keep those frames true while it does.

    Most shots here are events. A wake word happened, jv-act asked a
    question: the plates they light stay lit for as long as their own
    state says, and a single publish followed by a sleep photographs
    exactly what the bus said. A shot that declares `hold` is the other
    kind. core/OutputState.qml is a reading of the PRESENT and believes a
    `context.system` snapshot for three of jv-context's periods; a
    heartbeat speaks for two of the `period_s` it declares. So the settle
    IS the feed, at the 1 Hz jv-context publishes at all day. Nothing
    else changes: a shot with no `hold` sleeps, exactly as before.

    What that is worth was measured and is smaller than it sounds:
    publishing 04-unheard's pair once and sleeping writes the same PNG
    today, byte for byte, because one exposure reaches grim about two
    seconds after the publish and the snapshot expires at three. The feed
    is what stops a sub-second margin from being the thing that makes the
    picture right — it survives a slower machine, a longer settle, and a
    second monitor, none of which anything here would notice. A42's
    live-lit window is the same margin at the far end: it published a
    heartbeat once, and `jv-voice lost` arrived under the plate it was
    holding still.
    """
    if hold:
        feed_snapshots(seconds, hold, bus_addr)
    else:
        time.sleep(seconds)


# --------------------------------------------------------------------- pixels


def read_ppm(path: Path) -> np.ndarray:
    """grim's raw output. PPM rather than PNG so the checks below read
    pixels without a decoder, and so the PNG this writes is one this file
    controls end to end."""
    data = path.read_bytes()
    if data[:2] != b"P6":
        raise Fail(f"{path}: not a P6 ppm")
    vals: list[int] = []
    i = 2
    while len(vals) < 3:
        while data[i : i + 1].isspace():
            i += 1
        if data[i : i + 1] == b"#":
            while data[i : i + 1] != b"\n":
                i += 1
            continue
        j = i
        while not data[j : j + 1].isspace():
            j += 1
        vals.append(int(data[i:j]))
        i = j
    i += 1
    w, h, _maxval = vals
    return np.frombuffer(data[i : i + w * h * 3], dtype=np.uint8).reshape(h, w, 3).copy()


def write_png(path: Path, arr: np.ndarray) -> None:
    import struct
    import zlib

    h, w, _ = arr.shape
    stride = w * 3
    raw = np.zeros((h, stride + 1), dtype=np.uint8)
    raw[:, 1:] = arr.reshape(h, stride)

    def chunk(tag: bytes, payload: bytes) -> bytes:
        body = tag + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw.tobytes(), 9))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def drawn_box(region: np.ndarray, background: np.ndarray):
    """Bounding box of everything in `region` that is not the desktop, or
    None if the HUD drew nothing there."""
    diff = (region != background).any(axis=2)
    ys, xs = np.nonzero(diff)
    if len(ys) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def drawn_bands(region: np.ndarray, background: np.ndarray):
    """`drawn_box`, once per PLATE, top to bottom.

    The stack puts `Theme.gapPx` of untouched desktop between its plates
    and every plate is a filled rectangle of glass, so the drawn rows come
    in contiguous runs and each run is one plate. `sheet.row_bands` does
    the cutting — it is the part a test with no compositor can run — and
    this measures how far left each band reaches.

    Why a band and not the box (PLAN A86): the box is the union, and a
    plate that stays put and says a LONGER word does not move it. That is
    not a worry, it is a photograph: `deaf -> lossy` was measured before
    this existed and the union was the same four numbers under both.
    """
    drawn = (region != background).any(axis=2)
    rows = np.nonzero(drawn.any(axis=1))[0]
    bands = []
    for top, bottom in sheet.row_bands(int(r) for r in rows):
        cols = np.nonzero(drawn[top : bottom + 1].any(axis=0))[0]
        bands.append((int(cols.min()), top, int(cols.max()), bottom))
    return bands


def check_grim_size(label: str, img: np.ndarray, want: dict) -> None:
    """Refuse a capture that is not the screen it was asked for. The rule is
    `sheet.capture_size_complaint`, which says at length why a wrongly-sized
    image is worse here than a missing one."""
    complaint = sheet.capture_size_complaint(label, (img.shape[1], img.shape[0]), want)
    if complaint is not None:
        raise Fail(complaint)


def check_desk_is_bare(ppm: Path, background: np.ndarray, why: str) -> None:
    """Photograph EVERY output the compositor has and insist every one of
    them is the flat backdrop and nothing else. Used for two different
    claims — the desktop before the HUD exists, and the desktop a running
    HUD has decided to leave alone — so the caller says which it is asking.

    Two exposures, because the desk is not every output (D70). `OUTPUTS` is
    ares and comes back in one wide `grim -g`; the narrow output sits to the
    right of the desk on purpose, so the desk capture cannot see it, and
    until this took its own picture a surface that mapped on that screen with
    nothing to say was caught by NOTHING: the quiet shot photographs the desk
    alone, and the lit shots' corner check only bounds the box that was drawn.
    The second exposure is 0.3 Mpx against the desk's 33.
    """
    capture("desk", ppm)
    img = read_ppm(ppm)
    check_grim_size(f"the desk shot for {ppm.name}", img, sheet.DESK)
    for out in sheet.OUTPUTS:
        region = img[0 : out["height"], out["x"] : out["x"] + out["width"]]
        box = drawn_box(region, background)
        if box is not None:
            raise Fail(f"{out['name']}: something is drawn at {box} — {why}")

    narrow = sheet.output_by_role("narrow")
    narrow_ppm = ppm.with_name(f"{ppm.stem}-narrow.ppm")
    capture("narrow", narrow_ppm)
    narrow_img = read_ppm(narrow_ppm)
    check_grim_size(f"the narrow shot for {ppm.name}", narrow_img, narrow)
    box = drawn_box(narrow_img, background)
    if box is not None:
        raise Fail(f"{narrow['name']}: something is drawn at {box} — {why}")


def check_corner(name: str, region: np.ndarray, background: np.ndarray, lit: bool) -> None:
    """Whatever the HUD drew on this monitor has to be inside the box
    shell.qml declares, inset from the TOP-RIGHT corner. Everything else
    on the monitor must be untouched desktop."""
    h, w, _ = region.shape
    box = drawn_box(region, background)
    if not lit:
        if box is not None:
            raise Fail(
                f"{name}: the HUD drew at {box} on a monitor that should be bare "
                "desktop — an unmapped surface is what earned emptiness MEANS, "
                "and this one is mapped"
            )
        return
    if box is None:
        raise Fail(
            f"{name}: nothing drawn. Either the surface never mapped on this "
            "monitor, or every plate refused the frames it was given"
        )
    x0, y0, x1, y1 = box
    left = w - sheet.SURFACE_W - sheet.INSET
    bottom = sheet.SURFACE_H + sheet.INSET
    if x0 < left or x1 >= w or y0 < 0 or y1 > bottom:
        raise Fail(
            f"{name}: drew at x{x0}..{x1} y{y0}..{y1}, outside the "
            f"{sheet.SURFACE_W}x{sheet.SURFACE_H} box shell.qml anchors to the "
            f"top-right corner (x>={left}, y<={bottom}) — the layer-shell "
            "anchors are not doing what the source says"
        )
    # The dock itself: the plates hang off the right edge at Theme.insetPx.
    # Anti-aliasing can shave a subpixel, so this is a window rather than
    # an equality — but an inset that drifted by ten pixels, or a stack
    # that quietly centred itself, would not fit through it.
    gap = w - 1 - x1
    if not (sheet.INSET - 2 <= gap <= sheet.INSET + 2):
        raise Fail(
            f"{name}: right-hand gap is {gap}px, not the {sheet.INSET}px inset "
            "personality/theme.toml declares"
        )
    # AND THE OTHER EDGE, on a screen narrower than the corner (PLAN D68).
    #
    # The box check above is vacuous there and silently so: `left` comes out
    # NEGATIVE on a 280 px output (280 - 300 - 16 = -36), because the surface
    # really does hang off the left of the world and the check is written
    # about the surface. What has to hold on such a screen is not a fact
    # about the surface at all — it is D66's clamp: `plateRoomPx` is
    # `min(surface.width, screen.width) - 2 x insetPx`, so a plate may reach
    # to the inset and no further, and a plate that reached past it would be
    # laying a sentence out in the part of the surface that is not on any
    # screen. Same two pixels of anti-aliasing slack the right-hand gap gets.
    #
    # It is asserted on EVERY output rather than only the narrow one, because
    # on a monitor wider than the corner it is a weaker restatement of the box
    # check and costs nothing; the day it bites is the day a surface stops
    # being granted what it asks for.
    if x0 < sheet.INSET - 2:
        raise Fail(
            f"{name}: drew from x{x0}, inside the {sheet.INSET}px left inset of "
            f"a {w}px screen. On an output narrower than the "
            f"{sheet.SURFACE_W}px surface the plates are capped by "
            "`plateRoomPx` and not by the surface, so this is that clamp "
            "failing on a real compositor — the HUD is drawing where the "
            "screen is not"
        )


# ----------------------------------------------------------- the click probe


# How long to wait for the HUD to light itself, and for a click to land.
# The first is the bridge's own respawn (2 s) plus LinkState's grace (5 s)
# with room to spare; the second is a compositor round trip.
BLIND_TIMEOUT_S = 25.0
CLICK_TIMEOUT_S = 3.0

# How long a second Wayland client gets to map its window onto the monitor it
# was told to open on, and how long the backdrop gets to be flat again once
# those windows are gone. Both were bare literals until PLAN D58 asked what a
# pathological run of this harness can cost and found two numbers nothing
# could add up.
CLIENT_WINDOW_TIMEOUT_S = 15.0
CLIENTS_GONE_S = 0.5


def click_at(x: int, y: int) -> None:
    """Warp the seat's cursor to a point in LAYOUT coordinates and press.

    `cursor set` is a warp, not motion, and the compositor is configured
    `focus_follows_mouse no` — so nothing at all happens until the button,
    and whatever the button does is a routing decision.
    """
    swaymsg("seat", "-", "cursor", "set", str(x), str(y))
    swaymsg("seat", "-", "cursor", "press", "button1")
    swaymsg("seat", "-", "cursor", "release", "button1")


def wait_for_blind_plate(ppm: Path, background: np.ndarray, label: str):
    """Wait until the HUD, given no bus at all, draws its blind plate.

    The one lit state a probe can hold indefinitely. Every OTHER thing
    this HUD says is a frame ageing out — a heartbeat speaks for two of
    its own periods, a confirmation for the window jv-act declared — and
    a plate that blanked part-way through a measurement would make that
    measurement a reading of an unmapped surface. LinkState's grace runs
    out, LinkPlate appears, and it stays until a bus comes back.

    Returns the capture it first saw the plate in and the box it drew in.
    """
    deadline = time.monotonic() + BLIND_TIMEOUT_S
    while time.monotonic() < deadline:
        capture("primary", ppm)
        img = read_ppm(ppm)
        box = drawn_box(img, background)
        if box is not None:
            check_corner(f"{label} {sheet.output_by_role('primary')['name']}", img, background, True)
            return img, box
        time.sleep(0.5)
    raise Fail(
        f"the HUD never drew anything on the primary monitor in "
        f"{BLIND_TIMEOUT_S:.0f}s with no bus at all — LinkPlate is the one lit "
        f"state {label} can rely on, and it never arrived"
    )


def wait_for_drawing(
    ppm: Path,
    background: np.ndarray,
    bus_addr: str,
    keepalive: list,
    complaint: str,
    differs_from=None,
):
    """Wait until the primary monitor's drawn region exists (and differs
    from `differs_from`, when given), re-publishing `keepalive` while we
    look.

    The keepalive is not politeness. Every live-bus state in this HUD is a
    frame ageing out — core/OutputState.qml stops believing a snapshot
    after three of jv-context's own periods — and a capture of a 2560x1440
    screen plus a numpy compare is slow enough to outlast that. Without it
    this loop could watch the plate it is waiting for expire, then time out
    and blame the element.

    Returns the box. Raises with `complaint` if it never arrives.
    """
    deadline = time.monotonic() + BLIND_TIMEOUT_S
    while time.monotonic() < deadline:
        capture("primary", ppm)
        box = drawn_box(read_ppm(ppm), background)
        if box is not None and box != differs_from:
            return box
        feed_snapshots(1.0, keepalive, bus_addr)
    raise Fail(
        f"{complaint} in {BLIND_TIMEOUT_S:.0f}s, so the idle window below "
        "would be measuring a bare desktop and calling it stillness"
    )


# The idle probe's two windows. The settle is past §06's longest ease with
# room to spare, so a fade that is still finishing is never counted as the
# HUD failing to stop; the window is long enough that a 60 fps scene would
# put hundreds of commits in it and a once-a-second blink would put several.
IDLE_SETTLE_S = 4.0
IDLE_WINDOW_S = 6.0

def probe_idle_frames(stage: Path, background: np.ndarray) -> None:
    """The HUD renders NOTHING while nothing changes (invariant 10, §06).

    "ambient GPU cost < 2 ms/frame, 0 fps when idle" is the one invariant-10
    claim that is about cost rather than about behaviour, and it was the
    last one resting on an argument: Qt Quick renders on change, the shell
    unmaps when it has nothing to say, therefore zero. Both halves are true
    and neither is a measurement — and the thing that would break them is
    not a bad argument but one ordinary edit. A plate that pulses, a
    duration that counts up, a `NumberAnimation` left on
    `loops: Animation.Infinite`: each of those looks completely correct in
    a diff and in a photograph, and each one costs a composite of three
    monitors, forever, on a desktop where nothing is happening.

    So the frames are counted, from the HUD's own side of the Wayland
    socket. Four windows, because they are four different claims and the
    HUD can fail each one without failing the others:

      · QUIET — a live bus CARRYING TRAFFIC the HUD subscribes to and has
        nothing to say about: one context.system snapshot per second, an
        ordinary unmuted sink (A40). The surface stays unmapped (earned
        emptiness is the ordinary state) and must produce nothing. A bus
        with literally nothing on it would prove less: the HUD is a live
        subscriber, jv-context heartbeats at 1 Hz all day, and the thing
        worth knowing is that a frame arriving is not a frame drawn.
      · LIT — a plate on screen, saying something true, with no further
        input at all: no broker, LinkPlate after LinkState's grace. The
        first measurement of stillness as a property of what the elements
        DO rather than of an absent surface — and, on its own, partly a
        fact about the silence, because a HUD with no bus has nothing
        arriving to make it re-render.
      · LIVE AND LIT (A42) — both at once, which is the state the HUD is
        actually in on a running machine: two plates on screen, a real
        broker, and a snapshot arriving every second for the whole window.
        Every second the `seq` moves, OutputState's expiry timer re-arms
        and every binding downstream of the snapshot re-evaluates — to the
        same values. A commit here is a re-render on BOOKKEEPING, which is
        the one way of spending §06's budget that neither window above can
        see. It was impossible until A40: OutputState is the first element
        that stays lit on a LIVE bus for as long as it is fed.
      · MIC AND HEALTH (A43) — live and lit again, with the other two
        plates this harness can hold: `MIC NO AUDIO` and `jv-ears
        DEGRADED`, both off one jv-ears heartbeat re-published at 1 Hz.
        The window above cannot reach them, and it cannot see how they
        fail either: HealthPlate renders a LIST, and a roster rebuilt into
        a fresh array on every heartbeat is a `Repeater` model that
        changed, whether or not a single word in it did.

    Each window has a control, because a probe that reads an empty log
    cannot tell "the HUD drew nothing" from "nobody was listening". The
    quiet window is followed by a real frame that lights the mic plate,
    the lit window is preceded by the blind plate arriving, and the two
    live-lit ones by two plates arriving; every one of those stretches
    MUST contain commits, measured by the same regex, through the same
    log. If the instrument breaks, it fails there rather than reporting a
    perfect idle.

    WHAT THIS IS NOT. Not milliseconds of GPU: this compositor is pixman
    on a headless backend and its timings say nothing about a 1660 SUPER.
    It answers the other half — "0 fps when idle" — which is the half that
    an edit can silently take away.
    """
    log("idle probe: 0 fps when nothing changes (invariant 10 / §06)")

    # --- QUIET: a live bus, nothing published, every plate with nothing
    # true to say. The surface is not mapped and there is nothing to draw.
    bus_addr = str(stage / "idle-quiet.sock")
    broker = Proc(
        "jarvisd",
        [os.environ["JARVISD_BIN"]],
        stage / "idle-quiet-jarvisd.log",
        dict(os.environ, JARVIS_BUS=bus_addr),
    )
    hud = None
    try:
        broker.wait_for("jarvisd listening on")
        hud = Proc(
            "jv-hud",
            [os.environ["JV_HUD_BIN"]],
            stage / "idle-quiet-hud.log",
            dict(os.environ, JARVIS_BUS=bus_addr, WAYLAND_DEBUG="1"),
        )
        hud.wait_for("Configuration Loaded")
        time.sleep(IDLE_SETTLE_S)

        quiet = stage / "idle-quiet.ppm"
        check_desk_is_bare(quiet, background, "before the quiet window")
        mark = hud.mark()
        # jv-context's own cadence, for the length of the window. Every one
        # of these reaches the HUD — it is a subscribed topic — and not one
        # of them is anything to draw.
        snapshots = feed_snapshots(IDLE_WINDOW_S, [sheet.SINK_OK], bus_addr)
        commits, frames = sheet.surface_traffic(hud.since(mark))
        if commits:
            raise Fail(
                f"the HUD committed {commits} surface updates ({frames} frame "
                f"callbacks) in {IDLE_WINDOW_S:.0f}s while receiving "
                f"{snapshots} context.system snapshots it had nothing to say "
                "about, with every plate dark and the surface unmapped — §06 "
                "says an idle desktop renders at 0 fps"
            )
        # Only now: the emptiness is what makes that zero mean something.
        check_desk_is_bare(quiet, background, "after the quiet window")
        log(
            f"  quiet: {commits} commits in {IDLE_WINDOW_S:.0f}s under "
            f"{snapshots} snapshots, desktop untouched"
        )

        # The control for that zero. One real frame, and the mic plate has
        # something true to say: whatever the HUD does next goes through
        # the same log and the same regex that just read nothing.
        mark = hud.mark()
        publish_shot({"frames": [sheet.MIC_OPEN]}, bus_addr)
        lit = stage / "idle-woken.ppm"
        deadline = time.monotonic() + BLIND_TIMEOUT_S
        box = None
        while time.monotonic() < deadline:
            capture("primary", lit)
            box = drawn_box(read_ppm(lit), background)
            if box is not None:
                break
            time.sleep(0.5)
        woke, _ = sheet.surface_traffic(hud.since(mark))
        if box is None:
            raise Fail(
                "the mic plate never appeared after jv-ears said the device was "
                "open, so the quiet window above proves nothing: a HUD that had "
                "stopped listening would have read exactly the same"
            )
        if not woke:
            raise Fail(
                "the HUD lit up without committing a single surface update, so "
                "this probe is not reading the HUD's Wayland traffic at all and "
                "its zero above means nothing"
            )
        log(f"  control: waking the HUD cost {woke} commits, through the same log")
    finally:
        if hud is not None:
            hud.stop()
        broker.stop()

    # --- LIT: a plate on screen and no further input. No broker at all,
    # because this window needs a lit state that cannot expire under it —
    # the same reason the click probe runs without one.
    hud = Proc(
        "jv-hud",
        [os.environ["JV_HUD_BIN"]],
        stage / "idle-lit-hud.log",
        dict(os.environ, JARVIS_BUS=str(stage / "idle-no-broker.sock"), WAYLAND_DEBUG="1"),
    )
    try:
        start = hud.mark()
        hud.wait_for("Configuration Loaded")
        ppm = stage / "idle-lit.ppm"
        _, box = wait_for_blind_plate(ppm, background, "idle probe")
        arriving, _ = sheet.surface_traffic(hud.since(start))
        if not arriving:
            raise Fail(
                "the blind plate reached the screen without a single surface "
                "commit in the HUD's Wayland log — the log is not the HUD's, "
                "and the window below would read zero no matter what it drew"
            )
        log(f"  the blind plate arrived at {box}, costing {arriving} commits")

        time.sleep(IDLE_SETTLE_S)
        mark = hud.mark()
        time.sleep(IDLE_WINDOW_S)
        commits, frames = sheet.surface_traffic(hud.since(mark))
        if commits:
            raise Fail(
                f"a HUD with a plate on screen and nothing new to say committed "
                f"{commits} surface updates ({frames} frame callbacks) in "
                f"{IDLE_WINDOW_S:.0f}s. Something in the shell is animating on "
                "its own: §06 allows motion that encodes a signal and forbids a "
                "scene that keeps rendering when nothing changed"
            )
        # The zero above is only worth something if the plate was still
        # there for all of it — a surface that unmapped mid-window would
        # have gone quiet for the least interesting reason there is.
        capture("primary", ppm)
        after = drawn_box(read_ppm(ppm), background)
        if after != box:
            raise Fail(
                f"the HUD drew at {box} before the window and {after} after it, "
                "so the plate changed under the measurement and its zero says "
                "nothing about stillness"
            )
        log(f"  lit and still: {commits} commits in {IDLE_WINDOW_S:.0f}s")
    finally:
        hud.stop()

    # --- LIVE AND LIT: a plate on screen, a real broker, and a frame
    # arriving every second for the whole window (A42).
    #
    # The window above is the one A34 could hold still, and its limit is
    # worth stating plainly: a HUD with no bus has nothing arriving to make
    # it re-render, so its zero is partly a fact about the silence. The
    # quiet window has the traffic and no plate; the lit window has the
    # plate and no traffic. This one has both, which is the state the HUD
    # is actually in on a running machine.
    #
    # `OutputState` is what makes it possible, and it is the first element
    # that could: it is a LIVE READING of two topics rather than a latch
    # (A40), so it stays true exactly as long as the frames keep coming.
    # One `speaking` from jv-voice, which does not expire on its own, plus a
    # muted snapshot re-published at 1 Hz, and two plates sit on screen
    # indefinitely — SPEAKING above, OUTPUT MUTED under it.
    #
    # What could go wrong here that neither window above would catch: the
    # HUD re-rendering on BOOKKEEPING. Every second the snapshot's `seq` and
    # `ts` change, `OutputState.pairKey` changes, its expiry timer re-arms,
    # and every binding downstream of the snapshot re-evaluates — to the
    # same values, because the mixer is still muted and the words are the
    # same words. If Qt commits a frame for that, §06's budget is being
    # spent on nothing a user could see.
    bus_addr = str(stage / "idle-live.sock")
    broker = Proc(
        "jarvisd",
        [os.environ["JARVISD_BIN"]],
        stage / "idle-live-jarvisd.log",
        dict(os.environ, JARVIS_BUS=bus_addr),
    )
    hud = None
    try:
        broker.wait_for("jarvisd listening on")
        hud = Proc(
            "jv-hud",
            [os.environ["JV_HUD_BIN"]],
            stage / "idle-live-hud.log",
            dict(os.environ, JARVIS_BUS=bus_addr, WAYLAND_DEBUG="1"),
        )
        hud.wait_for("Configuration Loaded")
        time.sleep(SETTLE_S)

        ppm = stage / "idle-live.ppm"
        check_desk_is_bare(ppm, background, "before the live-lit window")

        # Lit in TWO steps, because "something is drawn" is not the claim.
        # StatePlate has said SPEAKING since A3 and would light on the
        # jv-voice frame alone — so a window that only checked for pixels
        # could be holding StatePlate still while OutputPlate never
        # appeared, and it would report exactly the same zero. So: first an
        # AUDIBLE sink, which lights StatePlate and nothing else, then the
        # mute, and the drawn region has to GROW DOWNWARDS. That is
        # OutputPlate arriving under it, measured in pixels, and it is also
        # the first time A40's decision — this line exists only while the
        # sink is silent — has been checked through a compositor.
        # Both feeds carry jv-voice's heartbeat as well as the snapshot, and
        # that is a lesson this window taught rather than a decoration. A41
        # gave OutputPlate a second publisher to satisfy, and the first
        # version published that beat ONCE: `sys.health` says `period_s` 5,
        # core/HealthState.qml calls a service lost after two of its own
        # periods, and eleven seconds into the window HealthPlate arrived
        # under the plate being held still — 41 px of "jv-voice lost",
        # reported as the plate changing under the measurement. A service
        # this HUD is being told is SPEAKING has to keep saying it is alive,
        # which is what a real one does.
        audible = [sheet.VOICE_DEFAULT_SINK, sheet.SINK_OK]
        muted = [sheet.VOICE_DEFAULT_SINK, sheet.SINK_MUTED]

        mark = hud.mark()
        publish_shot({"frames": [sheet.VOICE_SPEAKING] + audible}, bus_addr)
        wait_for_drawing(
            ppm,
            background,
            bus_addr,
            audible,
            "jv-voice said it was speaking and the HUD drew nothing",
        )
        # Both boxes are read AFTER a settle, never off the first capture
        # that differs: §06's fade is a real animation and a region measured
        # half way through one is a smaller region than the plate. Comparing
        # two mid-fade boxes would make the growth check below a coin flip.
        feed_snapshots(IDLE_SETTLE_S, audible, bus_addr)
        capture("primary", ppm)
        speaking_box = drawn_box(read_ppm(ppm), background)
        log(f"  speaking into an audible sink: drawn at {speaking_box}")

        publish_shot({"frames": muted}, bus_addr)
        wait_for_drawing(
            ppm,
            background,
            bus_addr,
            muted,
            "the sink went muted mid-utterance and the HUD drew nothing",
            differs_from=speaking_box,
        )
        lighting, _ = sheet.surface_traffic(hud.since(mark))
        feed_snapshots(IDLE_SETTLE_S, muted, bus_addr)
        capture("primary", ppm)
        box = drawn_box(read_ppm(ppm), background)
        # What "a plate arrived UNDER another one" is, in this geometry.
        # sheet.grew_downwards is the rule, stated once and unit-tested
        # without a compositor: the top and right edges are what dock the
        # stack and must not move, the bottom must grow, and the left edge
        # may travel outwards — OUTPUT MUTED is a longer line than
        # SPEAKING, which the first version of this check called a failure.
        if not sheet.grew_downwards(speaking_box, box):
            raise Fail(
                f"muting the sink changed the drawn region from {speaking_box} "
                f"to {box}, which is not a plate ARRIVING UNDER another one at "
                "the same top-right corner — the window below would be holding "
                "something else still, and OutputPlate would be untested"
            )
        if not lighting:
            raise Fail(
                "two plates reached the screen without a single surface commit "
                "in the HUD's Wayland log — the log is not the HUD's, and the "
                "window below would read zero no matter what it drew"
            )
        check_corner(
            f"live-lit {sheet.output_by_role('primary')['name']}",
            read_ppm(ppm),
            background,
            True,
        )
        log(
            f"  and then into a muted one: {box[3] - speaking_box[3]} px taller "
            f"at {box}, the pair costing {lighting} commits"
        )

        mark = hud.mark()
        snapshots = feed_snapshots(IDLE_WINDOW_S, muted, bus_addr)
        commits, frames = sheet.surface_traffic(hud.since(mark))

        # The box FIRST, and the commit count is quoted in its message: a
        # plate that expired mid-window would have committed the traffic of
        # LEAVING, and reporting that as "the shell is animating" would send
        # the next reader looking for an animation that does not exist.
        capture("primary", ppm)
        after = drawn_box(read_ppm(ppm), background)
        if after != box:
            raise Fail(
                f"the HUD drew at {box} before the live-lit window and {after} "
                f"after it ({commits} commits under {snapshots} snapshots), so "
                "the plate changed under the measurement — most likely the feed "
                "did not keep it true, and its zero would have been about an "
                "unmapped surface"
            )
        if commits:
            raise Fail(
                f"a HUD with two plates on screen committed {commits} surface "
                f"updates ({frames} frame callbacks) in {IDLE_WINDOW_S:.0f}s "
                f"while receiving {snapshots} context.system snapshots that said "
                "exactly what the ones before them said. Nothing a user could "
                "see changed, so this is a re-render on bookkeeping — a `seq` "
                "moving, a timer re-arming — and §06 budgets the ambient scene "
                "for signals, not for housekeeping"
            )
        log(
            f"  live and lit: {commits} commits in {IDLE_WINDOW_S:.0f}s under "
            f"{snapshots} snapshots, plate still at {after}"
        )
    finally:
        if hud is not None:
            hud.stop()
        broker.stop()

    # --- MIC AND HEALTH: the other two plates this harness can hold (A43).
    #
    # The window above measures `StatePlate` and `OutputPlate`. That leaves
    # four plates that have never been watched standing still at all, and
    # two of them come cheap, because ONE jv-ears heartbeat lights both: a
    # device that is open and has gone silent is `MIC NO AUDIO` on
    # core/MicState.qml's reading, and `jv-ears DEGRADED` on jv-ears' own
    # word for itself. Re-publish that single frame at 1 Hz and both sit
    # there for as long as the harness cares to feed it.
    #
    # It is worth being exact about what the feed is doing here, because it
    # is NOT what it does above. `OutputState` stops believing a snapshot
    # after three of jv-context's periods, so the live-lit window's feed is
    # life support — stop it and the plate leaves. A heartbeat speaks for
    # two of its own `period_s`, and jv-ears declares 5, so these two plates
    # would survive a six-second window with no feed at all. The feed is the
    # SUBJECT, not the life support: a frame arriving every second, with a
    # plate on screen, and nothing in it that any pixel depends on. What it
    # does keep true is the run-up — two settles and two waits are well past
    # ten seconds — so a feed that never ran fails on the box below rather
    # than reading a vacuous zero.
    #
    # And this pair can fail in a way the pair above cannot. `HealthPlate`
    # renders a LIST: core/HealthState.qml rebuilds its roster on every
    # heartbeat, and a fresh JS array is a different array even when every
    # line in it is the same line. A `Repeater` told its model changed
    # rebuilds its delegates — a frame, on three surfaces, to draw exactly
    # what was already there. Nothing above could see that: the live-lit
    # window's findings list is empty the whole time, and an empty list
    # rebuilt is still nothing on screen.
    bus_addr = str(stage / "idle-ears.sock")
    broker = Proc(
        "jarvisd",
        [os.environ["JARVISD_BIN"]],
        stage / "idle-ears-jarvisd.log",
        dict(os.environ, JARVIS_BUS=bus_addr),
    )
    hud = None
    try:
        broker.wait_for("jarvisd listening on")
        hud = Proc(
            "jv-hud",
            [os.environ["JV_HUD_BIN"]],
            stage / "idle-ears-hud.log",
            dict(os.environ, JARVIS_BUS=bus_addr, WAYLAND_DEBUG="1"),
        )
        hud.wait_for("Configuration Loaded")
        time.sleep(SETTLE_S)

        ppm = stage / "idle-ears.ppm"
        check_desk_is_bare(ppm, background, "before the mic-and-health window")

        # Lit in two steps, for the same reason the window above is: "the
        # HUD drew something" is not the claim. A healthy jv-ears with the
        # device open lights `MicPlate` ALONE — nothing is wrong, so
        # HealthPlate draws its earned nothing — and then the device goes
        # silent and the same service reports itself degraded. The drawn
        # region has to grow DOWNWARDS: that is the health line arriving
        # under the mic line, measured in pixels. Without it this could be
        # holding MicPlate still while HealthPlate never appeared, and it
        # would report exactly the same zero.
        open_mic = [sheet.MIC_OPEN]
        deaf = [sheet.MIC_DEAF]

        mark = hud.mark()
        publish_shot({"frames": open_mic}, bus_addr)
        wait_for_drawing(
            ppm,
            background,
            bus_addr,
            open_mic,
            "jv-ears said the device was open and delivering audio and the "
            "HUD drew nothing",
        )
        # Measured after a settle, never off the first capture that differs:
        # §06's fade is a real animation and a region read half way through
        # one is smaller than the plate, which would make the growth check
        # below a coin flip.
        feed_snapshots(IDLE_SETTLE_S, open_mic, bus_addr)
        capture("primary", ppm)
        mic_box = drawn_box(read_ppm(ppm), background)
        log(f"  a microphone open and delivering: drawn at {mic_box}")

        publish_shot({"frames": deaf}, bus_addr)
        wait_for_drawing(
            ppm,
            background,
            bus_addr,
            deaf,
            "the device went silent and the HUD neither said MIC NO AUDIO nor "
            "reported jv-ears degraded",
            differs_from=mic_box,
        )
        lighting, _ = sheet.surface_traffic(hud.since(mark))
        feed_snapshots(IDLE_SETTLE_S, deaf, bus_addr)
        capture("primary", ppm)
        box = drawn_box(read_ppm(ppm), background)
        if not sheet.grew_downwards(mic_box, box):
            raise Fail(
                f"the device going silent changed the drawn region from "
                f"{mic_box} to {box}, which is not a plate ARRIVING UNDER "
                "another one at the same top-right corner — the window below "
                "would be holding MicPlate alone, and HealthPlate would be "
                "untested"
            )
        if not lighting:
            raise Fail(
                "two plates reached the screen without a single surface commit "
                "in the HUD's Wayland log — the log is not the HUD's, and the "
                "window below would read zero no matter what it drew"
            )
        check_corner(
            f"mic-and-health {sheet.output_by_role('primary')['name']}",
            read_ppm(ppm),
            background,
            True,
        )
        log(
            f"  and then deaf: {box[3] - mic_box[3]} px taller at {box}, the "
            f"pair costing {lighting} commits"
        )

        mark = hud.mark()
        beats = feed_snapshots(IDLE_WINDOW_S, deaf, bus_addr)
        commits, frames = sheet.surface_traffic(hud.since(mark))

        # The box FIRST, and the commit count quoted in its message: a plate
        # that left mid-window would have committed the traffic of LEAVING,
        # and calling that "the shell is animating" would send the next
        # reader looking for an animation that does not exist.
        capture("primary", ppm)
        after = drawn_box(read_ppm(ppm), background)
        if after != box:
            raise Fail(
                f"the HUD drew at {box} before the mic-and-health window and "
                f"{after} after it ({commits} commits under {beats} "
                "heartbeats), so the plates changed under the measurement and "
                "their zero says nothing about stillness"
            )
        # The one way this window can go quietly vacuous. Its plates outlive
        # a six-second silence on their own, so — unlike the window above —
        # a feed that stopped would leave the picture intact and turn this
        # back into A34's lit window without failing anything.
        if beats < 2:
            raise Fail(
                f"the mic-and-health window published {beats} heartbeats in "
                f"{IDLE_WINDOW_S:.0f}s, so nothing arrived while it was "
                "measuring: this is A34's lit window wearing a different name"
            )
        if commits:
            raise Fail(
                f"a HUD showing MIC NO AUDIO and jv-ears DEGRADED committed "
                f"{commits} surface updates ({frames} frame callbacks) in "
                f"{IDLE_WINDOW_S:.0f}s while receiving {beats} jv-ears "
                "heartbeats that said exactly what the ones before them said. "
                "Nothing a user could see changed, so this is a re-render on "
                "bookkeeping — most likely HealthPlate's list being rebuilt "
                "because HealthState handed it a new array of the same lines"
            )
        log(
            f"  mic and health: {commits} commits in {IDLE_WINDOW_S:.0f}s "
            f"under {beats} heartbeats, plates still at {after}"
        )
    finally:
        if hud is not None:
            hud.stop()
        broker.stop()


    # --- HEARD AND CONFIRM: the last two plates, and the only two whose
    # words come off a LATCH (A48).
    #
    # The three windows above hold five plates between them, and every one
    # of them is a READING: `OutputState` believes a snapshot while the
    # snapshots keep coming, `MicState` and `HealthState` read the heartbeat
    # in front of them. Nothing above this line has a latch in it.
    #
    # These two do, and they are the only two in the HUD that do.
    # `core/HeardState.qml` remembers a final transcript because partials
    # ride the same topic and `bus.latest()` would blank the sentence the
    # instant the user started the next one; `core/ConfirmState.qml`
    # remembers a question because the ANSWER lands on the same topic and
    # would erase it. Both remember an observation the bus no longer
    # carries, and both hold it against a clock they arm themselves.
    #
    # Which is what makes re-publishing mean something different here. Up
    # there a repeated frame re-evaluates a binding. Here it RE-TAKES THE
    # LATCH: `transcript` and `request` are replaced by new envelopes,
    # `transcriptKey` and `requestKey` change (`publish_shot` stamps a
    # fresh `ts` on every frame, which is what a live publisher does),
    # `armHold` and `armExpiry` run, `expired` is cleared again and a
    # one-shot timer is restarted — once a second, forever, while the two
    # sentences on screen do not move a pixel. A plate that did anything
    # visible when its latch was re-taken would be invisible to all four
    # windows above, and would cost a composite of three monitors for as
    # long as the question stood.
    #
    # That is not a hypothetical edit. A21 and A22 are both open items
    # about THIS plate — the confirm window shows that time is running and
    # never how much is left, and the plate vanishes rather than leaving —
    # and the obvious implementation of either is a number that ticks or a
    # bar that shrinks. This is the only window in which `ConfirmPlate` is
    # on screen at all.
    #
    # The window jv-act declares is 15 s and this publishes exactly that.
    # Inflating it would have made the feed unnecessary and the measurement
    # a picture of a machine that does not exist — the same refusal A43
    # made about a heartbeat's `period_s`.
    bus_addr = str(stage / "idle-ask.sock")
    broker = Proc(
        "jarvisd",
        [os.environ["JARVISD_BIN"]],
        stage / "idle-ask-jarvisd.log",
        dict(os.environ, JARVIS_BUS=bus_addr),
    )
    hud = None
    try:
        broker.wait_for("jarvisd listening on")
        hud = Proc(
            "jv-hud",
            [os.environ["JV_HUD_BIN"]],
            stage / "idle-ask-hud.log",
            dict(os.environ, JARVIS_BUS=bus_addr, WAYLAND_DEBUG="1"),
        )
        hud.wait_for("Configuration Loaded")
        time.sleep(SETTLE_S)

        ppm = stage / "idle-ask.ppm"
        check_desk_is_bare(ppm, background, "before the heard-and-confirm window")

        # Lit in two steps, like the two windows above and for the same
        # reason: "the HUD drew something" is not the claim. The transcript
        # alone lights `HeardPlate` — nothing is being asked yet — and then
        # jv-act stops in front of the tool and the question arrives. The
        # drawn region has to grow DOWNWARDS: `ConfirmPlate` sits ABOVE
        # `HeardPlate` in the stack (a question you have fifteen seconds to
        # answer must not appear under three other plates), so the top of
        # the stack is the top of the stack either way, the heard line moves
        # down to make room, and the union of the two is taller at the same
        # top-right corner. Without that check this could be holding the
        # transcript still while the question never appeared, and it would
        # report exactly the same zero.
        heard = [sheet.HEARD_FINAL]
        asked = [sheet.HEARD_FINAL, sheet.CONFIRM_REQUEST]

        mark = hud.mark()
        publish_shot({"frames": heard}, bus_addr)
        wait_for_drawing(
            ppm,
            background,
            bus_addr,
            heard,
            "jv-ears published a final transcript and the HUD never showed "
            "the words",
        )
        # Measured after a settle, never off the first capture that differs:
        # §06's fade is a real animation and a region read half way through
        # one is smaller than the plate, which would make the growth check
        # below a coin flip.
        feed_snapshots(IDLE_SETTLE_S, heard, bus_addr)
        capture("primary", ppm)
        heard_box = drawn_box(read_ppm(ppm), background)
        log(f"  the words jv-ears took down: drawn at {heard_box}")

        publish_shot({"frames": [sheet.CONFIRM_REQUEST]}, bus_addr)
        wait_for_drawing(
            ppm,
            background,
            bus_addr,
            asked,
            "jv-act stopped in front of a destructive tool and the HUD drew "
            "no question",
            differs_from=heard_box,
        )
        lighting, _ = sheet.surface_traffic(hud.since(mark))
        feed_snapshots(IDLE_SETTLE_S, asked, bus_addr)
        capture("primary", ppm)
        box = drawn_box(read_ppm(ppm), background)
        if not sheet.grew_downwards(heard_box, box):
            raise Fail(
                f"jv-act asking changed the drawn region from {heard_box} to "
                f"{box}, which is not a plate ARRIVING at the same top-right "
                "corner — the window below would be holding HeardPlate alone, "
                "and ConfirmPlate would be untested"
            )
        if not lighting:
            raise Fail(
                "two plates reached the screen without a single surface commit "
                "in the HUD's Wayland log — the log is not the HUD's, and the "
                "window below would read zero no matter what it drew"
            )
        check_corner(
            f"heard-and-confirm {sheet.output_by_role('primary')['name']}",
            read_ppm(ppm),
            background,
            True,
        )
        log(
            f"  and then jv-act asked: {box[3] - heard_box[3]} px taller at "
            f"{box}, the pair costing {lighting} commits"
        )

        mark = hud.mark()
        relatches = feed_snapshots(IDLE_WINDOW_S, asked, bus_addr)
        commits, frames = sheet.surface_traffic(hud.since(mark))

        # The box FIRST, and the commit count quoted in its message: a plate
        # that left mid-window would have committed the traffic of LEAVING,
        # and calling that "the shell is animating" would send the next
        # reader looking for an animation that does not exist.
        capture("primary", ppm)
        after = drawn_box(read_ppm(ppm), background)
        if after != box:
            raise Fail(
                f"the HUD drew at {box} before the heard-and-confirm window "
                f"and {after} after it ({commits} commits under {relatches} "
                "re-publishes), so the plates changed under the measurement "
                "and their zero says nothing about stillness"
            )
        # The one way this window can go quietly vacuous, and it is window
        # 4's way rather than window 3's. A latch outlives its own silence:
        # ConfirmState holds the question for the 15 s jv-act declared and
        # HeardState holds the line for 30, so a feed that never ran would
        # leave both plates exactly where they are for the whole six seconds
        # and turn this back into A34's lit window with more machinery in
        # front of it. The re-publishes are therefore counted, and the
        # re-taking of the latch IS the subject.
        if relatches < 2:
            raise Fail(
                f"the heard-and-confirm window published {relatches} frames in "
                f"{IDLE_WINDOW_S:.0f}s, so nothing arrived while it was "
                "measuring: the latches would have held on their own and this "
                "is A34's lit window wearing a different name"
            )
        if commits:
            raise Fail(
                f"a HUD showing a transcript and the question jv-act asked "
                f"about it committed {commits} surface updates ({frames} frame "
                f"callbacks) in {IDLE_WINDOW_S:.0f}s while receiving "
                f"{relatches} re-publishes of the same two frames. Nothing a "
                "user could see changed, so this is a re-render on the LATCH "
                "being re-taken — ConfirmState.request and "
                "HeardState.transcript replaced, their keys moved, their "
                "one-shot timers re-armed — and §06 budgets the ambient scene "
                "for signals, not for housekeeping"
            )
        log(
            f"  heard and confirm: {commits} commits in {IDLE_WINDOW_S:.0f}s "
            f"under {relatches} re-publishes, plates still at {after}"
        )

        # --- AND WHAT CAME OF IT: the last plate in the stack, and the
        # third latch (A49).
        #
        # `ActionPlate` was the only plate in this HUD that had never been
        # watched standing still, and the five windows above could not
        # reach it: nothing in any of them publishes an `action.result` at
        # all. It is a latch with a 30 s hold, exactly like `HeardState`,
        # so the mechanism A48 proved applies here unchanged.
        #
        # IT IS NOT A SIXTH PROCESS, and that was the decision A49 was
        # opened to make. A window per plate is how a probe stops being a
        # measurement and starts being a fixture, and a sixth jarvisd plus
        # a sixth jv-hud would have bought nothing but a longer run. So
        # this is the SAME broker, the SAME shell and the SAME turn as the
        # window above, carried to its end: the user asked for the
        # downloads folder to be emptied, jv-act stopped in front of the
        # tool, and now the user answers and the tool fails. The probe
        # still starts five HUDs, and a test pins that count.
        #
        # Which means the story has to run FORWARD, and that costs a step
        # nothing else in this harness has ever measured: a plate LEAVING.
        # `action.result` landing while `ConfirmPlate` still stood would be
        # jv-act having run a tool it was still asking permission for —
        # core/ConfirmState.qml would hold that question up quite happily,
        # since it only lets go for an answer naming this request_id — and
        # the measurement would be of a machine that cannot exist. So the
        # answer is published, the region has to SHRINK back (the same
        # `grew_downwards` rule read the other way round: the stack with
        # the question on it was taller, at the same top-right corner), and
        # only then does the outcome arrive.
        #
        # What the arriving frame does here is a step past A48. Re-taking
        # `HeardState.transcript` replaces an envelope and re-arms a timer.
        # Re-taking `ActionState.failure` does that AND re-runs
        # `toolFor()`, which reaches back to the `intent.action` still on
        # the bus, compares its request_id, and re-resolves the tool name
        # from scratch — once a second, forever, while the same three words
        # sit on screen. No window above has a binding that reads a SECOND
        # topic every time the first one arrives.
        answered = [sheet.HEARD_FINAL, sheet.TRASH_INTENT]
        acted = answered + [sheet.TRASH_FAILED]

        publish_shot({"frames": [sheet.CONFIRM_GRANTED]}, bus_addr)
        wait_for_drawing(
            ppm,
            background,
            bus_addr,
            answered,
            "the user answered jv-act and the question never came off the "
            "screen",
            differs_from=box,
        )
        feed_snapshots(IDLE_SETTLE_S, answered, bus_addr)
        capture("primary", ppm)
        answered_box = drawn_box(read_ppm(ppm), background)
        if not sheet.grew_downwards(answered_box, box):
            raise Fail(
                f"the answer changed the drawn region from {box} to "
                f"{answered_box}, which is not a plate LEAVING the same "
                "top-right corner — the outcome below would land on a HUD "
                "still asking permission for the tool it had already run"
            )
        log(
            f"  the user said yes: {box[3] - answered_box[3]} px shorter at "
            f"{answered_box}, the question gone"
        )

        mark = hud.mark()
        publish_shot({"frames": [sheet.TRASH_FAILED]}, bus_addr)
        wait_for_drawing(
            ppm,
            background,
            bus_addr,
            acted,
            "jv-act ran the tool, it failed, and the HUD said nothing about "
            "it",
            differs_from=answered_box,
        )
        lighting, _ = sheet.surface_traffic(hud.since(mark))
        feed_snapshots(IDLE_SETTLE_S, acted, bus_addr)
        capture("primary", ppm)
        acted_box = drawn_box(read_ppm(ppm), background)
        if not sheet.grew_downwards(answered_box, acted_box):
            raise Fail(
                f"the failure changed the drawn region from {answered_box} "
                f"to {acted_box}, which is not a plate ARRIVING at the same "
                "top-right corner — the window below would be holding "
                "HeardPlate alone, and ActionPlate would be untested"
            )
        if not lighting:
            raise Fail(
                "a plate reached the screen without a single surface commit "
                "in the HUD's Wayland log — the log is not the HUD's, and the "
                "window below would read zero no matter what it drew"
            )
        check_corner(
            f"and-what-came-of-it {sheet.output_by_role('primary')['name']}",
            read_ppm(ppm),
            background,
            True,
        )
        log(
            f"  and it did not work: {acted_box[3] - answered_box[3]} px "
            f"taller at {acted_box}, the report costing {lighting} commits"
        )

        mark = hud.mark()
        reruns = feed_snapshots(IDLE_WINDOW_S, acted, bus_addr)
        commits, frames = sheet.surface_traffic(hud.since(mark))

        capture("primary", ppm)
        after = drawn_box(read_ppm(ppm), background)
        if after != acted_box:
            raise Fail(
                f"the HUD drew at {acted_box} before the outcome window and "
                f"{after} after it ({commits} commits under {reruns} "
                "re-publishes), so the plates changed under the measurement "
                "and their zero says nothing about stillness"
            )
        # A48's guard, and needed for the same reason: both latches here
        # hold for 30 s, so a feed that never ran would leave the two plates
        # exactly where they are for the whole six seconds and report a
        # perfect zero about an idle bus.
        if reruns < 2:
            raise Fail(
                f"the outcome window published {reruns} frames in "
                f"{IDLE_WINDOW_S:.0f}s, so nothing arrived while it was "
                "measuring: the latches would have held on their own and "
                "this is A34's lit window wearing a different name"
            )
        if commits:
            raise Fail(
                f"a HUD showing a transcript and the failure of the tool it "
                f"led to committed {commits} surface updates ({frames} frame "
                f"callbacks) in {IDLE_WINDOW_S:.0f}s while receiving "
                f"{reruns} re-publishes of the same three frames. Nothing a "
                "user could see changed, so this is a re-render on "
                "housekeeping — ActionState.failure replaced, its key moved, "
                "its hold re-armed, and toolFor() re-reading intent.action "
                "to arrive at the same tool name — and §06 budgets the "
                "ambient scene for signals, not for bookkeeping"
            )
        log(
            f"  and what came of it: {commits} commits in "
            f"{IDLE_WINDOW_S:.0f}s under {reruns} re-publishes, plates still "
            f"at {after}"
        )
    finally:
        if hud is not None:
            hud.stop()
        broker.stop()


def probe_click_through(stage: Path, background: np.ndarray) -> None:
    """A click over the HUD reaches the window underneath it (A32).

    `mask: Region {}` — an empty input region — is the third of invariant
    10's structural promises, and it was the only one this compositor
    could not be asked about, because a pass-through has no meaning
    without something to pass through TO. So this stage puts an ordinary
    window under the HUD on the primary monitor, a second one on a side
    monitor to hold the keyboard, and clicks three points:

      · a CONTROL far from the surface, which proves the measurement
        itself works — without it a harness whose clicks went nowhere
        would report a perfect pass-through.
      · a pixel the HUD actually PAINTED. Chosen from the capture rather
        than guessed, so it is over a plate and not over transparency.
      · a point inside the 300x826 surface box that the HUD painted
        NOTHING on. A mask narrowed to the visible plates would pass the
        previous point and fail here, and it is the likelier mistake: an
        input region that tracks the content looks reasonable in a diff.

    Every one of them must end with the keyboard on the window under the
    HUD, which is sway saying it routed that button to the window.

    WHAT THIS IS NOT. The window's own wl_pointer never fires, and the
    assertion is not "the client logged a button". A headless seat has no
    input device, so it advertises no pointer capability and no client
    binds one; the button is synthesised through sway's IPC and the only
    witness is sway's own routing, read back over IPC. That routing IS the
    hit test — `node_at_coords` consults each layer surface's input region
    before it ever looks at a window — so a HUD that had opened its mask
    would keep the keyboard exactly where it was. VERIFIED both ways by
    mutation, which is the only reason to trust the direction of it.

    It runs LAST and starts no jarvisd on purpose. Last, because it puts
    two windows on screen and every photograph above needs a bare desktop
    behind the HUD. Without a broker, because the probe needs a lit HUD
    that does not expire: every other lit state is a frame ageing out
    (a heartbeat speaks for two of its own periods, a confirmation for
    its window), and a plate that blanked mid-probe would report a
    pass-through that was really an unmapped surface. A bus the HUD
    cannot see is the one thing it says indefinitely — LinkPlate, after
    LinkState's grace — and the input region is a property of the
    surface, not of what is drawn on it.
    """
    log("click probe: the empty input mask, against a real window (A32)")
    primary = sheet.output_by_role("primary")
    side = sheet.output_by_role("side")
    env = dict(os.environ, JARVIS_BUS=str(stage / "click-no-broker.sock"))

    hud = Proc("jv-hud", [os.environ["JV_HUD_BIN"]], stage / "click-hud.log", env)
    clients: list[Proc] = []
    try:
        hud.wait_for("Configuration Loaded")

        # Wait for the surface to admit it is blind. Until then it is
        # unmapped, and an unmapped surface passes every click through
        # whatever its mask says.
        lit = stage / "click-lit.ppm"
        lit_img, box = wait_for_blind_plate(lit, background, "click probe")
        painted = (lit_img != background).any(axis=2)
        log(f"  the blind HUD is drawing at {box}")

        # The three points, in this monitor's own coordinates.
        cy = (box[1] + box[3]) // 2
        row = np.nonzero(painted[cy])[0]
        on_plate = (int(row[len(row) // 2]), cy)

        left = primary["width"] - sheet.SURFACE_W
        in_box: tuple[int, int] | None = None
        for y in range(sheet.SURFACE_H - 1, -1, -1):
            cols = np.nonzero(~painted[y, left:])[0]
            if len(cols):
                in_box = (left + int(cols[len(cols) // 2]), y)
                break
        if in_box is None:
            raise Fail(
                "every pixel of the surface box is painted, so there is no "
                "unpainted point inside it to click"
            )

        control = (primary["width"] // 2, primary["height"] // 2)
        for name, (px, py) in (("control", control), ("unpainted", in_box)):
            if painted[py, px]:
                raise Fail(f"the {name} point {(px, py)} is painted after all")
        if not painted[on_plate[1], on_plate[0]]:
            raise Fail(f"the plate point {on_plate} is not painted after all")

        # Two ordinary windows: one filling the monitor the HUD docks to,
        # one on a side monitor with nothing over it, whose only job is to
        # hold the keyboard between clicks so that "it moved" is a fact
        # about the click and not about where focus already was.
        under = start_client("under", primary, stage, clients)
        holder = start_client("holder", side, stage, clients)
        if (under["rect"]["width"], under["rect"]["height"]) != (
            primary["width"],
            primary["height"],
        ):
            raise Fail(
                f"the window under the HUD is {under['rect']}, not the whole of "
                f"{primary['name']} — the points below would not all be over it"
            )

        for label, (px, py) in (
            ("control, clear of the surface", control),
            ("on a painted plate", on_plate),
            ("inside the surface box, unpainted", in_box),
        ):
            swaymsg(f"[con_id={holder['id']}]", "focus")
            if focused_node() != holder["id"]:
                raise Fail("could not park the keyboard on the holder window")
            click_at(primary["x"] + px, py)
            got = focused_node()
            end = time.monotonic() + CLICK_TIMEOUT_S
            while got != under["id"] and time.monotonic() < end:
                time.sleep(0.1)
                got = focused_node()
            if got != under["id"]:
                if label.startswith("control"):
                    raise Fail(
                        f"a click at {(px, py)} — nowhere near the HUD — did not "
                        "reach the window it landed on, so this probe is broken "
                        "rather than the HUD"
                    )
                raise Fail(
                    f"a click {label} at {(px, py)} never reached the window "
                    f"underneath (the keyboard stayed on {got}). The HUD's "
                    "surface took the button, so `mask: Region {}` is no longer "
                    "an empty input region — invariant 10 says every click "
                    "passes through"
                )
            log(f"  {label}: the window underneath got it")

        # The HUD was drawing for all of that, not just before it. The
        # windows go first so the backdrop is flat again and the box is
        # measured the same way it was the first time.
        for client in clients:
            client.stop()
        clients = []
        time.sleep(CLIENTS_GONE_S)
        capture("primary", lit)
        after = drawn_box(read_ppm(lit), background)
        if after != box:
            raise Fail(
                f"the HUD drew at {box} before the clicks and {after} after, so "
                "it was not necessarily on screen for them"
            )
        log("  the HUD was still drawing the same box afterwards")
    finally:
        for client in clients:
            client.stop()
        hud.stop()


def start_client(role: str, out: dict, stage: Path, clients: list) -> dict:
    """An ordinary Wayland toplevel, tiled onto one monitor.

    `wev` because it is the smallest real client available and it needs
    nothing: this stage wants a window, not a widget. It is NOT used for
    what it prints — see probe_click_through on why the button never
    reaches any client's wl_pointer here.
    """
    swaymsg("focus", "output", out["name"])
    before = {w["id"] for w in toplevels()}
    clients.append(
        Proc(f"wev-{role}", [os.environ["WEV_BIN"]], stage / f"click-{role}.log", dict(os.environ))
    )
    deadline = time.monotonic() + CLIENT_WINDOW_TIMEOUT_S
    while time.monotonic() < deadline:
        fresh = [w for w in toplevels() if w["id"] not in before]
        if fresh:
            if len(fresh) > 1:
                raise Fail(f"{len(fresh)} windows appeared where one was started")
            win = fresh[0]
            if win["rect"]["x"] != out["x"]:
                raise Fail(
                    f"the {role} window opened at x={win['rect']['x']}, not on "
                    f"{out['name']} at x={out['x']}"
                )
            log(f"  {role} window {win['id']} on {out['name']} at {win['rect']}")
            return win
        time.sleep(0.2)
    raise Fail(f"the {role} window never appeared on {out['name']}")


# ------------------------------------------- the granted-width probe (D68)


def probe_surface_granted(stage: Path, background: np.ndarray) -> None:
    """What size the compositor GAVE a surface that asked for 300 px on a
    280 px screen (PLAN D68).

    `shell.qml` declares a 300 px corner on every monitor it can see, and
    since D66 it clamps its plates with
    `min(surface.width, screen.width) - 2 x insetPx` — a line whose whole
    reason for existing is that a layer-shell surface anchored to one edge is
    granted the width it asks for whether or not the output is that wide, so
    on a narrow screen the surface overhangs the left edge and the plates
    have to know. That sentence is in three comments in this repo and had
    never been observed. D66 measured the clamp in a QML engine, against a
    plain `Item` whose `width` a test assigns, and a test assigning a width
    is not a compositor configuring a surface.

    PIXELS CANNOT ANSWER IT, which is why this is a probe and not another
    photograph. A surface clamped by wlroots to 280 and a surface granted 300
    over a 280 px screen leave the stack in exactly the same place: anchored
    16 px off the right edge, 248 px of room, the same plate, the same
    picture. The two readings differ in one place only — the `configure`
    event the compositor sends — and the HUD's own WAYLAND_DEBUG log carries
    it, the same log the idle probe counts commits in.

    So: one shell, on all four outputs, lit by one real heartbeat, and every
    layer surface it was given read back out of the socket log. The census is
    the instrument's control — a regex that stopped matching, or a shell that
    mapped nothing, both come back as an empty dict, and "no surface was
    configured wrongly" is true of both. One surface per output, or this
    probe says nothing.
    """
    log("granted probe: what the compositor gave a 300px surface on a 280px screen")

    bus_addr = str(stage / "granted.sock")
    broker = Proc(
        "jarvisd",
        [os.environ["JARVISD_BIN"]],
        stage / "granted-jarvisd.log",
        dict(os.environ, JARVIS_BUS=bus_addr),
    )
    hud = None
    try:
        broker.wait_for("jarvisd listening on")
        hud = Proc(
            "jv-hud",
            [os.environ["JV_HUD_BIN"]],
            stage / "granted-hud.log",
            dict(os.environ, JARVIS_BUS=bus_addr, WAYLAND_DEBUG="1"),
        )
        hud.wait_for("Configuration Loaded")

        # One open microphone. The narrowest thing this HUD can say — 164 px
        # of `MIC` against 248 px of room — on purpose: the plate must not be
        # the thing under test. What is under test is whether the SURFACE it
        # sits on was given 300 px, and a plate that fitted with room to
        # spare cannot be mistaken for evidence about the clamp.
        publish_shot({"frames": [sheet.MIC_OPEN]}, bus_addr)

        ppm = stage / "granted-narrow.ppm"
        deadline = time.monotonic() + BLIND_TIMEOUT_S
        box = None
        while time.monotonic() < deadline:
            capture("narrow", ppm)
            img = read_ppm(ppm)
            box = drawn_box(img, background)
            if box is not None:
                break
            # The heartbeat again while we look, for `wait_for_drawing`'s
            # reason: jv-ears declares `period_s: 5` and MicState believes a
            # beat for two of them, which a slow capture loop can outlast.
            feed_snapshots(1.0, [sheet.MIC_OPEN], bus_addr)
        if box is None:
            raise Fail(
                f"the HUD drew nothing on the {sheet.NARROW_W}px output in "
                f"{BLIND_TIMEOUT_S:.0f}s with the microphone open. Either the "
                "surface never mapped there — which is its own news, since "
                "`Variants` is supposed to give every screen one — or the "
                "clamp left the plate with no room at all"
            )
        narrow = sheet.output_by_role("narrow")
        check_corner(f"granted {narrow['name']}", img, background, True)
        log(f"  the corner on {narrow['name']} ({narrow['width']}px): {box}")

        sizes = sheet.layer_surface_sizes(hud.since(0))
        if len(sizes) != len(sheet.ALL_OUTPUTS):
            raise Fail(
                f"{len(sizes)} layer surfaces were configured in the HUD's "
                f"Wayland log and this compositor has {len(sheet.ALL_OUTPUTS)} "
                f"outputs ({sizes}) — so this probe is not reading the traffic "
                "it thinks it is, and whatever it says about the width below "
                "is about a surface nobody can name"
            )
        asked = (sheet.SURFACE_W, sheet.SURFACE_H)
        wrong = {oid: got for oid, got in sizes.items() if got != asked}
        if wrong:
            raise Fail(
                f"the HUD asked for {asked[0]}x{asked[1]} on every output and "
                f"the compositor configured {wrong} — so a layer surface is "
                f"NOT granted the size it asks for, and the three comments "
                "that say it is (shell.qml's `plateRoomPx`, sheet.py's "
                "narrow output, this probe) are wrong. The clamp in "
                "`plateRoomPx` is then doing nothing, because `surface.width` "
                "is already the screen's"
            )
        # The line itself, once, because everything above is a count. A
        # census that came back right for the wrong reason — a regex matching
        # something else that happens to be four per run — is exactly the
        # failure this probe is built against, and one verbatim line in the
        # run's output is what lets a reader check the instrument rather than
        # trust it. It is also where `tools/tests/test_hudscreens.py` gets
        # the real text its reader is graded on.
        sample = next(
            (
                line.strip()
                for line in hud.since(0).splitlines()
                if sheet.LAYER_CONFIGURE_RE.search(line)
            ),
            "",
        )
        log(f"  the line that says so: {sample}")
        log(
            f"  all {len(sizes)} surfaces configured {asked[0]}x{asked[1]} — "
            f"granted as asked, including on the {narrow['width']}px output, "
            f"so the surface overhangs its left edge by "
            f"{sheet.SURFACE_W - narrow['width'] + sheet.INSET}px"
        )
    finally:
        if hud is not None:
            hud.stop()
        broker.stop()


# ---------------------------------------------------------------------- main


def capture(target: str, ppm: Path) -> None:
    grim = os.environ["GRIM_BIN"]
    if target == "desk":
        geom = f"0,0 {sheet.DESK_WIDTH}x{sheet.DESK_HEIGHT}"
        argv = [grim, "-t", "ppm", "-g", geom, str(ppm)]
    else:
        out = sheet.output_by_role(target)
        argv = [grim, "-t", "ppm", "-o", out["name"], str(ppm)]
    subprocess.run(argv, check=True, capture_output=True)


def check_capture(
    shot: dict, target: str, ppm: Path, img: np.ndarray, background: np.ndarray
) -> None:
    if target == "desk":
        # One monitor at a time: the desk shot's job is to answer whether
        # the same plate really is on all three, so it is checked as three
        # monitors rather than as one wide picture.
        check_grim_size(f"{shot['file']} desk", img, sheet.DESK)
        for out in sheet.OUTPUTS:
            region = img[0 : out["height"], out["x"] : out["x"] + out["width"]]
            check_corner(f"{shot['file']} {out['name']}", region, background, shot["lit"])

        # AND THE FOURTH SCREEN, which is not in the picture (PLAN D72).
        #
        # A desk capture is `sheet.OUTPUTS` in one wide `grim`, and the narrow
        # output sits to the right of the desk on purpose, so every verdict
        # taken off a desk shot was a verdict about three of the four screens
        # the compositor has. D70 closed that for the desktop with no HUD on
        # it (`check_desk_is_bare` takes its own second exposure for exactly
        # this reason); this closes it for the shots.
        #
        # `01-quiet` is why it matters. Its `captures` is `["desk"]` and its
        # `lit` is false, so the one DARK shot on the sheet — frames ARRIVE,
        # and every plate decides it has nothing true to show — was never
        # asked about the one screen where a plate drawing a zero-height
        # sliver or an empty rectangle of glass is most likely and least
        # visible. `check_corner(lit=False)` is the other place in this file
        # where "nothing drawn" is the pass, and until this it never ran on
        # that output at all.
        #
        # One 0.3 Mpx exposure against the desk's 33, and NO PNG: the sheet
        # stays at ten pictures and gains an assertion. An eleventh photograph
        # of an empty 280 px screen was declined on its own grounds (D70) —
        # it is a picture of nothing, and the assertion is worth more.
        #
        # Said out loud rather than discovered: this runs for every desk shot
        # including the LIT ones, and on a 280 px output `check_corner` loses
        # the LEFT bound of its box — `w - SURFACE_W - INSET` is -36, so
        # `x0 < left` is true of nothing. Exactly that one bound, and the item
        # that raised this said "the box half" when it meant it: `y1 > bottom`
        # still holds the stack to 842 px, the right-hand gap still holds it
        # to the inset, and D66's clamp (the `x0 < INSET - 2` below) is what
        # replaces the bound that went. So on `02-heard` and `03-confirm` this
        # is a cheap restatement of claims `03-confirm-narrow.png` already
        # makes; on `01-quiet` it is the only place any of them is made.
        narrow = sheet.output_by_role("narrow")
        narrow_ppm = ppm.with_name(f"{ppm.stem}-narrow.ppm")
        capture("narrow", narrow_ppm)
        narrow_img = read_ppm(narrow_ppm)
        check_grim_size(f"{shot['file']} {narrow['name']}", narrow_img, narrow)
        check_corner(
            f"{shot['file']} {narrow['name']}", narrow_img, background, shot["lit"]
        )
        # Said out loud, because a check nobody can see run is not evidence.
        # Every other probe in this file logs its measurement; this one has no
        # PNG to point at, so the line is the only trace that the fourth screen
        # was looked at — and it names the size the image came back as, which
        # is the half that stops a vacuous read from reading as a pass.
        log(
            f"  and the screen outside the picture: {narrow['name']} came back "
            f"{narrow_img.shape[1]}x{narrow_img.shape[0]} and "
            f"{'is bare' if not shot['lit'] else 'draws in its corner'}, "
            "no picture kept"
        )
    else:
        out = sheet.output_by_role(target)
        check_grim_size(f"{shot['file']} {target}", img, out)
        check_corner(f"{shot['file']} {out['name']}", img, background, shot["lit"])


def main() -> int:
    outdir = Path(os.environ["JV_SCREENS_OUT"])
    stage = Path(os.environ["JV_SCREENS_STAGE"])
    outdir.mkdir(parents=True, exist_ok=True)

    # What the run costs, booked as it is spent (PLAN B75). `hudscreens.sh`
    # has already written the phases it owns — the flake, the compositor —
    # into this same file, and prints the table once the comparison is done.
    # Every name below is classified in `sheet.PHASES`, and a test holds both
    # ends of that: no stretch of this file can escape the accounting, and
    # none can be charged to the wrong half of it.
    cost = sheet.Cost(stage / sheet.COST_FILE)

    background = np.array(
        [int(sheet.BACKDROP[i : i + 2], 16) for i in (1, 3, 5)], dtype=np.uint8
    )

    with cost.phase("checks"):
        check_the_outputs_are_the_ones_the_sheet_declares()
        bare_focus = seat_focus()
        log(
            f"three monitors and the narrow output up; the seat's keyboard is "
            f"on {bare_focus}"
        )

        # The desktop with no HUD on it at all. The quiet shot is compared
        # against THIS, not against an idea of what dark looks like.
        check_desk_is_bare(
            stage / "bare.ppm",
            background,
            f"the bare desktop is not a flat {sheet.BACKDROP} — the backdrop "
            "never came up, so 'the HUD drew nothing' would be unprovable",
        )

    written: list[str] = []
    for shot in sheet.SHOTS:
        log(f"shot {shot['file']}")
        bus_addr = str(stage / f"bus-{shot['file']}.sock")
        env = dict(os.environ, JARVIS_BUS=bus_addr)
        hud = None
        with cost.phase("processes"):
            broker = Proc("jarvisd", [os.environ["JARVISD_BIN"]], stage / f"{shot['file']}-jarvisd.log", env)
        try:
            with cost.phase("processes"):
                broker.wait_for("jarvisd listening on")
                hud = Proc("jv-hud", [os.environ["JV_HUD_BIN"]], stage / f"{shot['file']}-hud.log", env)
                hud.wait_for("Configuration Loaded")
            with cost.phase("settle"):
                time.sleep(SETTLE_S)
                publish_shot(shot, bus_addr)
            hold = shot.get("hold", [])

            # A shot that declares `grows_from` is photographed TWICE. The
            # first exposure is thrown away: it is the same HUD fed the same
            # frames MINUS the one thing the picture is of, and its only job
            # is to be smaller. `StatePlate` has said SPEAKING since A3 and
            # lights on jv-voice's frame alone, so a `04-unheard` in which
            # `OutputPlate` never appeared would be a perfectly good
            # photograph of one plate, pass every check in this file, and
            # sit under a caption describing a second line that is not in
            # it. The measured claim is the same one A42's window makes: the
            # drawn region grew DOWNWARDS, which is what a plate arriving
            # under another one looks like on a stack docked to the corner.
            shorter = None
            if shot.get("grows_from"):
                with cost.phase("settle"):
                    settle(SETTLE_S, shot["grows_from"], bus_addr)
                before = stage / f"{shot['file']}-shorter.ppm"
                with cost.phase("capture"):
                    capture("primary", before)
                    smaller = read_ppm(before)
                with cost.phase("checks"):
                    shorter = drawn_box(smaller, background)
                log(f"  one plate shorter: drawn at {shorter}")

            # And a shot that declares `widens_from` is photographed twice
            # for the OTHER growth (PLAN A86). `grows_from` asks whether a
            # plate arrived; this asks whether a plate that was already
            # there is saying a longer thing — which is what `06-lossy` is
            # a picture of, and which the union of the plates cannot see.
            # That is measured, not assumed: the pair below was
            # photographed before this code existed and the box around the
            # two plates was the same four numbers under both readings,
            # because `MIC LOSING AUDIO` and `jv-ears DEGRADED` are the
            # same sixteen characters wide.
            narrow = None
            if shot.get("widens_from"):
                with cost.phase("settle"):
                    settle(SETTLE_S, shot["widens_from"], bus_addr)
                before = stage / f"{shot['file']}-narrow.ppm"
                with cost.phase("capture"):
                    capture("primary", before)
                    narrower = read_ppm(before)
                with cost.phase("checks"):
                    narrow = drawn_bands(narrower, background)
                log(f"  one word shorter: plates at {narrow}")
                # And the shot's own frames back on the bus. `grows_from`'s
                # shot declares a `hold`, so the settle below re-feeds it;
                # this one deliberately declares none (a heartbeat is
                # believed for two of its own periods), so without this the
                # settle would SLEEP and the picture would be of the
                # narrower reading with the wider one's caption under it.
                with cost.phase("settle"):
                    publish_shot(shot, bus_addr)

            with cost.phase("settle"):
                settle(SETTLE_S, hold, bus_addr)

            # AFTER the frames, on purpose. `visible` is false whenever the
            # HUD has nothing to say, and an unmapped layer surface reserves
            # nothing and focuses nothing no matter what it asked for — so a
            # check run on the quiet shot, or before the frames land, passes
            # for a HUD that would steal the screen the moment it spoke. It
            # was written that way first, and ExclusionMode.Normal walked
            # straight through it.
            with cost.phase("checks"):
                check_no_space_reserved()
                if seat_focus() != bare_focus:
                    raise Fail(
                        f"the seat's keyboard moved to {seat_focus()} while the "
                        f"HUD was drawing (was {bare_focus}) — the HUD stole "
                        "focus, which invariant 10 forbids"
                    )

            grown = None
            for target in shot["captures"]:
                ppm = stage / f"{shot['file']}-{target}.ppm"
                # Re-fed immediately before every exposure, for the same
                # reason the settle above feeds: three monitors and three
                # PNG encodes can outlast a snapshot, and the last shot of
                # the run is the one that would quietly be of a bare
                # desktop.
                if hold:
                    with cost.phase("settle"):
                        publish_shot({"frames": hold}, bus_addr)
                with cost.phase("capture"):
                    capture(target, ppm)
                    img = read_ppm(ppm)
                with cost.phase("checks"):
                    check_capture(shot, target, ppm, img, background)
                    if target == "primary" and shot.get("grows_from"):
                        # BEFORE the PNG is written, not after: a failed run
                        # that had already saved the picture would leave the
                        # wrong one sitting in docs/hud/screens, where the
                        # next reader finds it looking exactly as finished
                        # as the others.
                        grown = drawn_box(img, background)
                        if not sheet.grew_downwards(shorter, grown):
                            raise Fail(
                                f"{shot['file']}: the HUD drew {shorter} on "
                                f"the primary without the frame this shot is "
                                f"OF, and {grown} with it — which is not a "
                                "plate arriving under another one at the same "
                                "top-right corner. The picture about to be "
                                "written is of a HUD saying less than its "
                                "caption says it does"
                            )
                        log(
                            f"  and {grown[3] - shorter[3]} px taller with "
                            f"it: {grown}"
                        )
                    if target == "primary" and shot.get("widens_from"):
                        # Before the PNG is written, for `grows_from`'s
                        # reason: a failed run that had already saved the
                        # picture leaves the wrong one sitting in
                        # docs/hud/screens looking as finished as the rest.
                        wide = drawn_bands(img, background)
                        which = shot["widens_band"]
                        if len(wide) != len(narrow):
                            raise Fail(
                                f"{shot['file']}: the corner held "
                                f"{len(narrow)} plates without the frame "
                                f"this shot is OF and {len(wide)} with it "
                                f"({narrow} -> {wide}) — a plate arrived or "
                                "left, which is not the growth this shot "
                                "measures and means the band counted below "
                                "is not the same plate twice"
                            )
                        moved = [
                            i
                            for i in range(len(wide))
                            if i != which and wide[i] != narrow[i]
                        ]
                        if moved:
                            raise Fail(
                                f"{shot['file']}: band(s) {moved} moved "
                                f"between the two exposures ({narrow} -> "
                                f"{wide}), so the pair does not isolate the "
                                f"plate at band {which} and its widening is "
                                "not evidence about the word this picture "
                                "is of"
                            )
                        if not sheet.widened(narrow[which], wide[which]):
                            raise Fail(
                                f"{shot['file']}: band {which} was "
                                f"{narrow[which]} without the frame this "
                                f"shot is OF and {wide[which]} with it, "
                                "which is not the same plate at the same "
                                "top-right corner reaching further left. "
                                "The picture about to be written is of a "
                                "plate saying a word no longer than the one "
                                "its caption is about"
                            )
                        log(
                            f"  and {narrow[which][0] - wide[which][0]} px "
                            f"wider with it: band {which} at {wide[which]}"
                        )
                name = f"{shot['file']}-{target}.png"
                with cost.phase("encode"):
                    write_png(outdir / name, img)
                written.append(name)
                log(f"  wrote {name} ({img.shape[1]}x{img.shape[0]})")

            # The measurement above only happens on the primary, which is
            # where the shorter exposure was taken. A shot that declared
            # `grows_from` and photographed something else would otherwise
            # skip it in silence.
            if shot.get("grows_from") and grown is None:
                raise Fail(
                    f"{shot['file']} grows from a shorter exposure of the "
                    "primary and never photographed the primary, so nothing "
                    "measured whether the plate it is OF ever arrived"
                )
            if shot.get("widens_from") and "primary" not in shot["captures"]:
                raise Fail(
                    f"{shot['file']} widens from a narrower exposure of the "
                    "primary and never photographed the primary, so nothing "
                    "measured whether the plate it is OF ever said the "
                    "longer word"
                )
        finally:
            with cost.phase("processes"):
                if hud is not None:
                    hud.stop()
                broker.stop()

    with cost.phase("idle"):
        probe_idle_frames(stage, background)
    with cost.phase("click"):
        probe_click_through(stage, background)
    with cost.phase("granted"):
        probe_surface_granted(stage, background)

    expected = sheet.all_files()
    if written != expected:
        raise Fail(f"wrote {written}, sheet declares {expected}")

    # An orphan is a picture of a HUD that no longer exists, and it looks
    # exactly as convincing as the real ones.
    for stale in sorted(outdir.glob("*.png")):
        if stale.name not in expected:
            stale.unlink()
            log(f"removed stale {stale.name}")

    log(f"wrote {len(written)} screens to {outdir}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Fail as exc:
        print(f"hudscreens: FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
