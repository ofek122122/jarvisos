"""Installer fingerprinting: architecture + installer framework from
file headers alone (no execution, obviously)."""

from __future__ import annotations

import dataclasses
import struct
from pathlib import Path

MSI_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # OLE compound file
# Framework markers searched in the first chunk of PE installers.
NSIS_MARKERS = (b"NullsoftInst", b"Nullsoft.NSIS")
INNO_MARKERS = (b"Inno Setup", b"JR.Inno.Setup")

_MACHINES = {0x014C: "x86", 0x8664: "x64", 0xAA64: "arm64"}

HEAD_BYTES = 1 << 20  # 1 MiB is plenty for markers in real installers


@dataclasses.dataclass
class Fingerprint:
    is_pe: bool
    arch: str  # x86 | x64 | arm64 | unknown
    installer: str  # nsis | inno | msi | unknown


def fingerprint(path: Path) -> Fingerprint:
    head = path.read_bytes()[:HEAD_BYTES]

    if head.startswith(MSI_MAGIC):
        return Fingerprint(is_pe=False, arch="unknown", installer="msi")

    if len(head) < 0x40 or head[:2] != b"MZ":
        return Fingerprint(is_pe=False, arch="unknown", installer="unknown")

    arch = "unknown"
    pe_ok = False
    (pe_off,) = struct.unpack_from("<I", head, 0x3C)
    if pe_off + 6 <= len(head) and head[pe_off : pe_off + 4] == b"PE\0\0":
        pe_ok = True
        (machine,) = struct.unpack_from("<H", head, pe_off + 4)
        arch = _MACHINES.get(machine, "unknown")

    installer = "unknown"
    if any(m in head for m in NSIS_MARKERS):
        installer = "nsis"
    elif any(m in head for m in INNO_MARKERS):
        installer = "inno"

    return Fingerprint(is_pe=pe_ok, arch=arch, installer=installer)


def silent_args(installer: str) -> list[str]:
    """Standard silent switches per framework (blueprint §08)."""
    return {
        "nsis": ["/S"],
        "inno": ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
        "msi": ["/qn", "/norestart"],  # via msiexec /i
    }.get(installer, [])
