"""The `suspicious` rung: a local look at a Windows binary's shape.

The approved policy (2026-08-22) has three rungs — `clean`, `suspicious`,
`blocked` — and until this module existed only two of them could ever be
published. That made the middle rung a description of an intention in
three files (the schema's policy note, jv-compat's override message, the
HUD's `warn` colour) and a live code path in none.

What raises a concern, and why each one is rare enough to mean something:

1. **A packed or encrypted EXECUTABLE section.** Compiled machine code is
   lopsided — a handful of opcodes carry most of the bytes — and measures
   around 6 bits of entropy per byte. Compressed or encrypted data
   measures very nearly 8. Only sections the CPU will EXECUTE are
   measured, which is the difference between a useful rung and a useless
   one: every Inno/NSIS/7z installer on earth carries a high-entropy
   compressed payload, and it lives in a data section or an overlay, not
   in `.text`.
2. **A section that is both writable and executable.** Ordinary compiler
   output never ships W+X; unpacker stubs need it, because they write the
   code they are about to run.
3. **An executable section with no bytes in the file at all.** The UPX0
   shape: hundreds of KiB of virtual address space, nothing on disk,
   filled in at run time. Entropy cannot see this one — there is nothing
   to measure — so it is checked separately.

What deliberately does NOT raise a concern:

- **A missing Authenticode signature.** It was the other obvious
  candidate and it is the wrong one twice over. Nearly every binary this
  machine will ever screen — indie games, mod tools, old installers — is
  unsigned, so the rung would fire on almost everything and `suspicious`
  would come to mean "is a Windows program". And the cheap half of the
  check is worthless anyway: the PRESENCE of a signature blob is not
  trust, only a verified chain is, and verifying one needs a certificate
  store and a policy about who is trusted — a different and much bigger
  piece of work than this module.

This engine is ADVISORY (`kind = HEURISTIC`). It can raise suspicion and
it can never grant trust: see `scan.decide`, where a run with no
authoritative engine is still no verdict at all, however loudly the
shape reads.
"""

from __future__ import annotations

import math
from pathlib import Path

from .pe import Section, read_sections
from .scan import HEURISTIC, ScanHit, ScanReport

# Enough for the DOS stub, the PE headers and a 96-entry section table
# many times over; an installer's remaining gigabytes are never read.
HEADER_WINDOW = 64 * 1024


def shannon_entropy(data: bytes) -> float:
    """Bits of information per byte, 0.0 (one repeated byte) to 8.0
    (every byte equally likely)."""
    if not data:
        return 0.0
    counts = [0] * 256
    for b in data:
        counts[b] += 1
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in counts if c)


def _kib(n: int) -> str:
    return f"{n // 1024} KiB" if n % 1024 == 0 else f"{n} bytes"


class PEHeuristicScanner:
    """Advisory engine: reads shape, never bytes' reputation."""

    name = "pe-shape"
    kind = HEURISTIC

    #: Compiled code sits near 6.0; compressed/encrypted data near 8.0.
    #: /bin/sh on this machine measures 6.13 whole-file (a calibration
    #: test holds that gap open, so this constant cannot quietly drift
    #: down into ordinary binaries).
    ENTROPY_SUSPECT = 7.2

    #: Below this a section is too small for entropy to mean anything —
    #: 256 distinct bytes score a perfect 8.0 for arithmetic reasons.
    MIN_MEASURABLE = 1024

    #: A section with virtual space but no file bytes is only interesting
    #: at a size a real unpacker would need.
    MIN_VIRTUAL_ONLY = 4096

    def __init__(self, sample_bytes: int = 8 * 1024 * 1024) -> None:
        #: Entropy converges long before this; a 200 MB executable
        #: section is not worth 200 MB of reads. When a section IS longer
        #: than the sample, the reason says so rather than implying the
        #: whole thing was measured.
        self.sample_bytes = sample_bytes

    def scan(self, path: Path) -> ScanReport:
        try:
            with path.open("rb") as fh:
                sections = read_sections(fh.read(HEADER_WINDOW))
                if sections is None:
                    # Not a PE, or a header this reader will not guess at.
                    # "Did not run" is the honest answer: `scanned_by` is
                    # the field that makes outages visible, and claiming a
                    # look at a file we never understood would blunt it.
                    return ScanReport(self.name, ran=False, kind=self.kind)
                hits = [
                    ScanHit(self.name, d)
                    for s in sections
                    for d in self._concerns(fh, s)
                ]
        except OSError:
            return ScanReport(self.name, ran=False, kind=self.kind)
        return ScanReport(self.name, ran=True, kind=self.kind, hits=hits)

    def _concerns(self, fh, s: Section) -> list[str]:
        if not s.executable:
            return []
        out: list[str] = []
        if s.raw_size == 0:
            if s.virtual_size >= self.MIN_VIRTUAL_ONLY:
                out.append(
                    f"executable section '{s.name}' has no bytes in the file "
                    f"but claims {_kib(s.virtual_size)} at run time "
                    f"(unpacks itself)"
                )
            return out
        if s.writable:
            out.append(
                f"executable section '{s.name}' is also writable "
                f"(W+X: it can rewrite the code it runs)"
            )
        if s.raw_size >= self.MIN_MEASURABLE:
            read = min(s.raw_size, self.sample_bytes)
            fh.seek(s.raw_offset)
            data = fh.read(read)
            if len(data) >= self.MIN_MEASURABLE:
                e = shannon_entropy(data)
                if e >= self.ENTROPY_SUSPECT:
                    where = (
                        f"over the first {_kib(len(data))} of it"
                        if s.raw_size > len(data)
                        else "over all of it"
                    )
                    out.append(
                        f"executable section '{s.name}' looks packed or "
                        f"encrypted: entropy {e:.2f} of a possible 8.00 "
                        f"{where}"
                    )
        return out
