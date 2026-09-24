"""Regression for the 2026-09-15 field bug: jv-ears raced PipeWire at
login, PortAudio failed to open the capture stream, the pipeline thread
died — and the process exited 0, so systemd's Restart=on-failure never
fired and the mic stayed silently dead. A dead pipeline must exit 1.

No models, no bus, no mic: bus client and pipeline are faked."""

import asyncio

import pytest

import jv_ears.main as main_mod


class FakeBus:
    async def publish(self, *args, **kwargs):
        pass

    async def subscribe(self, topics):
        pass

    async def next_frame(self):
        await asyncio.Event().wait()  # no frames ever; cancelled at exit

    async def close(self):
        pass


class FakeBusClient:
    @staticmethod
    async def connect(*args, **kwargs):
        return FakeBus()


class FakePipeline:
    """The half of EarsPipeline main.py touches: run it, ask its budgets."""

    def __init__(self, cfg, publish):
        pass

    def budgets(self):
        return {"wake_timeout_s": 8.0}

    def run(self, source):
        pass


class CrashingPipeline(FakePipeline):
    """PortAudio losing the ALSA race, distilled."""

    def run(self, source):
        raise RuntimeError("PaAlsaStream_Configure failed")


class CleanPipeline(FakePipeline):
    """A pipeline that ends normally (e.g. --wav ran out of files)."""


@pytest.fixture(autouse=True)
def no_hardware(monkeypatch):
    monkeypatch.setattr(main_mod, "BusClient", FakeBusClient)
    monkeypatch.setattr(main_mod, "MicSource", lambda *a, **k: object())


def test_pipeline_crash_exits_nonzero(monkeypatch):
    monkeypatch.setattr(main_mod, "EarsPipeline", CrashingPipeline)
    assert asyncio.run(main_mod.amain([])) == 1


def test_clean_pipeline_end_exits_zero(monkeypatch):
    monkeypatch.setattr(main_mod, "EarsPipeline", CleanPipeline)
    assert asyncio.run(main_mod.amain([])) == 0
