"""The VRAM guard's probe, its rung file, and what the heartbeat says
about a reading that never happened.

`pick_rung` has always read `None` as "no usable GPU" and dropped Jarvis
to the CPU rung for the life of that llama-server. The bug these tests
pin is that `None` used to mean FOUR different things — no driver, a
driver that timed out, a driver that exited non-zero, and a driver that
answered `[N/A]` — and the only trace of which was a line on stderr.
"""

import subprocess
from pathlib import Path

import pytest

from jv_brain.config import LADDER, BrainConfig
from jv_brain.launcher import (
    ABSENT,
    MEASURED,
    UNREADABLE,
    VramReading,
    VramUnreadable,
    launch,
    parse_nvidia_smi_vram_mb,
    probe_free_vram_bytes,
    read_rung_file,
    read_vram,
    write_rung_file,
)

GB = 1024**3
MB = 1024**2


# --- the parse -------------------------------------------------------


def test_parse_reads_the_first_gpu():
    """One line per GPU, nounits, MiB. ares has one card."""
    assert parse_nvidia_smi_vram_mb("5432\n") == 5432.0
    assert parse_nvidia_smi_vram_mb("943\n8192\n") == 943.0


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   \n",
        "[N/A]\n",  # the device cannot answer this query
        "[Not Supported]\n",
        "Failed to initialize NVML: Driver/library version mismatch\n",
        "nan\n",  # float() takes it; it is not a measurement
        "inf\n",
        "-1\n",
    ],
)
def test_parse_refuses_everything_that_is_not_a_reading(text: str):
    with pytest.raises(VramUnreadable):
        parse_nvidia_smi_vram_mb(text)


# --- the probe seam --------------------------------------------------


class FakeRun:
    """Stands in for subprocess.run: either raises or returns a result."""

    def __init__(self, *, stdout: str = "", returncode: int = 0, raises=None):
        self.stdout, self.returncode, self.raises = stdout, returncode, raises

    def __call__(self, *a, **kw):
        if self.raises is not None:
            raise self.raises
        return subprocess.CompletedProcess(a[0], self.returncode, self.stdout, "")


def patch_run(monkeypatch, fake: FakeRun) -> None:
    monkeypatch.setattr("jv_brain.launcher.subprocess.run", fake)


def test_no_driver_is_absent_not_a_failure(monkeypatch):
    """A machine with no NVIDIA driver is not impaired; it is a machine
    with no NVIDIA driver. This is the ONLY silent None."""
    patch_run(monkeypatch, FakeRun(raises=FileNotFoundError("nvidia-smi")))
    assert probe_free_vram_bytes() is None


def test_a_measurement_comes_back_in_bytes(monkeypatch):
    patch_run(monkeypatch, FakeRun(stdout="943\n"))
    assert probe_free_vram_bytes() == 943 * MB


@pytest.mark.parametrize(
    "fake",
    [
        FakeRun(raises=subprocess.TimeoutExpired("nvidia-smi", 10)),
        FakeRun(raises=PermissionError("nvidia-smi")),
        FakeRun(stdout="5432\n", returncode=9),  # a number, and a failure
        FakeRun(stdout="[N/A]\n"),
    ],
)
def test_a_driver_that_will_not_answer_is_a_fault(monkeypatch, fake: FakeRun):
    """There IS a card here and it went quiet. That must not look like a
    machine that never had one — it is the difference between a choice
    and a blind guess."""
    patch_run(monkeypatch, fake)
    with pytest.raises(VramUnreadable):
        probe_free_vram_bytes()


# --- the three-way reading -------------------------------------------


def test_read_vram_measured():
    r = read_vram(lambda: 6 * GB)
    assert (r.source, r.free_bytes, r.detail) == (MEASURED, 6 * GB, None)


def test_read_vram_absent():
    r = read_vram(lambda: None)
    assert (r.source, r.free_bytes, r.detail) == (ABSENT, None, None)


def test_read_vram_unreadable_keeps_the_reason():
    def boom():
        raise VramUnreadable("nvidia-smi exited 9")

    r = read_vram(boom)
    assert r.source == UNREADABLE and r.free_bytes is None
    assert "exited 9" in r.detail


def test_every_non_measurement_still_lands_on_the_cpu_rung(tmp_path: Path):
    """Unreadable is not a licence to guess. You cannot allocate VRAM you
    could not count, so the floor holds for both silences."""
    cfg = BrainConfig(models_dir=tmp_path, rung_file=tmp_path / "llm-rung")

    def boom():
        raise VramUnreadable("nvidia-smi did not run")

    for probe in (lambda: None, boom):
        rung = launch(cfg, port=9999, probe=probe, exec_fn=lambda a: None)
        assert rung.index == LADDER[-1].index and not rung.gpu


# --- the rung file, which is the only channel the launcher has --------


def test_rung_file_round_trips_a_measurement(tmp_path: Path):
    p = tmp_path / "llm-rung"
    write_rung_file(p, LADDER[1], VramReading(free_bytes=5800 * MB, source=MEASURED))
    rec = read_rung_file(p)
    assert (rec.index, rec.backend) == (1, "gpu")
    assert rec.vram.source == MEASURED and rec.vram.free_mb == 5800
    assert rec.vram.detail is None


def test_rung_file_tells_the_two_silences_apart(tmp_path: Path):
    """Both write free_vram_mb=-1 — that number is why this field had to
    exist. jv-brain reads this file and nothing else."""
    p = tmp_path / "llm-rung"
    cfg = BrainConfig(models_dir=tmp_path, rung_file=p)

    launch(cfg, port=9999, probe=lambda: None, exec_fn=lambda a: None)
    absent = read_rung_file(p)

    def boom():
        raise VramUnreadable("nvidia-smi exited 9")

    launch(cfg, port=9999, probe=boom, exec_fn=lambda a: None)
    unreadable = read_rung_file(p)

    assert absent.vram.free_mb == unreadable.vram.free_mb == -1
    assert absent.vram.source == ABSENT and absent.vram.detail is None
    assert unreadable.vram.source == UNREADABLE
    assert "exited 9" in unreadable.vram.detail


def test_rung_file_note_survives_an_equals_sign(tmp_path: Path):
    """The reason is nvidia-smi's own words; it can contain anything."""
    p = tmp_path / "llm-rung"
    write_rung_file(
        p, LADDER[-1], VramReading(None, UNREADABLE, "nvidia-smi said 'a=b'\nline2")
    )
    rec = read_rung_file(p)
    assert rec.vram.detail == "nvidia-smi said 'a=b' line2"


def test_missing_rung_file_reads_as_unknown(tmp_path: Path):
    rec = read_rung_file(tmp_path / "nope")
    assert rec.index is None and rec.vram.source == ABSENT


def test_old_rung_file_without_the_field_is_never_read_as_a_fault(tmp_path: Path):
    """A file written before this change says only -1 or a number. It
    must not be able to invent an 'unreadable' that nobody measured."""
    p = tmp_path / "llm-rung"
    p.write_text("rung=0\nlabel=full\nbackend=gpu\nfree_vram_mb=9999\n")
    assert read_rung_file(p).vram.source == MEASURED
    p.write_text("rung=4\nlabel=CPU fallback\nbackend=cpu\nfree_vram_mb=-1\n")
    assert read_rung_file(p).vram.source == ABSENT


# --- what the bus finally hears --------------------------------------


class FakeBus:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict]] = []

    async def publish(self, topic: str, body: dict) -> None:
        self.published.append((topic, body))


def brain(tmp_path: Path, rung_text: str):
    from jv_brain.service import BrainService

    REPO = Path(__file__).resolve().parents[3]
    p = tmp_path / "llm-rung"
    p.write_text(rung_text)
    bus = FakeBus()
    cfg = BrainConfig(rung_file=p, personality_dir=REPO / "personality")
    return bus, BrainService(bus, cfg)


async def test_health_says_so_when_the_brain_chose_its_rung_blind(tmp_path: Path):
    bus, svc = brain(
        tmp_path,
        "rung=4\nlabel=CPU fallback\nbackend=cpu\nfree_vram_mb=-1\n"
        "vram=unreadable\nvram_note=nvidia-smi exited 9\n",
    )
    await svc._health()
    await svc.close()
    topic, body = bus.published[-1]
    assert topic == "sys.health"
    assert body["state"] == "degraded"
    assert "nvidia-smi exited 9" in body["notes"]


async def test_a_blind_launch_does_not_erase_a_worse_note(tmp_path: Path):
    bus, svc = brain(
        tmp_path,
        "rung=4\nbackend=cpu\nfree_vram_mb=-1\nvram=unreadable\nvram_note=timed out\n",
    )
    await svc._health("error", notes="llm error: connection refused")
    await svc.close()
    _, body = bus.published[-1]
    assert body["state"] == "error"
    assert "connection refused" in body["notes"] and "timed out" in body["notes"]


async def test_a_gpu_less_machine_is_not_degraded(tmp_path: Path):
    """No card is a fact about the machine, not an impairment — and on a
    dev box it would otherwise be degraded forever."""
    bus, svc = brain(
        tmp_path, "rung=4\nbackend=cpu\nfree_vram_mb=-1\nvram=absent\n"
    )
    await svc._health()
    await svc.close()
    _, body = bus.published[-1]
    assert body["state"] == "ok" and "notes" not in body


async def test_a_measured_rung_is_quiet(tmp_path: Path):
    bus, svc = brain(
        tmp_path, "rung=1\nlabel=KV q8\nbackend=gpu\nfree_vram_mb=5800\nvram=measured\n"
    )
    await svc._health()
    await svc.close()
    _, body = bus.published[-1]
    assert body["state"] == "ok" and "notes" not in body
    assert body["metrics"]["llm_rung"] == 1.0 and body["metrics"]["llm_gpu"] == 1.0
