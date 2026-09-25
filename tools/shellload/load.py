#!/usr/bin/env python3
"""Load every shell under a real quickshell, and say what each one said (D41).

Run by `ops/ralph/shellload.sh`, which realizes the binaries out of the flake
and puts a headless sway and a private session bus around this. Everything this
file decides — which shells, which monitors, which notification — is next door
in `shells.py`, where a test with no compositor can read it.

What it does per shell, and it is deliberately the whole of it: start the
shipped binary, wait for quickshell's own `Configuration Loaded`, give the
notifier its one real message, hold for a beat, stop it. The log goes to
`$JV_SHELLLOAD_STAGE/<attr>.log` and the SCAN is the script's — one
`tools/qmlerrors.py` per shell, because each one needs its own `--prefix`.

THE WAIT IS THE CENSUS. `qmlerrors.py` over an empty file reports "nothing
threw", so a harness that started no engine would grade itself clean forever;
that is why the three staged harnesses had to grow a census in D38. This one
needs none, for the reason `hudscreens.sh` gives: every shell is waited for on
a line quickshell's own logger writes, so a log that was never written, an
engine that died on a syntax error and a binary that is not there are all a
non-zero exit before anything is scanned.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import shells  # noqa: E402


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


# ----------------------------------------------------------------- the run


def load(shell: shells.Shell, stage: Path) -> None:
    binary = need(shell.env)
    logpath = stage / f"{shell.attr}.log"
    proc = Proc(shell.attr, [binary], logpath)
    try:
        took = proc.wait_for(shells.READY, shells.READY_TIMEOUT_S)
        log(f"  {shell.attr}: loaded in {took:.2f} s")
        if shell.wake:
            wake_notifier()
        # A beat, so a binding queued behind the first frame gets the frame.
        time.sleep(shells.HOLD_S)
    finally:
        proc.stop()


def main() -> int:
    stage = Path(need("JV_SHELLLOAD_STAGE"))
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
    log(f"\nshellload: all {len(shells.SHELLS)} shells loaded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
