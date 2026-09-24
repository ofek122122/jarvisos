"""Photograph the REAL HUD on a real compositor, and measure what it drew.

Driven by `ops/ralph/hudscreens.sh`, which is what puts a wlroots
compositor with ares' three monitors underneath it (PLAN A30). This half
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
    drawn region has to fall inside the 300x560 box shell.qml declares,
    inset from the top-right corner. An anchor that silently flipped, or
    a `Variants` that stopped making one surface per screen, would look
    completely fine in a photograph nobody measured.
  · earned emptiness is REAL emptiness. The quiet shot must come back
    pixel-identical to the bare desktop — not "looks dark", but every
    monitor untouched, which is what an unmapped surface means.
  · a click over the HUD reaches the window UNDERNEATH it (A32). The
    empty input mask was the one invariant-10 claim left resting on a
    reading of shell.qml, because it cannot be measured without a second
    client to pass through to. `probe_click_through` puts one there.
  · the HUD renders NOTHING while nothing changes (A34). "0 fps when
    idle" was an argument about how Qt Quick works, and the thing that
    breaks it is one ordinary edit — a pulse, a counter, an animation
    left looping. `probe_idle_frames` counts commits on the HUD's own
    side of the Wayland socket over three windows — quiet, lit, and lit
    on a bus that never stops talking (A42) — with a control for each.

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


def check_outputs_are_ares_monitors() -> None:
    got = {
        o["name"]: (o["current_mode"]["width"], o["current_mode"]["height"], o["rect"]["x"])
        for o in swaymsg("-t", "get_outputs")
    }
    want = {o["name"]: (o["width"], o["height"], o["x"]) for o in sheet.OUTPUTS}
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
    for out in sheet.OUTPUTS:
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
                self.p.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.p.kill()
                self.p.wait(timeout=8)
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
            await asyncio.sleep(0.1)
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


def check_desk_is_bare(ppm: Path, background: np.ndarray, why: str) -> None:
    """Photograph all three monitors and insist every one of them is the
    flat backdrop and nothing else. Used for two different claims — the
    desktop before the HUD exists, and the desktop a running HUD has
    decided to leave alone — so the caller says which it is asking."""
    capture("desk", ppm)
    img = read_ppm(ppm)
    for out in sheet.OUTPUTS:
        region = img[0 : out["height"], out["x"] : out["x"] + out["width"]]
        box = drawn_box(region, background)
        if box is not None:
            raise Fail(f"{out['name']}: something is drawn at {box} — {why}")


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


# ----------------------------------------------------------- the click probe


# How long to wait for the HUD to light itself, and for a click to land.
# The first is the bridge's own respawn (2 s) plus LinkState's grace (5 s)
# with room to spare; the second is a compositor round trip.
BLIND_TIMEOUT_S = 25.0
CLICK_TIMEOUT_S = 3.0


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
    socket. Three windows, because they are three different claims and the
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

    Each window has a control, because a probe that reads an empty log
    cannot tell "the HUD drew nothing" from "nobody was listening". The
    quiet window is followed by a real frame that lights the mic plate,
    the lit window is preceded by the blind plate arriving, and the
    live-lit one by two plates arriving; every one of those stretches MUST
    contain commits, measured by the same regex, through the same log. If
    the instrument breaks, it fails there rather than reporting a perfect
    idle.

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
        mark = hud.mark()
        publish_shot({"frames": [sheet.VOICE_SPEAKING, sheet.SINK_OK]}, bus_addr)
        wait_for_drawing(
            ppm,
            background,
            bus_addr,
            [sheet.SINK_OK],
            "jv-voice said it was speaking and the HUD drew nothing",
        )
        # Both boxes are read AFTER a settle, never off the first capture
        # that differs: §06's fade is a real animation and a region measured
        # half way through one is a smaller region than the plate. Comparing
        # two mid-fade boxes would make the growth check below a coin flip.
        feed_snapshots(IDLE_SETTLE_S, [sheet.SINK_OK], bus_addr)
        capture("primary", ppm)
        speaking_box = drawn_box(read_ppm(ppm), background)
        log(f"  speaking into an audible sink: drawn at {speaking_box}")

        publish_shot({"frames": [sheet.SINK_MUTED]}, bus_addr)
        wait_for_drawing(
            ppm,
            background,
            bus_addr,
            [sheet.SINK_MUTED],
            "the sink went muted mid-utterance and the HUD drew nothing",
            differs_from=speaking_box,
        )
        lighting, _ = sheet.surface_traffic(hud.since(mark))
        feed_snapshots(IDLE_SETTLE_S, [sheet.SINK_MUTED], bus_addr)
        capture("primary", ppm)
        box = drawn_box(read_ppm(ppm), background)
        # What "a plate arrived UNDER another one" is, in this geometry. The
        # stack is docked to the top-right, so the top edge and the RIGHT
        # edge are the ones that must not move; the bottom must grow. The
        # left edge may travel outwards and does — OUTPUT MUTED is a longer
        # line than SPEAKING, so the region widens leftwards, which the
        # first version of this check called a failure.
        moved = (
            box is None
            or box[1] != speaking_box[1]
            or box[2] != speaking_box[2]
            or box[0] > speaking_box[0]
        )
        if moved or box[3] <= speaking_box[3]:
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
        snapshots = feed_snapshots(IDLE_WINDOW_S, [sheet.SINK_MUTED], bus_addr)
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
      · a point inside the 300x560 surface box that the HUD painted
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
        time.sleep(0.5)
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
    deadline = time.monotonic() + 15.0
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


def check_capture(shot: dict, target: str, img: np.ndarray, background: np.ndarray) -> None:
    if target == "desk":
        # One monitor at a time: the desk shot's job is to answer whether
        # the same plate really is on all three, so it is checked as three
        # monitors rather than as one wide picture.
        for out in sheet.OUTPUTS:
            region = img[0 : out["height"], out["x"] : out["x"] + out["width"]]
            check_corner(f"{shot['file']} {out['name']}", region, background, shot["lit"])
    else:
        out = sheet.output_by_role(target)
        if img.shape[:2] != (out["height"], out["width"]):
            raise Fail(
                f"{shot['file']} {target}: grim returned "
                f"{img.shape[1]}x{img.shape[0]}, not {out['width']}x{out['height']}"
            )
        check_corner(f"{shot['file']} {out['name']}", img, background, shot["lit"])


def main() -> int:
    outdir = Path(os.environ["JV_SCREENS_OUT"])
    stage = Path(os.environ["JV_SCREENS_STAGE"])
    outdir.mkdir(parents=True, exist_ok=True)

    background = np.array(
        [int(sheet.BACKDROP[i : i + 2], 16) for i in (1, 3, 5)], dtype=np.uint8
    )

    check_outputs_are_ares_monitors()
    bare_focus = seat_focus()
    log(f"three monitors up; the seat's keyboard is on {bare_focus}")

    # The desktop with no HUD on it at all. The quiet shot is compared
    # against THIS, not against an idea of what dark looks like.
    check_desk_is_bare(
        stage / "bare.ppm",
        background,
        f"the bare desktop is not a flat {sheet.BACKDROP} — the backdrop never "
        "came up, so 'the HUD drew nothing' would be unprovable",
    )

    written: list[str] = []
    for shot in sheet.SHOTS:
        log(f"shot {shot['file']}")
        bus_addr = str(stage / f"bus-{shot['file']}.sock")
        env = dict(os.environ, JARVIS_BUS=bus_addr)
        broker = Proc("jarvisd", [os.environ["JARVISD_BIN"]], stage / f"{shot['file']}-jarvisd.log", env)
        hud = None
        try:
            broker.wait_for("jarvisd listening on")
            hud = Proc("jv-hud", [os.environ["JV_HUD_BIN"]], stage / f"{shot['file']}-hud.log", env)
            hud.wait_for("Configuration Loaded")
            time.sleep(SETTLE_S)
            publish_shot(shot, bus_addr)
            time.sleep(SETTLE_S)

            # AFTER the frames, on purpose. `visible` is false whenever the
            # HUD has nothing to say, and an unmapped layer surface reserves
            # nothing and focuses nothing no matter what it asked for — so a
            # check run on the quiet shot, or before the frames land, passes
            # for a HUD that would steal the screen the moment it spoke. It
            # was written that way first, and ExclusionMode.Normal walked
            # straight through it.
            check_no_space_reserved()
            if seat_focus() != bare_focus:
                raise Fail(
                    f"the seat's keyboard moved to {seat_focus()} while the HUD "
                    f"was drawing (was {bare_focus}) — the HUD stole focus, "
                    "which invariant 10 forbids"
                )

            for target in shot["captures"]:
                ppm = stage / f"{shot['file']}-{target}.ppm"
                capture(target, ppm)
                img = read_ppm(ppm)
                check_capture(shot, target, img, background)
                name = f"{shot['file']}-{target}.png"
                write_png(outdir / name, img)
                written.append(name)
                log(f"  wrote {name} ({img.shape[1]}x{img.shape[0]})")
        finally:
            if hud is not None:
                hud.stop()
            broker.stop()

    probe_idle_frames(stage, background)
    probe_click_through(stage, background)

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
