"""Scanner seam + verdict logic.

Verdict policy (approved 2026-08-22):
- signature hit            -> blocked   (never overridable)
- heuristic concern        -> suspicious (overridable via confirm flow)
- all engines clean        -> clean
- NO engine could run      -> NO VERDICT AT ALL. jv-compat's wait times
  out and it fails closed ("I can't screen this right now"). A scanner
  outage must neither grant trust (clean) nor invite an override
  (suspicious) nor permanently taint the file (blocked).

Only hashes ever leave the machine (invariant 7): the optional
VirusTotal client sends a SHA256 lookup, never bytes. Off by default.
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


@dataclasses.dataclass
class ScanHit:
    engine: str
    signature: str


@dataclasses.dataclass
class ScanReport:
    engine: str
    ran: bool
    hit: Optional[ScanHit] = None


class Scanner(Protocol):
    name: str

    def scan(self, path: Path) -> ScanReport: ...


class ClamAVScanner:
    """clamscan subprocess. TODO(machine): CI mocks this (freshclam's DB
    is too heavy there); the real engine is exercised on ares — exit
    item 6 (EICAR blocked, explained out loud)."""

    name = "clamav"

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
            return ScanReport(self.name, ran=True, hit=ScanHit(self.name, sig))
        return ScanReport(self.name, ran=False)  # engine error


class MockScanner:
    """Test scanner: flags paths by predicate."""

    name = "mock"

    def __init__(self, infected: Optional[dict[str, str]] = None, broken: bool = False):
        self.infected = infected or {}
        self.broken = broken

    def scan(self, path: Path) -> ScanReport:
        if self.broken:
            return ScanReport(self.name, ran=False)
        for needle, sig in self.infected.items():
            if needle in str(path) or needle == path.name:
                return ScanReport(self.name, ran=True, hit=ScanHit(self.name, sig))
        return ScanReport(self.name, ran=True)


@dataclasses.dataclass
class Verdict:
    sha256: str
    verdict: str  # clean | suspicious | blocked
    reasons: list[str]
    scanned_by: list[str]


def decide(sha256: str, reports: list[ScanReport]) -> Optional[Verdict]:
    """None = no engine ran; the caller publishes nothing (fail-closed
    happens on the compat side)."""
    ran = [r for r in reports if r.ran]
    if not ran:
        return None
    hits = [r.hit for r in ran if r.hit]
    if hits:
        return Verdict(
            sha256,
            "blocked",
            [f"{h.engine} signature: {h.signature}" for h in hits],
            [r.engine for r in ran],
        )
    return Verdict(sha256, "clean", [], [r.engine for r in ran])
