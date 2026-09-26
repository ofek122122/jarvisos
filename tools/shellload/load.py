#!/usr/bin/env python3
"""Load every shell under a real quickshell, and say what each one said (D41).

Run by `ops/ralph/shellload.sh`, which realizes the binaries out of the flake
and puts a headless sway and a private session bus around this. Everything this
file decides — which shells, which monitors, which notification — is next door
in `shells.py`, where a test with no compositor can read it.

What it does per shell, and it is deliberately the whole of it: start the
shipped binary, wait for quickshell's own `Configuration Loaded`, wake it if
anything here can, hold for a beat, ask the compositor what the surface
reserved, stop it. The log goes to `$JV_SHELLLOAD_STAGE/<attr>.log` and the
SCAN is the script's — one `tools/qmlerrors.py` per shell, because each one
needs its own `--prefix`.

TWO OF THE THREE ARE WOKEN, each by the only thing that can reach it. The
notifier gets a D-Bus client, because the session bus is the whole of its
world. The HUD gets a real broker and eleven real frames (PLAN D43): the
script starts `jarvisd` on this run's own socket, `publish.py` puts
`shells.HUD_FRAMES` on it at 1 Hz, and the HUD's own read-only bridge carries
them into the plates. Before that the HUD here had nothing to say, so no
wl_surface of its was ever created and every plate, every state machine under
it and every binding that only runs on a real frame was outside this gate.

THE COMPOSITOR IS ASKED TWO THINGS, and both are here because a log line
cannot answer either (PLAN D44). First, ONCE, that sway really has the three
monitors `shells.OUTPUTS` declares — every shell builds one surface per
`Quickshell.screens` entry, so a run that got one output would load one
delegate and call it a shell, and nothing checked. Second, PER SHELL, what it
took off the top of each of them: `Configuration Loaded` is the root component
built, and a `PanelWindow` whose layer-shell properties failed to attach gets
that line too. See the D44 section in `shells.py` for which direction each
shell's answer is a proof and which is only a refutation.

THE WAIT IS THE CENSUS. `qmlerrors.py` over an empty file reports "nothing
threw", so a harness that started no engine would grade itself clean forever;
that is why the three staged harnesses had to grow a census in D38. This one
needs none, for the reason `hudscreens.sh` gives: every shell is waited for on
a line quickshell's own logger writes, so a log that was never written, an
engine that died on a syntax error and a binary that is not there are all a
non-zero exit before anything is scanned.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import shells  # noqa: E402

PUBLISH = Path(__file__).resolve().parent / "publish.py"


class Fail(Exception):
    """Something this gate is about did not happen."""


def log(message: str) -> None:
    print(message, flush=True)


def need(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise Fail(f"{name} is not set — this is run by ops/ralph/shellload.sh")
    return value


class Proc:
    """One shipped shell, running, with its output in a file.

    Its own rather than `tools/hudscreens/shoot.py`'s, which is the same shape
    plus the log-offset machinery that harness's frame counter needs — and
    lives behind a numpy import this gate has no use for. Two copies is a
    coincidence; a third would be the time to extract one (PLAN D42).
    """

    def __init__(self, name: str, argv: list[str], logpath: Path):
        self.name = name
        self.logpath = logpath
        self._fh = logpath.open("wb")
        self.p = subprocess.Popen(
            argv, stdout=self._fh, stderr=subprocess.STDOUT
        )

    def stop(self) -> None:
        if self.p.poll() is None:
            self.p.terminate()
            try:
                self.p.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.p.kill()
                self.p.wait(timeout=8)
        self._fh.close()

    def tail(self, chars: int = 2000) -> str:
        return self.logpath.read_text("utf-8", "replace")[-chars:]

    def wait_for(self, needle: str, timeout: float) -> float:
        """Seconds until the log said `needle`.

        A process that EXITED is reported as itself rather than waited out: a
        shell that could not reach the compositor dies in a tenth of a second,
        and thirty seconds of silence is a worse report of the same fact.
        """
        start = time.monotonic()
        deadline = start + timeout
        while time.monotonic() < deadline:
            if self.p.poll() is not None:
                raise Fail(
                    f"{self.name} exited with {self.p.returncode} before saying "
                    f"{needle!r}:\n{self.tail()}"
                )
            if needle in self.logpath.read_text("utf-8", "replace"):
                return time.monotonic() - start
            time.sleep(0.1)
        raise Fail(
            f"{self.name} never said {needle!r} in {timeout:.0f}s:\n{self.tail()}"
        )


# ---------------------------------------------------------- the compositor
#
# Two questions, both of them things no log line can answer. See the D44
# section in `shells.py` for why each shell's answer means what it means.


def swaymsg(*args: str):
    """One sway IPC call, as JSON.

    `-r` so sway answers with the raw reply rather than a success envelope.
    Non-zero is raised rather than reported: a compositor that will not talk
    has made every claim below unanswerable, and an unanswerable claim must
    never read as a passing one.
    """
    done = subprocess.run(
        [need("SWAYMSG_BIN"), "-r", *args],
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        raise Fail(
            f"swaymsg {' '.join(args)} failed (exit {done.returncode}): "
            f"{done.stderr.strip() or done.stdout.strip()}"
        )
    return json.loads(done.stdout)


def check_outputs() -> None:
    """The compositor really has the monitors `shells.OUTPUTS` declares.

    Asked ONCE, before any shell starts, and it is the floor under everything
    else here. `WLR_HEADLESS_OUTPUTS=3` and the `output` lines in the config
    are both requests; nothing until now read the answer. All three shells
    build one surface per `Quickshell.screens` entry, so a run that got one
    output would load one delegate, scan one surface's worth of log and report
    that every shell loads — which is the shape of a gate that quietly stopped
    asking most of its question.
    """
    got = {
        out["name"]: (
            out["current_mode"]["width"],
            out["current_mode"]["height"],
            out["rect"]["x"],
        )
        for out in swaymsg("-t", "get_outputs")
    }
    want = {
        out["name"]: (out["width"], out["height"], out["x"])
        for out in shells.OUTPUTS
    }
    if got != want:
        raise Fail(
            f"the compositor has outputs {got}, and tools/shellload/shells.py "
            f"declares {want} — every shell builds one surface per monitor, so "
            "a run on the wrong ones is a run about a different shell"
        )
    log(f"  compositor: {len(got)} monitors, as declared")


def usable_areas() -> dict[str, tuple[int, int]]:
    """Each output's usable area, which sway shrinks by every exclusive zone.

    Keyed and shaped like `shells.usable_areas()` so the two compare with one
    `==`. An output with no workspace at all is left out rather than defaulted,
    so it fails as a missing key with both dicts printed.
    """
    return {
        ws["output"]: (ws["rect"]["width"], ws["rect"]["height"])
        for ws in swaymsg("-t", "get_workspaces")
    }


def check_reserved(px: int, when: str) -> None:
    """Every monitor is exactly `px` shorter than itself, or this waits.

    POLLED in both directions, because neither is synchronous with anything
    this driver can see: a layer surface is configured over the wayland
    protocol after the client has drawn, and unmapped some time after the
    process is gone. The timeout is short — see `MAPPED_TIMEOUT_S`.
    """
    want = shells.usable_areas(px)
    deadline = time.monotonic() + shells.MAPPED_TIMEOUT_S
    got = None
    while time.monotonic() < deadline:
        got = usable_areas()
        if got == want:
            return
        time.sleep(shells.MAPPED_POLL_S)
    raise Fail(
        f"{when}, the usable area of each monitor should have been {want} "
        f"— {px} px off the top of every one — and after "
        f"{shells.MAPPED_TIMEOUT_S:.0f}s the compositor still reports {got}"
    )


def check_zone(shell: shells.Shell, when: str, *, up: bool) -> None:
    """What this shell has taken off every monitor, right now.

    `up` is whether the shell is supposed to be on screen. Down, the answer is
    always zero: the strip must come back, which is the control that makes the
    bar's reading the BAR'S rather than something else in the session.

    What each shell's answer is worth is not the same for all three, and the
    difference is measured rather than argued — `shells.py`'s D44 section is
    the place it is written down, because that is the file a reader of this
    gate's claims will open.
    """
    px = shells.bar_strip_px(shells.theme_toml_path().read_text("utf-8"))
    want = px if (up and shell.reserves_top) else 0
    check_reserved(want, f"{when} {shell.attr}")


# ------------------------------------------------------------ the notifier


def gdbus(method: str, args: list[str]) -> str:
    """One method on the notification daemon, as an ordinary D-Bus client.

    An external caller on purpose. The notifier's whole input is the session
    bus, so a client is the only thing that can reach it at all — and a reply
    is a fact about the running daemon rather than about the QML that declares
    it.
    """
    done = subprocess.run(
        [need("GDBUS_BIN"), *shells.gdbus_call(method, args)],
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        raise Fail(
            f"{method} on {shells.NOTIFY_DEST} failed "
            f"(exit {done.returncode}): {done.stderr.strip() or done.stdout.strip()}"
        )
    return done.stdout


def wake_notifier() -> None:
    """Ask the daemon what it can do, then send it one notification.

    The capability check first, because it is the cheaper question and the one
    whose answer explains the other: a daemon that answers `GetCapabilities`
    is a daemon that really holds the name, and a `Notify` that returns an id
    is that name accepting a message from a stranger.
    """
    caps = shells.capabilities(gdbus("GetCapabilities", []))
    log(f"  notify: the daemon says it can do {caps or ['nothing']}")
    for want in shells.CAPABILITIES_REQUIRED:
        if want not in caps:
            raise Fail(
                f"the notification daemon does not advertise {want!r}, which "
                f"shell/jv-notify declares it does: {caps}"
            )
    for refused in shells.CAPABILITIES_REFUSED:
        if refused in caps:
            raise Fail(
                f"the notification daemon advertises {refused!r} — the corner "
                "takes no input and cannot deliver it (invariant 10)"
            )
    ident = shells.notify_id(gdbus("Notify", shells.notify_args()))
    if ident <= 0:
        raise Fail(f"Notify answered with id {ident}, which is no notification")
    log(f"  notify: one message accepted as id {ident}")


# ---------------------------------------------------------------- the HUD


def wake_hud(stage: Path) -> Proc:
    """Put real frames on the bus and wait for the corner to name its plates.

    Returns the publisher, for the caller to stop: it republishes at 1 Hz for
    as long as it runs, which is what keeps `output` alive (jv-context's
    snapshot goes stale at 3 s) and what makes the subscription race stop
    mattering — a bus has no backlog, so a frame sent before the HUD's bridge
    subscribed is simply gone.

    THE CENSUS IS THE HUD'S OWN ACCOUNT, and it has to be. Nothing this driver
    can ask sway or the bus would reveal whether the frames reached the plates:
    the HUD reserves no space, takes no focus and — with `ExclusionMode.Ignore`
    and no zone — changes nothing a compositor reports when it maps. So
    `shell/jv-hud/shell.qml` logs one line per surface naming the plates on it,
    and this waits for the line every monitor has to write. A publisher that
    graded itself on what it had just sent would be grading the bus.

    Per monitor, and that is the part worth having: `Variants` builds one
    surface per screen and each one's plates decide for themselves, so a shell
    that quietly stopped building the third surface fails here rather than
    reporting that the HUD lit.
    """
    pub = Proc("publish", [sys.executable, str(PUBLISH)], stage / "hud-frames.log")
    try:
        # One whole round out before anything is expected of the corner: until
        # then a HUD that named nothing is a HUD nobody has told anything.
        pub.wait_for("round 1", shells.HUD_LIT_TIMEOUT_S)
        want = list(shells.HUD_PLATES_LIT)
        hudlog = stage / "jv-hud.log"
        deadline = time.monotonic() + shells.HUD_LIT_TIMEOUT_S
        got: dict[str, list[str] | None] = {}
        while time.monotonic() < deadline:
            if pub.p.poll() is not None:
                raise Fail(
                    f"the publisher exited with {pub.p.returncode}:\n{pub.tail()}"
                )
            said = hudlog.read_text("utf-8", "replace")
            got = {
                out["name"]: shells.hud_corner_plates(said, out["name"])
                for out in shells.OUTPUTS
            }
            if all(plates == want for plates in got.values()):
                log(f"  jv-hud: the corner names {len(want)} plates on every monitor")
                return pub
            time.sleep(shells.MAPPED_POLL_S)
        # Named per monitor and per plate, because the two ways this fails are
        # different repairs: a monitor that never wrote a line at all is a
        # surface that was never built, and one naming nine plates is one plate
        # that never lit.
        report = []
        for name, plates in got.items():
            if plates == want:
                continue
            if plates is None:
                report.append(f"{name}: never said anything about its corner")
                continue
            short = [p for p in want if p not in plates]
            extra = [p for p in plates if p not in want]
            report.append(
                f"{name}: showed [{' '.join(plates) or 'nothing'}]"
                + (f", missing {short}" if short else "")
                + (f", unexpected {extra}" if extra else "")
                + ("" if short or extra else " — in the wrong order")
            )
        raise Fail(
            f"after {shells.HUD_LIT_TIMEOUT_S:.0f}s of "
            f"{len(shells.HUD_FRAMES)} frames at {1 / shells.HUD_ROUND_S:.0f} Hz, "
            f"the corner should have been showing [{' '.join(want)}] on every "
            "monitor. " + "; ".join(report)
        )
    except Exception:
        pub.stop()
        raise


# ----------------------------------------------------------------- the run


def load(shell: shells.Shell, stage: Path) -> None:
    binary = need(shell.env)
    logpath = stage / f"{shell.attr}.log"
    # The control, and the first of the three readings: whatever this shell
    # reserves has to be reserved by THIS shell, so the screens must be whole
    # before it starts. A previous shell that never went away would otherwise
    # be handing this one its verdict.
    check_zone(shell, "before", up=False)
    proc = Proc(shell.attr, [binary], logpath)
    woken: Proc | None = None
    try:
        took = proc.wait_for(shells.READY, shells.READY_TIMEOUT_S)
        log(f"  {shell.attr}: loaded in {took:.2f} s")
        # Whatever can reach this shell, reaches it. Dispatched on the name in
        # `shells.py` rather than on `attr`, so the list of shells stays the
        # only place that decides which of them is given something to do.
        if shell.wake == "notify":
            wake_notifier()
        elif shell.wake == "hud":
            woken = wake_hud(stage)
        elif shell.wake:
            raise Fail(f"{shell.attr} declares wake={shell.wake!r}, which is nothing")
        # A beat, so a binding queued behind the first frame gets the frame.
        time.sleep(shells.HOLD_S)
        check_zone(shell, "while", up=True)
        # Said as what was measured rather than as what it implies. "Took
        # nothing" is also true of a surface that was never created, which is
        # what the notifier's reading still is — its `PanelWindow` is
        # conditionally visible and a zone declared while it was invisible
        # never reaches the compositor (the D44 section in `shells.py`). The
        # HUD's used to be the same sentence about the same nothing and is
        # not any more: with the frames above in it, the corner is lit on
        # every monitor before this is asked, so a surface really is there
        # and really does leave every screen whole (PLAN D43).
        log(
            f"  {shell.attr}: "
            + (
                "its strip is reserved on every monitor"
                if shell.reserves_top
                else "took no space off any monitor"
            )
        )
    finally:
        if woken is not None:
            woken.stop()
        proc.stop()
    # And the third: it gave the screens back. For the two that reserve
    # nothing this is a second reading of the same nothing; for the bar it is
    # what turns "31 px went missing" into "the bar took them".
    check_zone(shell, "after", up=False)


def main() -> int:
    stage = Path(need("JV_SHELLLOAD_STAGE"))
    # Asked first and ends the run on its own rather than being counted with
    # the shells: a run on the wrong monitors is not a shell that failed, it is
    # a gate that cannot ask its question, and three more failures underneath
    # that one would only bury it.
    log("shellload: the compositor")
    try:
        check_outputs()
    except Fail as exc:
        log(f"  FAILED: {exc}")
        return 1
    bad = 0
    for shell in shells.SHELLS:
        log(f"shellload: {shell.attr}")
        try:
            load(shell, stage)
        except Fail as exc:
            log(f"  FAILED: {exc}")
            bad += 1
    if bad:
        log(f"\nshellload: {bad} of {len(shells.SHELLS)} shells did not load.")
        return 1
    log(f"\nshellload: all {len(shells.SHELLS)} shells loaded and mapped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
