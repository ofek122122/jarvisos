"""Scanner seam + verdict logic.

Verdict policy (approved 2026-08-22):
- signature hit            -> blocked   (never overridable)
- heuristic concern        -> suspicious (overridable via confirm flow)
- all engines clean        -> clean
- NO engine could run      -> NO VERDICT AT ALL. jv-compat's wait times
  out and it fails closed ("I can't screen this right now"). A scanner
  outage must neither grant trust (clean) nor invite an override
  (suspicious) nor permanently taint the file (blocked).

Engines are of two KINDS, and the difference is what "no engine could
run" means:

- SIGNATURE engines are authoritative. Their silence is what `clean`
  is made of: ClamAV looked at this file and recognised nothing.
- HEURISTIC engines are advisory (`heuristics.py`). They read a binary's
  SHAPE, which is exactly the question a signature engine cannot answer
  about a file nobody has seen before — but a shape that reads ordinary
  is not evidence of anything. An advisory engine can raise the verdict
  to `suspicious` and can NEVER grant trust.

That distinction is load-bearing rather than tidy. Without it, adding a
heuristic engine would silently delete the fail-closed path: ClamAV goes
down, the shape engine still runs, "no engine ran" stops being true, and
a binary nothing recognised gets published as `clean`. So `decide()`
requires an authoritative engine to have run before it will say anything
at all — and when none did, a loud heuristic concern is still no verdict,
because the approved policy's outage rule says an outage must not invite
an override either.

Only hashes ever leave the machine (invariant 7): the optional
VirusTotal client sends a SHA256 lookup, never bytes. Off by default.
The shape engine sends nothing anywhere — it reads local bytes.
"""

from __future__ import annotations

import dataclasses
import hashlib
import subprocess
from pathlib import Path
from typing import Optional, Protocol


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


#: An engine whose silence means "clean". See the module docstring.
SIGNATURE = "signature"
#: An engine that may raise suspicion and may never grant trust.
HEURISTIC = "heuristic"


@dataclasses.dataclass
class ScanHit:
    engine: str
    #: What was found, in the engine's own words — a signature name for a
    #: signature engine, a described concern for a heuristic one. Spoken
    #: out loud on request, so it is written for a person.
    detail: str


@dataclasses.dataclass
class ScanReport:
    engine: str
    ran: bool
    #: One engine can have several things to say about one file (a
    #: packer stub is usually W+X *and* high-entropy), and each is a
    #: separate reason the user hears.
    hits: list[ScanHit] = dataclasses.field(default_factory=list)
    #: Defaults to authoritative: every engine that predates the
    #: heuristic seam is a signature engine and stays one untouched.
    kind: str = SIGNATURE


class Scanner(Protocol):
    name: str
    kind: str

    def scan(self, path: Path) -> ScanReport: ...


class ClamAVScanner:
    """clamscan subprocess. TODO(machine): CI mocks this (freshclam's DB
    is too heavy there); the real engine is exercised on ares — exit
    item 6 (EICAR blocked, explained out loud)."""

    name = "clamav"
    kind = SIGNATURE

    def scan(self, path: Path) -> ScanReport:
        try:
            out = subprocess.run(
                ["clamscan", "--no-summary", str(path)],
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired):
            return ScanReport(self.name, ran=False)
        if out.returncode == 0:
            return ScanReport(self.name, ran=True)
        if out.returncode == 1:  # FOUND
            sig = "unknown"
            for line in out.stdout.splitlines():
                if line.endswith("FOUND"):
                    sig = line.split(":", 1)[1].strip().removesuffix("FOUND").strip()
            return ScanReport(self.name, ran=True, hits=[ScanHit(self.name, sig)])
        return ScanReport(self.name, ran=False)  # engine error


class MockScanner:
    """Test scanner: flags paths by predicate."""

    name = "mock"
    kind = SIGNATURE

    def __init__(self, infected: Optional[dict[str, str]] = None, broken: bool = False):
        self.infected = infected or {}
        self.broken = broken

    def scan(self, path: Path) -> ScanReport:
        if self.broken:
            return ScanReport(self.name, ran=False)
        for needle, sig in self.infected.items():
            if needle in str(path) or needle == path.name:
                return ScanReport(self.name, ran=True, hits=[ScanHit(self.name, sig)])
        return ScanReport(self.name, ran=True)


@dataclasses.dataclass
class Verdict:
    sha256: str
    verdict: str  # clean | suspicious | blocked
    reasons: list[str]
    scanned_by: list[str]


def decide(sha256: str, reports: list[ScanReport]) -> Optional[Verdict]:
    """None = no AUTHORITATIVE engine ran; the caller publishes nothing
    (fail-closed happens on the compat side). A heuristic engine that
    ran, with or without concerns, cannot change that answer."""
    ran = [r for r in reports if r.ran]
    if not any(r.kind == SIGNATURE for r in ran):
        return None
    scanned_by = [r.engine for r in ran]

    signature_hits = [h for r in ran if r.kind == SIGNATURE for h in r.hits]
    if signature_hits:
        return Verdict(
            sha256,
            "blocked",
            [f"{h.engine} signature: {h.detail}" for h in signature_hits],
            scanned_by,
        )

    concerns = [h for r in ran if r.kind == HEURISTIC for h in r.hits]
    if concerns:
        return Verdict(
            sha256,
            "suspicious",
            [f"{h.engine}: {h.detail}" for h in concerns],
            scanned_by,
        )

    return Verdict(sha256, "clean", [], scanned_by)
