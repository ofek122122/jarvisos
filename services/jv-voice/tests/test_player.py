"""SoundDevicePlayer must wait for the DEVICE to finish, not a wall-clock
guess. Field bug (2026-09-16): the deadline was computed from the audio
duration alone, but PortAudio->PipeWire takes time to open the stream, so
real playback always outlived the deadline and the finally-stop() clipped
the tail of every utterance ("he always stops talking at the last second").

sounddevice is faked at the module seam — no sound card in CI.
"""

import asyncio
import sys
import types

import numpy as np
import pytest

from jv_voice.player import SoundDevicePlayer


class FakeStream:
    def __init__(self) -> None:
        self.active = False


class FakeSD(types.ModuleType):
    """Mimics the sounddevice module: play() starts LATE and runs LONGER
    than the nominal duration, as the real device does."""

    def __init__(self, extra_latency_s: float) -> None:
        super().__init__("sounddevice")
        self.stream = FakeStream()
        self.extra_latency_s = extra_latency_s
        self.stopped_while_active = False
        self.stop_calls = 0
        self._finish_task = None

    def play(self, audio, rate) -> None:
        self.stream.active = True
        duration = len(audio) / rate + self.extra_latency_s

        async def finish():
            await asyncio.sleep(duration)
            self.stream.active = False

        self._finish_task = asyncio.get_running_loop().create_task(finish())

    def get_stream(self):
        return self.stream

    def stop(self) -> None:
        self.stop_calls += 1
        if self.stream.active:
            self.stopped_while_active = True
        self.stream.active = False
        if self._finish_task:
            self._finish_task.cancel()


@pytest.fixture
def fake_sd(monkeypatch):
    fake = FakeSD(extra_latency_s=0.3)
    monkeypatch.setitem(sys.modules, "sounddevice", fake)
    return fake


async def test_playback_runs_to_device_completion(fake_sd):
    """0.2 s of audio + 0.3 s device latency: the player must NOT cut the
    stream while it is still actively playing."""
    audio = np.zeros(int(0.2 * 22050), dtype=np.float32)
    completed = await SoundDevicePlayer().play(audio, 22050, asyncio.Event())
    assert completed is True
    assert fake_sd.stopped_while_active is False


async def test_abort_stops_immediately(fake_sd):
    fake_sd.extra_latency_s = 60.0  # would "play" for a minute
    audio = np.zeros(int(0.2 * 22050), dtype=np.float32)
    abort = asyncio.Event()

    async def trip():
        await asyncio.sleep(0.15)
        abort.set()

    trip_task = asyncio.create_task(trip())
    completed = await SoundDevicePlayer().play(audio, 22050, abort)
    await trip_task
    assert completed is False
    assert fake_sd.stop_calls >= 1
