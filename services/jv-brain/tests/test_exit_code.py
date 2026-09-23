"""jv-brain must exit NON-ZERO when the bus connection drops, so systemd's
Restart=on-failure brings it back. Field bug (2026-09-23): restarting
jarvisd dropped the brain's connection; run()'s frame loop broke on a
None frame and amain returned 0, so systemd saw a clean exit and left the
brain dead — a silent, unrecoverable outage. (Same class as the jv-ears
fix e3be821.) SIGTERM shutdown is a separate path and stays clean.
"""

import asyncio

import jv_brain.main as main_mod


class DeadBus:
    """A bus that connects, then immediately reports the peer gone."""

    @staticmethod
    async def connect(*args, **kwargs):
        return DeadBus()

    async def subscribe(self, topics):
        pass

    async def publish(self, *args, **kwargs):
        pass

    async def next_frame(self):
        return None  # peer closed → run()'s loop ends

    async def close(self):
        pass


def test_bus_drop_exits_nonzero(monkeypatch):
    monkeypatch.setattr(main_mod, "BusClient", DeadBus)
    # no llm needed: warmup runs concurrently and is cancelled when run() ends
    assert asyncio.run(main_mod.amain([])) == 1
