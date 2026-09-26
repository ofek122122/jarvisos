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

AND THE HUD IS LOADED TWICE, because one of its plates is only ever on screen
when the other ten cannot be (PLAN D47). `LinkPlate` reports that the HUD
cannot SEE the bus, so a fourth quickshell runs the same shipped binary with
`JARVIS_BUS` pointed at nothing and waits out `core/LinkState.qml`'s grace.
The corner then has to name exactly `link` — which is both the first proof
anywhere that this HUD ever admits it is blind, and the only reading that can
tell a plate REFUSING from a plate with nothing to say.

AND THAT RUN HAS A SECOND ACT, which is the more dangerous half (PLAN D49): a
real broker is started on the very path that HUD has been failing to reach, and
the corner has to go DARK again. `LinkState` never clears the flag its grace
set, so a plate that latched on forever — a permanent NO BUS over a healthy
machine, which teaches the user to ignore the one plate that qualifies all the
others — passes the blind census exactly as the shipped HUD does.

AND A THIRD, because letting go of the plate is only half a cycle (PLAN D52).
The recovered HUD is shown the same eleven frames on that late broker and its
corner has to light the same ten plates — on an engine whose `BusModel` caches
and `HealthState` roster were emptied by every one of the link-downs it sat
through, and whose surface was destroyed when the corner went empty. A HUD that
came back LINKED and never accepted another frame passes the act above exactly:
the corner goes dark because the SOCKET came back, and nothing watched traffic.

THE COMPOSITOR IS ASKED TWO THINGS, and both are here because a log line
cannot answer either (PLAN D44). First, ONCE, that sway really has the three
monitors `shells.OUTPUTS` declares — every shell builds one surface per
`Quickshell.screens` entry, so a run that got one output would load one
delegate and call it a shell, and nothing checked. Second, PER SHELL, what it
took off the top of each of them: `Configuration Loaded` is the root component
built, and a `PanelWindow` whose layer-shell properties failed to attach gets
that line too. Exactly one of the three answers is a PROOF — the bar's, whose
window is always mapped and anchored to an edge plus both perpendicular ones,
which is the only configuration sway zones. The other two are the control that
makes the bar's 31 px the bar's; see the D44 section in `shells.py` for the
injections that say so and for what still protects invariant 10.

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

    def __init__(
        self,
        name: str,
        argv: list[str],
        logpath: Path,
        env: dict[str, str] | None = None,
    ):
        self.name = name
        self.logpath = logpath
        self._fh = logpath.open("wb")
        self.p = subprocess.Popen(
            argv, stdout=self._fh, stderr=subprocess.STDOUT, env=env
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


class ReadyBudget:
    """How long each engine of THIS run may take to say READY (PLAN D53).

    One number was wrong in a way that only showed up in the arithmetic.
    `READY_TIMEOUT_COLD_S` is written against a cold Qt and a cold font cache,
    which is a cost paid once and then not again — so giving it to all four
    engines put 120 s of un-payable wait into the run's pathological ceiling,
    and 30 of the blind engine's 98 s (D50/D52). That mattered because the
    ceiling is a BOUND rather than a budget: a bound nobody could reach is a
    bound that stopped describing the run.

    So the first engine gets the cold number and every engine after it gets one
    derived from what the run has already measured. Shared across `load` and
    `load_blind` rather than kept per call, because "the first engine of the
    run" is the whole of the distinction and a per-shell budget would hand the
    cold number to all four again.

    It is deliberately NOT a stopwatch on the gate. Nothing here is expected to
    spend any of it; what this bounds is the engine that comes up and then holds
    still forever.
    """

    def __init__(self) -> None:
        # None until one engine of this run has loaded, which is exactly the
        # condition "nothing on this machine has been measured yet".
        self.slowest: float | None = None
        # And what the engine that just ran was GIVEN, which is not the same
        # question a moment later: `wait` records the load before anything is
        # printed, so asking `timeout()` after it answers about the NEXT engine.
        self.spent: float | None = None
        self.spent_cold = False

    def timeout(self) -> float:
        if self.slowest is None:
            return shells.READY_TIMEOUT_COLD_S
        return shells.warm_ready_timeout(self.slowest)

    def wait(self, proc: Proc) -> float:
        """Wait for READY on this engine's own bound, and remember the cost."""
        warm = self.slowest
        self.spent, self.spent_cold = self.timeout(), warm is None
        try:
            took = proc.wait_for(shells.READY, self.spent)
        except Fail as exc:
            if warm is None:
                raise
            # A derived bound has to say what it was derived FROM, or a run
            # that failed on a slow machine reads as a shell that did not load.
            # The repair for this failure is a constant, and it is named.
            raise Fail(
                f"{exc}\nthat bound is derived (PLAN D53): the slowest engine "
                f"this run had already loaded took {warm:.2f} s, and nothing "
                f"after the first pays for a cold Qt again. If a WARM engine "
                f"really needs longer on this machine, the number to raise is "
                f"shells.READY_WARM_CEILING_S "
                f"(now {shells.READY_WARM_CEILING_S:.0f}s)."
            ) from None
        self.slowest = took if warm is None else max(warm, took)
        return took

    def spell(self, took: float) -> str:
        """`loaded in 0.40 s of a derived 6s` — the cost AND the bound on it.

        Printed on every run because this is the only place a reader can watch
        the rule decide: the numbers in `shells.py` say what the rule IS, and
        every line here says what it did to one engine. It is also how the D53
        measurement gets made again on every machine this ever runs on — a
        first engine that really is slower than the rest says so in the log
        rather than in an argument.
        """
        return (
            f"loaded in {took:.2f} s of "
            f"{'a cold' if self.spent_cold else 'a derived'} {self.spent:.0f}s"
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
        # On its own budget rather than the corner's — starting a python
        # process and connecting to a bound socket is not a cold Qt, and the
        # two waits stopped being one number when D52 gave this gate a second
        # publisher.
        pub.wait_for("round 1", shells.HUD_PUBLISH_TIMEOUT_S)
        corner_census(
            shells.hud_shell().attr,
            stage / "jv-hud.log",
            list(shells.HUD_PLATES_LIT),
            shells.HUD_LIT_TIMEOUT_S,
            because=(
                f"{len(shells.HUD_FRAMES)} frames at "
                f"{1 / shells.HUD_ROUND_S:.0f} Hz"
            ),
            alive=pub,
        )
        return pub
    except Exception:
        pub.stop()
        raise


def spell(plates: list[str]) -> str:
    """How many plates, in the corner's own vocabulary.

    `nothing` rather than "0 plates", because that is the word the QML logs
    for an empty corner and the word `hud_corner_plates` parses back — and
    since D49 an empty corner is an EXPECTATION here, not only a failure.
    """
    if not plates:
        return "nothing"
    return f"{len(plates)} plate{'' if len(plates) == 1 else 's'}"


def corner_census(
    name: str,
    hudlog: Path,
    want: list[str],
    timeout: float,
    *,
    because: str,
    alive: Proc | None = None,
) -> None:
    """Wait until every monitor's corner names exactly `want`.

    Shared by every reading of a corner here, which is the only reason it is
    a function: one run has a broker and ten lit plates, the blind one has
    none and exactly one (PLAN D47), and the same blind HUD once the bus
    arrives has to have NOTHING on it (PLAN D49). The way a corner is READ is
    the same question all three times, and two copies of it would be two
    answers.
    `name` is which of the two runs is being read, because both write the
    same line and a report that did not say which would send a reader to the
    wrong log. `because` is what the caller did to deserve an answer, for the
    failure message; `alive` is a process whose death means the wait is
    pointless.
    """
    deadline = time.monotonic() + timeout
    got: dict[str, list[str] | None] = {}
    while time.monotonic() < deadline:
        if alive is not None and alive.p.poll() is not None:
            raise Fail(f"{alive.name} exited with {alive.p.returncode}:\n{alive.tail()}")
        said = hudlog.read_text("utf-8", "replace")
        got = {
            out["name"]: shells.hud_corner_plates(said, out["name"])
            for out in shells.OUTPUTS
        }
        if all(plates == want for plates in got.values()):
            log(f"  {name}: the corner names {spell(want)} on every monitor")
            return
        time.sleep(shells.MAPPED_POLL_S)
    # Named per monitor and per plate, because the two ways this fails are
    # different repairs: a monitor that never wrote a line at all is a
    # surface that was never built, and one naming nine plates is one plate
    # that never lit.
    report = []
    # `monitor` rather than `name`, which is the run: the raise below is headed
    # by which of the HUD's runs this is, and a loop variable called `name`
    # quietly retitled every failure after the last monitor it looked at.
    for monitor, plates in got.items():
        if plates == want:
            continue
        if plates is None:
            report.append(f"{monitor}: never said anything about its corner")
            continue
        short = [p for p in want if p not in plates]
        extra = [p for p in plates if p not in want]
        report.append(
            f"{monitor}: showed [{' '.join(plates) or 'nothing'}]"
            + (f", missing {short}" if short else "")
            + (f", unexpected {extra}" if extra else "")
            + ("" if short or extra else " — in the wrong order")
        )
    raise Fail(
        f"{name}: after {timeout:.0f}s of {because}, the corner should have been "
        f"showing [{' '.join(want) or 'nothing'}] on every monitor. "
        + "; ".join(report)
    )


# ----------------------------------------------------------------- the run


def load(shell: shells.Shell, stage: Path, ready: ReadyBudget) -> None:
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
        took = ready.wait(proc)
        log(f"  {shell.attr}: {ready.spell(took)}")
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
        # nothing" is also true of a surface that was never created, and of one
        # that exists and whose zone the compositor DISCARDED — and both of
        # these readings are the second of those. sway honours an exclusive
        # zone only for a surface anchored to one edge or to an edge plus both
        # perpendicular ones; this corner is top+right, so a HUD carrying
        # `exclusiveZone: 100` leaves all three monitors whole here — lit, on
        # both runs, and `visible: true` as well (three injections, in the D44
        # section in `shells.py`). So this is the control that makes the bar's
        # 31 px the bar's and not evidence about what the corner takes. D43
        # amended this comment to claim it had become the second, on the
        # strength of the corner now being lit; mapping was never what was
        # missing, and that claim was wrong.
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


def load_blind(stage: Path, ready: ReadyBudget) -> None:
    """The same HUD again, with no bus at all, until it says so (PLAN D47).

    `LinkPlate` is the one plate the run above cannot light: it is on screen
    exactly while the HUD CANNOT see the bus, so lighting it means taking the
    broker away — and then there are no frames for anything else. Hence a
    second quickshell, the same shipped binary, with `JARVIS_BUS` pointed at a
    path that is not a socket.

    TWO CLAIMS, and the second is the stronger one. That the HUD admits it is
    blind — nothing in this repo had ever watched a real one do that, and
    `core/LinkState.qml`'s grace, the whole judgement in that file, had no gate
    over it at all. And that the other ten stay DARK: every state machine under
    this corner is built to refuse rather than guess, a refusal and a calm
    machine draw the same nothing, and a corner naming exactly `link` is the
    one reading that can tell them apart.

    The environment is this process's own with one variable replaced, which is
    deliberate: everything else about the run — the compositor, the private
    session bus, the pinned bridge in the wrapper — has to be identical, or
    what fails here is not the bus being gone.
    """
    shell = shells.hud_shell()
    binary = need(shell.env)
    # The control, as for every other shell: the screens are whole before it.
    check_zone(shell, "before", up=False)
    env = dict(os.environ, JARVIS_BUS=str(stage / shells.HUD_BLIND_BUS))
    proc = Proc(
        shells.HUD_BLIND_LOG,
        [binary],
        stage / f"{shells.HUD_BLIND_LOG}.log",
        env=env,
    )
    try:
        took = ready.wait(proc)
        log(f"  {shells.HUD_BLIND_LOG}: {ready.spell(took)}, with no bus")
        corner_census(
            shells.HUD_BLIND_LOG,
            proc.logpath,
            list(shells.HUD_PLATES_DARK),
            shells.HUD_BLIND_TIMEOUT_S,
            because=(
                f"a bus that is not there and the HUD's own "
                f"{shells.link_grace_s(shells.link_state_path().read_text('utf-8')):.0f}s "
                "grace"
            ),
        )
        # And this surface really is mapped while it says it — the plate lit,
        # so `visible: selfTest || stack.anyLit` is true and a wl_surface
        # exists. It is still the CONTROL and not a reading about the corner's
        # footprint, for the reason `load()` above states: a zone on a surface
        # anchored to a bare corner is discarded by the compositor, mapped or
        # not (measured in D54; the D44 section in `shells.py`).
        check_zone(shell, "while", up=True)
        log(f"  {shells.HUD_BLIND_LOG}: took no space off any monitor")
        # And then the bus arrives. Same quickshell, same surface, same log.
        relink(stage, proc)
    finally:
        proc.stop()
    check_zone(shell, "after", up=False)


def relink(stage: Path, hud: Proc) -> None:
    """Give the blind HUD a bus, and require it to stop saying NO BUS (D49).

    The dangerous half, and the one D47 could not walk. `core/LinkState.qml`
    does not clear `waited` when the link returns — `blind` goes false because
    `linked` went true — so a `link` plate one edit away from latching forever
    passes the census above exactly as the shipped one does. A permanent NO BUS
    over a healthy machine is the worst fault this corner can have: it teaches
    the user to ignore the one plate that qualifies all the others.

    Nothing has to be restarted and nothing has to be told. The bridge the
    HUD's own wrapper pins retries forever by design, so a broker started on
    the very path it has been failing to reach is the whole intervention — and
    the corner has to go DARK, which `shells.hud_corner_plates` spells
    `nothing` rather than as an absence, for exactly this reading.

    AND THAT READING IS NOT VACUOUS, which is the whole reason this is called
    from inside `load_blind` rather than being a run of its own. An empty corner
    is what a HUD that never lit anything looks like too — but the blind census
    has already required the NEWEST corner line on every monitor to be `link`,
    and `hud_corner_plates` reads the newest. So the only way this passes is a
    line the HUD wrote after the broker arrived.

    The BROKER IS THE SCRIPT'S, arriving in an environment variable like every
    other binary here: realizing something out of the flake is the one thing in
    this harness that is not a measurement, and a driver that could produce a
    broker could produce a different one.

    Its log is quoted into the failure rather than scanned. `tools/qmlerrors.py`
    reads what a QML engine said; a broker's tracing lines under a scanner that
    knows quickshell's prefixes would be graded by a reader of the wrong
    language — so the one place it is worth having is the message a reader of
    this failure needs, which is "did the thing I started even come up".
    """
    bus = stage / shells.HUD_BLIND_BUS
    broker = Proc(
        shells.HUD_RELINK_BROKER_LOG,
        [need("JARVISD_BIN"), "--bus", str(bus)],
        stage / f"{shells.HUD_RELINK_BROKER_LOG}.log",
    )
    try:
        # The socket first, and on its own short budget: a broker that never
        # bound is not a HUD that latched, and the corner's whole wait spent on
        # a socket that was never there would report the wrong repair. Both
        # halves of that are measured — a broker given a bad argument comes back
        # as its own exit and its own stderr, and one that comes up and never
        # binds as the four seconds it was given.
        deadline = time.monotonic() + shells.HUD_RELINK_BUS_TIMEOUT_S
        while not bus.is_socket():
            if broker.p.poll() is not None:
                raise Fail(
                    f"the broker exited with {broker.p.returncode} instead of "
                    f"listening on {bus.name}:\n{broker.tail()}"
                )
            if time.monotonic() > deadline:
                raise Fail(
                    f"the broker never created {bus.name} in "
                    f"{shells.HUD_RELINK_BUS_TIMEOUT_S:.0f}s:\n{broker.tail()}"
                )
            time.sleep(shells.MAPPED_POLL_S)
        log(f"  {shells.HUD_BLIND_LOG}: a broker is now listening on {bus.name}")
        try:
            corner_census(
                shells.HUD_BLIND_LOG,
                hud.logpath,
                list(shells.HUD_PLATES_RELINKED),
                shells.HUD_RELINK_TIMEOUT_S,
                because=(
                    "a bus that is there now and the bridge's own "
                    f"{shells.bridge_max_backoff_s(shells.bridge_path().read_text('utf-8')):.0f}s "
                    "worst-case retry"
                ),
                alive=broker,
            )
        except Fail as exc:
            # The broker's own account, appended: the two ways this fails —
            # a plate that latched on, and a broker that came up and then
            # refused the bridge — are different repairs and read the same
            # from the corner alone.
            raise Fail(f"{exc}\nthe broker said:\n{broker.tail(600)}") from None
        # And then it has to WORK again, which is the other half of the cycle.
        recover(stage, hud, broker)
    finally:
        broker.stop()


def recover(stage: Path, hud: Proc, broker: Proc) -> None:
    """Show the recovered HUD real frames, and require the corner to light (D52).

    The third act, and without it this run walks half a cycle: blind, says so,
    lets go — and stops. The engine that was blind is never shown a frame, and
    the ten-plate census belongs to a DIFFERENT quickshell, one that had a
    broker from the moment it started. So nothing anywhere proved that a HUD
    which survived an outage can still light a plate.

    NOT THE SAME CLAIM TWICE, and the difference is state rather than code.
    This engine has been told the link is DOWN half a dozen times — once per
    failed connect on the bridge's doubling backoff, against the frames run's
    one — and every one of those emptied both of `core/BusModel.qml`'s caches
    and `core/HealthState.qml`'s roster of services. Then `LinkPlate` was the
    only thing on the surface, and then the surface went away entirely
    (`visible: selfTest || stack.anyLit`, and the corner said `nothing`).

    The fault this act is really for is a HUD that is LINKED, SILENT, and
    certain it is fine: the corner going dark is a reading of the SOCKET, since
    `core/LinkState.qml` watches `Bus.linkUp` rather than the traffic, so a HUD
    that came back linked and never accepted another frame passes the census
    above exactly as the shipped one does. Measured — see the D52 section in
    `shells.py` for the injection and what stayed green under it.

    The same publisher and the same census as the frames run, on the broker
    `relink` has already started, against `shells.HUD_PLATES_LIT` itself rather
    than a copy of it: the recovered corner has to be the SAME corner.

    `alive` is the publisher rather than the broker, and it covers both — a
    broker that dies takes the publisher's connection with it, and a publisher
    that cannot publish is the only reason to stop waiting on a corner.
    """
    pub = Proc(
        shells.HUD_RECOVER_LOG,
        [sys.executable, str(PUBLISH)],
        stage / f"{shells.HUD_RECOVER_LOG}.log",
        # The late bus, which is the only thing about this publisher that
        # differs from the frames run's: `jarvis_bus.default_addr()` reads
        # `JARVIS_BUS`, and the one inherited here is the SCRIPT's broker —
        # a publisher that used it would light this corner from a bus the
        # blind HUD has never been able to see.
        env=dict(os.environ, JARVIS_BUS=str(stage / shells.HUD_BLIND_BUS)),
    )
    try:
        pub.wait_for("round 1", shells.HUD_PUBLISH_TIMEOUT_S)
        corner_census(
            shells.HUD_BLIND_LOG,
            hud.logpath,
            list(shells.HUD_PLATES_LIT),
            shells.HUD_RECOVER_TIMEOUT_S,
            because=(
                f"{len(shells.HUD_FRAMES)} frames at "
                f"{1 / shells.HUD_ROUND_S:.0f} Hz on the bus it just got back"
            ),
            alive=pub,
        )
    except Fail as exc:
        raise Fail(f"{exc}\nthe broker said:\n{broker.tail(600)}") from None
    finally:
        pub.stop()


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
    # One budget for the whole run: the cold Qt the generous bound is written
    # against is paid by whichever engine starts first, and by none of the rest
    # (PLAN D53).
    ready = ReadyBudget()
    for shell in shells.SHELLS:
        log(f"shellload: {shell.attr}")
        try:
            load(shell, stage, ready)
        except Fail as exc:
            log(f"  FAILED: {exc}")
            bad += 1
    # And the HUD once more with nothing under it, which is a run rather than
    # a shell: the same binary, the same wait, a bus that is not there. Counted
    # with the shells because it fails the same way and for the same reader.
    log(f"shellload: {shells.HUD_BLIND_LOG}")
    runs = len(shells.SHELLS) + 1
    try:
        load_blind(stage, ready)
    except Fail as exc:
        log(f"  FAILED: {exc}")
        bad += 1
    if bad:
        log(f"\nshellload: {bad} of {runs} runs did not load.")
        return 1
    log(f"\nshellload: all {runs} runs loaded and mapped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
