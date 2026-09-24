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
