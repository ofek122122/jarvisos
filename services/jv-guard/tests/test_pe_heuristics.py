"""jv-guard: the `suspicious` rung.

Until now `decide()` could only ever say `clean` or `blocked` — the
approved policy's middle rung existed in three files (the schema's policy
note, jv-compat's override message, the HUD's `warn` colour) and in no
code path. These tests are the rung: a local, hash-free look at a Windows
binary's SHAPE, and the authority rule that keeps that look from ever
being mistaken for trust.
"""

import math
import os
import struct
from pathlib import Path

import pytest

from jv_guard.heuristics import PEHeuristicScanner, shannon_entropy
from jv_guard.pe import read_sections
from jv_guard.scan import HEURISTIC, SIGNATURE, MockScanner, ScanHit, ScanReport, decide

# IMAGE_SCN_* characteristics
CNT_CODE = 0x00000020
MEM_EXECUTE = 0x20000000
MEM_READ = 0x40000000
MEM_WRITE = 0x80000000

TEXT = CNT_CODE | MEM_EXECUTE | MEM_READ
DATA = MEM_READ | MEM_WRITE


def build_pe(sections, *, pe32plus: bool = True) -> bytes:
    """A minimal but real PE: DOS stub, PE signature, COFF + optional
    header, a section table, and the sections' bytes at file alignment.
    `sections` is [(name, characteristics, raw_bytes, virtual_size)];
    virtual_size None means "same as raw".
    """
    n = len(sections)
    opt_size = 240 if pe32plus else 224
    e_lfanew = 0x80
    headers_end = e_lfanew + 4 + 20 + opt_size + 40 * n
    raw_base = (headers_end + 511) // 512 * 512

    dos = bytearray(b"\x00" * e_lfanew)
    dos[0:2] = b"MZ"
    dos[0x3C:0x40] = struct.pack("<I", e_lfanew)

    coff = struct.pack(
        "<HHIIIHH", 0x8664 if pe32plus else 0x014C, n, 0, 0, 0, opt_size, 0x0022
    )

    opt = bytearray(b"\x00" * opt_size)
    opt[0:2] = struct.pack("<H", 0x20B if pe32plus else 0x10B)
    nrva = 108 if pe32plus else 92
    opt[nrva : nrva + 4] = struct.pack("<I", 16)

    table = b""
    blobs = b""
    off = raw_base
    va = 0x1000
    for name, chars, raw, vsize in sections:
        rsize = len(raw)
        padded = raw + b"\x00" * ((-rsize) % 512)
        table += struct.pack(
            "<8sIIIIIIHHI",
            name.encode()[:8],
            vsize if vsize is not None else rsize,
            va,
            rsize,
            off if rsize else 0,
            0,
            0,
            0,
            0,
            chars,
        )
        blobs += padded
        off += len(padded)
        va += 0x10000

    head = bytes(dos) + b"PE\x00\x00" + coff + bytes(opt) + table
    return head + b"\x00" * (raw_base - len(head)) + blobs


def compiled_code(n: int) -> bytes:
    """Byte soup with the lopsided histogram real machine code has (lots
    of 0x00/0x48/0xE8, few of everything else). Entropy well under the
    threshold — the point is that ordinary code must never trip it."""
    common = b"\x48\x89\xe5\x00\x00\xff\x15\x00\x48\x8b\x00\x00\xe8\x00\x00\x00"
    out = bytearray()
    i = 0
    while len(out) < n:
        out += common
        out.append((i * 7) % 32)  # a little tail variety, still narrow
        i += 1
    return bytes(out[:n])


def packed(n: int) -> bytes:
    """Compressed/encrypted payload: flat histogram, entropy ~8."""
    return os.urandom(n)


# ------------------------------------------------------------- entropy


def test_entropy_of_one_repeated_byte_is_zero():
    assert shannon_entropy(b"\x00" * 4096) == 0.0


def test_entropy_of_nothing_is_zero():
    assert shannon_entropy(b"") == 0.0


def test_entropy_of_random_bytes_is_near_the_maximum():
    assert shannon_entropy(packed(65536)) > 7.9


def test_entropy_of_real_compiled_code_is_far_below_the_threshold():
    """Calibration, not a unit: the threshold is only worth anything if
    an ordinary compiled binary sits nowhere near it. /bin/sh on this
    machine is the nearest real sample."""
    sh = Path(os.path.realpath("/bin/sh"))
    if not sh.is_file() or sh.stat().st_size < 100_000:
        pytest.skip("no sizeable /bin/sh to calibrate against")
    e = shannon_entropy(sh.read_bytes())
    assert e < PEHeuristicScanner.ENTROPY_SUSPECT, f"/bin/sh entropy {e:.3f}"


# --------------------------------------------------------- PE parsing


def test_reads_section_names_and_flags():
    pe = build_pe([(".text", TEXT, compiled_code(2048), None),
                   (".data", DATA, b"\x01" * 512, None)])
    secs = read_sections(pe)
    assert [s.name for s in secs] == [".text", ".data"]
    assert secs[0].executable and not secs[0].writable
    assert secs[1].writable and not secs[1].executable
    assert secs[0].raw_size == 2048


def test_reads_a_pe32_as_well_as_a_pe32plus():
    pe = build_pe([(".text", TEXT, compiled_code(2048), None)], pe32plus=False)
    secs = read_sections(pe)
    assert [s.name for s in secs] == [".text"]


def test_not_a_pe_is_refused_rather_than_guessed():
    assert read_sections(b"") is None
    assert read_sections(b"#!/bin/sh\necho hi\n" * 100) is None
    assert read_sections(b"MZ" + b"\x00" * 4096) is None  # DOS stub, no PE header


def test_a_truncated_header_is_refused():
    pe = build_pe([(".text", TEXT, compiled_code(2048), None)])
    assert read_sections(pe[:100]) is None


# -------------------------------------------------------- the concerns


def scan_pe(tmp_path, sections, **kw):
    f = tmp_path / "app.exe"
    f.write_bytes(build_pe(sections))
    return PEHeuristicScanner(**kw).scan(f)


def test_an_ordinary_binary_raises_nothing(tmp_path):
    r = scan_pe(tmp_path, [(".text", TEXT, compiled_code(8192), None),
                           (".data", DATA, b"\x01" * 2048, None)])
    assert r.ran and r.hits == []
    assert r.kind == HEURISTIC


def test_a_packed_code_section_is_a_concern(tmp_path):
    r = scan_pe(tmp_path, [(".text", TEXT, packed(8192), None)])
    assert len(r.hits) == 1
    assert ".text" in r.hits[0].detail and "packed" in r.hits[0].detail


def test_a_high_entropy_DATA_section_is_not_a_concern(tmp_path):
    """The false positive that would have made this rung worthless: every
    Inno/NSIS/7z installer carries its compressed payload in a non-code
    section. Only sections the CPU will execute are measured."""
    r = scan_pe(tmp_path, [(".text", TEXT, compiled_code(8192), None),
                           (".rsrc", MEM_READ, packed(65536), None)])
    assert r.ran and r.hits == []


def test_a_tiny_executable_section_is_not_measured(tmp_path):
    """A 256-byte section of distinct bytes scores a perfect 8.0 for
    arithmetic reasons, not suspicious ones."""
    r = scan_pe(tmp_path, [(".text", TEXT, bytes(range(256)), None)])
    assert r.ran and r.hits == []


def test_a_writable_executable_section_is_a_concern(tmp_path):
    r = scan_pe(tmp_path, [(".text", TEXT | MEM_WRITE, compiled_code(8192), None)])
    assert len(r.hits) == 1
    assert "writable" in r.hits[0].detail


def test_an_executable_section_with_no_bytes_in_the_file_is_a_concern(tmp_path):
    """The UPX0 shape: 256 KiB of virtual space, nothing on disk, filled
    in at run time. Entropy cannot see it — there is nothing to measure."""
    r = scan_pe(tmp_path, [("UPX0", TEXT, b"", 0x40000),
                           ("UPX1", TEXT | MEM_WRITE, packed(8192), None)])
    details = " | ".join(h.detail for h in r.hits)
    assert "UPX0" in details and "no bytes" in details
    assert len(r.hits) == 3  # UPX0 empty, UPX1 writable, UPX1 packed


def test_concerns_name_the_engine_that_raised_them(tmp_path):
    r = scan_pe(tmp_path, [(".text", TEXT, packed(8192), None)])
    assert r.hits[0].engine == r.engine == "pe-shape"


def test_a_long_section_is_sampled_and_the_reason_says_so(tmp_path):
    r = scan_pe(tmp_path, [(".text", TEXT, packed(16384), None)], sample_bytes=4096)
    assert len(r.hits) == 1
    assert "first 4 KiB" in r.hits[0].detail


def test_a_non_pe_file_means_this_engine_did_not_run(tmp_path):
    """`scanned_by` is 'engines that actually ran'. A shell script is not
    something this engine has an opinion about, and saying it ran would
    be an overclaim in exactly the field built to make outages visible."""
    f = tmp_path / "notes.txt"
    f.write_bytes(b"hello, this is not a windows binary\n" * 100)
    r = PEHeuristicScanner().scan(f)
    assert not r.ran and r.hits == []


def test_an_unreadable_file_means_this_engine_did_not_run(tmp_path):
    r = PEHeuristicScanner().scan(tmp_path / "gone.exe")
    assert not r.ran


# ------------------------------------------------- the authority rule


def sig_clean(engine="clamav"):
    return ScanReport(engine, ran=True, kind=SIGNATURE)


def heur(*details, ran=True):
    return ScanReport(
        "pe-shape", ran=ran, kind=HEURISTIC,
        hits=[ScanHit("pe-shape", d) for d in details],
    )


def test_a_heuristic_concern_under_a_clean_signature_scan_is_suspicious():
    v = decide("abc", [sig_clean(), heur("packed code section '.text'")])
    assert v.verdict == "suspicious"
    assert v.reasons == ["pe-shape: packed code section '.text'"]
    assert v.scanned_by == ["clamav", "pe-shape"]


def test_a_signature_hit_outranks_every_heuristic():
    v = decide("abc", [
        ScanReport("clamav", ran=True, hits=[ScanHit("clamav", "Win.Trojan.X")]),
        heur("packed code section '.text'"),
    ])
    assert v.verdict == "blocked"
    assert v.reasons == ["clamav signature: Win.Trojan.X"]


def test_a_heuristic_alone_can_never_grant_clean():
    """The regression this rung could have introduced: if the heuristic
    engine counted as an engine, a ClamAV outage would stop being 'no
    engine ran' and start being 'clean' — fail-closed silently deleted by
    a feature. Advisory engines cannot answer the question ClamAV was
    asked."""
    assert decide("abc", [ScanReport("clamav", ran=False), heur()]) is None


def test_a_heuristic_concern_during_a_signature_outage_is_still_no_verdict():
    """Approved policy, verbatim: an outage must neither grant trust nor
    invite an override. Publishing `suspicious` here would invite one."""
    assert decide("abc", [ScanReport("clamav", ran=False),
                          heur("packed code section '.text'")]) is None


def test_both_engines_clean_is_clean_and_says_who_looked():
    v = decide("abc", [sig_clean(), heur()])
    assert v.verdict == "clean"
    assert v.reasons == []
    assert v.scanned_by == ["clamav", "pe-shape"]


def test_a_heuristic_that_could_not_run_does_not_darken_a_clean_verdict():
    v = decide("abc", [sig_clean(), heur(ran=False)])
    assert v.verdict == "clean"
    assert v.scanned_by == ["clamav"]


def test_the_default_scanner_kind_is_authoritative():
    """Every pre-existing ScanReport in the tree is a signature engine and
    must stay one without being edited."""
    assert ScanReport("clamav", ran=True).kind == SIGNATURE
    assert MockScanner().scan(Path("/nonexistent")).kind == SIGNATURE
