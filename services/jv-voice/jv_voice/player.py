"""Playback seam. SoundDevicePlayer on ares (PortAudio -> PipeWire);
FakePlayer for tests, where wall-clock playback would be flaky and a
sound card absent."""

from __future__ import annotations

import asyncio

import numpy as np


class Player:
    async def play(
        self, audio: np.ndarray, rate: int, abort: asyncio.Event
    ) -> bool:  # pragma: no cover - interface
        """Play to completion. Returns False if aborted mid-way."""
        raise NotImplementedError


class SoundDevicePlayer(Player):
    """TODO(machine): exit-checklist items 1 and 3 run through this."""

    async def play(self, audio: np.ndarray, rate: int, abort: asyncio.Event) -> bool:
        import sounddevice as sd

        loop = asyncio.get_running_loop()
        end = loop.time() + len(audio) / rate
        sd.play(audio, rate)
        try:
            while loop.time() < end:
                if abort.is_set():
                    sd.stop()
                    return False
                await asyncio.sleep(0.05)
            return True
        finally:
            sd.stop()


class FakePlayer(Player):
    """Pretends every clip lasts `clip_seconds` — deterministic tests."""

    def __init__(self, clip_seconds: float = 1.0) -> None:
        self.clip_seconds = clip_seconds
        self.played: list[int] = []  # sample counts handed to us
        self.aborted = 0
        self.started = asyncio.Event()  # set when playback actually begins

    async def play(self, audio: np.ndarray, rate: int, abort: asyncio.Event) -> bool:
        self.played.append(len(audio))
        self.started.set()
        loop = asyncio.get_running_loop()
        end = loop.time() + self.clip_seconds
        while loop.time() < end:
            if abort.is_set():
                self.aborted += 1
                return False
            await asyncio.sleep(0.01)
        return True
