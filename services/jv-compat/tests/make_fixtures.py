"""Synthesize minimal installer HEADERS for fingerprint tests — headers
only, never real payloads (BRIEF-phase2 §4). Deterministic; committed
under tests/fixtures/."""

from __future__ import annotations

import struct
from pathlib import Path

FIX = Path(__file__).resolve().parent / "fixtures"


def pe_header(machine: int, marker: bytes = b"") -> bytes:
    """A minimal-but-valid-enough PE: MZ, e_lfanew at 0x3C -> 'PE\\0\\0'
    + machine word, then a marker padded into the first chunk."""
    buf = bytearray(b"MZ" + b"\x00" * 0x3E)
    pe_off = 0x80
    struct.pack_into("<I", buf, 0x3C, pe_off)
    buf += b"\x00" * (pe_off - len(buf))
    buf += b"PE\x00\x00" + struct.pack("<H", machine)
    buf += b"\x00" * 64
    if marker:
        buf += marker + b"\x00" * 32
    return bytes(buf)


def main() -> None:
    FIX.mkdir(exist_ok=True)
    (FIX / "nsis-x64.exe").write_bytes(pe_header(0x8664, b"NullsoftInst"))
    (FIX / "inno-x86.exe").write_bytes(pe_header(0x014C, b"Inno Setup Setup Data"))
    (FIX / "plain-x64.exe").write_bytes(pe_header(0x8664, b"just an app"))
    # MSI = OLE compound file magic
    (FIX / "installer.msi").write_bytes(
        b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 512
    )
    # not an installer at all
    (FIX / "notpe.txt").write_bytes(b"hello, not a program\n")
    print(f"wrote fixtures to {FIX}")


if __name__ == "__main__":
    main()
