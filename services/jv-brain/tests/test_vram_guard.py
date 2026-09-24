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

from jv_brain.config import LADDER, SAFETY_MARGIN_BYTES, BrainConfig
from jv_brain.launcher import (
    ABSENT,
    MEASURED,
    UNREADABLE,
    VramReading,
    VramUnreadable,
    describe_rung,
    gpu_floor_bytes,
    gpu_floor_mb,
    launch,
    parse_nvidia_smi_vram_mb,
    pick_rung,
    probe_free_vram_bytes,
    read_rung_file,
    read_vram,
    rung_budget_bytes,
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


# --- the rung, in words ----------------------------------------------
#
# `llm_rung=4.0` is a number that only means something to a reader who has
# the ladder memorised. The launcher writes the one human-readable string
# there is (`label=`), and until now nobody read it.


def test_the_record_carries_the_label_the_launcher_wrote(tmp_path: Path):
    p = tmp_path / "llm-rung"
    write_rung_file(p, LADDER[-1], VramReading(943 * MB, MEASURED))
    assert read_rung_file(p).label == LADDER[-1].label == "CPU fallback"


def test_a_file_without_a_label_never_invents_one(tmp_path: Path):
    """Written before `label=` existed, or torn. An empty label is the
    only honest answer; `describe_rung` must fall back to the backend."""
    p = tmp_path / "llm-rung"
    p.write_text("rung=4\nbackend=cpu\nfree_vram_mb=943\nvram=measured\n")
    rec = read_rung_file(p)
    assert rec.label == ""
    assert describe_rung(rec) == "rung 4 (cpu)"


def test_describe_rung_says_the_rung_and_its_label(tmp_path: Path):
    p = tmp_path / "llm-rung"
    write_rung_file(p, LADDER[1], VramReading(5800 * MB, MEASURED))
    assert describe_rung(read_rung_file(p)) == "rung 1 (KV q8)"


def test_describe_rung_has_no_words_for_a_rung_it_never_read(tmp_path: Path):
    assert describe_rung(read_rung_file(tmp_path / "nope")) == ""


async def test_a_cpu_rung_on_a_machine_with_a_card_is_degraded_and_says_why(
    tmp_path: Path,
):
    """ares today: a healthy GTX 1660 SUPER, 943 MiB of its 6 GB free
    because the desktop and a browser own the rest, and an 8B Q4 brain
    that therefore runs on the CPU. `sys.health`'s own schema names this
    exact case as the example of 'degraded' — and until now jv-brain
    published `ok` and a number nobody can decode."""
    bus, svc = brain(
        tmp_path,
        "rung=4\nlabel=CPU fallback\nbackend=cpu\nfree_vram_mb=943\nvram=measured\n",
    )
    await svc._health()
    await svc.close()
    _, body = bus.published[-1]
    assert body["state"] == "degraded"
    notes = body["notes"]
    assert "rung 4 (CPU fallback)" in notes
    assert "slow" in notes, "the consequence, not just the rung"
    assert "943" in notes, "why it fell — the reading it fell on"


async def test_the_blind_note_now_says_which_rung_too(tmp_path: Path):
    bus, svc = brain(
        tmp_path,
        "rung=4\nlabel=CPU fallback\nbackend=cpu\nfree_vram_mb=-1\n"
        "vram=unreadable\nvram_note=nvidia-smi exited 9\n",
    )
    await svc._health()
    await svc.close()
    _, body = bus.published[-1]
    assert body["state"] == "degraded"
    assert "rung 4 (CPU fallback)" in body["notes"]
    assert "nvidia-smi exited 9" in body["notes"]
    assert "943" not in body["notes"], "there is no reading to quote"
    assert "-1" not in body["notes"], "and -1 is not one either"


async def test_a_gpu_less_machine_still_says_nothing(tmp_path: Path):
    """No card is not an impairment, so there is no finding to word —
    the CPU rung was the whole ladder, not a fall down it."""
    bus, svc = brain(tmp_path, "rung=4\nlabel=CPU fallback\nbackend=cpu\nvram=absent\n")
    await svc._health()
    await svc.close()
    _, body = bus.published[-1]
    assert body["state"] == "ok" and "notes" not in body


async def test_a_gpu_rung_is_still_quiet_even_though_it_has_a_label(tmp_path: Path):
    """Rungs 1-3 gave something up, but they gave it up on purpose and
    the brain is still on the card. A note every 5 s for a ladder working
    as designed teaches a reader to skip the field the fault will appear
    in."""
    bus, svc = brain(
        tmp_path, "rung=2\nlabel=ctx 2k\nbackend=gpu\nfree_vram_mb=3000\nvram=measured\n"
    )
    await svc._health()
    await svc.close()
    _, body = bus.published[-1]
    assert body["state"] == "ok" and "notes" not in body


async def test_a_worse_note_still_comes_first_and_keeps_the_worse_state(
    tmp_path: Path,
):
    bus, svc = brain(
        tmp_path,
        "rung=4\nlabel=CPU fallback\nbackend=cpu\nfree_vram_mb=943\nvram=measured\n",
    )
    await svc._health("error", notes="llm error: connection refused")
    await svc.close()
    _, body = bus.published[-1]
    assert body["state"] == "error"
    assert body["notes"].startswith("llm error: connection refused")
    assert "rung 4 (CPU fallback)" in body["notes"]


def test_a_negative_rung_is_not_a_rung(tmp_path: Path):
    """`-1` is the parser's sentinel for a file with no `rung=` line. The
    launcher writes 0..4 and nothing else, so there are no words for it."""
    p = tmp_path / "llm-rung"
    p.write_text("backend=cpu\nfree_vram_mb=943\nvram=measured\n")
    rec = read_rung_file(p)
    assert rec.index == -1 and describe_rung(rec) == ""


async def test_an_unrecorded_rung_still_reports_the_fall(tmp_path: Path):
    bus, svc = brain(tmp_path, "backend=cpu\nfree_vram_mb=943\nvram=measured\n")
    await svc._health()
    await svc.close()
    _, body = bus.published[-1]
    assert body["state"] == "degraded"
    assert "unrecorded rung" in body["notes"] and "943" in body["notes"]
    assert "rung ?" not in body["notes"]


def test_a_padded_label_arrives_as_one_clean_line(tmp_path: Path):
    """`jv health` renders notes as one line of a table, so the label is
    flattened on the way in as well as on the way out."""
    p = tmp_path / "llm-rung"
    p.write_text("rung=4\nlabel=  CPU  fallback  \nbackend=cpu\n")
    assert read_rung_file(p).label == "CPU fallback"


async def test_a_hand_edited_rung_file_still_reports_the_fall(tmp_path: Path):
    """`backend` and `vram` decide a state now, so ` cpu` must not read
    as a word that is neither cpu nor gpu and answers 'no' to every
    question asked of it."""
    bus, svc = brain(
        tmp_path, "rung = 4\nbackend = cpu\nfree_vram_mb = 943\nvram = measured\n"
    )
    await svc._health()
    await svc.close()
    _, body = bus.published[-1]
    assert body["state"] == "degraded" and "943" in body["notes"]


# --- what a GPU rung would cost --------------------------------------
#
# B45. The HUD can quote the free-VRAM figure (B40) and cannot judge it:
# the ladder's requirements live in this package and invariant 1 says a
# consumer may not know them. So the one sentence a reader still has to
# supply — "5 GiB free and STILL on the CPU?" — is the one nobody can
# check, and on this ladder it is wrong: the cheapest GPU rung needs
# 5424 MiB, which is 5.3 GiB of a 6 GiB card. Publishing the floor is
# how the HUD stops guessing.


def test_the_floor_is_the_cheapest_gpu_rung_plus_the_margin():
    """`pick_rung` takes the FIRST rung that fits, so the last GPU rung
    is the cheapest one — the floor under the whole GPU half of the
    ladder. Taken as a min() rather than as LADDER[-2], so a reordered
    ladder cannot silently publish a figure that is not the floor."""
    cheapest = min(rung_budget_bytes(r) for r in LADDER if r.gpu)
    assert gpu_floor_bytes() == cheapest + SAFETY_MARGIN_BYTES


def test_the_floor_is_the_figure_pick_rung_actually_turns_on():
    """The number is only worth publishing if it is the same threshold
    the launcher will apply on the next launch — one byte below it is a
    CPU brain, and at it the GPU half of the ladder opens."""
    floor = gpu_floor_bytes()
    assert floor is not None
    assert pick_rung(floor).gpu, "at the floor a GPU rung must be reachable"
    assert not pick_rung(floor - 1).gpu, "below it the ladder falls to the CPU"


def test_the_floor_in_mib_rounds_up_and_never_claims_an_early_fit():
    """jv-context measures free VRAM in whole MiB, so the floor has to
    be whole MiB too — rounded UP, because a figure rounded down is a
    HUD saying "it fits now" about a launch that would fall straight
    back to the CPU."""
    floor_mb = gpu_floor_mb()
    assert floor_mb == 5424, "Qwen3-8B Q4_K_S, 2k ctx, q8 KV + overhead + margin"
    assert pick_rung(floor_mb * MB).gpu
    assert not pick_rung((floor_mb - 1) * MB).gpu


def test_a_ladder_with_no_gpu_rung_has_no_floor():
    """There is no VRAM figure that would buy a GPU brain, so there is
    no number to publish — None, never 0, which would read as "any card
    at all will do"."""
    cpu_only = tuple(r for r in LADDER if not r.gpu)
    assert gpu_floor_bytes(cpu_only) is None
    assert gpu_floor_mb(cpu_only) is None


async def test_a_cpu_rung_publishes_what_a_gpu_rung_would_need(tmp_path: Path):
    """ares: 943 MiB free of 6144, brain on the floor. The heartbeat now
    carries both halves of the comparison, so the reader (and the HUD)
    can tell "the card is busy" from "the card is free and nobody has
    restarted jv-llm"."""
    bus, svc = brain(
        tmp_path,
        "rung=4\nlabel=CPU fallback\nbackend=cpu\nfree_vram_mb=943\nvram=measured\n",
    )
    await svc._health()
    await svc.close()
    _, body = bus.published[-1]
    assert body["metrics"]["llm_gpu"] == 0.0
    assert body["metrics"]["llm_gpu_floor_mb"] == 5424.0


async def test_a_blind_fall_publishes_the_floor_too(tmp_path: Path):
    """The launch was blind; the card is not. Whatever nvidia-smi would
    not say at launch, a live reading can be compared with the floor
    now."""
    bus, svc = brain(
        tmp_path,
        "rung=4\nlabel=CPU fallback\nbackend=cpu\nfree_vram_mb=-1\n"
        "vram=unreadable\nvram_note=nvidia-smi exited 9\n",
    )
    await svc._health()
    await svc.close()
    _, body = bus.published[-1]
    assert body["metrics"]["llm_gpu_floor_mb"] == 5424.0


async def test_a_gpu_rung_publishes_no_floor(tmp_path: Path):
    """Nothing is waiting on the card. A requirement already met,
    restated every 5 s, is the all-day gauge nobody reads."""
    bus, svc = brain(
        tmp_path, "rung=1\nlabel=KV q8\nbackend=gpu\nfree_vram_mb=5800\nvram=measured\n"
    )
    await svc._health()
    await svc.close()
    _, body = bus.published[-1]
    assert "llm_gpu_floor_mb" not in body["metrics"]


async def test_a_machine_with_no_card_publishes_no_floor(tmp_path: Path):
    """There is no card to free. A floor here would invite a reader to
    go looking for VRAM that this machine has never had — the same
    invented shortage VramState refuses to draw (B40)."""
    bus, svc = brain(tmp_path, "rung=4\nlabel=CPU fallback\nbackend=cpu\nvram=absent\n")
    await svc._health()
    await svc.close()
    _, body = bus.published[-1]
    assert "llm_gpu_floor_mb" not in body.get("metrics", {})


async def test_a_brain_that_has_read_no_rung_file_publishes_no_floor(tmp_path: Path):
    """llama-server has not said anything yet. A floor without a rung is
    a requirement for a launch nobody can describe."""
    bus, svc = brain(tmp_path, "")
    await svc._health()
    await svc.close()
    _, body = bus.published[-1]
    assert "llm_gpu_floor_mb" not in body.get("metrics", {})


async def test_the_fall_says_how_much_the_gpu_needed(tmp_path: Path):
    """`jv health` shows notes and not metrics, so the terminal reader
    gets the comparison in words or not at all."""
    bus, svc = brain(
        tmp_path,
        "rung=4\nlabel=CPU fallback\nbackend=cpu\nfree_vram_mb=943\nvram=measured\n",
    )
    await svc._health()
    await svc.close()
    _, body = bus.published[-1]
    assert "943 MiB VRAM free at launch, 5424 needed" in body["notes"]


async def test_the_blind_note_quotes_no_requirement(tmp_path: Path):
    """A requirement is only a finding next to a reading, and a blind
    launch has none to put beside it."""
    bus, svc = brain(
        tmp_path,
        "rung=4\nlabel=CPU fallback\nbackend=cpu\nfree_vram_mb=-1\n"
        "vram=unreadable\nvram_note=nvidia-smi exited 9\n",
    )
    await svc._health()
    await svc.close()
    _, body = bus.published[-1]
    assert "5424" not in body["notes"], "nothing to compare it with"
