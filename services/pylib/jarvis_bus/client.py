"""Asyncio bus client — Python side of services/jarvisd's wire protocol:
length-prefixed (u32 BE) MessagePack; ClientMsg/ServerMsg maps tagged
with "op". See schemas/README.md for envelope conventions.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from typing import Any, Dict, List, Optional

import msgpack

MAX_FRAME = 16 * 1024 * 1024

DEFAULT_UNIX = "/run/jarvis/bus.sock"
DEFAULT_TCP = "127.0.0.1:7451"


def mono_now() -> float:
    """Envelope `ts`: CLOCK_MONOTONIC seconds (see schemas/README.md).
    Python's time.monotonic() is clock_gettime(CLOCK_MONOTONIC) on Linux —
    cross-process comparable there, which is where the bus really runs."""
    return time.monotonic()


def default_addr() -> str:
    env = os.environ.get("JARVIS_BUS")
    if env:
        return env
    return DEFAULT_UNIX if sys.platform != "win32" else DEFAULT_TCP


class BusError(RuntimeError):
    """The broker rejected a publish (invalid envelope)."""


class BusClient:
    def __init__(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, src: str
    ) -> None:
        self._r = reader
        self._w = writer
        self.src = src
        self._seq = 0

    @classmethod
    async def connect(cls, addr: Optional[str] = None, src: str = "py") -> "BusClient":
        addr = addr or default_addr()
        if ":" in addr and not addr.startswith("/"):
            host, port = addr.rsplit(":", 1)
            reader, writer = await asyncio.open_connection(host, int(port))
        else:
            reader, writer = await asyncio.open_unix_connection(addr)
        return cls(reader, writer, src)

    async def close(self) -> None:
        self._w.close()
        try:
            await self._w.wait_closed()
        except (ConnectionError, OSError):
            pass

    async def _send(self, msg: Dict[str, Any]) -> None:
        body = msgpack.packb(msg, use_bin_type=True)
        self._w.write(len(body).to_bytes(4, "big") + body)
        await self._w.drain()

    async def subscribe(self, patterns: List[str]) -> None:
        await self._send({"op": "sub", "patterns": list(patterns)})

    async def unsubscribe(self, patterns: List[str]) -> None:
        await self._send({"op": "unsub", "patterns": list(patterns)})

    async def publish(
        self, topic: str, body: Dict[str, Any], conf: float = 1.0, v: int = 1
    ) -> int:
        """Publish a body, building the envelope. Returns the seq used."""
        seq = self._seq
        self._seq += 1
        await self._send(
            {
                "op": "pub",
                "frame": {
                    "topic": topic,
                    "ts": mono_now(),
                    "seq": seq,
                    "src": self.src,
                    "conf": float(conf),
                    "v": int(v),
                    "body": body,
                },
            }
        )
        return seq

    async def publish_env(self, frame: Dict[str, Any]) -> None:
        """Publish a pre-built envelope verbatim (used by harness/replay)."""
        await self._send({"op": "pub", "frame": frame})

    async def next_event(self) -> Optional[Dict[str, Any]]:
        """Next raw protocol message, or None on EOF."""
        try:
            head = await self._r.readexactly(4)
        except (asyncio.IncompleteReadError, ConnectionError):
            return None
        n = int.from_bytes(head, "big")
        if n > MAX_FRAME:
            raise BusError(f"frame too large: {n}")
        try:
            body = await self._r.readexactly(n)
        except (asyncio.IncompleteReadError, ConnectionError):
            return None
        return msgpack.unpackb(body, raw=False)

    async def next_frame(self) -> Optional[Dict[str, Any]]:
        """Next envelope frame; skips pongs, raises BusError on a broker
        rejection. None on EOF."""
        while True:
            msg = await self.next_event()
            if msg is None:
                return None
            op = msg.get("op")
            if op == "frame":
                return msg["frame"]
            if op == "pong":
                continue
            if op == "err":
                raise BusError(msg.get("msg", "unknown broker error"))
