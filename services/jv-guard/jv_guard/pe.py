"""A read-only, dependency-free reader for a Windows binary's section table.

jv-guard needs to say something about a binary's SHAPE, because that is the
one question a signature engine structurally cannot answer: ClamAV answers
"have I seen these bytes before", and a packer's whole purpose is to make
the answer no. The shape — which sections the CPU will execute, whether
they are also writable, and how compressible their bytes are — survives
repacking, and it is entirely local: nothing here reads a network, and
nothing here leaves the machine (invariant 7).

Deliberately small. No imports resolved, no relocations walked, no
Authenticode verified (see `heuristics.py` for why signedness is NOT a
rung here). Anything it cannot parse confidently it refuses to parse at
all — `read_sections` returns None — because a half-read header is a worse
input to a security decision than no input.
"""

from __future__ import annotations

import dataclasses
import struct
from typing import Optional

# IMAGE_SCN_* section characteristics (winnt.h)
MEM_EXECUTE = 0x20000000
MEM_READ = 0x40000000
MEM_WRITE = 0x80000000

_COFF_SIZE = 20
_SECTION_SIZE = 40
_MAX_SECTIONS = 96  # the loader's own limit; more means malformed


@dataclasses.dataclass(frozen=True)
class Section:
    name: str
    characteristics: int
    virtual_size: int
    raw_offset: int
    raw_size: int

    @property
    def executable(self) -> bool:
        return bool(self.characteristics & MEM_EXECUTE)

    @property
    def writable(self) -> bool:
        return bool(self.characteristics & MEM_WRITE)


def read_sections(head: bytes) -> Optional[list[Section]]:
    """Parse the section table out of the first bytes of a PE file.

    `head` need only contain the headers (a few KiB in practice); the
    section BYTES are read separately and lazily by the caller, because an
    installer can be gigabytes and none of it belongs in memory at once.
    """
    if len(head) < 0x40 or head[:2] != b"MZ":
        return None
    (e_lfanew,) = struct.unpack_from("<I", head, 0x3C)
    if e_lfanew < 0x40 or e_lfanew + 4 + _COFF_SIZE > len(head):
        return None
    if head[e_lfanew : e_lfanew + 4] != b"PE\x00\x00":
        return None

    coff = e_lfanew + 4
    n_sections, _, _, _, opt_size, _ = struct.unpack_from("<HIIIHH", head, coff + 2)
    if not 1 <= n_sections <= _MAX_SECTIONS:
        return None

    opt = coff + _COFF_SIZE
    if opt_size < 2 or opt + opt_size > len(head):
        return None
    (magic,) = struct.unpack_from("<H", head, opt)
    if magic not in (0x10B, 0x20B):  # PE32, PE32+
        return None

    table = opt + opt_size
    if table + n_sections * _SECTION_SIZE > len(head):
        return None

    out: list[Section] = []
    for i in range(n_sections):
        base = table + i * _SECTION_SIZE
        name_bytes, virtual_size, _va, raw_size, raw_offset = struct.unpack_from(
            "<8sIIII", head, base
        )
        (characteristics,) = struct.unpack_from("<I", head, base + 36)
        out.append(
            Section(
                name=name_bytes.rstrip(b"\x00").decode("ascii", "replace"),
                characteristics=characteristics,
                virtual_size=virtual_size,
                raw_offset=raw_offset,
                raw_size=raw_size,
            )
        )
    return out
