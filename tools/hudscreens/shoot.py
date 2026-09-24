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
        deadline = time.monotonic() + BLIND_TIMEOUT_S
        box = None
        while time.monotonic() < deadline:
            capture("primary", lit)
            lit_img = read_ppm(lit)
            box = drawn_box(lit_img, background)
            if box is not None:
                break
            time.sleep(0.5)
        if box is None:
            raise Fail(
                f"the HUD never drew anything on {primary['name']} in "
                f"{BLIND_TIMEOUT_S:.0f}s with no bus at all — LinkPlate is the "
                "one lit state this probe can rely on, and it never arrived"
            )
        check_corner(f"click probe {primary['name']}", lit_img, background, True)
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
    bare = stage / "bare.ppm"
    capture("desk", bare)
    bare_img = read_ppm(bare)
    for out in sheet.OUTPUTS:
        region = bare_img[0 : out["height"], out["x"] : out["x"] + out["width"]]
        if drawn_box(region, background) is not None:
            raise Fail(
                f"{out['name']}: the bare desktop is not a flat {sheet.BACKDROP} — "
                "the backdrop never came up, so 'the HUD drew nothing' would be "
                "unprovable"
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
